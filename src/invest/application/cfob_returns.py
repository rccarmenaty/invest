"""CFOB E1/E2 returns gates — pure inference primitives (ADR 0003).

The reusable statistical core shared by both gates of the two-gate conjunctive
funnel. Everything here is pure and deterministic given its seed: no I/O, no
clock, no global RNG. The driver supplies the cohort, the seeds, and the wiring.

Three primitives, each frozen in ADR 0003:
- ``winsorized_mean`` — the cohort estimator T(d), §3.
- ``stationary_block_bootstrap_p`` — the null-imposed circular Politis–Romano
  stationary block bootstrap that turns a cohort of per-cluster statistics into a
  one-sided p-value, §2.
- ``derive_seed`` — the SHA-256 serialization that separates the E1, E2, and
  placebo RNG streams, §6.

This module is research-only (needs the ``research-ml`` extra for numpy) and is
never imported by the production scan/backtest path.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

# --- T(d): winsorized mean (ADR 0003 §3) -------------------------------------


def winsorized_mean(values: Sequence[float] | NDArray[np.float64]) -> float:
    """The frozen cohort estimator T(d): equal-weight arithmetic mean after
    two-sided 1% winsorization (clip, never drop).

    For every sample handed to T — the observed cohort and every bootstrap
    replication — the empirical P1/P99 are recomputed from *that sample's own*
    values, so T is a single functional applied identically everywhere. float64
    throughout; ``method="linear"`` is named explicitly so a NumPy default change
    cannot silently alter the estimator. T is translation-equivariant:
    ``T(d + c) == T(d) + c``, which is what makes the null imposition exact.
    """

    v = np.asarray(values, dtype=np.float64)
    if v.size == 0:
        raise ValueError("winsorized_mean requires at least one value")
    if not np.all(np.isfinite(v)):
        raise ValueError("winsorized_mean requires finite (non-NaN, non-inf) values")
    q_low, q_high = np.quantile(v, [0.01, 0.99], method="linear")
    winsorized = np.clip(v, q_low, q_high)  # inclusive clip, no drops
    return float(winsorized.mean())  # equal weight — one vote per cluster


# --- Reproducibility contract (ADR 0003 §6) ----------------------------------


def derive_seed(
    master_seed: int,
    spec_version: str,
    gate_tag: str,
    *cluster_id: str,
) -> int:
    """Frozen SHA-256 serialization of ``(master seed, spec version, gate tag[,
    cluster id...])`` → a stream seed.

    E1, E2, and placebo streams are separated by ``gate_tag``; per-cluster
    placebo streams add the immutable cluster identifier(s). The serialization is
    length-prefixed field-by-field so distinct field boundaries can never collide
    (``"a","b"`` never hashes like ``"ab",""``).
    """

    hasher = hashlib.sha256()
    parts: tuple[str, ...] = (str(int(master_seed)), spec_version, gate_tag, *cluster_id)
    for part in parts:
        raw = part.encode("utf-8")
        hasher.update(len(raw).to_bytes(8, "big"))
        hasher.update(raw)
    return int.from_bytes(hasher.digest(), "big")


# --- Null-imposed circular block bootstrap (ADR 0003 §2) ---------------------


@dataclass(frozen=True)
class BootstrapResult:
    """Outcome of one gate's block-bootstrap test.

    ``p`` is the one-sided p-value ``(1 + k) / (replications + 1)``; ``observed``
    is θ̂ = T(d), the un-recentered cohort statistic the null distribution is
    tested against; ``k`` is the number of valid replications whose statistic was
    ≥ observed; ``discards`` counts zero-cluster paths that were discarded and
    regenerated (they never count toward ``replications``).
    """

    p: float
    observed: float
    k: int
    replications: int
    discards: int

    def to_dict(self) -> dict[str, float | int]:
        """Serialization for the reproducibility manifest / results artifact."""
        return {
            "p": self.p,
            "observed": self.observed,
            "k": self.k,
            "replications": self.replications,
            "discards": self.discards,
        }


def stationary_block_bootstrap_p(
    month_buckets: Sequence[Sequence[float]],
    *,
    statistic_fn: Callable[[NDArray[np.float64]], float] = winsorized_mean,
    q: float,
    replications: int,
    seed: int,
) -> BootstrapResult:
    """Null-imposed circular Politis–Romano stationary block bootstrap over the
    ordered sequence of known-time calendar-month buckets (ADR 0003 §2, §15).

    ``month_buckets`` is the complete ordered month sequence — **including empty
    months** — each bucket holding that month's per-cluster statistics ``d_i``.
    The month structure carries the real event-time clumping; a resampled month
    contributes *all* of its (recentered) clusters, so the bootstrap cluster
    count varies by replication.

    Mechanics:
    - θ̂ = ``statistic_fn`` over the pooled observed ``d_i``; the null is imposed
      by recentering every value to ``d_i - θ̂`` (translation-equivariance of the
      estimator makes the recentered cohort statistic 0 in expectation).
    - Each replication draws the original number of month positions: start at a
      uniform month, then at each step restart at a fresh uniform month with
      probability ``q`` or advance one **circular** month otherwise → geometric
      block lengths with expected length ``1/q`` months (frozen ``q = 1/6`` → 6).
    - A path that lands only on empty months (zero clusters) is discarded and
      regenerated; the discard count is recorded and such paths never count.
    - One-sided gate: ``k`` = valid replications with statistic ≥ θ̂;
      ``p = (1 + k) / (replications + 1)``.

    ``seed`` seeds a private ``Generator(PCG64)`` — the placebo dates are fixed
    inputs and are never redrawn inside a replication.
    """

    if replications < 1:
        raise ValueError("replications must be >= 1")
    if not 0.0 < q <= 1.0:
        # q is the geometric restart probability; outside (0, 1] the block
        # structure degenerates (q<=0 never restarts; q>1 is undefined).
        raise ValueError("q must be in (0, 1]")
    n_months = len(month_buckets)
    if n_months == 0:
        raise ValueError("month_buckets must contain at least one month")

    # Impose the null: recenter each month's values by θ̂ = T(pooled observed).
    bucket_arrays = [np.asarray(b, dtype=np.float64) for b in month_buckets]
    pooled = np.concatenate(bucket_arrays)
    if pooled.size == 0:
        raise ValueError("month_buckets contain no cluster statistics")
    observed = statistic_fn(pooled)
    recentered = [a - observed for a in bucket_arrays]

    rng = np.random.Generator(np.random.PCG64(seed))
    k = 0
    discards = 0
    valid = 0
    while valid < replications:
        # Draw n_months circular-stationary month positions.
        idx = np.empty(n_months, dtype=np.int64)
        idx[0] = rng.integers(n_months)
        for pos in range(1, n_months):
            if rng.random() < q:
                idx[pos] = rng.integers(n_months)
            else:
                idx[pos] = (idx[pos - 1] + 1) % n_months
        drawn = [recentered[i] for i in idx if recentered[i].size]
        if not drawn:
            discards += 1
            continue
        statistic = statistic_fn(np.concatenate(drawn))
        if statistic >= observed:
            k += 1
        valid += 1

    p = (1 + k) / (replications + 1)
    return BootstrapResult(
        p=p, observed=float(observed), k=k, replications=replications, discards=discards
    )
