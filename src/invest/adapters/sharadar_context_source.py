"""Backtest-only Sharadar market-context source.

Sole allowed importer/caller of ``SharadarTickersReader`` and
``SharadarActionsReader``. Discovers TICKERS, fetches SEP in listing-period
cohorts (reusing ``SharadarMarketDataReader.fetch_range`` unchanged), fetches
ACTIONS once, and returns immutable normalized ``GeneratorInputs``.
"""

from __future__ import annotations

from datetime import date
from typing import Callable

import exchange_calendars as xcals
import httpx

from invest.adapters.alpaca_market_data import MarketDataFetchError
from invest.adapters.sharadar_actions import SharadarActionsReader
from invest.adapters.sharadar_market_data import SharadarMarketDataReader
from invest.adapters.sharadar_tickers import SharadarTicker, SharadarTickersReader
from invest.application.generate_market_context import (
    GeneratorInputs,
    NormalizedAction,
    NormalizedListing,
)
from invest.domain.liquidity_screen import ScreenConfig
from invest.domain.models import DailyBar, Universe
from invest.domain.momentum_selection_scanner import HISTORY_DAYS


class SharadarContextSource:
    """Load normalized generator inputs from TICKERS, SEP, and ACTIONS."""

    # Pinned start: the default calendar begins at "now minus 20 years", a
    # floating boundary that makes deep warmup lookbacks underflow the first
    # session over time. Sharadar SEP begins ~1998; 1990 gives permanent headroom.
    XNYS_CALENDAR = xcals.get_calendar("XNYS", start="1990-01-01")

    def __init__(
        self,
        *,
        client: httpx.Client,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._client = client
        self._sleep = sleep
        tickers_kwargs: dict[str, object] = {"client": client}
        actions_kwargs: dict[str, object] = {"client": client}
        sep_kwargs: dict[str, object] = {"client": client}
        if sleep is not None:
            tickers_kwargs["sleep"] = sleep
            actions_kwargs["sleep"] = sleep
            sep_kwargs["sleep"] = sleep
        self._tickers = SharadarTickersReader(**tickers_kwargs)  # type: ignore[arg-type]
        self._actions = SharadarActionsReader(**actions_kwargs)  # type: ignore[arg-type]
        self._sep = SharadarMarketDataReader(**sep_kwargs)  # type: ignore[arg-type]

    def load(self, start: date, end: date, config: ScreenConfig) -> GeneratorInputs:
        if end < start:
            raise MarketDataFetchError("malformed-response", "end precedes start")

        sessions = tuple(
            session.date() for session in self.XNYS_CALENDAR.sessions_in_range(start, end)
        )
        if not sessions:
            raise MarketDataFetchError("malformed-response", "no XNYS sessions in range")

        tickers = self._tickers.fetch()
        candidates = self._normalize_candidates(tickers, start, end)
        bars = self._fetch_sep_cohorts(candidates, start, end, config)
        actions = self._fetch_actions({listing.symbol for listing in candidates})

        return GeneratorInputs(
            sessions=sessions,
            listings=candidates,
            bars=bars,
            actions=actions,
        )

    def _normalize_candidates(
        self,
        tickers: tuple[SharadarTicker, ...],
        start: date,
        end: date,
    ) -> tuple[NormalizedListing, ...]:
        by_ticker: dict[str, SharadarTicker] = {}
        for ticker in tickers:
            existing = by_ticker.get(ticker.ticker)
            if existing is None:
                by_ticker[ticker.ticker] = ticker
                continue
            if existing != ticker:
                raise MarketDataFetchError(
                    "malformed-response", f"conflicting TICKERS facts for {ticker.ticker}"
                )

        listings: list[NormalizedListing] = []
        for ticker in sorted(by_ticker.values(), key=lambda item: item.ticker):
            if not ticker.is_primary_common_stock:
                continue
            if ticker.listed_date is None:
                raise MarketDataFetchError(
                    "malformed-response", f"missing listed_date for {ticker.ticker}"
                )
            delisting = ticker.delisted_date if ticker.delisted_date is not None else date.max
            if delisting < ticker.listed_date:
                raise MarketDataFetchError(
                    "malformed-response", f"delisting precedes listing for {ticker.ticker}"
                )
            # Listing interval must intersect the requested range.
            if delisting < start or ticker.listed_date > end:
                continue
            listings.append(
                NormalizedListing(
                    symbol=ticker.ticker,
                    listing_date=ticker.listed_date,
                    delisting_date=delisting,
                    primary_common=True,
                )
            )
        return tuple(listings)

    def _fetch_sep_cohorts(
        self,
        candidates: tuple[NormalizedListing, ...],
        start: date,
        end: date,
        config: ScreenConfig,
    ) -> tuple[DailyBar, ...]:
        if not candidates:
            return ()

        needed = max(
            config.min_observed_bars,
            config.dollar_volume_window,
            HISTORY_DAYS,
        )
        cohorts: dict[tuple[date, date], list[str]] = {}
        for listing in candidates:
            fetch_start, fetch_end = self._cohort_window(listing, start, end, needed)
            cohorts.setdefault((fetch_start, fetch_end), []).append(listing.symbol)

        bars: list[DailyBar] = []
        for (fetch_start, fetch_end), symbols in sorted(cohorts.items()):
            universe = Universe("context-generator", tuple(sorted(symbols)))
            result = self._sep.fetch_range(universe, fetch_start, fetch_end)
            bars.extend(result.bars)
        return tuple(sorted(bars, key=lambda bar: (bar.symbol, bar.date)))

    def _cohort_window(
        self,
        listing: NormalizedListing,
        start: date,
        end: date,
        needed_bars: int,
    ) -> tuple[date, date]:
        active_start = max(listing.listing_date, start)
        active_end = min(listing.delisting_date, end)
        if active_end < active_start:
            raise MarketDataFetchError(
                "malformed-response", f"empty active window for {listing.symbol}"
            )

        first_session = self.XNYS_CALENDAR.date_to_session(active_start, direction="next")
        # This exchange-calendars version returns exactly ``n`` sessions for
        # sessions_window(session, -n), including ``session`` itself.
        if needed_bars <= 1:
            fetch_start = first_session.date()
        else:
            window = self.XNYS_CALENDAR.sessions_window(first_session, -needed_bars)
            fetch_start = window[0].date()

        # Never request SEP before listing: absent pre-listing rows are normal
        # (insufficient history), not incomplete/malformed coverage.
        fetch_start = max(fetch_start, listing.listing_date)

        return fetch_start, active_end

    def _fetch_actions(self, symbols: set[str]) -> tuple[NormalizedAction, ...]:
        raw_actions = self._actions.fetch()
        seen: set[tuple[str, date, str, str]] = set()
        normalized: list[NormalizedAction] = []
        for action in raw_actions:
            if action.ticker not in symbols:
                continue
            key = (
                action.ticker,
                action.effective_date,
                action.kind.value,
                "" if action.value is None else str(action.value),
            )
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                NormalizedAction(
                    symbol=action.ticker,
                    effective_date=action.effective_date,
                    kind=action.kind.value,
                    value=action.value,
                )
            )
        return tuple(
            sorted(
                normalized,
                key=lambda item: (
                    item.symbol,
                    item.effective_date,
                    item.kind,
                    "" if item.value is None else str(item.value),
                ),
            )
        )
