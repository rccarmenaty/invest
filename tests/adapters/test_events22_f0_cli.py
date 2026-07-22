"""Public manifest-to-artifact seam for the EVENTS-22 F0 driver."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest

from invest.adapters.events22_f0_cli import run_manifest
from invest.application.events22_f0 import (
    EligibilityFact,
    EventRow,
    F0Evidence,
    ListingRecord,
    PowerBasis,
    compute_events22_input_hashes,
)


def _evidence() -> F0Evidence:
    return F0Evidence(
        semantics_verified=True,
        known_time_verified=True,
        pit_mapping_verified=True,
        duplicate_policy_verified=True,
        actions_and_delistings_verified=True,
        reproducibility_verified=True,
        return_fields_absent=True,
        semantics_source="provider-data-dictionary",
    )


def _manifest() -> dict[str, object]:
    manifest: dict[str, object] = {
        "schema_version": "events22-f0-input-v1",
        "snapshot_id": "snapshot-test",
        "code_id": "056f584-test",
        "events": [
            {
                "source_row_id": "row-1",
                "ticker": "ACME",
                "event_date": "2020-01-03",
                "event_code": 22,
            }
        ],
        "listings": [
            {
                "issuer_id": "issuer-1",
                "ticker": "ACME",
                "related_tickers": [],
                "listed_date": "2010-01-01",
                "delisted_date": None,
                "is_primary_common_stock": True,
                "is_us_primary_listing": True,
            }
        ],
        "sessions": [f"2020-01-{day:02d}" for day in range(1, 32)]
        + [f"2020-02-{day:02d}" for day in range(1, 30)]
        + [f"2020-03-{day:02d}" for day in range(1, 32)]
        + [f"2020-04-{day:02d}" for day in range(1, 11)],
        "eligibility": [
            {
                "ticker": "ACME",
                "known_date": "2020-01-03",
                "price": 20.0,
                "median_dollar_volume_20_session": 20_000_000.0,
                "prior_valid_sessions": 300,
                "actions_and_delistings_complete": True,
            }
        ],
        "evidence": asdict(_evidence()),
        "power_basis": None,
        "input_hashes": {},
    }
    evidence = _evidence()
    manifest["input_hashes"] = compute_events22_input_hashes(
        events=(EventRow("row-1", "ACME", date(2020, 1, 3), 22),),
        listings=(ListingRecord("issuer-1", "ACME", (), date(2010, 1, 1), None, True, True),),
        sessions=tuple(date.fromisoformat(item) for item in manifest["sessions"]),
        eligibility=(EligibilityFact("ACME", date(2020, 1, 3), 20.0, 20_000_000.0, 300),),
        evidence=evidence,
        power_basis=None,
    )
    return manifest


def test_run_manifest_writes_a_sealed_f0_artifact(tmp_path: Path) -> None:
    source = tmp_path / "input.json"
    output = tmp_path / "artifact.json"
    source.write_text(json.dumps(_manifest()))

    artifact = run_manifest(source, output)

    assert json.loads(output.read_text()) == artifact
    assert artifact["protocol"]["primary_entry"] == "D+2_open"
    assert artifact["protocol"]["secondary_entry"] == "D+1_open"
    assert artifact["protocol"]["dollar_volume_lookback_sessions"] == 20
    assert artifact["ledger"][0]["known_date"] == "2020-01-03"
    assert "normalized_session_date" not in artifact["ledger"][0]
    assert artifact["returns_measured"] is False
    assert artifact["provenance"] == {
        "code_id": "056f584-test",
        "snapshot_id": "snapshot-test",
    }


def test_run_manifest_rejects_outcome_fields_and_writes_nothing(tmp_path: Path) -> None:
    source = tmp_path / "input.json"
    output = tmp_path / "artifact.json"
    manifest = _manifest()
    manifest["forward_returns"] = [0.10]
    source.write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="sealed F0 manifest"):
        run_manifest(source, output)

    assert not output.exists()


def test_run_manifest_rejects_stale_section_hashes(tmp_path: Path) -> None:
    source = tmp_path / "input.json"
    output = tmp_path / "artifact.json"
    manifest = _manifest()
    events = cast(list[dict[str, object]], manifest["events"])
    events[0]["ticker"] = "CHANGED"
    source.write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="input hash mismatch"):
        run_manifest(source, output)

    assert not output.exists()


def test_run_manifest_rejects_nonfinite_eligibility_and_blank_provenance(
    tmp_path: Path,
) -> None:
    source = tmp_path / "input.json"
    output = tmp_path / "artifact.json"
    manifest = _manifest()
    manifest["snapshot_id"] = "  "
    eligibility = cast(list[dict[str, object]], manifest["eligibility"])
    eligibility[0]["price"] = float("nan")
    source.write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="sealed F0 manifest rejected"):
        run_manifest(source, output)

    assert not output.exists()


def test_run_manifest_recomputes_the_preexisting_power_source_hash(
    tmp_path: Path,
) -> None:
    basis = tmp_path / "prior-power.json"
    basis.write_text(
        json.dumps(
            {
                "schema_version": "events22-power-basis-v1",
                "cluster_adjusted_dispersion": 0.01,
                "source_frozen_date": "2020-01-01",
            }
        )
    )
    source = tmp_path / "input.json"
    output = tmp_path / "artifact.json"
    manifest = _manifest()
    manifest["power_basis"] = {
        "source_name": "prior-power",
        "source_path": basis.name,
        "source_sha256": "0" * 64,
        "outcome_inspection_not_before": "2020-01-02",
    }
    source.write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="power source hash mismatch"):
        run_manifest(source, output)

    assert not output.exists()


def test_run_manifest_uses_dispersion_parsed_from_the_hashed_power_artifact(
    tmp_path: Path,
) -> None:
    basis = tmp_path / "prior-power.json"
    basis.write_text(
        json.dumps(
            {
                "schema_version": "events22-power-basis-v1",
                "cluster_adjusted_dispersion": 0.123,
                "source_frozen_date": "2019-12-31",
            }
        )
    )
    digest = sha256(basis.read_bytes()).hexdigest()
    source = tmp_path / "input.json"
    output = tmp_path / "artifact.json"
    manifest = _manifest()
    manifest["power_basis"] = {
        "source_name": "prior-power",
        "source_path": basis.name,
        "source_sha256": digest,
        "outcome_inspection_not_before": "2020-01-01",
    }
    evidence = _evidence()
    power_basis = PowerBasis(
        "prior-power",
        digest,
        0.123,
        date(2019, 12, 31),
        date(2020, 1, 1),
    )
    manifest["input_hashes"] = compute_events22_input_hashes(
        events=(EventRow("row-1", "ACME", date(2020, 1, 3), 22),),
        listings=(ListingRecord("issuer-1", "ACME", (), date(2010, 1, 1), None, True, True),),
        sessions=tuple(date.fromisoformat(item) for item in cast(list[str], manifest["sessions"])),
        eligibility=(EligibilityFact("ACME", date(2020, 1, 3), 20.0, 20_000_000.0, 300),),
        evidence=evidence,
        power_basis=power_basis,
    )
    source.write_text(json.dumps(manifest))

    artifact = run_manifest(source, output)

    assert artifact["power_basis"]["cluster_adjusted_dispersion"] == 0.123
