"""CMFT Stage A: pure conditional-momentum family trial helpers and gates.

Ranking-science research line (not residual packaging, not production scanner).
Primary seam: pure application helpers for protocol freeze, features arithmetic,
decile spreads, G0-data / K0 / G1–G8 evaluation, and dual-exit artifacts.
Research driver I/O and optional LightGBM training are out of scope here.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from enum import StrEnum

from invest.application.event_study_excess import SummaryStats


class GateSeverity(StrEnum):
    HARD = "hard"
    ESCALATE = "escalate"
    INFO = "info"


@dataclass(frozen=True)
class ProtocolConfig:
    experiment_id: str = "cmft-stage-a"
    line: str = "cmft-conditional-momentum-family"
    mom_far_sessions: int = 252
    mom_near_sessions: int = 21
    label_horizon_sessions: int = 21
    skip_sessions: int = 1
    history_sessions: int = 253
    breakout_window_sessions: int = 20
    deciles: int = 10
    primary_min_price: float = 5.0
    primary_min_adv: float = 10_000_000.0
    year_share_max: float = 0.25
    month_share_max: float = 0.20
    accept_cost_bps: float = 10.0
    diagnostic_cost_bps: float = 5.0
    stress_cost_bps: float = 25.0
    g1_min_t: float = 3.0
    g0_max_placebo_abs_t: float = 2.0
    g0_data_min_monotone_years: int = 4
    k0_mds_bps: float = 50.0
    k0_z_alpha: float = 1.96  # ~5% two-sided
    k0_z_beta: float = 0.84  # ~80% power
    t1_max_depth: int = 3
    t1_max_leaves: int = 16
    t1_min_data_in_leaf: int = 200
    t1_max_configs: int = 8
    vi_price_trend_min_share: float = 0.50
    vi_short_horizon_max_share: float = 0.40
    capital_go: bool = False
    declared_trial_count: int = 8 * 4 * 3  # configs × rungs × cost levels (upper bound)


PROTOCOL = ProtocolConfig()

# F0 price-trend family (VI yardstick). Core scanner map.
PRICE_TREND_FEATURES: frozenset[str] = frozenset(
    {
        "mom_12_1",
        "mom_6_1",
        "mom_3_1",
        "ret_21d",
        "pct_of_52w_high",
        "close_over_sma50",
        "sma50_over_sma200",
        "sma200_slope_20d",
        "dist_to_20d_high",
    }
)
SHORT_HORIZON_FEATURES: frozenset[str] = frozenset({"ret_21d"})
NOISE_FEATURE_PREFIX = "noise_"


@dataclass(frozen=True)
class CmftGateResult:
    id: str
    passed: bool
    severity: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CmftGateReport:
    gates: tuple[CmftGateResult, ...]
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


def _gate(
    gate_id: str,
    *,
    passed: bool,
    severity: GateSeverity,
    reason: str,
) -> CmftGateResult:
    return CmftGateResult(
        id=gate_id,
        passed=passed,
        severity=str(severity),
        reason=reason,
    )


def month_end_formation_dates(session_dates: Sequence[date]) -> list[date]:
    """Last session of each calendar month present in a sorted session calendar."""
    if not session_dates:
        return []
    ordered = sorted(session_dates)
    last_by_month: dict[tuple[int, int], date] = {}
    for d in ordered:
        last_by_month[(d.year, d.month)] = d
    return [last_by_month[k] for k in sorted(last_by_month)]


def mom_12_1_return(
    closes: Sequence[float],
    *,
    formation_index: int,
    far: int | None = None,
    near: int | None = None,
) -> float | None:
    """Core-equivalent momentum: close[t−near]/close[t−far] − 1 at formation t.

    Matches domain ``momentum_return(far=252, near=21)`` arithmetic on float closes.
    """
    far_n = PROTOCOL.mom_far_sessions if far is None else far
    near_n = PROTOCOL.mom_near_sessions if near is None else near
    if formation_index < far_n or formation_index >= len(closes):
        return None
    if formation_index - near_n < 0:
        return None
    far_close = closes[formation_index - far_n]
    near_close = closes[formation_index - near_n]
    if far_close <= 0:
        return None
    return near_close / far_close - 1.0


def forward_open_to_open_return(
    opens: Sequence[float],
    *,
    formation_index: int,
    skip: int | None = None,
    horizon: int | None = None,
) -> float | None:
    """Return from open[entry] to open[entry+horizon]; entry = formation + skip."""
    sk = PROTOCOL.skip_sessions if skip is None else skip
    hz = PROTOCOL.label_horizon_sessions if horizon is None else horizon
    entry = formation_index + sk
    exit_i = entry + hz
    if entry < 0 or exit_i >= len(opens):
        return None
    start = opens[entry]
    end = opens[exit_i]
    if start <= 0:
        return None
    return end / start - 1.0


def demean_cross_section(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    mu = sum(values) / len(values)
    return [v - mu for v in values]


def assign_deciles(scores: Sequence[float]) -> list[int]:
    """Assign decile 1..10 (1 = lowest) for every score in one sort pass."""
    n = len(scores)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: (scores[i], i))
    out = [1] * n
    for rank, i in enumerate(order):
        d = rank * PROTOCOL.deciles // n + 1
        out[i] = min(PROTOCOL.deciles, max(1, d))
    return out


def top_minus_bottom_spread(
    d1_returns: Sequence[float], d10_returns: Sequence[float]
) -> float | None:
    """Momentum long-short: mean(D10) − mean(D1)."""
    if not d1_returns or not d10_returns:
        return None
    return sum(d10_returns) / len(d10_returns) - sum(d1_returns) / len(d1_returns)


def cost_net_spread(gross: float, *, bps_per_side: float) -> float:
    """Subtract round-trip cost: 2 * bps_per_side on the long-short return unit."""
    return gross - 2.0 * (bps_per_side / 10_000.0)


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


def decile_mean_monotone_increasing(mean_by_decile: Mapping[int, float]) -> bool:
    """True if decile → mean forward return is non-decreasing (ties allowed)."""
    if len(mean_by_decile) < 2:
        return False
    ordered = [mean_by_decile[d] for d in sorted(mean_by_decile)]
    return all(ordered[i] <= ordered[i + 1] for i in range(len(ordered) - 1))


def min_detectable_spread(*, n_formations: int, spread_vol: float) -> float:
    """Approx MDS (return units) for two-sided t test at protocol alpha/power."""
    if n_formations <= 1 or spread_vol <= 0 or not math.isfinite(spread_vol):
        return float("inf")
    z = PROTOCOL.k0_z_alpha + PROTOCOL.k0_z_beta
    return z * spread_vol / math.sqrt(n_formations)


def t1_config_within_bounds(
    *, max_depth: int, num_leaves: int, min_data_in_leaf: int
) -> bool:
    return (
        max_depth <= PROTOCOL.t1_max_depth
        and num_leaves <= PROTOCOL.t1_max_leaves
        and min_data_in_leaf >= PROTOCOL.t1_min_data_in_leaf
    )


def importance_shares(
    importances: Mapping[str, float],
) -> dict[str, float | bool]:
    """Aggregate gain importances into VI gate inputs.

    Returns price_trend_share, short_horizon_share, noise_in_top10.
    """
    if not importances:
        return {
            "price_trend_share": 0.0,
            "short_horizon_share": 0.0,
            "noise_in_top10": False,
        }
    total = sum(max(0.0, v) for v in importances.values())
    if total <= 0:
        return {
            "price_trend_share": 0.0,
            "short_horizon_share": 0.0,
            "noise_in_top10": False,
        }
    pt = sum(max(0.0, v) for k, v in importances.items() if k in PRICE_TREND_FEATURES)
    sh = sum(max(0.0, v) for k, v in importances.items() if k in SHORT_HORIZON_FEATURES)
    ranked = sorted(importances.items(), key=lambda kv: kv[1], reverse=True)[:10]
    noise_top = any(k.startswith(NOISE_FEATURE_PREFIX) for k, _ in ranked)
    return {
        "price_trend_share": pt / total,
        "short_horizon_share": sh / total,
        "noise_in_top10": noise_top,
    }


def evaluate_g0_data(
    *,
    years_monotone: int | None,
    years_total: int | None,
) -> CmftGateResult:
    if years_monotone is None or years_total is None:
        return _gate(
            "G0-data",
            passed=False,
            severity=GateSeverity.HARD,
            reason="G0-data not measured — fail closed",
        )
    if years_total <= 0:
        return _gate(
            "G0-data",
            passed=False,
            severity=GateSeverity.HARD,
            reason="no years for G0-data",
        )
    thr = PROTOCOL.g0_data_min_monotone_years
    if years_monotone >= thr:
        return _gate(
            "G0-data",
            passed=True,
            severity=GateSeverity.HARD,
            reason=f"monotone years {years_monotone}/{years_total} >= {thr}",
        )
    return _gate(
        "G0-data",
        passed=False,
        severity=GateSeverity.HARD,
        reason=f"monotone years {years_monotone}/{years_total} < {thr}",
    )


def evaluate_k0_power(
    *,
    n_formations: int | None,
    spread_vol: float | None,
) -> CmftGateResult:
    if n_formations is None or spread_vol is None:
        return _gate(
            "K0-power",
            passed=False,
            severity=GateSeverity.HARD,
            reason="K0 power inputs not measured — fail closed",
        )
    mds = min_detectable_spread(n_formations=n_formations, spread_vol=spread_vol)
    mds_bps = mds * 10_000.0
    thr = PROTOCOL.k0_mds_bps
    if math.isfinite(mds_bps) and mds_bps <= thr:
        return _gate(
            "K0-power",
            passed=True,
            severity=GateSeverity.HARD,
            reason=f"MDS={mds_bps:.2f}bps <= {thr}bps (n={n_formations})",
        )
    return _gate(
        "K0-power",
        passed=False,
        severity=GateSeverity.HARD,
        reason=f"underpowered: MDS={mds_bps:.2f}bps > {thr}bps (n={n_formations})",
    )


def evaluate_g0_placebo(*, clustered_t_abs: float) -> CmftGateResult:
    thr = PROTOCOL.g0_max_placebo_abs_t
    if clustered_t_abs < thr:
        return _gate(
            "G0-placebo",
            passed=True,
            severity=GateSeverity.HARD,
            reason=f"placebo |t|={clustered_t_abs} < {thr}",
        )
    return _gate(
        "G0-placebo",
        passed=False,
        severity=GateSeverity.HARD,
        reason=f"placebo |t|={clustered_t_abs} >= {thr}",
    )


def evaluate_g1(spread_stats: SummaryStats, *, min_t: float | None = None) -> CmftGateResult:
    thr = PROTOCOL.g1_min_t if min_t is None else min_t
    mean = spread_stats.mean
    t = spread_stats.clustered_t
    if spread_stats.n < 2 or not math.isfinite(mean):
        return _gate(
            "G1",
            passed=False,
            severity=GateSeverity.HARD,
            reason="insufficient or non-finite spread sample",
        )
    if mean <= 0:
        return _gate(
            "G1",
            passed=False,
            severity=GateSeverity.HARD,
            reason=f"gross D10-D1 mean<=0 (mean={mean})",
        )
    if not math.isfinite(t):
        t = float("inf")
    if t < thr:
        return _gate(
            "G1",
            passed=False,
            severity=GateSeverity.HARD,
            reason=f"gross D10-D1 clustered_t<{thr} (t={t})",
        )
    return _gate(
        "G1",
        passed=True,
        severity=GateSeverity.HARD,
        reason=f"gross D10-D1 mean>0 and clustered_t>={thr}",
    )


def evaluate_g2(spread_stats: SummaryStats) -> CmftGateResult:
    med = spread_stats.median
    if med is None or not math.isfinite(med):
        return _gate(
            "G2",
            passed=False,
            severity=GateSeverity.HARD,
            reason="median missing or non-finite",
        )
    if med <= 0:
        return _gate(
            "G2",
            passed=False,
            severity=GateSeverity.HARD,
            reason=f"median spread<=0 (median={med})",
        )
    return _gate(
        "G2",
        passed=True,
        severity=GateSeverity.HARD,
        reason=f"median spread>0 (median={med})",
    )


def evaluate_g3(
    *,
    positive_annual_folds: int,
    total_annual_folds: int,
    max_year_share: float,
    max_month_share: float,
) -> CmftGateResult:
    if total_annual_folds <= 0:
        return _gate(
            "G3",
            passed=False,
            severity=GateSeverity.HARD,
            reason="no annual folds",
        )
    majority = positive_annual_folds * 2 > total_annual_folds
    year_ok = max_year_share <= PROTOCOL.year_share_max
    month_ok = max_month_share <= PROTOCOL.month_share_max
    if majority and year_ok and month_ok:
        return _gate(
            "G3",
            passed=True,
            severity=GateSeverity.HARD,
            reason=(
                f"folds {positive_annual_folds}/{total_annual_folds} majority; "
                f"year_share={max_year_share}; month_share={max_month_share}"
            ),
        )
    return _gate(
        "G3",
        passed=False,
        severity=GateSeverity.HARD,
        reason=(
            f"folds={positive_annual_folds}/{total_annual_folds} majority={majority}; "
            f"year_share={max_year_share} (max {PROTOCOL.year_share_max}); "
            f"month_share={max_month_share} (max {PROTOCOL.month_share_max})"
        ),
    )


def evaluate_g4_costs(
    *,
    mean_net_10bps: float,
    mean_net_5bps: float,
) -> CmftGateResult:
    # 5 bps is diagnostic only; hard bar is 10 bps.
    if mean_net_10bps > 0:
        return _gate(
            "G4-costs",
            passed=True,
            severity=GateSeverity.HARD,
            reason=(
                f"mean_net_10bps={mean_net_10bps}>0 "
                f"(mean_net_5bps={mean_net_5bps} diagnostic)"
            ),
        )
    return _gate(
        "G4-costs",
        passed=False,
        severity=GateSeverity.HARD,
        reason=f"mean_net_10bps={mean_net_10bps}<=0",
    )


def evaluate_g5_beat_c1(
    *,
    t1_mean_net: float,
    t1_median_net: float,
    c1_mean_net: float,
    c1_median_net: float,
) -> CmftGateResult:
    mean_ok = t1_mean_net > c1_mean_net
    med_ok = t1_median_net > c1_median_net
    if mean_ok and med_ok:
        return _gate(
            "G5-beat-c1",
            passed=True,
            severity=GateSeverity.HARD,
            reason=(
                f"T1 mean {t1_mean_net}>C1 {c1_mean_net} and "
                f"T1 median {t1_median_net}>C1 {c1_median_net}"
            ),
        )
    return _gate(
        "G5-beat-c1",
        passed=False,
        severity=GateSeverity.HARD,
        reason=(
            f"T1 mean {t1_mean_net} vs C1 {c1_mean_net} (ok={mean_ok}); "
            f"T1 median {t1_median_net} vs C1 {c1_median_net} (ok={med_ok})"
        ),
    )


def evaluate_g6_vi(
    *,
    price_trend_share: float | None,
    noise_in_top10: bool | None,
) -> CmftGateResult:
    if price_trend_share is None or noise_in_top10 is None:
        return _gate(
            "G6-VI",
            passed=False,
            severity=GateSeverity.HARD,
            reason="VI not measured — fail closed",
        )
    thr = PROTOCOL.vi_price_trend_min_share
    if noise_in_top10:
        return _gate(
            "G6-VI",
            passed=False,
            severity=GateSeverity.HARD,
            reason="noise probe feature in top-10 importance",
        )
    if price_trend_share >= thr:
        return _gate(
            "G6-VI",
            passed=True,
            severity=GateSeverity.HARD,
            reason=f"price-trend share={price_trend_share}>={thr}",
        )
    return _gate(
        "G6-VI",
        passed=False,
        severity=GateSeverity.HARD,
        reason=f"price-trend share={price_trend_share}<{thr}",
    )


def evaluate_g7_reversal(*, short_horizon_share: float | None) -> CmftGateResult:
    if short_horizon_share is None:
        return _gate(
            "G7-reversal",
            passed=False,
            severity=GateSeverity.ESCALATE,
            reason="short-horizon VI share not measured — fail closed escalate",
        )
    thr = PROTOCOL.vi_short_horizon_max_share
    if short_horizon_share > thr:
        return _gate(
            "G7-reversal",
            passed=False,
            severity=GateSeverity.ESCALATE,
            reason=(
                f"short-horizon share={short_horizon_share}>{thr} — "
                "escalate (possible silent R2-1 reopen)"
            ),
        )
    return _gate(
        "G7-reversal",
        passed=True,
        severity=GateSeverity.INFO,
        reason=f"short-horizon share={short_horizon_share}<={thr}",
    )


def evaluate_g8_deflated(
    *,
    deflated_sharpe: float | None,
    measured: bool,
) -> CmftGateResult:
    if not measured or deflated_sharpe is None:
        return _gate(
            "G8-DSR",
            passed=False,
            severity=GateSeverity.HARD,
            reason="deflated Sharpe not measured — fail closed",
        )
    if deflated_sharpe > 0:
        return _gate(
            "G8-DSR",
            passed=True,
            severity=GateSeverity.HARD,
            reason=f"deflated_sharpe={deflated_sharpe}>0",
        )
    return _gate(
        "G8-DSR",
        passed=False,
        severity=GateSeverity.HARD,
        reason=f"deflated_sharpe={deflated_sharpe}<=0",
    )


def evaluate_cmft_gates(
    *,
    g0_data_years_monotone: int | None,
    g0_data_years_total: int | None,
    k0_n_formations: int | None,
    k0_spread_vol: float | None,
    g0_placebo_t_abs: float,
    spread_stats: SummaryStats,
    positive_annual_folds: int,
    total_annual_folds: int,
    max_year_share: float,
    max_month_share: float,
    mean_net_10bps: float,
    mean_net_5bps: float,
    t1_mean_net: float,
    t1_median_net: float,
    c1_mean_net: float,
    c1_median_net: float,
    vi_price_trend_share: float | None,
    vi_noise_in_top10: bool | None,
    vi_short_horizon_share: float | None,
    deflated_sharpe: float | None,
    deflated_sharpe_measured: bool,
) -> CmftGateReport:
    gates = (
        evaluate_g0_data(
            years_monotone=g0_data_years_monotone,
            years_total=g0_data_years_total,
        ),
        evaluate_k0_power(
            n_formations=k0_n_formations,
            spread_vol=k0_spread_vol,
        ),
        evaluate_g0_placebo(clustered_t_abs=g0_placebo_t_abs),
        evaluate_g1(spread_stats),
        evaluate_g2(spread_stats),
        evaluate_g3(
            positive_annual_folds=positive_annual_folds,
            total_annual_folds=total_annual_folds,
            max_year_share=max_year_share,
            max_month_share=max_month_share,
        ),
        evaluate_g4_costs(
            mean_net_10bps=mean_net_10bps,
            mean_net_5bps=mean_net_5bps,
        ),
        evaluate_g5_beat_c1(
            t1_mean_net=t1_mean_net,
            t1_median_net=t1_median_net,
            c1_mean_net=c1_mean_net,
            c1_median_net=c1_median_net,
        ),
        evaluate_g6_vi(
            price_trend_share=vi_price_trend_share,
            noise_in_top10=vi_noise_in_top10,
        ),
        evaluate_g7_reversal(short_horizon_share=vi_short_horizon_share),
        evaluate_g8_deflated(
            deflated_sharpe=deflated_sharpe,
            measured=deflated_sharpe_measured,
        ),
    )

    k0 = gates[1]
    hard = [g for g in gates if g.severity == str(GateSeverity.HARD)]
    escalate = [g for g in gates if g.severity == str(GateSeverity.ESCALATE)]
    all_hard = all(g.passed for g in hard)
    any_escalate_fail = any(not g.passed for g in escalate)

    if not k0.passed:
        verdict = "underpowered-stop"
        eligible = False
    elif any_escalate_fail:
        verdict = "escalate"
        eligible = False
    elif not all_hard:
        verdict = "kill_line"
        eligible = False
    else:
        verdict = "implementability_eligible"
        eligible = True

    return CmftGateReport(
        gates=gates,
        all_hard_gates_passed=all_hard and not any_escalate_fail,
        implementability_eligible=eligible,
        capital_go=False,  # law: always false
        verdict=verdict,
    )


def build_cmft_artifact(
    report: CmftGateReport,
    *,
    fold_table: Sequence[Mapping[str, object]] | None = None,
    protocol: ProtocolConfig | None = None,
) -> dict:
    """Machine-readable dual-exit artifact. capital_go always false."""
    proto = protocol or PROTOCOL
    return {
        "experiment_id": proto.experiment_id,
        "line": proto.line,
        "verdict": report.verdict,
        "capital_go": False,
        "implementability_eligible": report.implementability_eligible,
        "all_hard_gates_passed": report.all_hard_gates_passed,
        "gates": [g.to_dict() for g in report.gates],
        "fold_table": list(fold_table or ()),
        "protocol": asdict(proto),
        "residual_freeze_untouched": True,
        "r21_kill_line_untouched": True,
        "sf_features_included": False,
        "hmm_included": False,
        "price_trend_features": sorted(PRICE_TREND_FEATURES),
        "declared_trial_count": proto.declared_trial_count,
    }
