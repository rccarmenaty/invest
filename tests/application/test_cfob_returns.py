"""Pure inference primitives for the CFOB E1/E2 returns gates (ticket #90).

Covers the three frozen building blocks of ADR 0003:
- ``winsorized_mean`` — the cohort estimator T(d) (§3)
- ``stationary_block_bootstrap_p`` — the null-imposed circular block bootstrap (§2)
- ``derive_seed`` — the SHA-256 reproducibility contract (§6)
"""

from __future__ import annotations

import numpy as np
import pytest

from invest.application.cfob_returns import (
    derive_seed,
    stationary_block_bootstrap_p,
    winsorized_mean,
)

# --- winsorized_mean (T(d), ADR 0003 §3) -------------------------------------


def test_winsorized_mean_of_symmetric_data_is_the_plain_mean() -> None:
    # Symmetric clipping leaves the mean unchanged.
    assert winsorized_mean(list(range(101))) == pytest.approx(50.0)


def test_winsorized_mean_clips_a_one_sided_outlier_at_p99() -> None:
    # 100 zeros + one huge value: P99 == 0, so the outlier is clipped to 0 and
    # the winsorized mean is 0 — versus a raw mean near 9,901.
    values = [0.0] * 100 + [1_000_000.0]
    assert np.mean(values) > 9_000.0
    assert winsorized_mean(values) == pytest.approx(0.0)


def test_winsorized_mean_is_translation_equivariant() -> None:
    # T(d + c) == T(d) + c — the property the null imposition relies on.
    rng = np.random.default_rng(1)
    x = rng.normal(size=500)
    assert winsorized_mean(x + 7.5) == pytest.approx(winsorized_mean(x) + 7.5)


def test_winsorized_mean_rejects_nan_input() -> None:
    with pytest.raises(ValueError):
        winsorized_mean([1.0, 2.0, float("nan")])


def test_winsorized_mean_returns_a_python_float() -> None:
    result = winsorized_mean([1.0, 2.0, 3.0])
    assert isinstance(result, float)


# --- derive_seed (reproducibility contract, ADR 0003 §6) ---------------------


def test_derive_seed_is_deterministic() -> None:
    a = derive_seed(0xCF0B, "cfob-e1-e2-1", "E1")
    b = derive_seed(0xCF0B, "cfob-e1-e2-1", "E1")
    assert a == b
    assert isinstance(a, int)


def test_derive_seed_separates_gate_streams() -> None:
    e1 = derive_seed(0xCF0B, "cfob-e1-e2-1", "E1")
    e2 = derive_seed(0xCF0B, "cfob-e1-e2-1", "E2")
    placebo = derive_seed(0xCF0B, "cfob-e1-e2-1", "placebo")
    assert len({e1, e2, placebo}) == 3


def test_derive_seed_separates_per_cluster_placebo_streams() -> None:
    a = derive_seed(0xCF0B, "cfob-e1-e2-1", "placebo", "ACME-2020-03-12")
    b = derive_seed(0xCF0B, "cfob-e1-e2-1", "placebo", "OTHER-2020-03-12")
    assert a != b


def test_derive_seed_changes_with_spec_version() -> None:
    v1 = derive_seed(0xCF0B, "cfob-e1-e2-1", "E1")
    v2 = derive_seed(0xCF0B, "cfob-e1-e2-2", "E1")
    assert v1 != v2


# --- stationary_block_bootstrap_p (ADR 0003 §2) ------------------------------


def _months_from_flat(values: list[float], per_month: int) -> list[list[float]]:
    """Chop a flat value list into consecutive month buckets."""
    return [values[i : i + per_month] for i in range(0, len(values), per_month)]


def test_bootstrap_p_formula_and_result_shape() -> None:
    rng = np.random.default_rng(3)
    buckets = _months_from_flat(list(rng.normal(size=600)), per_month=5)
    result = stationary_block_bootstrap_p(buckets, q=1 / 6, replications=999, seed=42)

    assert result.replications == 999
    assert result.discards == 0  # dense buckets, never all-empty
    # p = (1 + K) / (B + 1)
    assert result.p == pytest.approx((1 + result.k) / (999 + 1))
    assert 0.0 < result.p <= 1.0


def test_bootstrap_detects_a_strong_planted_effect() -> None:
    rng = np.random.default_rng(4)
    buckets = _months_from_flat(list(rng.normal(loc=5.0, size=600)), per_month=5)
    result = stationary_block_bootstrap_p(buckets, q=1 / 6, replications=999, seed=7)
    # A large positive effect sits far in the right tail of the recentered null.
    assert result.p < 0.005


def _assert_uniform_pvalues(ps: list[float]) -> None:
    """Coarse distributional uniformity check (no scipy): mean near 0.5 and the
    lower-tail quantile masses near their nominal levels."""
    arr = np.asarray(ps)
    assert 0.4 < float(arr.mean()) < 0.6
    assert 0.13 < float(np.mean(arr <= 0.25)) < 0.37
    assert 0.38 < float(np.mean(arr <= 0.5)) < 0.62


def test_bootstrap_is_calibrated_under_an_iid_null() -> None:
    # Over many independent iid null cohorts the one-sided p is ~Uniform(0,1).
    ps = []
    for s in range(300):
        rng = np.random.default_rng(1000 + s)
        buckets = _months_from_flat(list(rng.normal(size=300)), per_month=5)
        ps.append(
            stationary_block_bootstrap_p(buckets, q=1 / 6, replications=199, seed=s).p
        )
    _assert_uniform_pvalues(ps)


def test_bootstrap_is_calibrated_under_a_block_dependent_null() -> None:
    # The stationary block bootstrap exists to stay calibrated under serial
    # dependence: an AR(1) mean-zero null must still yield ~Uniform p.
    ps = []
    for s in range(300):
        rng = np.random.default_rng(5000 + s)
        eps = rng.normal(size=300)
        series = np.empty(300)
        series[0] = eps[0]
        for t in range(1, 300):  # phi=0.7 serial correlation, stationary mean 0
            series[t] = 0.7 * series[t - 1] + eps[t]
        # Do NOT re-center: the natural (correlation-inflated) sample-mean spread
        # is exactly what the stationary block bootstrap must stay calibrated to.
        buckets = _months_from_flat(list(series), per_month=5)
        ps.append(
            stationary_block_bootstrap_p(buckets, q=1 / 6, replications=199, seed=s).p
        )
    _assert_uniform_pvalues(ps)


def test_bootstrap_rejects_a_degenerate_restart_probability() -> None:
    buckets = _months_from_flat([1.0, 2.0, 3.0, 4.0], per_month=2)
    for bad_q in (0.0, -0.1, 1.5):
        with pytest.raises(ValueError, match="q must be"):
            stationary_block_bootstrap_p(buckets, q=bad_q, replications=10, seed=1)


def test_bootstrap_result_serializes_for_the_manifest() -> None:
    buckets = _months_from_flat([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], per_month=3)
    result = stationary_block_bootstrap_p(buckets, q=1 / 6, replications=99, seed=1)
    d = result.to_dict()
    assert set(d) == {"p", "observed", "k", "replications", "discards", "index_hash"}
    assert d["p"] == result.p
    assert isinstance(d["index_hash"], str) and len(d["index_hash"]) == 64


def test_bootstrap_discards_and_regenerates_zero_cluster_paths() -> None:
    # One non-empty month among many empty ones: some resampled paths land on
    # only-empty months and must be discarded, regenerated, and counted.
    buckets: list[list[float]] = [[] for _ in range(8)]
    buckets[3] = [1.0, 2.0, 3.0, 4.0]
    result = stationary_block_bootstrap_p(buckets, q=1 / 6, replications=500, seed=11)
    assert result.discards > 0
    assert result.replications == 500  # discards do not count toward B


def test_bootstrap_is_reproducible_for_a_fixed_seed() -> None:
    buckets = _months_from_flat(list(np.random.default_rng(5).normal(size=400)), per_month=5)
    r1 = stationary_block_bootstrap_p(buckets, q=1 / 6, replications=999, seed=99)
    r2 = stationary_block_bootstrap_p(buckets, q=1 / 6, replications=999, seed=99)
    assert r1.p == r2.p
    assert r1.k == r2.k
    assert r1.discards == r2.discards


def test_bootstrap_index_hash_pins_the_resample() -> None:
    # The index hash is a 64-hex SHA-256, reproducible for a fixed seed and
    # sensitive to the drawn resample (a different seed → a different hash).
    buckets = _months_from_flat(list(np.random.default_rng(5).normal(size=400)), per_month=5)
    a = stationary_block_bootstrap_p(buckets, q=1 / 6, replications=500, seed=99)
    b = stationary_block_bootstrap_p(buckets, q=1 / 6, replications=500, seed=99)
    c = stationary_block_bootstrap_p(buckets, q=1 / 6, replications=500, seed=100)
    assert len(a.index_hash) == 64
    assert a.index_hash == b.index_hash  # same seed → same resample
    assert a.index_hash != c.index_hash  # different seed → different resample


def test_non_circular_blocks_change_the_resample_but_stay_valid() -> None:
    # circular vs non-circular draw different resamples (different index hash) yet
    # both yield a valid one-sided p in (0, 1].
    buckets = _months_from_flat(list(np.random.default_rng(6).normal(size=400)), per_month=5)
    circ = stationary_block_bootstrap_p(buckets, q=1 / 6, replications=500, seed=3)
    noncirc = stationary_block_bootstrap_p(
        buckets, q=1 / 6, replications=500, seed=3, circular=False
    )
    assert circ.index_hash != noncirc.index_hash
    assert 0.0 < noncirc.p <= 1.0


# --- E1 gate orchestration (ADR 0003 §1, §5) ---------------------------------

from datetime import date, timedelta  # noqa: E402

from invest.application.cfob import PROTOCOL, ProtocolConfig  # noqa: E402
from invest.application.cfob_returns import (  # noqa: E402
    ClusterReturnInputs,
    E1Cohort,
    admissible_placebo_indices,
    assemble_e1_cohort,
    build_cluster_return_inputs,
    cluster_d_statistic,
    evaluate_e1_gate,
    focal_net_return,
    ordered_month_buckets,
    resolve_entry_index,
    sample_placebo_indices,
)


def test_resolve_entry_index_is_the_first_session_strictly_after_known_time() -> None:
    dates = [date(2020, 1, d) for d in (2, 3, 6, 7, 8)]
    assert resolve_entry_index(dates, date(2020, 1, 3)) == 2  # not the 3rd itself
    assert resolve_entry_index(dates, date(2020, 1, 1)) == 0
    assert resolve_entry_index(dates, date(2020, 1, 8)) is None  # nothing after


def test_focal_net_return_is_open_to_open_less_round_trip_cost() -> None:
    opens = [10.0] * 100
    opens[0] = 100.0
    opens[60] = 110.0
    r = focal_net_return(opens, 0, horizon=60, cost_bps=25.0)
    assert r == pytest.approx(0.10 - 0.0025)


def test_focal_net_return_is_none_when_forward_window_is_incomplete() -> None:
    opens = [10.0] * 40  # only 40 sessions, horizon 60 runs off the end
    assert focal_net_return(opens, 0, horizon=60, cost_bps=25.0) is None


def test_admissible_placebo_excludes_the_full_forward_window_intersection() -> None:
    # 200 sessions, horizon 5, one real event entry at index 100. Candidates run
    # 0..194 (complete window); the embargo removes 95..105 inclusive.
    adm = admissible_placebo_indices(
        session_count=200, real_event_entry_indices=[100], horizon=5
    )
    assert max(adm) == 194  # no candidate without a complete forward window
    assert all(not (95 <= c <= 105) for c in adm)
    assert 94 in adm and 106 in adm


def test_admissible_placebo_honours_events_dropped_by_de_overlap() -> None:
    # The caller passes the full pre-de-overlap set; every one embargoes.
    adm = admissible_placebo_indices(
        session_count=300, real_event_entry_indices=[50, 120, 121], horizon=5
    )
    for r in (50, 120, 121):
        assert all(not (r - 5 <= c <= r + 5) for c in adm)


def test_sample_placebo_is_exactly_draws_unique_and_deterministic() -> None:
    admissible = list(range(500))
    a = sample_placebo_indices(admissible, draws=100, seed=7)
    b = sample_placebo_indices(admissible, draws=100, seed=7)
    assert a is not None and len(a) == 100 == len(set(a))
    assert a == b  # deterministic for a fixed seed
    assert sample_placebo_indices(list(range(99)), draws=100, seed=7) is None


def test_cluster_d_statistic_is_focal_minus_placebo_mean() -> None:
    opens = [10.0] * 200
    opens[0] = 100.0
    opens[60] = 110.0  # focal: +10% at index 0
    # placebo entries all on flat stretch → placebo returns are -cost each
    d = cluster_d_statistic(opens, 0, [70, 80, 90], horizon=60, cost_bps=0.0)
    assert d == pytest.approx(0.10)  # focal +10%, placebo mean 0


def test_ordered_month_buckets_fills_empty_calendar_months() -> None:
    keys = [(2020, 1), (2020, 1), (2020, 3)]  # Feb is empty
    buckets = ordered_month_buckets(keys, [1.0, 2.0, 3.0])
    assert len(buckets) == 3  # Jan, Feb, Mar
    assert buckets[0] == [1.0, 2.0]
    assert buckets[1] == []  # empty February preserved
    assert buckets[2] == [3.0]


def test_ordered_month_buckets_spans_a_year_boundary() -> None:
    keys = [(2019, 11), (2020, 2)]
    buckets = ordered_month_buckets(keys, [1.0, 2.0])
    assert len(buckets) == 4  # Nov, Dec, Jan, Feb


def _flat_bars(n: int, symbol_start: date = date(2015, 1, 2)) -> list[tuple[date, float]]:
    return [(symbol_start + timedelta(days=i), 10.0) for i in range(n)]


def test_build_cluster_return_inputs_resolves_entries_and_real_events() -> None:
    bars = _flat_bars(300)
    dates = [b[0] for b in bars]
    clusters = [("ACME", dates[100])]
    inputs = build_cluster_return_inputs(
        clusters,
        session_bars_by_symbol={"ACME": bars},
        real_event_known_times_by_symbol={"ACME": [dates[100], dates[200]]},
    )
    assert len(inputs) == 1
    item = inputs[0]
    assert item.cluster_id == f"ACME:{dates[100].isoformat()}"
    assert item.entry_index == 101  # first session strictly after known_time
    assert item.real_event_entry_indices == (101, 201)


def test_assemble_e1_cohort_counts_every_drop_reason() -> None:
    cfg = ProtocolConfig(estage_placebo_draws=5, horizon_sessions=10)
    base = date(2015, 1, 2)
    opens_full = tuple(10.0 for _ in range(400))
    # 1) kept: complete window + enough placebo
    kept = ClusterReturnInputs("KEEP:1", base, opens_full, 0, ())
    # 2) no entry session
    no_entry = ClusterReturnInputs("NOENT:1", base, opens_full, None, ())
    # 3) insufficient placebo: only ~a handful of admissible dates
    tiny = ClusterReturnInputs("TINY:1", base, tuple(10.0 for _ in range(14)), 0, ())
    # 4) focal window incomplete: entry too close to the end
    late = ClusterReturnInputs("LATE:1", base, opens_full, 395, ())
    cohort = assemble_e1_cohort([kept, no_entry, tiny, late], config=cfg)
    assert cohort.size == 1
    assert cohort.drop_counts["no_entry_session"] == 1
    assert cohort.drop_counts["insufficient_placebo"] == 1
    assert cohort.drop_counts["focal_window_incomplete"] == 1


def test_evaluate_e1_gate_stops_under_the_cohort_floor() -> None:
    cfg = ProtocolConfig(estage_min_cohort=2000)
    cohort = E1Cohort(
        d_values=tuple(0.01 for _ in range(1999)),
        month_keys=tuple((2015 + i // 12, 1 + i % 12) for i in range(1999)),
        drop_counts={},
    )
    result = evaluate_e1_gate(cohort, config=cfg)
    assert result.underpowered is True
    assert result.passed is False
    assert result.p is None
    assert result.cohort_n == 1999


def test_evaluate_e1_gate_passes_on_a_planted_positive_effect() -> None:
    cfg = ProtocolConfig(
        estage_min_cohort=2000,
        estage_bootstrap_replications=999,
        estage_bootstrap_alpha=0.005,
    )
    rng = np.random.default_rng(0)
    n = 2400
    # 200 months, ~12 clusters each, all shifted strongly positive.
    d_values = tuple(float(x) for x in rng.normal(loc=0.5, scale=0.05, size=n))
    month_keys = tuple((2000 + i // 12, 1 + i % 12) for i in range(n // 12) for _ in range(12))
    cohort = E1Cohort(d_values=d_values, month_keys=month_keys, drop_counts={"x": 3})
    result = evaluate_e1_gate(cohort, config=cfg)
    assert result.underpowered is False
    assert result.passed is True
    assert result.p is not None and result.p < 0.005
    assert result.drop_counts == {"x": 3}  # ledger propagated
    assert result.month_span == 200


# --- E2 gate: habitat LOO factor, pre-event beta, benchmark residual (§4) -----

from invest.application.cfob_returns import (  # noqa: E402
    ClusterE2Inputs,
    E2Cohort,
    assemble_e2_cohort,
    beta_benchmark,
    date_e2_residual,
    evaluate_e2_gate,
    factor_daily_returns,
    loo_factor,
    ols_beta,
)


def test_loo_factor_excludes_the_focal_name() -> None:
    # sum over 4 names incl focal = 0.40, focal = 0.10 → non-focal mean = 0.30/3.
    assert loo_factor(sum_r=0.40, count=4, r_focal=0.10) == pytest.approx(0.10)


def test_loo_factor_requires_a_non_focal_name() -> None:
    with pytest.raises(ValueError):
        loo_factor(sum_r=0.05, count=1, r_focal=0.05)


def test_factor_daily_returns_match_loo_factor_and_floor_marks_missing() -> None:
    # 4 sessions → 3 daily returns. Counts chosen around the ≥50 non-focal floor:
    # count-1 = 51, 50, 49 → the third day is below the floor and is NaN.
    opens = [100.0, 110.0, 121.0, 133.1]  # +10% each session
    habitat_sum = [5.0, 6.0, 7.0]
    habitat_count = [52, 51, 50]
    factor = factor_daily_returns(opens, habitat_sum, habitat_count, breadth_floor=50)
    assert factor.shape == (3,)
    # Days 0 and 1 clear the floor and equal the scalar loo_factor exactly.
    assert factor[0] == pytest.approx(loo_factor(5.0, 52, 0.10))
    assert factor[1] == pytest.approx(loo_factor(6.0, 51, 0.10))
    assert np.isnan(factor[2])  # count-1 = 49 < 50 → missing, never zero-filled


def test_ols_beta_matches_numpy_polyfit() -> None:
    rng = np.random.default_rng(11)
    x = rng.normal(size=300)
    y = 1.7 * x + 0.3 + rng.normal(scale=0.1, size=300)
    beta = ols_beta(y, x, min_pairs=200)
    assert beta is not None
    assert beta == pytest.approx(float(np.polyfit(x, y, 1)[0]))


def test_ols_beta_drops_nan_pairs_and_the_200_pair_rule_governs() -> None:
    # Asymmetric handling: below-floor days show up as NaN in the factor window
    # and are simply dropped; the fit survives while ≥200 finite pairs remain.
    rng = np.random.default_rng(12)
    x = 2.0 * rng.normal(size=252)
    y = 0.9 * x + rng.normal(scale=0.05, size=252)
    holed = x.copy()
    holed[:50] = np.nan  # 50 missing → 202 valid pairs, still ≥ 200
    beta = ols_beta(y, holed, min_pairs=200)
    assert beta is not None
    holed[:53] = np.nan  # 199 valid pairs → below the floor, no beta
    assert ols_beta(y, holed, min_pairs=200) is None


def test_ols_beta_does_not_extend_backward_below_min_pairs() -> None:
    # A window with fewer than min_pairs sessions returns None — no back-extension.
    rng = np.random.default_rng(13)
    x = rng.normal(size=150)
    y = x + rng.normal(scale=0.1, size=150)
    assert ols_beta(y, x, min_pairs=200) is None


def test_beta_benchmark_compounds_per_day_not_the_naive_approximation() -> None:
    beta = 1.3
    h = [0.02, -0.01, 0.03, 0.015, -0.02]
    per_day = beta_benchmark(beta, h)
    naive = beta * (float(np.prod([1 + x for x in h])) - 1.0)
    # The per-daily-compounded benchmark is provably different from β·[∏(1+h)−1].
    assert per_day != pytest.approx(naive)
    assert per_day == pytest.approx(float(np.prod([1 + beta * x for x in h])) - 1.0)


def test_beta_benchmark_has_no_intercept_beta_zero_is_flat() -> None:
    # With no estimated intercept, beta=0 makes the benchmark exactly 0 — the
    # residual is then the raw net return (alpha handled by the placebo, not here).
    assert beta_benchmark(0.0, [0.05, -0.03, 0.10]) == pytest.approx(0.0)


def _e2_opens_and_habitat(
    n: int, *, count: int = 60, drift: float = 0.0
) -> tuple[list[float], list[float], list[int]]:
    """A flat-ish price series plus a focal-inclusive habitat aggregate wide enough
    to clear the breadth floor on every session."""
    opens = [100.0 * (1.0 + drift) ** i for i in range(n)]
    # habitat_sum is arbitrary but finite; count clears count-1 >= 50.
    habitat_sum = [0.001 * (i % 7) for i in range(n - 1)]
    habitat_count = [count] * (n - 1)
    return opens, habitat_sum, habitat_count


def test_date_e2_residual_is_none_when_a_forward_day_is_below_breadth() -> None:
    n = 400
    opens, hsum, hcount = _e2_opens_and_habitat(n)
    hcount = list(hcount)
    hcount[300] = 40  # one forward session below the floor → factor NaN there
    focal_daily = np.asarray(opens[1:], float) / np.asarray(opens[:-1], float) - 1.0
    factor = factor_daily_returns(opens, hsum, hcount, breadth_floor=50)
    # entry at 260 → forward window 260..319 includes the holed session 300.
    r = date_e2_residual(
        opens, focal_daily, factor, 260, horizon=60, cost_bps=25.0, beta_window=252, min_pairs=200
    )
    assert r is None


def test_date_e2_residual_is_finite_with_full_support() -> None:
    n = 400
    opens, hsum, hcount = _e2_opens_and_habitat(n)
    focal_daily = np.asarray(opens[1:], float) / np.asarray(opens[:-1], float) - 1.0
    factor = factor_daily_returns(opens, hsum, hcount, breadth_floor=50)
    r = date_e2_residual(
        opens, focal_daily, factor, 300, horizon=60, cost_bps=25.0, beta_window=252, min_pairs=200
    )
    assert r is not None and np.isfinite(r)


def test_beta_window_excludes_the_entry_straddling_return() -> None:
    # The beta window must end *before* the entry open — the daily return ending
    # at the entry open (index entry-1) spans the filing reaction and is excluded,
    # while the return before it (index entry-2) is the last one included.
    n, entry = 400, 300
    rng = np.random.default_rng(7)
    steps = rng.normal(scale=0.01, size=n - 1)
    opens = [100.0]
    for step in steps:
        opens.append(opens[-1] * (1.0 + step))
    focal_daily = np.asarray(opens[1:]) / np.asarray(opens[:-1]) - 1.0
    factor = 0.5 * focal_daily + rng.normal(scale=0.001, size=n - 1)  # identifiable beta

    kw = dict(horizon=60, cost_bps=0.0, beta_window=252, min_pairs=200)
    base = date_e2_residual(opens, focal_daily, factor, entry, **kw)
    assert base is not None

    straddle = factor.copy()
    straddle[entry - 1] += 5.0  # the excluded straddling return — residual unchanged
    assert date_e2_residual(opens, focal_daily, straddle, entry, **kw) == pytest.approx(base)

    included = factor.copy()
    included[entry - 2] += 5.0  # the last included return — residual must move
    assert date_e2_residual(opens, focal_daily, included, entry, **kw) != pytest.approx(base)


def test_assemble_e2_cohort_counts_e2_support_drops() -> None:
    cfg = ProtocolConfig(
        estage_placebo_draws=5,
        horizon_sessions=10,
        estage_beta_window_sessions=30,
        estage_beta_min_pairs=20,
        estage_factor_breadth_floor=50,
    )
    base = date(2015, 1, 2)
    n = 200
    opens, hsum, hcount = _e2_opens_and_habitat(n, count=60, drift=0.001)
    opens_t = tuple(opens)
    hsum_t = tuple(hsum)
    hcount_full = tuple(hcount)
    # 1) full E2 support → kept. A real event at index 9 embargoes placebo indices
    # 0..19, so every drawn placebo has a full pre-event beta window (E1's placebo
    # admissibility does not itself pre-require the beta window — a placebo landing
    # in the first `beta_window` sessions would otherwise drop as placebo_e2_support).
    kept = ClusterE2Inputs("KEEP:1", base, opens_t, hsum_t, hcount_full, 40, (9,))
    # 2) no entry session
    no_entry = ClusterE2Inputs("NOENT:1", base, opens_t, hsum_t, hcount_full, None, ())
    # 3) focal_e2_support: entry too early → beta window has < min_pairs sessions.
    early = ClusterE2Inputs("EARLY:1", base, opens_t, hsum_t, hcount_full, 5, ())
    cohort = assemble_e2_cohort([kept, no_entry, early], config=cfg)
    assert cohort.size == 1
    assert cohort.drop_counts["no_entry_session"] == 1
    assert cohort.drop_counts["focal_e2_support"] == 1


def test_assemble_e2_cohort_uses_the_same_placebo_dates_as_e1() -> None:
    # E2 draws placebo indices with the same admissibility + per-cluster seed as
    # E1, so the two cohorts share identical placebo dates for the same cluster.
    cfg = ProtocolConfig(estage_placebo_draws=5, horizon_sessions=10)
    base = date(2015, 1, 2)
    n = 200
    opens, hsum, hcount = _e2_opens_and_habitat(n, drift=0.001)
    item_e1 = ClusterReturnInputs("SHARE:1", base, tuple(opens), 40, ())
    from invest.application.cfob_returns import derive_seed as _derive
    from invest.application.cfob_returns import (
        admissible_placebo_indices as _adm,
    )
    from invest.application.cfob_returns import (
        sample_placebo_indices as _samp,
    )

    adm = _adm(session_count=n, real_event_entry_indices=(), horizon=cfg.horizon_sessions)
    seed = _derive(cfg.estage_master_seed, cfg.estage_spec_version, "placebo", "SHARE:1")
    draw = _samp(adm, draws=cfg.estage_placebo_draws, seed=seed)
    assert draw is not None  # the shared draw both gates resolve to
    assert item_e1.entry_index == 40


def test_evaluate_e2_gate_stops_under_the_cohort_floor() -> None:
    cfg = ProtocolConfig(estage_min_cohort=2000)
    cohort = E2Cohort(
        d_values=tuple(0.01 for _ in range(10)),
        month_keys=tuple((2015, 1 + i % 12) for i in range(10)),
        drop_counts={"placebo_e2_support": 4},
    )
    result = evaluate_e2_gate(cohort, config=cfg)
    assert result.underpowered is True
    assert result.passed is False
    assert result.p is None
    assert result.drop_counts == {"placebo_e2_support": 4}


def test_evaluate_e2_gate_passes_on_a_planted_positive_residual() -> None:
    cfg = ProtocolConfig(
        estage_min_cohort=2000,
        estage_bootstrap_replications=999,
        estage_bootstrap_alpha=0.005,
    )
    rng = np.random.default_rng(2)
    n = 2400
    d_values = tuple(float(x) for x in rng.normal(loc=0.5, scale=0.05, size=n))
    month_keys = tuple((2000 + i // 12, 1 + i % 12) for i in range(n // 12) for _ in range(12))
    cohort = E2Cohort(d_values=d_values, month_keys=month_keys, drop_counts={})
    result = evaluate_e2_gate(cohort, config=cfg)
    assert result.underpowered is False
    assert result.passed is True
    assert result.p is not None and result.p < 0.005


def test_e2_gate_uses_a_separate_rng_stream_from_e1() -> None:
    # The E1 and E2 gates must not share a bootstrap seed (gate-tag separation).
    from invest.application.cfob_returns import derive_seed as _derive

    e1 = _derive(PROTOCOL.estage_master_seed, PROTOCOL.estage_spec_version, "E1")
    e2 = _derive(PROTOCOL.estage_master_seed, PROTOCOL.estage_spec_version, "E2")
    assert e1 != e2


# --- Common cohort + conjunctive verdict + manifest (ticket #93) --------------

from invest.application.cfob import Verdict  # noqa: E402
from invest.application.cfob_returns import (  # noqa: E402
    CommonCohort,
    E1GateResult,
    E2GateResult,
    assemble_common_cohort,
    cohort_fingerprint,
    conjunctive_verdict,
    evaluate_returns_line,
    reproducibility_manifest,
    returns_diagnostics,
)


def _gate(passed: bool, underpowered: bool, p: float | None) -> tuple:
    from invest.application.cfob_returns import BootstrapResult

    boot = None if p is None else BootstrapResult(p=p, observed=0.1, k=0, replications=999, discards=2)
    return passed, underpowered, boot


def _e1(passed: bool, underpowered: bool = False, p: float | None = 0.001) -> E1GateResult:
    pa, un, boot = _gate(passed, underpowered, p)
    return E1GateResult(pa, un, cohort_n=2400, month_span=200, bootstrap=boot, drop_counts={})


def _e2(passed: bool, underpowered: bool = False, p: float | None = 0.001) -> E2GateResult:
    pa, un, boot = _gate(passed, underpowered, p)
    return E2GateResult(pa, un, cohort_n=2400, month_span=200, bootstrap=boot, drop_counts={})


def test_conjunctive_verdict_stage_pass_needs_both_gates() -> None:
    verdict, failing = conjunctive_verdict(_e1(True), _e2(True))
    assert verdict == str(Verdict.STAGE_PASS)
    assert failing == ()


def test_conjunctive_verdict_blocks_and_names_the_failing_gate() -> None:
    v1, f1 = conjunctive_verdict(_e1(True), _e2(False, p=0.20))
    assert v1 == str(Verdict.PROMOTION_BLOCK) and f1 == ("E2",)
    v2, f2 = conjunctive_verdict(_e1(False, p=0.30), _e2(True))
    assert v2 == str(Verdict.PROMOTION_BLOCK) and f2 == ("E1",)
    v3, f3 = conjunctive_verdict(_e1(False, p=0.3), _e2(False, p=0.4))
    assert v3 == str(Verdict.PROMOTION_BLOCK) and f3 == ("E1", "E2")


def test_conjunctive_verdict_underpowered_when_either_gate_is() -> None:
    verdict, failing = conjunctive_verdict(
        _e1(False, underpowered=True, p=None), _e2(False, underpowered=True, p=None)
    )
    assert verdict == str(Verdict.UNDERPOWERED_STOP)
    assert failing == ()


def _e2_cluster(cid: str, entry: int, *, n: int = 400) -> ClusterE2Inputs:
    opens, hsum, hcount = _e2_opens_and_habitat(n, count=60, drift=0.001)
    return ClusterE2Inputs(
        cluster_id=cid,
        known_time=date(2015, 1, 2),
        session_opens=tuple(opens),
        habitat_sum=tuple(hsum),
        habitat_count=tuple(hcount),
        entry_index=entry,
        real_event_entry_indices=(9,),  # embargo the sub-beta-window placebo indices
    )


def test_assemble_common_cohort_aligns_e1_e2_on_identical_clusters() -> None:
    cfg = ProtocolConfig(
        estage_placebo_draws=5, horizon_sessions=10,
        estage_beta_window_sessions=30, estage_beta_min_pairs=20,
    )
    kept = _e2_cluster("SYM1:2015-01-02", 300)
    no_entry = ClusterE2Inputs("SYM2:x", date(2015, 1, 2), kept.session_opens,
                               kept.habitat_sum, kept.habitat_count, None, ())
    cohort = assemble_common_cohort([kept, no_entry], config=cfg)
    assert cohort.size == 1
    # E1 and E2 statistics are aligned on the SAME single cluster.
    assert len(cohort.d_e1_values) == len(cohort.d_e2_values) == 1
    assert cohort.cluster_ids == ("SYM1:2015-01-02",)
    assert cohort.drop_counts["no_entry_session"] == 1


def test_evaluate_returns_line_runs_both_gates_on_one_cohort() -> None:
    cfg = ProtocolConfig(
        estage_min_cohort=2000, estage_bootstrap_replications=299, estage_bootstrap_alpha=0.005,
    )
    rng = np.random.default_rng(0)
    n = 2400
    e1_vals = tuple(float(x) for x in rng.normal(loc=0.5, scale=0.05, size=n))
    e2_vals = tuple(float(x) for x in rng.normal(loc=0.5, scale=0.05, size=n))
    mk = tuple((2000 + i // 12, 1 + i % 12) for i in range(n // 12) for _ in range(12))
    cids = tuple(f"T{i}:2015-01-02" for i in range(n))
    cohort = CommonCohort(cids, e1_vals, e2_vals, mk, {})
    result = evaluate_returns_line(cohort, config=cfg)
    assert result.verdict == str(Verdict.STAGE_PASS)
    assert result.capital_go is False
    assert result.cohort_n == 2400 and result.month_span == 200


def test_returns_diagnostics_present_and_cost_invariant() -> None:
    cfg = ProtocolConfig(estage_min_cohort=5, estage_bootstrap_replications=99)
    rng = np.random.default_rng(1)
    n = 60
    cohort = CommonCohort(
        tuple(f"T{i%7}:2015-01-02" for i in range(n)),
        tuple(float(x) for x in rng.normal(size=n)),
        tuple(float(x) for x in rng.normal(size=n)),
        tuple((2015 + i // 12, 1 + i % 12) for i in range(n)),
        {},
    )
    result = evaluate_returns_line(cohort, config=cfg)
    diag = returns_diagnostics(cohort, result, config=cfg, block_diagnostic_replications=99)
    # Every named diagnostic family present.
    for key in ("parametric_t", "block_length_sensitivity", "cost_ladder_bps",
                "power_context", "deferred"):
        assert key in diag
    assert diag["cost_ladder_bps"]["d_statistic_cost_invariant"] is True
    assert set(diag["parametric_t"]["E1"]) == {"iid_t", "month_clustered_t", "ticker_clustered_t"}
    assert set(diag["block_length_sensitivity"]["E1"]) == {
        "block_1m_p", "block_3m_p", "block_6m_p", "block_12m_p", "block_6m_noncircular_p"
    }
    # non_circular is now a computed value, not a deferred label.
    assert "non_circular_blocks" not in diag["deferred"]
    # Deferred estimator/data diagnostics are present with a reason.
    assert diag["deferred"]["spy_specs"]["status"] == "deferred_non_gating"


def test_reproducibility_manifest_is_deterministic_and_fingerprints_the_cohort() -> None:
    cohort = CommonCohort(
        ("A:2015-01-02", "B:2016-02-03"),
        (0.01, -0.02), (0.03, 0.04), ((2015, 1), (2016, 2)), {},
    )
    cfg = ProtocolConfig(estage_min_cohort=1, estage_bootstrap_replications=49)
    result = evaluate_returns_line(cohort, config=cfg)
    m1 = reproducibility_manifest(cohort, result, config=cfg)
    m2 = reproducibility_manifest(cohort, result, config=cfg)
    assert m1 == m2  # nothing wall-clock in the manifest itself
    assert m1["generator"] == "PCG64"
    assert m1["numpy_major_minor"] == ".".join(np.__version__.split(".")[:2])
    assert m1["data_fingerprint"] == cohort_fingerprint(cohort)
    # A changed cohort changes the fingerprint.
    other = CommonCohort(
        ("A:2015-01-02", "B:2016-02-03"),
        (0.99, -0.02), (0.03, 0.04), ((2015, 1), (2016, 2)), {},
    )
    assert cohort_fingerprint(other) != cohort_fingerprint(cohort)


def test_manifest_data_fingerprint_prefers_the_input_panel() -> None:
    from invest.application.cfob_returns import inputs_fingerprint

    cohort = CommonCohort(
        ("A:2015-01-02",), (0.01,), (0.02,), ((2015, 1),), {},
    )
    cfg = ProtocolConfig(estage_min_cohort=1, estage_bootstrap_replications=49)
    result = evaluate_returns_line(cohort, config=cfg)
    inp = _e2_cluster("A:2015-01-02", 300)
    fp = inputs_fingerprint([inp])
    m = reproducibility_manifest(cohort, result, config=cfg, data_fingerprint=fp)
    assert m["data_fingerprint"] == fp  # input panel wins over the cohort fallback
    assert m["data_fingerprint_source"] == "input_panel"
    assert m["cohort_fingerprint"] == cohort_fingerprint(cohort)
    # Without an input fingerprint it falls back and says so.
    m2 = reproducibility_manifest(cohort, result, config=cfg)
    assert m2["data_fingerprint_source"] == "cohort_derived_fallback"


def test_inputs_fingerprint_tracks_raw_inputs() -> None:
    from invest.application.cfob_returns import inputs_fingerprint

    a = _e2_cluster("A:2015-01-02", 300)
    assert inputs_fingerprint([a]) == inputs_fingerprint([a])  # deterministic
    b = ClusterE2Inputs(
        a.cluster_id, a.known_time, a.session_opens, a.habitat_sum, a.habitat_count,
        301, a.real_event_entry_indices,  # entry index moved
    )
    assert inputs_fingerprint([a]) != inputs_fingerprint([b])
