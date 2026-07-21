"""Unit tests for CFOB Stage D / F0 pure helpers (PRD #76)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from invest.application.cfob import (
    PROTOCOL,
    ProtocolConfig,
    Verdict,
    build_cfob_artifact,
    build_clusters,
    de_overlap,
    dedupe_amendments,
    evaluate_d1_volume,
    evaluate_d2_year_spread,
    evaluate_d3_year_concentration,
    evaluate_f1_mapping_rate,
    evaluate_f2_unmapped_composition,
    evaluate_f3_reconcile,
    evaluate_stage_d,
    evaluate_stage_f0,
    min_detectable_size,
    qualifying_purchases,
    required_events,
    year_shares,
)
from invest.domain.models import InsiderTransaction


def txn(
    *,
    owner: str = "owner-1",
    symbol: str = "ACME",
    trans: date = date(2024, 3, 4),
    filed: date | None = None,
    code: str = "P",
    acquired: str = "A",
    shares: str = "1000",
    price: str = "50",
    direct: bool = True,
    document_type: str = "4",
    accession: str | None = None,
    late: bool = False,
) -> InsiderTransaction:
    filing_date = filed if filed is not None else trans + timedelta(days=2)
    return InsiderTransaction(
        accession_number=accession or f"{owner}-{trans:%Y%m%d}-{document_type}",
        issuer_cik="0000001",
        trading_symbol=symbol,
        owner_cik=owner,
        filing_date=filing_date,
        transaction_date=trans,
        transaction_code=code,
        acquired_disposed=acquired,
        shares=Decimal(shares),
        price_per_share=Decimal(price),
        direct_ownership=direct,
        document_type=document_type,
        original_submission_date=None,
        late_filing=late,
    )


# --- Qualification -----------------------------------------------------------


def test_keeps_code_p_acquisitions_clearing_the_size_floor() -> None:
    kept, counts = qualifying_purchases([txn()])

    assert len(kept) == 1
    assert counts.qualified == 1


def test_excludes_non_purchase_codes() -> None:
    kept, counts = qualifying_purchases([txn(code="S"), txn(code="A"), txn(code="M")])

    assert kept == ()
    assert counts.wrong_code == 3


def test_excludes_disposals_even_under_code_p() -> None:
    kept, counts = qualifying_purchases([txn(acquired="D")])

    assert kept == ()
    assert counts.disposals == 1


def test_excludes_purchases_below_the_ten_thousand_dollar_floor() -> None:
    kept, counts = qualifying_purchases([txn(shares="10", price="50")])

    assert kept == ()
    assert counts.below_size_floor == 1


def test_size_floor_is_inclusive_at_exactly_ten_thousand() -> None:
    kept, _ = qualifying_purchases([txn(shares="200", price="50")])

    assert len(kept) == 1


def test_excludes_purchases_filed_beyond_the_staleness_cap() -> None:
    stale = txn(trans=date(2024, 3, 4), filed=date(2024, 3, 20))

    kept, counts = qualifying_purchases([stale])

    assert kept == ()
    assert counts.stale == 1


def test_staleness_cap_is_inclusive_at_ten_days() -> None:
    kept, _ = qualifying_purchases([txn(trans=date(2024, 3, 4), filed=date(2024, 3, 14))])

    assert len(kept) == 1


def test_excludes_filings_dated_before_their_transaction() -> None:
    kept, counts = qualifying_purchases(
        [txn(trans=date(2024, 3, 4), filed=date(2024, 3, 1))]
    )

    assert kept == ()
    assert counts.stale == 1


def test_indirect_ownership_qualifies_but_is_counted() -> None:
    kept, counts = qualifying_purchases([txn(direct=False)])

    assert len(kept) == 1
    assert counts.indirect_ownership == 1


def test_late_filings_qualify_but_are_counted() -> None:
    kept, counts = qualifying_purchases([txn(late=True)])

    assert len(kept) == 1
    assert counts.late_filed == 1


# --- Amendments --------------------------------------------------------------


def test_amendment_supersedes_the_original_trade() -> None:
    original = txn(accession="a-1", document_type="4", filed=date(2024, 3, 6))
    amendment = txn(accession="a-2", document_type="4/A", filed=date(2024, 3, 9))

    deduped, superseded = dedupe_amendments([original, amendment])

    assert superseded == 1
    assert len(deduped) == 1
    assert deduped[0].is_amendment is True


def test_amendment_keeps_the_original_filing_date_as_known_time() -> None:
    original = txn(accession="a-1", document_type="4", filed=date(2024, 3, 6))
    amendment = txn(accession="a-2", document_type="4/A", filed=date(2024, 3, 9))

    deduped, _ = dedupe_amendments([original, amendment])

    assert deduped[0].filing_date == date(2024, 3, 6)


def test_distinct_trades_are_not_treated_as_amendments() -> None:
    deduped, superseded = dedupe_amendments(
        [txn(owner="owner-1"), txn(owner="owner-2")]
    )

    assert superseded == 0
    assert len(deduped) == 2


# --- Cluster construction ----------------------------------------------------


def test_two_insiders_inside_the_window_form_a_cluster() -> None:
    purchases = [
        txn(owner="owner-1", trans=date(2024, 3, 4)),
        txn(owner="owner-2", trans=date(2024, 3, 20)),
    ]

    clusters = build_clusters(purchases)

    assert len(clusters) == 1
    assert clusters[0].distinct_insiders == 2


def test_one_insider_buying_repeatedly_is_not_a_cluster() -> None:
    purchases = [
        txn(owner="owner-1", trans=date(2024, 3, 4)),
        txn(owner="owner-1", trans=date(2024, 3, 10)),
        txn(owner="owner-1", trans=date(2024, 3, 15)),
    ]

    assert build_clusters(purchases) == ()


def test_insiders_beyond_the_window_do_not_cluster() -> None:
    purchases = [
        txn(owner="owner-1", trans=date(2024, 3, 4)),
        txn(owner="owner-2", trans=date(2024, 5, 1)),
    ]

    assert build_clusters(purchases) == ()


def test_insiders_at_different_issuers_do_not_cluster() -> None:
    purchases = [
        txn(owner="owner-1", symbol="ACME", trans=date(2024, 3, 4)),
        txn(owner="owner-2", symbol="OTHER", trans=date(2024, 3, 6)),
    ]

    assert build_clusters(purchases) == ()


def test_cluster_known_time_is_the_latest_filing_date() -> None:
    purchases = [
        txn(owner="owner-1", trans=date(2024, 3, 4), filed=date(2024, 3, 6)),
        txn(owner="owner-2", trans=date(2024, 3, 5), filed=date(2024, 3, 12)),
    ]

    clusters = build_clusters(purchases)

    assert clusters[0].known_time == date(2024, 3, 12)


def test_cluster_aggregates_value_and_purchase_count() -> None:
    purchases = [
        txn(owner="owner-1", shares="1000", price="50"),
        txn(owner="owner-2", shares="200", price="50"),
    ]

    cluster = build_clusters(purchases)[0]

    assert cluster.purchase_count == 2
    assert cluster.gross_value == Decimal("60000")


def test_secondary_sixty_day_window_is_available_without_retuning_the_default() -> None:
    purchases = [
        txn(owner="owner-1", trans=date(2024, 3, 4)),
        txn(owner="owner-2", trans=date(2024, 4, 15)),
    ]

    assert build_clusters(purchases) == ()
    assert len(build_clusters(purchases, window_days=60)) == 1


# --- De-overlap --------------------------------------------------------------


def test_repeat_cluster_inside_the_horizon_is_dropped() -> None:
    # Two genuinely separate clusters (58 days apart, so outside the 30-day
    # trade window) but inside the h60 measurement horizon.
    purchases = [
        txn(owner="owner-1", trans=date(2024, 1, 2)),
        txn(owner="owner-2", trans=date(2024, 1, 3)),
        txn(owner="owner-3", trans=date(2024, 3, 1)),
        txn(owner="owner-4", trans=date(2024, 3, 2)),
    ]
    clusters = build_clusters(purchases)
    assert len(clusters) == 2

    assert len(de_overlap(clusters)) == 1


def test_repeat_cluster_after_the_horizon_closes_is_kept() -> None:
    purchases = [
        txn(owner="owner-1", trans=date(2024, 1, 2)),
        txn(owner="owner-2", trans=date(2024, 1, 3)),
        txn(owner="owner-3", trans=date(2024, 9, 2)),
        txn(owner="owner-4", trans=date(2024, 9, 3)),
    ]

    assert len(de_overlap(build_clusters(purchases))) == 2


def test_de_overlap_is_per_symbol() -> None:
    purchases = [
        txn(owner="owner-1", symbol="ACME", trans=date(2024, 1, 2)),
        txn(owner="owner-2", symbol="ACME", trans=date(2024, 1, 3)),
        txn(owner="owner-3", symbol="OTHER", trans=date(2024, 1, 2)),
        txn(owner="owner-4", symbol="OTHER", trans=date(2024, 1, 3)),
    ]

    assert len(de_overlap(build_clusters(purchases))) == 2


def test_de_overlap_uses_the_session_calendar_when_given_one() -> None:
    purchases = [
        txn(owner="owner-1", trans=date(2024, 1, 2)),
        txn(owner="owner-2", trans=date(2024, 1, 3)),
        txn(owner="owner-3", trans=date(2024, 3, 1)),
        txn(owner="owner-4", trans=date(2024, 3, 2)),
    ]
    clusters = build_clusters(purchases)
    sessions = [date(2024, 1, 1) + timedelta(days=offset) for offset in range(400)]

    # A 2-session horizon closes long before the March cluster, so both survive
    # — where the calendar-day approximation would have blocked the second.
    kept = de_overlap(clusters, horizon_sessions=2, sessions_by_symbol={"ACME": sessions})

    assert len(kept) == 2


# --- Power -------------------------------------------------------------------


def test_required_events_matches_the_grilled_density_floor() -> None:
    assert 7000 <= required_events() <= 8000
    assert PROTOCOL.min_clusters >= 7000


def test_min_detectable_size_falls_as_events_accumulate() -> None:
    assert min_detectable_size(n_events=1000) > min_detectable_size(n_events=10_000)


def test_min_detectable_size_is_infinite_without_events() -> None:
    assert min_detectable_size(n_events=0) == float("inf")


def test_measured_dispersion_reproduces_the_gate_1a_calibration() -> None:
    # Gate-1a: mean +1.89% at clustered t=5.3 on n=11,489 implies sigma ~= 0.38.
    assert abs(PROTOCOL.excess_dispersion - 0.38) < 0.01


# --- Stage D gates -----------------------------------------------------------


def test_year_shares_sum_to_one() -> None:
    purchases = [
        txn(owner="owner-1", trans=date(2024, 3, 4)),
        txn(owner="owner-2", trans=date(2024, 3, 5)),
        txn(owner="owner-3", symbol="OTHER", trans=date(2023, 3, 4)),
        txn(owner="owner-4", symbol="OTHER", trans=date(2023, 3, 5)),
    ]

    shares = year_shares(build_clusters(purchases))

    assert abs(sum(shares.values()) - 1.0) < 1e-9


def test_d1_fails_below_the_cluster_floor() -> None:
    assert evaluate_d1_volume(de_overlapped_clusters=100).passed is False


def test_d1_passes_at_the_floor() -> None:
    assert evaluate_d1_volume(de_overlapped_clusters=PROTOCOL.min_clusters).passed is True


def test_d2_fails_when_too_few_years_contribute() -> None:
    shares = {2020: 0.5, 2021: 0.5}

    assert evaluate_d2_year_spread(shares=shares).passed is False


def test_d2_passes_with_a_broad_year_spread() -> None:
    shares = {year: 1 / 15 for year in range(2010, 2025)}

    assert evaluate_d2_year_spread(shares=shares).passed is True


def test_d3_fails_when_one_year_dominates() -> None:
    shares = {2020: 0.4, 2021: 0.3, 2022: 0.3}

    assert evaluate_d3_year_concentration(shares=shares).passed is False


def test_empty_cohort_fails_stage_d_closed() -> None:
    report = evaluate_stage_d(de_overlapped_clusters=0, shares={})

    assert report.all_hard_gates_passed is False
    assert report.verdict == str(Verdict.KILL_LINE)


def test_stage_d_passes_only_when_every_hard_gate_passes() -> None:
    shares = {year: 1 / 15 for year in range(2010, 2025)}

    report = evaluate_stage_d(de_overlapped_clusters=PROTOCOL.min_clusters, shares=shares)

    assert report.all_hard_gates_passed is True
    assert report.verdict == str(Verdict.STAGE_PASS)


def test_stage_d_never_grants_capital() -> None:
    shares = {year: 1 / 15 for year in range(2010, 2025)}

    report = evaluate_stage_d(de_overlapped_clusters=PROTOCOL.min_clusters, shares=shares)

    assert report.capital_go is False


# --- Stage F0 gates ----------------------------------------------------------


def test_mapping_gate_fails_below_ninety_percent() -> None:
    assert evaluate_f1_mapping_rate(mapped=80, total=100).passed is False


def test_mapping_gate_passes_at_ninety_percent() -> None:
    assert evaluate_f1_mapping_rate(mapped=90, total=100).passed is True


def test_mapping_gate_fails_closed_without_any_purchases() -> None:
    assert evaluate_f1_mapping_rate(mapped=0, total=0).passed is False


def test_unmapped_composition_fails_when_failures_concentrate_in_one_year() -> None:
    result = evaluate_f2_unmapped_composition(
        unmapped_by_year={2008: 90, 2009: 10},
        total_by_year={2008: 100, 2009: 1000},
    )

    assert result.passed is False


def test_unmapped_composition_passes_when_failures_spread_evenly() -> None:
    result = evaluate_f2_unmapped_composition(
        unmapped_by_year={year: 10 for year in range(2010, 2020)},
        total_by_year={year: 1000 for year in range(2010, 2020)},
    )

    assert result.passed is True


def test_a_small_unmapped_set_does_not_fail_merely_for_being_small() -> None:
    result = evaluate_f2_unmapped_composition(
        unmapped_by_year={2010: 2, 2011: 3},
        total_by_year={2010: 1000, 2011: 1000},
    )

    assert result.passed is True


def test_unmapped_composition_fails_closed_without_year_totals() -> None:
    result = evaluate_f2_unmapped_composition(unmapped_by_year={2010: 5}, total_by_year={})

    assert result.passed is False


def test_unreconciled_counts_fail_closed() -> None:
    assert evaluate_f3_reconcile(reconciled=None).passed is False


def test_stage_f0_requires_every_hard_gate() -> None:
    report = evaluate_stage_f0(
        protocol_present=True,
        trial_ledger_present=True,
        mapped=95,
        total=100,
        unmapped_by_year={2010: 2, 2011: 3},
        total_by_year={2010: 1000, 2011: 1000},
        reconciled=True,
    )

    assert report.all_hard_gates_passed is True
    assert report.capital_go is False


def test_stage_f0_fails_closed_on_an_unmeasured_reconcile() -> None:
    report = evaluate_stage_f0(
        protocol_present=True,
        trial_ledger_present=True,
        mapped=95,
        total=100,
        unmapped_by_year={},
        total_by_year={2010: 1000},
        reconciled=None,
    )

    assert report.verdict == str(Verdict.KILL_LINE)


# --- Artifact ----------------------------------------------------------------


def test_artifact_records_the_frozen_protocol_and_denies_capital() -> None:
    shares = {year: 1 / 15 for year in range(2010, 2025)}
    report = evaluate_stage_d(de_overlapped_clusters=PROTOCOL.min_clusters, shares=shares)
    _, counts = qualifying_purchases([txn()])

    artifact = build_cfob_artifact(
        stage="D",
        report=report,
        counts=counts,
        raw_clusters=9000,
        de_overlapped_clusters=PROTOCOL.min_clusters,
        shares=shares,
        mode="test",
    )

    assert artifact["capital_go"] is False
    assert artifact["implementability_eligible"] is False
    assert artifact["protocol"]["entry_rule"] == "next_open_after_filing_date"
    assert artifact["protocol"]["known_time_axis"] == "filing_date_day_granular"
    assert artifact["clusters"]["de_overlapped"] == PROTOCOL.min_clusters


def test_artifact_reports_raw_and_de_overlapped_counts_separately() -> None:
    report = evaluate_stage_d(de_overlapped_clusters=10, shares={2020: 1.0})

    artifact = build_cfob_artifact(
        stage="D",
        report=report,
        counts=qualifying_purchases([txn()])[1],
        raw_clusters=25,
        de_overlapped_clusters=10,
        shares={2020: 1.0},
        mode="test",
    )

    assert artifact["clusters"]["raw"] == 25
    assert artifact["clusters"]["de_overlapped"] == 10


def test_custom_protocol_does_not_mutate_the_frozen_default() -> None:
    relaxed = ProtocolConfig(min_clusters=10)

    assert evaluate_d1_volume(de_overlapped_clusters=10, config=relaxed).passed is True
    assert evaluate_d1_volume(de_overlapped_clusters=10).passed is False
