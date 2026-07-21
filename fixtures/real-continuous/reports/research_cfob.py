"""CFOB Stage D (density) and F0 (integrity) research driver — PRD #76.

Sequential by construction: the 16GB host must never hold two multi-GB objects
at once (step3 OOM law). SEP is walked one year at a time and filtered to the
symbols that actually produced clusters.

Stage E1 (returns) was separately authorised (PRD #76 grill session 2, after
PR #77 merged) and runs under ``--e1``. ``capital_go`` is false in every
artifact.

Usage:
    uv run python fixtures/real-continuous/reports/research_cfob.py --pull-only
    uv run python fixtures/real-continuous/reports/research_cfob.py --measure-only --write-docs
    uv run python fixtures/real-continuous/reports/research_cfob.py --synthetic --write-docs
    CFOB_SEP_DIR=... CFOB_TAPE_DIR=... \
        uv run python fixtures/real-continuous/reports/research_cfob.py --e1 --write-docs
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from invest.adapters.sec_insider_tape import (
    InsiderTapeError,
    SecInsiderTapeReader,
    parse_form_index_form4,
)
from invest.application.cfob import (
    E1_COST_LADDER_BPS,
    PROTOCOL,
    ReferenceListing,
    cik_from_secfilings_url,
    PurchaseCluster,
    QualificationCounts,
    amendment_collision_count,
    build_cfob_artifact,
    build_cfob_e1_artifact,
    build_clusters,
    combine_stage_reports,
    contribution_shares,
    de_overlap,
    empirical_percentile,
    evaluate_stage_d,
    evaluate_stage_e1,
    evaluate_stage_f0,
    evaluate_universe_membership,
    map_purchases_by_cik,
    min_detectable_size,
    qualifying_purchases,
    run_placebo,
    winsorize,
    year_shares,
)
from invest.application.event_study_excess import clustered_t
from invest.domain.models import InsiderTransaction

REPO_ROOT = Path(__file__).resolve().parents[3]
# The SEC tape archives are gitignored, so a worktree does not carry them.
# CFOB_TAPE_DIR points a session at an existing read-only cache (mirrors the
# CFOB_SEP_DIR pattern below); the tape is never re-downloaded for E1.
TAPE_DIR = Path(os.environ.get("CFOB_TAPE_DIR", REPO_ROOT / "fixtures" / "sec-insider-tape"))
# SEP year parquet is gitignored, so a worktree does not carry it. Allow an
# explicit override and fail closed if it cannot be found — a missing panel must
# never masquerade as "no cluster qualifies".
SEP_DIR = Path(os.environ.get("CFOB_SEP_DIR", REPO_ROOT / "fixtures" / "full-depth-sep"))
REPORTS_DIR = REPO_ROOT / "fixtures" / "real-continuous" / "reports"
DOCS_PATH = REPO_ROOT / "docs" / "research" / "cfob-results.md"
ARTIFACT_PATH = REPORTS_DIR / "cfob-structure.json"
REFERENCE_CACHE = TAPE_DIR / "tickers_reference_v2.json"

BASE_URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets"
USER_AGENT = "invest-research ramoncarmenaty@gmail.com"
FIRST_YEAR = 2006
REQUEST_PAUSE_SECONDS = 0.4
RECONCILE_TOLERANCE = 0.02
RECONCILE_SAMPLE = ((2006, 2), (2009, 4), (2012, 3), (2015, 1), (2018, 2), (2021, 4), (2024, 3))


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
        request = urllib.request.Request(f"{BASE_URL}/{name}", headers={"User-Agent": USER_AGENT})
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


def load_purchases(*, through: date, verbose: bool = True) -> tuple[list[InsiderTransaction], dict]:
    """Parse every cached quarter, then dedupe and qualify once globally.

    Quarters are prefiltered to code-P rows as they are read (the raw tape is
    an order of magnitude larger, ~7M rows vs ~1M code-P). Amendment dedupe and
    qualification then run in ONE global pass, so a Form 4/A filed quarters
    after the trade it restates can still supersede — or disqualify — the
    original. Qualifying before deduping would let an amendment that shrinks a
    trade below the size floor vanish while its original survived.
    """

    reader = SecInsiderTapeReader(cache_dir=TAPE_DIR)
    code_p_rows: list[InsiderTransaction] = []
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
            if txn.transaction_code == PROTOCOL.transaction_code:
                code_p_rows.append(txn)
            else:
                wrong_code += 1
        if verbose and quarter == 4:
            print(f"  {year}: cumulative code-P rows {len(code_p_rows):,}")

    purchases, counts = qualifying_purchases(code_p_rows)
    del code_p_rows
    totals = counts.to_dict()
    totals["total_rows"] = total_rows
    totals["wrong_code"] = wrong_code
    totals["quarters_read"] = quarters_read
    totals["archives_expected"] = archives_expected
    totals["archives_parsed"] = archives_parsed
    return list(purchases), totals


def _load_sep_year(year: int, symbols: set[str]) -> dict[str, list[tuple[date, float, float]]]:
    """Read one SEP year parquet, keeping only symbols with clusters."""

    import pyarrow.parquet as pq

    path = SEP_DIR / f"sep_{year}.parquet"
    if not path.is_file():
        if FIRST_YEAR - 1 <= year <= date.today().year:
            raise SystemExit(f"fail-closed: SEP year parquet missing for {year}: {path}")
        return {}
    wanted = ["symbol", "date", "close_adj", "volume"]
    available = set(pq.ParquetFile(path).schema_arrow.names)
    missing = [column for column in wanted if column not in available]
    if missing:
        raise SystemExit(f"fail-closed: SEP {year} missing columns {missing}")
    table = pq.read_table(path, columns=wanted)
    tickers = table.column("symbol").to_pylist()
    dates = table.column("date").to_pylist()
    closes = table.column("close_adj").to_pylist()
    volumes = table.column("volume").to_pylist()

    out: dict[str, list[tuple[date, float, float]]] = defaultdict(list)
    for ticker, day, close, volume in zip(tickers, dates, closes, volumes, strict=False):
        if ticker not in symbols:
            continue
        if close is None or volume is None:
            continue
        day = day.date() if hasattr(day, "date") else day
        out[ticker].append((day, float(close), float(volume)))
    return out


def load_reference_listings(*, verbose: bool = True) -> tuple[list[ReferenceListing], str]:
    """TICKERS reference with CIK + related symbols (cache -> live fetch).

    CIK-primary mapping (grill 2026-07-21) needs three columns the plain
    listing-window path never fetched: secfilings (embeds the issuer CIK) and
    relatedtickers (historical/renamed symbols). Fails closed when neither a
    cache nor an API key is available -- there is no honest symbol-only
    fallback for an identity join.
    """

    if REFERENCE_CACHE.is_file():
        rows = json.loads(REFERENCE_CACHE.read_text())
        listings = [
            ReferenceListing(
                symbol=row["symbol"],
                cik=row.get("cik"),
                related_symbols=frozenset(row.get("related", [])),
                first_price_date=date.fromisoformat(row["first"]) if row.get("first") else None,
                last_price_date=date.fromisoformat(row["last"]) if row.get("last") else None,
            )
            for row in rows
        ]
        if verbose:
            print(f"  reference listings from cache: {len(listings):,}")
        return listings, "tickers-reference-cache"

    api_key = os.environ.get("NASDAQ_DATA_LINK_API_KEY")
    if not api_key:
        raise SystemExit(
            "fail-closed: CIK-primary mapping needs the TICKERS reference; no "
            f"cache at {REFERENCE_CACHE} and no NASDAQ_DATA_LINK_API_KEY set"
        )

    if verbose:
        print("  fetching Sharadar TICKERS reference (CIK + related symbols)...")
    columns = "ticker,category,firstpricedate,lastpricedate,isdelisted,secfilings,relatedtickers"
    base = (
        "https://data.nasdaq.com/api/v3/datatables/SHARADAR/TICKERS.json"
        f"?qopts.columns={columns}&api_key={api_key}"
    )
    seen: set[tuple] = set()
    listings: list[ReferenceListing] = []
    cursor: str | None = None
    for _page in range(512):
        url = base + (f"&qopts.cursor_id={cursor}" if cursor else "")
        with urllib.request.urlopen(url, timeout=180) as response:
            payload = json.loads(response.read().decode())
        table = payload.get("datatable", {})
        names = [column["name"] for column in table.get("columns", [])]
        index = {name: position for position, name in enumerate(names)}
        for values in table.get("data", []):
            symbol = (values[index["ticker"]] or "").strip()
            if not symbol:
                continue
            first_raw = values[index["firstpricedate"]]
            last_raw = values[index["lastpricedate"]]
            delisted = values[index["isdelisted"]]
            cik = cik_from_secfilings_url(values[index["secfilings"]])
            related_raw = values[index["relatedtickers"]] or ""
            related = frozenset(
                part.strip().upper() for part in related_raw.split() if part.strip()
            )
            first = date.fromisoformat(first_raw) if first_raw else None
            # Open listings keep last=None so covers() extends to the present.
            last = date.fromisoformat(last_raw) if (last_raw and delisted == "Y") else None
            key = (symbol, cik, related, first, last)
            if key in seen:
                continue
            seen.add(key)
            listings.append(
                ReferenceListing(
                    symbol=symbol,
                    cik=cik,
                    related_symbols=related,
                    first_price_date=first,
                    last_price_date=last,
                )
            )
        cursor = payload.get("meta", {}).get("next_cursor_id")
        if not cursor:
            break
    else:
        raise SystemExit("fail-closed: TICKERS pagination did not terminate")

    TAPE_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCE_CACHE.write_text(
        json.dumps(
            [
                {
                    "symbol": listing.symbol,
                    "cik": listing.cik,
                    "related": sorted(listing.related_symbols),
                    "first": listing.first_price_date.isoformat()
                    if listing.first_price_date
                    else None,
                    "last": listing.last_price_date.isoformat()
                    if listing.last_price_date
                    else None,
                }
                for listing in listings
            ]
        )
    )
    if verbose:
        print(f"  reference listings from TICKERS API: {len(listings):,}")
    return listings, "tickers-reference-api"


def apply_universe_filter(
    clusters: list[PurchaseCluster], *, verbose: bool = True
) -> tuple[list[PurchaseCluster], dict[str, list[date]], dict]:
    """Keep clusters whose symbol cleared the habitat floor at known-time.

    Binding habitat floor (ADR 0002 amended): 20-bar median dollar volume ≥ $2M
    and 252 bars of history. The $5 price floor is diagnostic on adjusted closes
    only (``gate_on_min_price=False``). The house $10M band is a secondary.
    """

    available_years = sorted(int(path.stem.split("_")[1]) for path in SEP_DIR.glob("sep_*.parquet"))
    if not available_years:
        raise SystemExit(f"fail-closed: no SEP year parquet found in {SEP_DIR}")
    last_priced_year = available_years[-1]
    out_of_span = [cluster for cluster in clusters if cluster.year > last_priced_year]
    clusters = [cluster for cluster in clusters if cluster.year <= last_priced_year]

    symbols = {cluster.trading_symbol for cluster in clusters}
    years = sorted({cluster.year for cluster in clusters})
    history: dict[str, list[tuple[date, float, float]]] = defaultdict(list)
    kept: list[PurchaseCluster] = []
    secondary_kept = 0
    price_floor_excluded = 0
    market_sessions: set[date] = set()
    no_price_history_by_year: dict[int, int] = defaultdict(int)
    insufficient_history_by_year: dict[int, int] = defaultdict(int)
    below_dollar_volume_by_year: dict[int, int] = defaultdict(int)
    total_by_year: dict[int, int] = defaultdict(int)

    clusters_by_year: dict[int, list[PurchaseCluster]] = defaultdict(list)
    for cluster in clusters:
        clusters_by_year[cluster.year].append(cluster)

    for year in years:
        for load_year in (year - 1, year):
            if load_year < FIRST_YEAR - 2:
                continue
            for symbol, bars in _load_sep_year(load_year, symbols).items():
                history[symbol].extend(bars)
                market_sessions.update(day for day, _, _ in bars)
        for symbol in list(history):
            history[symbol] = sorted(set(history[symbol]))[-600:]

        for cluster in clusters_by_year[year]:
            total_by_year[year] += 1
            decision = evaluate_universe_membership(
                bars=history.get(cluster.trading_symbol, []),
                known_time=cluster.known_time,
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
            kept.append(cluster)
            if decision.in_secondary_band:
                secondary_kept += 1

        if verbose:
            print(f"  {year}: universe-eligible clusters {len(kept):,}")

    calendar = sorted(market_sessions)
    sessions = {symbol: calendar for symbol in symbols}
    diagnostics = {
        "measured_span": f"{FIRST_YEAR}-01-01..{last_priced_year}-12-31",
        "clusters_out_of_price_span": len(out_of_span),
        "secondary_10m_band_clusters": secondary_kept,
        "adjusted_price_below_5_count": price_floor_excluded,
        "price_floor_role": (
            "primary_habitat_gate" if PROTOCOL.gate_on_min_price else "diagnostic_on_adjusted_close"
        ),
        "price_floor_caveat": (
            "SEP exposes only split/dividend-adjusted closes; the $5 price floor is "
            "reported, not gated (ADR 0002). Dollar volume is the binding habitat gate."
        ),
        "no_price_history_by_year": dict(no_price_history_by_year),
        "insufficient_history_by_year": dict(insufficient_history_by_year),
        "below_dollar_volume_by_year": dict(below_dollar_volume_by_year),
        "universe_total_by_year": dict(total_by_year),
    }
    return kept, sessions, diagnostics


def reconcile_against_edgar_index(*, verbose: bool = True) -> tuple[bool | None, list[dict]]:
    """Compare parsed Form 4 submissions against EDGAR's quarterly form.idx.

    form.idx lists each Form 4 once per (filer appearance), so raw line counts
    are roughly 2× unique accessions. Integrity binds on **unique accession**
    counts, which match the structured SUBMISSION table when ingestion is whole.
    """

    reader = SecInsiderTapeReader(cache_dir=TAPE_DIR)
    rows: list[dict] = []
    for year, quarter in RECONCILE_SAMPLE:
        if not reader.archive_path(year, quarter).is_file():
            continue

        with zipfile.ZipFile(reader.archive_path(year, quarter)) as archive:
            with archive.open("SUBMISSION.tsv") as handle:
                header = handle.readline().decode().rstrip("\n").split("\t")
                type_index = header.index("DOCUMENT_TYPE")
                ours = sum(
                    1
                    for line in handle
                    if line.decode("utf-8", "replace").split("\t")[type_index].strip()
                    in {"4", "4/A"}
                )

        url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/form.idx"
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                form4_lines, accessions = parse_form_index_form4(
                    raw.decode("utf-8", "replace").rstrip("\n") for raw in response
                )
        except urllib.error.HTTPError as exc:
            if verbose:
                print(f"  {year}Q{quarter}: index unavailable (HTTP {exc.code})")
            return None, rows
        theirs = len(accessions)
        time.sleep(REQUEST_PAUSE_SECONDS)

        delta = abs(ours - theirs) / theirs if theirs else 1.0
        rows.append(
            {
                "quarter": f"{year}Q{quarter}",
                "dataset_form4_submissions": ours,
                "edgar_index_form4_unique_accessions": theirs,
                "edgar_index_form4_lines": form4_lines,
                "relative_delta": round(delta, 4),
                "within_tolerance": delta <= RECONCILE_TOLERANCE,
            }
        )
        if verbose:
            print(
                f"  {year}Q{quarter}: dataset {ours:,} vs index accessions {theirs:,} "
                f"(lines {form4_lines:,}, delta {delta:.2%})"
            )

    if not rows:
        return None, rows
    return all(row["within_tolerance"] for row in rows), rows


def current_git_sha() -> str:
    """SHA the artifact was produced at — required for gate-run traceability.

    A dirty tree is marked: an artifact from uncommitted code must not claim
    the parent commit produced it.
    """

    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
    ).strip()
    return f"{sha}-dirty" if dirty else sha


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
    notes = artifact.get("notes") or {}
    f0 = notes.get("f0") or {}
    lines = [
        "# CFOB Stage D + F0 results",
        "",
        f"**Date:** {date.today().isoformat()}  ",
        f"**Git SHA:** `{artifact.get('git_sha')}`  ",
        "**Driver:** `fixtures/real-continuous/reports/research_cfob.py`  ",
        "**Artifact:** `fixtures/real-continuous/reports/cfob-structure.json`  ",
        "**Parent PRD:** #76 (grilled 2026-07-21)  ",
        "**ADR:** `docs/adr/0002-cfob-gate-law-divergence.md`",
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
        lines.append(
            f"- {field}: `{value:,}`" if isinstance(value, int) else f"- {field}: `{value}`"
        )
    lines += ["", "## Year shares", ""]
    for year, share in sorted(shares.items(), key=lambda item: str(item[0])):
        lines.append(f"- {year}: {share:.4f}")
    lines += ["", "## Gates (D + F0 combined)", ""]
    for gate in gates:
        status = "PASS" if gate["passed"] else "FAIL"
        lines.append(f"- **{gate['id']}** [{gate['severity']}] **{status}** — {gate['reason']}")
    if f0:
        lines += [
            "",
            "## Stage F0 detail",
            "",
            f"- F0 sub-verdict (informational; top-level already combines): `{f0.get('verdict')}`",
            f"- reference source: `{f0.get('reference_source')}`",
            f"- mapped purchases: `{f0.get('mapped_purchases')}`",
            f"- total purchases mapped against: `{f0.get('total_purchases')}`",
            f"- ambiguous multi-match: `{f0.get('ambiguous_purchases')}`",
        ]
    lines += [
        "",
        "## What this does and does not claim",
        "",
        "### Claims",
        "",
        "- Density, spread, and tape-integrity of insider purchase clusters on the free "
        "SEC tape (2006-), measured against floors frozen before any returns existed.",
        "- The density floor is derived from Gate-1a's measured dispersion, not chosen "
        "for convenience.",
        "- Purchase-level mapping is a CIK-primary identity join against the Sharadar "
        "TICKERS reference, with the frozen tiebreak ladder: exact as-filed symbol → "
        "related symbols → sole covering row → ambiguous-excluded, counted (grill "
        "2026-07-21). The as-filed symbol never establishes identity on its own.",
        "",
        "### Non-claims",
        "",
        "- **No returns were measured.** Stages D/F0 count and integrity-check events; "
        "they say nothing about whether insider clusters predict anything.",
        "- Not capital permission; `capital_go` is false by construction.",
        "- Not a reopening of residual, R2-1, PEAD, or CMFT #74.",
        "- The $5 price floor is diagnostic on adjusted closes only (ADR 0002); dollar "
        "volume is the binding habitat gate.",
        "",
        "## How to re-run",
        "",
        "```bash",
        "uv run python fixtures/real-continuous/reports/research_cfob.py --pull-only",
        "CFOB_SEP_DIR=fixtures/full-depth-sep \\",
        "  uv run python fixtures/real-continuous/reports/research_cfob.py --measure-only --write-docs",
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
    parser.add_argument(
        "--skip-reconcile",
        action="store_true",
        help="skip EDGAR form.idx reconcile (fail-closed unless synthetic)",
    )
    parser.add_argument(
        "--e1",
        action="store_true",
        help="Stage E1 returns measurement (separately authorised, PRD #76)",
    )
    args = parser.parse_args()

    through = date.today()

    if args.e1:
        return run_e1(synthetic=args.synthetic, write_docs_flag=args.write_docs)

    if args.synthetic:
        raw = synthetic_clusters()
        deoverlapped = list(de_overlap(raw))
        shares = year_shares(deoverlapped)
        d_report = evaluate_stage_d(de_overlapped_clusters=len(deoverlapped), shares=shares)
        f0_report = evaluate_stage_f0(
            protocol_present=True,
            trial_ledger_present=True,
            mapped=len(deoverlapped),
            total=len(deoverlapped),
            unmapped_by_year={},
            total_by_year={year: 1 for year in range(2006, 2026)},
            reconciled=True,
            archives_expected=1,
            archives_parsed=1,
            derivative_rows_in_qualified=0,
            amendment_dedupe_measured=True,
            late_filed=0,
            qualified=len(deoverlapped),
        )
        combined = combine_stage_reports(d_report, f0_report)
        artifact = build_cfob_artifact(
            stage="D+F0",
            report=combined,
            counts=QualificationCounts(),
            raw_clusters=len(raw),
            de_overlapped_clusters=len(deoverlapped),
            shares=shares,
            mode="synthetic",
            git_sha=current_git_sha(),
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

    if not SEP_DIR.is_dir():
        raise SystemExit(
            f"fail-closed: SEP panel not found at {SEP_DIR}. "
            "Set CFOB_SEP_DIR to the full-depth SEP year-parquet directory."
        )

    print("Loading TICKERS reference for CIK-primary mapping...")
    listings, window_source = load_reference_listings()
    mapping = map_purchases_by_cik(purchases, listings)
    print(
        f"  mapped purchases: {mapping.mapped_count:,} / {mapping.total_count:,} "
        f"(ambiguous {len(mapping.ambiguous):,}; source={window_source})"
    )
    for reason, count in sorted(mapping.reason_counts.items(), key=lambda kv: -kv[1]):
        print(f"    {reason}: {count:,}")
    if mapping.mapped_count == 0:
        raise SystemExit("fail-closed: zero purchases mapped via CIK reference")

    print("Building clusters on canonical Sharadar symbols...")
    # The canonical symbol is what SEP prices — so renamed issuers (as-filed
    # SYMC → GEN row) now find their price history downstream.
    canonical_purchases = [
        replace(purchase, trading_symbol=canonical_symbol)
        for purchase, canonical_symbol in mapping.canonical
    ]
    raw = list(build_clusters(canonical_purchases))
    print(f"  raw clusters: {len(raw):,}")

    print(f"Applying habitat universe filter from SEP ({SEP_DIR})...")
    eligible, sessions, diagnostics = apply_universe_filter(raw)
    print(f"  universe-eligible clusters: {len(eligible):,}")
    if not eligible:
        raise SystemExit(
            "fail-closed: universe filter admitted zero clusters from "
            f"{len(raw):,} raw. That is a data/join failure, not a density result."
        )

    print("De-overlapping (first-wins, h60)...")
    deoverlapped = list(de_overlap(eligible, sessions_by_symbol=sessions))
    print(f"  de-overlapped clusters: {len(deoverlapped):,}")

    shares = year_shares(deoverlapped)
    d_report = evaluate_stage_d(de_overlapped_clusters=len(deoverlapped), shares=shares)

    counts_obj = QualificationCounts(
        **{field: counts.get(field, 0) for field in QualificationCounts.__dataclass_fields__}
    )

    print("\nRunning Stage F0 integrity gates...")
    if args.skip_reconcile:
        reconciled, reconcile_rows = None, []
        print("  reconcile skipped (--skip-reconcile) → fail closed")
    else:
        reconciled, reconcile_rows = reconcile_against_edgar_index()

    # F5/F6 are measured over the qualified stream, not asserted: provenance is
    # stamped by the adapter, and residual amendment collisions must be zero.
    derivative_rows = sum(1 for p in purchases if p.source_table != "NONDERIV_TRANS")
    amendment_collisions = amendment_collision_count(purchases)

    f0_report = evaluate_stage_f0(
        protocol_present=True,
        trial_ledger_present=True,
        mapped=mapping.mapped_count,
        total=mapping.total_count,
        unmapped_by_year=mapping.unmapped_by_year,
        total_by_year=mapping.total_by_year,
        reconciled=reconciled,
        archives_expected=counts.get("archives_expected"),
        archives_parsed=counts.get("archives_parsed"),
        derivative_rows_in_qualified=derivative_rows,
        amendment_dedupe_measured=amendment_collisions == 0,
        late_filed=counts_obj.late_filed,
        qualified=counts_obj.qualified,
    )
    print(f"Stage F0 verdict: {f0_report.verdict}")
    for gate in f0_report.to_dict()["gates"]:
        print(f"  {'PASS' if gate['passed'] else 'FAIL'} {gate['id']}: {gate['reason']}")

    combined = combine_stage_reports(d_report, f0_report)
    artifact = build_cfob_artifact(
        stage="D+F0",
        report=combined,
        counts=counts_obj,
        raw_clusters=len(raw),
        de_overlapped_clusters=len(deoverlapped),
        shares=shares,
        mode="sec-insider-tape-2006-present",
        git_sha=current_git_sha(),
        notes={
            "quarters_read": counts.get("quarters_read", 0),
            "dedupe_scope": (
                "single global pass over all code-P rows before qualification; "
                "a cross-quarter 4/A can supersede or disqualify its original"
            ),
            "universe_eligible_clusters": len(eligible),
            "stage_d": {
                "verdict": d_report.verdict,
                "all_hard_gates_passed": d_report.all_hard_gates_passed,
                "gates": d_report.to_dict()["gates"],
            },
            "f0": {
                "verdict": f0_report.verdict,
                "all_hard_gates_passed": f0_report.all_hard_gates_passed,
                "gates": f0_report.to_dict()["gates"],
                "reference_source": window_source,
                "mapped_purchases": mapping.mapped_count,
                "total_purchases": mapping.total_count,
                "ambiguous_purchases": len(mapping.ambiguous),
                "unmapped_by_year": mapping.unmapped_by_year,
                "total_by_year": mapping.total_by_year,
                "derivative_rows_in_qualified": derivative_rows,
                "amendment_collisions": amendment_collisions,
                "reconcile_sample": reconcile_rows,
                "reconcile_tolerance": RECONCILE_TOLERANCE,
                "reconcile_sample_quarters": [f"{y}Q{q}" for y, q in RECONCILE_SAMPLE],
            },
            **diagnostics,
        },
    )
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2, default=str))
    if args.write_docs:
        write_docs(artifact)

    print(f"\nCombined D+F0 verdict: {artifact['verdict']}")
    for gate in artifact["gates"]:
        print(f"  {'PASS' if gate['passed'] else 'FAIL'} {gate['id']}: {gate['reason']}")
    return 0


# --- Stage E1 (returns) --------------------------------------------------------
#
# Separately authorised (PRD #76 grill session 2, Q3 = option 1; merge of #77
# first). The cohort is re-derived at runtime through the SAME code path as
# D+F0 — qualify → CIK map → clusters → habitat universe → first-wins
# de-overlap — and cross-checked against the published D+F0 artifact before a
# single return is measured. ``capital_go`` stays false whatever E1 finds.

E1_ARTIFACT_PATH = REPORTS_DIR / "cfob-e1.json"
E1_SYNTHETIC_ARTIFACT_PATH = REPORTS_DIR / "cfob-e1-synthetic.json"
E1_DOCS_PATH = REPO_ROOT / "docs" / "research" / "cfob-e1-results.md"
SPY_SIDECAR = REPORTS_DIR / "spy-opens-cfob-sidecar.json"
SPY_TICKER = "SPY"
PLACEBO_SEED = 20260722
E1_HORIZONS = (20, 60, 120)
E1_SYMBOL_CHUNK = 1500


def load_or_fetch_spy_adjusted_opens(start: date, end: date) -> tuple[dict[date, float], dict]:
    """SPY total-return-adjusted opens (open x adjclose/close), sidecar-cached.

    SEP carries no ETFs and SFP is not entitled (I0 probe 2026-07-21; re-probed
    2026-07-22: zero rows with a recent-date filter). Matched-SPY therefore
    follows the Phase-2b precedent: real SPY via the Yahoo chart API, cached in
    a committed sidecar, provenance recorded in the artifact. Opens are
    dividend+split adjusted exactly the way the SEP panel's ``open_adj`` is, so
    both legs of the comparison share one return convention.
    """

    provenance: dict = {
        "symbol": SPY_TICKER,
        "sidecar_path": str(SPY_SIDECAR.relative_to(REPO_ROOT)),
        "adjustment": "open * adjclose / close (matches SEP open_adj convention)",
        "span_required": {"start": start.isoformat(), "end": end.isoformat()},
    }
    if SPY_SIDECAR.is_file():
        payload = json.loads(SPY_SIDECAR.read_text())
        span = payload.get("span", {})
        if (
            span.get("start", "9999") <= start.isoformat()
            and span.get("end", "0") >= end.isoformat()
        ):
            opens = {date.fromisoformat(k): float(v) for k, v in payload["opens"].items()}
            provenance["source"] = "sidecar-file"
            provenance["session_count"] = len(opens)
            return opens, provenance

    import httpx

    from datetime import datetime, timezone

    print(f"  fetching SPY adjusted opens {start}..{end} (yahoo-chart-v8)...")
    period1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    end_plus = end + timedelta(days=2)
    period2 = int(
        datetime(end_plus.year, end_plus.month, end_plus.day, tzinfo=timezone.utc).timestamp()
    )
    resp = httpx.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{SPY_TICKER}",
        params={
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "div,splits",
        },
        timeout=120.0,
        headers={"User-Agent": "invest-research/cfob-e1"},
        follow_redirects=True,
    )
    resp.raise_for_status()
    body = resp.json()
    result = (body.get("chart") or {}).get("result") or []
    if not result:
        raise SystemExit(
            f"fail-closed: Yahoo chart empty for SPY: {body.get('chart', {}).get('error')}"
        )
    series = result[0]
    timestamps = series.get("timestamp") or []
    quote = (series.get("indicators") or {}).get("quote") or [{}]
    adj = (series.get("indicators") or {}).get("adjclose") or [{}]
    raw_opens = quote[0].get("open") or []
    raw_closes = quote[0].get("close") or []
    adj_closes = adj[0].get("adjclose") or []
    opens: dict[date, float] = {}
    from datetime import datetime as _dt

    for ts, o, c, ac in zip(timestamps, raw_opens, raw_closes, adj_closes, strict=False):
        if o is None or c is None or ac is None or o <= 0 or c <= 0 or ac <= 0:
            continue
        day = _dt.fromtimestamp(int(ts), tz=timezone.utc).date()
        if day < start or day > end:
            continue
        opens[day] = float(o) * float(ac) / float(c)
    if not opens:
        raise SystemExit("fail-closed: no SPY opens in Yahoo response for requested span")
    SPY_SIDECAR.write_text(
        json.dumps(
            {
                "symbol": SPY_TICKER,
                "source": "yahoo-chart-v8",
                "adjustment": "open * adjclose / close",
                "span": {"start": start.isoformat(), "end": end.isoformat()},
                "opens": {d.isoformat(): repr(px) for d, px in sorted(opens.items())},
            },
            indent=1,
            sort_keys=True,
        )
    )
    provenance["source"] = "yahoo-chart-v8-fetch"
    provenance["session_count"] = len(opens)
    return opens, provenance


def _derive_symbol_stats(opens, closes, volumes, *, horizons):
    """Per-symbol eligibility masks and open-to-open forward returns.

    Eligibility at index i uses only bars strictly before i (the last
    ``dollar_volume_window`` bars for the median dollar volume, and
    ``min_history_bars`` bars of history) — the same information the habitat
    filter had at cluster known-time, since entry is always after known-time.
    """

    import numpy as np

    n = len(opens)
    window = PROTOCOL.dollar_volume_window
    dollar_volume = closes * volumes
    med20 = np.full(n, np.nan)
    if n > window:
        from numpy.lib.stride_tricks import sliding_window_view

        rolled = np.median(sliding_window_view(dollar_volume, window), axis=1)
        med20[window:] = rolled[: n - window]
    history_ok = np.arange(n) >= PROTOCOL.min_history_bars
    eligible = history_ok & (med20 >= float(PROTOCOL.min_dollar_volume))
    band10m = eligible & (med20 >= float(PROTOCOL.secondary_min_dollar_volume))
    rets = {}
    for horizon in horizons:
        forward = np.full(n, np.nan)
        if n > horizon:
            entry = opens[: n - horizon]
            exit_ = opens[horizon:]
            valid = (entry > 0) & (exit_ > 0)
            forward[: n - horizon] = np.where(valid, exit_ / entry - 1.0, np.nan)
        rets[horizon] = forward
    return rets, eligible, band10m


def e1_price_pass(cluster_symbols: set[str], *, verbose: bool = True):
    """One sequential sweep of the SEP panel, chunked by symbol.

    Produces (a) per-session habitat-eligible-universe mean forward returns for
    every horizon (the excess benchmark) and (b) full-span per-symbol series
    for the cluster symbols (event and placebo returns). Symbols are processed
    in chunks so the host never holds the whole panel at once.
    """

    import numpy as np
    import pyarrow.parquet as pq

    wanted = ["symbol", "date", "open_adj", "close_adj", "volume"]
    years = sorted(
        year
        for year in (int(path.stem.split("_")[1]) for path in SEP_DIR.glob("sep_*.parquet"))
        if year >= FIRST_YEAR - 2
    )
    if not years:
        raise SystemExit(f"fail-closed: no SEP year parquet found in {SEP_DIR}")
    paths = []
    for year in years:
        path = SEP_DIR / f"sep_{year}.parquet"
        available = set(pq.ParquetFile(path).schema_arrow.names)
        missing = [column for column in wanted if column not in available]
        if missing:
            raise SystemExit(f"fail-closed: SEP {year} missing columns {missing}")
        paths.append(path)

    all_symbols: set[str] = set()
    for path in paths:
        all_symbols.update(pq.read_table(path, columns=["symbol"]).column("symbol").to_pylist())
    ordered_symbols = sorted(all_symbols)
    chunks = [
        ordered_symbols[i : i + E1_SYMBOL_CHUNK]
        for i in range(0, len(ordered_symbols), E1_SYMBOL_CHUNK)
    ]
    if verbose:
        print(
            f"  E1 price pass: {len(ordered_symbols):,} symbols in {len(chunks)} chunks, "
            f"years {years[0]}..{years[-1]}"
        )

    day0 = int(np.datetime64(f"{FIRST_YEAR}-01-01").astype("datetime64[D]").astype(int))
    ndays = int(np.datetime64(f"{years[-1]}-12-31").astype("datetime64[D]").astype(int)) - day0 + 1
    uni_sum = {h: np.zeros(ndays) for h in E1_HORIZONS}
    uni_cnt = {h: np.zeros(ndays, dtype=np.int64) for h in E1_HORIZONS}
    sym_data: dict[str, dict] = {}

    import pandas as pd

    for index, chunk in enumerate(chunks, start=1):
        frames = []
        for path in paths:
            table = pq.read_table(path, columns=wanted, filters=[("symbol", "in", chunk)])
            frames.append(table.to_pandas())
        panel = pd.concat(frames, ignore_index=True)
        del frames
        panel.sort_values(["symbol", "date"], inplace=True, kind="mergesort")
        for symbol, group in panel.groupby("symbol", observed=True, sort=False):
            dates64 = group["date"].to_numpy().astype("datetime64[D]")
            opens = group["open_adj"].to_numpy(dtype=np.float64)
            closes = group["close_adj"].to_numpy(dtype=np.float64)
            volumes = group["volume"].to_numpy(dtype=np.float64)
            rets, eligible, band10m = _derive_symbol_stats(
                opens, closes, volumes, horizons=E1_HORIZONS
            )
            day_index = dates64.astype(int) - day0
            in_span = day_index >= 0
            for horizon in E1_HORIZONS:
                mask = eligible & in_span & np.isfinite(rets[horizon])
                if mask.any():
                    np.add.at(uni_sum[horizon], day_index[mask], rets[horizon][mask])
                    np.add.at(uni_cnt[horizon], day_index[mask], 1)
            if symbol in cluster_symbols:
                sym_data[symbol] = {
                    "dates": dates64,
                    "day_index": day_index,
                    "rets": {h: rets[h].astype(np.float32) for h in E1_HORIZONS},
                    "eligible": eligible,
                    "band10m": band10m,
                }
        del panel
        if verbose:
            print(f"  chunk {index}/{len(chunks)} done")

    return uni_sum, uni_cnt, day0, sym_data


def e1_measure(
    deoverlapped: list[PurchaseCluster],
    uni_sum,
    uni_cnt,
    day0: int,
    sym_data: dict[str, dict],
    spy_opens: dict[date, float],
    *,
    verbose: bool = True,
) -> tuple[dict, dict, "object"]:
    """Assemble events, run the placebo null, and evaluate the frozen E1 gates.

    Returns (measurements, exclusions, gate report). Every dropped event is
    counted under a reason; nothing shrinks silently.
    """

    import numpy as np

    horizon = PROTOCOL.horizon_sessions
    uni_mean = {
        h: np.where(uni_cnt[h] > 0, uni_sum[h] / np.maximum(uni_cnt[h], 1), np.nan)
        for h in E1_HORIZONS
    }

    exclusions: dict[str, int] = defaultdict(int)
    events: list[dict] = []
    for cluster in deoverlapped:
        record = sym_data.get(cluster.trading_symbol)
        if record is None:
            exclusions["symbol_missing_price_series"] += 1
            continue
        known64 = np.datetime64(cluster.known_time.isoformat())
        i = int(np.searchsorted(record["dates"], known64, side="right"))
        n = len(record["dates"])
        if i >= n:
            exclusions["no_entry_session"] += 1
            continue
        gross = float(record["rets"][horizon][i])
        if not np.isfinite(gross):
            exclusions["incomplete_horizon"] += 1
            continue
        day_index = int(record["day_index"][i])
        if day_index < 0 or day_index >= len(uni_mean[horizon]):
            exclusions["entry_outside_measured_span"] += 1
            continue
        universe = float(uni_mean[horizon][day_index])
        if not np.isfinite(universe):
            exclusions["no_universe_mean"] += 1
            continue
        entry_date = record["dates"][i].astype(object)
        exit_date = record["dates"][i + horizon].astype(object)
        events.append(
            {
                "symbol": cluster.trading_symbol,
                "entry_index": i,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "gross": gross,
                "universe": universe,
                "band10m": bool(record["band10m"][i]),
            }
        )

    if not events:
        raise SystemExit(
            "fail-closed: zero measurable E1 events — data/join failure, not a verdict"
        )

    # Placebo candidates: the symbol's habitat-eligible sessions with full
    # horizon coverage and a universe mean, inside the measured span.
    candidates_by_symbol: dict[str, "np.ndarray"] = {}
    for symbol in {event["symbol"] for event in events}:
        record = sym_data[symbol]
        day_index = record["day_index"]
        rets60 = record["rets"][horizon].astype(np.float64)
        in_span = (day_index >= 0) & (day_index < len(uni_mean[horizon]))
        safe_index = np.clip(day_index, 0, len(uni_mean[horizon]) - 1)
        universe_at = uni_mean[horizon][safe_index]
        mask = record["eligible"] & in_span & np.isfinite(rets60) & np.isfinite(universe_at)
        if mask.any():
            candidates_by_symbol[symbol] = rets60[mask] - universe_at[mask]

    measurable = [event for event in events if event["symbol"] in candidates_by_symbol]
    exclusions["no_placebo_candidates"] += len(events) - len(measurable)
    events = measurable
    realized_n = len(events)
    if verbose:
        print(f"  measurable events: {realized_n:,} (exclusions: {dict(exclusions)})")

    placebo = run_placebo(
        candidates_by_symbol,
        [event["symbol"] for event in events],
        draws=PROTOCOL.future_placebo_draws,
        seed=PLACEBO_SEED,
    )

    gross_excess = [event["gross"] - event["universe"] for event in events]
    clusters_key = [event["entry_date"].isoformat() for event in events]
    differenced = [g - p for g, p in zip(gross_excess, placebo.per_event_mean, strict=True)]

    from statistics import median as _median

    ladder: dict[str, dict] = {}
    primary_key = f"{PROTOCOL.future_primary_cost_bps:g}bps"
    for bps in E1_COST_LADDER_BPS:
        round_trip = 2.0 * bps / 10_000.0
        values = [v - round_trip for v in differenced]
        mean, t, n = clustered_t(values, clusters_key)
        ladder[f"{bps:g}bps"] = {
            "cost_bps_per_side": bps,
            "mean": mean,
            "clustered_t": t,
            "median_diagnostic": _median(values),
            "n": n,
        }

    primary_round_trip = 2.0 * PROTOCOL.future_primary_cost_bps / 10_000.0
    primary_values = [v - primary_round_trip for v in differenced]
    winsorized = winsorize(primary_values, tail=PROTOCOL.future_winsor_tail)
    winsor_mean, winsor_t, _ = clustered_t(winsorized, clusters_key)

    contribution = contribution_shares(
        [(event["entry_date"], value) for event, value in zip(events, primary_values, strict=True)]
    )
    by_year_contribution: dict[str, float] = defaultdict(float)
    for event, value in zip(events, primary_values, strict=True):
        by_year_contribution[str(event["entry_date"].year)] += value

    observed_mean_gross, gross_t, _ = clustered_t(gross_excess, clusters_key)
    percentile = empirical_percentile(observed_mean_gross, placebo.draw_cohort_means)

    # Matched-SPY trade windows: the long leg net of the primary cost rung must
    # beat the same-window SPY return. Events without both SPY opens are
    # counted, excluded from this comparison only.
    spy_values: list[float] = []
    spy_clusters: list[str] = []
    spy_missing = 0
    for event in events:
        entry_open = spy_opens.get(event["entry_date"])
        exit_open = spy_opens.get(event["exit_date"])
        if entry_open is None or exit_open is None or entry_open <= 0:
            spy_missing += 1
            continue
        spy_return = exit_open / entry_open - 1.0
        spy_values.append((event["gross"] - primary_round_trip) - spy_return)
        spy_clusters.append(event["entry_date"].isoformat())
    spy_mean, spy_t, spy_n = (
        clustered_t(spy_values, spy_clusters) if spy_values else (None, None, 0)
    )
    exclusions["matched_spy_window_missing"] = spy_missing

    # Secondary diagnostics: h20/h120 gross excess, and the $10M house band.
    secondary: dict[str, dict] = {}
    for h in E1_HORIZONS:
        if h == horizon:
            continue
        values: list[float] = []
        keys: list[str] = []
        dropped = 0
        for event in events:
            record = sym_data[event["symbol"]]
            i = event["entry_index"]
            ret = float(record["rets"][h][i])
            day_index = int(record["day_index"][i])
            universe = (
                float(uni_mean[h][day_index]) if 0 <= day_index < len(uni_mean[h]) else float("nan")
            )
            if not (np.isfinite(ret) and np.isfinite(universe)):
                dropped += 1
                continue
            values.append(ret - universe)
            keys.append(event["entry_date"].isoformat())
        mean_h, t_h, n_h = clustered_t(values, keys) if values else (None, None, 0)
        secondary[f"h{h}"] = {
            "gross_excess_mean": mean_h,
            "clustered_t": t_h,
            "n": n_h,
            "incomplete": dropped,
        }

    band_values = [g for event, g in zip(events, gross_excess, strict=True) if event["band10m"]]
    band_keys = [event["entry_date"].isoformat() for event in events if event["band10m"]]
    band_mean, band_t, band_n = (
        clustered_t(band_values, band_keys) if band_values else (None, None, 0)
    )

    hit_rate = sum(1 for v in gross_excess if v > 0) / realized_n

    report = evaluate_stage_e1(
        realized_n=realized_n,
        placebo_t=ladder[primary_key]["clustered_t"],
        trimmed_t=winsor_t,
        max_year_contribution_share=contribution["max_year_share"],
        mean_net_minus_spy=spy_mean,
        max_month_contribution_share=contribution["max_month_share"],
    )

    universe_counts = uni_cnt[horizon][uni_cnt[horizon] > 0]
    measurements = {
        "cohort": {
            "de_overlapped_clusters": len(deoverlapped),
            "measured_events": realized_n,
            "mds_at_cohort_n": min_detectable_size(n_events=len(deoverlapped)),
            "mds_at_realized_n": min_detectable_size(n_events=realized_n),
        },
        "h60": {
            "raw_excess_gross": {
                "mean": observed_mean_gross,
                "clustered_t": gross_t,
                "median_diagnostic": _median(gross_excess),
                "hit_rate_gt0": hit_rate,
                "n": realized_n,
            },
            "placebo": {
                "draws": placebo.draws,
                "seed": placebo.seed,
                "mean_of_per_event_means": sum(placebo.per_event_mean) / realized_n,
                "mean_of_draw_cohort_means": (
                    sum(placebo.draw_cohort_means) / len(placebo.draw_cohort_means)
                ),
                "observed_gross_mean_percentile": percentile,
            },
            "placebo_differenced_net_ladder": ladder,
            "winsorized_primary": {
                "tail": PROTOCOL.future_winsor_tail,
                "mean": winsor_mean,
                "clustered_t": winsor_t,
            },
            "contribution_at_primary_cost": {
                "max_year_share": contribution["max_year_share"],
                "max_month_share": contribution["max_month_share"],
                "by_year": dict(sorted(by_year_contribution.items())),
            },
            "matched_spy_net_primary": {
                "mean_net_minus_spy": spy_mean,
                "clustered_t": spy_t,
                "n": spy_n,
                "missing_windows": spy_missing,
            },
            "secondary_band_10m_gross_excess": {
                "mean": band_mean,
                "clustered_t": band_t,
                "n": band_n,
            },
        },
        "secondary_horizons": secondary,
        "universe_baseline": {
            "sessions_with_h60_mean": int((uni_cnt[horizon] > 0).sum()),
            "min_symbols_per_session": int(universe_counts.min()) if len(universe_counts) else 0,
            "median_symbols_per_session": (
                float(np.median(universe_counts)) if len(universe_counts) else 0.0
            ),
        },
    }
    return measurements, dict(exclusions), report


def write_e1_docs(artifact: dict) -> None:
    gates = artifact["gates"]
    h60 = artifact["measurements"]["h60"]
    ladder = h60["placebo_differenced_net_ladder"]
    cohort = artifact["measurements"]["cohort"]
    lines = [
        "# CFOB Stage E1 results — insider purchase-cluster event study",
        "",
        f"**Date:** {date.today().isoformat()}  ",
        f"**Git SHA:** `{artifact.get('git_sha')}`  ",
        "**Driver:** `fixtures/real-continuous/reports/research_cfob.py --e1`  ",
        "**Artifact:** `fixtures/real-continuous/reports/cfob-e1.json`  ",
        "**Parent PRD:** #76 (grilled 2026-07-21; E1 separately authorised)  ",
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
        f"- de-overlapped clusters (input): `{cohort['de_overlapped_clusters']:,}`",
        f"- measured events (realized n): `{cohort['measured_events']:,}`",
        f"- MDS at realized n: `{cohort['mds_at_realized_n']:.4f}` (bar 0.0125)",
        f"- exclusions: `{artifact['exclusions']}`",
        "",
        "## Primary measurement (h60, placebo-differenced, net of cost)",
        "",
        "| Rung | Mean | Clustered t | Median (diagnostic) |",
        "|---|---|---|---|",
    ]
    for key, row in ladder.items():
        marker = (
            " **(primary)**" if row["cost_bps_per_side"] == PROTOCOL.future_primary_cost_bps else ""
        )
        lines.append(
            f"| {key}{marker} | {row['mean']:+.5f} | {row['clustered_t']:.3f} | "
            f"{row['median_diagnostic']:+.5f} |"
        )
    raw = h60["raw_excess_gross"]
    placebo = h60["placebo"]
    spy = h60["matched_spy_net_primary"]
    lines += [
        "",
        f"- raw gross excess: mean `{raw['mean']:+.5f}`, clustered t `{raw['clustered_t']:.3f}`, "
        f"median `{raw['median_diagnostic']:+.5f}`, hit rate `{raw['hit_rate_gt0']:.3f}`",
        f"- placebo null: draws `{placebo['draws']}`, seed `{placebo['seed']}`, "
        f"placebo mean `{placebo['mean_of_draw_cohort_means']:+.5f}`, observed percentile "
        f"`{placebo['observed_gross_mean_percentile']:.2f}`",
        f"- winsorized (1/99) primary: mean `{h60['winsorized_primary']['mean']:+.5f}`, "
        f"clustered t `{h60['winsorized_primary']['clustered_t']:.3f}`",
        f"- matched SPY (net, primary rung): mean diff `{spy['mean_net_minus_spy']:+.5f}`, "
        f"t `{spy['clustered_t']:.3f}`, n `{spy['n']:,}`, missing `{spy['missing_windows']}`",
        f"- contribution: max year share "
        f"`{h60['contribution_at_primary_cost']['max_year_share']:.4f}`, max month share "
        f"`{h60['contribution_at_primary_cost']['max_month_share']:.4f}` (month is diagnostic)",
        "",
        "### Contribution by entry year (share of positive total, primary rung)",
        "",
    ]
    by_year = h60["contribution_at_primary_cost"]["by_year"]
    positive_total = sum(v for v in by_year.values() if v > 0)
    for year, value in sorted(by_year.items(), key=lambda kv: -kv[1])[:6]:
        share = value / positive_total if positive_total > 0 else 0.0
        lines.append(f"- {year}: `{value:+.2f}` (share `{share:.3f}`)")
    secondary = artifact["measurements"].get("secondary_horizons", {})
    band = h60["secondary_band_10m_gross_excess"]
    lines += [
        "",
        "## Secondary diagnostics (never promotable to primary)",
        "",
    ]
    for name, row in secondary.items():
        lines.append(
            f"- {name} gross excess: mean `{row['gross_excess_mean']:+.5f}`, "
            f"t `{row['clustered_t']:.3f}`, n `{row['n']:,}` (incomplete `{row['incomplete']}`)"
        )
    lines += [
        f"- $10M house band gross excess: mean `{band['mean']:+.5f}`, "
        f"t `{band['clustered_t']:.3f}`, n `{band['n']:,}`",
        "",
        "## Gates",
        "",
    ]
    for gate in gates:
        status = "PASS" if gate["passed"] else "FAIL"
        lines.append(f"- **{gate['id']}** [{gate['severity']}] **{status}** — {gate['reason']}")
    lines += [
        "",
        "## What this does and does not claim",
        "",
        "### Claims",
        "",
        "- One pre-registered event study on the de-overlapped D+F0 cohort: h60 open-to-open "
        "excess vs the same-entry-date habitat-eligible-universe mean, measured against the "
        "within-ticker date-shuffled placebo null, net of the frozen cost ladder.",
        "- The placebo isolates timing: firms are preserved, dates are shuffled, so cohort "
        "composition cannot manufacture the primary statistic.",
        "",
        "### Non-claims",
        "",
        "- Not capital permission; `capital_go` is false by construction.",
        "- No secondary band, horizon, or diagnostic can promote itself to primary.",
        "- Not a reopening of residual, R2-1, PEAD, or CMFT #74.",
        "- A kill or underpowered-stop re-seals Full-Stop immediately (grill Q8; "
        "`docs/research/full-stop-seal.md`).",
        "",
        "## Decisions the PRD did not settle (flagged, not silently chosen)",
        "",
        "- **SPY source**: SEP has no ETFs and SFP is not entitled (re-probed at run time: "
        "zero rows). Matched-SPY uses real SPY opens via the Yahoo chart API per the "
        "Phase-2b precedent, dividend/split-adjusted like SEP `open_adj`, committed sidecar, "
        "provenance in the artifact.",
        "- **Cost application**: the round-trip cost is charged to the traded (event) leg "
        "only; the placebo leg stays gross. A cost-symmetric placebo would cancel and make "
        "the frozen 10/25/50 ladder vacuous on the primary gate.",
        "- **Month-share**: the PRD names 'a month-share bound' with no frozen number; it is "
        "reported as a diagnostic, never gated.",
        "- **Delisting truncation**: events whose h60 window is not fully covered are "
        "excluded and counted (`incomplete_horizon`), the reused Gate-1a full-window "
        "convention; placebo candidates obey the same rule, so the differencing does not "
        "inherit a one-sided bias.",
        "",
        "## How to re-run",
        "",
        "```bash",
        "CFOB_SEP_DIR=fixtures/full-depth-sep CFOB_TAPE_DIR=<tape-cache> \\",
        "  uv run python fixtures/real-continuous/reports/research_cfob.py --e1 --write-docs",
        "```",
        "",
    ]
    E1_DOCS_PATH.write_text("\n".join(lines))


def _e1_synthetic_run(*, write_docs_flag: bool) -> int:
    """Deterministic smoke for the E1 wiring — claims nothing.

    Builds a tiny synthetic panel and cohort, then exercises the exact
    measurement path (placebo, ladder, gates, artifact). The cohort is far
    below the power floor by construction, so the verdict must be
    ``underpowered_stop`` — a wiring regression that flips it is loud.
    """

    import numpy as np

    sessions: list[date] = []
    day = date(2018, 1, 1)
    while len(sessions) < 900:
        if day.weekday() < 5:
            sessions.append(day)
        day += timedelta(days=1)
    dates64 = np.array([np.datetime64(s.isoformat()) for s in sessions], dtype="datetime64[D]")
    day0 = int(np.datetime64("2018-01-01").astype("datetime64[D]").astype(int))
    ndays = int(dates64[-1].astype(int)) - day0 + 1

    uni_sum = {h: np.zeros(ndays) for h in E1_HORIZONS}
    uni_cnt = {h: np.zeros(ndays, dtype=np.int64) for h in E1_HORIZONS}
    sym_data: dict[str, dict] = {}
    clusters: list[PurchaseCluster] = []
    for k in range(30):
        symbol = f"SYN{k}"
        drift = 0.0001 + 0.00001 * (k % 5)
        t = np.arange(900, dtype=np.float64)
        opens = 50.0 * (1.0 + drift) ** t * (1.0 + 0.01 * np.sin(t / 7.0 + k))
        closes = opens
        volumes = np.full(900, 1_000_000.0)
        rets, eligible, band10m = _derive_symbol_stats(opens, closes, volumes, horizons=E1_HORIZONS)
        day_index = dates64.astype(int) - day0
        for h in E1_HORIZONS:
            mask = eligible & np.isfinite(rets[h])
            np.add.at(uni_sum[h], day_index[mask], rets[h][mask])
            np.add.at(uni_cnt[h], day_index[mask], 1)
        sym_data[symbol] = {
            "dates": dates64,
            "day_index": day_index,
            "rets": {h: rets[h].astype(np.float32) for h in E1_HORIZONS},
            "eligible": eligible,
            "band10m": band10m,
        }
        known = sessions[400 + k]
        clusters.append(
            PurchaseCluster(
                trading_symbol=symbol,
                issuer_cik=f"{k:07d}",
                known_time=known,
                first_transaction_date=known - timedelta(days=5),
                last_transaction_date=known - timedelta(days=1),
                distinct_insiders=2,
                purchase_count=2,
                gross_value=Decimal("50000"),
            )
        )
    spy_opens = {s: 200.0 * (1.0002**i) for i, s in enumerate(sessions)}

    measurements, exclusions, report = e1_measure(
        clusters, uni_sum, uni_cnt, day0, sym_data, spy_opens
    )
    artifact = build_cfob_e1_artifact(
        report=report,
        measurements=measurements,
        exclusions=exclusions,
        mode="synthetic",
        git_sha=current_git_sha(),
        placebo_seed=PLACEBO_SEED,
        notes={"warning": "synthetic smoke cohort — claims nothing"},
    )
    E1_SYNTHETIC_ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2, default=str))
    print(f"synthetic E1 verdict: {artifact['verdict']} (expected underpowered_stop)")
    if artifact["verdict"] != "underpowered_stop":
        raise SystemExit("fail-closed: synthetic E1 smoke must be underpowered_stop")
    return 0


def run_e1(*, synthetic: bool, write_docs_flag: bool) -> int:
    """Stage E1: re-derive the cohort through the D+F0 code path, measure once."""

    if synthetic:
        return _e1_synthetic_run(write_docs_flag=write_docs_flag)

    through = date.today()
    print("E1: parsing tape into qualifying purchases (same path as D+F0)...")
    purchases, counts = load_purchases(through=through)
    if not purchases:
        raise SystemExit("fail-closed: no qualifying purchases parsed")
    print(f"  qualifying purchases: {len(purchases):,}")

    if not SEP_DIR.is_dir():
        raise SystemExit(
            f"fail-closed: SEP panel not found at {SEP_DIR}. "
            "Set CFOB_SEP_DIR to the full-depth SEP year-parquet directory."
        )

    print("E1: CIK-primary mapping...")
    listings, window_source = load_reference_listings()
    mapping = map_purchases_by_cik(purchases, listings)
    if mapping.mapped_count == 0:
        raise SystemExit("fail-closed: zero purchases mapped via CIK reference")
    canonical_purchases = [
        replace(purchase, trading_symbol=canonical_symbol)
        for purchase, canonical_symbol in mapping.canonical
    ]
    del purchases

    print("E1: clusters on canonical symbols...")
    raw = list(build_clusters(canonical_purchases))
    del canonical_purchases
    print(f"  raw clusters: {len(raw):,}")

    print(f"E1: habitat universe filter from SEP ({SEP_DIR})...")
    eligible, sessions, universe_diagnostics = apply_universe_filter(raw)
    if not eligible:
        raise SystemExit("fail-closed: universe filter admitted zero clusters")
    deoverlapped = list(de_overlap(eligible, sessions_by_symbol=sessions))
    print(f"  de-overlapped clusters: {len(deoverlapped):,}")

    published = json.loads(ARTIFACT_PATH.read_text()) if ARTIFACT_PATH.is_file() else None
    if published is None:
        raise SystemExit("fail-closed: no published D+F0 artifact to cross-check the cohort")
    published_count = published["clusters"]["de_overlapped"]
    if len(deoverlapped) != published_count:
        raise SystemExit(
            f"fail-closed: re-derived cohort {len(deoverlapped)} != published D+F0 "
            f"cohort {published_count}; the code path drifted — that is a new trial, "
            "not an E1 run"
        )
    print(f"  cohort cross-check vs published D+F0 artifact: OK ({published_count:,})")

    cluster_symbols = {cluster.trading_symbol for cluster in deoverlapped}
    print("E1: sequential price pass (universe baseline + cluster series)...")
    uni_sum, uni_cnt, day0, sym_data = e1_price_pass(cluster_symbols)

    spy_start = date(FIRST_YEAR, 1, 1)
    spy_end = max(cluster.known_time for cluster in deoverlapped) + timedelta(days=200)
    spy_opens, spy_provenance = load_or_fetch_spy_adjusted_opens(spy_start, min(spy_end, through))

    print("E1: measurement (placebo null, ladder, gates)...")
    measurements, exclusions, report = e1_measure(
        deoverlapped, uni_sum, uni_cnt, day0, sym_data, spy_opens
    )

    artifact = build_cfob_e1_artifact(
        report=report,
        measurements=measurements,
        exclusions=exclusions,
        mode="sec-insider-tape-2006-present",
        git_sha=current_git_sha(),
        placebo_seed=PLACEBO_SEED,
        notes={
            "cohort_cross_check": {
                "published_d_f0_sha": published.get("git_sha"),
                "published_de_overlapped": published_count,
                "re_derived_de_overlapped": len(deoverlapped),
            },
            "reference_source": window_source,
            "spy": spy_provenance,
            "universe_filter_diagnostics": {
                "measured_span": universe_diagnostics.get("measured_span"),
                "secondary_10m_band_clusters": universe_diagnostics.get(
                    "secondary_10m_band_clusters"
                ),
            },
        },
    )
    E1_ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2, default=str))
    if write_docs_flag:
        write_e1_docs(artifact)

    print(f"\nE1 verdict: {artifact['verdict']}")
    for gate in artifact["gates"]:
        print(f"  {'PASS' if gate['passed'] else 'FAIL'} {gate['id']}: {gate['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
