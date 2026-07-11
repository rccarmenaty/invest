from pathlib import Path
from typing import Protocol

from invest.domain.models import FixtureInputs


class FixtureReader(Protocol):
    def load(self, universe_path: Path, bars_path: Path) -> FixtureInputs: ...
