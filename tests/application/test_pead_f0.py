"""R2-2 PEAD F0: pure data-feasibility gates D0–D7 (no returns)."""

from __future__ import annotations

import pytest

from invest.application.pead_f0 import (
    PROTOCOL,
    KnownTimePolicy,
    PeadF0Evidence,
    build_pead_f0_artifact,
    evaluate_d0_protocol,
    evaluate_d1_original_eps,
    evaluate_d2_original_revenue,
    evaluate_d3_known_time,
    evaluate_d4_integrity,
    evaluate_d5_mapping_terminals,
    evaluate_d6_fold_floors,
    evaluate_d7_reconcile,
    evaluate_pead_f0_gates,
    passing_evidence,
)


def test_protocol_freezes_f0_knobs() -> None:
    assert PROTOCOL.signal_family == "revenue_confirmed_gaap_earnings_surprise"
    assert PROTOCOL.eps_field == "diluted_gaap_eps"
    assert PROTOCOL.revenue_field == "gaap_revenue"
    assert PROTOCOL.min_prior_seasonal_changes == 8
    assert PROTOCOL.min_annual_test_folds == 10
    assert PROTOCOL.capital_go is False
    assert PROTOCOL.analyst_sue_fallback is False
    # Future E1 freezes recorded, not measured in F0
    assert PROTOCOL.future_primary_horizon_sessions == 60
    assert PROTOCOL.future_entry == "next_open"
    assert PROTOCOL.future_primary_min_adv == 10_000_000.0
    assert PROTOCOL.future_accept_cost_bps == 5.0


def test_d0_fails_when_protocol_or_ledger_missing() -> None:
    g = evaluate_d0_protocol(protocol_present=False, trial_ledger_present=True)
    assert g.id == "D0"
    assert g.passed is False
    g2 = evaluate_d0_protocol(protocol_present=True, trial_ledger_present=False)
    assert g2.passed is False
    g3 = evaluate_d0_protocol(protocol_present=True, trial_ledger_present=True)
    assert g3.passed is True


def test_d1_d2_original_as_published() -> None:
    assert evaluate_d1_original_eps(reconstructable=True).passed is True
    assert evaluate_d1_original_eps(reconstructable=False).passed is False
    assert evaluate_d1_original_eps(reconstructable=None).passed is False  # fail closed
    assert evaluate_d2_original_revenue(reconstructable=True).passed is True
    assert evaluate_d2_original_revenue(reconstructable=None).passed is False


def test_d3_known_time_policy() -> None:
    # Exact proven
    g = evaluate_d3_known_time(
        exact_known_time_proven=True,
        policy=KnownTimePolicy.EXACT_TIMESTAMP,
        policy_applied_consistently=True,
    )
    assert g.passed is True
    # Conservative second-open when exact unavailable
    g2 = evaluate_d3_known_time(
        exact_known_time_proven=False,
        policy=KnownTimePolicy.SECOND_OPEN_DATE_ONLY,
        policy_applied_consistently=True,
    )
    assert g2.passed is True
    # Exact claimed but not proven → fail
    g3 = evaluate_d3_known_time(
        exact_known_time_proven=False,
        policy=KnownTimePolicy.EXACT_TIMESTAMP,
        policy_applied_consistently=True,
    )
    assert g3.passed is False
    # Policy not applied consistently → fail
    g4 = evaluate_d3_known_time(
        exact_known_time_proven=True,
        policy=KnownTimePolicy.EXACT_TIMESTAMP,
        policy_applied_consistently=False,
    )
    assert g4.passed is False
    # None consistency → fail closed
    g5 = evaluate_d3_known_time(
        exact_known_time_proven=True,
        policy=KnownTimePolicy.EXACT_TIMESTAMP,
        policy_applied_consistently=None,
    )
    assert g5.passed is False


def test_d4_integrity_any_leak_fails() -> None:
    assert (
        evaluate_d4_integrity(
            lookahead_detected=False,
            current_id_leakage=False,
            silent_unit_change=False,
            amendment_rewrite=False,
        ).passed
        is True
    )
    assert (
        evaluate_d4_integrity(
            lookahead_detected=True,
            current_id_leakage=False,
            silent_unit_change=False,
            amendment_rewrite=False,
        ).passed
        is False
    )
    assert (
        evaluate_d4_integrity(
            lookahead_detected=False,
            current_id_leakage=False,
            silent_unit_change=False,
            amendment_rewrite=True,
        ).passed
        is False
    )
    # Not measured → fail closed
    assert (
        evaluate_d4_integrity(
            lookahead_detected=None,
            current_id_leakage=False,
            silent_unit_change=False,
            amendment_rewrite=False,
        ).passed
        is False
    )


def test_d5_mapping_and_terminals() -> None:
    assert (
        evaluate_d5_mapping_terminals(
            period_valid_mapping=True,
            terminal_economics_complete=True,
        ).passed
        is True
    )
    assert (
        evaluate_d5_mapping_terminals(
            period_valid_mapping=False,
            terminal_economics_complete=True,
        ).passed
        is False
    )
    assert (
        evaluate_d5_mapping_terminals(
            period_valid_mapping=True,
            terminal_economics_complete=None,
        ).passed
        is False
    )


def test_d6_fold_floors() -> None:
    assert (
        evaluate_d6_fold_floors(
            max_prior_seasonal_changes=8,
            annual_test_folds=10,
        ).passed
        is True
    )
    assert (
        evaluate_d6_fold_floors(
            max_prior_seasonal_changes=7,
            annual_test_folds=10,
        ).passed
        is False
    )
    assert (
        evaluate_d6_fold_floors(
            max_prior_seasonal_changes=8,
            annual_test_folds=9,
        ).passed
        is False
    )
    assert (
        evaluate_d6_fold_floors(
            max_prior_seasonal_changes=None,
            annual_test_folds=10,
        ).passed
        is False
    )


def test_d7_reconcile_fail_closed() -> None:
    assert evaluate_d7_reconcile(reconcile_pass=True).passed is True
    assert evaluate_d7_reconcile(reconcile_pass=False).passed is False
    assert evaluate_d7_reconcile(reconcile_pass=None).passed is False


def test_full_pass_evidence_is_f2_tape_eligible() -> None:
    ev = passing_evidence()
    report = evaluate_pead_f0_gates(ev)
    assert report.all_hard_gates_passed is True
    assert report.f2_tape_eligible is True
    assert report.capital_go is False
    assert report.verdict == "f2_tape_eligible"
    assert len(report.gates) == 8
    assert {g.id for g in report.gates} == {
        "D0",
        "D1",
        "D2",
        "D3",
        "D4",
        "D5",
        "D6",
        "D7",
    }


def test_any_hard_fail_is_kill_line() -> None:
    ev = passing_evidence()
    # mutate via replace-style: build partial fail
    bad = PeadF0Evidence(
        protocol_present=ev.protocol_present,
        trial_ledger_present=ev.trial_ledger_present,
        original_eps_reconstructable=False,
        original_revenue_reconstructable=ev.original_revenue_reconstructable,
        exact_known_time_proven=ev.exact_known_time_proven,
        known_time_policy=ev.known_time_policy,
        known_time_policy_applied_consistently=ev.known_time_policy_applied_consistently,
        lookahead_detected=ev.lookahead_detected,
        current_id_leakage=ev.current_id_leakage,
        silent_unit_change=ev.silent_unit_change,
        amendment_rewrite=ev.amendment_rewrite,
        period_valid_mapping=ev.period_valid_mapping,
        terminal_economics_complete=ev.terminal_economics_complete,
        max_prior_seasonal_changes=ev.max_prior_seasonal_changes,
        annual_test_folds=ev.annual_test_folds,
        reconcile_pass=ev.reconcile_pass,
        coverage_included=ev.coverage_included,
        coverage_rejected=ev.coverage_rejected,
        source_label=ev.source_label,
    )
    report = evaluate_pead_f0_gates(bad)
    assert report.f2_tape_eligible is False
    assert report.capital_go is False
    assert report.verdict == "kill_line"
    d1 = next(g for g in report.gates if g.id == "D1")
    assert d1.passed is False


def test_missing_measurements_fail_closed_kill_line() -> None:
    """Empty / unmeasured evidence must never silent-GO."""
    empty = PeadF0Evidence()
    report = evaluate_pead_f0_gates(empty)
    assert report.verdict == "kill_line"
    assert report.f2_tape_eligible is False
    assert report.capital_go is False
    # At least D1–D7 should hard-fail when None
    hard_fails = [g for g in report.gates if g.severity == "hard" and not g.passed]
    assert len(hard_fails) >= 5


def test_build_pead_f0_artifact_json_friendly() -> None:
    ev = passing_evidence()
    report = evaluate_pead_f0_gates(ev)
    art = build_pead_f0_artifact(evidence=ev, gate_report=report)
    assert art["experiment"] == "r2-2-pead-f0"
    assert art["line"] == "pead-revenue-confirmed"
    assert art["capital_go"] is False
    assert art["pass_meaning"] == "f2_tape_eligible_only"
    assert art["residual_claim"] == "hard_frozen"
    assert art["returns_measured"] is False
    assert art["gates"]["verdict"] == "f2_tape_eligible"
    assert "protocol" in art
    assert art["protocol"]["min_annual_test_folds"] == 10
    assert art["known_time_policy"] == KnownTimePolicy.SECOND_OPEN_DATE_ONLY.value or art[
        "known_time_policy"
    ] in {p.value for p in KnownTimePolicy}
    assert "coverage" in art
    assert art["coverage"]["included"] == ev.coverage_included
    assert art["e1_status"] == "not_started"
    # Serialize-ish: no non-JSON types at top level leaves
    import json

    json.dumps(art)


def test_artifact_kill_line_never_sets_capital_go() -> None:
    report = evaluate_pead_f0_gates(PeadF0Evidence())
    art = build_pead_f0_artifact(evidence=PeadF0Evidence(), gate_report=report)
    assert art["capital_go"] is False
    assert art["gates"]["verdict"] == "kill_line"
    assert art["gates"]["f2_tape_eligible"] is False
