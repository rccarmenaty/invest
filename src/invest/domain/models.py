from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    from invest.domain.backtest_metrics import Metrics
    from invest.domain.market_context import ContextOutcome
    from invest.domain.rejection import RejectionReason


@dataclass(frozen=True)
class Universe:
    fixture_version: str
    symbols: tuple[str, ...]


@dataclass(frozen=True)
class DailyBar:
    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass(frozen=True)
class FixtureInputs:
    universe: Universe
    bars: tuple[DailyBar, ...]


@dataclass(frozen=True)
class ScanDecision:
    symbol: str
    decision_date: date
    accepted: bool
    reason: "RejectionReason | None" = None


@dataclass(frozen=True)
class AccountSnapshot:
    equity: Decimal
    last_equity: Decimal
    buying_power: Decimal
    open_position_count: int
    deployed_value: Decimal
    trading_blocked: bool
    account_blocked: bool


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    decision_date: date
    qty: int
    entry: Decimal
    stop: Decimal
    take_profit: Decimal


@dataclass(frozen=True)
class BrokerAck:
    broker_order_id: str | None
    status: str
    reason: str | None = None


@dataclass(frozen=True)
class SimulatedTrade:
    """One independent backtest trade with RAW (pre-cost) bar-derived prices.

    Cost application (slippage/tax) lives exclusively in `domain.backtest_metrics`.
    """

    symbol: str
    entry_date: date
    exit_date: date
    entry_price: Decimal
    exit_price: Decimal
    qty: int
    exit_reason: str


@dataclass(frozen=True)
class SkippedEntry:
    symbol: str
    decision_date: date
    entry_date: date
    reason: str


@dataclass(frozen=True)
class PortfolioSummary:
    starting_capital: Decimal
    cash: Decimal
    equity: Decimal
    open_position_count: int
    deployed_capital: Decimal
    closed_trade_count: int


@dataclass(frozen=True)
class EquitySummary:
    starting_equity: Decimal
    ending_equity: Decimal
    min_equity: Decimal
    max_equity: Decimal
    max_drawdown: Decimal
    total_return: Decimal
    trading_day_count: int


@dataclass(frozen=True)
class GateTelemetry:
    label: str
    counts: Mapping[str, int]


@dataclass(frozen=True)
class BacktestResult:
    trades: tuple[SimulatedTrade, ...]
    skipped_entries: tuple[SkippedEntry, ...]
    context_outcomes: tuple["ContextOutcome", ...]
    metrics: "Metrics"
    portfolio: PortfolioSummary
    gates: GateTelemetry
    equity_summary: EquitySummary
    segments: Mapping[str, "Metrics"]
    warnings: tuple[str, ...]
