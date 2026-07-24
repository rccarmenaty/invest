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
- **E2 gate orchestration** (§4, §5): the habitat leave-one-out daily factor,
  the date-specific pre-event OLS beta (252 sessions, ≥200 pairs), the
  per-daily-compounded beta benchmark, the benchmark residual ``e``, per-cluster
  ``d_i^E2`` collapse, and the E2 gate — the *same* null-imposed block bootstrap
  on the *same* frozen cohort as E1, with E2-specific support drops counted.

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

from invest.application.cfob import PROTOCOL, ProtocolConfig, Verdict

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
    index_hash: str = ""

    def to_dict(self) -> dict[str, float | int | str]:
        """Serialization for the reproducibility manifest / results artifact."""
        return {
            "p": self.p,
            "observed": self.observed,
            "k": self.k,
            "replications": self.replications,
            "discards": self.discards,
            "index_hash": self.index_hash,
        }


def stationary_block_bootstrap_p(
    month_buckets: Sequence[Sequence[float]],
    *,
    statistic_fn: Callable[[NDArray[np.float64]], float] = winsorized_mean,
    q: float,
    replications: int,
    seed: int,
    circular: bool = True,
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
    index_hasher = hashlib.sha256()
    while valid < replications:
        # Draw n_months stationary month positions. Default is **circular** (blocks
        # wrap past the last month); the non-gating ``circular=False`` diagnostic
        # restarts instead of wrapping so a block never straddles the calendar end.
        idx = np.empty(n_months, dtype=np.int64)
        idx[0] = rng.integers(n_months)
        for pos in range(1, n_months):
            nxt = idx[pos - 1] + 1
            if rng.random() < q or (not circular and nxt >= n_months):
                idx[pos] = rng.integers(n_months)
            else:
                idx[pos] = nxt % n_months if circular else nxt
        drawn = [recentered[i] for i in idx if recentered[i].size]
        if not drawn:
            discards += 1
            continue
        index_hasher.update(idx.tobytes())  # pin the realized resample, in draw order
        statistic = statistic_fn(np.concatenate(drawn))
        if statistic >= observed:
            k += 1
        valid += 1

    p = (1 + k) / (replications + 1)
    return BootstrapResult(
        p=p,
        observed=float(observed),
        k=k,
        replications=replications,
        discards=discards,
        index_hash=index_hasher.hexdigest(),
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


# --- E2 gate: habitat LOO factor, pre-event beta, benchmark residual (§4) -----


def loo_factor(sum_r: float, count: int, r_focal: float) -> float:
    """The daily leave-one-out equal-weight habitat return with the focal name
    removed (ADR 0003 §4): ``(sum_r − r_focal) / (count − 1)``.

    ``sum_r`` is the sum of that session's daily returns over the ``count``
    point-in-time-eligible habitat names *including* the focal, so removing the
    focal's own return ``r_focal`` and averaging over the remaining ``count − 1``
    names gives a control that never includes the ticker being tested (no
    self-inclusion). Requires ``count ≥ 2`` — a single-name habitat has no
    non-focal average.
    """

    if count < 2:
        raise ValueError("loo_factor requires count >= 2 (at least one non-focal name)")
    return (sum_r - r_focal) / (count - 1)


def _daily_open_returns(session_opens: Sequence[float]) -> NDArray[np.float64]:
    """Per-session open-to-open daily simple returns ``open[s+1]/open[s] − 1``
    (length ``n − 1``, indexed by the starting session ``s``)."""

    o = np.asarray(session_opens, dtype=np.float64)
    return o[1:] / o[:-1] - 1.0


def factor_daily_returns(
    session_opens: Sequence[float],
    habitat_sum: Sequence[float],
    habitat_count: Sequence[int],
    *,
    breadth_floor: int,
) -> NDArray[np.float64]:
    """The per-session habitat LOO daily factor for one focal (ADR 0003 §4, §5),
    aligned to the daily-return index ``s`` (session ``s → s+1``), ``NaN`` where
    the breadth floor is not met.

    ``habitat_sum[s]`` / ``habitat_count[s]`` are the focal-inclusive habitat
    daily-return sum and PIT-eligible name count for session ``s``. A session is
    factor-valid only when it carries **≥ ``breadth_floor`` distinct non-focal
    names** — i.e. ``count − 1 ≥ breadth_floor`` (ADR 0002/0003: "≥50 distinct
    PIT-eligible non-focal names"); below that the observation is **missing**
    (``NaN``), never zero-filled or imputed. This is the asymmetric handling: a
    missing day inside the beta window simply drops that pair (the ≥200-pair rule
    governs), while every forward session must be non-missing for a date to be
    admissible.
    """

    o = np.asarray(session_opens, dtype=np.float64)
    n = o.size
    if n < 2:
        return np.empty(0, dtype=np.float64)
    s = np.asarray(habitat_sum, dtype=np.float64)[: n - 1]
    c = np.asarray(habitat_count, dtype=np.int64)[: n - 1]
    r_focal = o[1:] / o[:-1] - 1.0
    non_focal = c - 1  # focal excluded from the average — no self-inclusion
    valid = non_focal >= breadth_floor
    out = np.full(n - 1, np.nan, dtype=np.float64)
    # Same arithmetic as loo_factor, vectorized; only evaluated where valid so a
    # below-floor count (which could be 0 or 1) never divides by zero.
    idx = np.flatnonzero(valid)
    out[idx] = (s[idx] - r_focal[idx]) / (c[idx] - 1)
    return out


def ols_beta(
    focal_returns: Sequence[float] | NDArray[np.float64],
    factor_returns: Sequence[float] | NDArray[np.float64],
    *,
    min_pairs: int,
) -> float | None:
    """Single-factor OLS slope **with intercept** of focal on factor daily returns
    (ADR 0003 §4) — the frozen pre-event beta.

    Non-finite pairs (a factor ``NaN`` from a below-breadth day, or a missing
    focal return) are dropped; the fit needs **≥ ``min_pairs`` valid pairs**
    (frozen 200) or it returns ``None`` (no imputation, no backward extension —
    the caller passes exactly the 252-session window). Returns ``None`` on a
    degenerate zero-variance factor (beta unidentified). The closed-form slope
    ``cov(x, y) / var(x)`` equals ``numpy.polyfit(x, y, 1)[0]``.
    """

    y = np.asarray(focal_returns, dtype=np.float64)
    x = np.asarray(factor_returns, dtype=np.float64)
    if x.shape != y.shape:
        raise ValueError("focal and factor return series must have the same length")
    mask = np.isfinite(x) & np.isfinite(y)
    if int(mask.sum()) < min_pairs:
        return None
    xm = x[mask]
    ym = y[mask]
    xc = xm - xm.mean()
    denom = float(xc @ xc)
    if denom == 0.0:
        return None
    return float((xc @ (ym - ym.mean())) / denom)


def beta_benchmark(beta: float, h_forward: Sequence[float] | NDArray[np.float64]) -> float:
    """The habitat benchmark ``∏_{s} (1 + β·h_s) − 1`` (ADR 0003 §4): beta is
    applied to **each daily habitat return before compounding**, *not* the naive
    ``β·[∏(1+h_s) − 1]`` approximation. **No intercept** in the primary benchmark
    (the within-ticker observed-minus-placebo construction removes the ticker's
    unconditional drift/alpha; subtracting α̂ too would double-count)."""

    factors = 1.0 + beta * np.asarray(h_forward, dtype=np.float64)
    return float(np.prod(factors) - 1.0)


def date_e2_residual(
    session_opens: Sequence[float],
    focal_daily: NDArray[np.float64],
    factor: NDArray[np.float64],
    entry_index: int,
    *,
    horizon: int,
    cost_bps: float,
    beta_window: int,
    min_pairs: int,
) -> float | None:
    """The benchmark residual ``e = R^net − B^β`` for one entry date (ADR 0003
    §4). ``None`` — the date is **inadmissible** for E2 — when the focal forward
    window is incomplete, any of the ``horizon`` forward factor days is missing
    (below breadth), or the pre-event beta cannot be estimated (< ``min_pairs``
    valid pairs in the 252-session window)."""

    focal_net = focal_net_return(session_opens, entry_index, horizon=horizon, cost_bps=cost_bps)
    if focal_net is None:
        return None
    forward = factor[entry_index : entry_index + horizon]
    if forward.size < horizon or not bool(np.all(np.isfinite(forward))):
        # Every one of the 60 forward sessions must clear the breadth floor.
        return None
    # The beta window ends at the last daily return completed *before* the entry
    # open (ADR 0003 §4 — the window "ends on the previous session" for a filing
    # date). The return ending at the entry open (index ``entry_index - 1``) spans
    # the filing-reaction gap, so it is excluded; ``beta_end`` is its exclusive
    # upper bound and the 252-session window is the returns immediately before it.
    beta_end = max(0, entry_index - 1)
    lo = max(0, beta_end - beta_window)  # no backward extension past the panel
    beta = ols_beta(focal_daily[lo:beta_end], factor[lo:beta_end], min_pairs=min_pairs)
    if beta is None:
        return None
    return focal_net - beta_benchmark(beta, forward)


@dataclass(frozen=True)
class ClusterE2Inputs:
    """One cluster's resolved inputs for the E2 gate: the E1 price/entry inputs
    plus the aligned focal-inclusive habitat daily aggregate (``habitat_sum`` /
    ``habitat_count`` indexed by daily-return start session ``s``)."""

    cluster_id: str
    known_time: date
    session_opens: tuple[float, ...]
    habitat_sum: tuple[float, ...]
    habitat_count: tuple[int, ...]
    entry_index: int | None
    real_event_entry_indices: tuple[int, ...]


def build_cluster_e2_inputs(
    clusters: Sequence[tuple[str, date]],
    *,
    session_bars_by_symbol: Mapping[str, Sequence[tuple[date, float]]],
    real_event_known_times_by_symbol: Mapping[str, Sequence[date]],
    habitat_daily_by_date: Mapping[date, tuple[float, int]],
) -> list[ClusterE2Inputs]:
    """Map loaded price bars + the per-ticker real-event catalogue + the cached
    daily habitat aggregate into the pure ``ClusterE2Inputs`` the E2 gate consumes
    (ADR 0003 §4, §5).

    ``habitat_daily_by_date`` is the reused per-session ``date → (sum_r, count)``
    focal-inclusive aggregate; a cluster's ``habitat_sum`` / ``habitat_count`` are
    it, aligned by the symbol's own session dates (missing sessions default to
    ``(0.0, 0)`` → below the breadth floor → a ``NaN`` factor day). The
    ``cluster_id`` matches ``build_cluster_return_inputs`` so the per-cluster
    placebo seed — and therefore the drawn placebo dates — are identical to E1's."""

    out: list[ClusterE2Inputs] = []
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
        aggregate = [habitat_daily_by_date.get(day, (0.0, 0)) for day in session_dates]
        out.append(
            ClusterE2Inputs(
                cluster_id=f"{symbol}:{known_time.isoformat()}",
                known_time=known_time,
                session_opens=session_opens,
                habitat_sum=tuple(float(a[0]) for a in aggregate),
                habitat_count=tuple(int(a[1]) for a in aggregate),
                entry_index=entry_index,
                real_event_entry_indices=tuple(real_indices),
            )
        )
    return out


@dataclass(frozen=True)
class E2Cohort:
    """The common frozen cohort as seen by E2 (ADR 0003 §4, §5). Same clusters and
    same placebo draws as E1; the ledger adds E2-specific support drops.

    E2 support (beta ≥200 pairs, all 60 forward breadth days present) is a
    numerical data-support requirement resolved on the E1 cohort — not survivor
    selection or reranking between gates. In the frozen design these drops would
    be resolved jointly at cohort formation; they are counted here so the E2
    cohort is auditable against E1's."""

    d_values: tuple[float, ...]
    month_keys: tuple[tuple[int, int], ...]
    drop_counts: Mapping[str, int]

    @property
    def size(self) -> int:
        return len(self.d_values)


def assemble_e2_cohort(
    inputs: Sequence[ClusterE2Inputs],
    *,
    config: ProtocolConfig = PROTOCOL,
) -> E2Cohort:
    """Resolve E2 support on the common frozen cohort and collapse each cluster to
    ``d_i^E2 = e_obs − mean(e_placebo)`` (ADR 0003 §4, §5).

    The placebo dates are drawn with the *same* admissibility and *same* per-cluster
    seed as E1, so the E2 cohort's placebo dates are identical to E1's. Drop
    reasons: the three E1 support reasons (``no_entry_session`` /
    ``insufficient_placebo`` / ``focal_window_incomplete``) plus two E2-specific
    ones — ``focal_e2_support`` (observed date has no beta or a broken forward
    breadth window) and ``placebo_e2_support`` (some placebo date lacks E2
    support)."""

    horizon = config.horizon_sessions
    cost_bps = config.estage_cost_bps
    draws = config.estage_placebo_draws
    beta_window = config.estage_beta_window_sessions
    min_pairs = config.estage_beta_min_pairs
    breadth_floor = config.estage_factor_breadth_floor
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

        focal_daily = _daily_open_returns(item.session_opens)
        factor = factor_daily_returns(
            item.session_opens,
            item.habitat_sum,
            item.habitat_count,
            breadth_floor=breadth_floor,
        )

        # Observed-date focal window (E1's admissibility) then E2 support.
        e_obs = date_e2_residual(
            item.session_opens,
            focal_daily,
            factor,
            item.entry_index,
            horizon=horizon,
            cost_bps=cost_bps,
            beta_window=beta_window,
            min_pairs=min_pairs,
        )
        if e_obs is None:
            # Distinguish "focal forward window runs off the panel" (an E1 drop
            # reason) from "E2 beta/breadth support missing".
            if focal_net_return(
                item.session_opens, item.entry_index, horizon=horizon, cost_bps=cost_bps
            ) is None:
                drop_counts["focal_window_incomplete"] += 1
            else:
                drop_counts["focal_e2_support"] += 1
            continue

        placebo_residuals = [
            date_e2_residual(
                item.session_opens,
                focal_daily,
                factor,
                i,
                horizon=horizon,
                cost_bps=cost_bps,
                beta_window=beta_window,
                min_pairs=min_pairs,
            )
            for i in placebo
        ]
        if any(r is None for r in placebo_residuals):
            drop_counts["placebo_e2_support"] += 1
            continue

        d = e_obs - float(np.mean(placebo_residuals))
        d_values.append(d)
        month_keys.append((item.known_time.year, item.known_time.month))

    return E2Cohort(
        d_values=tuple(d_values),
        month_keys=tuple(month_keys),
        drop_counts=dict(drop_counts),
    )


@dataclass(frozen=True)
class E2GateResult:
    """E2 gate outcome (ADR 0003 §4). E2 is the acceptance gate: a green E1 **and**
    green E2 on the same cohort accept the line (ticket #5 wires the conjunctive
    verdict). ``underpowered`` marks the sub-2,000-cluster operational floor."""

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


def evaluate_e2_gate(cohort: E2Cohort, *, config: ProtocolConfig = PROTOCOL) -> E2GateResult:
    """Run the E2 gate on the frozen cohort (ADR 0003 §4) — the **same** null-imposed
    circular block bootstrap as E1, on its own separated RNG stream (gate tag
    ``"E2"``). Below the ``estage_min_cohort`` floor it returns ``underpowered_stop``
    and attempts no statistic; otherwise it passes when ``p ≤ estage_bootstrap_alpha``."""

    buckets = ordered_month_buckets(cohort.month_keys, cohort.d_values)
    if cohort.size < config.estage_min_cohort:
        return E2GateResult(
            passed=False,
            underpowered=True,
            cohort_n=cohort.size,
            month_span=len(buckets),
            bootstrap=None,
            drop_counts=cohort.drop_counts,
        )
    seed = derive_seed(config.estage_master_seed, config.estage_spec_version, "E2")
    boot = stationary_block_bootstrap_p(
        buckets,
        q=config.estage_block_restart_q,
        replications=config.estage_bootstrap_replications,
        seed=seed,
    )
    return E2GateResult(
        passed=boot.p <= config.estage_bootstrap_alpha,
        underpowered=False,
        cohort_n=cohort.size,
        month_span=len(buckets),
        bootstrap=boot,
        drop_counts=cohort.drop_counts,
    )


# --- One common frozen cohort + conjunctive verdict (§Roles, §5, ticket #93) --


@dataclass(frozen=True)
class CommonCohort:
    """The single common frozen cohort both gates run on (ADR 0003 §5): one cluster
    set with **aligned** E1 and E2 per-cluster statistics and a *single* drop-reason
    ledger. A cluster is admitted only when it has full support for **both** gates
    (entry, ≥100 placebo dates, complete observed+placebo focal windows, and — for
    E2 — a pre-event beta and full forward breadth on every one of those dates), so
    E1 and E2 measure the identical clusters. This is the frozen "resolve all
    support before inference, no post-E1 exclusion" design — not a per-gate subset."""

    cluster_ids: tuple[str, ...]
    d_e1_values: tuple[float, ...]
    d_e2_values: tuple[float, ...]
    month_keys: tuple[tuple[int, int], ...]
    drop_counts: Mapping[str, int]

    @property
    def size(self) -> int:
        return len(self.cluster_ids)

    def e1_cohort(self) -> E1Cohort:
        return E1Cohort(self.d_e1_values, self.month_keys, self.drop_counts)

    def e2_cohort(self) -> E2Cohort:
        return E2Cohort(self.d_e2_values, self.month_keys, self.drop_counts)


def assemble_common_cohort(
    inputs: Sequence[ClusterE2Inputs],
    *,
    config: ProtocolConfig = PROTOCOL,
) -> CommonCohort:
    """Freeze the one common cohort, resolving E1 **and** E2 support in a single
    pass so both gates measure identical clusters (ADR 0003 §5).

    Each admitted cluster contributes a matched pair ``(d_i^E1, d_i^E2)`` computed
    over the *same* placebo draws (same admissibility + per-cluster seed as the
    standalone gates). One counted ledger, drop reasons in resolution order:
    ``no_entry_session`` → ``insufficient_placebo`` → ``focal_window_incomplete``
    (observed or a placebo focal window runs off the panel) → ``focal_e2_support``
    (observed date lacks a beta or full forward breadth) → ``placebo_e2_support``
    (some placebo date lacks E2 support)."""

    horizon = config.horizon_sessions
    cost_bps = config.estage_cost_bps
    draws = config.estage_placebo_draws
    beta_window = config.estage_beta_window_sessions
    min_pairs = config.estage_beta_min_pairs
    breadth_floor = config.estage_factor_breadth_floor
    drop_counts: dict[str, int] = defaultdict(int)
    cluster_ids: list[str] = []
    d_e1: list[float] = []
    d_e2: list[float] = []
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

        # E1 leg: focal net returns (cost cancels in the placebo difference, but is
        # applied to every leg for the frozen return convention).
        d1 = cluster_d_statistic(
            item.session_opens, item.entry_index, placebo, horizon=horizon, cost_bps=cost_bps
        )
        if d1 is None:
            drop_counts["focal_window_incomplete"] += 1
            continue

        # E2 leg: benchmark residuals over the same placebo dates.
        focal_daily = _daily_open_returns(item.session_opens)
        factor = factor_daily_returns(
            item.session_opens, item.habitat_sum, item.habitat_count, breadth_floor=breadth_floor
        )
        e_obs = date_e2_residual(
            item.session_opens, focal_daily, factor, item.entry_index,
            horizon=horizon, cost_bps=cost_bps, beta_window=beta_window, min_pairs=min_pairs,
        )
        if e_obs is None:
            drop_counts["focal_e2_support"] += 1
            continue
        e_placebo = [
            date_e2_residual(
                item.session_opens, focal_daily, factor, i,
                horizon=horizon, cost_bps=cost_bps, beta_window=beta_window, min_pairs=min_pairs,
            )
            for i in placebo
        ]
        if any(e is None for e in e_placebo):
            drop_counts["placebo_e2_support"] += 1
            continue

        cluster_ids.append(item.cluster_id)
        d_e1.append(d1)
        d_e2.append(e_obs - float(np.mean(e_placebo)))
        month_keys.append((item.known_time.year, item.known_time.month))

    return CommonCohort(
        cluster_ids=tuple(cluster_ids),
        d_e1_values=tuple(d_e1),
        d_e2_values=tuple(d_e2),
        month_keys=tuple(month_keys),
        drop_counts=dict(drop_counts),
    )


def conjunctive_verdict(e1: E1GateResult, e2: E2GateResult) -> tuple[str, tuple[str, ...]]:
    """The dual-gate verdict on the common cohort (ADR 0003 §Roles): ``stage_pass``
    only when **both** gates clear (``passed``); ``underpowered_stop`` when the
    cohort is below the 2,000 floor (both gates report ``underpowered``); otherwise
    ``promotion_block`` naming the failing gate(s). Returns ``(verdict, failing)``
    where ``failing`` lists the red gate tags (empty on pass/underpowered).
    ``capital_go`` is never decided here — it stays a separate human call."""

    if e1.underpowered or e2.underpowered:
        return str(Verdict.UNDERPOWERED_STOP), ()
    if e1.passed and e2.passed:
        return str(Verdict.STAGE_PASS), ()
    failing = tuple(tag for tag, res in (("E1", e1), ("E2", e2)) if not res.passed)
    return str(Verdict.PROMOTION_BLOCK), failing


@dataclass(frozen=True)
class ReturnsLineResult:
    """The closed-out E1/E2 returns-line outcome on the common frozen cohort
    (ticket #93). ``capital_go`` is false by construction — a green ``stage_pass``
    authorizes one predeclared next step, never capital."""

    verdict: str
    failing_gates: tuple[str, ...]
    cohort_n: int
    month_span: int
    e1: E1GateResult
    e2: E2GateResult
    capital_go: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "verdict": self.verdict,
            "failing_gates": list(self.failing_gates),
            "capital_go": self.capital_go,
            "cohort_n": self.cohort_n,
            "month_span": self.month_span,
            "e1": self.e1.to_dict(),
            "e2": self.e2.to_dict(),
        }


def evaluate_returns_line(
    cohort: CommonCohort, *, config: ProtocolConfig = PROTOCOL
) -> ReturnsLineResult:
    """Run both gates on the one common cohort and collapse to the conjunctive
    verdict (ADR 0003 §Roles, ticket #93). Both gates see the identical cluster set
    and month structure; only their per-cluster statistic differs."""

    e1 = evaluate_e1_gate(cohort.e1_cohort(), config=config)
    e2 = evaluate_e2_gate(cohort.e2_cohort(), config=config)
    verdict, failing = conjunctive_verdict(e1, e2)
    return ReturnsLineResult(
        verdict=verdict,
        failing_gates=failing,
        cohort_n=cohort.size,
        month_span=e1.month_span,
        e1=e1,
        e2=e2,
    )


# --- Non-gating diagnostics + reproducibility manifest (§2, §4, §6, #93) ------


def _iid_t(values: NDArray[np.float64]) -> float | None:
    """One-sample iid t = mean / (s / √n), ddof=1. ``None`` for n<2 or zero spread."""
    n = values.size
    if n < 2:
        return None
    sd = float(values.std(ddof=1))
    if sd == 0.0:
        return None
    return float(values.mean() / (sd / np.sqrt(n)))


def _clustered_t(values: NDArray[np.float64], cluster_keys: Sequence[object]) -> float | None:
    """Cluster-robust one-sample t for the mean: θ̂ = mean(d), with a CR0 variance
    over the clusters (each cluster's residuals summed), small-cluster corrected.
    ``None`` for <2 clusters or zero clustered variance — a non-gating diagnostic
    that (unlike the block bootstrap) assumes the cluster is the only dependence."""
    n = values.size
    if n < 2:
        return None
    theta = float(values.mean())
    resid = values - theta
    by_cluster: dict[object, float] = defaultdict(float)
    for key, r in zip(cluster_keys, resid, strict=True):
        by_cluster[key] += float(r)
    m = len(by_cluster)
    if m < 2:
        return None
    meat = sum(g * g for g in by_cluster.values())
    var = meat / (n * n) * (m / (m - 1))
    if var <= 0.0:
        return None
    return theta / float(np.sqrt(var))


def _diagnostic_t_block(
    d_values: tuple[float, ...], cluster_ids: tuple[str, ...], month_keys: tuple[tuple[int, int], ...]
) -> dict[str, float | None]:
    """Parametric t diagnostics for one gate's statistic (all non-gating): iid,
    month-clustered, and ticker-clustered. The block bootstrap remains the gate;
    these under-state the calendar-overlap dependence and are shown for contrast."""
    values = np.asarray(d_values, dtype=np.float64)
    tickers = [cid.rsplit(":", 1)[0] for cid in cluster_ids]
    return {
        "iid_t": _iid_t(values),
        "month_clustered_t": _clustered_t(values, list(month_keys)),
        "ticker_clustered_t": _clustered_t(values, tickers),
    }


def _bootstrap_block_sensitivity(
    d_values: tuple[float, ...],
    month_keys: tuple[tuple[int, int], ...],
    *,
    gate_tag: str,
    config: ProtocolConfig,
    replications: int,
) -> dict[str, float]:
    """Block-length sensitivity (non-gating, ADR 0003 §2): the same circular
    stationary bootstrap p at expected block lengths 1 / 3 / 6 / 12 months
    (``q = 1/L``), at a reduced diagnostic replication count. The frozen gate uses
    exactly 6 months at the full ``estage_bootstrap_replications``."""
    if not d_values:
        return {}
    buckets = ordered_month_buckets(month_keys, d_values)
    out: dict[str, float] = {}
    for months in (1, 3, 6, 12):
        seed = derive_seed(
            config.estage_master_seed, config.estage_spec_version, f"{gate_tag}-diag-block{months}"
        )
        boot = stationary_block_bootstrap_p(
            buckets, q=1.0 / months, replications=replications, seed=seed
        )
        out[f"block_{months}m_p"] = boot.p
    # Non-circular (truncated) blocks at the frozen 6-month expected length: the
    # same resample but blocks never wrap past the calendar end (non-gating).
    nc_seed = derive_seed(
        config.estage_master_seed, config.estage_spec_version, f"{gate_tag}-diag-noncircular6"
    )
    out["block_6m_noncircular_p"] = stationary_block_bootstrap_p(
        buckets, q=1.0 / 6.0, replications=replications, seed=nc_seed, circular=False
    ).p
    return out


def _crisis_concentration(month_keys: tuple[tuple[int, int], ...]) -> dict[str, float]:
    """Power-context: the single-year maximum share of clusters and the combined
    2008+2020 crisis share — the calendar clumping the block bootstrap exists to
    price (ADR 0003 §2, §3)."""
    if not month_keys:
        return {"max_year_share": 0.0, "crisis_2008_2020_share": 0.0}
    by_year: dict[int, int] = defaultdict(int)
    for year, _month in month_keys:
        by_year[year] += 1
    n = len(month_keys)
    crisis = by_year.get(2008, 0) + by_year.get(2020, 0)
    return {
        "max_year_share": max(by_year.values()) / n,
        "crisis_2008_2020_share": crisis / n,
    }


def returns_diagnostics(
    cohort: CommonCohort,
    result: ReturnsLineResult,
    *,
    config: ProtocolConfig = PROTOCOL,
    block_diagnostic_replications: int = 9_999,
) -> dict[str, object]:
    """The full non-gating diagnostics block (ADR 0003 §2, §4; ticket #93).

    Computed here (cheap, pure): parametric iid / month-clustered / ticker-clustered
    t for both gates, block-length sensitivity (1/3/6/12 months), the cost ladder's
    invariance, ``d_i`` dispersion, month span, crisis concentration, and the
    bootstrap zero-cluster discard counts. Diagnostics that need an estimator or a
    data panel outside this build (non-circular blocks, the Politis–White selector,
    the intercept-inclusive / log-return / unit-beta / SPY benchmark variants, the
    universe-excess leg) are present as structured entries flagged
    ``deferred_non_gating`` with the reason — the block is complete, the values
    honest about entitlement."""

    e1_discards = None if result.e1.bootstrap is None else result.e1.bootstrap.discards
    e2_discards = None if result.e2.bootstrap is None else result.e2.bootstrap.discards
    deferred = "deferred_non_gating"
    return {
        "parametric_t": {
            "E1": _diagnostic_t_block(cohort.d_e1_values, cohort.cluster_ids, cohort.month_keys),
            "E2": _diagnostic_t_block(cohort.d_e2_values, cohort.cluster_ids, cohort.month_keys),
            "note": "clustered/iid t under-state the calendar-overlap dependence; "
            "the circular block bootstrap is the gate.",
        },
        "block_length_sensitivity": {
            "replications": block_diagnostic_replications,
            "E1": _bootstrap_block_sensitivity(
                cohort.d_e1_values, cohort.month_keys, gate_tag="E1",
                config=config, replications=block_diagnostic_replications,
            ),
            "E2": _bootstrap_block_sensitivity(
                cohort.d_e2_values, cohort.month_keys, gate_tag="E2",
                config=config, replications=block_diagnostic_replications,
            ),
        },
        "cost_ladder_bps": {
            "ladder": list(config.estage_cost_ladder_bps),
            "primary": config.estage_cost_bps,
            "d_statistic_cost_invariant": True,
            "note": "the round-trip cost is applied to the observed and every placebo "
            "leg alike, so it cancels in d_i = obs_net − mean(placebo_net); the ladder "
            "moves only the raw return level, not the gate statistic.",
        },
        "power_context": {
            "cohort_n": cohort.size,
            "month_span": result.month_span,
            "d_i_dispersion": {
                "E1_std": float(np.asarray(cohort.d_e1_values).std(ddof=1))
                if cohort.size > 1 else None,
                "E2_std": float(np.asarray(cohort.d_e2_values).std(ddof=1))
                if cohort.size > 1 else None,
            },
            "zero_cluster_discards": {"E1": e1_discards, "E2": e2_discards},
            **_crisis_concentration(cohort.month_keys),
        },
        "deferred": {
            "politis_white_selector": {"method": "corrected Politis–White block-length "
                "selector", "status": deferred, "reason": "the frozen block length is "
                "predeclared 6 months; the data-driven selector is a full-panel report, "
                "computed alongside the artifact when the SEP panel is present"},
            "intercept_inclusive_benchmark": {"method": "∏(1+α̂+β̂h)−1", "status": deferred,
                "reason": "needs a re-collapsed per-cluster residual cohort (raw returns "
                "not retained in the frozen d_i cohort); computed in the full-panel run"},
            "log_return_residual": {"method": "log-return residualization", "status": deferred,
                "reason": "needs the per-cluster raw returns (full-panel run)"},
            "unit_beta_habitat": {"method": "β=1 habitat subtraction", "status": deferred,
                "reason": "needs the per-cluster raw returns (full-panel run)"},
            "spy_specs": {"method": "SPY-based market benchmark", "status": deferred,
                "reason": "entitlement-bound: SEP-only build, no SPY factor panel"},
            "universe_excess": {"method": "same-window universe excess", "status": deferred,
                "reason": "needs the same-window universe returns panel (full-panel run); "
                "demoted from primary in ADR 0002"},
        },
    }


def reproducibility_manifest(
    cohort: CommonCohort,
    result: ReturnsLineResult,
    *,
    config: ProtocolConfig = PROTOCOL,
    data_fingerprint: str | None = None,
) -> dict[str, object]:
    """The reproducibility manifest (ADR 0003 §6): everything needed to reproduce
    every p-value bit-for-bit on a second same-seed / same-data run. NumPy
    major/minor, the generator, all derived seeds, a deterministic cohort/data
    fingerprint, the per-gate bootstrap-index hash, and the hash-serialization
    contract. Only wall-clock and git-SHA fields (added by the driver) vary run to
    run — nothing in this manifest does."""

    major_minor = ".".join(np.__version__.split(".")[:2])
    e1_seed = derive_seed(config.estage_master_seed, config.estage_spec_version, "E1")
    e2_seed = derive_seed(config.estage_master_seed, config.estage_spec_version, "E2")
    cohort_fp = cohort_fingerprint(cohort)
    return {
        "numpy_version": np.__version__,
        "numpy_major_minor": major_minor,
        "generator": "PCG64",
        "master_seed": config.estage_master_seed,
        "spec_version": config.estage_spec_version,
        "derived_seeds": {
            "E1": e1_seed,
            "E2": e2_seed,
            "placebo": "per-cluster: sha256(master_seed, spec_version, 'placebo', cluster_id)",
        },
        # §6 "data fingerprint": the *input* panel fingerprint when the driver
        # supplies one (see inputs_fingerprint); otherwise the derived-cohort
        # fingerprint as a fallback, flagged as such. cohort_fingerprint is always
        # carried too as an output-determinism check.
        "data_fingerprint": data_fingerprint or cohort_fp,
        "data_fingerprint_source": "input_panel" if data_fingerprint else "cohort_derived_fallback",
        "cohort_fingerprint": cohort_fp,
        # §6 "bootstrap-index hash": the SHA-256 over each gate's realized resample
        # index sequence, emitted by the bootstrap itself. None when a gate did not
        # run (underpowered_stop). This is what verifies index-level reproduction.
        "bootstrap_index_hash": {
            "E1": None if result.e1.bootstrap is None else result.e1.bootstrap.index_hash,
            "E2": None if result.e2.bootstrap is None else result.e2.bootstrap.index_hash,
        },
        "hash_serialization_contract": (
            "sha256 over length-prefixed utf-8 fields (str(int(master_seed)), "
            "spec_version, gate_tag[, cluster_id...]); each field is 8-byte big-endian "
            "length then bytes, so field boundaries can never collide"
        ),
    }


def cohort_fingerprint(cohort: CommonCohort) -> str:
    """A deterministic sha256 over the frozen cohort — the sorted per-cluster
    ``(cluster_id, d_i^E1, d_i^E2, year, month)`` rows serialized with fixed float
    formatting. Same cohort → same fingerprint, cross-platform; it is what pins the
    "same data" half of the reproducibility contract when no external panel
    fingerprint is supplied."""

    rows = sorted(
        f"{cid}|{d1!r}|{d2!r}|{ym[0]}-{ym[1]:02d}"
        for cid, d1, d2, ym in zip(
            cohort.cluster_ids, cohort.d_e1_values, cohort.d_e2_values, cohort.month_keys,
            strict=True,
        )
    )
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def inputs_fingerprint(inputs: Sequence[ClusterE2Inputs]) -> str:
    """A deterministic sha256 over the *raw input panel* — the per-cluster session
    opens, habitat aggregate, entry index, and real-event indices — before any
    statistic is computed. This is the §6 "data fingerprint": it pins the *inputs*
    a run consumed (unlike ``cohort_fingerprint``, which digests the derived
    ``d_i``), so a second run over the same panel is provably the same data."""

    rows = sorted(
        "|".join((
            item.cluster_id,
            item.known_time.isoformat(),
            ",".join(repr(o) for o in item.session_opens),
            ",".join(repr(s) for s in item.habitat_sum),
            ",".join(str(c) for c in item.habitat_count),
            str(item.entry_index),
            ",".join(str(i) for i in item.real_event_entry_indices),
        ))
        for item in inputs
    )
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()
