"""Position-blind event-study excess metrics and Gate 1a evaluation.

Gate 1a (meta-judge / Quiet Drift Q1): same-date eligible-universe excess
forward return at a predeclared horizon (primary: 60 sessions) must have
positive mean and date-clustered t at least ``min_t`` (default 2.5).
"""

from __future__ import annotations

import math
from bisect import bisect_left
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date


@dataclass(frozen=True)
class SummaryStats:
    n: int
    mean: float
    median: float | None
    hit_rate_gt0: float | None
    clustered_t: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Gate1aResult:
    passed: bool
    horizon: int
    excess: SummaryStats
    threshold_t: float
    reason: str

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "horizon": self.horizon,
            "excess": self.excess.to_dict(),
            "threshold_t": self.threshold_t,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SymbolBarSeries:
    """Per-symbol session arrays (sorted ascending by date)."""

    dates: Sequence[date]
    opens: Sequence[float]
    closes: Sequence[float]


def clustered_t(
    values: Sequence[float], clusters: Sequence[object]
) -> tuple[float, float, int]:
    """Mean, CR0 cluster-robust t (clustered by entry/decision date), n."""
    n = len(values)
    if n == 0:
        return (float("nan"), float("nan"), 0)
    if n == 1:
        return (float(values[0]), float("nan"), 1)
    mean = sum(values) / n
    sums: dict[object, float] = defaultdict(float)
    for v, c in zip(values, clusters, strict=True):
        sums[c] += v - mean
    se = math.sqrt(sum(s * s for s in sums.values())) / n
    return (mean, mean / se if se > 0 else float("nan"), n)


def summarize(values: Sequence[float], clusters: Sequence[object]) -> SummaryStats:
    mean, t, n = clustered_t(values, clusters)
    if n == 0:
        return SummaryStats(
            n=0, mean=float("nan"), median=None, hit_rate_gt0=None, clustered_t=float("nan")
        )
    ordered = sorted(values)
    return SummaryStats(
        n=n,
        mean=mean,
        median=ordered[n // 2],
        hit_rate_gt0=sum(1 for v in values if v > 0) / n,
        clustered_t=t,
    )


def forward_session_return(
    *,
    opens: Sequence[float],
    closes: Sequence[float],
    dates: Sequence[date],
    decision_date: date,
    horizon: int,
) -> float | None:
    """Return from next-session open after decision_date to close at +horizon sessions.

    Matches research_steps12 Phase C: entry_i = decision_index + 1, exit at entry_i + h.
    """
    if horizon < 1:
        raise ValueError("horizon must be >= 1")
    i = bisect_left(dates, decision_date)
    if i >= len(dates) or dates[i] != decision_date:
        return None
    entry_i = i + 1
    j = entry_i + horizon
    if entry_i >= len(opens) or j >= len(closes):
        return None
    entry = opens[entry_i]
    if entry <= 0:
        return None
    return closes[j] / entry - 1.0


def universe_mean_forward_return(
    series_by_symbol: Mapping[str, SymbolBarSeries],
    *,
    eligible: Iterable[str],
    decision_date: date,
    horizon: int,
) -> float | None:
    """Mean next-open→+h close return over eligible symbols with full horizon coverage."""
    vals: list[float] = []
    for sym in eligible:
        series = series_by_symbol.get(sym)
        if series is None:
            continue
        ret = forward_session_return(
            opens=series.opens,
            closes=series.closes,
            dates=series.dates,
            decision_date=decision_date,
            horizon=horizon,
        )
        if ret is not None:
            vals.append(ret)
    if not vals:
        return None
    return sum(vals) / len(vals)


def excess_return(signal_return: float, universe_mean: float) -> float:
    return signal_return - universe_mean


def evaluate_gate_1a(
    excess: SummaryStats,
    *,
    min_t: float = 2.5,
    horizon: int = 60,
) -> Gate1aResult:
    """Pass iff excess mean > 0 and clustered_t >= min_t (finite)."""
    t = excess.clustered_t
    mean = excess.mean
    if excess.n < 2 or not math.isfinite(mean) or not math.isfinite(t):
        return Gate1aResult(
            passed=False,
            horizon=horizon,
            excess=excess,
            threshold_t=min_t,
            reason="insufficient or non-finite excess sample",
        )
    if mean <= 0:
        return Gate1aResult(
            passed=False,
            horizon=horizon,
            excess=excess,
            threshold_t=min_t,
            reason=f"h{horizon} excess mean<=0 (mean={mean})",
        )
    if t < min_t:
        return Gate1aResult(
            passed=False,
            horizon=horizon,
            excess=excess,
            threshold_t=min_t,
            reason=f"h{horizon} excess clustered_t<{min_t} (t={t})",
        )
    return Gate1aResult(
        passed=True,
        horizon=horizon,
        excess=excess,
        threshold_t=min_t,
        reason=f"h{horizon} excess mean>0 and clustered_t>={min_t}",
    )


def information_discreteness(daily_returns: Sequence[float]) -> float:
    """Da–Gurun–Warachka style ID: sign(cum) * (%neg − %pos) over formation days.

    Lower ID ⇒ more continuous (smooth) information. Zero-return days count in
    the denominator but neither positive nor negative share.
    """
    if not daily_returns:
        raise ValueError("daily_returns must be non-empty")
    n = len(daily_returns)
    pos = sum(1 for r in daily_returns if r > 0)
    neg = sum(1 for r in daily_returns if r < 0)
    cum = sum(daily_returns)
    if cum > 0:
        sign = 1.0
    elif cum < 0:
        sign = -1.0
    else:
        sign = 0.0
    return sign * (neg / n - pos / n)


def formation_daily_returns(
    closes: Sequence[float], *, decision_index: int, lookback: int = 60
) -> list[float] | None:
    """Close-to-close returns for ``lookback`` sessions ending the day before decision.

    For decision bar index ``i``, returns the ``lookback`` daily returns ending at
    close[i-1]/close[i-2]-1 (decision-day close is not in the formation path).
    """
    if lookback < 1:
        raise ValueError("lookback must be >= 1")
    first = decision_index - lookback
    if first < 1 or decision_index > len(closes):
        return None
    out: list[float] = []
    for t in range(first, decision_index):
        prev = closes[t - 1]
        if prev <= 0:
            return None
        out.append(closes[t] / prev - 1.0)
    return out if len(out) == lookback else None


def high_proximity_52w(
    closes: Sequence[float], *, decision_index: int, window: int = 252
) -> float | None:
    """close[decision] / max(close over trailing ``window`` sessions incl. decision)."""
    if decision_index < 0 or decision_index >= len(closes):
        return None
    start = max(0, decision_index - window + 1)
    window_closes = closes[start : decision_index + 1]
    if not window_closes:
        return None
    peak = max(window_closes)
    if peak <= 0:
        return None
    return closes[decision_index] / peak


def assign_quintile(score: float, sorted_scores: Sequence[float]) -> int:
    """Return quintile 1..5 (1 = lowest scores) via rank in ``sorted_scores``."""
    n = len(sorted_scores)
    if n == 0:
        raise ValueError("sorted_scores must be non-empty")
    # first index equal to score (or insertion point)
    rank = bisect_left(sorted_scores, score)
    q = rank * 5 // n + 1
    return min(5, max(1, q))


def bucket_by_score_quintiles(
    pairs: Sequence[tuple[float, float, str]],
) -> dict[int, list[tuple[float, str]]]:
    """Bucket (score, excess, cluster) into quintiles 1..5 by ascending score rank."""
    if not pairs:
        return {}
    ordered = sorted(pairs, key=lambda p: p[0])
    n = len(ordered)
    buckets: dict[int, list[tuple[float, str]]] = defaultdict(list)
    for rank, (_score, excess, cluster) in enumerate(ordered):
        q = min(5, rank * 5 // n + 1)
        buckets[q].append((excess, cluster))
    return buckets


def excess_summary_for_horizon(
    *,
    signal_returns: Sequence[float | None],
    decision_dates: Sequence[date],
    universe_means: Mapping[date, float],
) -> SummaryStats:
    """Build clustered excess summary: signal_ret − universe_mean[decision_date]."""
    if len(signal_returns) != len(decision_dates):
        raise ValueError("signal_returns and decision_dates length mismatch")
    vals: list[float] = []
    clusters: list[str] = []
    for ret, dd in zip(signal_returns, decision_dates, strict=True):
        if ret is None:
            continue
        uni = universe_means.get(dd)
        if uni is None:
            continue
        vals.append(excess_return(ret, uni))
        clusters.append(dd.isoformat())
    return summarize(vals, clusters)
