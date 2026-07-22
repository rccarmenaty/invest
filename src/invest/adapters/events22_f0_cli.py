"""Sealed manifest driver for the EVENTS-22 F0 feasibility audit."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from datetime import date
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from invest.application.events22_f0 import (
    PROTOCOL,
    EligibilityFact,
    EventRow,
    F0Evidence,
    F0Provenance,
    ListingRecord,
    PowerBasis,
    build_events22_f0_artifact,
    compute_events22_input_hashes,
    refuse_events22_e1,
    run_events22_f0,
)


class _SealedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _EventInput(_SealedModel):
    source_row_id: str
    ticker: str
    event_date: date
    event_code: int


class _ListingInput(_SealedModel):
    issuer_id: str
    ticker: str
    related_tickers: tuple[str, ...]
    listed_date: date
    delisted_date: date | None
    is_primary_common_stock: bool
    is_us_primary_listing: bool


class _EligibilityInput(_SealedModel):
    ticker: str
    known_date: date
    price: float = Field(gt=0, allow_inf_nan=False)
    median_dollar_volume_20_session: float = Field(ge=0, allow_inf_nan=False)
    prior_valid_sessions: int = Field(ge=0)
    actions_and_delistings_complete: bool


class _EvidenceInput(_SealedModel):
    semantics_verified: bool
    known_time_verified: bool
    pit_mapping_verified: bool
    duplicate_policy_verified: bool
    actions_and_delistings_verified: bool
    reproducibility_verified: bool
    return_fields_absent: bool
    semantics_source: str


class _PowerBasisInput(_SealedModel):
    source_name: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    source_sha256: str
    outcome_inspection_not_before: date


class _PowerBasisArtifact(_SealedModel):
    schema_version: Literal["events22-power-basis-v1"]
    cluster_adjusted_dispersion: float = Field(gt=0, allow_inf_nan=False)
    source_frozen_date: date


class _F0Manifest(_SealedModel):
    schema_version: Literal["events22-f0-input-v1"]
    snapshot_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9._:/-]+$")
    code_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9._:/-]+$")
    events: tuple[_EventInput, ...]
    listings: tuple[_ListingInput, ...]
    sessions: tuple[date, ...]
    eligibility: tuple[_EligibilityInput, ...]
    evidence: _EvidenceInput
    power_basis: _PowerBasisInput | None
    input_hashes: dict[str, str]


def run_manifest(source: Path, output: Path) -> dict[str, Any]:
    """Validate a sealed input manifest, execute F0, and atomically write its artifact."""

    try:
        manifest = _F0Manifest.model_validate_json(source.read_text())
    except (OSError, ValidationError, ValueError) as error:
        raise ValueError(f"sealed F0 manifest rejected: {error}") from None

    evidence = F0Evidence(**manifest.evidence.model_dump())
    power_basis = None
    if manifest.power_basis:
        basis_values = manifest.power_basis.model_dump()
        basis_path = source.parent / basis_values.pop("source_path")
        try:
            basis_bytes = basis_path.read_bytes()
            observed_basis_hash = sha256(basis_bytes).hexdigest()
            basis_artifact = _PowerBasisArtifact.model_validate_json(basis_bytes)
        except (OSError, ValidationError, ValueError) as error:
            raise ValueError(f"sealed F0 power source rejected: {error}") from None
        if observed_basis_hash != basis_values["source_sha256"]:
            raise ValueError("sealed F0 power source hash mismatch")
        power_basis = PowerBasis(
            source_name=basis_values["source_name"],
            source_sha256=basis_values["source_sha256"],
            cluster_adjusted_dispersion=basis_artifact.cluster_adjusted_dispersion,
            source_frozen_date=basis_artifact.source_frozen_date,
            outcome_inspection_not_before=basis_values["outcome_inspection_not_before"],
        )
    events = tuple(EventRow(**item.model_dump()) for item in manifest.events)
    listings = tuple(ListingRecord(**item.model_dump()) for item in manifest.listings)
    eligibility = tuple(EligibilityFact(**item.model_dump()) for item in manifest.eligibility)
    expected_hashes = compute_events22_input_hashes(
        events=events,
        listings=listings,
        sessions=manifest.sessions,
        eligibility=eligibility,
        evidence=evidence,
        power_basis=power_basis,
    )
    if manifest.input_hashes != expected_hashes:
        raise ValueError("sealed F0 manifest input hash mismatch")
    result = run_events22_f0(
        events=events,
        listings=listings,
        sessions=manifest.sessions,
        eligibility=eligibility,
        evidence=evidence,
        power_basis=power_basis,
        input_hashes=manifest.input_hashes,
        config=PROTOCOL,
    )
    artifact = build_events22_f0_artifact(
        result=result,
        evidence=evidence,
        input_hashes=manifest.input_hashes,
        power_basis=power_basis,
        provenance=F0Provenance(manifest.snapshot_id, manifest.code_id),
        config=PROTOCOL,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    temporary.replace(output)
    return artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--e1",
        action="store_true",
        help="refuse explicitly: E1 is outside this F0-only implementation",
    )
    args = parser.parse_args(argv)
    if args.e1:
        refuse_events22_e1()
    run_manifest(args.input, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
