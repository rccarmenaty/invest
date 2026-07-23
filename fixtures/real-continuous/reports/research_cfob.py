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
    PROTOCOL,
    ReferenceListing,
    cik_from_secfilings_url,
    PurchaseCluster,
    QualificationCounts,
    amendment_collision_count,
    build_cfob_artifact,
    build_clusters,
    combine_stage_reports,
    de_overlap,
    evaluate_stage_d,
    evaluate_stage_f0,
    evaluate_universe_membership,
    map_purchases_by_cik,
    qualifying_purchases,
    year_shares,
)
from invest.domain.models import InsiderTransaction

REPO_ROOT = Path(__file__).resolve().parents[3]
TAPE_DIR = REPO_ROOT / "fixtures" / "sec-insider-tape"
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


def _load_sep_year(year: int, symbols: set[str]) -> dict[str, list[tuple[date, float, float, float]]]:
    """Read one SEP year parquet, keeping only symbols with clusters.

    Bars are the canonical ``(date, open_adj, close_adj, volume)`` shape: the
    opening price is carried because the E1/E2 returns gates measure open-to-open
    returns (ADR 0003 §1). ``open_adj`` is a hard requirement — a parquet without
    it fails closed here, it is never synthesized.
    """

    import pyarrow.parquet as pq

    path = SEP_DIR / f"sep_{year}.parquet"
    if not path.is_file():
        if FIRST_YEAR - 1 <= year <= date.today().year:
            raise SystemExit(f"fail-closed: SEP year parquet missing for {year}: {path}")
        return {}
    wanted = ["symbol", "date", "open_adj", "close_adj", "volume"]
    available = set(pq.ParquetFile(path).schema_arrow.names)
    missing = [column for column in wanted if column not in available]
    if missing:
        raise SystemExit(f"fail-closed: SEP {year} missing columns {missing}")
    table = pq.read_table(path, columns=wanted)
    tickers = table.column("symbol").to_pylist()
    dates = table.column("date").to_pylist()
    opens = table.column("open_adj").to_pylist()
    closes = table.column("close_adj").to_pylist()
    volumes = table.column("volume").to_pylist()

    out: dict[str, list[tuple[date, float, float, float]]] = defaultdict(list)
    for ticker, day, open_, close, volume in zip(
        tickers, dates, opens, closes, volumes, strict=False
    ):
        if ticker not in symbols:
            continue
        if open_ is None or close is None or volume is None:
            continue
        day = day.date() if hasattr(day, "date") else day
        out[ticker].append((day, float(open_), float(close), float(volume)))
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
            related = frozenset(part.strip().upper() for part in related_raw.split() if part.strip())
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

    available_years = sorted(
        int(path.stem.split("_")[1]) for path in SEP_DIR.glob("sep_*.parquet")
    )
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
                market_sessions.update(day for day, *_ in bars)
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

    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()
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
        lines.append(
            f"- **{gate['id']}** [{gate['severity']}] **{status}** — {gate['reason']}"
        )
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
    args = parser.parse_args()

    through = date.today()

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


if __name__ == "__main__":
    raise SystemExit(main())
