"""EVENTS-22 F0: feasibility and integrity only, never returns."""

from __future__ import annotations

from datetime import date, timedelta
from dataclasses import replace

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


def _basis(dispersion: float) -> PowerBasis:
    return PowerBasis(
        "prior-artifact",
        "a" * 64,
        dispersion,
        date(2019, 12, 31),
        date(2020, 1, 1),
    )


def _run(**kwargs):
    input_hashes = compute_events22_input_hashes(
        events=kwargs["events"],
        listings=kwargs["listings"],
        sessions=kwargs["sessions"],
        eligibility=kwargs["eligibility"],
        evidence=kwargs["evidence"],
        power_basis=kwargs["power_basis"],
    )
    return run_events22_f0(**kwargs, input_hashes=input_hashes)


def test_protocol_freezes_issue_81_f0_and_future_e1_boundaries() -> None:
    assert PROTOCOL.event_code == 22
    assert PROTOCOL.event_semantics == "Results of Operations / Item 2.02"
    assert PROTOCOL.known_time_policy == "second_open_date_only"
    assert PROTOCOL.primary_entry == "D+2_open"
    assert PROTOCOL.secondary_entry == "D+1_open"
    assert PROTOCOL.primary_horizon_sessions == 60
    assert PROTOCOL.secondary_horizon_sessions == 60
    assert PROTOCOL.diagnostic_horizon_sessions == 20
    assert PROTOCOL.min_prior_years == 2
    assert PROTOCOL.min_prior_events == 1_000
    assert PROTOCOL.min_usable_years == 10
    assert PROTOCOL.min_price == 5.0
    assert PROTOCOL.dollar_volume_lookback_sessions == 20
    assert PROTOCOL.min_median_dollar_volume == 10_000_000.0
    assert PROTOCOL.min_prior_sessions == 252
    assert PROTOCOL.power_target_effect == 0.01
    assert PROTOCOL.power_target == 0.80
    assert PROTOCOL.primary_cost_bps == 10.0
    assert PROTOCOL.stress_cost_bps == 25.0
    assert PROTOCOL.capital_go is False
    assert PROTOCOL.initial_authorisation == "F0_only"


def test_run_coalesces_issuer_date_rows_then_applies_first_wins_deoverlap() -> None:
    sessions = tuple(date(2020, 1, 1) + timedelta(days=offset) for offset in range(200))
    listings = (
        ListingRecord("issuer-1", "ACME", (), date(2010, 1, 1), None, True, True),
        ListingRecord("issuer-1", "OLD", ("ACME",), date(2010, 1, 1), date(2020, 6, 1), True, True),
    )
    events = (
        EventRow("row-1", "ACME", date(2020, 1, 3), 22),
        EventRow("row-2", "OLD", date(2020, 1, 3), 22),
        EventRow("row-3", "ACME", date(2020, 1, 10), 22),
    )
    eligibility = (
        EligibilityFact("ACME", date(2020, 1, 3), 20.0, 20_000_000.0, 300),
        EligibilityFact("ACME", date(2020, 1, 10), 20.0, 20_000_000.0, 307),
    )

    result = _run(
        events=events,
        listings=listings,
        sessions=sessions,
        eligibility=eligibility,
        evidence=F0Evidence.synthetic_pass(),
        power_basis=None,
    )

    assert len(result.canonical_events) == 1
    canonical = result.canonical_events[0]
    assert canonical.issuer_id == "issuer-1"
    assert canonical.known_date == date(2020, 1, 3)
    assert canonical.raw_row_ids == ("row-1", "row-2")
    assert result.counts.raw_code22 == 3
    assert result.counts.canonical == 2
    assert result.density.duplicate_rows_coalesced == 1
    assert result.counts.de_overlapped == 1
    assert result.counts.exclusions["issuer_horizon_overlap"] == 1
    assert result.counts.mapped == 3
    assert result.counts.canonical == 2
    assert result.counts.eligible == 2
    assert result.counts_by_year[2020].raw == 3
    assert result.counts_by_year[2020].canonical == 2
    assert result.counts_by_year[2020].de_overlapped == 1
    assert {(entry.source_row_id, entry.decision, entry.reason) for entry in result.ledger} == {
        ("row-1", "included", "issuer_date_coalesced"),
        ("row-2", "included", "issuer_date_coalesced"),
        ("row-3", "excluded", "issuer_horizon_overlap"),
    }
    assert result.verdict == "underpowered_stop"


def test_run_freezes_annual_folds_from_strictly_prior_events() -> None:
    sessions = tuple(date(2017, 1, 1) + timedelta(days=offset) for offset in range(1_900))
    years = (2018, 2019, 2020)
    events = tuple(EventRow(f"row-{year}", f"T{year}", date(year, 6, 1), 22) for year in years)
    listings = tuple(
        ListingRecord(f"issuer-{year}", f"T{year}", (), date(2010, 1, 1), None, True, True)
        for year in years
    )
    eligibility = tuple(
        EligibilityFact(f"T{year}", date(year, 6, 1), 20.0, 20_000_000.0, 300) for year in years
    )

    result = _run(
        events=events,
        listings=listings,
        sessions=sessions,
        eligibility=eligibility,
        evidence=F0Evidence.synthetic_pass(),
        power_basis=None,
        config=replace(PROTOCOL, min_prior_events=2),
    )

    assert result.folds[2018].usable is False
    assert result.folds[2019].prior_years == 1
    assert result.folds[2019].prior_events == 1
    assert result.folds[2019].usable is False
    assert result.folds[2020].prior_years == 2
    assert result.folds[2020].prior_events == 2
    assert result.folds[2020].usable is True
    assert result.usable_years == (2020,)


def test_power_gate_uses_only_expected_q5_events_and_a_preexisting_basis() -> None:
    sessions = tuple(date(2019, 1, 1) + timedelta(days=offset) for offset in range(800))
    event_date = date(2020, 1, 3)
    events = tuple(EventRow(f"row-{i}", f"T{i}", event_date, 22) for i in range(100))
    listings = tuple(
        ListingRecord(f"issuer-{i}", f"T{i}", (), date(2010, 1, 1), None, True, True)
        for i in range(100)
    )
    eligibility = tuple(
        EligibilityFact(f"T{i}", event_date, 20.0, 20_000_000.0, 300) for i in range(100)
    )
    config = replace(PROTOCOL, min_prior_years=0, min_prior_events=0, min_usable_years=1)
    common = {
        "events": events,
        "listings": listings,
        "sessions": sessions,
        "eligibility": eligibility,
        "evidence": F0Evidence.synthetic_pass(),
        "config": config,
    }

    passing = _run(
        **common,
        power_basis=_basis(0.01),
    )
    failing = _run(
        **common,
        power_basis=_basis(0.10),
    )

    assert passing.power.q5_events == 20
    assert passing.power.detectable_effect_at_target_power < 0.01
    assert passing.power.passed is True
    assert passing.verdict == "f0_pass"
    assert failing.power.detectable_effect_at_target_power > 0.01
    assert failing.power.passed is False
    assert failing.verdict == "underpowered_stop"


def test_power_gate_requires_the_frozen_minimum_usable_years() -> None:
    sessions = tuple(date(2017, 1, 1) + timedelta(days=offset) for offset in range(1_900))
    years = (2018, 2019, 2020)
    result = _run(
        events=tuple(EventRow(f"row-{year}", f"T{year}", date(year, 6, 1), 22) for year in years),
        listings=tuple(
            ListingRecord(f"issuer-{year}", f"T{year}", (), date(2010, 1, 1), None, True, True)
            for year in years
        ),
        sessions=sessions,
        eligibility=tuple(
            EligibilityFact(f"T{year}", date(year, 6, 1), 20.0, 20_000_000.0, 300) for year in years
        ),
        evidence=F0Evidence.synthetic_pass(),
        power_basis=_basis(0.0001),
        config=replace(PROTOCOL, min_prior_years=0, min_prior_events=0),
    )

    assert len(result.usable_years) == 3
    assert result.power.passed is False
    assert "10 usable years" in result.power.reason


def test_power_basis_must_predate_outcome_inspection() -> None:
    event_date = date(2020, 1, 3)
    result = _run(
        events=(EventRow("row-1", "ACME", event_date, 22),),
        listings=(ListingRecord("issuer-1", "ACME", (), date(2010, 1, 1), None, True, True),),
        sessions=tuple(event_date + timedelta(days=offset) for offset in range(100)),
        eligibility=(EligibilityFact("ACME", event_date, 20.0, 20_000_000.0, 300),),
        evidence=F0Evidence.synthetic_pass(),
        power_basis=replace(
            _basis(0.001),
            source_frozen_date=date(2020, 1, 1),
            outcome_inspection_not_before=date(2020, 1, 1),
        ),
        config=replace(PROTOCOL, min_prior_years=0, min_prior_events=0, min_usable_years=1),
    )

    assert result.power.basis_valid is False
    assert result.verdict == "underpowered_stop"


def test_duplicate_eligibility_facts_fail_closed_instead_of_overwriting() -> None:
    event_date = date(2020, 1, 3)
    facts = (
        EligibilityFact("ACME", event_date, 20.0, 20_000_000.0, 300),
        EligibilityFact("ACME", event_date, 4.0, 20_000_000.0, 300),
    )

    try:
        _run(
            events=(EventRow("row-1", "ACME", event_date, 22),),
            listings=(ListingRecord("issuer-1", "ACME", (), date(2010, 1, 1), None, True, True),),
            sessions=tuple(event_date + timedelta(days=offset) for offset in range(100)),
            eligibility=facts,
            evidence=F0Evidence.synthetic_pass(),
            power_basis=None,
        )
    except ValueError as error:
        assert "unique" in str(error)
    else:
        raise AssertionError("duplicate eligibility facts must fail closed")


def test_integrity_failure_kills_before_power_and_never_authorises_capital() -> None:
    event_date = date(2020, 1, 3)
    evidence = replace(F0Evidence.synthetic_pass(), pit_mapping_verified=False)
    result = _run(
        events=(EventRow("row-1", "ACME", event_date, 22),),
        listings=(ListingRecord("issuer-1", "ACME", (), date(2010, 1, 1), None, True, True),),
        sessions=tuple(event_date + timedelta(days=offset) for offset in range(100)),
        eligibility=(EligibilityFact("ACME", event_date, 20.0, 20_000_000.0, 300),),
        evidence=evidence,
        power_basis=_basis(0.001),
        config=replace(PROTOCOL, min_prior_years=0, min_prior_events=0),
    )

    mapping_gate = next(gate for gate in result.gates if gate.id == "F0-PIT-map")
    assert mapping_gate.passed is False
    assert result.verdict == "kill_line"
    assert result.capital_go is False
    assert result.returns_measured is False
    assert result.e1_status == "blocked"


def test_invalid_input_hash_fails_the_reproducibility_gate() -> None:
    event_date = date(2020, 1, 3)
    result = run_events22_f0(
        events=(EventRow("row-1", "ACME", event_date, 22),),
        listings=(ListingRecord("issuer-1", "ACME", (), date(2010, 1, 1), None, True, True),),
        sessions=tuple(event_date + timedelta(days=offset) for offset in range(100)),
        eligibility=(EligibilityFact("ACME", event_date, 20.0, 20_000_000.0, 300),),
        evidence=F0Evidence.synthetic_pass(),
        power_basis=_basis(0.001),
        input_hashes={"events": "not-a-sha256"},
        config=replace(PROTOCOL, min_prior_years=0, min_prior_events=0),
    )

    gate = next(gate for gate in result.gates if gate.id == "F0-reproducibility")
    assert gate.passed is False
    assert result.verdict == "kill_line"


def test_artifact_is_deterministic_self_hashed_and_f0_sealed() -> None:
    event_date = date(2020, 1, 3)
    evidence = F0Evidence.synthetic_pass()
    power_basis = _basis(0.001)
    config = replace(PROTOCOL, min_prior_years=0, min_prior_events=0)
    input_hashes = compute_events22_input_hashes(
        events=(EventRow("row-1", "ACME", event_date, 22),),
        listings=(ListingRecord("issuer-1", "ACME", (), date(2010, 1, 1), None, True, True),),
        sessions=tuple(event_date + timedelta(days=offset) for offset in range(100)),
        eligibility=(EligibilityFact("ACME", event_date, 20.0, 20_000_000.0, 300),),
        evidence=evidence,
        power_basis=power_basis,
    )
    result = run_events22_f0(
        events=(EventRow("row-1", "ACME", event_date, 22),),
        listings=(ListingRecord("issuer-1", "ACME", (), date(2010, 1, 1), None, True, True),),
        sessions=tuple(event_date + timedelta(days=offset) for offset in range(100)),
        eligibility=(EligibilityFact("ACME", event_date, 20.0, 20_000_000.0, 300),),
        evidence=evidence,
        power_basis=power_basis,
        input_hashes=input_hashes,
        config=config,
    )

    first = build_events22_f0_artifact(
        result=result,
        evidence=evidence,
        input_hashes=input_hashes,
        power_basis=power_basis,
        provenance=F0Provenance("snapshot-test", "code-test"),
        config=config,
    )
    second = build_events22_f0_artifact(
        result=result,
        evidence=evidence,
        input_hashes=input_hashes,
        power_basis=power_basis,
        provenance=F0Provenance("snapshot-test", "code-test"),
        config=config,
    )

    assert first == second
    assert len(first["config_sha256"]) == 64
    assert len(first["artifact_sha256"]) == 64
    assert first["protocol"]["primary_entry"] == "D+2_open"
    assert first["protocol"]["secondary_entry"] == "D+1_open"
    assert first["capital_go"] is False
    assert first["returns_measured"] is False
    assert "reaction_values" not in first
    assert "forward_returns" not in first


def test_e1_entry_point_refuses_until_a_separate_implementation_is_approved() -> None:
    try:
        refuse_events22_e1()
    except PermissionError as error:
        assert "F0-only" in str(error)
    else:
        raise AssertionError("E1 must be unavailable in the F0 implementation")
