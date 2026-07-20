import json
from collections import defaultdict, deque
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any, TextIO

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
    volume: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def validate_price_relationships(self) -> "_BarPayload":
        if self.low > self.high or not self.low <= self.open <= self.high or not self.low <= self.close <= self.high:
            raise ValueError("OHLC prices have an impossible relationship")
        return self


class _InvalidFixture(ValueError):
    pass


class _SeenBarDates:
    """Compact per-symbol date membership for exact duplicate classification."""

    def __init__(self) -> None:
        self._dates: dict[str, tuple[int, bytearray]] = {}

    def add(self, symbol: str, value: date) -> bool:
        ordinal = value.toordinal()
        state = self._dates.get(symbol)
        if state is None:
            self._dates[symbol] = (ordinal, bytearray(b"\x01"))
            return True

        first_ordinal, bits = state
        offset = ordinal - first_ordinal
        if offset < 0:
            # The caller will reject this as non-monotonic; no need to grow the
            # compact forward-only bitmap for an invalid fixture.
            return True
        byte_index, bit_index = divmod(offset, 8)
        if byte_index >= len(bits):
            bits.extend(b"\x00" * (byte_index + 1 - len(bits)))
        mask = 1 << bit_index
        if bits[byte_index] & mask:
            return False
        bits[byte_index] |= mask
        return True


class _StreamingJsonCursor:
    """Incrementally decode JSON values without retaining consumed input text."""

    _CHUNK_SIZE = 64 * 1024
    _MAX_VALUE_SIZE = 1024 * 1024

    def __init__(self, fixture_file: TextIO) -> None:
        self._fixture_file = fixture_file
        self._decoder = json.JSONDecoder()
        self._buffer = ""
        self._position = 0
        self._eof = False

    def decode_value(self) -> Any:
        self._skip_whitespace()
        while True:
            try:
                value, end = self._decoder.raw_decode(self._buffer, self._position)
            except json.JSONDecodeError:
                if self._eof:
                    raise
                if len(self._buffer) - self._position >= self._MAX_VALUE_SIZE:
                    raise _InvalidFixture("JSON value exceeds streaming size limit")
                self._read_more()
            else:
                self._position = end
                return value

    def expect(self, expected: str) -> None:
        self._skip_whitespace()
        if self._position >= len(self._buffer) or self._buffer[self._position] != expected:
            raise _InvalidFixture(f"expected {expected!r}")
        self._position += 1

    def consume(self, expected: str) -> bool:
        self._skip_whitespace()
        if self._position < len(self._buffer) and self._buffer[self._position] == expected:
            self._position += 1
            return True
        return False

    def ensure_finished(self) -> None:
        self._skip_whitespace()
        if self._position != len(self._buffer) or not self._eof:
            raise _InvalidFixture("unexpected trailing JSON content")

    def _skip_whitespace(self) -> None:
        while True:
            while (
                self._position < len(self._buffer)
                and self._buffer[self._position].isspace()
            ):
                self._position += 1
            if self._position < len(self._buffer) or self._eof:
                return
            self._read_more()

    def _read_more(self) -> None:
        unread = self._buffer[self._position :]
        chunk = self._fixture_file.read(self._CHUNK_SIZE)
        self._buffer = unread + chunk
        self._position = 0
        if chunk == "":
            self._eof = True


class JsonFixtureReader:
    """Validate JSON fixtures completely before exposing domain inputs."""

    def load(
        self,
        universe_path: Path,
        bars_path: Path,
        *,
        start: date | None = None,
        end: date | None = None,
        warmup_bars: int = 0,
    ) -> FixtureInputs:
        if (
            (start is not None and end is not None and start > end)
            or type(warmup_bars) is not int
            or warmup_bars < 0
        ):
            raise FixtureValidationError(RejectionReason.FIXTURE_INVALID)

        try:
            universe_payload = _UniversePayload.model_validate(self._read(universe_path))
            bars_version, bars, bar_symbols = self._read_bars(
                bars_path,
                allowed_symbols=set(universe_payload.symbols),
                start=start,
                end=end,
                warmup_bars=warmup_bars,
            )
        except FixtureValidationError:
            raise
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            ValidationError,
            TypeError,
            _InvalidFixture,
        ) as error:
            raise FixtureValidationError(RejectionReason.FIXTURE_INVALID) from error

        if universe_payload.fixture_version != bars_version:
            raise FixtureValidationError(RejectionReason.FIXTURE_VERSION_MISMATCH)

        allowed_symbols = set(universe_payload.symbols)
        if not allowed_symbols.issubset(bar_symbols):
            raise FixtureValidationError(RejectionReason.FIXTURE_SYMBOL_MISSING)

        universe = Universe(universe_payload.fixture_version, tuple(universe_payload.symbols))
        return FixtureInputs(universe=universe, bars=tuple(bars))

    @staticmethod
    def _read_bars(
        path: Path,
        *,
        allowed_symbols: set[str],
        start: date | None,
        end: date | None,
        warmup_bars: int,
    ) -> tuple[str, list[DailyBar], set[str]]:
        with path.open(encoding="utf-8") as fixture_file:
            cursor = _StreamingJsonCursor(fixture_file)
            cursor.expect("{")
            seen_fields: set[str] = set()
            fixture_version: str | None = None
            selected: list[DailyBar] = []
            warmup_by_symbol: dict[str, deque[DailyBar]] = defaultdict(
                lambda: deque(maxlen=warmup_bars)
            )
            bar_symbols: set[str] = set()
            last_date_by_symbol: dict[str, date] = {}
            seen_dates = _SeenBarDates()

            if cursor.consume("}"):
                raise _InvalidFixture("bars fixture is empty")

            while True:
                field = cursor.decode_value()
                if not isinstance(field, str) or field in seen_fields:
                    raise _InvalidFixture("invalid or duplicate object field")
                seen_fields.add(field)
                cursor.expect(":")

                if field == "fixture_version":
                    fixture_version = cursor.decode_value()
                    if not isinstance(fixture_version, str):
                        raise _InvalidFixture("fixture_version must be a string")
                elif field == "bars":
                    cursor.expect("[")
                    if not cursor.consume("]"):
                        while True:
                            payload = _BarPayload.model_validate(cursor.decode_value())
                            if payload.symbol not in allowed_symbols:
                                raise FixtureValidationError(
                                    RejectionReason.FIXTURE_SYMBOL_MISSING
                                )
                            if not seen_dates.add(payload.symbol, payload.date):
                                raise FixtureValidationError(RejectionReason.DUPLICATE_BAR)
                            previous_date = last_date_by_symbol.get(payload.symbol)
                            if previous_date is not None:
                                if payload.date < previous_date:
                                    raise FixtureValidationError(
                                        RejectionReason.NON_MONOTONIC_BARS
                                    )
                            last_date_by_symbol[payload.symbol] = payload.date
                            bar_symbols.add(payload.symbol)

                            in_window = (start is None or payload.date >= start) and (
                                end is None or payload.date <= end
                            )
                            needs_warmup = (
                                warmup_bars > 0
                                and start is not None
                                and payload.date < start
                            )
                            if in_window or needs_warmup:
                                bar = DailyBar(
                                    symbol=payload.symbol,
                                    date=payload.date,
                                    open=payload.open,
                                    high=payload.high,
                                    low=payload.low,
                                    close=payload.close,
                                    volume=payload.volume,
                                )
                                if in_window:
                                    selected.append(bar)
                                else:
                                    warmup_by_symbol[payload.symbol].append(bar)

                            if cursor.consume("]"):
                                break
                            cursor.expect(",")
                            if cursor.consume("]"):
                                raise _InvalidFixture("trailing comma in bars array")
                else:
                    raise _InvalidFixture(f"unexpected field {field!r}")

                if cursor.consume("}"):
                    break
                cursor.expect(",")
                if cursor.consume("}"):
                    raise _InvalidFixture("trailing comma in bars fixture")

            cursor.ensure_finished()
            if fixture_version is None or "bars" not in seen_fields:
                raise _InvalidFixture("missing required bars fixture field")
            warmup = [
                bar
                for symbol in sorted(warmup_by_symbol)
                for bar in warmup_by_symbol[symbol]
            ]
            return fixture_version, warmup + selected, bar_symbols

    @staticmethod
    def _read(path: Path) -> Any:
        with path.open(encoding="utf-8") as fixture_file:
            return json.load(fixture_file)
