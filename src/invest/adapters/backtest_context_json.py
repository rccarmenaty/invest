import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, model_validator

from invest.domain.market_context import (
    BlockerWindow,
    ContextReason,
    CoverageWindow,
    EligibilityWindow,
    MarketContext,
    MarketContextInvalidError,
    SymbolContext,
)


class ContextOutputExistsError(OSError):
    def __init__(self, path: Path) -> None:
        self.reason = "output-exists"
        super().__init__(f"output already exists: {path}")


class ContextStorageFailureError(OSError):
    def __init__(self, message: str) -> None:
        self.reason = "storage-failure"
        super().__init__(message)


Symbol = Annotated[str, StringConstraints(min_length=1)]


class _DateRangePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    start: date
    end: date

    @model_validator(mode="after")
    def validate_dates(self) -> "_DateRangePayload":
        if self.end < self.start:
            raise ValueError("end precedes start")
        return self


class _EligibilityPayload(_DateRangePayload):
    eligible: bool


class _BlockerPayload(_DateRangePayload):
    reason: Literal["corporate-action", "earnings-context-missing"]


class _SymbolContextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    symbol: Symbol
    coverage: list[_DateRangePayload] = Field(min_length=1)
    eligibility: list[_EligibilityPayload] = Field(min_length=1)
    blockers: list[_BlockerPayload] = Field(default_factory=list)


class _MarketContextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["market-context-v1"]
    symbols: list[_SymbolContextPayload] = Field(min_length=1)


class BacktestContextJsonReader:
    def load(self, path: Path) -> MarketContext:
        try:
            payload = _MarketContextPayload.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValidationError, TypeError) as error:
            raise MarketContextInvalidError("market context JSON is unreadable or malformed") from error

        by_symbol: dict[str, SymbolContext] = {}
        for symbol_payload in payload.symbols:
            if symbol_payload.symbol in by_symbol:
                raise MarketContextInvalidError(f"duplicate context symbol: {symbol_payload.symbol}")
            by_symbol[symbol_payload.symbol] = SymbolContext(
                coverage=tuple(
                    CoverageWindow(start=window.start, end=window.end) for window in symbol_payload.coverage
                ),
                eligibility=tuple(
                    EligibilityWindow(start=window.start, end=window.end, eligible=window.eligible)
                    for window in symbol_payload.eligibility
                ),
                blockers=tuple(
                    BlockerWindow(
                        start=window.start,
                        end=window.end,
                        reason=ContextReason(window.reason),
                    )
                    for window in symbol_payload.blockers
                ),
            )
        return MarketContext(by_symbol)


class BacktestContextJsonWriter:
    """Atomically publish a reader-valid market-context-v1 document.

    Writes a same-directory temporary file, fsyncs, reader-validates, then
    creates the final path without replacement (``os.link``). Existing targets
    are refused. Temporary files are cleaned on every failure path.
    """

    def write(self, context: MarketContext, out: Path) -> Path:
        out = Path(out)
        if out.exists():
            raise ContextOutputExistsError(out)

        payload = self._to_payload(context)
        body = payload.model_dump_json() + "\n"

        temp_path: Path | None = None
        try:
            temp_path = self._write_temp(out, body)
            # Reader-validate before publication.
            BacktestContextJsonReader().load(temp_path)
            try:
                os.link(temp_path, out)
            except FileExistsError as error:
                raise ContextOutputExistsError(out) from error
            except OSError as error:
                raise ContextStorageFailureError(str(error)) from error
        except ContextOutputExistsError:
            raise
        except MarketContextInvalidError:
            raise
        except ContextStorageFailureError:
            raise
        except OSError as error:
            raise ContextStorageFailureError(str(error)) from error
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

        return out

    def _to_payload(self, context: MarketContext) -> _MarketContextPayload:
        if not context.by_symbol:
            raise MarketContextInvalidError("market context has no symbols")

        symbols: list[_SymbolContextPayload] = []
        for symbol in sorted(context.by_symbol):
            symbol_context = context.by_symbol[symbol]
            symbols.append(
                _SymbolContextPayload(
                    symbol=symbol,
                    coverage=[
                        _DateRangePayload(start=window.start, end=window.end)
                        for window in symbol_context.coverage
                    ],
                    eligibility=[
                        _EligibilityPayload(
                            start=window.start, end=window.end, eligible=window.eligible
                        )
                        for window in symbol_context.eligibility
                    ],
                    blockers=[
                        _BlockerPayload(
                            start=window.start,
                            end=window.end,
                            reason=window.reason.value,  # type: ignore[arg-type]
                        )
                        for window in symbol_context.blockers
                    ],
                )
            )
        return _MarketContextPayload(schema_version="market-context-v1", symbols=symbols)

    @staticmethod
    def _write_temp(out: Path, body: str) -> Path:
        directory = out.parent if out.parent.as_posix() not in {"", "."} else Path.cwd()
        directory.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(
            prefix=f".{out.name}.",
            suffix=".tmp",
            dir=directory,
        )
        path = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(body)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return path
