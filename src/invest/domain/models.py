from dataclasses import dataclass
from datetime import date
from decimal import Decimal


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
