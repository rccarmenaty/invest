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


Symbol = Annotated[str, StringConstraints(min_length=1)]


class _DateRangePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    model_config = ConfigDict(extra="forbid")

    symbol: Symbol
    coverage: list[_DateRangePayload] = Field(min_length=1)
    eligibility: list[_EligibilityPayload] = Field(min_length=1)
    blockers: list[_BlockerPayload] = Field(default_factory=list)


class _MarketContextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
