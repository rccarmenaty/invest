"""R2-1 xs-reversal-lp: pure cross-sectional reverse helpers and frozen gates.

New research line (not residual packaging). Primary seam: pure application
helpers for formation → residualization → decile spreads → G0–G8 evaluation.
Short-engine / BacktestRun work is out of scope for this module.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date

from invest.application.event_study_excess import SummaryStats


@dataclass(frozen=True)
class ProtocolConfig:
    formation_sessions: int = 5
    hold_sessions: int = 5
    skip_sessions: int = 1
    deciles: int = 10
    primary_min_price: float = 5.0
    primary_min_adv: float = 10_000_000.0
    diagnostic_min_adv: float = 1_000_000.0
    g1_min_t: float = 3.0
    g5_min_t: float = 2.0
    year_share_max: float = 0.25
    month_share_max: float = 0.20
    accept_cost_bps: float = 10.0
    g4_max_abs_rho: float = 0.3
    g0_max_placebo_abs_t: float = 2.0
    target_vol: float = 0.20
    scale_clip_lo: float = 0.5
    scale_clip_hi: float = 1.5


PROTOCOL = ProtocolConfig()


@dataclass(frozen=True)
class XsGateResult:
    id: str
    passed: bool
    severity: str  # hard | escalate | info
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class R21GateReport:
    gates: tuple[XsGateResult, ...]
    all_hard_gates_passed: bool
    implementability_eligible: bool
    capital_go: bool
    verdict: str

    def to_dict(self) -> dict:
        return {
            "gates": [g.to_dict() for g in self.gates],
            "all_hard_gates_passed": self.all_hard_gates_passed,
            "implementability_eligible": self.implementability_eligible,
            "capital_go": self.capital_go,
            "verdict": self.verdict,
        }


def iso_week_formation_dates(session_dates: Sequence[date]) -> list[date]:
    """Last session of each ISO week present in a sorted session calendar."""
    if not session_dates:
        return []
    ordered = sorted(session_dates)
    last_by_week: dict[tuple[int, int], date] = {}
    for d in ordered:
        iso = d.isocalendar()
        last_by_week[(iso.year, iso.week)] = d
    return [last_by_week[k] for k in sorted(last_by_week)]


def formation_close_to_close_return(
    closes: Sequence[float], *, formation_index: int | None = None, **kwargs: object
) -> float | None:
    """Close-to-close return over sessions t−4…t: close[t]/close[t−4] − 1."""
    # Support both positional formation_index and keyword for call-site flexibility.
    if formation_index is None:
        raw = kwargs.get("formation_index")
        if raw is None:
            raise TypeError("formation_index is required")
        formation_index = int(raw)  # type: ignore[arg-type]
    lag = PROTOCOL.formation_sessions - 1  # 4
    if formation_index < lag or formation_index >= len(closes):
        return None
    start = closes[formation_index - lag]
    end = closes[formation_index]
    if start <= 0:
        return None
    return end / start - 1.0


def execution_entry_index(formation_index: int, *, skip_sessions: int | None = None) -> int:
    """Open index for first execution after formation close + skip sessions.

    skip_sessions=1 → skip t+1 entirely → entry open at formation_index + 2.
    """
    skip = PROTOCOL.skip_sessions if skip_sessions is None else skip_sessions
    return formation_index + 1 + skip


def open_to_open_return(
    opens: Sequence[float],
    *,
    entry_index: int,
    hold_sessions: int | None = None,
) -> float | None:
    hold = PROTOCOL.hold_sessions if hold_sessions is None else hold_sessions
    exit_i = entry_index + hold
    if entry_index < 0 or exit_i >= len(opens):
        return None
    entry = opens[entry_index]
    if entry <= 0:
        return None
    return opens[exit_i] / entry - 1.0


def residualize_cross_section(
    y: Sequence[float],
    *,
    beta: Sequence[float],
    log_adv_rank: Sequence[float],
) -> list[float]:
    """OLS residual of y on intercept + beta + log_adv_rank (pure Python)."""
    n = len(y)
    if n != len(beta) or n != len(log_adv_rank):
        raise ValueError("y, beta, and log_adv_rank must have equal length")
    if n == 0:
        return []
    if n < 3:
        # underdetermined — return demeaned y
        mean = sum(y) / n
        return [v - mean for v in y]

    # Design matrix columns: 1, beta, log_adv_rank
    xtx = [[0.0] * 3 for _ in range(3)]
    xty = [0.0, 0.0, 0.0]
    for i in range(n):
        row = (1.0, float(beta[i]), float(log_adv_rank[i]))
        yi = float(y[i])
        for a in range(3):
            xty[a] += row[a] * yi
            for b in range(3):
                xtx[a][b] += row[a] * row[b]

    coef = _solve_3x3(xtx, xty)
    if coef is None:
        mean = sum(y) / n
        return [v - mean for v in y]

    a, b1, b2 = coef
    return [
        float(y[i]) - (a + b1 * float(beta[i]) + b2 * float(log_adv_rank[i]))
        for i in range(n)
    ]


def _solve_3x3(a: list[list[float]], b: list[float]) -> tuple[float, float, float] | None:
    """Gaussian elimination for 3x3; None if singular."""
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(3):
        pivot = col
        for r in range(col + 1, 3):
            if abs(m[r][col]) > abs(m[pivot][col]):
                pivot = r
        if abs(m[pivot][col]) < 1e-14:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        piv = m[col][col]
        for c in range(col, 4):
            m[col][c] /= piv
        for r in range(3):
            if r == col:
                continue
            factor = m[r][col]
            for c in range(col, 4):
                m[r][c] -= factor * m[col][c]
    return (m[0][3], m[1][3], m[2][3])


def assign_decile(score: float, scores: Sequence[float]) -> int:
    """Decile 1..10 (1 = lowest scores) by rank in ascending scores."""
    n = len(scores)
    if n == 0:
        raise ValueError("scores must be non-empty")
    ordered = sorted(scores)
    # rank = number of scores strictly less than score, plus ties mid via bisect
    lo = 0
    hi = n
    while lo < hi:
        mid = (lo + hi) // 2
        if ordered[mid] < score:
            lo = mid + 1
        else:
            hi = mid
    rank = lo  # first index >= score
    # If exact match, use first occurrence rank
    d = rank * PROTOCOL.deciles // n + 1
    return min(PROTOCOL.deciles, max(1, d))


def bottom_minus_top_spread(
    d1_returns: Sequence[float], d10_returns: Sequence[float]
) -> float | None:
    if not d1_returns or not d10_returns:
        return None
    return sum(d1_returns) / len(d1_returns) - sum(d10_returns) / len(d10_returns)


def is_liquid(
    *,
    price: float,
    median_adv: float,
    tier: str = "primary",
) -> bool:
    if price < PROTOCOL.primary_min_price:
        return False
    floor = (
        PROTOCOL.primary_min_adv if tier == "primary" else PROTOCOL.diagnostic_min_adv
    )
    return median_adv >= floor


def cost_net_spread(gross: float, *, bps_per_side: float) -> float:
    """Subtract round-trip cost: 2 * bps_per_side on the long-short return unit."""
    return gross - 2.0 * (bps_per_side / 10_000.0)


def gross_scale(
    *,
    realized_vol: float,
    target_vol: float | None = None,
    mode: str = "primary",
) -> float:
    """Predeclared exposure scaler. primary = realized/target; inverse = target/realized."""
    tv = PROTOCOL.target_vol if target_vol is None else target_vol
    if tv <= 0 or realized_vol <= 0:
        return 1.0
    if mode == "inverse":
        raw = tv / realized_vol
    else:
        raw = realized_vol / tv
    return max(PROTOCOL.scale_clip_lo, min(PROTOCOL.scale_clip_hi, raw))


def max_period_share(pnl_by_period: Mapping[object, float]) -> float:
    total = sum(v for v in pnl_by_period.values() if v > 0)
    if total <= 0:
        return 0.0
    return max((v for v in pnl_by_period.values() if v > 0), default=0.0) / total


def year_month_profit_shares(
    dated_pnls: Sequence[tuple[date, float]],
) -> dict[str, float]:
    by_year: dict[int, float] = {}
    by_month: dict[tuple[int, int], float] = {}
    for d, pnl in dated_pnls:
        by_year[d.year] = by_year.get(d.year, 0.0) + pnl
        key = (d.year, d.month)
        by_month[key] = by_month.get(key, 0.0) + pnl
    return {
        "max_year_share": max_period_share(by_year),
        "max_month_share": max_period_share(by_month),
    }


def evaluate_g0_placebo(
    *,
    clustered_t_abs: float,
    max_t: float | None = None,
) -> XsGateResult:
    thr = PROTOCOL.g0_max_placebo_abs_t if max_t is None else max_t
    # Fail if |t| >= thr (require strictly below)
    if clustered_t_abs < thr:
        return XsGateResult(
            id="G0-placebo",
            passed=True,
            severity="hard",
            reason=f"placebo |t|={clustered_t_abs} < {thr}",
        )
    return XsGateResult(
        id="G0-placebo",
        passed=False,
        severity="hard",
        reason=f"placebo |t|={clustered_t_abs} >= {thr}",
    )


def evaluate_g0_synthetic_migration(*, deciles_changed: bool) -> XsGateResult:
    if not deciles_changed:
        return XsGateResult(
            id="G0-synthetic",
            passed=True,
            severity="hard",
            reason="synthetic action injection: no decile migration",
        )
    return XsGateResult(
        id="G0-synthetic",
        passed=False,
        severity="hard",
        reason="synthetic action injection changed decile membership",
    )


def evaluate_g1(spread_stats: SummaryStats, *, min_t: float | None = None) -> XsGateResult:
    thr = PROTOCOL.g1_min_t if min_t is None else min_t
    mean = spread_stats.mean
    t = spread_stats.clustered_t
    if spread_stats.n < 2 or not math.isfinite(mean):
        return XsGateResult(
            id="G1",
            passed=False,
            severity="hard",
            reason="insufficient or non-finite spread sample",
        )
    if mean <= 0:
        return XsGateResult(
            id="G1",
            passed=False,
            severity="hard",
            reason=f"gross B-T mean<=0 (mean={mean})",
        )
    # Zero within-cluster residual (all equal positive spreads) → infinite t
    if not math.isfinite(t):
        t = float("inf")
    if t < thr:
        return XsGateResult(
            id="G1",
            passed=False,
            severity="hard",
            reason=f"gross B-T clustered_t<{thr} (t={t})",
        )
    return XsGateResult(
        id="G1",
        passed=True,
        severity="hard",
        reason=f"gross B-T mean>0 and clustered_t>={thr}",
    )


def evaluate_g2(spread_stats: SummaryStats) -> XsGateResult:
    med = spread_stats.median
    if med is None or not math.isfinite(med):
        return XsGateResult(
            id="G2",
            passed=False,
            severity="hard",
            reason="median missing or non-finite",
        )
    if med <= 0:
        return XsGateResult(
            id="G2",
            passed=False,
            severity="hard",
            reason=f"median spread<=0 (median={med})",
        )
    return XsGateResult(
        id="G2",
        passed=True,
        severity="hard",
        reason=f"median spread>0 (median={med})",
    )


def evaluate_g3(
    *,
    positive_annual_folds: int,
    total_annual_folds: int,
    max_year_share: float,
    max_month_share: float,
) -> XsGateResult:
    if total_annual_folds <= 0:
        return XsGateResult(
            id="G3",
            passed=False,
            severity="hard",
            reason="no annual folds",
        )
    majority = positive_annual_folds * 2 > total_annual_folds
    year_ok = max_year_share <= PROTOCOL.year_share_max
    month_ok = max_month_share <= PROTOCOL.month_share_max
    if majority and year_ok and month_ok:
        return XsGateResult(
            id="G3",
            passed=True,
            severity="hard",
            reason=(
                f"folds {positive_annual_folds}/{total_annual_folds} majority; "
                f"year_share={max_year_share}; month_share={max_month_share}"
            ),
        )
    return XsGateResult(
        id="G3",
        passed=False,
        severity="hard",
        reason=(
            f"folds={positive_annual_folds}/{total_annual_folds} majority={majority}; "
            f"year_share={max_year_share} (max {PROTOCOL.year_share_max}); "
            f"month_share={max_month_share} (max {PROTOCOL.month_share_max})"
        ),
    )


def evaluate_g4(
    *,
    abs_rho: float,
    alpha: float,
    alpha_ci_excludes_zero: bool,
) -> XsGateResult:
    rho_ok = abs_rho <= PROTOCOL.g4_max_abs_rho
    alpha_ok = alpha > 0 and alpha_ci_excludes_zero
    if rho_ok and alpha_ok:
        return XsGateResult(
            id="G4",
            passed=True,
            severity="hard",
            reason=f"|rho|={abs_rho}<= {PROTOCOL.g4_max_abs_rho}; alpha>0 with CI",
        )
    return XsGateResult(
        id="G4",
        passed=False,
        severity="hard",
        reason=(
            f"|rho|={abs_rho} ok={rho_ok}; alpha={alpha} "
            f"ci_excludes_0={alpha_ci_excludes_zero}"
        ),
    )


def evaluate_g5(*, unscaled_clustered_t: float) -> XsGateResult:
    if math.isfinite(unscaled_clustered_t) and unscaled_clustered_t >= PROTOCOL.g5_min_t:
        return XsGateResult(
            id="G5",
            passed=True,
            severity="hard",
            reason=f"unscaled t={unscaled_clustered_t}>={PROTOCOL.g5_min_t}",
        )
    return XsGateResult(
        id="G5",
        passed=False,
        severity="hard",
        reason=f"unscaled t={unscaled_clustered_t}<{PROTOCOL.g5_min_t}",
    )


def evaluate_g6(*, within_limits: bool) -> XsGateResult:
    if within_limits:
        return XsGateResult(
            id="G6",
            passed=True,
            severity="info",
            reason="tail / Jan-2021 short-leg loss within predeclared limits",
        )
    return XsGateResult(
        id="G6",
        passed=False,
        severity="escalate",
        reason="tail honesty breach — escalate to human sizing, not silent GO",
    )


def evaluate_g7(
    *,
    net_at_10bps: float,
    net_at_5bps_primary_tier: float,
) -> XsGateResult:
    if net_at_10bps > 0 and net_at_5bps_primary_tier > 0:
        return XsGateResult(
            id="G7",
            passed=True,
            severity="hard",
            reason="net>0 at 10bps with buffering and at 5bps primary tier",
        )
    return XsGateResult(
        id="G7",
        passed=False,
        severity="hard",
        reason=(
            f"net_10bps={net_at_10bps}; net_5bps_primary={net_at_5bps_primary_tier}"
        ),
    )


def evaluate_g8(*, deflated_sharpe: float) -> XsGateResult:
    if math.isfinite(deflated_sharpe) and deflated_sharpe > 0:
        return XsGateResult(
            id="G8",
            passed=True,
            severity="hard",
            reason=f"deflated Sharpe={deflated_sharpe}>0",
        )
    return XsGateResult(
        id="G8",
        passed=False,
        severity="hard",
        reason=f"deflated Sharpe={deflated_sharpe} not >0",
    )


def trailing_median_dollar_volume(
    closes: Sequence[float],
    volumes: Sequence[float],
    *,
    end_index: int,
    window: int = 20,
) -> float | None:
    """Trailing-inclusive median of close*volume ending at end_index (prior-session use)."""
    if end_index < 0 or end_index >= len(closes) or end_index >= len(volumes):
        return None
    start = end_index - window + 1
    if start < 0:
        return None
    dvs = []
    for i in range(start, end_index + 1):
        c, v = closes[i], volumes[i]
        if c <= 0 or v < 0:
            return None
        dvs.append(c * v)
    ordered = sorted(dvs)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def simple_beta(
    asset_returns: Sequence[float],
    market_returns: Sequence[float],
) -> float | None:
    """OLS beta of asset on market without intercept (cov/var)."""
    n = len(asset_returns)
    if n < 2 or n != len(market_returns):
        return None
    mean_a = sum(asset_returns) / n
    mean_m = sum(market_returns) / n
    cov = sum((a - mean_a) * (m - mean_m) for a, m in zip(asset_returns, market_returns, strict=True)) / n
    var_m = sum((m - mean_m) ** 2 for m in market_returns) / n
    if var_m <= 0:
        return None
    return cov / var_m


@dataclass(frozen=True)
class NameFormationRow:
    symbol: str
    formation_return: float
    beta: float
    log_adv_rank: float
    forward_return: float


def residualized_decile_spread(
    rows: Sequence[NameFormationRow],
) -> tuple[float | None, list[float], list[float]]:
    """One formation date: residualize, decile, return B−T and leg returns."""
    if len(rows) < PROTOCOL.deciles:
        return (None, [], [])
    y = [r.formation_return for r in rows]
    betas = [r.beta for r in rows]
    ranks = [r.log_adv_rank for r in rows]
    resid = residualize_cross_section(y, beta=betas, log_adv_rank=ranks)
    scores = list(resid)
    d1: list[float] = []
    d10: list[float] = []
    for res, row in zip(resid, rows, strict=True):
        d = assign_decile(res, scores)
        if d == 1:
            d1.append(row.forward_return)
        elif d == PROTOCOL.deciles:
            d10.append(row.forward_return)
    return (bottom_minus_top_spread(d1, d10), d1, d10)


def summarize_spread_series(
    spreads: Sequence[float],
    formation_dates: Sequence[date],
) -> SummaryStats:
    from invest.application.event_study_excess import summarize

    if len(spreads) != len(formation_dates):
        raise ValueError("spreads and formation_dates length mismatch")
    return summarize(list(spreads), list(formation_dates))


def annual_fold_signs(spreads: Sequence[float], formation_dates: Sequence[date]) -> dict[int, float]:
    """Mean spread by formation calendar year."""
    buckets: dict[int, list[float]] = {}
    for s, d in zip(spreads, formation_dates, strict=True):
        buckets.setdefault(d.year, []).append(s)
    return {y: sum(vs) / len(vs) for y, vs in sorted(buckets.items())}


def count_positive_folds(fold_means: Mapping[int, float]) -> tuple[int, int]:
    total = len(fold_means)
    pos = sum(1 for v in fold_means.values() if v > 0)
    return pos, total


def pearson_corr(x: Sequence[float], y: Sequence[float]) -> float | None:
    n = len(x)
    if n < 2 or n != len(y):
        return None
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True))
    dx = math.sqrt(sum((a - mx) ** 2 for a in x))
    dy = math.sqrt(sum((b - my) ** 2 for b in y))
    if dx <= 0 or dy <= 0:
        return None
    return num / (dx * dy)


def ols_alpha_vs_market(
    spreads: Sequence[float],
    market: Sequence[float],
) -> tuple[float | None, bool]:
    """Return (alpha, ci_excludes_zero heuristic via |t_alpha|>=2)."""
    n = len(spreads)
    if n < 3 or n != len(market):
        return (None, False)
    mx = sum(market) / n
    my = sum(spreads) / n
    var_x = sum((x - mx) ** 2 for x in market)
    if var_x <= 0:
        return (None, False)
    cov = sum((x - mx) * (y - my) for x, y in zip(market, spreads, strict=True))
    beta = cov / var_x
    alpha = my - beta * mx
    resid = [y - (alpha + beta * x) for x, y in zip(market, spreads, strict=True)]
    s2 = sum(r * r for r in resid) / (n - 2)
    se_alpha = math.sqrt(s2 * (1.0 / n + mx * mx / var_x)) if s2 > 0 else 0.0
    if se_alpha <= 0:
        return (alpha, alpha > 0)
    t_alpha = alpha / se_alpha
    return (alpha, abs(t_alpha) >= 2.0 and alpha > 0)


def deflated_sharpe_proxy(
    *,
    sharpe: float,
    n_obs: int,
    n_trials: int,
) -> float:
    """Bailey–López de Prado style rough deflation (conservative proxy).

    DSR ≈ Sharpe * sqrt(1 - sharpe^2/n) adjusted down by trial count.
    Not a full Probabilistic Sharpe; enough for a frozen gate input.
    """
    if n_obs < 2 or n_trials < 1 or not math.isfinite(sharpe):
        return float("nan")
    # Expected max Sharpe under n_trials nulls ~ sqrt(2 log n_trials)
    haircut = math.sqrt(2.0 * math.log(max(n_trials, 2))) / math.sqrt(n_obs)
    return sharpe - haircut


def build_r21_artifact(
    *,
    spread_stats: SummaryStats,
    gate_report: R21GateReport,
    fold_means: Mapping[int, float],
    max_year_share: float,
    max_month_share: float,
    abs_rho: float | None,
    alpha: float | None,
    net_at_5bps: float,
    net_at_10bps: float,
    net_at_25bps: float,
    n_formations: int,
    protocol: ProtocolConfig = PROTOCOL,
) -> dict:
    """JSON-serializable research artifact (no multi-GB dependency)."""
    return {
        "experiment": "r2-1-xs-reversal-lp",
        "line": "xs-reversal-lp",
        "status": "complete",
        "protocol": asdict(protocol),
        "n_formations": n_formations,
        "spread": spread_stats.to_dict(),
        "folds": {str(k): v for k, v in fold_means.items()},
        "concentration": {
            "max_year_share": max_year_share,
            "max_month_share": max_month_share,
        },
        "market": {"abs_rho": abs_rho, "alpha": alpha},
        "costs": {
            "net_5bps": net_at_5bps,
            "net_10bps": net_at_10bps,
            "net_25bps": net_at_25bps,
        },
        "gates": gate_report.to_dict(),
        "capital_go": False,
        "pass_meaning": "implementability_eligible_only",
        "residual_claim": "hard_frozen",
    }


def evaluate_r21_gates(
    *,
    g0_placebo_t_abs: float,
    g0_deciles_changed: bool,
    spread_stats: SummaryStats,
    positive_annual_folds: int,
    total_annual_folds: int,
    max_year_share: float,
    max_month_share: float,
    abs_rho: float,
    alpha: float,
    alpha_ci_excludes_zero: bool,
    unscaled_clustered_t: float,
    tail_within_limits: bool,
    net_at_10bps: float,
    net_at_5bps_primary_tier: float,
    deflated_sharpe: float,
) -> R21GateReport:
    gates = (
        evaluate_g0_placebo(clustered_t_abs=g0_placebo_t_abs),
        evaluate_g0_synthetic_migration(deciles_changed=g0_deciles_changed),
        evaluate_g1(spread_stats),
        evaluate_g2(spread_stats),
        evaluate_g3(
            positive_annual_folds=positive_annual_folds,
            total_annual_folds=total_annual_folds,
            max_year_share=max_year_share,
            max_month_share=max_month_share,
        ),
        evaluate_g4(
            abs_rho=abs_rho,
            alpha=alpha,
            alpha_ci_excludes_zero=alpha_ci_excludes_zero,
        ),
        evaluate_g5(unscaled_clustered_t=unscaled_clustered_t),
        evaluate_g6(within_limits=tail_within_limits),
        evaluate_g7(
            net_at_10bps=net_at_10bps,
            net_at_5bps_primary_tier=net_at_5bps_primary_tier,
        ),
        evaluate_g8(deflated_sharpe=deflated_sharpe),
    )
    hard = [g for g in gates if g.severity == "hard"]
    all_hard = all(g.passed for g in hard)
    # G6 escalate does not block implementability eligibility by itself in meta table
    # but "within limits" false means escalate — still not capital GO.
    implementability = all_hard and gates[7].passed  # G6 must not escalate for eligibility
    return R21GateReport(
        gates=gates,
        all_hard_gates_passed=all_hard,
        implementability_eligible=implementability,
        capital_go=False,
        verdict="implementability_eligible" if implementability else "kill_line",
    )
