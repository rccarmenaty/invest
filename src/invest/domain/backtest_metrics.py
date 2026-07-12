"""Pure backtest accounting: the SOLE place cost model is applied.

`BacktestRun` records `SimulatedTrade` with RAW (pre-cost) bar-derived prices.
This module applies fixed-bps slippage (both sides), zero commission, and a
flat tax haircut on net gains only, then computes hit rate / expectancy / max
drawdown / trade count / net P&L as pure, deterministic functions of a trade
log. No I/O, no clock, no network -- covered by tests/test_boundaries.py's
domain AST ban.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from invest.domain.models import SimulatedTrade

DEFAULT_SLIPPAGE_BPS = Decimal("5")
DEFAULT_TAX_RATE = Decimal("0.15")


class ExitReason(StrEnum):
    STOP = "stop"
    TAKE_PROFIT = "take-profit"
    OPEN_AT_END = "open-at-end"


@dataclass(frozen=True)
class Metrics:
    hit_rate: Decimal
    expectancy: Decimal
    max_drawdown: Decimal
    trade_count: int
    net_pnl: Decimal


def apply_costs(
    trade: SimulatedTrade,
    slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
    tax_rate: Decimal = DEFAULT_TAX_RATE,
) -> Decimal:
    """Net P&L for one trade: bps slippage both sides, zero commission, tax on gains only."""
    slippage_fraction = slippage_bps / Decimal("10000")
    entry_fill = trade.entry_price * (Decimal("1") + slippage_fraction)
    exit_fill = trade.exit_price * (Decimal("1") - slippage_fraction)
    gross = (exit_fill - entry_fill) * trade.qty
    if gross <= 0:
        return gross
    return gross * (Decimal("1") - tax_rate)


def compute_metrics(
    trades: list[SimulatedTrade],
    slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
    tax_rate: Decimal = DEFAULT_TAX_RATE,
) -> Metrics:
    if not trades:
        return Metrics(Decimal("0"), Decimal("0"), Decimal("0"), 0, Decimal("0"))

    ordered = sorted(trades, key=lambda trade: (trade.exit_date, trade.entry_date, trade.symbol))
    nets = [apply_costs(trade, slippage_bps, tax_rate) for trade in ordered]

    trade_count = len(nets)
    net_pnl = sum(nets, Decimal("0"))
    wins = sum(1 for net in nets if net > 0)
    hit_rate = Decimal(wins) / trade_count
    expectancy = net_pnl / trade_count

    cumulative = Decimal("0")
    peak = Decimal("0")
    max_drawdown = Decimal("0")
    for net in nets:
        cumulative += net
        peak = max(peak, cumulative)
        max_drawdown = max(max_drawdown, peak - cumulative)

    return Metrics(hit_rate, expectancy, max_drawdown, trade_count, net_pnl)
