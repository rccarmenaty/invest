"""Phase 2 portfolio-structure report: after-cost books, folds, FC, go/no-go.

Pure analysis over SimulatedTrade logs. Primary metric is pre-tax after-cost
(5 bps/side, tax_rate=0). Tax-on-gains is secondary only. No I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence

from invest.domain.backtest_metrics import DEFAULT_SLIPPAGE_BPS, apply_costs
from invest.domain.market_context import ContextOutcomeType
from invest.domain.models import SimulatedTrade

FC_EXIT_REASON = ContextOutcomeType.POSITION_FORCED_CLOSED.value
PRIMARY_TAX_RATE = Decimal("0")  # pre-tax primary
SECONDARY_TAX_RATE = Decimal("0.15")
MAX_YEAR_PROFIT_SHARE = Decimal("0.25")
# Predeclared annual walk-forward test folds (2023–2025 are folds, not holdout).
WALK_FORWARD_YEARS = (2019, 2020, 2021, 2022, 2023, 2024, 2025)


def _decimal_median(values: Sequence[Decimal]) -> Decimal:
    """Median of Decimals without float coercion (statistics.median averages to float)."""
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return Decimal("0")
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal("2")



@dataclass(frozen=True)
class BookSummary:
    trade_count: int
    net_pnl: Decimal
    mean_expectancy: Decimal
    median_expectancy: Decimal
    hit_rate: Decimal

    def to_dict(self) -> dict:
        return {
            "trade_count": self.trade_count,
            "net_pnl": str(self.net_pnl),
            "mean_expectancy": str(self.mean_expectancy),
            "median_expectancy": str(self.median_expectancy),
            "hit_rate": str(self.hit_rate),
        }


@dataclass(frozen=True)
class Phase2GateResult:
    passed: bool
    decision: str  # "GO" | "NO-GO"
    majority_folds_positive: bool
    fc_segregated_holds: bool
    year_concentration_ok: bool
    positive_fold_count: int
    evaluated_fold_count: int
    max_year_profit_share: Decimal | None
    peak_profit_year: int | None
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "decision": self.decision,
            "majority_folds_positive": self.majority_folds_positive,
            "fc_segregated_holds": self.fc_segregated_holds,
            "year_concentration_ok": self.year_concentration_ok,
            "positive_fold_count": self.positive_fold_count,
            "evaluated_fold_count": self.evaluated_fold_count,
            "max_year_profit_share": (
                str(self.max_year_profit_share)
                if self.max_year_profit_share is not None
                else None
            ),
            "peak_profit_year": self.peak_profit_year,
            "reasons": list(self.reasons),
        }


def is_forced_close(trade: SimulatedTrade) -> bool:
    return trade.exit_reason == FC_EXIT_REASON


def non_fc_trades(trades: Sequence[SimulatedTrade]) -> list[SimulatedTrade]:
    return [t for t in trades if not is_forced_close(t)]


def fc_trades(trades: Sequence[SimulatedTrade]) -> list[SimulatedTrade]:
    return [t for t in trades if is_forced_close(t)]


def trade_nets(
    trades: Sequence[SimulatedTrade],
    *,
    slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
    tax_rate: Decimal = PRIMARY_TAX_RATE,
) -> list[Decimal]:
    return [apply_costs(t, slippage_bps, tax_rate) for t in trades]


def summarize_book(
    trades: Sequence[SimulatedTrade],
    *,
    slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
    tax_rate: Decimal = PRIMARY_TAX_RATE,
) -> BookSummary:
    if not trades:
        zero = Decimal("0")
        return BookSummary(
            trade_count=0,
            net_pnl=zero,
            mean_expectancy=zero,
            median_expectancy=zero,
            hit_rate=zero,
        )
    nets = trade_nets(trades, slippage_bps=slippage_bps, tax_rate=tax_rate)
    n = len(nets)
    net_pnl = sum(nets, Decimal("0"))
    wins = sum(1 for x in nets if x > 0)
    return BookSummary(
        trade_count=n,
        net_pnl=net_pnl,
        mean_expectancy=net_pnl / n,
        median_expectancy=_decimal_median(nets),
        hit_rate=Decimal(wins) / Decimal(n),
    )


def by_entry_year(trades: Sequence[SimulatedTrade]) -> dict[int, list[SimulatedTrade]]:
    out: dict[int, list[SimulatedTrade]] = {}
    for trade in trades:
        out.setdefault(trade.entry_date.year, []).append(trade)
    return dict(sorted(out.items()))


def walk_forward_folds(
    trades: Sequence[SimulatedTrade],
    *,
    years: Sequence[int] = WALK_FORWARD_YEARS,
    slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
    tax_rate: Decimal = PRIMARY_TAX_RATE,
) -> dict[str, BookSummary]:
    """Annual entry-year folds. Empty years still appear with zero books."""
    grouped = by_entry_year(trades)
    return {
        str(year): summarize_book(
            grouped.get(year, []),
            slippage_bps=slippage_bps,
            tax_rate=tax_rate,
        )
        for year in years
    }


def max_year_profit_share(
    trades: Sequence[SimulatedTrade],
    *,
    slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
    tax_rate: Decimal = PRIMARY_TAX_RATE,
) -> tuple[Decimal | None, int | None]:
    """Largest positive year share of total net profit.

    Returns (None, None) when total net_pnl is not positive (no profit base).
    """
    year_books = {
        year: summarize_book(rows, slippage_bps=slippage_bps, tax_rate=tax_rate)
        for year, rows in by_entry_year(trades).items()
    }
    total = sum((b.net_pnl for b in year_books.values()), Decimal("0"))
    if total <= 0:
        return None, None
    peak_year: int | None = None
    peak_share = Decimal("0")
    for year, book in year_books.items():
        if book.net_pnl <= 0:
            continue
        share = book.net_pnl / total
        if share > peak_share:
            peak_share = share
            peak_year = year
    if peak_year is None:
        return None, None
    return peak_share, peak_year


def _majority_folds_positive(
    folds: Mapping[str, BookSummary],
) -> tuple[bool, int, int]:
    evaluated = [
        book for book in folds.values() if book.trade_count > 0
    ]
    if not evaluated:
        return False, 0, 0
    positive = sum(1 for book in evaluated if book.mean_expectancy > 0)
    return positive * 2 > len(evaluated), positive, len(evaluated)


def evaluate_phase2_gates(
    trades: Sequence[SimulatedTrade],
    *,
    fold_years: Sequence[int] = WALK_FORWARD_YEARS,
    slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
    tax_rate: Decimal = PRIMARY_TAX_RATE,
    max_year_share: Decimal = MAX_YEAR_PROFIT_SHARE,
) -> Phase2GateResult:
    """PRD #58 accept gates on the primary (pre-tax after-cost) book."""
    full_folds = walk_forward_folds(
        trades, years=fold_years, slippage_bps=slippage_bps, tax_rate=tax_rate
    )
    majority_ok, positive_n, evaluated_n = _majority_folds_positive(full_folds)

    alpha = non_fc_trades(trades)
    alpha_folds = walk_forward_folds(
        alpha, years=fold_years, slippage_bps=slippage_bps, tax_rate=tax_rate
    )
    fc_ok, _, _ = _majority_folds_positive(alpha_folds)

    share, peak_year = max_year_profit_share(
        trades, slippage_bps=slippage_bps, tax_rate=tax_rate
    )
    if share is None:
        year_ok = False
    else:
        year_ok = share <= max_year_share

    reasons: list[str] = []
    if not majority_ok:
        reasons.append(
            f"after-cost expectancy not >0 on majority of folds "
            f"({positive_n}/{evaluated_n})"
        )
    if not fc_ok:
        reasons.append(
            "FC-segregated (ex-forced-close) book fails majority-fold expectancy>0"
        )
    if not year_ok:
        if share is None:
            reasons.append("year concentration: total after-cost net_pnl non-positive")
        else:
            reasons.append(
                f"year concentration: {peak_year} contributes {share} "
                f"(> {max_year_share} cap)"
            )

    passed = majority_ok and fc_ok and year_ok
    if passed:
        reasons = [
            "majority walk-forward folds after-cost exp>0; "
            "FC-segregated holds; no year >~25% of profit"
        ]

    return Phase2GateResult(
        passed=passed,
        decision="GO" if passed else "NO-GO",
        majority_folds_positive=majority_ok,
        fc_segregated_holds=fc_ok,
        year_concentration_ok=year_ok,
        positive_fold_count=positive_n,
        evaluated_fold_count=evaluated_n,
        max_year_profit_share=share,
        peak_profit_year=peak_year,
        reasons=tuple(reasons),
    )


def build_phase2_report(
    *,
    trades: Sequence[SimulatedTrade],
    provenance: Mapping[str, object],
    fold_years: Sequence[int] = WALK_FORWARD_YEARS,
    slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
    primary_tax_rate: Decimal = PRIMARY_TAX_RATE,
    secondary_tax_rate: Decimal = SECONDARY_TAX_RATE,
    max_year_share: Decimal = MAX_YEAR_PROFIT_SHARE,
) -> dict:
    """JSON-serializable Phase 2 research artifact (no float money fields)."""
    primary = summarize_book(
        trades, slippage_bps=slippage_bps, tax_rate=primary_tax_rate
    )
    tax_secondary = summarize_book(
        trades, slippage_bps=slippage_bps, tax_rate=secondary_tax_rate
    )
    folds = walk_forward_folds(
        trades, years=fold_years, slippage_bps=slippage_bps, tax_rate=primary_tax_rate
    )
    by_year = {
        str(year): summarize_book(
            rows, slippage_bps=slippage_bps, tax_rate=primary_tax_rate
        ).to_dict()
        for year, rows in by_entry_year(trades).items()
    }
    alpha = non_fc_trades(trades)
    forced = fc_trades(trades)
    gate = evaluate_phase2_gates(
        trades,
        fold_years=fold_years,
        slippage_bps=slippage_bps,
        tax_rate=primary_tax_rate,
        max_year_share=max_year_share,
    )
    alpha_gate = evaluate_phase2_gates(
        alpha,
        fold_years=fold_years,
        slippage_bps=slippage_bps,
        tax_rate=primary_tax_rate,
        max_year_share=max_year_share,
    )

    return {
        "experiment": "phase2-fixed-horizon-structure",
        "primary_metric": "pre-tax after 5 bps/side",
        "note": (
            "2023–2025 treated as walk-forward folds only — not an untouched holdout. "
            "Primary claim is random-admission structure, not ID/Core ranking."
        ),
        "after_cost_pre_tax": primary.to_dict(),
        "tax_secondary": {
            "tax_rate": str(secondary_tax_rate),
            **tax_secondary.to_dict(),
        },
        "walk_forward_folds": {year: book.to_dict() for year, book in folds.items()},
        "by_year": by_year,
        "fc_segregated": {
            "fc_exit_reason": FC_EXIT_REASON,
            "all": primary.to_dict(),
            "non_fc": summarize_book(
                alpha, slippage_bps=slippage_bps, tax_rate=primary_tax_rate
            ).to_dict(),
            "fc_only": summarize_book(
                forced, slippage_bps=slippage_bps, tax_rate=primary_tax_rate
            ).to_dict(),
            "non_fc_go_no_go": alpha_gate.to_dict(),
        },
        "go_no_go": gate.to_dict(),
        "provenance": dict(provenance),
        "gates_predeclared": {
            "majority_wf_folds_after_cost_exp_gt_0": True,
            "fc_segregated_still_holds": True,
            "max_single_year_profit_share": str(max_year_share),
            "ranking_not_accept_path": True,
        },
    }
