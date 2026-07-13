from pathlib import Path
from datetime import date
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from invest.domain.models import AccountSnapshot, BrokerAck, DailyBar, FixtureInputs, OrderIntent, ScanDecision, Universe


class FixtureReader(Protocol):
    def load(self, universe_path: Path, bars_path: Path) -> FixtureInputs: ...


class ScannerPort(Protocol):
    """Seam shared by `MomentumScanner` (benchmark) and `MomentumSelectionScanner`
    (core): either strategy runs through the identical, unmodified `BacktestRun`
    replay harness."""

    def scan(self, universe: Universe, bars: tuple[DailyBar, ...]) -> list[ScanDecision]: ...


@runtime_checkable
class MarketDataReader(Protocol):
    def fetch(self, universe: Universe, as_of: date) -> FixtureInputs: ...


class BrokerPort(Protocol):
    def snapshot(self) -> AccountSnapshot: ...

    def find_order(self, client_order_id: str) -> str | None: ...

    def submit_bracket(self, intent: OrderIntent, client_order_id: str) -> BrokerAck: ...


class Journal(Protocol):
    def append(self, event: BaseModel) -> None: ...

    def events(self) -> list[BaseModel]: ...
