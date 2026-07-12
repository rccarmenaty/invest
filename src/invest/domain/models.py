from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
