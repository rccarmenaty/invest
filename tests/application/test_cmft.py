"""CMFT Stage A: pure helpers, protocol freeze, and dual-exit gates (#74)."""

from __future__ import annotations

import math
from datetime import date

import pytest

from invest.application.event_study_excess import summarize
from invest.application.cmft import (
    PROTOCOL,
    PRICE_TREND_FEATURES,
    NOISE_FEATURE_PREFIX,
    assign_deciles,
    build_cmft_artifact,
    cost_net_spread,
    demean_cross_section,
    evaluate_cmft_gates,
    evaluate_g0_data,
    evaluate_g0_placebo,
    evaluate_g1,
    evaluate_g2,
    evaluate_g3,
    evaluate_g4_costs,
    evaluate_g5_beat_c1,
    evaluate_g6_vi,
    evaluate_g7_reversal,
    evaluate_g8_deflated,
    evaluate_k0_power,
    forward_open_to_open_return,
    importance_shares,
    max_period_share,
    min_detectable_spread,
    mom_12_1_return,
    month_end_formation_dates,
    t1_config_within_bounds,
    top_minus_bottom_spread,
    year_month_profit_shares,
)


def _stats(values: list[float], clusters: list | None = None):
    if clusters is None:
        clusters = list(range(len(values)))
    return summarize(values, clusters)


def _passing_kwargs(**overrides):
    stats = _stats([0.02] * 12)
    base = dict(
        g0_data_years_monotone=5,
        g0_data_years_total=7,
        k0_n_formations=500,
        k0_spread_vol=0.03,
        g0_placebo_t_abs=0.4,
        spread_stats=stats,
        positive_annual_folds=6,
        total_annual_folds=7,
        max_year_share=0.15,
        max_month_share=0.10,
        mean_net_10bps=0.005,
        mean_net_5bps=0.008,
        t1_mean_net=0.01,
        t1_median_net=0.008,
        c1_mean_net=0.002,
        c1_median_net=0.001,
        vi_price_trend_share=0.6,
        vi_noise_in_top10=False,
        vi_short_horizon_share=0.1,
        deflated_sharpe=0.15,
        deflated_sharpe_measured=True,
    )
    base.update(overrides)
    return base


def test_protocol_freezes_cmft_knobs() -> None:
    assert PROTOCOL.experiment_id == "cmft-stage-a"
    assert PROTOCOL.mom_far_sessions == 252
    assert PROTOCOL.mom_near_sessions == 21
    assert PROTOCOL.label_horizon_sessions == 21
    assert PROTOCOL.skip_sessions == 1
    assert PROTOCOL.history_sessions == 253
    assert PROTOCOL.deciles == 10
    assert PROTOCOL.primary_min_price == 5.0
    assert PROTOCOL.year_share_max == pytest.approx(0.25)
    assert PROTOCOL.accept_cost_bps == 10.0
    assert PROTOCOL.g1_min_t == 3.0
    assert PROTOCOL.t1_max_depth == 3
    assert PROTOCOL.t1_max_leaves == 16
    assert PROTOCOL.t1_min_data_in_leaf == 200
    assert PROTOCOL.k0_mds_bps == 50.0
    assert PROTOCOL.g0_data_min_monotone_years == 4
    assert PROTOCOL.capital_go is False
    assert "mom_12_1" in PRICE_TREND_FEATURES
    assert NOISE_FEATURE_PREFIX == "noise_"


def test_month_end_formation_dates_are_last_session_of_each_month() -> None:
    sessions = [
        date(2020, 1, 30),
        date(2020, 1, 31),
        date(2020, 2, 27),
        date(2020, 2, 28),
        date(2020, 3, 31),
    ]
    assert month_end_formation_dates(sessions) == [
        date(2020, 1, 31),
        date(2020, 2, 28),
        date(2020, 3, 31),
    ]


def test_mom_12_1_matches_core_far_near_arithmetic() -> None:
    # closes[i] = 100 + i; at end index 252: near=21 → close[231]=331, far=252 → close[0]=100
    closes = [100.0 + i for i in range(253)]
    got = mom_12_1_return(closes, formation_index=252)
    assert got == pytest.approx(331.0 / 100.0 - 1.0)


def test_mom_12_1_none_when_insufficient_history() -> None:
    closes = [100.0 + i for i in range(100)]
    assert mom_12_1_return(closes, formation_index=99) is None


def test_forward_open_to_open_uses_skip_and_horizon() -> None:
    # indices: formation f=0, entry = 1, exit = 1+21 = 22
    opens = [10.0 + i for i in range(30)]
    got = forward_open_to_open_return(opens, formation_index=0)
    assert got == pytest.approx(opens[22] / opens[1] - 1.0)


def test_demean_cross_section_zero_mean() -> None:
    xs = demean_cross_section([1.0, 2.0, 3.0])
    assert sum(xs) == pytest.approx(0.0)
    assert xs[1] == pytest.approx(0.0)


def test_assign_deciles_lowest_is_one_highest_is_ten() -> None:
    scores = list(range(20))  # 0..19
    d = assign_deciles(scores)
    assert d[0] == 1
    assert d[-1] == 10
    assert set(d) <= set(range(1, 11))


def test_top_minus_bottom_spread_is_mean_d10_minus_mean_d1() -> None:
    assert top_minus_bottom_spread([0.01, 0.03], [0.10, 0.12]) == pytest.approx(0.09)


def test_cost_net_spread_subtracts_round_trip() -> None:
    # 10 bps/side → 20 bps RT = 0.002
    assert cost_net_spread(0.01, bps_per_side=10.0) == pytest.approx(0.008)


def test_year_month_profit_shares() -> None:
    dated = [
        (date(2020, 1, 31), 10.0),
        (date(2020, 2, 28), 10.0),
        (date(2021, 1, 29), 80.0),
    ]
    shares = year_month_profit_shares(dated)
    assert shares["max_year_share"] == pytest.approx(0.8)
    assert shares["max_month_share"] == pytest.approx(0.8)


def test_g0_data_pass_when_enough_monotone_years() -> None:
    g = evaluate_g0_data(years_monotone=5, years_total=7)
    assert g.passed is True
    assert g.id == "G0-data"


def test_g0_data_fail_when_too_few_monotone_years() -> None:
    g = evaluate_g0_data(years_monotone=2, years_total=7)
    assert g.passed is False


def test_g0_data_unmeasured_fails_closed() -> None:
    g = evaluate_g0_data(years_monotone=None, years_total=None)
    assert g.passed is False
    assert "fail closed" in g.reason


def test_k0_power_pass_when_mds_at_or_below_threshold() -> None:
    # large n, modest vol → MDS small
    g = evaluate_k0_power(n_formations=400, spread_vol=0.03)
    assert g.passed is True
    assert g.id == "K0-power"


def test_k0_power_fail_when_underpowered() -> None:
    g = evaluate_k0_power(n_formations=10, spread_vol=0.10)
    assert g.passed is False
    assert "underpowered" in g.reason or "MDS" in g.reason


def test_k0_unmeasured_fails_closed() -> None:
    g = evaluate_k0_power(n_formations=None, spread_vol=None)
    assert g.passed is False


def test_min_detectable_spread_decreases_with_n() -> None:
    a = min_detectable_spread(n_formations=100, spread_vol=0.05)
    b = min_detectable_spread(n_formations=400, spread_vol=0.05)
    assert b < a


def test_g0_placebo() -> None:
    assert evaluate_g0_placebo(clustered_t_abs=0.5).passed is True
    assert evaluate_g0_placebo(clustered_t_abs=2.5).passed is False


def test_g1_requires_mean_and_t() -> None:
    good = _stats([0.02] * 20)
    assert evaluate_g1(good).passed is True
    bad = _stats([-0.01] * 20)
    assert evaluate_g1(bad).passed is False


def test_g2_median() -> None:
    # 11 positive values → median positive
    assert evaluate_g2(_stats([0.01] * 11)).passed is True
    assert evaluate_g2(_stats([-0.01] * 11)).passed is False


def test_g3_year_share_and_majority() -> None:
    ok = evaluate_g3(
        positive_annual_folds=5,
        total_annual_folds=7,
        max_year_share=0.2,
        max_month_share=0.1,
    )
    assert ok.passed is True
    bad = evaluate_g3(
        positive_annual_folds=5,
        total_annual_folds=7,
        max_year_share=0.5,
        max_month_share=0.1,
    )
    assert bad.passed is False


def test_g4_costs_require_net_at_10bps() -> None:
    assert evaluate_g4_costs(mean_net_10bps=0.001, mean_net_5bps=0.002).passed is True
    assert evaluate_g4_costs(mean_net_10bps=-0.001, mean_net_5bps=0.002).passed is False


def test_g5_beat_c1_requires_mean_and_median() -> None:
    assert (
        evaluate_g5_beat_c1(
            t1_mean_net=0.01,
            t1_median_net=0.008,
            c1_mean_net=0.002,
            c1_median_net=0.001,
        ).passed
        is True
    )
    assert (
        evaluate_g5_beat_c1(
            t1_mean_net=0.01,
            t1_median_net=0.0005,
            c1_mean_net=0.002,
            c1_median_net=0.001,
        ).passed
        is False
    )


def test_g6_vi_price_trend_and_noise() -> None:
    assert (
        evaluate_g6_vi(price_trend_share=0.55, noise_in_top10=False).passed is True
    )
    assert (
        evaluate_g6_vi(price_trend_share=0.30, noise_in_top10=False).passed is False
    )
    assert (
        evaluate_g6_vi(price_trend_share=0.80, noise_in_top10=True).passed is False
    )
    assert evaluate_g6_vi(price_trend_share=None, noise_in_top10=None).passed is False


def test_g7_reversal_escalate_when_short_horizon_dominates() -> None:
    g = evaluate_g7_reversal(short_horizon_share=0.5)
    assert g.passed is False
    assert g.severity == "escalate"
    ok = evaluate_g7_reversal(short_horizon_share=0.1)
    assert ok.passed is True


def test_g8_deflated_fail_closed_when_unmeasured() -> None:
    g = evaluate_g8_deflated(deflated_sharpe=None, measured=False)
    assert g.passed is False
    assert evaluate_g8_deflated(deflated_sharpe=0.1, measured=True).passed is True
    assert evaluate_g8_deflated(deflated_sharpe=-0.1, measured=True).passed is False


def test_t1_config_bounds() -> None:
    assert t1_config_within_bounds(max_depth=3, num_leaves=8, min_data_in_leaf=200)
    assert not t1_config_within_bounds(max_depth=6, num_leaves=8, min_data_in_leaf=200)
    assert not t1_config_within_bounds(max_depth=3, num_leaves=64, min_data_in_leaf=200)
    assert not t1_config_within_bounds(max_depth=3, num_leaves=8, min_data_in_leaf=50)


def test_evaluate_cmft_gates_all_pass_still_capital_go_false() -> None:
    report = evaluate_cmft_gates(**_passing_kwargs())
    assert report.all_hard_gates_passed is True
    assert report.implementability_eligible is True
    assert report.capital_go is False
    assert report.verdict == "implementability_eligible"


def test_evaluate_cmft_k0_fail_is_underpowered_stop() -> None:
    report = evaluate_cmft_gates(**_passing_kwargs(k0_n_formations=5, k0_spread_vol=0.2))
    assert report.capital_go is False
    assert report.verdict == "underpowered-stop"
    assert report.implementability_eligible is False


def test_evaluate_cmft_hard_fail_is_kill_line() -> None:
    report = evaluate_cmft_gates(**_passing_kwargs(mean_net_10bps=-0.01))
    assert report.verdict == "kill_line"
    assert report.capital_go is False
    assert report.implementability_eligible is False


def test_g0_data_fail_is_kill_line() -> None:
    report = evaluate_cmft_gates(**_passing_kwargs(g0_data_years_monotone=1, g0_data_years_total=7))
    assert report.verdict == "kill_line"


def test_g7_escalate_is_not_implementability() -> None:
    report = evaluate_cmft_gates(**_passing_kwargs(vi_short_horizon_share=0.5))
    assert report.verdict in ("kill_line", "escalate")
    assert report.implementability_eligible is False
    assert report.capital_go is False


def test_artifact_always_capital_go_false() -> None:
    report = evaluate_cmft_gates(**_passing_kwargs())
    art = build_cmft_artifact(report, fold_table=[{"year": 2021, "mean": 0.01}])
    assert art["capital_go"] is False
    assert art["experiment_id"] == "cmft-stage-a"
    assert art["residual_freeze_untouched"] is True
    assert art["r21_kill_line_untouched"] is True
    assert art["sf_features_included"] is False
    assert art["hmm_included"] is False
    assert "gates" in art


def test_max_period_share() -> None:
    assert max_period_share({2020: 10.0, 2021: 30.0}) == pytest.approx(0.75)


def test_importance_shares_for_vi_gates() -> None:
    shares = importance_shares(
        {
            "mom_12_1": 40.0,
            "pct_of_52w_high": 20.0,
            "ret_21d": 10.0,
            "rvol_21": 20.0,
            "noise_0": 10.0,
        }
    )
    assert shares["price_trend_share"] == pytest.approx(0.70)
    assert shares["short_horizon_share"] == pytest.approx(0.10)
    assert shares["noise_in_top10"] is True
