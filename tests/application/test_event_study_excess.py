"""Gate 1a: excess-vs-universe stats and pass/fail evaluation."""

from datetime import date

import pytest

from invest.application.event_study_excess import (
    Gate1aResult,
    SymbolBarSeries,
    SummaryStats,
    clustered_t,
    evaluate_gate_1a,
    excess_return,
    excess_summary_for_horizon,
    formation_daily_returns,
    forward_session_return,
    high_proximity_52w,
    information_discreteness,
    summarize,
    universe_mean_forward_return,
)


def test_clustered_t_is_mean_over_cluster_robust_se() -> None:
    # Two clusters: date A has +1,+1; date B has -1. Mean = 1/3.
    values = [1.0, 1.0, -1.0]
    clusters = ["A", "A", "B"]
    mean, t, n = clustered_t(values, clusters)
    assert n == 3
    assert mean == pytest.approx(1.0 / 3.0)
    assert t == pytest.approx((1.0 / 3.0) / ((math_sqrt_cluster_ss(values, clusters, mean)) / 3.0))


def math_sqrt_cluster_ss(values, clusters, mean) -> float:
    from collections import defaultdict
    import math

    sums: dict = defaultdict(float)
    for v, c in zip(values, clusters):
        sums[c] += v - mean
    return math.sqrt(sum(s * s for s in sums.values()))


def test_summarize_reports_hit_rate_and_median() -> None:
    stats = summarize([0.1, -0.05, 0.2], ["d1", "d1", "d2"])
    assert isinstance(stats, SummaryStats)
    assert stats.n == 3
    assert stats.mean == pytest.approx(0.0833333333)
    assert stats.median == pytest.approx(0.1)
    assert stats.hit_rate_gt0 == pytest.approx(2 / 3)


def test_forward_session_return_from_next_open() -> None:
    # decision at index 0 → entry open index 1; h=2 → close index 3
    opens = [10.0, 100.0, 101.0, 102.0]
    closes = [10.5, 100.5, 101.5, 110.0]
    dates = [date(2020, 1, d) for d in (1, 2, 3, 4)]
    ret = forward_session_return(
        opens=opens, closes=closes, dates=dates, decision_date=date(2020, 1, 1), horizon=2
    )
    assert ret == pytest.approx(110.0 / 100.0 - 1.0)


def test_forward_session_return_none_when_horizon_missing() -> None:
    opens = [10.0, 100.0]
    closes = [10.5, 100.5]
    dates = [date(2020, 1, 1), date(2020, 1, 2)]
    assert (
        forward_session_return(
            opens=opens, closes=closes, dates=dates, decision_date=date(2020, 1, 1), horizon=5
        )
        is None
    )


def test_universe_mean_forward_return_averages_eligible_symbols() -> None:
    series = {
        "AAA": SymbolBarSeries(
            dates=[date(2020, 1, 1), date(2020, 1, 2), date(2020, 1, 3)],
            opens=[10.0, 10.0, 10.0],
            closes=[10.0, 10.0, 11.0],  # +10% at h=1 from entry open day2
        ),
        "BBB": SymbolBarSeries(
            dates=[date(2020, 1, 1), date(2020, 1, 2), date(2020, 1, 3)],
            opens=[20.0, 20.0, 20.0],
            closes=[20.0, 20.0, 22.0],  # +10%
        ),
        "CCC": SymbolBarSeries(
            dates=[date(2020, 1, 1), date(2020, 1, 2), date(2020, 1, 3)],
            opens=[30.0, 30.0, 30.0],
            closes=[30.0, 30.0, 27.0],  # -10%
        ),
    }
    mean = universe_mean_forward_return(
        series, eligible=("AAA", "BBB", "CCC"), decision_date=date(2020, 1, 1), horizon=1
    )
    assert mean == pytest.approx((0.1 + 0.1 - 0.1) / 3)


def test_excess_return_is_signal_minus_universe() -> None:
    assert excess_return(0.05, 0.02) == pytest.approx(0.03)


def test_gate_1a_passes_when_mean_positive_and_t_meets_threshold() -> None:
    excess = SummaryStats(
        n=100, mean=0.01, median=0.005, hit_rate_gt0=0.55, clustered_t=2.7
    )
    result = evaluate_gate_1a(excess, min_t=2.5, horizon=60)
    assert result == Gate1aResult(
        passed=True,
        horizon=60,
        excess=excess,
        threshold_t=2.5,
        reason="h60 excess mean>0 and clustered_t>=2.5",
    )


def test_gate_1a_fails_when_t_below_threshold() -> None:
    excess = SummaryStats(
        n=100, mean=0.01, median=0.005, hit_rate_gt0=0.55, clustered_t=1.8
    )
    result = evaluate_gate_1a(excess, min_t=2.5, horizon=60)
    assert result.passed is False
    assert "clustered_t" in result.reason


def test_gate_1a_fails_when_mean_non_positive() -> None:
    excess = SummaryStats(
        n=100, mean=-0.001, median=-0.002, hit_rate_gt0=0.48, clustered_t=3.0
    )
    result = evaluate_gate_1a(excess, min_t=2.5, horizon=60)
    assert result.passed is False
    assert "mean" in result.reason


def test_information_discreteness_prefers_smooth_same_sign_path() -> None:
    # All small positive days → continuous information → lower ID
    smooth = [0.01] * 10
    jump = [-0.01] * 9 + [0.19]  # same cumulative ~0.10, one jump day
    id_smooth = information_discreteness(smooth)
    id_jump = information_discreteness(jump)
    assert id_smooth < id_jump


def test_formation_daily_returns_end_before_decision_day() -> None:
    # closes: day0..day5; decision at index 5 → formation ends at day4
    closes = [100.0, 101.0, 102.0, 103.0, 104.0, 200.0]
    rets = formation_daily_returns(closes, decision_index=5, lookback=3)
    assert rets == pytest.approx(
        [102.0 / 101.0 - 1, 103.0 / 102.0 - 1, 104.0 / 103.0 - 1]
    )


def test_high_proximity_52w_is_close_over_window_max() -> None:
    closes = [10.0, 20.0, 15.0, 18.0]
    assert high_proximity_52w(closes, decision_index=3, window=4) == pytest.approx(18.0 / 20.0)


def test_excess_summary_for_horizon_subtracts_same_date_universe() -> None:
    d1, d2 = date(2020, 1, 1), date(2020, 1, 2)
    stats = excess_summary_for_horizon(
        signal_returns=[0.10, 0.00, None],
        decision_dates=[d1, d2, d2],
        universe_means={d1: 0.04, d2: 0.01},
    )
    assert stats.n == 2
    assert stats.mean == pytest.approx(((0.10 - 0.04) + (0.00 - 0.01)) / 2)
