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
import time
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import median

from invest.adapters.sec_insider_tape import InsiderTapeError, SecInsiderTapeReader
from invest.application.cfob import (
    PROTOCOL,
    ListingWindow,
    PurchaseCluster,
    QualificationCounts,
    build_cfob_artifact,
    build_clusters,
    combine_stage_reports,
    de_overlap,
    dedupe_amendments,
    evaluate_stage_d,
    evaluate_stage_f0,
    map_purchases,
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
TICKERS_CACHE = TAPE_DIR / "tickers_listing_windows.json"

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
    """Parse every cached quarter into qualifying purchases.

    Quarters are qualified as they are read so only the surviving purchases
    stay resident — the raw tape is an order of magnitude larger.
    """

    reader = SecInsiderTapeReader(cache_dir=TAPE_DIR)
    kept: list[InsiderTransaction] = []
    totals: dict[str, int] = defaultdict(int)
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
    totals["archives_expected"] = archives_expected
    totals["archives_parsed"] = archives_parsed
    totals["cross_quarter_superseded"] = cross_quarter_superseded
    totals["qualified"] = len(kept_tuple)
    totals["dropped_by_global_dedupe"] = before - len(kept_tuple)
    return list(kept_tuple), dict(totals)


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


def build_listing_windows_from_sep(*, verbose: bool = True) -> list[ListingWindow]:
    """Offline listing windows: first/last observed SEP session per symbol.

    Preferred source is Sharadar TICKERS first/lastpricedate (see
    ``load_listing_windows``). SEP-derived windows are the fail-closed offline
    substitute when no TICKERS cache/API is available: they include delisted
    names and cannot invent a listing that never trades on the panel.
    """

    import pyarrow.parquet as pq

    available_years = sorted(
        int(path.stem.split("_")[1]) for path in SEP_DIR.glob("sep_*.parquet")
    )
    if not available_years:
        raise SystemExit(f"fail-closed: no SEP year parquet found in {SEP_DIR}")

    first_last: dict[str, list[date | None]] = {}
    for year in available_years:
        path = SEP_DIR / f"sep_{year}.parquet"
        table = pq.read_table(path, columns=["symbol", "date"])
        symbols = table.column("symbol").to_pylist()
        days = table.column("date").to_pylist()
        for symbol, day in zip(symbols, days, strict=False):
            if symbol is None or day is None:
                continue
            day = day.date() if hasattr(day, "date") else day
            entry = first_last.get(symbol)
            if entry is None:
                first_last[symbol] = [day, day]
            else:
                if day < entry[0]:
                    entry[0] = day
                if day > entry[1]:
                    entry[1] = day
        if verbose and year % 5 == 0:
            print(f"  listing windows through {year}: {len(first_last):,} symbols")

    windows = [
        ListingWindow(symbol=symbol, first_price_date=bounds[0], last_price_date=bounds[1])
        for symbol, bounds in first_last.items()
    ]
    if verbose:
        print(f"  listing windows total: {len(windows):,}")
    return windows


def load_listing_windows(*, verbose: bool = True) -> tuple[list[ListingWindow], str]:
    """Load listing windows: TICKERS cache → live TICKERS → SEP fallback."""

    if TICKERS_CACHE.is_file():
        payload = json.loads(TICKERS_CACHE.read_text())
        windows = [
            ListingWindow(
                symbol=row["symbol"],
                first_price_date=date.fromisoformat(row["first"]) if row.get("first") else None,
                last_price_date=date.fromisoformat(row["last"]) if row.get("last") else None,
            )
            for row in payload
        ]
        if verbose:
            print(f"  listing windows from cache {TICKERS_CACHE.name}: {len(windows):,}")
        return windows, "tickers-cache"

    api_key = os.environ.get("NASDAQ_DATA_LINK_API_KEY")
    if api_key:
        import httpx

        from invest.adapters.sharadar_tickers import SharadarTickersReader

        if verbose:
            print("  fetching Sharadar TICKERS for listing windows...")
        with httpx.Client(timeout=180.0) as client:
            # Reader already filters columns; keep primary+delisted equities.
            os.environ.setdefault("NASDAQ_DATA_LINK_API_KEY", api_key)
            reader = SharadarTickersReader(client=client)
            # _request_params uses env key via nasdaq helpers — check reader
            tickers = reader.fetch()
        windows = [
            ListingWindow(
                symbol=row.ticker,
                first_price_date=row.listed_date,
                last_price_date=row.delisted_date if not row.is_listed else None,
            )
            for row in tickers
            if row.is_primary_common_stock or row.delisted_date is not None or row.is_listed
        ]
        TAPE_DIR.mkdir(parents=True, exist_ok=True)
        TICKERS_CACHE.write_text(
            json.dumps(
                [
                    {
                        "symbol": window.symbol,
                        "first": window.first_price_date.isoformat()
                        if window.first_price_date
                        else None,
                        "last": window.last_price_date.isoformat()
                        if window.last_price_date
                        else None,
                    }
                    for window in windows
                ]
            )
        )
        if verbose:
            print(f"  listing windows from TICKERS API: {len(windows):,}")
        return windows, "tickers-api"

    if verbose:
        print("  no TICKERS cache/API key; building listing windows from SEP...")
    return build_listing_windows_from_sep(verbose=verbose), "sep-first-last"


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
            bars = history.get(cluster.trading_symbol, [])
            if not bars:
                no_price_history_by_year[year] += 1
                continue
            prior = [bar for bar in bars if bar[0] <= cluster.known_time]
            if len(prior) < PROTOCOL.min_history_bars:
                insufficient_history_by_year[year] += 1
                continue
            window = prior[-PROTOCOL.dollar_volume_window :]
            price = prior[-1][1]
            dollar_volume = median(close * volume for _, close, volume in window)
            if dollar_volume < float(PROTOCOL.min_dollar_volume):
                continue
            if price < float(PROTOCOL.min_price):
                price_floor_excluded += 1
                if PROTOCOL.gate_on_min_price:
                    continue
            kept.append(cluster)
            if dollar_volume >= float(PROTOCOL.secondary_min_dollar_volume):
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
        accessions: set[str] = set()
        form4_lines = 0
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                started = False
                for raw in response:
                    line = raw.decode("utf-8", "replace").rstrip("\n")
                    if not started:
                        if line.startswith("---"):
                            started = True
                        continue
                    form = line[:12].strip()
                    if form not in {"4", "4/A"}:
                        continue
                    form4_lines += 1
                    parts = line.split()
                    if not parts:
                        continue
                    filename = parts[-1]
                    if filename.endswith(".txt"):
                        accessions.add(filename.rsplit("/", 1)[-1][:-4])
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
            f"- listing window source: `{f0.get('listing_window_source')}`",
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
        "- Purchase-level mapping uses listing windows (TICKERS first/lastpricedate when "
        "available; otherwise SEP first/last session) on filing-date.",
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

    print("Loading listing windows for purchase-level mapping...")
    windows, window_source = load_listing_windows()
    mapping = map_purchases(purchases, windows)
    print(
        f"  mapped purchases: {mapping.mapped_count:,} / {mapping.total_count:,} "
        f"(ambiguous {len(mapping.ambiguous):,}; source={window_source})"
    )
    if mapping.mapped_count == 0:
        raise SystemExit("fail-closed: zero purchases mapped to listing windows")

    print("Building clusters from mapped purchases only...")
    raw = list(build_clusters(mapping.mapped))
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

    print("\nRunning Stage F0 integrity gates...")
    if args.skip_reconcile:
        reconciled, reconcile_rows = None, []
        print("  reconcile skipped (--skip-reconcile) → fail closed")
    else:
        reconciled, reconcile_rows = reconcile_against_edgar_index()

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
        derivative_rows_in_qualified=0,  # reader only emits NONDERIV_TRANS
        amendment_dedupe_measured=True,
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
        notes={
            "quarters_read": counts.get("quarters_read", 0),
            "cross_quarter_superseded": counts.get("cross_quarter_superseded", 0),
            "dropped_by_global_dedupe": counts.get("dropped_by_global_dedupe", 0),
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
                "listing_window_source": window_source,
                "mapped_purchases": mapping.mapped_count,
                "total_purchases": mapping.total_count,
                "ambiguous_purchases": len(mapping.ambiguous),
                "unmapped_by_year": mapping.unmapped_by_year,
                "total_by_year": mapping.total_by_year,
                "reconcile_sample": reconcile_rows,
                "reconcile_tolerance": RECONCILE_TOLERANCE,
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
