from pathlib import Path
from datetime import date
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from invest.domain.models import (
    AccountSnapshot,
    BrokerAck,
    DailyBar,
    FixtureInputs,
    InsiderTransaction,
    OrderIntent,
    ScanDecision,
    Universe,
)


class FixtureReader(Protocol):
    def load(self, universe_path: Path, bars_path: Path) -> FixtureInputs: ...


class ScannerPort(Protocol):
    """Seam shared by `MomentumScanner` (benchmark) and `MomentumSelectionScanner`
    (core): either strategy runs through the identical, unmodified `BacktestRun`
    replay harness.

    Scanners may additionally opt into bounded indexed replay by declaring
    ``replay_history_bars`` and ``scan_indexed`` on their concrete class. The
    indexed mapping may carry sticky facts about validation failures older than
    its bounded sequences. The base port remains intentionally unbounded so
    third-party scanners preserve correctness without making an undeclared
    history assumption.
    """

    def scan(self, universe: Universe, bars: tuple[DailyBar, ...]) -> list[ScanDecision]: ...


@runtime_checkable
class MarketDataReader(Protocol):
    def fetch(self, universe: Universe, as_of: date) -> FixtureInputs: ...


@runtime_checkable
class InsiderTapeReader(Protocol):
    """Seam over the SEC Insider Transactions Data Sets (Forms 3/4/5, 2006-).

    Implementations are fail-closed: a truncated file, a missing required
    column, or an unparseable row raises rather than yielding a short panel
    that would silently understate event density.
    """

    def load_quarter(self, year: int, quarter: int) -> tuple[InsiderTransaction, ...]: ...


class BrokerPort(Protocol):
    def snapshot(self) -> AccountSnapshot: ...

    def find_order(self, client_order_id: str) -> str | None: ...

    def submit_bracket(self, intent: OrderIntent, client_order_id: str) -> BrokerAck: ...


class Journal(Protocol):
    def append(self, event: BaseModel) -> None: ...

    def events(self) -> list[BaseModel]: ...
