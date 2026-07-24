"""CMP-B Stage C+D research driver — opportunistic Form-4 baseline (PRD #79).

Sequential by construction (step3 OOM law): reuse CFOB tape/SEP loaders; do not
hold two multi-GB objects at once.

Stage E1 (returns) is **refused** unless both ``--e1`` and a recorded human-go
are present. This PRD authorises C+D only. ``capital_go`` is always false.

Usage:
    uv run python fixtures/real-continuous/reports/research_cmp.py --pull-only
    uv run python fixtures/real-continuous/reports/research_cmp.py --measure-only --write-docs
    uv run python fixtures/real-continuous/reports/research_cmp.py --synthetic --write-docs
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

# Sibling driver import (research_cfob) when executed as a script.
_REPORTS_DIR = Path(__file__).resolve().parent
if str(_REPORTS_DIR) not in sys.path:
    sys.path.insert(0, str(_REPORTS_DIR))

from invest.application.cfob import (  # noqa: E402
    QualificationCounts,
    amendment_collision_count,
    evaluate_universe_membership,
    map_purchases_by_cik,
)
from invest.application.cmp_form4 import (  # noqa: E402
    PROTOCOL,
    ClassificationCounts,
    CmpClass,
    PurchaseEvent,
    build_cmp_artifact,
    build_purchase_events,
    combine_stage_reports,
    de_overlap_events,
    evaluate_stage_c,
    evaluate_stage_d,
    opportunistic_events,
    require_e1_authorisation,
    year_shares,
)
from invest.domain.models import InsiderTransaction  # noqa: E402

# Reuse CFOB driver I/O seams (tape, reference, SEP, reconcile) without sharing
# verdict paths or the cluster object.
from research_cfob import (  # type: ignore[import-not-found]  # noqa: E402
    FIRST_YEAR,
    REPO_ROOT,
    SEP_DIR,
    TAPE_DIR,
    current_git_sha,
    load_reference_listings,
    pull_tape,
    reconcile_against_edgar_index,
)

REPORTS_DIR = REPO_ROOT / "fixtures" / "real-continuous" / "reports"
ARTIFACT_PATH = REPORTS_DIR / "cmp-structure.json"
DOCS_PATH = REPO_ROOT / "docs" / "research" / "cmp-results.md"
HUMAN_GO_PATH = REPORTS_DIR / "cmp-e1-human-go.json"


def apply_universe_filter_events(
    events: list[PurchaseEvent], *, verbose: bool = True
) -> tuple[list[PurchaseEvent], dict[str, list[date]], dict]:
    """Habitat filter for purchase events — same floors as CFOB, event object."""

    # Reuse the CFOB helper by projecting to a minimal cluster-like surface via
    # a temporary adapter: map events → pseudo clusters is wrong. Instead
    # duplicate the year-walk logic against PurchaseEvent (same SEP path).
    available_years = sorted(
        int(path.stem.split("_")[1]) for path in SEP_DIR.glob("sep_*.parquet")
    )
    if not available_years:
        raise SystemExit(f"fail-closed: no SEP year parquet found in {SEP_DIR}")
    last_priced_year = available_years[-1]
    out_of_span = [e for e in events if e.year > last_priced_year]
    events = [e for e in events if e.year <= last_priced_year]

    symbols = {e.trading_symbol for e in events}
    years = sorted({e.year for e in events})
    history: dict[str, list[tuple[date, float, float]]] = defaultdict(list)
    kept: list[PurchaseEvent] = []
    secondary_kept = 0
    price_floor_excluded = 0
    market_sessions: set[date] = set()
    no_price_history_by_year: dict[int, int] = defaultdict(int)
    insufficient_history_by_year: dict[int, int] = defaultdict(int)
    below_dollar_volume_by_year: dict[int, int] = defaultdict(int)
    total_by_year: dict[int, int] = defaultdict(int)

    from research_cfob import _load_sep_year  # local import; private helper reuse

    events_by_year: dict[int, list[PurchaseEvent]] = defaultdict(list)
    for event in events:
        events_by_year[event.year].append(event)

    for year in years:
        for load_year in (year - 1, year):
            if load_year < FIRST_YEAR - 2:
                continue
            for symbol, bars in _load_sep_year(load_year, symbols).items():
                history[symbol].extend(bars)
                market_sessions.update(day for day, _, _ in bars)
        for symbol in list(history):
            history[symbol] = sorted(set(history[symbol]))[-600:]

        for event in events_by_year[year]:
            total_by_year[year] += 1
            decision = evaluate_universe_membership(
                bars=history.get(event.trading_symbol, []),
                known_time=event.known_time,
            )
            if decision.reason == "no_price_history":
                no_price_history_by_year[year] += 1
                continue
            if decision.reason == "insufficient_history":
                insufficient_history_by_year[year] += 1
                continue
            if decision.reason == "below_dollar_volume":
                below_dollar_volume_by_year[year] += 1
                continue
            if decision.below_price_floor:
                price_floor_excluded += 1
                if not decision.eligible:
                    continue
            kept.append(event)
            if decision.in_secondary_band:
                secondary_kept += 1

        if verbose:
            print(f"  {year}: universe-eligible opportunistic events {len(kept):,}")

    calendar = sorted(market_sessions)
    sessions = {symbol: calendar for symbol in symbols}
    diagnostics = {
        "measured_span": f"{FIRST_YEAR}-01-01..{last_priced_year}-12-31",
        "events_out_of_price_span": len(out_of_span),
        "secondary_10m_band_events": secondary_kept,
        "adjusted_price_below_5_count": price_floor_excluded,
        "price_floor_role": "diagnostic_on_adjusted_close",
        "no_price_history_by_year": dict(no_price_history_by_year),
        "insufficient_history_by_year": dict(insufficient_history_by_year),
        "below_dollar_volume_by_year": dict(below_dollar_volume_by_year),
        "universe_total_by_year": dict(total_by_year),
    }
    return kept, sessions, diagnostics


def load_purchases_and_history(
    *, through: date, verbose: bool = True
) -> tuple[dict[str, list[tuple[date, int, int]]], list[InsiderTransaction], dict]:
    """One tape pass: compact full-code history + qualifying purchases + counts.

    Classification history uses **all** non-derivative Form 3/4/5 codes (not only
    code-P), so sales/other codes can mark routine. Stored as compact
    ``(known_time, trade_year, trade_month)`` triples per owner to respect the
    step3 OOM law. Qualification still binds the event object to code-P purchases
    after amendment dedupe on the code-P stream alone.
    """

    from invest.adapters.sec_insider_tape import InsiderTapeError, SecInsiderTapeReader
    from invest.application.cfob import qualifying_purchases
    from research_cfob import quarters

    reader = SecInsiderTapeReader(cache_dir=TAPE_DIR)
    history_by_owner: dict[str, list[tuple[date, int, int]]] = defaultdict(list)
    code_p: list[InsiderTransaction] = []
    total_rows = 0
    wrong_code = 0
    quarters_read = 0
    archives_expected = 0
    archives_parsed = 0

    for year, quarter in quarters(through):
        path = reader.archive_path(year, quarter)
        if not path.is_file():
            continue
        archives_expected += 1
        try:
            transactions = reader.load_quarter(year, quarter)
        except InsiderTapeError as exc:
            raise SystemExit(f"fail-closed: {exc}") from exc
        archives_parsed += 1
        quarters_read += 1
        total_rows += len(transactions)
        for txn in transactions:
            history_by_owner[txn.owner_cik].append(
                (txn.filing_date, txn.transaction_date.year, txn.transaction_date.month)
            )
            if txn.transaction_code == PROTOCOL.transaction_code:
                code_p.append(txn)
            else:
                wrong_code += 1
        if verbose and quarter == 4:
            print(
                f"  {year}: cumulative rows {total_rows:,} "
                f"(code-P {len(code_p):,}; owners {len(history_by_owner):,})"
            )

    for owner, rows in history_by_owner.items():
        history_by_owner[owner] = sorted(rows, key=lambda row: (row[0], row[1], row[2]))

    purchases, counts = qualifying_purchases(code_p)
    del code_p
    totals = counts.to_dict()
    totals["total_rows"] = total_rows
    totals["wrong_code"] = wrong_code
    totals["quarters_read"] = quarters_read
    totals["archives_expected"] = archives_expected
    totals["archives_parsed"] = archives_parsed
    totals["history_owners"] = len(history_by_owner)
    totals["history_rows"] = sum(len(rows) for rows in history_by_owner.values())
    return dict(history_by_owner), list(purchases), totals


def human_go_recorded() -> bool:
    if not HUMAN_GO_PATH.is_file():
        return False
    try:
        payload = json.loads(HUMAN_GO_PATH.read_text())
    except json.JSONDecodeError:
        return False
    return bool(payload.get("human_go") and payload.get("timestamp") and payload.get("git_sha"))


def synthetic_pipeline() -> dict:
    """Deterministic smoke cohort — exercises gates, claims nothing."""

    # Build synthetic opportunistic events across 20 years with enough unique
    # tickers that first-wins de-overlap still clears the 7,500 density floor.
    events: list[PurchaseEvent] = []
    for year in range(2006, 2026):
        for index in range(500):
            # One event per (year, ticker index) — no within-year re-entry.
            known = date(year, 1 + (index % 12), 1 + (index % 27))
            events.append(
                PurchaseEvent(
                    trading_symbol=f"SYN{index}",
                    issuer_cik=f"{index:07d}",
                    owner_cik=f"own{index % 300}",
                    known_time=known,
                    first_transaction_date=known - timedelta(days=2),
                    last_transaction_date=known - timedelta(days=2),
                    purchase_count=1,
                    gross_value=Decimal("50000"),
                    cmp_class=CmpClass.OPPORTUNISTIC,
                )
            )
    deoverlapped = list(de_overlap_events(events))
    shares = year_shares(deoverlapped)
    class_counts = ClassificationCounts(
        total_purchases=len(events) + 1000,
        opportunistic=len(events),
        routine=800,
        unclassified=200,
        opportunistic_events=len(events),
        routine_events=700,
    )
    c_report = evaluate_stage_c(
        archives_expected=1,
        archives_parsed=1,
        reconciled=True,
        mapped=len(events),
        total=len(events),
        counts=class_counts,
        protocol_present=True,
        trial_ledger_present=True,
        primary_is_cluster=False,
    )
    d_report = evaluate_stage_d(
        de_overlapped_events=len(deoverlapped),
        shares=shares,
    )
    combined = combine_stage_reports(c_report, d_report)
    return build_cmp_artifact(
        stage="C+D",
        report=combined,
        qualification_counts={"qualified": len(events), "mode": "synthetic"},
        classification=class_counts,
        raw_opportunistic_events=len(events),
        universe_eligible_events=len(events),
        de_overlapped_events=len(deoverlapped),
        shares=shares,
        mode="synthetic",
        git_sha=current_git_sha(),
        notes={"warning": "synthetic smoke cohort — claims nothing"},
    )


def write_docs(artifact: dict) -> None:
    gates = artifact["gates"]
    shares = artifact["events"]["year_shares"]
    classif = artifact["classification"]
    lines = [
        "# CMP opportunistic Form-4 baseline — Stage C+D results",
        "",
        f"**Date:** {date.today().isoformat()}  ",
        f"**Git SHA:** `{artifact.get('git_sha')}`  ",
        "**Driver:** `fixtures/real-continuous/reports/research_cmp.py`  ",
        "**Artifact:** `fixtures/real-continuous/reports/cmp-structure.json`  ",
        "**Parent PRD:** #79 (grilled 2026-07-22)  ",
        "**ADR:** `docs/adr/0003-cmp-opportunistic-baseline-path.md`",
        "",
        "## Verdict",
        "",
        f"### **{artifact['verdict']}**",
        "",
        f"- stage: `{artifact['stage']}`",
        f"- capital_go: `{artifact['capital_go']}` (always false)",
        f"- implementability_eligible: `{artifact['implementability_eligible']}`",
        f"- all hard gates passed: `{artifact['all_hard_gates_passed']}`",
        "",
        "## Cohort (opportunistic primary)",
        "",
        f"- raw opportunistic events: `{artifact['events']['raw_opportunistic']:,}`",
        f"- universe-eligible opportunistic: `{artifact['events']['universe_eligible_opportunistic']:,}`",
        f"- **de-overlapped opportunistic (gated object)**: "
        f"`{artifact['events']['de_overlapped_opportunistic']:,}`",
        f"- required for MDS bar: `{artifact['events']['required_for_mds_bar']:,}`",
        f"- MDS at measured n: `{artifact['events']['mds_at_measured_n']:.4f}`",
        "",
        "## Classification counts",
        "",
    ]
    for field, value in classif.items():
        lines.append(f"- {field}: `{value:,}`" if isinstance(value, int) else f"- {field}: `{value}`")
    lines += ["", "## Qualification counts", ""]
    for field, value in artifact["counts"].items():
        lines.append(
            f"- {field}: `{value:,}`" if isinstance(value, int) else f"- {field}: `{value}`"
        )
    lines += ["", "## Year shares (de-overlapped opportunistic)", ""]
    for year, share in sorted(shares.items(), key=lambda item: str(item[0])):
        lines.append(f"- {year}: {share:.4f}")
    lines += ["", "## Gates (C + D combined)", ""]
    for gate in gates:
        status = "PASS" if gate["passed"] else "FAIL"
        lines.append(
            f"- **{gate['id']}** [{gate['severity']}] **{status}** — {gate['reason']}"
        )
    lines += [
        "",
        "## Dual-exit interpretation",
        "",
        f"Top-level verdict **{artifact['verdict']}**. Stage C integrity/classification "
        "and Stage D density are combined; power-only D fails yield `underpowered_stop`, "
        "structure fails yield `kill_line`. Any dual-exit re-seals Full-Stop: no E1, no "
        "floor retune, no GP on this object.",
        "",
        "## What this does and does not claim",
        "",
        "### Claims",
        "",
        "- Point-in-time CMP opportunistic vs routine classification on free SEC Form-4 tape.",
        "- Density/power of de-overlapped opportunistic purchase events against floors "
        "frozen before any returns.",
        "",
        "### Non-claims",
        "",
        "- **No returns were measured** at Stage C+D (E1 needs human go + `--e1` after C+D pass).",
        "- Not purchase-cluster rescue (#76 kill_line stands).",
        "- Not capital permission; `capital_go` is false by construction.",
        "- Not genetic/symbolic search.",
        "- Not a licence to loosen density floors post-hoc after underpowered_stop.",
        "",
        "## How to re-run",
        "",
        "```bash",
        "uv run python fixtures/real-continuous/reports/research_cmp.py --pull-only",
        "CFOB_SEP_DIR=fixtures/full-depth-sep \\",
        "  uv run python fixtures/real-continuous/reports/research_cmp.py --measure-only --write-docs",
        "```",
        "",
    ]
    DOCS_PATH.write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="CMP Stage C+D driver (PRD #79)")
    parser.add_argument("--pull-only", action="store_true", help="download the tape and exit")
    parser.add_argument("--measure-only", action="store_true", help="skip download")
    parser.add_argument("--synthetic", action="store_true", help="smoke mode, claims nothing")
    parser.add_argument("--write-docs", action="store_true", help="write the results doc")
    parser.add_argument(
        "--skip-reconcile",
        action="store_true",
        help="skip EDGAR form.idx reconcile (fail-closed unless synthetic)",
    )
    parser.add_argument(
        "--e1",
        action="store_true",
        help="authorise Stage E1 returns (also requires human-go file); default refused",
    )
    args = parser.parse_args()

    if args.e1:
        try:
            require_e1_authorisation(
                e1_flag=True, human_go_recorded=human_go_recorded()
            )
        except PermissionError as exc:
            raise SystemExit(f"fail-closed: {exc}") from exc
        raise SystemExit(
            "fail-closed: E1 measurement path is frozen in protocol but not "
            "implemented in this C+D deliverable — record human go, then open "
            "the E1 implementation ticket after C+D stage_pass"
        )

    through = date.today()

    if args.synthetic:
        artifact = synthetic_pipeline()
        ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2, default=str))
        if args.write_docs:
            write_docs(artifact)
        print(f"synthetic verdict: {artifact['verdict']}")
        return 0

    if not args.measure_only:
        print("Pulling SEC insider tape (polite, resumable)...")
        pull_tape(through=through)
    if args.pull_only:
        return 0

    if not SEP_DIR.is_dir():
        raise SystemExit(
            f"fail-closed: SEP panel not found at {SEP_DIR}. "
            "Set CFOB_SEP_DIR to the full-depth SEP year-parquet directory."
        )

    print("Parsing tape (full-code history + qualifying purchases, one pass)...")
    history_by_owner, purchases, counts = load_purchases_and_history(through=through)
    print(
        f"  history owners: {len(history_by_owner):,} "
        f"(rows={counts.get('history_rows', 0):,})"
    )
    if not purchases:
        raise SystemExit("fail-closed: no qualifying purchases parsed")
    print(f"  qualifying purchases: {len(purchases):,}")

    print("Loading TICKERS reference for CIK-primary mapping...")
    listings, window_source = load_reference_listings()
    mapping = map_purchases_by_cik(purchases, listings)
    print(
        f"  mapped purchases: {mapping.mapped_count:,} / {mapping.total_count:,} "
        f"(ambiguous {len(mapping.ambiguous):,}; source={window_source})"
    )
    if mapping.mapped_count == 0:
        raise SystemExit("fail-closed: zero purchases mapped via CIK reference")

    # Remap history owners already use owner_cik (identity); remap purchase
    # symbols to canonical Sharadar tickers for SEP join.
    canonical_purchases = [
        replace(purchase, trading_symbol=canonical_symbol)
        for purchase, canonical_symbol in mapping.canonical
    ]

    print("Building CMP-classified purchase events...")
    all_events, class_counts = build_purchase_events(
        canonical_purchases, history_by_owner=history_by_owner
    )
    opp_raw = list(opportunistic_events(all_events))
    print(
        f"  opportunistic purchases={class_counts.opportunistic:,} "
        f"(events={class_counts.opportunistic_events:,}); "
        f"routine={class_counts.routine:,}; unclassified={class_counts.unclassified:,}"
    )
    if not opp_raw:
        raise SystemExit("fail-closed: zero opportunistic events after classification")

    print(f"Applying habitat universe filter from SEP ({SEP_DIR})...")
    eligible, sessions, diagnostics = apply_universe_filter_events(opp_raw)
    print(f"  universe-eligible opportunistic events: {len(eligible):,}")
    if not eligible:
        raise SystemExit(
            "fail-closed: universe filter admitted zero opportunistic events from "
            f"{len(opp_raw):,} raw. That is a data/join failure, not a density result."
        )

    print("De-overlapping opportunistic events (first-wins, h60)...")
    deoverlapped = list(de_overlap_events(eligible, sessions_by_symbol=sessions))
    print(f"  de-overlapped opportunistic events: {len(deoverlapped):,}")
    shares = year_shares(deoverlapped)

    print("\nRunning Stage C integrity / classification gates...")
    if args.skip_reconcile:
        reconciled, reconcile_rows = None, []
        print("  reconcile skipped (--skip-reconcile) → fail closed")
    else:
        reconciled, reconcile_rows = reconcile_against_edgar_index()

    c_report = evaluate_stage_c(
        archives_expected=counts.get("archives_expected"),
        archives_parsed=counts.get("archives_parsed"),
        reconciled=reconciled,
        mapped=mapping.mapped_count,
        total=mapping.total_count,
        counts=class_counts,
        protocol_present=True,
        trial_ledger_present=True,
        primary_is_cluster=False,
    )
    print(f"Stage C verdict: {c_report.verdict}")
    for gate in c_report.to_dict()["gates"]:
        print(f"  {'PASS' if gate['passed'] else 'FAIL'} {gate['id']}: {gate['reason']}")

    print("\nRunning Stage D density gates...")
    d_report = evaluate_stage_d(
        de_overlapped_events=len(deoverlapped),
        shares=shares,
    )
    print(f"Stage D verdict: {d_report.verdict}")
    for gate in d_report.to_dict()["gates"]:
        print(f"  {'PASS' if gate['passed'] else 'FAIL'} {gate['id']}: {gate['reason']}")

    combined = combine_stage_reports(c_report, d_report)
    counts_obj = QualificationCounts(
        **{field: counts.get(field, 0) for field in QualificationCounts.__dataclass_fields__}
    )
    derivative_rows = sum(1 for p in purchases if p.source_table != "NONDERIV_TRANS")
    amendment_collisions = amendment_collision_count(purchases)

    artifact = build_cmp_artifact(
        stage="C+D",
        report=combined,
        qualification_counts=counts_obj.to_dict(),
        classification=class_counts,
        raw_opportunistic_events=len(opp_raw),
        universe_eligible_events=len(eligible),
        de_overlapped_events=len(deoverlapped),
        shares=shares,
        mode="sec-insider-tape-2006-present",
        git_sha=current_git_sha(),
        notes={
            "quarters_read": counts.get("quarters_read", 0),
            "reference_source": window_source,
            "mapped_purchases": mapping.mapped_count,
            "total_purchases": mapping.total_count,
            "ambiguous_purchases": len(mapping.ambiguous),
            "derivative_rows_in_qualified": derivative_rows,
            "amendment_collisions": amendment_collisions,
            "reconcile_sample": reconcile_rows,
            "stage_c": {
                "verdict": c_report.verdict,
                "all_hard_gates_passed": c_report.all_hard_gates_passed,
                "gates": c_report.to_dict()["gates"],
            },
            "stage_d": {
                "verdict": d_report.verdict,
                "all_hard_gates_passed": d_report.all_hard_gates_passed,
                "gates": d_report.to_dict()["gates"],
            },
            "routine_events_diagnostic": class_counts.routine_events,
            "e1_status": "refused_until_human_go",
            **diagnostics,
        },
    )
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2, default=str))
    if args.write_docs:
        write_docs(artifact)

    print(f"\nCombined C+D verdict: {artifact['verdict']}")
    for gate in artifact["gates"]:
        print(f"  {'PASS' if gate['passed'] else 'FAIL'} {gate['id']}: {gate['reason']}")
    print(f"artifact: {ARTIFACT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
