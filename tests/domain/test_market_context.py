from datetime import date

import pytest

from invest.domain.market_context import (
    BlockerWindow,
    ContextOutcome,
    ContextOutcomeType,
    ContextReason,
    CoverageWindow,
    EligibilityWindow,
    MarketContext,
    MarketContextIncompleteError,
    MarketContextInvalidError,
    SymbolContext,
)


def _context(*, eligibility: tuple[EligibilityWindow, ...], blockers: tuple[BlockerWindow, ...] = ()) -> MarketContext:
    return MarketContext(
        {
            "ACME": SymbolContext(
                coverage=(CoverageWindow(date(2024, 1, 1), date(2024, 1, 5)),),
                eligibility=eligibility,
                blockers=blockers,
            )
        }
    )


def test_status_resolves_complete_matrix_and_exact_outcome_values() -> None:
    context = _context(
        eligibility=(
            EligibilityWindow(date(2024, 1, 1), date(2024, 1, 2), eligible=True),
            EligibilityWindow(date(2024, 1, 3), date(2024, 1, 5), eligible=False),
        ),
        blockers=(
            BlockerWindow(
                date(2024, 1, 2),
                date(2024, 1, 2),
                reason=ContextReason.CORPORATE_ACTION,
            ),
        ),
    )

    safe = context.status("ACME", date(2024, 1, 1))
    blocked = context.status("ACME", date(2024, 1, 2))
    ineligible = context.status("ACME", date(2024, 1, 3))

    assert safe.eligible is True
    assert safe.reason is None
    assert blocked.eligible is True
    assert blocked.reason is ContextReason.CORPORATE_ACTION
    assert ineligible.eligible is False
    assert ineligible.reason is ContextReason.SYMBOL_INELIGIBLE
    assert ContextOutcomeType.ENTRY_BLOCKED.value == "context-entry-blocked"
    assert ContextOutcomeType.POSITION_FORCED_CLOSED.value == "context-position-forced-closed"
    assert ContextReason.EARNINGS_CONTEXT_MISSING.value == "earnings-context-missing"
    assert ContextOutcome.from_status(blocked, ContextOutcomeType.ENTRY_BLOCKED) == ContextOutcome(
        outcome_type=ContextOutcomeType.ENTRY_BLOCKED,
        reason=ContextReason.CORPORATE_ACTION,
        symbol="ACME",
        date=date(2024, 1, 2),
    )


def test_require_complete_accepts_a_complete_multi_symbol_matrix() -> None:
    context = MarketContext(
        {
            "ACME": SymbolContext(
                coverage=(CoverageWindow(date(2024, 1, 1), date(2024, 1, 2)),),
                eligibility=(EligibilityWindow(date(2024, 1, 1), date(2024, 1, 2), eligible=True),),
            ),
            "BETA": SymbolContext(
                coverage=(CoverageWindow(date(2024, 1, 1), date(2024, 1, 2)),),
                eligibility=(
                    EligibilityWindow(date(2024, 1, 1), date(2024, 1, 1), eligible=True),
                    EligibilityWindow(date(2024, 1, 2), date(2024, 1, 2), eligible=False),
                ),
            ),
        }
    )

    context.require_complete(
        dates=(date(2024, 1, 1), date(2024, 1, 2)),
        symbols=("ACME", "BETA"),
    )

    assert tuple(
        (context.status(symbol, as_of).eligible, context.status(symbol, as_of).reason)
        for symbol in ("ACME", "BETA")
        for as_of in (date(2024, 1, 1), date(2024, 1, 2))
    ) == (
        (True, None),
        (True, None),
        (True, None),
        (False, ContextReason.SYMBOL_INELIGIBLE),
    )


def test_require_complete_checks_later_symbols_for_missing_dates() -> None:
    context = MarketContext(
        {
            "ACME": SymbolContext(
                coverage=(CoverageWindow(date(2024, 1, 1), date(2024, 1, 3)),),
                eligibility=(EligibilityWindow(date(2024, 1, 1), date(2024, 1, 3), eligible=True),),
            ),
            "BETA": SymbolContext(
                coverage=(CoverageWindow(date(2024, 1, 1), date(2024, 1, 3)),),
                eligibility=(EligibilityWindow(date(2024, 1, 1), date(2024, 1, 2), eligible=True),),
            ),
        }
    )

    with pytest.raises(MarketContextIncompleteError) as error:
        context.require_complete(
            dates=(date(2024, 1, 1), date(2024, 1, 3)),
            symbols=("ACME", "BETA"),
        )

    assert error.value.reason == "market-context-incomplete"
    assert str(error.value) == "missing eligibility for BETA on 2024-01-03"


def test_future_eligibility_mutations_do_not_change_prior_day_status() -> None:
    before = _context(
        eligibility=(
            EligibilityWindow(date(2024, 1, 1), date(2024, 1, 2), eligible=True),
            EligibilityWindow(date(2024, 1, 3), date(2024, 1, 5), eligible=False),
        )
    )
    after = _context(
        eligibility=(
            EligibilityWindow(date(2024, 1, 1), date(2024, 1, 2), eligible=True),
            EligibilityWindow(date(2024, 1, 3), date(2024, 1, 3), eligible=False),
            EligibilityWindow(date(2024, 1, 4), date(2024, 1, 5), eligible=True),
        )
    )

    assert after.status("ACME", date(2024, 1, 2)) == before.status("ACME", date(2024, 1, 2))


def test_symbol_mapping_cannot_be_mutated_after_construction() -> None:
    context = _context(
        eligibility=(EligibilityWindow(date(2024, 1, 1), date(2024, 1, 5), eligible=True),)
    )

    with pytest.raises(TypeError):
        context.by_symbol["BETA"] = context.by_symbol["ACME"]  # type: ignore[index]


def test_blockers_are_inclusive_at_both_endpoints() -> None:
    context = _context(
        eligibility=(EligibilityWindow(date(2024, 1, 1), date(2024, 1, 5), eligible=True),),
        blockers=(
            BlockerWindow(
                date(2024, 1, 2),
                date(2024, 1, 4),
                reason=ContextReason.EARNINGS_CONTEXT_MISSING,
            ),
        ),
    )

    assert context.status("ACME", date(2024, 1, 2)).reason is ContextReason.EARNINGS_CONTEXT_MISSING
    assert context.status("ACME", date(2024, 1, 3)).reason is ContextReason.EARNINGS_CONTEXT_MISSING
    assert context.status("ACME", date(2024, 1, 4)).reason is ContextReason.EARNINGS_CONTEXT_MISSING


def test_contradictory_symbol_state_raises_market_context_invalid() -> None:
    with pytest.raises(MarketContextInvalidError) as error:
        _context(
            eligibility=(EligibilityWindow(date(2024, 1, 1), date(2024, 1, 5), eligible=False),),
            blockers=(
                BlockerWindow(
                    date(2024, 1, 2),
                    date(2024, 1, 4),
                    reason=ContextReason.CORPORATE_ACTION,
                ),
            ),
        )

    assert error.value.reason == "market-context-invalid"
