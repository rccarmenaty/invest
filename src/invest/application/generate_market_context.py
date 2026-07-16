"""Application use case: build MarketContext from normalized generator inputs.

Coordinates adapter-normalized listing/action facts and adjusted DailyBars into
the pure domain builder. Raw Sharadar reader classes never enter this layer.
Malformed or partial inputs fail closed as ``reference-data-incomplete``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Sequence

from invest.domain.liquidity_screen import ListingFacts, ScreenConfig
from invest.domain.market_context import MarketContext
from invest.domain.market_context_builder import (
    CorporateActionEvent,
    SymbolData,
    build_market_context,
)
from invest.domain.models import DailyBar


class ReferenceDataIncompleteError(ValueError):
    """Normalized inputs are incomplete or malformed for context generation."""

    def __init__(self, message: str = "reference data incomplete") -> None:
        self.reason = "reference-data-incomplete"
        super().__init__(message)


@dataclass(frozen=True)
class NormalizedListing:
    symbol: str
    listing_date: date
    delisting_date: date
    primary_common: bool


@dataclass(frozen=True)
class NormalizedAction:
    symbol: str
    effective_date: date
    kind: str
    value: Decimal | None


@dataclass(frozen=True)
class GeneratorInputs:
    sessions: tuple[date, ...]
    listings: tuple[NormalizedListing, ...]
    bars: tuple[DailyBar, ...]
    actions: tuple[NormalizedAction, ...]


class GenerateMarketContext:
    """Map normalized inputs through the domain builder to a MarketContext."""

    def run(self, inputs: GeneratorInputs, config: ScreenConfig) -> MarketContext:
        if not isinstance(inputs, GeneratorInputs):
            raise TypeError("inputs must be GeneratorInputs")
        if not inputs.sessions:
            raise ReferenceDataIncompleteError("requested sessions are empty")

        try:
            self._assert_normalized_listings(inputs.listings)
            self._assert_normalized_actions(inputs.actions)
            symbol_data = self._to_symbol_data(inputs)
            return build_market_context(inputs.sessions, symbol_data, config)
        except ReferenceDataIncompleteError:
            raise
        except (TypeError, ValueError, AttributeError) as error:
            raise ReferenceDataIncompleteError(str(error)) from error

    @staticmethod
    def _assert_normalized_listings(listings: Sequence[object]) -> None:
        for listing in listings:
            if not isinstance(listing, NormalizedListing):
                raise TypeError("listings must be NormalizedListing instances")

    @staticmethod
    def _assert_normalized_actions(actions: Sequence[object]) -> None:
        for action in actions:
            if not isinstance(action, NormalizedAction):
                raise TypeError("actions must be NormalizedAction instances")

    def _to_symbol_data(self, inputs: GeneratorInputs) -> list[SymbolData]:
        listing_symbols = {listing.symbol for listing in inputs.listings}

        bars_by_symbol: dict[str, list[DailyBar]] = {}
        for bar in inputs.bars:
            bars_by_symbol.setdefault(bar.symbol, []).append(bar)
        orphan_bars = sorted(set(bars_by_symbol) - listing_symbols)
        if orphan_bars:
            raise ReferenceDataIncompleteError(
                f"bars without listing facts: {','.join(orphan_bars)}"
            )

        actions_by_symbol: dict[str, list[CorporateActionEvent]] = {}
        for action in inputs.actions:
            if action.symbol not in listing_symbols:
                raise ReferenceDataIncompleteError(
                    f"action without listing facts: {action.symbol}"
                )
            value = action.value if action.value is not None else Decimal("0")
            actions_by_symbol.setdefault(action.symbol, []).append(
                CorporateActionEvent(
                    effective_date=action.effective_date,
                    kind=action.kind,
                    value=value,
                )
            )

        symbol_data: list[SymbolData] = []
        for listing in inputs.listings:
            symbol_data.append(
                SymbolData(
                    symbol=listing.symbol,
                    listing=ListingFacts(
                        listing_date=listing.listing_date,
                        delisting_date=listing.delisting_date,
                        primary_common=listing.primary_common,
                    ),
                    bars=tuple(bars_by_symbol.get(listing.symbol, ())),
                    actions=tuple(actions_by_symbol.get(listing.symbol, ())),
                )
            )
        return symbol_data
