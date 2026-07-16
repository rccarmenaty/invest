"""Point-in-time MarketContext builder.

Owns run-length encoded eligibility windows, full-session coverage for every
valid input listing (including listings ineligible on every session), and
exact-effective-day corporate-action blockers. Reuses the unchanged
``MarketContext`` as the final invariant check. No earnings blocker is ever
emitted; listing and liquidity failure is ``eligible=False``, never a blocker.
"""

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Sequence

from invest.domain.liquidity_screen import ListingFacts, ScreenConfig, screen_eligible
from invest.domain.market_context import (
    BlockerWindow,
    ContextReason,
    CoverageWindow,
    EligibilityWindow,
    MarketContext,
    SymbolContext,
)
from invest.domain.models import DailyBar


@dataclass(frozen=True)
class CorporateActionEvent:
    effective_date: date
    kind: str
    value: Decimal


@dataclass(frozen=True)
class SymbolData:
    symbol: str
    listing: ListingFacts
    bars: tuple[DailyBar, ...]
    actions: tuple[CorporateActionEvent, ...] = ()

    def __post_init__(self) -> None:
        for bar in self.bars:
            if bar.symbol != self.symbol:
                raise ValueError(
                    f"SymbolData symbol {self.symbol!r} does not match bar symbol {bar.symbol!r}"
                )


def build_market_context(
    sessions: Sequence[date],
    symbols: Sequence[SymbolData],
    config: ScreenConfig,
) -> MarketContext:
    """Build a deterministic, invariant-safe ``MarketContext`` covering every
    requested session for every valid input listing.

    Listings that are ineligible on every session still receive full coverage
    with ``eligible=False`` windows so replay can treat them as ineligible
    instead of aborting with ``MarketContextIncompleteError``.
    """
    sorted_sessions = sorted(sessions)
    if not sorted_sessions:
        return MarketContext({})

    session_set = set(sorted_sessions)
    coverage_start = sorted_sessions[0]
    coverage_end = sorted_sessions[-1]

    by_symbol: dict[str, SymbolContext] = {}
    for data in sorted(symbols, key=lambda item: item.symbol):
        per_day = _eligibility_per_session(data.bars, sorted_sessions, data.listing, config)
        coverage = (CoverageWindow(coverage_start, coverage_end),)
        eligibility = _run_length_encode(per_day, sorted_sessions)
        blockers = _build_blockers(data.actions, per_day, session_set)

        by_symbol[data.symbol] = SymbolContext(
            coverage=coverage,
            eligibility=eligibility,
            blockers=blockers,
        )

    return MarketContext(by_symbol)


def _eligibility_per_session(
    bars: Sequence[DailyBar],
    sessions: list[date],
    listing: ListingFacts,
    config: ScreenConfig,
) -> dict[date, bool]:
    """Eligibility for each session, sorting the full bar history once instead
    of filtering and re-sorting it on every session evaluation.

    Bars are sorted chronologically a single time; for each session only the
    prefix dated on or before that session is passed to ``screen_eligible``.
    The no-look-ahead and eligibility semantics are identical to evaluating
    ``screen_eligible`` on the full bar list per session."""
    sorted_bars = sorted(bars, key=lambda bar: bar.date)
    bar_dates = [bar.date for bar in sorted_bars]
    return {
        session: screen_eligible(
            sorted_bars[: bisect_right(bar_dates, session)],
            session,
            listing,
            config,
        )
        for session in sessions
    }


def _run_length_encode(
    per_day: dict[date, bool], sorted_sessions: list[date]
) -> tuple[EligibilityWindow, ...]:
    windows: list[EligibilityWindow] = []
    run_start = sorted_sessions[0]
    run_eligible = per_day[sorted_sessions[0]]
    prev = sorted_sessions[0]

    for session in sorted_sessions[1:]:
        if per_day[session] != run_eligible:
            windows.append(EligibilityWindow(run_start, prev, eligible=run_eligible))
            run_start = session
            run_eligible = per_day[session]
        prev = session

    windows.append(EligibilityWindow(run_start, prev, eligible=run_eligible))
    return tuple(windows)


def _build_blockers(
    actions: Sequence[CorporateActionEvent],
    per_day: dict[date, bool],
    session_set: set[date],
) -> tuple[BlockerWindow, ...]:
    blocker_dates: set[date] = set()
    for action in actions:
        if action.effective_date in session_set and per_day.get(action.effective_date, False):
            blocker_dates.add(action.effective_date)
    return tuple(
        BlockerWindow(day, day, reason=ContextReason.CORPORATE_ACTION)
        for day in sorted(blocker_dates)
    )
