from pathlib import Path
from datetime import date
from typing import Protocol, runtime_checkable

from invest.domain.models import FixtureInputs, Universe
from invest.contracts.events import EventBase


class FixtureReader(Protocol):
    def load(self, universe_path: Path, bars_path: Path) -> FixtureInputs: ...


@runtime_checkable
class MarketDataReader(Protocol):
    def fetch(self, universe: Universe, as_of: date) -> FixtureInputs: ...


class Journal(Protocol):
    def append(self, event: EventBase) -> None: ...

    def events(self) -> list[EventBase]: ...
