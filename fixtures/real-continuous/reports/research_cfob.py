"""CFOB Stage D (density) and F0 (integrity) research driver — PRD #76.

Sequential by construction: the 16GB host must never hold two multi-GB objects
at once (step3 OOM law). SEP is walked one year at a time and filtered to the
symbols that actually produced clusters.

Stage E1 (returns) is NOT implemented here. It requires a separate human
authorisation per the PRD #76 grill. ``capital_go`` is false in every artifact.

Usage:
    uv run python fixtures/real-continuous/reports/research_cfob.py --pull-only
    uv run python fixtures/real-continuous/reports/research_cfob.py --measure-only --write-docs
    uv run python fixtures/real-continuous/reports/research_cfob.py --synthetic --write-docs
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import median

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

from invest.adapters.sec_insider_tape import InsiderTapeError, SecInsiderTapeReader  # noqa: E402
from invest.application.cfob import (  # noqa: E402
    PROTOCOL,
    PurchaseCluster,
    build_cfob_artifact,
    build_clusters,
    de_overlap,
    dedupe_amendments,
    evaluate_stage_d,
    evaluate_stage_f0,
    qualifying_purchases,
    year_shares,
)
from invest.domain.models import InsiderTransaction  # noqa: E402

TAPE_DIR = REPO_ROOT / "fixtures" / "sec-insider-tape"
SEP_DIR = REPO_ROOT / "fixtures" / "full-depth-sep"
REPORTS_DIR = REPO_ROOT / "fixtures" / "real-continuous" / "reports"
DOCS_PATH = REPO_ROOT / "docs" / "research" / "cfob-results.md"
ARTIFACT_PATH = REPORTS_DIR / "cfob-structure.json"

BASE_URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets"
USER_AGENT = "invest-research ramoncarmenaty@gmail.com"
FIRST_YEAR = 2006
REQUEST_PAUSE_SECONDS = 0.4


def quarters(through: date) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for year in range(FIRST_YEAR, through.year + 1):
        for quarter in (1, 2, 3, 4):
            if year == through.year and (quarter - 1) * 3 + 1 > through.month:
                break
            out.append((year, quarter))
    return out


def pull_tape(*, through: date, verbose: bool = True) -> dict:
    """Resumable, rate-limited download of the quarterly archives."""

    TAPE_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = TAPE_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}

    for year, quarter in quarters(through):
        name = f"{year}q{quarter}_form345.zip"
        target = TAPE_DIR / name
        if target.is_file() and manifest.get(name, {}).get("bytes") == target.stat().st_size:
            continue
        request = urllib.request.Request(
            f"{BASE_URL}/{name}", headers={"User-Agent": USER_AGENT}
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                if verbose:
                    print(f"  {name}: not published yet (404)")
                continue
            raise
        target.write_bytes(payload)
        manifest[name] = {"bytes": len(payload), "pulled": date.today().isoformat()}
        if verbose:
            print(f"  {name}: {len(payload) / 1e6:.1f} MB")
        time.sleep(REQUEST_PAUSE_SECONDS)

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    return manifest


def load_purchases(*, through: date, verbose: bool = True) -> tuple[list, dict]:
    """Parse every cached quarter into qualifying purchases.

    Quarters are qualified as they are read so only the surviving purchases
    stay resident — the raw tape is an order of magnitude larger.
    """

    reader = SecInsiderTapeReader(cache_dir=TAPE_DIR)
    kept: list[InsiderTransaction] = []
    totals = defaultdict(int)
    quarters_read = 0

    for year, quarter in quarters(through):
        if not reader.archive_path(year, quarter).is_file():
            continue
        try:
            transactions = reader.load_quarter(year, quarter)
        except InsiderTapeError as exc:
            raise SystemExit(f"fail-closed: {exc}") from exc
        purchases, counts = qualifying_purchases(transactions)
        kept.extend(purchases)
        quarters_read += 1
        for field, value in counts.to_dict().items():
            totals[field] += value
        if verbose and quarter == 4:
            print(f"  {year}: cumulative qualifying purchases {len(kept):,}")

    # Quarter-local dedupe cannot see an amendment filed in a later quarter than
    # the trade it restates, so run one global pass over the (much smaller)
    # qualified set.
    before = len(kept)
    kept_tuple, cross_quarter_superseded = dedupe_amendments(kept)
    totals["quarters_read"] = quarters_read
    totals["cross_quarter_superseded"] = cross_quarter_superseded
    totals["qualified"] = len(kept_tuple)
    totals["dropped_by_global_dedupe"] = before - len(kept_tuple)
    return list(kept_tuple), dict(totals)


def _load_sep_year(year: int, symbols: set[str]) -> dict[str, list[tuple[date, float, float]]]:
    """Read one SEP year parquet, keeping only symbols with clusters."""

    import pyarrow.parquet as pq

    path = SEP_DIR / f"sep_{year}.parquet"
    if not path.is_file():
        return {}
    table = pq.read_table(path, columns=["ticker", "date", "close", "volume"])
    tickers = table.column("ticker").to_pylist()
    dates = table.column("date").to_pylist()
    closes = table.column("close").to_pylist()
    volumes = table.column("volume").to_pylist()

    out: dict[str, list[tuple[date, float, float]]] = defaultdict(list)
    for ticker, day, close, volume in zip(tickers, dates, closes, volumes):
        if ticker not in symbols:
            continue
        if close is None or volume is None:
            continue
        day = day.date() if hasattr(day, "date") else day
        out[ticker].append((day, float(close), float(volume)))
    return out


def apply_universe_filter(
    clusters: list[PurchaseCluster], *, verbose: bool = True
) -> tuple[list[PurchaseCluster], dict[str, list[date]], dict]:
    """Keep clusters whose symbol cleared the habitat floor at known-time.

    Habitat floor (grilled): price >= $5, 20-bar median dollar volume >= $2M,
    252 bars of history. The house $10M band is measured alongside as the
    secondary comparability diagnostic.
    """

    symbols = {c.trading_symbol for c in clusters}
    years = sorted({c.year for c in clusters})
    history: dict[str, list[tuple[date, float, float]]] = defaultdict(list)
    kept: list[PurchaseCluster] = []
    secondary_kept = 0
    unmapped_by_year: dict[int, int] = defaultdict(int)
    total_by_year: dict[int, int] = defaultdict(int)

    clusters_by_year: dict[int, list[PurchaseCluster]] = defaultdict(list)
    for cluster in clusters:
        clusters_by_year[cluster.year].append(cluster)

    for year in years:
        # Carry the prior year's tail so the trailing window is complete at the
        # start of the year; SEP is never fully resident.
        for load_year in (year - 1, year):
            if load_year < FIRST_YEAR - 2:
                continue
            for symbol, bars in _load_sep_year(load_year, symbols).items():
                history[symbol].extend(bars)
        for symbol in list(history):
            history[symbol] = sorted(set(history[symbol]))[-600:]

        for cluster in clusters_by_year[year]:
            total_by_year[year] += 1
            bars = history.get(cluster.trading_symbol, [])
            prior = [b for b in bars if b[0] <= cluster.known_time]
            if len(prior) < PROTOCOL.min_history_bars:
                unmapped_by_year[year] += 1
                continue
            window = prior[-PROTOCOL.dollar_volume_window :]
            price = prior[-1][1]
            dollar_volume = median(close * volume for _, close, volume in window)
            if price < float(PROTOCOL.min_price):
                continue
            if dollar_volume < float(PROTOCOL.min_dollar_volume):
                continue
            kept.append(cluster)
            if dollar_volume >= float(PROTOCOL.secondary_min_dollar_volume):
                secondary_kept += 1

        if verbose:
            print(f"  {year}: universe-eligible clusters {len(kept):,}")

    sessions = {
        symbol: sorted({day for day, _, _ in bars}) for symbol, bars in history.items()
    }
    diagnostics = {
        "secondary_10m_band_clusters": secondary_kept,
        "unmapped_by_year": dict(unmapped_by_year),
        "total_by_year": dict(total_by_year),
    }
    return kept, sessions, diagnostics


def synthetic_clusters() -> list[PurchaseCluster]:
    """Deterministic smoke cohort — exercises the pipeline, claims nothing."""

    out: list[PurchaseCluster] = []
    for year in range(2006, 2026):
        for index in range(400):
            known = date(year, 1, 1) + timedelta(days=index % 360)
            out.append(
                PurchaseCluster(
                    trading_symbol=f"SYN{index % 50}",
                    issuer_cik=f"{index:07d}",
                    known_time=known,
                    first_transaction_date=known - timedelta(days=5),
                    last_transaction_date=known - timedelta(days=2),
                    distinct_insiders=2,
                    purchase_count=2,
                    gross_value=Decimal("50000"),
                )
            )
    return out


def write_docs(artifact: dict) -> None:
    gates = artifact["gates"]
    shares = artifact["clusters"]["year_shares"]
    lines = [
        "# CFOB Stage D results",
        "",
        f"**Date:** {date.today().isoformat()}  ",
        "**Driver:** `fixtures/real-continuous/reports/research_cfob.py`  ",
        "**Artifact:** `fixtures/real-continuous/reports/cfob-structure.json`  ",
        "**Parent PRD:** #76 (grilled 2026-07-21)  ",
        "**ADR:** `docs/adr/0002-cfob-gate-law-divergence.md`",
        "",
        "## Verdict",
        "",
        f"### **{artifact['verdict']}**",
        "",
        f"- capital_go: `{artifact['capital_go']}` (always false)",
        f"- implementability_eligible: `{artifact['implementability_eligible']}`",
        f"- all hard gates passed: `{artifact['all_hard_gates_passed']}`",
        "",
        "## Cohort",
        "",
        f"- raw clusters: `{artifact['clusters']['raw']:,}`",
        f"- **de-overlapped clusters (gated object)**: `{artifact['clusters']['de_overlapped']:,}`",
        f"- required for MDS bar: `{artifact['clusters']['required_for_mds_bar']:,}`",
        f"- MDS at measured n: `{artifact['clusters']['mds_at_measured_n']:.4f}`",
        "",
        "## Qualification counts",
        "",
    ]
    for field, value in artifact["counts"].items():
        lines.append(f"- {field}: `{value:,}`" if isinstance(value, int) else f"- {field}: `{value}`")
    lines += ["", "## Year shares", ""]
    for year, share in sorted(shares.items()):
        lines.append(f"- {year}: {share:.4f}")
    lines += ["", "## Gates", ""]
    for gate in gates:
        status = "PASS" if gate["passed"] else "FAIL"
        lines.append(f"- **{gate['id']}** [{gate['severity']}] **{status}** — {gate['reason']}")
    lines += [
        "",
        "## What this does and does not claim",
        "",
        "### Claims",
        "",
        "- Density and spread of insider purchase clusters on the free SEC tape (2006-), "
        "measured against floors frozen before any returns existed.",
        "- The floor is derived from Gate-1a's measured dispersion, not chosen for convenience.",
        "",
        "### Non-claims",
        "",
        "- **No returns were measured.** Stage D counts events; it says nothing about whether "
        "insider clusters predict anything.",
        "- Not capital permission; `capital_go` is false by construction.",
        "- Not a reopening of residual, R2-1, PEAD, or CMFT #74.",
        "",
        "## How to re-run",
        "",
        "```bash",
        "uv run python fixtures/real-continuous/reports/research_cfob.py --pull-only",
        "uv run python fixtures/real-continuous/reports/research_cfob.py --measure-only --write-docs",
        "```",
        "",
    ]
    DOCS_PATH.write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description="CFOB Stage D / F0 driver")
    parser.add_argument("--pull-only", action="store_true", help="download the tape and exit")
    parser.add_argument("--measure-only", action="store_true", help="skip download")
    parser.add_argument("--synthetic", action="store_true", help="smoke mode, claims nothing")
    parser.add_argument("--write-docs", action="store_true", help="write the results doc")
    args = parser.parse_args()

    through = date.today()

    if args.synthetic:
        raw = synthetic_clusters()
        deoverlapped = list(de_overlap(raw))
        shares = year_shares(deoverlapped)
        report = evaluate_stage_d(de_overlapped_clusters=len(deoverlapped), shares=shares)
        from invest.application.cfob import QualificationCounts

        artifact = build_cfob_artifact(
            stage="D",
            report=report,
            counts=QualificationCounts(),
            raw_clusters=len(raw),
            de_overlapped_clusters=len(deoverlapped),
            shares=shares,
            mode="synthetic",
            notes={"warning": "synthetic smoke cohort — claims nothing"},
        )
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

    print("Parsing tape into qualifying purchases...")
    purchases, counts = load_purchases(through=through)
    if not purchases:
        raise SystemExit("fail-closed: no qualifying purchases parsed")
    print(f"  qualifying purchases: {len(purchases):,}")

    print("Building clusters (30d trade window, >=2 distinct insiders)...")
    raw = list(build_clusters(purchases))
    print(f"  raw clusters: {len(raw):,}")

    print("Applying habitat universe filter from SEP...")
    eligible, sessions, diagnostics = apply_universe_filter(raw)
    print(f"  universe-eligible clusters: {len(eligible):,}")

    print("De-overlapping (first-wins, h60)...")
    deoverlapped = list(de_overlap(eligible, sessions_by_symbol=sessions))
    print(f"  de-overlapped clusters: {len(deoverlapped):,}")

    shares = year_shares(deoverlapped)
    report = evaluate_stage_d(de_overlapped_clusters=len(deoverlapped), shares=shares)

    from invest.application.cfob import QualificationCounts

    counts_obj = QualificationCounts(
        total_rows=counts.get("total_rows", 0),
        qualified=counts.get("qualified", 0),
        wrong_code=counts.get("wrong_code", 0),
        disposals=counts.get("disposals", 0),
        below_size_floor=counts.get("below_size_floor", 0),
        stale=counts.get("stale", 0),
        amendment_superseded=counts.get("amendment_superseded", 0),
        unparseable_value=counts.get("unparseable_value", 0),
        late_filed=counts.get("late_filed", 0),
        indirect_ownership=counts.get("indirect_ownership", 0),
    )

    artifact = build_cfob_artifact(
        stage="D",
        report=report,
        counts=counts_obj,
        raw_clusters=len(raw),
        de_overlapped_clusters=len(deoverlapped),
        shares=shares,
        mode="sec-insider-tape-2006-present",
        notes={
            "quarters_read": counts.get("quarters_read", 0),
            "universe_eligible_clusters": len(eligible),
            **diagnostics,
        },
    )
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2, default=str))
    if args.write_docs:
        write_docs(artifact)

    print(f"\nStage D verdict: {artifact['verdict']}")
    for gate in artifact["gates"]:
        print(f"  {'PASS' if gate['passed'] else 'FAIL'} {gate['id']}: {gate['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
