"""CFOB E1/E2 returns gates — pure inference primitives (ADR 0003).

The reusable statistical core shared by both gates of the two-gate conjunctive
funnel. Everything here is pure and deterministic given its seed: no I/O, no
clock, no global RNG. The driver supplies the cohort, the seeds, and the wiring.

Two layers:

- **Config-free primitives** (§2, §3, §6): ``winsorized_mean`` (the cohort
  estimator T(d)), ``stationary_block_bootstrap_p`` (the null-imposed circular
  Politis–Romano block bootstrap → one-sided p), and ``derive_seed`` (the
  SHA-256 serialization separating the E1/E2/placebo RNG streams).
- **E1 gate orchestration** (§1, §5): open-to-open net return, placebo embargo /
  admissibility, per-cluster ``d_i`` collapse, common-cohort assembly with a
  counted drop-reason ledger, and the E1 gate itself (block bootstrap on the
  cohort, ``underpowered_stop`` below the 2,000-cluster floor). This layer reads
  the frozen ``ProtocolConfig`` constants; the primitives above stay config-free.

This module is research-only (needs the ``research-ml`` extra for numpy) and is
never imported by the production scan/backtest path.
"""

from __future__ import annotations

import bisect
import hashlib
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
from numpy.typing import NDArray

from invest.application.cfob import PROTOCOL, ProtocolConfig

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


# --- E1 gate orchestration (ADR 0003 §1, §5) ---------------------------------


def resolve_entry_index(session_dates: Sequence[date], known_time: date) -> int | None:
    """Index of the entry session: the first session strictly after ``known_time``
    (the frozen ``next_open_after_filing_date`` entry rule). ``None`` when the
    known-time falls on or after the last session (no tradable entry)."""

    idx = bisect.bisect_right(session_dates, known_time)
    return idx if idx < len(session_dates) else None


def focal_net_return(
    session_opens: Sequence[float],
    entry_index: int,
    *,
    horizon: int,
    cost_bps: float,
) -> float | None:
    """Open-to-open ``horizon``-session simple return, net of one round-trip cost
    (ADR 0003 §1). Returns ``None`` when the forward window is incomplete — the
    date is then *inadmissible*, never truncated to a partial horizon."""

    exit_index = entry_index + horizon
    if entry_index < 0 or exit_index >= len(session_opens):
        return None
    entry_open = session_opens[entry_index]
    exit_open = session_opens[exit_index]
    gross = exit_open / entry_open - 1.0
    return gross - cost_bps / 10_000.0


def admissible_placebo_indices(
    *,
    session_count: int,
    real_event_entry_indices: Sequence[int],
    horizon: int,
) -> list[int]:
    """Entry-session indices admissible as placebo dates (ADR 0003 §5).

    A candidate is admissible when (a) it has a complete forward window and
    (b) its forward window does not intersect the forward window of *any*
    qualifying code-P insider event for the ticker. Two forward windows of equal
    length ``horizon`` intersect on entry-session index iff ``|c - r| <= horizon``,
    so a candidate is embargoed within ``horizon`` sessions either side of every
    real-event entry index (including events later dropped by de-overlap — the
    caller passes the full pre-de-overlap set)."""

    last_valid = session_count - horizon - 1  # inclusive; complete forward window
    if last_valid < 0:
        return []
    embargoed: set[int] = set()
    for r in real_event_entry_indices:
        embargoed.update(range(r - horizon, r + horizon + 1))
    return [c for c in range(last_valid + 1) if c not in embargoed]


def sample_placebo_indices(
    admissible: Sequence[int], *, draws: int, seed: int
) -> list[int] | None:
    """Exactly ``draws`` unique placebo entry indices, uniform without
    replacement (ADR 0003 §5). ``None`` when fewer than ``draws`` are admissible —
    the cluster is then excluded during common-cohort formation."""

    if len(admissible) < draws:
        return None
    rng = np.random.Generator(np.random.PCG64(seed))
    chosen = rng.choice(np.asarray(admissible, dtype=np.int64), size=draws, replace=False)
    return sorted(int(i) for i in chosen)


def cluster_d_statistic(
    session_opens: Sequence[float],
    entry_index: int,
    placebo_indices: Sequence[int],
    *,
    horizon: int,
    cost_bps: float,
) -> float | None:
    """The per-cluster E1 statistic ``d_i = R_obs^net - mean(R_placebo^net)``
    (ADR 0003 §1). ``None`` if the observed forward window is incomplete. Every
    placebo index is admissible by construction, so all placebo returns exist."""

    focal = focal_net_return(session_opens, entry_index, horizon=horizon, cost_bps=cost_bps)
    if focal is None:
        return None
    placebo = [
        focal_net_return(session_opens, i, horizon=horizon, cost_bps=cost_bps)
        for i in placebo_indices
    ]
    if any(p is None for p in placebo):
        # Every placebo index is admissible (complete forward window) by
        # construction; a None here means that invariant was violated upstream —
        # fail loud rather than silently averaging a shrunken set.
        raise ValueError("placebo index without a complete forward window")
    placebo_mean = float(np.mean(placebo))
    return focal - placebo_mean


def ordered_month_buckets(
    month_keys: Sequence[tuple[int, int]], d_values: Sequence[float]
) -> list[list[float]]:
    """Group ``d_values`` into the complete ordered sequence of ``(year, month)``
    buckets from the earliest to the latest known-time month **inclusive**, empty
    months included (ADR 0003 §2 — the bootstrap resamples over the full month
    span, so calendar gaps must be present as empty buckets)."""

    if not month_keys:
        return []
    lo, hi = min(month_keys), max(month_keys)
    span: list[tuple[int, int]] = []
    y, m = lo
    while (y, m) <= hi:
        span.append((y, m))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    position = {key: i for i, key in enumerate(span)}
    buckets: list[list[float]] = [[] for _ in span]
    for key, d in zip(month_keys, d_values, strict=True):
        buckets[position[key]].append(d)
    return buckets


@dataclass(frozen=True)
class ClusterReturnInputs:
    """One cluster's resolved inputs for the returns gates. ``entry_index`` is
    ``None`` when the known-time has no tradable entry session; the driver builds
    these from the loaded price panel and the per-ticker real-event catalogue."""

    cluster_id: str
    known_time: date
    session_opens: tuple[float, ...]
    entry_index: int | None
    real_event_entry_indices: tuple[int, ...]


def build_cluster_return_inputs(
    clusters: Sequence[tuple[str, date]],
    *,
    session_bars_by_symbol: Mapping[str, Sequence[tuple[date, float]]],
    real_event_known_times_by_symbol: Mapping[str, Sequence[date]],
) -> list[ClusterReturnInputs]:
    """Map loaded price bars + the per-ticker real-event catalogue into the pure
    ``ClusterReturnInputs`` the gates consume (ADR 0003 §1, §5).

    ``clusters`` are ``(trading_symbol, known_time)`` pairs; each cluster's
    identity (placebo seed key) is ``"symbol:known_time"``. Bars are ascending
    ``(session date, adjusted open)``. The real-event entry indices are resolved
    from *all* qualifying code-P event known-times for the ticker — the full
    pre-de-overlap set the embargo needs — dropping any with no tradable entry."""

    out: list[ClusterReturnInputs] = []
    for symbol, known_time in clusters:
        bars = session_bars_by_symbol.get(symbol, ())
        session_dates = [b[0] for b in bars]
        session_opens = tuple(float(b[1]) for b in bars)
        entry_index = resolve_entry_index(session_dates, known_time)
        real_events = real_event_known_times_by_symbol.get(symbol, ())
        real_indices = sorted(
            i
            for i in (resolve_entry_index(session_dates, t) for t in real_events)
            if i is not None
        )
        out.append(
            ClusterReturnInputs(
                cluster_id=f"{symbol}:{known_time.isoformat()}",
                known_time=known_time,
                session_opens=session_opens,
                entry_index=entry_index,
                real_event_entry_indices=tuple(real_indices),
            )
        )
    return out


@dataclass(frozen=True)
class E1Cohort:
    """The common frozen cohort as seen by E1: aligned per-cluster statistics and
    month keys, plus the counted drop-reason ledger (ADR 0003 §5 — every drop is
    counted, never silent)."""

    d_values: tuple[float, ...]
    month_keys: tuple[tuple[int, int], ...]
    drop_counts: Mapping[str, int]

    @property
    def size(self) -> int:
        return len(self.d_values)


def assemble_e1_cohort(
    inputs: Sequence[ClusterReturnInputs],
    *,
    config: ProtocolConfig = PROTOCOL,
) -> E1Cohort:
    """Resolve E1 support for every cluster and freeze the common cohort, counting
    each drop reason (ADR 0003 §5). Drop reasons: ``no_entry_session`` (known-time
    past the last session), ``insufficient_placebo`` (< ``draws`` admissible
    placebo dates), ``focal_window_incomplete`` (observed forward window runs off
    the panel)."""

    horizon = config.horizon_sessions
    cost_bps = config.estage_cost_bps
    draws = config.estage_placebo_draws
    drop_counts: dict[str, int] = defaultdict(int)
    d_values: list[float] = []
    month_keys: list[tuple[int, int]] = []

    for item in inputs:
        if item.entry_index is None:
            drop_counts["no_entry_session"] += 1
            continue
        admissible = admissible_placebo_indices(
            session_count=len(item.session_opens),
            real_event_entry_indices=item.real_event_entry_indices,
            horizon=horizon,
        )
        seed = derive_seed(
            config.estage_master_seed, config.estage_spec_version, "placebo", item.cluster_id
        )
        placebo = sample_placebo_indices(admissible, draws=draws, seed=seed)
        if placebo is None:
            drop_counts["insufficient_placebo"] += 1
            continue
        d = cluster_d_statistic(
            item.session_opens,
            item.entry_index,
            placebo,
            horizon=horizon,
            cost_bps=cost_bps,
        )
        if d is None:
            drop_counts["focal_window_incomplete"] += 1
            continue
        d_values.append(d)
        month_keys.append((item.known_time.year, item.known_time.month))

    return E1Cohort(
        d_values=tuple(d_values),
        month_keys=tuple(month_keys),
        drop_counts=dict(drop_counts),
    )


@dataclass(frozen=True)
class E1GateResult:
    """E1 gate outcome (ADR 0003 §1-3). E1 is provisional timing evidence: a green
    E1 (``passed``) advances the line but is *not* alpha — E2 is required for final
    acceptance (ticket #5 wires the conjunctive verdict). ``underpowered`` marks
    the sub-2,000-cluster operational floor, where no statistic is attempted."""

    passed: bool
    underpowered: bool
    cohort_n: int
    month_span: int
    bootstrap: BootstrapResult | None
    drop_counts: Mapping[str, int]

    @property
    def p(self) -> float | None:
        return None if self.bootstrap is None else self.bootstrap.p

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "underpowered": self.underpowered,
            "cohort_n": self.cohort_n,
            "month_span": self.month_span,
            "p": self.p,
            "bootstrap": None if self.bootstrap is None else self.bootstrap.to_dict(),
            "drop_counts": dict(self.drop_counts),
        }


def evaluate_e1_gate(cohort: E1Cohort, *, config: ProtocolConfig = PROTOCOL) -> E1GateResult:
    """Run the E1 gate on the frozen cohort (ADR 0003 §1-3). Below the
    ``estage_min_cohort`` floor the gate returns ``underpowered_stop`` and attempts
    no statistic; otherwise it runs the null-imposed block bootstrap and passes
    when ``p <= estage_bootstrap_alpha``."""

    buckets = ordered_month_buckets(cohort.month_keys, cohort.d_values)
    if cohort.size < config.estage_min_cohort:
        return E1GateResult(
            passed=False,
            underpowered=True,
            cohort_n=cohort.size,
            month_span=len(buckets),
            bootstrap=None,
            drop_counts=cohort.drop_counts,
        )
    seed = derive_seed(config.estage_master_seed, config.estage_spec_version, "E1")
    boot = stationary_block_bootstrap_p(
        buckets,
        q=config.estage_block_restart_q,
        replications=config.estage_bootstrap_replications,
        seed=seed,
    )
    return E1GateResult(
        passed=boot.p <= config.estage_bootstrap_alpha,
        underpowered=False,
        cohort_n=cohort.size,
        month_span=len(buckets),
        bootstrap=boot,
        drop_counts=cohort.drop_counts,
    )
