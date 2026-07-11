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
