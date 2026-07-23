#!/usr/bin/env python3
"""Build and audit the sealed SEC-8K-UF universe-first I0 artifact.

This driver reads only the immutable issue #83 SEC manifest/artifact, the PIT
listing artifact, and its source-side exchange facts. It has no price, reaction,
return, candle, P&L, F0, or E1 path.
"""

from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from invest.adapters.sec8k_i0_cli import canonical_json, main


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _require_sha256(path: Path, expected: str) -> None:
    actual = _sha256(path)
    if actual != expected:
        raise ValueError(f"SHA-256 mismatch for {path}: expected={expected} actual={actual}")


def _json(path: Path, expected: type) -> Any:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read canonical JSON from {path}") from error
    if not isinstance(value, expected):
        raise ValueError(f"unexpected JSON root in {path}")
    return value


def _exchange_by_window(
    sep_rows: list[object],
) -> dict[tuple[str, str | None, str | None], str | None]:
    exchanges: dict[tuple[str, str | None, str | None], str | None] = {}
    for index, value in enumerate(sep_rows):
        if not isinstance(value, list) or len(value) != 9 or value[0] != "SEP":
            raise ValueError(f"invalid SEP listing row at index {index}")
        _, _, raw_symbol, _, raw_exchange, _, first, last, delisted = value
        symbol = str(raw_symbol).strip().upper()
        if not symbol:
            raise ValueError(f"blank SEP listing symbol at index {index}")
        first_date = str(first) if first else None
        last_date = str(last) if last and delisted == "Y" else None
        exchange = str(raw_exchange).strip().upper() if raw_exchange else None
        key = (symbol, first_date, last_date)
        previous = exchanges.get(key)
        if key in exchanges and previous != exchange:
            raise ValueError(f"conflicting exchange facts for listing window {key}")
        exchanges[key] = exchange
    return exchanges


def _enrich_listings(
    listing_values: list[object],
    exchange_by_window: dict[tuple[str, str | None, str | None], str | None],
) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    required = {
        "symbol",
        "cik",
        "related_symbols",
        "first_date",
        "last_date",
        "us_primary_common",
    }
    for index, value in enumerate(listing_values):
        if not isinstance(value, dict) or set(value) != required:
            raise ValueError(f"invalid PIT listing row at index {index}")
        symbol = str(value["symbol"]).strip().upper()
        first_date = str(value["first_date"]) if value["first_date"] else None
        last_date = str(value["last_date"]) if value["last_date"] else None
        key = (symbol, first_date, last_date)
        if key not in exchange_by_window:
            raise ValueError(f"PIT listing window lacks an exchange source fact: {key}")
        enriched.append({**value, "exchange": exchange_by_window[key]})
    return enriched


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="research-sec8k-uf-i0")
    parser.add_argument("--sec-manifest", required=True, type=Path)
    parser.add_argument("--sec-manifest-sha256", required=True)
    parser.add_argument("--predecessor-artifact", required=True, type=Path)
    parser.add_argument("--predecessor-artifact-sha256", required=True)
    parser.add_argument("--predecessor-self-hash", required=True)
    parser.add_argument("--pit-listings", required=True, type=Path)
    parser.add_argument("--pit-listings-sha256", required=True)
    parser.add_argument("--sep-cache", required=True, type=Path)
    parser.add_argument("--sep-cache-sha256", required=True)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--universe-output", required=True, type=Path)
    parser.add_argument("--artifact-output", required=True, type=Path)
    return parser


def run(args: argparse.Namespace) -> int:
    _require_sha256(args.sec_manifest, args.sec_manifest_sha256)
    _require_sha256(args.predecessor_artifact, args.predecessor_artifact_sha256)
    _require_sha256(args.pit_listings, args.pit_listings_sha256)
    _require_sha256(args.sep_cache, args.sep_cache_sha256)

    predecessor_artifact = _json(args.predecessor_artifact, dict)
    if predecessor_artifact.get("verdict") != "kill_line":
        raise ValueError("issue #83 predecessor verdict must remain kill_line")
    if predecessor_artifact.get("artifact_sha256") != args.predecessor_self_hash:
        raise ValueError("issue #83 predecessor self-hash changed")
    listing_values = _json(args.pit_listings, list)
    sep_rows = _json(args.sep_cache, list)
    listings = _enrich_listings(listing_values, _exchange_by_window(sep_rows))
    predecessor = {
        "issue": 83,
        "manifest_sha256": args.sec_manifest_sha256,
        "artifact_sha256": args.predecessor_artifact_sha256,
        "artifact_self_hash": args.predecessor_self_hash,
        "verdict": "kill_line",
    }
    universe: dict[str, object] = {
        "schema_version": "sec8k-uf-universe-v1",
        "generated_at": args.generated_at,
        "predecessor": predecessor,
        "provenance": {
            "source": "independent SHARADAR SEP PIT listing windows and exchange facts",
            "snapshot_id": args.snapshot_id,
            "acquired_at": args.generated_at,
        },
        "listings": listings,
    }
    universe["section_hashes"] = {
        section: sha256(canonical_json(universe[section])).hexdigest()
        for section in ("predecessor", "provenance", "listings")
    }
    universe["universe_sha256"] = sha256(canonical_json(universe)).hexdigest()

    if args.universe_output.exists() or args.artifact_output.exists():
        raise ValueError("refusing to replace an existing universe or artifact output")
    if args.universe_output.parent != args.artifact_output.parent:
        raise ValueError("universe and artifact outputs must share one destination directory")
    output_dir = args.universe_output.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".sec8k-uf-", dir=output_dir) as temporary:
        temporary_dir = Path(temporary)
        temporary_universe = temporary_dir / "universe.json"
        temporary_artifact = temporary_dir / "artifact.json"
        temporary_universe.write_bytes(canonical_json(universe))
        status = main(
            [
                "uf-audit",
                "--manifest",
                str(args.sec_manifest),
                "--universe",
                str(temporary_universe),
                "--predecessor-artifact",
                str(args.predecessor_artifact),
                "--output",
                str(temporary_artifact),
            ]
        )
        if status != 0:
            return status
        temporary_universe.replace(args.universe_output)
        temporary_artifact.replace(args.artifact_output)
    return 0


def entrypoint() -> int:
    try:
        return run(_parser().parse_args())
    except (OSError, ValueError) as error:
        print(json.dumps({"error": str(error)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(entrypoint())
