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
