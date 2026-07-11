import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, model_validator

from invest.domain.models import DailyBar, FixtureInputs, Universe
from invest.domain.rejection import RejectionReason


class FixtureValidationError(ValueError):
    def __init__(self, reason: RejectionReason) -> None:
        self.reason = reason
        super().__init__(reason.value)


Symbol = Annotated[str, StringConstraints(min_length=1)]


class _UniversePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fixture_version: str
    symbols: list[Symbol]


class _BarPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: Symbol
    date: date
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_price_relationships(self) -> "_BarPayload":
        if self.low > self.high or not self.low <= self.open <= self.high or not self.low <= self.close <= self.high:
            raise ValueError("OHLC prices have an impossible relationship")
        return self


class _BarsPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fixture_version: str
    bars: list[_BarPayload]


class JsonFixtureReader:
    """Validate JSON fixtures completely before exposing domain inputs."""

    def load(self, universe_path: Path, bars_path: Path) -> FixtureInputs:
        try:
            universe_payload = _UniversePayload.model_validate(self._read(universe_path))
            bars_payload = _BarsPayload.model_validate(self._read(bars_path))
        except (OSError, UnicodeError, json.JSONDecodeError, ValidationError, TypeError) as error:
            raise FixtureValidationError(RejectionReason.FIXTURE_INVALID) from error

        if universe_payload.fixture_version != bars_payload.fixture_version:
            raise FixtureValidationError(RejectionReason.FIXTURE_VERSION_MISMATCH)

        allowed_symbols = set(universe_payload.symbols)
        if any(bar.symbol not in allowed_symbols for bar in bars_payload.bars):
            raise FixtureValidationError(RejectionReason.FIXTURE_SYMBOL_MISSING)
        bar_symbols = {bar.symbol for bar in bars_payload.bars}
        if not allowed_symbols.issubset(bar_symbols):
            raise FixtureValidationError(RejectionReason.FIXTURE_SYMBOL_MISSING)

        keys = [(bar.symbol, bar.date) for bar in bars_payload.bars]
        if len(keys) != len(set(keys)):
            raise FixtureValidationError(RejectionReason.DUPLICATE_BAR)

        last_date_by_symbol: dict[str, date] = {}
        for bar in bars_payload.bars:
            if bar.symbol in last_date_by_symbol and bar.date <= last_date_by_symbol[bar.symbol]:
                raise FixtureValidationError(RejectionReason.NON_MONOTONIC_BARS)
            last_date_by_symbol[bar.symbol] = bar.date

        universe = Universe(universe_payload.fixture_version, tuple(universe_payload.symbols))
        bars = tuple(
            DailyBar(
                symbol=bar.symbol,
                date=bar.date,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
            )
            for bar in bars_payload.bars
        )
        return FixtureInputs(universe=universe, bars=bars)

    @staticmethod
    def _read(path: Path) -> Any:
        with path.open(encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
