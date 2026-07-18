"""Unit tests for the point-in-time MarketContext builder.

Covers sorted coalescing, full coverage for every valid input listing
(including all-ineligible ones), run-length encoded eligibility windows,
exact-day corporate-action blockers on eligible days only, absence of
earnings blockers, and MarketContext invariant safety.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from invest.domain.liquidity_screen import ListingFacts, ScreenConfig
from invest.domain.market_context import (
    BlockerWindow,
    ContextReason,
    CoverageWindow,
    EligibilityWindow,
    GenerationSpan,
    MarketContextInvalidError,
)
from invest.domain.market_context_builder import (
    CorporateActionEvent,
    SymbolData,
    build_market_context,
)
from invest.domain.models import DailyBar


def _bar(symbol: str, day: date, close: Decimal, volume: int = 1_000_000) -> DailyBar:
    return DailyBar(
        symbol=symbol,
        date=day,
        open=close,
        high=close + Decimal("0.5"),
        low=close - Decimal("0.5"),
        close=close,
        volume=volume,
    )


def _small_config() -> ScreenConfig:
    return ScreenConfig(
        price_floor=Decimal("1"),
        dollar_volume_floor=Decimal("1"),
        dollar_volume_window=2,
        min_observed_bars=3,
    )


def _eligible_symbol(
    symbol: str,
    start: date,
    *,
    bar_count: int = 3,
    close: Decimal = Decimal("10"),
    volume: int = 1_000_000,
    actions: tuple[CorporateActionEvent, ...] = (),
    primary_common: bool = True,
    listing_end: date | None = None,
    preceding: int = 0,
) -> SymbolData:
    """``preceding`` bars are emitted before ``start`` so the symbol has enough
    observed history to be eligible from the first session onward."""
    first = start - timedelta(days=preceding)
    bars = tuple(_bar(symbol, first + timedelta(days=i), close, volume) for i in range(bar_count))
    end = listing_end if listing_end is not None else start + timedelta(days=365)
    return SymbolData(
        symbol=symbol,
        listing=ListingFacts(first, end, primary_common=primary_common),
        bars=bars,
        actions=actions,
    )


# ---------------------------------------------------------------------------
# SymbolData fail-closed on foreign-symbol bars
# ---------------------------------------------------------------------------


def test_symbol_data_rejects_bar_with_foreign_symbol() -> None:
    """SymbolData must fail closed when a supplied bar carries a different
    symbol -- no foreign-symbol bar may influence the declared symbol's
    eligibility."""
    start = date(2024, 1, 1)
    foreign_bar = _bar("INTRUDER", start, Decimal("10"))
    with pytest.raises(ValueError):
        SymbolData(
            symbol="ACME",
            listing=ListingFacts(start, start + timedelta(days=365), primary_common=True),
            bars=(foreign_bar,),
        )


def test_symbol_data_rejects_mixed_correct_and_foreign_bars() -> None:
    """Even a single foreign-symbol bar among correct bars must fail closed."""
    start = date(2024, 1, 1)
    bars = (
        _bar("ACME", start, Decimal("10")),
        _bar("INTRUDER", start + timedelta(days=1), Decimal("10")),
    )
    with pytest.raises(ValueError):
        SymbolData(
            symbol="ACME",
            listing=ListingFacts(start, start + timedelta(days=365), primary_common=True),
            bars=bars,
        )


# ---------------------------------------------------------------------------
# Full coverage and run-length encoding -- single ever-eligible symbol
# ---------------------------------------------------------------------------


def test_single_eligible_symbol_full_coverage_and_single_rle_window() -> None:
    start = date(2024, 1, 1)
    sessions = [start, start + timedelta(days=1), start + timedelta(days=2)]
    # 5 bars starting 2 days before the first session so 3 are observed by day 0.
    symbol = _eligible_symbol("ACME", start, bar_count=5, preceding=2)

    context = build_market_context(sessions, [symbol], _small_config())

    assert context.generation_span == GenerationSpan(start, start + timedelta(days=2))
    assert "ACME" in context.by_symbol
    sym = context.by_symbol["ACME"]
    assert sym.coverage == (CoverageWindow(start, start + timedelta(days=2)),)
    assert sym.eligibility == (
        EligibilityWindow(start, start + timedelta(days=2), eligible=True),
    )
    assert sym.blockers == ()


# ---------------------------------------------------------------------------
# Full-session coverage for valid all-ineligible listings
# ---------------------------------------------------------------------------


def test_never_eligible_valid_listing_preserved_with_full_ineligible_coverage() -> None:
    """A valid listing that fails eligibility on every requested session MUST
    still appear with full coverage so replay treats every session as
    ineligible instead of raising MarketContextIncompleteError."""
    start = date(2024, 1, 1)
    sessions = [start, start + timedelta(days=1), start + timedelta(days=2)]
    eligible = _eligible_symbol("ACME", start, bar_count=5, preceding=2)
    # BETA has listing facts but no bars — never eligible, still covered.
    never = SymbolData(
        symbol="BETA",
        listing=ListingFacts(start, start + timedelta(days=365), primary_common=True),
        bars=(),
    )

    context = build_market_context(sessions, [eligible, never], _small_config())

    assert "ACME" in context.by_symbol
    assert "BETA" in context.by_symbol
    beta = context.by_symbol["BETA"]
    assert beta.coverage == (CoverageWindow(start, start + timedelta(days=2)),)
    assert beta.eligibility == (
        EligibilityWindow(start, start + timedelta(days=2), eligible=False),
    )
    assert beta.blockers == ()
    # Replay contract: require_complete over the input-universe listing must succeed.
    context.require_complete(dates=sessions, symbols=("ACME", "BETA"))
    for session in sessions:
        status = context.status("BETA", session)
        assert status.eligible is False
        assert status.reason is ContextReason.SYMBOL_INELIGIBLE


def test_all_ineligible_only_listing_still_covers_every_session() -> None:
    """When the only input listing is all-ineligible, coverage still spans every
    requested session so require_complete does not abort."""
    start = date(2024, 1, 1)
    sessions = [start, start + timedelta(days=1)]
    never = SymbolData(
        symbol="THIN",
        listing=ListingFacts(start, start + timedelta(days=365), primary_common=True),
        bars=(),
    )

    context = build_market_context(sessions, [never], _small_config())

    assert tuple(context.by_symbol) == ("THIN",)
    context.require_complete(dates=sessions, symbols=("THIN",))
    assert context.status("THIN", start).eligible is False
    assert context.status("THIN", start).reason is ContextReason.SYMBOL_INELIGIBLE


# ---------------------------------------------------------------------------
# Run-length encoding — mixed eligibility within the session range
# ---------------------------------------------------------------------------


def test_rle_splits_eligible_and_ineligible_runs() -> None:
    start = date(2024, 1, 1)
    sessions = [start + timedelta(days=i) for i in range(5)]
    # Listing ends on session index 2 (day 2) so days 3-4 are post-delisting.
    symbol = _eligible_symbol(
        "ACME",
        start,
        bar_count=7,
        preceding=2,
        listing_end=start + timedelta(days=2),
    )

    context = build_market_context(sessions, [symbol], _small_config())

    sym = context.by_symbol["ACME"]
    assert sym.eligibility == (
        EligibilityWindow(start, start + timedelta(days=2), eligible=True),
        EligibilityWindow(start + timedelta(days=3), start + timedelta(days=4), eligible=False),
    )


# ---------------------------------------------------------------------------
# Sorted coalescing — deterministic symbol ordering
# ---------------------------------------------------------------------------


def test_symbols_emitted_in_sorted_order_regardless_of_input() -> None:
    start = date(2024, 1, 1)
    sessions = [start, start + timedelta(days=1)]
    zebra = _eligible_symbol("ZEBRA", start, bar_count=4, preceding=2)
    alpha = _eligible_symbol("ALPHA", start, bar_count=4, preceding=2)
    mid = _eligible_symbol("MID", start, bar_count=4, preceding=2)

    context = build_market_context(sessions, [zebra, alpha, mid], _small_config())

    assert tuple(context.by_symbol) == ("ALPHA", "MID", "ZEBRA")


# ---------------------------------------------------------------------------
# Corporate-action blockers — exact effective day, eligible only
# ---------------------------------------------------------------------------


def test_corporate_action_blocks_eligible_day() -> None:
    start = date(2024, 1, 1)
    sessions = [start, start + timedelta(days=1), start + timedelta(days=2)]
    action_day = start + timedelta(days=1)
    actions = (CorporateActionEvent(effective_date=action_day, kind="dividend", value=Decimal("0.5")),)
    symbol = _eligible_symbol("ACME", start, bar_count=5, preceding=2, actions=actions)

    context = build_market_context(sessions, [symbol], _small_config())

    sym = context.by_symbol["ACME"]
    assert sym.blockers == (
        BlockerWindow(action_day, action_day, reason=ContextReason.CORPORATE_ACTION),
    )
    # The blocker does not split eligibility — it overlays an eligible day.
    assert sym.eligibility == (
        EligibilityWindow(start, start + timedelta(days=2), eligible=True),
    )
    # status() confirms the blocked day is eligible with corporate-action reason.
    status = context.status("ACME", action_day)
    assert status.eligible is True
    assert status.reason is ContextReason.CORPORATE_ACTION


def test_corporate_action_omitted_on_ineligible_day() -> None:
    """A corporate action on a day when the symbol is ineligible produces no
    blocker — this preserves the invariant that blockers never overlap
    ineligible intervals."""
    start = date(2024, 1, 1)
    sessions = [start + timedelta(days=i) for i in range(5)]
    # Listing ends on day 2 so days 3-4 are ineligible.
    action_on_ineligible = start + timedelta(days=3)
    actions = (
        CorporateActionEvent(effective_date=action_on_ineligible, kind="split", value=Decimal("2")),
    )
    symbol = _eligible_symbol(
        "ACME", start, bar_count=7, preceding=2, listing_end=start + timedelta(days=2), actions=actions
    )

    context = build_market_context(sessions, [symbol], _small_config())

    sym = context.by_symbol["ACME"]
    assert sym.blockers == ()


def test_corporate_action_on_non_session_date_is_ignored() -> None:
    """An action whose effective date is not a requested output session is
    never shifted or anticipated — it is simply not emitted."""
    start = date(2024, 1, 1)
    sessions = [start, start + timedelta(days=1), start + timedelta(days=2)]
    non_session_day = start + timedelta(days=10)
    actions = (
        CorporateActionEvent(effective_date=non_session_day, kind="dividend", value=Decimal("1")),
    )
    symbol = _eligible_symbol("ACME", start, bar_count=5, preceding=2, actions=actions)

    context = build_market_context(sessions, [symbol], _small_config())

    assert context.by_symbol["ACME"].blockers == ()


def test_multiple_same_day_actions_collapse_to_one_blocker() -> None:
    start = date(2024, 1, 1)
    sessions = [start, start + timedelta(days=1), start + timedelta(days=2)]
    action_day = start + timedelta(days=1)
    actions = (
        CorporateActionEvent(action_day, "dividend", Decimal("0.5")),
        CorporateActionEvent(action_day, "split", Decimal("2")),
    )
    symbol = _eligible_symbol("ACME", start, bar_count=5, preceding=2, actions=actions)

    context = build_market_context(sessions, [symbol], _small_config())

    assert context.by_symbol["ACME"].blockers == (
        BlockerWindow(action_day, action_day, reason=ContextReason.CORPORATE_ACTION),
    )


def test_no_earnings_blocker_is_ever_emitted() -> None:
    """The builder must never emit an earnings-context-missing blocker."""
    start = date(2024, 1, 1)
    sessions = [start, start + timedelta(days=1), start + timedelta(days=2)]
    action_day = start + timedelta(days=1)
    actions = (CorporateActionEvent(action_day, "dividend", Decimal("0.5")),)
    symbol = _eligible_symbol("ACME", start, bar_count=5, preceding=2, actions=actions)

    context = build_market_context(sessions, [symbol], _small_config())

    for sym in context.by_symbol.values():
        for blocker in sym.blockers:
            assert blocker.reason is not ContextReason.EARNINGS_CONTEXT_MISSING


# ---------------------------------------------------------------------------
# Invariant safety, full coverage, and determinism
# ---------------------------------------------------------------------------


def test_output_passes_market_context_invariants_and_full_coverage() -> None:
    """A complex mix — two symbols, mixed eligibility, a corporate action —
    must construct a valid MarketContext whose ``require_complete`` succeeds
    for every emitted symbol on every requested session."""
    start = date(2024, 1, 1)
    sessions = [start + timedelta(days=i) for i in range(6)]
    action_day = start + timedelta(days=2)
    acme = _eligible_symbol(
        "ACME",
        start,
        bar_count=8,
        preceding=2,
        listing_end=start + timedelta(days=4),
        actions=(CorporateActionEvent(action_day, "dividend", Decimal("0.5")),),
    )
    beta = _eligible_symbol("BETA", start, bar_count=8, preceding=2)

    context = build_market_context(sessions, [acme, beta], _small_config())

    # Every emitted symbol must cover every requested session without raising.
    context.require_complete(dates=sessions, symbols=tuple(context.by_symbol))

    # ACME is eligible days 0-4, ineligible day 5 (post-delisting).
    assert context.status("ACME", start + timedelta(days=4)).eligible is True
    assert context.status("ACME", start + timedelta(days=5)).eligible is False
    # The corporate action blocks day 2 while staying eligible.
    assert context.status("ACME", action_day).reason is ContextReason.CORPORATE_ACTION


def test_build_is_deterministic_for_identical_inputs() -> None:
    start = date(2024, 1, 1)
    sessions = [start, start + timedelta(days=1), start + timedelta(days=2)]
    actions = (CorporateActionEvent(start + timedelta(days=1), "split", Decimal("3")),)
    symbol = _eligible_symbol("ACME", start, bar_count=5, preceding=2, actions=actions)

    first = build_market_context(sessions, [symbol], _small_config())
    second = build_market_context(sessions, [symbol], _small_config())

    assert tuple(first.by_symbol) == tuple(second.by_symbol)
    for sym in first.by_symbol:
        assert first.by_symbol[sym] == second.by_symbol[sym]


def test_empty_sessions_reject_an_empty_generation_span() -> None:
    with pytest.raises(MarketContextInvalidError) as error:
        build_market_context([], [], _small_config())

    assert error.value.reason == "market-context-invalid"


# ---------------------------------------------------------------------------
# Broad full-range processing -- approval tests for the sort-once path
# ---------------------------------------------------------------------------


def test_broad_range_all_eligible_single_window() -> None:
    """A broad range of sessions over many bars must produce one eligible
    window spanning the full session range (enough history from day 0)."""
    start = date(2024, 1, 1)
    sessions = [start + timedelta(days=i) for i in range(60)]
    symbol = _eligible_symbol("ACME", start, bar_count=80, preceding=20)

    context = build_market_context(sessions, [symbol], _small_config())

    sym = context.by_symbol["ACME"]
    assert len(sym.eligibility) == 1
    assert sym.eligibility[0].eligible is True
    assert sym.eligibility[0].start == start
    assert sym.eligibility[0].end == start + timedelta(days=59)


def test_broad_range_mid_delisting_splits_exactly() -> None:
    """A mid-range delisting over a broad session range must split eligibility
    exactly at the delisting boundary -- the optimized path must not shift it."""
    start = date(2024, 1, 1)
    sessions = [start + timedelta(days=i) for i in range(40)]
    symbol = _eligible_symbol(
        "ACME", start, bar_count=60, preceding=20, listing_end=start + timedelta(days=19)
    )

    context = build_market_context(sessions, [symbol], _small_config())

    sym = context.by_symbol["ACME"]
    assert sym.eligibility == (
        EligibilityWindow(start, start + timedelta(days=19), eligible=True),
        EligibilityWindow(start + timedelta(days=20), start + timedelta(days=39), eligible=False),
    )


def test_broad_range_identical_regardless_of_bar_input_order() -> None:
    """Eligibility output must be identical whether bars arrive chronologically
    or shuffled -- the sort-once path must not depend on input bar order."""
    start = date(2024, 1, 1)
    sessions = [start + timedelta(days=i) for i in range(30)]
    listing = ListingFacts(start - timedelta(days=10), start + timedelta(days=365), primary_common=True)
    bars_sorted = tuple(
        _bar("ACME", start - timedelta(days=10) + timedelta(days=i), Decimal("10"), 1_000_000)
        for i in range(50)
    )
    bars_shuffled = tuple(sorted(bars_sorted, key=lambda b: b.volume))

    ordered = build_market_context(
        sessions, [SymbolData("ACME", listing, bars_sorted)], _small_config()
    )
    shuffled = build_market_context(
        sessions, [SymbolData("ACME", listing, bars_shuffled)], _small_config()
    )

    assert ordered.by_symbol["ACME"] == shuffled.by_symbol["ACME"]
