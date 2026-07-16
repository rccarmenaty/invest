"""Application-layer tests for GenerateMarketContext.

Covers immutable normalized inputs, mapping of malformed/partial data to
reference-data-incomplete, rejection of raw Sharadar reader classes, and
successful build of a MarketContext through the domain builder.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from invest.domain.liquidity_screen import ScreenConfig
from invest.domain.models import DailyBar


def _bar(symbol: str, day: date, close: Decimal = Decimal("10"), volume: int = 1_000_000) -> DailyBar:
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


def _eligible_bars(
    symbol: str, start: date, *, count: int = 3, preceding: int = 2
) -> tuple[DailyBar, ...]:
    """Emit ``preceding`` history bars before ``start`` so day-0 can be eligible."""
    first = start - timedelta(days=preceding)
    total = count + preceding
    return tuple(_bar(symbol, first + timedelta(days=i)) for i in range(total))


def test_generator_inputs_are_immutable() -> None:
    from invest.application.generate_market_context import (
        GeneratorInputs,
        NormalizedAction,
        NormalizedListing,
    )

    start = date(2024, 1, 1)
    inputs = GeneratorInputs(
        sessions=(start, start + timedelta(days=1), start + timedelta(days=2)),
        listings=(
            NormalizedListing(
                symbol="ACME",
                listing_date=start,
                delisting_date=start + timedelta(days=365),
                primary_common=True,
            ),
        ),
        bars=_eligible_bars("ACME", start),
        actions=(
            NormalizedAction(
                symbol="ACME",
                effective_date=start + timedelta(days=1),
                kind="split",
                value=Decimal("2"),
            ),
        ),
    )

    with pytest.raises(AttributeError):
        inputs.sessions = ()  # type: ignore[misc]
    with pytest.raises(AttributeError):
        inputs.listings[0].symbol = "X"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        inputs.actions[0].value = Decimal("1")  # type: ignore[misc]


def test_run_builds_market_context_for_eligible_symbol() -> None:
    from invest.application.generate_market_context import (
        GenerateMarketContext,
        GeneratorInputs,
        NormalizedListing,
    )

    start = date(2024, 1, 1)
    sessions = (start, start + timedelta(days=1), start + timedelta(days=2))
    listing_start = start - timedelta(days=2)
    inputs = GeneratorInputs(
        sessions=sessions,
        listings=(
            NormalizedListing(
                symbol="ACME",
                listing_date=listing_start,
                delisting_date=start + timedelta(days=365),
                primary_common=True,
            ),
        ),
        bars=_eligible_bars("ACME", start, preceding=2),
        actions=(),
    )

    context = GenerateMarketContext().run(inputs, _small_config())

    assert set(context.by_symbol) == {"ACME"}
    assert context.status("ACME", start).eligible is True
    assert context.status("ACME", start + timedelta(days=2)).eligible is True


def test_run_maps_orphan_bars_to_reference_data_incomplete() -> None:
    """Bars for a symbol with no listing fact fail closed as incomplete."""
    from invest.application.generate_market_context import (
        GenerateMarketContext,
        GeneratorInputs,
        NormalizedListing,
        ReferenceDataIncompleteError,
    )

    start = date(2024, 1, 1)
    inputs = GeneratorInputs(
        sessions=(start, start + timedelta(days=1), start + timedelta(days=2)),
        listings=(
            NormalizedListing(
                symbol="ACME",
                listing_date=start,
                delisting_date=start + timedelta(days=365),
                primary_common=True,
            ),
        ),
        bars=_eligible_bars("OTHER", start),
        actions=(),
    )

    with pytest.raises(ReferenceDataIncompleteError) as error:
        GenerateMarketContext().run(inputs, _small_config())

    assert error.value.reason == "reference-data-incomplete"


def test_run_maps_orphan_actions_to_reference_data_incomplete() -> None:
    from invest.application.generate_market_context import (
        GenerateMarketContext,
        GeneratorInputs,
        NormalizedAction,
        NormalizedListing,
        ReferenceDataIncompleteError,
    )

    start = date(2024, 1, 1)
    inputs = GeneratorInputs(
        sessions=(start, start + timedelta(days=1), start + timedelta(days=2)),
        listings=(
            NormalizedListing(
                symbol="ACME",
                listing_date=start,
                delisting_date=start + timedelta(days=365),
                primary_common=True,
            ),
        ),
        bars=_eligible_bars("ACME", start),
        actions=(
            NormalizedAction(
                symbol="OTHER",
                effective_date=start + timedelta(days=1),
                kind="split",
                value=Decimal("2"),
            ),
        ),
    )

    with pytest.raises(ReferenceDataIncompleteError) as error:
        GenerateMarketContext().run(inputs, _small_config())

    assert error.value.reason == "reference-data-incomplete"


def test_run_maps_partial_listing_without_sessions_to_reference_data_incomplete() -> None:
    from invest.application.generate_market_context import (
        GenerateMarketContext,
        GeneratorInputs,
        NormalizedListing,
        ReferenceDataIncompleteError,
    )

    start = date(2024, 1, 1)
    inputs = GeneratorInputs(
        sessions=(),
        listings=(
            NormalizedListing(
                symbol="ACME",
                listing_date=start,
                delisting_date=start + timedelta(days=365),
                primary_common=True,
            ),
        ),
        bars=_eligible_bars("ACME", start),
        actions=(),
    )

    with pytest.raises(ReferenceDataIncompleteError) as error:
        GenerateMarketContext().run(inputs, _small_config())

    assert error.value.reason == "reference-data-incomplete"


def test_run_rejects_raw_sharadar_ticker_classes() -> None:
    from invest.adapters.sharadar_tickers import SharadarTicker
    from invest.application.generate_market_context import (
        GenerateMarketContext,
        GeneratorInputs,
        ReferenceDataIncompleteError,
    )

    start = date(2024, 1, 1)
    raw = SharadarTicker("ACME", True, True, start, None)

    with pytest.raises((TypeError, ReferenceDataIncompleteError)):
        GenerateMarketContext().run(
            GeneratorInputs(
                sessions=(start,),
                listings=(raw,),  # type: ignore[arg-type]
                bars=(),
                actions=(),
            ),
            _small_config(),
        )


def test_run_rejects_raw_sharadar_action_classes() -> None:
    from invest.adapters.sharadar_actions import SharadarAction, SharadarActionKind
    from invest.application.generate_market_context import (
        GenerateMarketContext,
        GeneratorInputs,
        NormalizedListing,
        ReferenceDataIncompleteError,
    )

    start = date(2024, 1, 1)
    raw = SharadarAction("ACME", start, SharadarActionKind.SPLIT, Decimal("2"))

    with pytest.raises((TypeError, ReferenceDataIncompleteError)):
        GenerateMarketContext().run(
            GeneratorInputs(
                sessions=(start, start + timedelta(days=1), start + timedelta(days=2)),
                listings=(
                    NormalizedListing(
                        symbol="ACME",
                        listing_date=start,
                        delisting_date=start + timedelta(days=365),
                        primary_common=True,
                    ),
                ),
                bars=_eligible_bars("ACME", start),
                actions=(raw,),  # type: ignore[arg-type]
            ),
            _small_config(),
        )


def test_run_applies_corporate_action_blocker_on_eligible_day() -> None:
    from invest.application.generate_market_context import (
        GenerateMarketContext,
        GeneratorInputs,
        NormalizedAction,
        NormalizedListing,
    )
    from invest.domain.market_context import ContextReason

    start = date(2024, 1, 1)
    sessions = (start, start + timedelta(days=1), start + timedelta(days=2))
    action_day = start + timedelta(days=1)
    listing_start = start - timedelta(days=2)
    inputs = GeneratorInputs(
        sessions=sessions,
        listings=(
            NormalizedListing(
                symbol="ACME",
                listing_date=listing_start,
                delisting_date=start + timedelta(days=365),
                primary_common=True,
            ),
        ),
        bars=_eligible_bars("ACME", start, preceding=2),
        actions=(
            NormalizedAction(
                symbol="ACME",
                effective_date=action_day,
                kind="split",
                value=Decimal("2"),
            ),
        ),
    )

    context = GenerateMarketContext().run(inputs, _small_config())

    status = context.status("ACME", action_day)
    assert status.eligible is True
    assert status.reason is ContextReason.CORPORATE_ACTION


def test_run_maps_valueless_action_without_crashing() -> None:
    """Delisting/ticker-change actions carry no value; application must accept None."""
    from invest.application.generate_market_context import (
        GenerateMarketContext,
        GeneratorInputs,
        NormalizedAction,
        NormalizedListing,
    )

    start = date(2024, 1, 1)
    sessions = (start, start + timedelta(days=1), start + timedelta(days=2))
    listing_start = start - timedelta(days=2)
    inputs = GeneratorInputs(
        sessions=sessions,
        listings=(
            NormalizedListing(
                symbol="ACME",
                listing_date=listing_start,
                delisting_date=start + timedelta(days=365),
                primary_common=True,
            ),
        ),
        bars=_eligible_bars("ACME", start, preceding=2),
        actions=(
            NormalizedAction(
                symbol="ACME",
                effective_date=start + timedelta(days=1),
                kind="delisting",
                value=None,
            ),
        ),
    )

    context = GenerateMarketContext().run(inputs, _small_config())
    assert "ACME" in context.by_symbol
