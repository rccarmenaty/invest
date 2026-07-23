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
