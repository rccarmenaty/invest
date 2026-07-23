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
    assert set(d) == {"p", "observed", "k", "replications", "discards"}
    assert d["p"] == result.p


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


# --- E1 gate orchestration (ADR 0003 §1, §5) ---------------------------------

from datetime import date, timedelta  # noqa: E402

from invest.application.cfob import ProtocolConfig  # noqa: E402
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
