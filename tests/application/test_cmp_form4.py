"""Unit tests for CMP opportunistic Form-4 baseline pure helpers (PRD #79)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from invest.application.cmp_form4 import (
    PROTOCOL,
    ClassificationCounts,
    CmpClass,
    PurchaseEvent,
    Verdict,
    build_cmp_artifact,
    build_purchase_events,
    classify_at,
    classify_purchase,
    combine_stage_reports,
    de_overlap_events,
    evaluate_c1_parse,
    evaluate_c2_map,
    evaluate_c3_class,
    evaluate_c4_protocol,
    evaluate_d1_volume,
    evaluate_d2_year_spread,
    evaluate_d3_year_mass,
    evaluate_d4_mds,
    evaluate_stage_c,
    evaluate_stage_d,
    evaluate_stage_e1_authorisation,
    history_rows_from_transactions,
    min_detectable_size,
    opportunistic_events,
    require_e1_authorisation,
    required_events,
    year_shares,
)
from invest.domain.models import InsiderTransaction


def txn(
    *,
    owner: str = "owner-1",
    symbol: str = "ACME",
    issuer: str = "0000001",
    trans: date = date(2024, 3, 4),
    filed: date | None = None,
    code: str = "P",
    acquired: str = "A",
    shares: str = "1000",
    price: str = "50",
    accession: str | None = None,
) -> InsiderTransaction:
    filing_date = filed if filed is not None else trans + timedelta(days=2)
    return InsiderTransaction(
        accession_number=accession or f"{owner}-{trans:%Y%m%d}-{code}",
        issuer_cik=issuer,
        trading_symbol=symbol,
        owner_cik=owner,
        filing_date=filing_date,
        transaction_date=trans,
        transaction_code=code,
        acquired_disposed=acquired,
        shares=Decimal(shares),
        price_per_share=Decimal(price),
        direct_ownership=True,
        document_type="4",
        original_submission_date=None,
        late_filing=False,
    )


def _event(
    *,
    symbol: str = "ACME",
    known: date = date(2024, 3, 6),
    owner: str = "owner-1",
    cmp_class: CmpClass = CmpClass.OPPORTUNISTIC,
) -> PurchaseEvent:
    return PurchaseEvent(
        trading_symbol=symbol,
        issuer_cik="0000001",
        owner_cik=owner,
        known_time=known,
        first_transaction_date=known - timedelta(days=2),
        last_transaction_date=known - timedelta(days=2),
        purchase_count=1,
        gross_value=Decimal("50000"),
        cmp_class=cmp_class,
    )


# --- Classification (point-in-time) ------------------------------------------


def test_three_year_same_month_history_is_routine() -> None:
    # Evaluation in 2024; prior years 2021-2023 all have March trades
    history = [
        (date(2021, 3, 5), 2021, 3),
        (date(2022, 3, 8), 2022, 3),
        (date(2023, 3, 4), 2023, 3),
    ]

    assert (
        classify_at(history, evaluation_known_time=date(2024, 6, 1))
        is CmpClass.ROUTINE
    )


def test_three_year_activity_without_shared_month_is_opportunistic() -> None:
    history = [
        (date(2021, 1, 5), 2021, 1),
        (date(2022, 6, 8), 2022, 6),
        (date(2023, 11, 4), 2023, 11),
    ]

    assert (
        classify_at(history, evaluation_known_time=date(2024, 6, 1))
        is CmpClass.OPPORTUNISTIC
    )


def test_missing_one_of_three_prior_years_is_unclassified() -> None:
    history = [
        (date(2021, 3, 5), 2021, 3),
        (date(2023, 3, 4), 2023, 3),
        # 2022 absent
    ]

    assert (
        classify_at(history, evaluation_known_time=date(2024, 6, 1))
        is CmpClass.UNCLASSIFIED
    )


def test_empty_history_is_unclassified() -> None:
    assert classify_at((), evaluation_known_time=date(2024, 6, 1)) is CmpClass.UNCLASSIFIED


def test_classification_ignores_same_day_and_future_known_time() -> None:
    """Look-ahead trap: contemporaneous/future filings must not reclassify."""

    evaluation = date(2024, 6, 10)
    # Only 2021+2022 prior; a 2023 pattern would complete three years — but its
    # known-time is after evaluation, so it must not count.
    history = [
        (date(2021, 3, 5), 2021, 3),
        (date(2022, 3, 8), 2022, 3),
        (date(2024, 6, 10), 2023, 3),  # same known-time as evaluation
        (date(2024, 6, 11), 2023, 3),  # future known-time
    ]

    assert classify_at(history, evaluation_known_time=evaluation) is CmpClass.UNCLASSIFIED


def test_classification_uses_only_prior_known_time_even_when_trade_year_is_old() -> None:
    """A late-filed old trade (filing after evaluation) cannot enter history."""

    evaluation = date(2024, 6, 10)
    history = [
        (date(2021, 3, 5), 2021, 3),
        (date(2022, 3, 8), 2022, 3),
        # Transaction in 2023 but filed after evaluation → excluded by known-time
        (date(2024, 7, 1), 2023, 3),
    ]

    assert classify_at(history, evaluation_known_time=evaluation) is CmpClass.UNCLASSIFIED


def test_classify_purchase_delegates_to_filing_known_time() -> None:
    purchase = txn(trans=date(2024, 6, 1), filed=date(2024, 6, 3))
    history = [
        (date(2021, 1, 5), 2021, 1),
        (date(2022, 6, 8), 2022, 6),
        (date(2023, 11, 4), 2023, 11),
    ]

    assert classify_purchase(purchase, owner_history=history) is CmpClass.OPPORTUNISTIC


def test_history_rows_from_transactions_group_by_owner() -> None:
    rows = history_rows_from_transactions(
        [
            txn(owner="a", trans=date(2021, 3, 1), filed=date(2021, 3, 3)),
            txn(owner="b", trans=date(2022, 4, 1), filed=date(2022, 4, 3)),
            txn(owner="a", trans=date(2022, 5, 1), filed=date(2022, 5, 3)),
        ]
    )

    assert set(rows) == {"a", "b"}
    assert rows["a"] == [
        (date(2021, 3, 3), 2021, 3),
        (date(2022, 5, 3), 2022, 5),
    ]


# --- Event construction ------------------------------------------------------


def test_build_events_aggregates_same_person_issuer_filing() -> None:
    history = {
        "owner-1": [
            (date(2021, 1, 5), 2021, 1),
            (date(2022, 6, 8), 2022, 6),
            (date(2023, 11, 4), 2023, 11),
        ]
    }
    purchases = [
        txn(owner="owner-1", shares="500", price="50", accession="x1"),  # $25k
        txn(owner="owner-1", shares="500", price="50", accession="x2"),  # $25k same filing
    ]

    events, counts = build_purchase_events(purchases, history_by_owner=history)

    assert len(events) == 1
    assert events[0].purchase_count == 2
    assert events[0].gross_value == Decimal("50000")
    assert events[0].cmp_class is CmpClass.OPPORTUNISTIC
    assert counts.opportunistic == 2
    assert counts.opportunistic_events == 1


def test_build_events_separates_routine_and_opportunistic() -> None:
    history = {
        "opp": [
            (date(2021, 1, 5), 2021, 1),
            (date(2022, 6, 8), 2022, 6),
            (date(2023, 11, 4), 2023, 11),
        ],
        "routine": [
            (date(2021, 3, 5), 2021, 3),
            (date(2022, 3, 8), 2022, 3),
            (date(2023, 3, 4), 2023, 3),
        ],
    }
    purchases = [
        txn(owner="opp", accession="o1"),
        txn(owner="routine", accession="r1"),
    ]

    events, counts = build_purchase_events(purchases, history_by_owner=history)

    assert counts.opportunistic == 1
    assert counts.routine == 1
    assert len(opportunistic_events(events)) == 1
    assert opportunistic_events(events)[0].owner_cik == "opp"


def test_unclassified_purchases_are_counted_not_primary() -> None:
    events, counts = build_purchase_events(
        [txn(owner="newbie")],
        history_by_owner={},
    )

    assert counts.unclassified == 1
    assert counts.opportunistic == 0
    assert opportunistic_events(events) == ()


# --- De-overlap --------------------------------------------------------------


def test_repeat_event_inside_horizon_is_dropped() -> None:
    first = _event(known=date(2024, 1, 2))
    second = _event(known=date(2024, 2, 1), owner="owner-2")  # same ticker

    kept = de_overlap_events([first, second])

    assert kept == (first,)


def test_repeat_event_after_horizon_closes_is_kept() -> None:
    first = _event(known=date(2024, 1, 2))
    # Calendar approx: 60 * 7/5 = 84 days
    second = _event(known=date(2024, 1, 2) + timedelta(days=85), owner="owner-2")

    kept = de_overlap_events([first, second])

    assert len(kept) == 2


def test_de_overlap_is_per_symbol() -> None:
    a = _event(symbol="AAA", known=date(2024, 1, 2))
    b = _event(symbol="BBB", known=date(2024, 1, 3))

    kept = de_overlap_events([a, b])

    assert len(kept) == 2


def test_partial_session_calendar_is_rejected() -> None:
    event = _event(known=date(2024, 1, 2))
    sessions = {"ACME": [date(2024, 6, 1), date(2024, 6, 2)]}

    with pytest.raises(ValueError, match="starts"):
        de_overlap_events([event], sessions_by_symbol=sessions)


def test_de_overlap_uses_session_calendar_when_given() -> None:
    start = date(2024, 1, 2)
    # 60 sessions after known-time
    calendar = [start + timedelta(days=i) for i in range(0, 120)]
    first = _event(known=start)
    # Day after the 60th future session closes the block
    future_sessions = [s for s in calendar if s > start]
    close = future_sessions[59]
    second = _event(known=close + timedelta(days=1), owner="owner-2")
    blocked = _event(known=close, owner="owner-3")

    kept = de_overlap_events(
        [first, blocked, second],
        sessions_by_symbol={"ACME": calendar},
    )

    assert kept == (first, second)


# --- Density / MDS -----------------------------------------------------------


def test_required_events_matches_cfo_density_floor_derivation() -> None:
    assert required_events() == 7246  # same (z σ / bar)^2 + 1 as CFOB
    assert PROTOCOL.min_events == 7500


def test_min_detectable_size_falls_as_events_accumulate() -> None:
    assert min_detectable_size(n_events=7500) < min_detectable_size(n_events=1000)


def test_year_shares_sum_to_one() -> None:
    events = [
        _event(known=date(2020, 1, 1), owner="a"),
        _event(known=date(2020, 2, 1), owner="b"),
        _event(known=date(2021, 1, 1), owner="c"),
    ]
    shares = year_shares(events)

    assert abs(sum(shares.values()) - 1.0) < 1e-12
    assert shares[2020] == pytest.approx(2 / 3)


# --- Stage C gates -----------------------------------------------------------


def test_c1_fails_closed_when_reconcile_unmeasured() -> None:
    gate = evaluate_c1_parse(
        archives_expected=10, archives_parsed=10, reconciled=None
    )

    assert gate.passed is False
    assert gate.id == "C1-parse"


def test_c1_fails_when_archives_incomplete() -> None:
    gate = evaluate_c1_parse(
        archives_expected=10, archives_parsed=9, reconciled=True
    )

    assert gate.passed is False


def test_c1_passes_when_parse_and_reconcile_ok() -> None:
    gate = evaluate_c1_parse(
        archives_expected=10, archives_parsed=10, reconciled=True
    )

    assert gate.passed is True


def test_c2_fails_below_ninety_percent_mapping() -> None:
    gate = evaluate_c2_map(mapped=89, total=100)

    assert gate.passed is False
    assert gate.id == "C2-map"


def test_c2_passes_at_ninety_percent() -> None:
    assert evaluate_c2_map(mapped=90, total=100).passed is True


def test_c3_requires_both_opportunistic_and_routine() -> None:
    empty_routine = ClassificationCounts(
        total_purchases=10, opportunistic=10, routine=0, unclassified=0
    )
    empty_opp = ClassificationCounts(
        total_purchases=10, opportunistic=0, routine=10, unclassified=0
    )
    both = ClassificationCounts(
        total_purchases=20,
        opportunistic=10,
        routine=8,
        unclassified=2,
        opportunistic_events=9,
        routine_events=7,
    )

    assert evaluate_c3_class(counts=empty_routine).passed is False
    assert evaluate_c3_class(counts=empty_opp).passed is False
    assert evaluate_c3_class(counts=both).passed is True


def test_c4_rejects_cluster_as_primary() -> None:
    gate = evaluate_c4_protocol(
        protocol_present=True, trial_ledger_present=True, primary_is_cluster=True
    )

    assert gate.passed is False
    assert "cluster" in gate.reason


def test_stage_c_passes_when_every_hard_gate_passes() -> None:
    counts = ClassificationCounts(
        total_purchases=100,
        opportunistic=60,
        routine=30,
        unclassified=10,
        opportunistic_events=55,
        routine_events=28,
    )
    report = evaluate_stage_c(
        archives_expected=10,
        archives_parsed=10,
        reconciled=True,
        mapped=95,
        total=100,
        counts=counts,
        protocol_present=True,
        trial_ledger_present=True,
    )

    assert report.all_hard_gates_passed is True
    assert report.verdict == Verdict.STAGE_PASS
    assert report.capital_go is False


def test_stage_c_fails_closed_on_unmeasured_reconcile() -> None:
    counts = ClassificationCounts(
        total_purchases=10, opportunistic=5, routine=5, unclassified=0
    )
    report = evaluate_stage_c(
        archives_expected=1,
        archives_parsed=1,
        reconciled=None,
        mapped=10,
        total=10,
        counts=counts,
        protocol_present=True,
        trial_ledger_present=True,
    )

    assert report.verdict == Verdict.KILL_LINE
    assert report.all_hard_gates_passed is False


# --- Stage D gates -----------------------------------------------------------


def test_d1_fails_below_event_floor() -> None:
    assert evaluate_d1_volume(de_overlapped_events=7499).passed is False


def test_d1_passes_at_floor() -> None:
    assert evaluate_d1_volume(de_overlapped_events=7500).passed is True


def test_d2_fails_when_too_few_years_contribute() -> None:
    shares = {year: 0.5 for year in range(2010, 2012)}  # 2 years only
    assert evaluate_d2_year_spread(shares=shares).passed is False


def test_d2_passes_with_broad_year_spread() -> None:
    shares = {year: 0.05 for year in range(2006, 2026)}  # 20 years × 5%
    assert evaluate_d2_year_spread(shares=shares).passed is True


def test_d3_fails_when_one_year_dominates() -> None:
    shares = {2020: 0.40, 2021: 0.30, 2022: 0.30}
    assert evaluate_d3_year_mass(shares=shares).passed is False


def test_d3_passes_at_twenty_five_percent_cap() -> None:
    shares = {2020: 0.25, 2021: 0.25, 2022: 0.25, 2023: 0.25}
    assert evaluate_d3_year_mass(shares=shares).passed is True


def test_d4_mds_fails_when_n_too_small() -> None:
    assert evaluate_d4_mds(de_overlapped_events=100).passed is False


def test_d4_mds_passes_at_density_floor() -> None:
    assert evaluate_d4_mds(de_overlapped_events=7500).passed is True


def test_empty_cohort_fails_stage_d_closed() -> None:
    report = evaluate_stage_d(de_overlapped_events=0, shares={})

    assert report.all_hard_gates_passed is False
    assert report.capital_go is False


def test_stage_d_power_only_fail_is_underpowered_stop() -> None:
    # Enough years but n below floor → power fail only
    shares = {year: 1 / 20 for year in range(2006, 2026)}
    report = evaluate_stage_d(de_overlapped_events=1000, shares=shares)

    assert report.verdict == Verdict.UNDERPOWERED_STOP
    assert report.capital_go is False


def test_stage_d_year_mass_fail_is_kill_line() -> None:
    shares = {2020: 0.90, 2021: 0.10}
    report = evaluate_stage_d(de_overlapped_events=10000, shares=shares)

    assert report.verdict == Verdict.KILL_LINE


def test_stage_d_never_grants_capital() -> None:
    shares = {year: 1 / 20 for year in range(2006, 2026)}
    report = evaluate_stage_d(de_overlapped_events=10000, shares=shares)

    assert report.verdict == Verdict.STAGE_PASS
    assert report.capital_go is False


# --- Combine / artifact / E1 auth --------------------------------------------


def test_combine_stage_reports_any_hard_fail_kills() -> None:
    counts = ClassificationCounts(
        total_purchases=10, opportunistic=5, routine=5, unclassified=0
    )
    c_ok = evaluate_stage_c(
        archives_expected=1,
        archives_parsed=1,
        reconciled=True,
        mapped=10,
        total=10,
        counts=counts,
        protocol_present=True,
        trial_ledger_present=True,
    )
    d_fail = evaluate_stage_d(de_overlapped_events=0, shares={})
    combined = combine_stage_reports(c_ok, d_fail)

    assert combined.all_hard_gates_passed is False
    assert combined.capital_go is False


def test_artifact_capital_go_always_false() -> None:
    counts = ClassificationCounts(
        total_purchases=10, opportunistic=5, routine=5, unclassified=0
    )
    report = evaluate_stage_c(
        archives_expected=1,
        archives_parsed=1,
        reconciled=True,
        mapped=10,
        total=10,
        counts=counts,
        protocol_present=True,
        trial_ledger_present=True,
    )
    artifact = build_cmp_artifact(
        stage="C+D",
        report=report,
        qualification_counts={"qualified": 10},
        classification=counts,
        raw_opportunistic_events=5,
        universe_eligible_events=4,
        de_overlapped_events=3,
        shares={2024: 1.0},
        mode="unit-test",
    )

    assert artifact["capital_go"] is False
    assert artifact["implementability_eligible"] is False
    assert artifact["protocol"]["cluster_object_primary"] is False
    assert artifact["protocol"]["cmp_primary_class"] == "opportunistic"


def test_e1_refused_without_flag() -> None:
    with pytest.raises(PermissionError, match="--e1"):
        require_e1_authorisation(e1_flag=False, human_go_recorded=True)


def test_e1_refused_without_human_go_record() -> None:
    with pytest.raises(PermissionError, match="human go"):
        require_e1_authorisation(e1_flag=True, human_go_recorded=False)


def test_e1_authorisation_gate_passes_only_with_both() -> None:
    denied = evaluate_stage_e1_authorisation(e1_flag=True, human_go_recorded=False)
    allowed = evaluate_stage_e1_authorisation(e1_flag=True, human_go_recorded=True)

    assert denied.passed is False
    assert allowed.passed is True
