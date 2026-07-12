from enum import StrEnum


class RejectionReason(StrEnum):
    FIXTURE_INVALID = "fixture-invalid"
    FIXTURE_VERSION_MISMATCH = "fixture-version-mismatch"
    FIXTURE_SYMBOL_MISSING = "fixture-symbol-missing"
    DUPLICATE_BAR = "duplicate-bar"
    NON_MONOTONIC_BARS = "non-monotonic-bars"
    INSUFFICIENT_HISTORY = "insufficient-history"
    MISSING_DATA = "missing-data"
    UNSUPPORTED_INPUT = "unsupported-input"
    NO_SIGNAL = "no-signal"
    DOMAIN_INVARIANT_VIOLATION = "domain-invariant-violation"


class UnsupportedInputError(ValueError):
    """Scan inputs violate a run-level precondition the scanner cannot settle per symbol."""

    def __init__(self, symbols: tuple[str, ...]) -> None:
        self.reason = RejectionReason.UNSUPPORTED_INPUT
        self.symbols = symbols
        super().__init__(f"bars present for symbols outside the universe: {', '.join(symbols)}")
