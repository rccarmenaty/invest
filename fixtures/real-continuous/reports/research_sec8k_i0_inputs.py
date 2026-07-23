#!/usr/bin/env python3
"""Build source-only SEC-8K-2.02 I0 reference inputs.

This script reads only listing reference data, exchange calendars, and the frozen
pre-existing power basis. It does not read prices, reactions, returns, or P&L.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from json import JSONDecodeError
from hashlib import sha256
from pathlib import Path
from typing import Any

import exchange_calendars as xcals  # type: ignore[import-not-found]

from invest.application.sec8k_i0 import digest_i0_json

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SEP_CACHE = (
    REPO_ROOT
    / "fixtures"
    / "real-continuous"
    / "reports"
    / "events22_build_cache"
    / "tickers_sep_v2.json"
)
DEFAULT_BASIS_ARTIFACT = (
    REPO_ROOT / "fixtures" / "real-continuous" / "reports" / "cfob-structure.json"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "fixtures" / "real-continuous" / "reports" / "sec8k-i0"

PRIMARY_COMMON_CATEGORIES = {
    "Domestic Common Stock",
    "Domestic Common Stock Primary Class",
}
US_PRIMARY_EXCHANGES = {
    "AMEX",
    "ARCA",
    "BATS",
    "NASDAQ",
    "NYSE",
    "NYSEARCA",
    "NYSEMKT",
}


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, JSONDecodeError) as error:
        raise ValueError(f"cannot load JSON source {path}") from error


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _matching_cik(
    *,
    symbol: str,
    first_date: str | None,
    last_date: str | None,
    reference_by_symbol: dict[str, list[dict[str, object]]],
) -> tuple[str | None, set[str]]:
    symbol_rows = reference_by_symbol.get(symbol, [])
    candidates = [
        row
        for row in symbol_rows
        if row.get("first") == first_date and row.get("last") == last_date
    ]

    ciks = {str(row["cik"]) for row in candidates if row.get("cik")}
    if len(ciks) > 1:
        raise ValueError(f"ambiguous CIK reference for {symbol}: {sorted(ciks)}")
    related: set[str] = set()
    for row in candidates:
        related_values = row.get("related", [])
        if not isinstance(related_values, list):
            raise ValueError(f"invalid related-symbol reference for {symbol}")
        related.update(str(value).strip().upper() for value in related_values if str(value).strip())
    return (next(iter(ciks)) if ciks else None), related


def _build_listings(
    sep_rows: list[list[object]], reference_rows: list[dict[str, object]]
) -> list[dict[str, object]]:
    reference_by_symbol: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in reference_rows:
        symbol = str(row.get("symbol", "")).strip().upper()
        if symbol:
            reference_by_symbol[symbol].append(row)

    listings: list[dict[str, object]] = []
    for row in sep_rows:
        if len(row) != 9 or row[0] != "SEP":
            raise ValueError("unexpected SHARADAR SEP listing cache row")
        _, _, raw_symbol, raw_related, raw_exchange, raw_category, first, last, delisted = row
        symbol = str(raw_symbol).strip().upper()
        if not symbol:
            raise ValueError("blank listing symbol")
        last_date = str(last) if last and delisted == "Y" else None
        cik, reference_related = _matching_cik(
            symbol=symbol,
            first_date=str(first) if first else None,
            last_date=last_date,
            reference_by_symbol=reference_by_symbol,
        )
        source_related = {
            part.strip().upper() for part in str(raw_related or "").split() if part.strip()
        }
        listings.append(
            {
                "symbol": symbol,
                "cik": cik,
                "related_symbols": sorted((source_related | reference_related) - {symbol}),
                "first_date": str(first) if first else None,
                "last_date": last_date,
                "us_primary_common": (
                    raw_category in PRIMARY_COMMON_CATEGORIES
                    and raw_exchange in US_PRIMARY_EXCHANGES
                ),
            }
        )
    return sorted(
        listings,
        key=lambda row: (
            str(row["symbol"]),
            str(row["first_date"] or ""),
            str(row["last_date"] or ""),
        ),
    )


def _build_sessions() -> list[dict[str, str]]:
    calendar = xcals.get_calendar("XNYS", start="2004-01-01", end="2026-01-09")
    sessions: list[dict[str, str]] = []
    for session in calendar.sessions_in_range("2004-01-02", "2026-01-09"):
        market_open = calendar.session_open(session).isoformat().replace("+00:00", "Z")
        sessions.append({"session_date": session.date().isoformat(), "market_open": market_open})
    return sessions


def _build_power_basis(*, source_sha256: str) -> dict[str, object]:
    payload = {
        "basis_id": "cfob-gate1a-h60-excess-dispersion",
        "created_at": "2026-07-21T00:00:00Z",
        "effective_sigma": 0.38,
        "provenance": (
            "CFOB Gate-1a pre-existing h60 excess-return dispersion; "
            "commit 768328fca242d403ea96c6d7066380c33ee52380; "
            f"source_sha256={source_sha256}"
        ),
    }
    return {"payload": payload, "sha256": digest_i0_json(payload)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-cache", required=True, type=Path)
    parser.add_argument("--sep-cache", type=Path, default=DEFAULT_SEP_CACHE)
    parser.add_argument("--basis-artifact", type=Path, default=DEFAULT_BASIS_ARTIFACT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    sep_rows = _load_json(args.sep_cache)
    reference_rows = _load_json(args.reference_cache)
    if not isinstance(sep_rows, list) or not isinstance(reference_rows, list):
        raise ValueError("listing sources must be arrays")

    basis_source_sha256 = _file_sha256(args.basis_artifact)
    expected_basis_sha256 = "0e1122359139e5eb0628fe5ce339208bcb36c66a56e3f70028a6102733e9fa16"
    if basis_source_sha256 != expected_basis_sha256:
        raise ValueError("frozen CFOB power-basis artifact hash changed")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    listings_path = args.output_dir / "pit-listings.json"
    sessions_path = args.output_dir / "xnys-sessions.json"
    basis_path = args.output_dir / "sec8k-power-basis.json"
    provenance_path = args.output_dir / "input-provenance.json"

    listings = _build_listings(sep_rows, reference_rows)
    sessions = _build_sessions()
    power_basis = _build_power_basis(source_sha256=basis_source_sha256)
    _write_json(listings_path, listings)
    _write_json(sessions_path, sessions)
    _write_json(basis_path, power_basis)
    _write_json(
        provenance_path,
        {
            "basis_artifact": {
                "path": str(args.basis_artifact),
                "sha256": basis_source_sha256,
            },
            "outputs": {
                path.name: _file_sha256(path) for path in (listings_path, sessions_path, basis_path)
            },
            "reference_cache": {
                "path": str(args.reference_cache),
                "sha256": _file_sha256(args.reference_cache),
            },
            "sep_cache": {
                "path": str(args.sep_cache),
                "sha256": _file_sha256(args.sep_cache),
            },
        },
    )

    mapped = sum(row["cik"] is not None for row in listings)
    eligible = sum(bool(row["us_primary_common"]) for row in listings)
    print(f"listings={len(listings)} mapped_cik={mapped} eligible={eligible}")
    print(f"sessions={len(sessions)}")
    print(f"output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
