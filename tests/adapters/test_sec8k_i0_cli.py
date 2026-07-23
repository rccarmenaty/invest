"""Sealed manifest-to-artifact acceptance tests for SEC-8K-2.02 I0."""

from __future__ import annotations

import json
import runpy
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

from invest.adapters.sec8k_i0_cli import main, seal_manifest


def _assert_false(value: object) -> None:
    assert isinstance(value, bool)
    assert not value


def _assert_true(value: object) -> None:
    assert isinstance(value, bool)
    assert value


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AssertionError(f"artifact JSON must be readable: {error}") from error
    assert isinstance(value, dict)
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _write_predecessor_artifact(
    tmp_path: Path, manifest_path: Path
) -> tuple[Path, dict[str, object]]:
    artifact: dict[str, object] = {
        "schema_version": "sec8k-i0-artifact-v1",
        "verdict": "kill_line",
        "source_manifest_sha256": sha256(manifest_path.read_bytes()).hexdigest(),
    }
    artifact["artifact_sha256"] = sha256(_canonical(artifact)).hexdigest()
    path = tmp_path / f"{manifest_path.stem}-predecessor.json"
    path.write_bytes(_canonical(artifact))
    predecessor = {
        "issue": 83,
        "manifest_sha256": artifact["source_manifest_sha256"],
        "artifact_sha256": sha256(path.read_bytes()).hexdigest(),
        "artifact_self_hash": artifact["artifact_sha256"],
        "verdict": "kill_line",
    }
    return path, predecessor


def _passing_manifest() -> dict[str, object]:
    filings: list[dict[str, object]] = []
    sessions: list[dict[str, object]] = []
    for year in range(2004, 2026):
        first = date(year, 1, 2)
        for ordinal in range(100):
            session_date = first + timedelta(days=ordinal % 50)
            cik = 1 + ordinal // 50
            ticker = "ACME" if cik == 1 else "OTHER"
            accession = f"{cik:010d}-{year % 100:02d}-{ordinal:06d}"
            market_open = datetime.combine(
                session_date, datetime.min.time(), tzinfo=timezone.utc
            ).replace(hour=14, minute=30)
            filings.append(
                {
                    "accession_number": accession,
                    "cik": f"{cik:010d}",
                    "form": "8-K",
                    "filing_date": session_date.isoformat(),
                    "acceptance_raw": (session_date - timedelta(days=1)).strftime("%Y%m%d170000"),
                    "acceptance_at": (market_open - timedelta(hours=2)).isoformat(),
                    "source_url": (
                        f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}.txt"
                    ),
                    "content_sha256": sha256(accession.encode()).hexdigest(),
                    "item_codes": ["2.02"],
                    "item_202_evidence": ["sec_item_metadata"],
                    "source_occurrences": [f"{year}Q1/master.idx"],
                    "as_filed_ticker": ticker,
                    "item_202_conflicts": [],
                    "amendment_of": None,
                    "parse_error": None,
                }
            )
            sessions.append(
                {
                    "session_date": session_date.isoformat(),
                    "market_open": market_open.isoformat(),
                }
            )
    manifest = {
        "schema_version": "sec8k-i0-manifest-v1",
        "generated_at": "2026-01-02T00:00:00Z",
        "provenance": {
            "source": "original SEC EDGAR full-index and complete submissions",
            "snapshot_id": "fixture-clean-v1",
            "acquired_at": "2026-01-01T00:00:00Z",
            "sec_user_agent": "invest-research contact@example.com",
        },
        "filings": filings,
        "listings": [
            {
                "symbol": symbol,
                "cik": str(cik),
                "related_symbols": [],
                "first_date": "2003-01-01",
                "last_date": None,
                "us_primary_common": True,
            }
            for cik, symbol in ((1, "ACME"), (2, "OTHER"))
        ],
        "sessions": sessions,
        "reconciliation": [
            {
                "year": year,
                "quarter": quarter,
                "form": form,
                "expected": 100 if quarter == 1 and form == "8-K" else 0,
                "fetched": 100 if quarter == 1 and form == "8-K" else 0,
                "parsed": 100 if quarter == 1 and form == "8-K" else 0,
                "item_202": 100 if quarter == 1 and form == "8-K" else 0,
                "failed": 0,
                "excluded": 0,
            }
            for year in range(2004, 2026)
            for quarter in (1, 2, 3, 4)
            for form in ("8-K", "8-K/A")
        ],
        "power_basis": {
            "payload": {
                "basis_id": "pre-sec8k-count-basis-v1",
                "created_at": "2025-01-01T00:00:00Z",
                "effective_sigma": 0.10,
                "provenance": "Frozen independently before SEC-8K outcome inspection",
            },
            "sha256": "",
        },
    }
    power = manifest["power_basis"]
    assert isinstance(power, dict)
    power["sha256"] = sha256(_canonical(power["payload"])).hexdigest()
    return seal_manifest(manifest)


def test_cli_writes_byte_identical_self_hashed_i0_pass_artifacts(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    manifest.write_bytes(_canonical(_passing_manifest()))

    assert main(["audit", "--manifest", str(manifest), "--output", str(first)]) == 0
    assert main(["audit", "--manifest", str(manifest), "--output", str(second)]) == 0

    assert first.read_bytes() == second.read_bytes()
    artifact = _read_json(first)
    assert artifact["verdict"] == "i0_pass"
    assert artifact["status"] == "awaiting_f0_prd"
    _assert_false(artifact["capital_go"])
    _assert_false(artifact["returns_measured"])
    _assert_false(artifact["f0_authorized"])
    _assert_false(artifact["e1_authorized"])
    claimed_hash = artifact.pop("artifact_sha256")
    assert claimed_hash == sha256(_canonical(artifact)).hexdigest()
    result = artifact["result"]
    assert isinstance(result, dict)
    counts = result["counts"]
    assert isinstance(counts, dict)
    usable_years = counts["usable_years"]
    assert isinstance(usable_years, int)
    assert usable_years >= 10
    power = result["power"]
    assert isinstance(power, dict)
    assert power["required_events"] == 1117
    assert power["primary_clustered_t"] == 2.5
    assert power["power_z_beta"] == 0.841621


def test_universe_first_cli_requires_the_actual_predecessor_artifact(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(_canonical(_passing_manifest()))
    _, predecessor = _write_predecessor_artifact(tmp_path, manifest_path)
    universe: dict[str, object] = {
        "schema_version": "sec8k-uf-universe-v1",
        "generated_at": "2026-01-03T00:00:00Z",
        "predecessor": predecessor,
        "provenance": {
            "source": "independent PIT US-primary-common listing fixture",
            "snapshot_id": "fixture-universe-v1",
            "acquired_at": "2026-01-01T00:00:00Z",
        },
        "listings": _passing_manifest()["listings"],
    }
    universe["section_hashes"] = {
        section: sha256(_canonical(universe[section])).hexdigest()
        for section in ("predecessor", "provenance", "listings")
    }
    universe["universe_sha256"] = sha256(_canonical(universe)).hexdigest()
    universe_path = tmp_path / "universe.json"
    universe_path.write_bytes(_canonical(universe))

    assert (
        main(
            [
                "uf-audit",
                "--manifest",
                str(manifest_path),
                "--universe",
                str(universe_path),
                "--output",
                str(tmp_path / "artifact.json"),
            ]
        )
        == 2
    )

    predecessor["artifact_self_hash"] = "b" * 64
    universe["section_hashes"] = {
        section: sha256(_canonical(universe[section])).hexdigest()
        for section in ("predecessor", "provenance", "listings")
    }
    universe["universe_sha256"] = sha256(
        _canonical({key: value for key, value in universe.items() if key != "universe_sha256"})
    ).hexdigest()
    universe_path.write_bytes(_canonical(universe))
    assert (
        main(
            [
                "uf-audit",
                "--manifest",
                str(manifest_path),
                "--universe",
                str(universe_path),
                "--predecessor-artifact",
                str(tmp_path / "manifest-predecessor.json"),
                "--output",
                str(tmp_path / "detached.json"),
            ]
        )
        == 2
    )


def test_universe_first_cli_excludes_non_target_filers_from_mapping_quality(
    tmp_path: Path,
) -> None:
    manifest = deepcopy(_passing_manifest())
    filings = manifest["filings"]
    reconciliation = manifest["reconciliation"]
    assert isinstance(filings, list)
    assert isinstance(reconciliation, list)
    for year in range(2004, 2026):
        accession = f"0000000999-{year % 100:02d}-000001"
        filing_date = date(year, 1, 2)
        filings.append(
            {
                "accession_number": accession,
                "cik": "0000000999",
                "form": "8-K",
                "filing_date": filing_date.isoformat(),
                "acceptance_raw": filing_date.strftime("%Y%m%d170000"),
                "acceptance_at": datetime(year, 1, 2, 12, 30, tzinfo=timezone.utc).isoformat(),
                "source_url": (f"https://www.sec.gov/Archives/edgar/data/999/{accession}.txt"),
                "content_sha256": sha256(accession.encode()).hexdigest(),
                "item_codes": ["2.02"],
                "item_202_evidence": ["sec_item_metadata"],
                "source_occurrences": [f"{year}Q1/master.idx"],
                "as_filed_ticker": None,
                "item_202_conflicts": [],
                "amendment_of": None,
                "parse_error": None,
            }
        )
        for row in reconciliation:
            if (
                isinstance(row, dict)
                and row["year"] == year
                and row["quarter"] == 1
                and row["form"] == "8-K"
            ):
                for key in ("expected", "fetched", "parsed", "item_202"):
                    row[key] = 101
                break
    manifest = seal_manifest(manifest)
    manifest_path = tmp_path / "sec-manifest.json"
    manifest_bytes = _canonical(manifest) + b"\n"
    manifest_path.write_bytes(manifest_bytes)

    predecessor_path, predecessor = _write_predecessor_artifact(tmp_path, manifest_path)
    universe_listings = deepcopy(manifest["listings"])
    assert isinstance(universe_listings, list)
    for listing in universe_listings:
        assert isinstance(listing, dict)
        listing["exchange"] = "XNYS"
    universe = {
        "schema_version": "sec8k-uf-universe-v1",
        "generated_at": "2026-01-03T00:00:00Z",
        "predecessor": predecessor,
        "provenance": {
            "source": "independent PIT US-primary-common listing fixture",
            "snapshot_id": "fixture-universe-v1",
            "acquired_at": "2026-01-01T00:00:00Z",
        },
        "listings": universe_listings,
    }
    universe["section_hashes"] = {
        section: sha256(_canonical(universe[section])).hexdigest()
        for section in ("predecessor", "provenance", "listings")
    }
    universe["universe_sha256"] = sha256(_canonical(universe)).hexdigest()
    universe_path = tmp_path / "universe.json"
    universe_path.write_bytes(_canonical(universe))

    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    args = [
        "uf-audit",
        "--manifest",
        str(manifest_path),
        "--universe",
        str(universe_path),
        "--predecessor-artifact",
        str(predecessor_path),
        "--output",
    ]
    assert main([*args, str(first)]) == 0
    assert main([*args, str(second)]) == 0
    assert first.read_bytes() == second.read_bytes()

    artifact = _read_json(first)
    assert artifact["schema_version"] == "sec8k-uf-i0-artifact-v1"
    assert artifact["line"] == "sec-8k-uf-universe-first-pit-mapping"
    assert artifact["verdict"] == "i0_pass"
    assert artifact["status"] == "awaiting_f0_prd"
    _assert_false(artifact["capital_go"])
    _assert_false(artifact["returns_measured"])
    assert artifact["predecessor"] == predecessor
    assert artifact["universe_artifact_sha256"] == universe["universe_sha256"]
    result = artifact["result"]
    assert isinstance(result, dict)
    counts = result["counts"]
    gate_values = result["gates"]
    assert isinstance(counts, dict)
    assert isinstance(gate_values, list)
    assert counts["all_original_filer_records"] == 2_222
    assert counts["in_universe_candidates"] == 2_200
    assert counts["out_of_universe_filer_records"] == 22
    assert counts["mapped_original_filings"] == 2_200
    year_counts = result["year_counts"]
    assert isinstance(year_counts, dict)
    assert year_counts["2004"]["all_original_filer_records"] == 101
    assert year_counts["2004"]["in_universe_candidates"] == 100
    assert year_counts["2004"]["out_of_universe_filer_records"] == 1
    assert year_counts["2004"]["ambiguous_in_universe_candidates"] == 0
    gates = {gate["id"]: gate for gate in gate_values if isinstance(gate, dict)}
    coverage = result["universe_coverage"]
    assert isinstance(coverage, dict)
    by_exchange = coverage["by_exchange"]
    assert isinstance(by_exchange, dict)
    assert by_exchange["XNYS"] == {"windows": 2, "with_cik": 2, "rate": 1.0}
    _assert_true(gates["U1-universe-cik-coverage"]["passed"])
    _assert_true(gates["U3-in-universe-mapping"]["passed"])


def test_universe_first_cli_maps_listing_window_at_the_known_session(
    tmp_path: Path,
) -> None:
    manifest = deepcopy(_passing_manifest())
    filings = manifest["filings"]
    assert isinstance(filings, list)
    target_accession = "0000000001-04-000000"
    for filing in filings:
        if isinstance(filing, dict) and filing["accession_number"] == target_accession:
            filing["acceptance_at"] = "2004-01-02T16:00:00+00:00"
            break
    manifest = seal_manifest(manifest)
    manifest_path = tmp_path / "sec-manifest.json"
    manifest_path.write_bytes(_canonical(manifest))

    listings = deepcopy(manifest["listings"])
    assert isinstance(listings, list)
    for listing in listings:
        if isinstance(listing, dict) and listing["symbol"] == "ACME":
            listing["last_date"] = "2004-01-02"
            break
    listings.append(
        {
            "symbol": "ACME2",
            "cik": "1",
            "related_symbols": ["ACME"],
            "first_date": "2004-01-03",
            "last_date": None,
            "us_primary_common": True,
        }
    )
    predecessor_path, predecessor = _write_predecessor_artifact(tmp_path, manifest_path)
    universe = {
        "schema_version": "sec8k-uf-universe-v1",
        "generated_at": "2026-01-03T00:00:00Z",
        "predecessor": predecessor,
        "provenance": {
            "source": "independent PIT US-primary-common listing fixture",
            "snapshot_id": "fixture-universe-v1",
            "acquired_at": "2026-01-01T00:00:00Z",
        },
        "listings": listings,
    }
    universe["section_hashes"] = {
        section: sha256(_canonical(universe[section])).hexdigest()
        for section in ("predecessor", "provenance", "listings")
    }
    universe["universe_sha256"] = sha256(_canonical(universe)).hexdigest()
    universe_path = tmp_path / "universe.json"
    universe_path.write_bytes(_canonical(universe))
    output = tmp_path / "artifact.json"

    assert (
        main(
            [
                "uf-audit",
                "--manifest",
                str(manifest_path),
                "--universe",
                str(universe_path),
                "--predecessor-artifact",
                str(predecessor_path),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    artifact = _read_json(output)
    result = artifact["result"]
    assert isinstance(result, dict)
    ledger = result["decision_ledger"]
    assert isinstance(ledger, list)
    target = next(
        row
        for row in ledger
        if isinstance(row, dict) and row["accession_number"] == target_accession
    )
    assert target["known_session"] == "2004-01-03"
    assert target["canonical_symbol"] == "ACME2"


def test_universe_first_cli_enforces_frozen_95_percent_floors(
    tmp_path: Path,
) -> None:
    def run(
        manifest: dict[str, object], listings: list[dict[str, object]], name: str
    ) -> dict[str, object]:
        sealed_manifest = seal_manifest(manifest)
        manifest_path = tmp_path / f"{name}-manifest.json"
        manifest_path.write_bytes(_canonical(sealed_manifest))
        predecessor_path, predecessor = _write_predecessor_artifact(tmp_path, manifest_path)
        universe: dict[str, object] = {
            "schema_version": "sec8k-uf-universe-v1",
            "generated_at": "2026-01-03T00:00:00Z",
            "predecessor": predecessor,
            "provenance": {
                "source": "independent PIT US-primary-common listing fixture",
                "snapshot_id": name,
                "acquired_at": "2026-01-01T00:00:00Z",
            },
            "listings": listings,
        }
        universe["section_hashes"] = {
            section: sha256(_canonical(universe[section])).hexdigest()
            for section in ("predecessor", "provenance", "listings")
        }
        universe["universe_sha256"] = sha256(_canonical(universe)).hexdigest()
        universe_path = tmp_path / f"{name}-universe.json"
        universe_path.write_bytes(_canonical(universe))
        output = tmp_path / f"{name}-artifact.json"
        assert (
            main(
                [
                    "uf-audit",
                    "--manifest",
                    str(manifest_path),
                    "--universe",
                    str(universe_path),
                    "--predecessor-artifact",
                    str(predecessor_path),
                    "--output",
                    str(output),
                ]
            )
            == 0
        )
        return _read_json(output)

    def gates(artifact: dict[str, object]) -> dict[str, dict[str, object]]:
        result = artifact["result"]
        assert isinstance(result, dict)
        values = result["gates"]
        assert isinstance(values, list)
        return {str(gate["id"]): gate for gate in values if isinstance(gate, dict)}

    base_manifest = _passing_manifest()
    base_listings = deepcopy(base_manifest["listings"])
    assert isinstance(base_listings, list)
    for listing in base_listings:
        assert isinstance(listing, dict)
        listing["exchange"] = "XNYS"
    for ordinal in range(98):
        base_listings.append(
            {
                "symbol": f"DUMMY{ordinal:03d}",
                "cik": None if ordinal < 5 else str(10_000 + ordinal),
                "related_symbols": [],
                "first_date": "2003-01-01",
                "last_date": None,
                "us_primary_common": True,
                "exchange": "XNAS",
            }
        )
    at_coverage_floor = run(deepcopy(base_manifest), deepcopy(base_listings), "coverage-95")
    _assert_true(gates(at_coverage_floor)["U1-universe-cik-coverage"]["passed"])
    below_floor_listings = deepcopy(base_listings)
    below_floor_listings[7]["cik"] = None
    below_coverage_floor = run(deepcopy(base_manifest), below_floor_listings, "coverage-94")
    _assert_false(gates(below_coverage_floor)["U1-universe-cik-coverage"]["passed"])
    assert below_coverage_floor["verdict"] == "kill_line"

    def ambiguous_manifest(extra: bool) -> dict[str, object]:
        manifest = deepcopy(_passing_manifest())
        filings = manifest["filings"]
        assert isinstance(filings, list)
        changed = 0
        base_ordinals = {f"{ordinal:06d}" for ordinal in range(5)}
        for filing in filings:
            if not isinstance(filing, dict) or filing["cik"] != "0000000001":
                continue
            ordinal = str(filing["accession_number"]).rsplit("-", 1)[1]
            year = str(filing["filing_date"])[:4]
            if ordinal in base_ordinals or (extra and year == "2004" and ordinal == "000005"):
                filing["as_filed_ticker"] = None
                changed += 1
        assert changed == (111 if extra else 110)
        return manifest

    mapping_listings = deepcopy(_passing_manifest()["listings"])
    assert isinstance(mapping_listings, list)
    for listing in mapping_listings:
        assert isinstance(listing, dict)
        listing["exchange"] = "XNYS"
    mapping_listings.append(
        {
            "symbol": "ACME2",
            "cik": "1",
            "related_symbols": [],
            "first_date": "2003-01-01",
            "last_date": None,
            "us_primary_common": True,
            "exchange": "XNAS",
        }
    )
    at_mapping_floor = run(ambiguous_manifest(False), deepcopy(mapping_listings), "mapping-95")
    _assert_true(gates(at_mapping_floor)["U3-in-universe-mapping"]["passed"])
    assert at_mapping_floor["verdict"] == "i0_pass"
    below_mapping_floor = run(
        ambiguous_manifest(True), deepcopy(mapping_listings), "mapping-below-95"
    )
    _assert_false(gates(below_mapping_floor)["U3-in-universe-mapping"]["passed"])
    assert below_mapping_floor["verdict"] == "kill_line"


def test_universe_first_cli_rejects_non_hex_predecessor_hash_before_output(
    tmp_path: Path,
) -> None:
    manifest = _passing_manifest()
    manifest_path = tmp_path / "sec-manifest.json"
    manifest_path.write_bytes(_canonical(manifest))
    predecessor_path, predecessor = _write_predecessor_artifact(tmp_path, manifest_path)
    predecessor["artifact_sha256"] = "g" * 64
    universe = {
        "schema_version": "sec8k-uf-universe-v1",
        "generated_at": "2026-01-03T00:00:00Z",
        "predecessor": predecessor,
        "provenance": {
            "source": "independent PIT US-primary-common listing fixture",
            "snapshot_id": "fixture-universe-v1",
            "acquired_at": "2026-01-01T00:00:00Z",
        },
        "listings": deepcopy(manifest["listings"]),
    }
    universe["section_hashes"] = {
        section: sha256(_canonical(universe[section])).hexdigest()
        for section in ("predecessor", "provenance", "listings")
    }
    universe["universe_sha256"] = sha256(_canonical(universe)).hexdigest()
    universe_path = tmp_path / "universe.json"
    universe_path.write_bytes(_canonical(universe))
    output = tmp_path / "artifact.json"

    assert (
        main(
            [
                "uf-audit",
                "--manifest",
                str(manifest_path),
                "--universe",
                str(universe_path),
                "--predecessor-artifact",
                str(predecessor_path),
                "--output",
                str(output),
            ]
        )
        == 2
    )
    assert not output.exists()


def test_cli_refuses_outcomes_unknown_fields_stale_hashes_and_f0_e1_before_output(
    tmp_path: Path,
) -> None:
    outcome_manifest = _passing_manifest()
    filings = outcome_manifest["filings"]
    assert isinstance(filings, list)
    assert isinstance(filings[0], dict)
    filings[0]["forward_returns"] = [0.01]
    outcome_manifest = seal_manifest(outcome_manifest)
    outcome_path = tmp_path / "outcome.json"
    outcome_path.write_bytes(_canonical(outcome_manifest))
    outcome_output = tmp_path / "outcome-artifact.json"
    assert main(["audit", "--manifest", str(outcome_path), "--output", str(outcome_output)]) == 2
    assert not outcome_output.exists()

    unknown_manifest = _passing_manifest()
    unknown_manifest["mystery"] = "not allowed"
    unknown_path = tmp_path / "unknown.json"
    unknown_path.write_bytes(_canonical(unknown_manifest))
    unknown_output = tmp_path / "unknown-artifact.json"
    assert main(["audit", "--manifest", str(unknown_path), "--output", str(unknown_output)]) == 2
    assert not unknown_output.exists()

    stale_manifest = _passing_manifest()
    stale_filings = stale_manifest["filings"]
    assert isinstance(stale_filings, list)
    assert isinstance(stale_filings[0], dict)
    stale_filings[0]["as_filed_ticker"] = "CHANGED-AFTER-SEAL"
    stale_path = tmp_path / "stale.json"
    stale_path.write_bytes(_canonical(stale_manifest))
    stale_output = tmp_path / "stale-artifact.json"
    assert main(["audit", "--manifest", str(stale_path), "--output", str(stale_output)]) == 2
    assert not stale_output.exists()

    assert main(["f0"]) == 2
    assert main(["e1"]) == 2


def test_research_input_builder_does_not_reuse_a_symbol_outside_its_exact_pit_window() -> None:
    builder_path = (
        Path(__file__).parents[2]
        / "fixtures"
        / "real-continuous"
        / "reports"
        / "research_sec8k_i0_inputs.py"
    )
    build_listings = runpy.run_path(str(builder_path))["_build_listings"]
    sep_rows = [
        [
            "SEP",
            "unused",
            "REUSED",
            "",
            "NYSE",
            "Domestic Common Stock",
            "2020-01-01",
            "2021-12-31",
            "Y",
        ]
    ]
    reference_rows = [
        {
            "symbol": "REUSED",
            "cik": "999",
            "related": ["OLD"],
            "first": "2022-01-01",
            "last": None,
        }
    ]

    listings = build_listings(sep_rows, reference_rows)

    assert listings[0]["cik"] is None
    assert listings[0]["related_symbols"] == []


def test_acquire_refuses_any_period_other_than_the_full_frozen_protocol(
    tmp_path: Path,
    capsys,
) -> None:
    missing = tmp_path / "not-read.json"
    output = tmp_path / "manifest.json"

    code = main(
        [
            "acquire",
            "--start-year",
            "2005",
            "--end-year",
            "2025",
            "--listings",
            str(missing),
            "--sessions",
            str(missing),
            "--power-basis",
            str(missing),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--submissions-zip",
            str(missing),
            "--submissions-sha256",
            "0" * 64,
            "--manifest-output",
            str(output),
            "--user-agent",
            "invest-research contact@example.com",
            "--snapshot-id",
            "truncated",
            "--generated-at",
            "2026-01-01T00:00:00Z",
        ]
    )

    assert code == 2
    assert "must cover exactly 2004 through 2025" in capsys.readouterr().err
    assert not output.exists()
