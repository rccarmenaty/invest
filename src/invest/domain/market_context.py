from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from types import MappingProxyType
from typing import Iterable, Mapping


class ContextOutcomeType(StrEnum):
    ENTRY_BLOCKED = "context-entry-blocked"
    POSITION_FORCED_CLOSED = "context-position-forced-closed"


class ContextReason(StrEnum):
    SYMBOL_INELIGIBLE = "symbol-ineligible"
    CORPORATE_ACTION = "corporate-action"
    EARNINGS_CONTEXT_MISSING = "earnings-context-missing"


class MarketContextError(ValueError):
    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)


class MarketContextInvalidError(MarketContextError):
    def __init__(self, message: str) -> None:
        super().__init__("market-context-invalid", message)


class MarketContextIncompleteError(MarketContextError):
    def __init__(self, message: str) -> None:
        super().__init__("market-context-incomplete", message)


@dataclass(frozen=True)
class CoverageWindow:
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise MarketContextInvalidError("coverage window end precedes start")

    def contains(self, as_of: date) -> bool:
        return self.start <= as_of <= self.end

    def overlaps(self, other: "CoverageWindow") -> bool:
        return self.start <= other.end and other.start <= self.end


@dataclass(frozen=True)
class EligibilityWindow:
    start: date
    end: date
    eligible: bool

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise MarketContextInvalidError("eligibility window end precedes start")

    def contains(self, as_of: date) -> bool:
        return self.start <= as_of <= self.end

    def overlaps(self, other: "EligibilityWindow") -> bool:
        return self.start <= other.end and other.start <= self.end


@dataclass(frozen=True)
class BlockerWindow:
    start: date
    end: date
    reason: ContextReason

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise MarketContextInvalidError("blocker window end precedes start")
        if self.reason is ContextReason.SYMBOL_INELIGIBLE:
            raise MarketContextInvalidError("symbol ineligibility is not a blocker interval")

    def contains(self, as_of: date) -> bool:
        return self.start <= as_of <= self.end

    def overlaps(self, other: "BlockerWindow") -> bool:
        return self.start <= other.end and other.start <= self.end


@dataclass(frozen=True)
class SymbolContext:
    coverage: tuple[CoverageWindow, ...]
    eligibility: tuple[EligibilityWindow, ...]
    blockers: tuple[BlockerWindow, ...] = ()


@dataclass(frozen=True)
class ContextStatus:
    symbol: str
    date: date
    eligible: bool
    reason: ContextReason | None = None

    def __post_init__(self) -> None:
        if self.reason is ContextReason.SYMBOL_INELIGIBLE and self.eligible:
            raise MarketContextInvalidError("ineligible reason requires eligible=False")
        if self.reason in {ContextReason.CORPORATE_ACTION, ContextReason.EARNINGS_CONTEXT_MISSING} and not self.eligible:
            raise MarketContextInvalidError("blocker reasons require eligible=True")

    @property
    def is_safe(self) -> bool:
        return self.eligible and self.reason is None


@dataclass(frozen=True)
class ContextOutcome:
    outcome_type: ContextOutcomeType
    reason: ContextReason
    symbol: str
    date: date

    @classmethod
    def from_status(cls, status: ContextStatus, outcome_type: ContextOutcomeType) -> "ContextOutcome":
        if status.reason is None:
            raise MarketContextInvalidError("safe status cannot produce a context outcome")
        return cls(
            outcome_type=outcome_type,
            reason=status.reason,
            symbol=status.symbol,
            date=status.date,
        )


@dataclass(frozen=True)
class MarketContext:
    by_symbol: Mapping[str, SymbolContext]

    def __post_init__(self) -> None:
        normalized = {
            symbol: SymbolContext(
                coverage=tuple(context.coverage),
                eligibility=tuple(context.eligibility),
                blockers=tuple(context.blockers),
            )
            for symbol, context in self.by_symbol.items()
        }
        object.__setattr__(self, "by_symbol", MappingProxyType(normalized))
        for symbol, context in normalized.items():
            self._validate_symbol(symbol, context)

    def status(self, symbol: str, as_of: date) -> ContextStatus:
        context = self.by_symbol.get(symbol)
        if context is None or not any(window.contains(as_of) for window in context.coverage):
            raise MarketContextIncompleteError(f"missing coverage for {symbol} on {as_of.isoformat()}")

        eligibility = [window for window in context.eligibility if window.contains(as_of)]
        if not eligibility:
            raise MarketContextIncompleteError(f"missing eligibility for {symbol} on {as_of.isoformat()}")
        if len(eligibility) > 1:
            raise MarketContextInvalidError(f"contradictory eligibility for {symbol} on {as_of.isoformat()}")

        blockers = [window for window in context.blockers if window.contains(as_of)]
        if len(blockers) > 1:
            raise MarketContextInvalidError(f"contradictory blockers for {symbol} on {as_of.isoformat()}")

        current_eligibility = eligibility[0]
        current_blocker = blockers[0] if blockers else None
        if current_blocker is not None and not current_eligibility.eligible:
            raise MarketContextInvalidError(f"contradictory state for {symbol} on {as_of.isoformat()}")

        reason = current_blocker.reason if current_blocker else None
        if not current_eligibility.eligible:
            reason = ContextReason.SYMBOL_INELIGIBLE
        return ContextStatus(symbol=symbol, date=as_of, eligible=current_eligibility.eligible, reason=reason)

    def require_complete(self, dates: Iterable[date], symbols: Iterable[str]) -> None:
        for symbol in sorted(set(symbols)):
            for as_of in sorted(set(dates)):
                self.status(symbol, as_of)

    def eligible_symbols(self, symbols: Iterable[str], as_of: date) -> tuple[str, ...]:
        return tuple(symbol for symbol in symbols if self.status(symbol, as_of).eligible)

    @staticmethod
    def _validate_symbol(symbol: str, context: SymbolContext) -> None:
        if not context.coverage:
            raise MarketContextInvalidError(f"symbol {symbol} is missing coverage windows")
        if not context.eligibility:
            raise MarketContextInvalidError(f"symbol {symbol} is missing eligibility windows")

        MarketContext._ensure_non_overlapping(symbol, "coverage", context.coverage)
        MarketContext._ensure_non_overlapping(symbol, "eligibility", context.eligibility)
        MarketContext._ensure_non_overlapping(symbol, "blockers", context.blockers)

        for eligibility in context.eligibility:
            if not any(
                coverage.start <= eligibility.start and eligibility.end <= coverage.end
                for coverage in context.coverage
            ):
                raise MarketContextInvalidError(f"eligibility extends outside coverage for {symbol}")

        for blocker in context.blockers:
            if not any(
                coverage.start <= blocker.start and blocker.end <= coverage.end
                for coverage in context.coverage
            ):
                raise MarketContextInvalidError(f"blocker extends outside coverage for {symbol}")
            if any(
                not eligibility.eligible and blocker.start <= eligibility.end and eligibility.start <= blocker.end
                for eligibility in context.eligibility
            ):
                raise MarketContextInvalidError(f"blocker overlaps ineligible interval for {symbol}")

    @staticmethod
    def _ensure_non_overlapping(symbol: str, label: str, windows: tuple[object, ...]) -> None:
        for index, left in enumerate(windows):
            for right in windows[index + 1 :]:
                if left.overlaps(right):
                    raise MarketContextInvalidError(f"overlapping {label} windows for {symbol}")
