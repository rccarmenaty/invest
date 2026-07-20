"""R2-1 xs-reversal-lp: pure CS reverse helpers and frozen gates G0–G8."""

import math
import random
from datetime import date

import pytest

from invest.application.event_study_excess import summarize
from invest.application.xs_reversal import (
    PROTOCOL,
    NameFormationRow,
    XsGateResult,
    assign_decile,
    assign_deciles,
    bottom_minus_top_spread,
    cost_net_spread,
    cross_section_log_adv_ranks,
    evaluate_g0_placebo,
    evaluate_g0_synthetic_migration,
    evaluate_g1,
    evaluate_g2,
    evaluate_g3,
    evaluate_g4,
    evaluate_g5,
    evaluate_g6,
    evaluate_g7,
    evaluate_g8,
    evaluate_r21_gates,
    execution_entry_index,
    formation_close_to_close_return,
    gross_scale,
    is_liquid,
    iso_week_formation_dates,
    max_period_share,
    open_to_open_return,
    residualize_cross_section,
    residualized_decile_spread,
    signal_shuffle_placebo_spread,
    year_month_profit_shares,
)


def _all_pass_kwargs(stats, **overrides):
    base = dict(
        g0_placebo_t_abs=0.5,
        g0_deciles_changed=False,
        spread_stats=stats,
        positive_annual_folds=6,
        total_annual_folds=7,
        max_year_share=0.15,
        max_month_share=0.10,
        abs_rho=0.1,
        alpha=0.01,
        alpha_ci_excludes_zero=True,
        unscaled_clustered_t=2.5,
        tail_within_limits=True,
        net_at_10bps=0.01,
        net_at_5bps_primary_tier=0.02,
        deflated_sharpe=0.2,
        buffering_modeled=True,
    )
    base.update(overrides)
    return base


def test_protocol_freezes_primary_knobs() -> None:
    assert PROTOCOL.formation_sessions == 5
    assert PROTOCOL.hold_sessions == 5
    assert PROTOCOL.skip_sessions == 1
    assert PROTOCOL.deciles == 10
    assert PROTOCOL.primary_min_price == 5.0
    assert PROTOCOL.primary_min_adv == 10_000_000.0
    assert PROTOCOL.diagnostic_min_adv == 1_000_000.0
    assert PROTOCOL.g1_min_t == 3.0
    assert PROTOCOL.g5_min_t == 2.0
    assert PROTOCOL.year_share_max == pytest.approx(0.25)
    assert PROTOCOL.month_share_max == pytest.approx(0.20)
    assert PROTOCOL.accept_cost_bps == 10.0
    assert PROTOCOL.g4_max_abs_rho == pytest.approx(0.3)


def test_iso_week_formation_dates_are_last_session_of_each_iso_week() -> None:
    # Mon 6 Jan 2020 week → sessions Tue–Fri; last is Fri 10 Jan
    sessions = [
        date(2020, 1, 6),
        date(2020, 1, 7),
        date(2020, 1, 8),
        date(2020, 1, 9),
        date(2020, 1, 10),
        date(2020, 1, 13),
        date(2020, 1, 14),
        date(2020, 1, 15),
    ]
    assert iso_week_formation_dates(sessions) == [
        date(2020, 1, 10),
        date(2020, 1, 15),
    ]


def test_formation_close_to_close_return_uses_t_minus_4_to_t() -> None:
    # indices 0..4: close path 100 → 110 over four steps from idx 0 to 4
    closes = [100.0, 102.0, 101.0, 105.0, 110.0, 111.0]
    ret = formation_close_to_close_return(closes, formation_index=4)
    assert ret == pytest.approx(110.0 / 100.0 - 1.0)
    assert formation_close_to_close_return(closes, formation_index=3) is None  # need 4 lag


def test_execution_entry_index_skips_one_session() -> None:
    # formation at i=10 → skip t+1 → entry open at i+2
    assert execution_entry_index(10, skip_sessions=1) == 12


def test_open_to_open_return_over_hold() -> None:
    opens = [10.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0]
    # entry at index 2 (11), hold 5 → exit open index 7 (16)
    assert open_to_open_return(opens, entry_index=2, hold_sessions=5) == pytest.approx(
        16.0 / 11.0 - 1.0
    )
    assert open_to_open_return(opens, entry_index=4, hold_sessions=5) is None


def test_residualize_cross_section_removes_linear_predictors() -> None:
    # y = 1 + 2*beta + 3*rank + noise; noise orthogonal-ish small
    betas = [0.0, 1.0, 2.0, 3.0, 4.0]
    ranks = [0.0, 0.0, 1.0, 1.0, 2.0]
    y = [1.0 + 2.0 * b + 3.0 * r for b, r in zip(betas, ranks, strict=True)]
    resid = residualize_cross_section(y, beta=betas, log_adv_rank=ranks)
    assert len(resid) == 5
    assert all(abs(e) < 1e-9 for e in resid)


def test_assign_decile_lowest_is_one_highest_is_ten() -> None:
    scores = list(range(20))  # 0..19
    # lowest score → decile 1; highest → 10
    assert assign_decile(0, scores) == 1
    assert assign_decile(19, scores) == 10
    mids = assign_deciles(scores)
    assert min(mids) == 1 and max(mids) == 10
    assert len(set(mids)) == 10


def test_assign_deciles_one_pass_matches_per_score() -> None:
    scores = [3.0, 1.0, 4.0, 2.0, 0.0, 9.0, 8.0, 7.0, 6.0, 5.0]
    bulk = assign_deciles(scores)
    for i, s in enumerate(scores):
        assert bulk[i] == assign_decile(s, scores)


def test_bottom_minus_top_spread_is_mean_d1_minus_mean_d10() -> None:
    d1 = [0.02, 0.04]
    d10 = [-0.01, -0.03]
    assert bottom_minus_top_spread(d1, d10) == pytest.approx(0.03 - (-0.02))


def test_is_liquid_primary_and_diagnostic_tiers() -> None:
    assert is_liquid(price=5.0, median_adv=10_000_000.0, tier="primary") is True
    assert is_liquid(price=4.99, median_adv=10_000_000.0, tier="primary") is False
    assert is_liquid(price=5.0, median_adv=9_999_999.0, tier="primary") is False
    assert is_liquid(price=5.0, median_adv=1_000_000.0, tier="diagnostic") is True
    assert is_liquid(price=5.0, median_adv=999_999.0, tier="diagnostic") is False


def test_g0_placebo_requires_abs_t_below_two() -> None:
    ok = evaluate_g0_placebo(clustered_t_abs=1.5)
    bad = evaluate_g0_placebo(clustered_t_abs=2.0)
    assert ok.passed is True
    assert bad.passed is False
    assert "placebo" in bad.reason


def test_g0_synthetic_migration_fails_when_deciles_change() -> None:
    ok = evaluate_g0_synthetic_migration(deciles_changed=False)
    bad = evaluate_g0_synthetic_migration(deciles_changed=True)
    assert ok.passed is True
    assert bad.passed is False


def test_g0_synthetic_unmeasured_fails_closed() -> None:
    r = evaluate_g0_synthetic_migration(deciles_changed=None)
    assert r.passed is False
    assert "not measured" in r.reason


def test_g1_requires_positive_mean_and_t_at_least_3() -> None:
    # Build SummaryStats via summarize with large same-sign values, one cluster each
    # mean=0.05, high t
    values = [0.05] * 30
    clusters = [f"d{i}" for i in range(30)]
    stats = summarize(values, clusters)
    assert evaluate_g1(stats).passed is True

    neg = summarize([-0.01] * 10, [str(i) for i in range(10)])
    assert evaluate_g1(neg).passed is False
    assert "mean" in evaluate_g1(neg).reason


def test_g2_requires_positive_median() -> None:
    # mean positive but median negative: [ -1, -1, 10 ]
    stats = summarize([-1.0, -1.0, 10.0], ["a", "b", "c"])
    assert stats.mean > 0
    assert stats.median is not None and stats.median < 0
    assert evaluate_g2(stats).passed is False

    good = summarize([0.1, 0.2, 0.15], ["a", "b", "c"])
    assert evaluate_g2(good).passed is True


def test_g3_year_month_and_fold_majority() -> None:
    # 7 years, 6 positive folds, year share 0.2, month share 0.1
    r = evaluate_g3(
        positive_annual_folds=6,
        total_annual_folds=7,
        max_year_share=0.20,
        max_month_share=0.10,
    )
    assert r.passed is True
    bad_year = evaluate_g3(
        positive_annual_folds=6,
        total_annual_folds=7,
        max_year_share=0.30,
        max_month_share=0.10,
    )
    assert bad_year.passed is False
    bad_folds = evaluate_g3(
        positive_annual_folds=3,
        total_annual_folds=7,
        max_year_share=0.10,
        max_month_share=0.10,
    )
    assert bad_folds.passed is False


def test_g4_market_neutrality() -> None:
    assert evaluate_g4(abs_rho=0.2, alpha=0.01, alpha_ci_excludes_zero=True).passed
    assert evaluate_g4(abs_rho=0.4, alpha=0.01, alpha_ci_excludes_zero=True).passed is False
    assert evaluate_g4(abs_rho=0.2, alpha=0.01, alpha_ci_excludes_zero=False).passed is False


def test_g5_unscaled_survival() -> None:
    assert evaluate_g5(unscaled_clustered_t=2.5).passed is True
    assert evaluate_g5(unscaled_clustered_t=1.9).passed is False


def test_g6_tail_escalates_not_silent_go() -> None:
    ok = evaluate_g6(within_limits=True)
    assert ok.passed is True
    assert ok.severity == "info"
    esc = evaluate_g6(within_limits=False)
    assert esc.passed is False
    assert esc.severity == "escalate"


def test_g6_unmeasured_fails_closed() -> None:
    r = evaluate_g6(within_limits=None)
    assert r.passed is False
    assert r.severity == "escalate"
    assert "not measured" in r.reason


def test_g7_cost_survival_requires_buffering_modeled() -> None:
    # Without buffering model: hard fail even if mean nets look positive
    bare = evaluate_g7(net_at_10bps=0.01, net_at_5bps_primary_tier=0.02)
    assert bare.passed is False
    assert "buffering" in bare.reason

    assert evaluate_g7(
        net_at_10bps=0.01, net_at_5bps_primary_tier=0.02, buffering_modeled=True
    ).passed is True
    assert evaluate_g7(
        net_at_10bps=-0.001, net_at_5bps_primary_tier=0.02, buffering_modeled=True
    ).passed is False
    assert evaluate_g7(
        net_at_10bps=0.01, net_at_5bps_primary_tier=-0.001, buffering_modeled=True
    ).passed is False


def test_g8_deflated_sharpe() -> None:
    assert evaluate_g8(deflated_sharpe=0.1).passed is True
    assert evaluate_g8(deflated_sharpe=0.0).passed is False


def test_cost_net_spread_subtracts_round_trip_bps() -> None:
    # 10 bps/side = 20 bps round trip on notional per leg pair ≈ 0.002 absolute on return
    assert cost_net_spread(gross=0.01, bps_per_side=10.0) == pytest.approx(0.01 - 0.002)


def test_gross_scale_clips_vol_proportional_primary() -> None:
    # primary: realized/target clipped 0.5..1.5
    assert gross_scale(realized_vol=0.30, target_vol=0.20, mode="primary") == pytest.approx(
        1.5
    )
    assert gross_scale(realized_vol=0.05, target_vol=0.20, mode="primary") == pytest.approx(
        0.5
    )
    assert gross_scale(realized_vol=0.20, target_vol=0.20, mode="primary") == pytest.approx(
        1.0
    )
    # inverse ablation: target/realized
    assert gross_scale(realized_vol=0.40, target_vol=0.20, mode="inverse") == pytest.approx(
        0.5
    )


def test_max_period_share_and_year_month_helpers() -> None:
    pnls = {2019: 10.0, 2020: 90.0, 2021: 0.0}
    assert max_period_share(pnls) == pytest.approx(0.9)
    ym = year_month_profit_shares(
        [
            (date(2020, 3, 2), 50.0),
            (date(2020, 3, 9), 40.0),
            (date(2021, 1, 4), 10.0),
        ]
    )
    assert ym["max_year_share"] == pytest.approx(0.9)
    assert ym["max_month_share"] == pytest.approx(0.9)


def test_evaluate_r21_gates_all_pass_is_implementability_eligible_not_capital() -> None:
    stats = summarize([0.05] * 40, [f"d{i}" for i in range(40)])
    report = evaluate_r21_gates(**_all_pass_kwargs(stats))
    assert report.all_hard_gates_passed is True
    assert report.implementability_eligible is True
    assert report.capital_go is False
    assert report.verdict == "implementability_eligible"


def test_evaluate_r21_gates_g2_fail_kills_line() -> None:
    # median negative
    stats = summarize([-1.0, -1.0, 10.0], ["a", "b", "c"])
    report = evaluate_r21_gates(**_all_pass_kwargs(stats))
    assert report.all_hard_gates_passed is False
    assert report.implementability_eligible is False
    assert report.verdict == "kill_line"
    assert any(g.id == "G2" and not g.passed for g in report.gates)


def test_evaluate_r21_gates_unmeasured_g0_g6_kill_implementability() -> None:
    stats = summarize([0.05] * 40, [f"d{i}" for i in range(40)])
    report = evaluate_r21_gates(
        **_all_pass_kwargs(
            stats,
            g0_deciles_changed=None,
            tail_within_limits=None,
            buffering_modeled=False,
        )
    )
    assert report.implementability_eligible is False
    assert report.capital_go is False
    by_id = {g.id: g for g in report.gates}
    assert by_id["G0-synthetic"].passed is False
    assert by_id["G6"].passed is False
    assert by_id["G7"].passed is False


def test_evaluate_r21_gates_uses_g6_id_not_tuple_index() -> None:
    """Eligibility looks up G6 by id so reordering gates cannot silently drop it."""
    stats = summarize([0.05] * 40, [f"d{i}" for i in range(40)])
    report = evaluate_r21_gates(**_all_pass_kwargs(stats, tail_within_limits=False))
    assert report.implementability_eligible is False
    assert any(g.id == "G6" and not g.passed for g in report.gates)


def test_xs_gate_result_to_dict() -> None:
    r = XsGateResult(id="G1", passed=True, severity="hard", reason="ok")
    assert r.to_dict() == {
        "id": "G1",
        "passed": True,
        "severity": "hard",
        "reason": "ok",
    }


def test_trailing_median_dollar_volume_and_simple_beta() -> None:
    from invest.application.xs_reversal import (
        simple_beta,
        trailing_median_dollar_volume,
    )

    closes = [10.0] * 20
    volumes = [1_000_000.0] * 20
    med = trailing_median_dollar_volume(closes, volumes, end_index=19, window=20)
    assert med == pytest.approx(10_000_000.0)

    asset = [0.01, 0.02, -0.01, 0.03]
    market = [0.01, 0.02, -0.01, 0.03]
    assert simple_beta(asset, market) == pytest.approx(1.0)


def test_cross_section_log_adv_ranks_orders_by_log() -> None:
    # 1e6, e*1e6, e^2*1e6 → ranks 0, 0.5, 1.0 on log scale
    a0 = 1_000_000.0
    a1 = math.e * a0
    a2 = math.e * a1
    ranks = cross_section_log_adv_ranks([a0, a1, a2])
    assert ranks[0] == pytest.approx(0.0)
    assert ranks[1] == pytest.approx(0.5)
    assert ranks[2] == pytest.approx(1.0)


def test_residualized_decile_spread_long_losers_short_winners() -> None:
    # 10 names: formation residual ranks with forward returns inverse to formation
    rows = [
        NameFormationRow(
            symbol=f"S{i}",
            formation_return=float(i),
            beta=0.0,
            log_adv_rank=0.0,
            forward_return=float(9 - i) * 0.01,
        )
        for i in range(10)
    ]
    spread, d1, d10 = residualized_decile_spread(rows)
    assert spread is not None
    # D1 = lowest formation (i=0) forward 0.09; D10 = i=9 forward 0.0
    assert spread == pytest.approx(0.09 - 0.0)


def test_signal_shuffle_placebo_destroys_injected_reverse() -> None:
    """Real residual reverse → positive spread; signal shuffle collapses it.

    Not an identity of the real series (the old post-hoc date shuffle of finished
    spreads with 1-obs/cluster was).
    """
    rows = [
        NameFormationRow(
            symbol=f"S{i}",
            formation_return=float(i),
            beta=0.0,
            log_adv_rank=0.0,
            forward_return=float(9 - i) * 0.01,
        )
        for i in range(10)
    ]
    real, _, _ = residualized_decile_spread(rows)
    assert real is not None and real > 0.05

    rng = random.Random(0)
    placebos = [signal_shuffle_placebo_spread(rows, rng=rng) for _ in range(40)]
    placebos_f = [p for p in placebos if p is not None]
    assert placebos_f
    mean_p = sum(placebos_f) / len(placebos_f)
    # Shuffled signal should not systematically recover the engineered reverse.
    assert abs(mean_p) < real * 0.5


def test_summarize_spread_series_and_folds() -> None:
    from invest.application.xs_reversal import (
        annual_fold_signs,
        count_positive_folds,
        summarize_spread_series,
    )

    dates = [date(2019, 1, 4), date(2019, 1, 11), date(2020, 1, 3)]
    spreads = [0.01, 0.02, -0.01]
    stats = summarize_spread_series(spreads, dates)
    assert stats.n == 3
    folds = annual_fold_signs(spreads, dates)
    assert folds[2019] == pytest.approx(0.015)
    pos, total = count_positive_folds(folds)
    assert total == 2 and pos == 1


def test_build_r21_artifact_is_json_friendly() -> None:
    from invest.application.xs_reversal import build_r21_artifact, evaluate_r21_gates

    stats = summarize([0.05] * 40, [f"d{i}" for i in range(40)])
    report = evaluate_r21_gates(**_all_pass_kwargs(stats))
    art = build_r21_artifact(
        spread_stats=stats,
        gate_report=report,
        fold_means={2019: 0.01, 2020: 0.02},
        max_year_share=0.15,
        max_month_share=0.10,
        abs_rho=0.1,
        alpha=0.01,
        net_at_5bps=0.02,
        net_at_10bps=0.01,
        net_at_25bps=-0.01,
        n_formations=40,
        buffering_modeled=False,
    )
    assert art["experiment"] == "r2-1-xs-reversal-lp"
    assert art["capital_go"] is False
    assert art["residual_claim"] == "hard_frozen"
    assert "gates" in art
    assert art["costs"]["buffering_modeled"] is False
    assert "mean_spread_net_10bps" in art["costs"]


def test_pearson_and_alpha_and_deflated_sharpe() -> None:
    from invest.application.xs_reversal import (
        deflated_sharpe_proxy,
        ols_alpha_vs_market,
        pearson_corr,
    )

    x = [1.0, 2.0, 3.0, 4.0]
    y = [2.0, 4.0, 6.0, 8.0]
    assert pearson_corr(x, y) == pytest.approx(1.0)
    # spreads = 0.01 + 0*market + noise
    market = [0.01, -0.01, 0.02, 0.0, 0.01]
    spreads = [0.012, 0.009, 0.011, 0.010, 0.013]
    alpha, ok = ols_alpha_vs_market(spreads, market)
    assert alpha is not None and alpha > 0
    dsr = deflated_sharpe_proxy(sharpe=1.0, n_obs=100, n_trials=5)
    assert dsr < 1.0
