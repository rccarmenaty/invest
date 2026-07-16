"""Pure backtest accounting: the SOLE place cost model is applied.

`BacktestRun` records `SimulatedTrade` with RAW (pre-cost) bar-derived prices.
This module applies fixed-bps slippage (both sides), zero commission, and a
flat tax haircut on net gains only, then computes hit rate / expectancy / max
drawdown / trade count / net P&L as pure, deterministic functions of a trade
log. No I/O, no clock, no network -- covered by tests/test_boundaries.py's
domain AST ban.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

from invest.domain.models import EquitySummary, SimulatedTrade

DEFAULT_SLIPPAGE_BPS = Decimal("5")
DEFAULT_TAX_RATE = Decimal("0.15")


class ExitReason(StrEnum):
    STOP = "stop"
    TRAILING_CHANNEL = "trailing-channel"
    TIME_STOP = "time-stop"
    ATR_TRAIL = "atr-trail"
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
    return exit_proceeds(
        trade.entry_price,
        trade.exit_price,
        trade.qty,
        slippage_bps,
        tax_rate,
    ) - entry_fill(trade.entry_price, slippage_bps) * trade.qty


def entry_fill(price: Decimal, slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS) -> Decimal:
    return price * (Decimal("1") + slippage_bps / Decimal("10000"))


def exit_proceeds(
    entry_price: Decimal,
    exit_price: Decimal,
    qty: int,
    slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
    tax_rate: Decimal = DEFAULT_TAX_RATE,
) -> Decimal:
    entry_cost = entry_fill(entry_price, slippage_bps) * qty
    exit_fill = exit_price * (Decimal("1") - slippage_bps / Decimal("10000"))
    gross = exit_fill * qty - entry_cost
    if gross <= 0:
        return exit_fill * qty
    return exit_fill * qty - gross * tax_rate


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


def compute_equity_summary(samples: list[tuple[date, Decimal]]) -> EquitySummary:
    """Summarize daily marked equity without exposing a serialized equity curve."""
    if not samples:
        return EquitySummary(
            starting_equity=Decimal("0"),
            ending_equity=Decimal("0"),
            min_equity=Decimal("0"),
            max_equity=Decimal("0"),
            max_drawdown=Decimal("0"),
            total_return=Decimal("0"),
            trading_day_count=0,
        )

    ordered = sorted(samples, key=lambda sample: sample[0])
    values = [equity for _, equity in ordered]
    peak = values[0]
    max_drawdown = Decimal("0")
    for equity in values:
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, peak - equity)
    starting_equity = values[0]
    ending_equity = values[-1]
    total_return = Decimal("0") if starting_equity == 0 else (ending_equity - starting_equity) / starting_equity
    return EquitySummary(
        starting_equity=starting_equity,
        ending_equity=ending_equity,
        min_equity=min(values),
        max_equity=max(values),
        max_drawdown=max_drawdown,
        total_return=total_return,
        trading_day_count=len(values),
    )


def compute_segment_metrics(
    trades: list[SimulatedTrade],
    split_date: date,
    slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
    tax_rate: Decimal = DEFAULT_TAX_RATE,
) -> dict[str, Metrics]:
    """Compute IS/OOS metrics using entry date, with split-day entries in OOS."""
    return {
        "is": compute_metrics(
            [trade for trade in trades if trade.entry_date < split_date], slippage_bps, tax_rate
        ),
        "oos": compute_metrics(
            [trade for trade in trades if trade.entry_date >= split_date], slippage_bps, tax_rate
        ),
    }
