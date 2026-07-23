"""Sealed manifest-to-artifact CLI for SEC 8-K Item 2.02 I0.

Validation and all content hashes complete before the output path is opened.  The
accepted schema has no generic extension objects: unknown keys and outcome-bearing
keys are refused recursively.  F0 and E1 are executable refusal commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from dataclasses import asdict
from datetime import date, datetime
from math import isfinite
from pathlib import Path
from typing import Sequence

from invest.adapters.sec_edgar_8k import (
    SecEdgar8kError,
    SecFairAccessClient,
    build_i0_manifest,
    validate_sec_url,
)
from invest.application.sec8k_i0 import (
    I0_INPUT_SECTION_NAMES,
    PROTOCOL,
    UNIVERSE_FIRST_PROTOCOL,
    FilingRecord,
    ListingRecord,
    PowerBasis,
    ReconciliationRecord,
    SessionRecord,
    I0SealingError,
    canonical_i0_json,
    digest_i0_json,
    evaluate_i0,
    refuse_e1,
    refuse_f0,
    seal_i0_manifest,
)

SCHEMA_VERSION = "sec8k-i0-manifest-v1"
ARTIFACT_VERSION = "sec8k-i0-artifact-v1"
UF_UNIVERSE_VERSION = "sec8k-uf-universe-v1"
UF_ARTIFACT_VERSION = "sec8k-uf-i0-artifact-v1"
SECTION_NAMES = I0_INPUT_SECTION_NAMES
UF_UNIVERSE_SECTIONS = ("predecessor", "provenance", "listings")
_OUTCOME_KEY_FRAGMENTS = (
    "reaction",
    "return",
    "price",
    "candle",
    "profit",
    "pnl",
    "p&l",
    "abnormal",
    "outcome",
)


class ManifestError(ValueError):
    """The sealed input is invalid; no artifact may be written."""


def canonical_json(value: object) -> bytes:
    try:
        return canonical_i0_json(value)
    except I0SealingError as error:
        raise ManifestError("manifest contains non-JSON or non-finite values") from error


def _digest(value: object) -> str:
    try:
        return digest_i0_json(value)
    except I0SealingError as error:
        raise ManifestError("manifest contains non-JSON or non-finite values") from error


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def seal_manifest(manifest: dict[str, object]) -> dict[str, object]:
    """Return a copy with deterministic SHA-256 seals for every input section."""

    try:
        return seal_i0_manifest(manifest)
    except I0SealingError as error:
        raise ManifestError(str(error)) from error


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ManifestError(f"non-finite JSON value: {value}")
            ),
        )
    except ManifestError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ManifestError("manifest is unreadable or malformed JSON") from error
    if not isinstance(value, dict):
        raise ManifestError("manifest root must be an object")
    return value


def _reject_outcome_keys(value: object, *, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = key.lower().replace("-", "_")
            if any(fragment in normalized for fragment in _OUTCOME_KEY_FRAGMENTS):
                raise ManifestError(f"outcome-bearing field refused before output: {path}.{key}")
            _reject_outcome_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_outcome_keys(child, path=f"{path}[{index}]")


def _exact_keys(value: object, allowed: set[str], *, path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ManifestError(f"{path} must be an object")
    unknown = set(value) - allowed
    missing = allowed - set(value)
    if unknown:
        raise ManifestError(f"{path} contains unknown fields: {sorted(unknown)}")
    if missing:
        raise ManifestError(f"{path} is missing fields: {sorted(missing)}")
    return value


def _string(value: object, *, path: str, blank_ok: bool = False) -> str:
    if not isinstance(value, str) or (not blank_ok and not value.strip()):
        raise ManifestError(f"{path} must be a non-blank string")
    return value


def _sha256(value: object, *, path: str) -> str:
    digest = _string(value, path=path)
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ManifestError(f"{path} must be a lowercase SHA-256 digest")
    return digest


def _integer(value: object, *, path: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ManifestError(f"{path} must be an integer >= {minimum}")
    return value


def _number(value: object, *, path: str, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ManifestError(f"{path} must be numeric")
    try:
        converted = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ManifestError(f"{path} must be a finite number") from error
    if not isfinite(converted) or (positive and converted <= 0):
        raise ManifestError(f"{path} must be finite" + (" and positive" if positive else ""))
    return converted


def _date(value: object, *, path: str) -> date:
    try:
        return date.fromisoformat(_string(value, path=path))
    except ValueError as error:
        raise ManifestError(f"{path} must be an ISO date") from error


def _datetime(value: object, *, path: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(_string(value, path=path).replace("Z", "+00:00"))
    except ValueError as error:
        raise ManifestError(f"{path} must be an ISO datetime") from error
    if parsed.tzinfo is None:
        raise ManifestError(f"{path} must include an explicit UTC offset")
    return parsed


def _optional_date(value: object, *, path: str) -> date | None:
    return None if value is None else _date(value, path=path)


def _optional_string(value: object, *, path: str) -> str | None:
    return None if value is None else _string(value, path=path, blank_ok=False)


def _string_list(value: object, *, path: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ManifestError(f"{path} must be an array")
    return tuple(_string(item, path=f"{path}[]") for item in value)


def _parse_manifest(
    manifest: dict[str, object],
) -> tuple[
    tuple[FilingRecord, ...],
    tuple[ListingRecord, ...],
    tuple[SessionRecord, ...],
    tuple[ReconciliationRecord, ...],
    PowerBasis,
]:
    _reject_outcome_keys(manifest)
    top = _exact_keys(
        manifest,
        {
            "schema_version",
            "generated_at",
            "provenance",
            "filings",
            "listings",
            "sessions",
            "reconciliation",
            "power_basis",
            "section_hashes",
        },
        path="$",
    )
    if _string(top["schema_version"], path="$.schema_version") != SCHEMA_VERSION:
        raise ManifestError("unsupported manifest schema_version")
    generated_at = _datetime(top["generated_at"], path="$.generated_at")

    hashes = _exact_keys(top["section_hashes"], set(SECTION_NAMES), path="$.section_hashes")
    for section in SECTION_NAMES:
        expected = _string(hashes[section], path=f"$.section_hashes.{section}")
        if len(expected) != 64 or expected != _digest(top[section]):
            raise ManifestError(f"stale or invalid section hash: {section}")

    provenance = _exact_keys(
        top["provenance"],
        {"source", "snapshot_id", "acquired_at", "sec_user_agent"},
        path="$.provenance",
    )
    _string(provenance["source"], path="$.provenance.source")
    _string(provenance["snapshot_id"], path="$.provenance.snapshot_id")
    _datetime(provenance["acquired_at"], path="$.provenance.acquired_at")
    user_agent = _string(provenance["sec_user_agent"], path="$.provenance.sec_user_agent")
    if "@" not in user_agent:
        raise ManifestError("SEC User-Agent must contain a contact email")

    filing_values = top["filings"]
    if not isinstance(filing_values, list) or not filing_values:
        raise ManifestError("$.filings must be a non-empty array")
    filings: list[FilingRecord] = []
    filing_keys = {
        "accession_number",
        "cik",
        "form",
        "filing_date",
        "acceptance_raw",
        "acceptance_at",
        "source_url",
        "content_sha256",
        "item_codes",
        "item_202_evidence",
        "source_occurrences",
        "as_filed_ticker",
        "item_202_conflicts",
        "amendment_of",
        "parse_error",
    }
    for index, raw in enumerate(filing_values):
        path = f"$.filings[{index}]"
        item = _exact_keys(raw, filing_keys, path=path)
        source_url = _string(item["source_url"], path=f"{path}.source_url")
        try:
            validate_sec_url(source_url)
        except ValueError as error:
            raise ManifestError(str(error)) from error
        acceptance_at = (
            None
            if item["acceptance_at"] is None
            else _datetime(item["acceptance_at"], path=f"{path}.acceptance_at")
        )
        filings.append(
            FilingRecord(
                accession_number=_string(item["accession_number"], path=f"{path}.accession_number"),
                cik=_string(item["cik"], path=f"{path}.cik"),
                form=_string(item["form"], path=f"{path}.form"),
                filing_date=_date(item["filing_date"], path=f"{path}.filing_date"),
                acceptance_raw=_optional_string(
                    item["acceptance_raw"], path=f"{path}.acceptance_raw"
                ),
                acceptance_at=acceptance_at,
                source_url=source_url,
                content_sha256=_string(item["content_sha256"], path=f"{path}.content_sha256"),
                item_codes=_string_list(item["item_codes"], path=f"{path}.item_codes"),
                item_202_evidence=_string_list(
                    item["item_202_evidence"], path=f"{path}.item_202_evidence"
                ),
                source_occurrences=_string_list(
                    item["source_occurrences"], path=f"{path}.source_occurrences"
                ),
                as_filed_ticker=_optional_string(
                    item["as_filed_ticker"], path=f"{path}.as_filed_ticker"
                ),
                item_202_conflicts=_string_list(
                    item["item_202_conflicts"], path=f"{path}.item_202_conflicts"
                ),
                amendment_of=_optional_string(item["amendment_of"], path=f"{path}.amendment_of"),
                parse_error=_optional_string(item["parse_error"], path=f"{path}.parse_error"),
            )
        )

    listing_values = top["listings"]
    if not isinstance(listing_values, list) or not listing_values:
        raise ManifestError("$.listings must be a non-empty array")
    listings: list[ListingRecord] = []
    listing_keys = {
        "symbol",
        "cik",
        "related_symbols",
        "first_date",
        "last_date",
        "us_primary_common",
    }
    for index, raw in enumerate(listing_values):
        path = f"$.listings[{index}]"
        item = _exact_keys(raw, listing_keys, path=path)
        eligible = item["us_primary_common"]
        if not isinstance(eligible, bool):
            raise ManifestError(f"{path}.us_primary_common must be boolean")
        listings.append(
            ListingRecord(
                symbol=_string(item["symbol"], path=f"{path}.symbol"),
                cik=_optional_string(item["cik"], path=f"{path}.cik"),
                related_symbols=_string_list(
                    item["related_symbols"], path=f"{path}.related_symbols"
                ),
                first_date=_optional_date(item["first_date"], path=f"{path}.first_date"),
                last_date=_optional_date(item["last_date"], path=f"{path}.last_date"),
                us_primary_common=eligible,
            )
        )

    session_values = top["sessions"]
    if not isinstance(session_values, list) or not session_values:
        raise ManifestError("$.sessions must be a non-empty array")
    sessions: list[SessionRecord] = []
    for index, raw in enumerate(session_values):
        path = f"$.sessions[{index}]"
        item = _exact_keys(raw, {"session_date", "market_open"}, path=path)
        sessions.append(
            SessionRecord(
                session_date=_date(item["session_date"], path=f"{path}.session_date"),
                market_open=_datetime(item["market_open"], path=f"{path}.market_open"),
            )
        )

    reconciliation_values = top["reconciliation"]
    if not isinstance(reconciliation_values, list) or not reconciliation_values:
        raise ManifestError("$.reconciliation must be a non-empty array")
    reconciliation: list[ReconciliationRecord] = []
    reconciliation_keys = {
        "year",
        "quarter",
        "form",
        "expected",
        "fetched",
        "parsed",
        "item_202",
        "failed",
        "excluded",
    }
    for index, raw in enumerate(reconciliation_values):
        path = f"$.reconciliation[{index}]"
        item = _exact_keys(raw, reconciliation_keys, path=path)
        reconciliation.append(
            ReconciliationRecord(
                year=_integer(item["year"], path=f"{path}.year", minimum=2004),
                quarter=_integer(item["quarter"], path=f"{path}.quarter", minimum=1),
                form=_string(item["form"], path=f"{path}.form"),
                expected=_integer(item["expected"], path=f"{path}.expected"),
                fetched=_integer(item["fetched"], path=f"{path}.fetched"),
                parsed=_integer(item["parsed"], path=f"{path}.parsed"),
                item_202=_integer(item["item_202"], path=f"{path}.item_202"),
                failed=_integer(item["failed"], path=f"{path}.failed"),
                excluded=_integer(item["excluded"], path=f"{path}.excluded"),
            )
        )

    power_section = _exact_keys(top["power_basis"], {"payload", "sha256"}, path="$.power_basis")
    power_payload = _exact_keys(
        power_section["payload"],
        {"basis_id", "created_at", "effective_sigma", "provenance"},
        path="$.power_basis.payload",
    )
    power_hash = _string(power_section["sha256"], path="$.power_basis.sha256")
    if power_hash != _digest(power_payload):
        raise ManifestError("stale or invalid pre-existing power-basis hash")
    basis_created = _datetime(power_payload["created_at"], path="$.power_basis.payload.created_at")
    if basis_created >= generated_at:
        raise ManifestError("power basis must predate the I0 manifest")
    power_basis = PowerBasis(
        basis_id=_string(power_payload["basis_id"], path="$.power_basis.payload.basis_id"),
        created_at=basis_created,
        effective_sigma=_number(
            power_payload["effective_sigma"],
            path="$.power_basis.payload.effective_sigma",
            positive=True,
        ),
        provenance=_string(power_payload["provenance"], path="$.power_basis.payload.provenance"),
    )
    return (
        tuple(filings),
        tuple(listings),
        tuple(sessions),
        tuple(reconciliation),
        power_basis,
    )


def _parse_universe(
    universe: dict[str, object],
    *,
    sec_manifest_sha256: str,
    predecessor_artifact: dict[str, object],
    predecessor_artifact_sha256: str,
) -> tuple[tuple[ListingRecord, ...], dict[str, object], str, dict[str, object]]:
    _reject_outcome_keys(universe)
    top = _exact_keys(
        universe,
        {
            "schema_version",
            "generated_at",
            "predecessor",
            "provenance",
            "listings",
            "section_hashes",
            "universe_sha256",
        },
        path="$",
    )
    if _string(top["schema_version"], path="$.schema_version") != UF_UNIVERSE_VERSION:
        raise ManifestError("unsupported universe schema_version")
    _datetime(top["generated_at"], path="$.generated_at")

    supplied_self_hash = _sha256(top["universe_sha256"], path="$.universe_sha256")
    unsealed = {key: value for key, value in top.items() if key != "universe_sha256"}
    if supplied_self_hash != _digest(unsealed):
        raise ManifestError("stale or invalid universe self-hash")

    hashes = _exact_keys(top["section_hashes"], set(UF_UNIVERSE_SECTIONS), path="$.section_hashes")
    for section in UF_UNIVERSE_SECTIONS:
        expected = _string(hashes[section], path=f"$.section_hashes.{section}")
        if len(expected) != 64 or expected != _digest(top[section]):
            raise ManifestError(f"stale or invalid universe section hash: {section}")

    predecessor = _exact_keys(
        top["predecessor"],
        {
            "issue",
            "manifest_sha256",
            "artifact_sha256",
            "artifact_self_hash",
            "verdict",
        },
        path="$.predecessor",
    )
    if _integer(predecessor["issue"], path="$.predecessor.issue") != 83:
        raise ManifestError("universe must preserve issue #83 as predecessor")
    if _string(predecessor["verdict"], path="$.predecessor.verdict") != "kill_line":
        raise ManifestError("predecessor verdict must remain kill_line")
    for name in ("manifest_sha256", "artifact_sha256", "artifact_self_hash"):
        _sha256(predecessor[name], path=f"$.predecessor.{name}")
    if predecessor["manifest_sha256"] != sec_manifest_sha256:
        raise ManifestError("universe is not bound to the supplied SEC manifest")
    if predecessor["artifact_sha256"] != predecessor_artifact_sha256:
        raise ManifestError("universe is not bound to the supplied predecessor artifact")
    if predecessor_artifact.get("schema_version") != ARTIFACT_VERSION:
        raise ManifestError("unsupported predecessor artifact schema_version")
    artifact_self_hash = _sha256(
        predecessor_artifact.get("artifact_sha256"), path="$.predecessor_artifact.artifact_sha256"
    )
    artifact_unsealed = {
        key: value for key, value in predecessor_artifact.items() if key != "artifact_sha256"
    }
    if artifact_self_hash != _digest(artifact_unsealed):
        raise ManifestError("stale or invalid predecessor artifact self-hash")
    if predecessor["artifact_self_hash"] != artifact_self_hash:
        raise ManifestError("universe predecessor self-hash is detached from its artifact")
    if predecessor_artifact.get("source_manifest_sha256") != sec_manifest_sha256:
        raise ManifestError("predecessor artifact is not bound to the supplied SEC manifest")
    if predecessor_artifact.get("verdict") != "kill_line":
        raise ManifestError("predecessor artifact verdict must remain kill_line")

    provenance = _exact_keys(
        top["provenance"],
        {"source", "snapshot_id", "acquired_at"},
        path="$.provenance",
    )
    _string(provenance["source"], path="$.provenance.source")
    _string(provenance["snapshot_id"], path="$.provenance.snapshot_id")
    _datetime(provenance["acquired_at"], path="$.provenance.acquired_at")

    listing_values = top["listings"]
    if not isinstance(listing_values, list) or not listing_values:
        raise ManifestError("$.listings must be a non-empty array")
    listings: list[ListingRecord] = []
    seen_windows: set[tuple[object, ...]] = set()
    listing_keys = {
        "symbol",
        "cik",
        "related_symbols",
        "first_date",
        "last_date",
        "us_primary_common",
        "exchange",
    }
    for index, raw in enumerate(listing_values):
        path = f"$.listings[{index}]"
        if isinstance(raw, dict) and "exchange" not in raw:
            raw = {**raw, "exchange": None}
        item = _exact_keys(raw, listing_keys, path=path)
        eligible = item["us_primary_common"]
        if not isinstance(eligible, bool):
            raise ManifestError(f"{path}.us_primary_common must be boolean")
        listing = ListingRecord(
            symbol=_string(item["symbol"], path=f"{path}.symbol"),
            cik=_optional_string(item["cik"], path=f"{path}.cik"),
            related_symbols=_string_list(item["related_symbols"], path=f"{path}.related_symbols"),
            first_date=_optional_date(item["first_date"], path=f"{path}.first_date"),
            last_date=_optional_date(item["last_date"], path=f"{path}.last_date"),
            us_primary_common=eligible,
            exchange=_optional_string(item["exchange"], path=f"{path}.exchange"),
        )
        identity = (
            listing.symbol,
            listing.cik,
            listing.related_symbols,
            listing.first_date,
            listing.last_date,
            listing.us_primary_common,
            listing.exchange,
        )
        if identity in seen_windows:
            raise ManifestError(f"duplicate universe listing window: {listing.symbol}")
        seen_windows.add(identity)
        listings.append(listing)
    return tuple(listings), predecessor, supplied_self_hash, hashes


def build_universe_first_artifact(
    manifest: dict[str, object],
    universe: dict[str, object],
    predecessor_artifact: dict[str, object],
    *,
    source_manifest_sha256: str | None = None,
    predecessor_artifact_sha256: str,
) -> dict[str, object]:
    filings, _, sessions, reconciliation, power_basis = _parse_manifest(manifest)
    source_manifest_sha256 = source_manifest_sha256 or _digest(manifest)
    listings, predecessor, universe_sha256, universe_hashes = _parse_universe(
        universe,
        sec_manifest_sha256=source_manifest_sha256,
        predecessor_artifact=predecessor_artifact,
        predecessor_artifact_sha256=predecessor_artifact_sha256,
    )
    result = evaluate_i0(
        filings=filings,
        listings=listings,
        sessions=sessions,
        reconciliation=reconciliation,
        power_basis=power_basis,
        protocol=UNIVERSE_FIRST_PROTOCOL,
        universe_first=True,
    )
    artifact: dict[str, object] = {
        "schema_version": UF_ARTIFACT_VERSION,
        "line": UNIVERSE_FIRST_PROTOCOL.line,
        "stage": "i0",
        "verdict": result.verdict,
        "status": result.status,
        "capital_go": False,
        "returns_measured": False,
        "f0_authorized": False,
        "e1_authorized": False,
        "predecessor": predecessor,
        "source_manifest_sha256": source_manifest_sha256,
        "universe_artifact_sha256": universe_sha256,
        "input_section_hashes": {
            "sec_manifest": manifest["section_hashes"],
            "universe": universe_hashes,
        },
        "protocol": asdict(UNIVERSE_FIRST_PROTOCOL),
        "result": result.to_dict(),
    }
    artifact["artifact_sha256"] = _digest(artifact)
    return artifact


def build_artifact(manifest: dict[str, object]) -> dict[str, object]:
    filings, listings, sessions, reconciliation, power_basis = _parse_manifest(manifest)
    result = evaluate_i0(
        filings=filings,
        listings=listings,
        sessions=sessions,
        reconciliation=reconciliation,
        power_basis=power_basis,
    )
    result_payload = result.to_dict()
    artifact: dict[str, object] = {
        "schema_version": ARTIFACT_VERSION,
        "line": PROTOCOL.line,
        "stage": "i0",
        "verdict": result.verdict,
        "status": result.status,
        "capital_go": False,
        "returns_measured": False,
        "f0_authorized": False,
        "e1_authorized": False,
        "source_manifest_sha256": _digest(manifest),
        "input_section_hashes": manifest["section_hashes"],
        "protocol": asdict(PROTOCOL),
        "result": result_payload,
    }
    artifact["artifact_sha256"] = _digest(artifact)
    return artifact


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="invest-sec8k-i0")
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="evaluate one sealed I0 manifest")
    audit.add_argument("--manifest", required=True, type=Path)
    audit.add_argument("--output", required=True, type=Path)
    uf_audit = commands.add_parser("uf-audit", help="evaluate one sealed universe-first I0 join")
    uf_audit.add_argument("--manifest", required=True, type=Path)
    uf_audit.add_argument("--universe", required=True, type=Path)
    uf_audit.add_argument("--predecessor-artifact", required=True, type=Path)
    uf_audit.add_argument("--output", required=True, type=Path)
    acquire = commands.add_parser("acquire", help="build a resumable sealed SEC I0 manifest")
    acquire.add_argument("--start-year", required=True, type=int)
    acquire.add_argument("--end-year", required=True, type=int)
    acquire.add_argument("--listings", required=True, type=Path)
    acquire.add_argument("--sessions", required=True, type=Path)
    acquire.add_argument("--power-basis", required=True, type=Path)
    acquire.add_argument("--cache-dir", required=True, type=Path)
    acquire.add_argument("--submissions-zip", required=True, type=Path)
    acquire.add_argument("--submissions-sha256", required=True)
    acquire.add_argument("--manifest-output", required=True, type=Path)
    acquire.add_argument("--user-agent", required=True)
    acquire.add_argument("--snapshot-id", required=True)
    acquire.add_argument("--generated-at", required=True)
    commands.add_parser("f0", help="refuse unauthorized F0 execution")
    commands.add_parser("e1", help="refuse unauthorized E1 execution")
    return parser


def _load_acquisition_input(path: Path, *, expected: type) -> object:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=lambda raw: (_ for _ in ()).throw(
                ManifestError(f"non-finite JSON value: {raw}")
            ),
        )
    except ManifestError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ManifestError(f"acquisition input is unreadable: {path}") from error
    if not isinstance(value, expected):
        raise ManifestError(f"acquisition input has wrong root type: {path}")
    return value


def _acquire(args: argparse.Namespace) -> int:
    if (
        args.start_year != PROTOCOL.regime_start_year
        or args.end_year != PROTOCOL.last_complete_year
    ):
        raise ManifestError("acquisition must cover exactly 2004 through 2025")
    listings_value = _load_acquisition_input(args.listings, expected=list)
    sessions_value = _load_acquisition_input(args.sessions, expected=list)
    power_value = _load_acquisition_input(args.power_basis, expected=dict)
    if not isinstance(listings_value, list):
        raise ManifestError("listing input must be an array")
    if not isinstance(sessions_value, list):
        raise ManifestError("session input must be an array")
    if not isinstance(power_value, dict):
        raise ManifestError("power-basis input must be an object")
    if not all(isinstance(row, dict) for row in listings_value + sessions_value):
        raise ManifestError("listing and session inputs must contain only objects")
    quarters = tuple(
        (year, quarter)
        for year in range(args.start_year, args.end_year + 1)
        for quarter in (1, 2, 3, 4)
    )
    with SecFairAccessClient(
        cache_dir=args.cache_dir,
        user_agent=args.user_agent,
    ) as client:
        manifest = build_i0_manifest(
            client=client,
            quarters=quarters,
            submissions_zip=args.submissions_zip,
            submissions_sha256=args.submissions_sha256,
            listings=tuple(dict(row) for row in listings_value),
            sessions=tuple(dict(row) for row in sessions_value),
            power_basis=power_value,
            generated_at=args.generated_at,
            snapshot_id=args.snapshot_id,
            sec_user_agent=args.user_agent,
        )
    # Run the exact sealed validator before publishing the manifest.
    _parse_manifest(manifest)
    payload = canonical_json(manifest) + b"\n"
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest_output.open("xb") as handle:
        handle.write(payload)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command == "f0":
            refuse_f0()
        if args.command == "e1":
            refuse_e1()
        if args.command == "acquire":
            return _acquire(args)
        manifest = _load_json(args.manifest)
        artifact = (
            build_universe_first_artifact(
                manifest,
                _load_json(args.universe),
                _load_json(args.predecessor_artifact),
                source_manifest_sha256=_file_sha256(args.manifest),
                predecessor_artifact_sha256=_file_sha256(args.predecessor_artifact),
            )
            if args.command == "uf-audit"
            else build_artifact(manifest)
        )
        payload = canonical_json(artifact) + b"\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as handle:
            handle.write(payload)
        return 0
    except (ManifestError, PermissionError, SecEdgar8kError, OSError) as error:
        print(json.dumps({"error": str(error)}, sort_keys=True), file=sys.stderr)
        return 2
    except SystemExit as error:
        return int(error.code) if isinstance(error.code, int) else 2


if __name__ == "__main__":
    sys.exit(main())
