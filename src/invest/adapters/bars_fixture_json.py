"""Deep adapter: write a JsonFixtureReader-compatible fixture pair from already-fetched bars.

Used by ``invest-generate-context --bars-out DIR``. Never fetches from a live
source; serializes ``FixtureInputs`` already held in caller scope. Mirrors (but
does not import) ``alpaca_market_data.SnapshotWriter`` serialization and atomic
publish so the Alpaca/Sharadar adapter boundary stays clean.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

from invest.domain.models import FixtureInputs


class BarsFixtureError(OSError):
    reason: str

    def __init__(self, reason: str, message: str | None = None) -> None:
        self.reason = reason
        super().__init__(message or reason)


class BarsFixtureExistsError(BarsFixtureError):
    def __init__(self) -> None:
        super().__init__("bars-out-exists")


class BarsFixtureStorageError(BarsFixtureError):
    def __init__(self, message: str = "storage failure") -> None:
        super().__init__("storage-failure", message)


class BarsFixtureSymbolMismatchError(BarsFixtureError):
    def __init__(self) -> None:
        super().__init__("bars-universe-mismatch")


class BarsFixtureDuplicateBarError(BarsFixtureError):
    def __init__(self) -> None:
        super().__init__("duplicate-bar")


class BarsFixtureWriter:
    """Atomically publish a ``JsonFixtureReader``-compatible fixture pair."""

    def write(self, inputs: FixtureInputs, out: Path) -> Path:
        out = Path(out)
        bar_symbols = {bar.symbol for bar in inputs.bars}
        if not inputs.bars or set(inputs.universe.symbols) != bar_symbols:
            raise BarsFixtureSymbolMismatchError()

        sorted_bars = sorted(inputs.bars, key=lambda bar: (bar.symbol, bar.date))
        keys = [(bar.symbol, bar.date) for bar in sorted_bars]
        if len(keys) != len(set(keys)):
            raise BarsFixtureDuplicateBarError()

        if out.exists():
            raise BarsFixtureExistsError()

        version = inputs.universe.fixture_version
        universe_bytes = self._json_bytes(
            {"fixture_version": version, "symbols": list(inputs.universe.symbols)}
        )
        bars_bytes = self._json_bytes(
            {
                "fixture_version": version,
                "bars": [
                    {
                        "symbol": bar.symbol,
                        "date": bar.date.isoformat(),
                        "open": str(bar.open),
                        "high": str(bar.high),
                        "low": str(bar.low),
                        "close": str(bar.close),
                        "volume": (
                            int(bar.volume)
                            if Decimal(bar.volume) == Decimal(bar.volume).to_integral_value()
                            else str(bar.volume)
                        ),
                    }
                    for bar in sorted_bars
                ],
            }
        )

        staging: Path | None = None
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=".bars-out-", dir=out.parent))
            (staging / "universe.json").write_bytes(universe_bytes)
            (staging / "bars.json").write_bytes(bars_bytes)
            staging.replace(out)
        except OSError as error:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)
            if out.exists():
                raise BarsFixtureExistsError() from None
            raise BarsFixtureStorageError(str(error)) from None
        except BaseException:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)
            raise
        return out

    @staticmethod
    def _json_bytes(payload: object) -> bytes:
        return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
