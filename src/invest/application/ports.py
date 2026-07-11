from pathlib import Path
from typing import Protocol

from invest.domain.models import FixtureInputs
from invest.contracts.events import EventBase


class FixtureReader(Protocol):
    def load(self, universe_path: Path, bars_path: Path) -> FixtureInputs: ...


class Journal(Protocol):
    def append(self, event: EventBase) -> None: ...

    def events(self) -> list[EventBase]: ...
