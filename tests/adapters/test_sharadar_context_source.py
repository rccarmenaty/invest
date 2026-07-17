"""Adapter tests for SharadarContextSource.

Covers MockTransport discovery of TICKERS primary/listing facts, ticker conflict
detection, preceding-XNYS SEP cohorts, complete unique SEP coverage, a single
ACTIONS fetch, and blank/exhausted pagination fail-closed behavior.
"""

from datetime import date
from decimal import Decimal

import httpx
import pytest

from invest.adapters.alpaca_market_data import MarketDataFetchError
from invest.domain.liquidity_screen import ScreenConfig


TICKERS_COLUMNS = (
    "ticker",
    "exchange",
    "category",
    "firstpricedate",
    "lastpricedate",
    "isdelisted",
)
SEP_COLUMNS = ("ticker", "date", "open", "high", "low", "close", "volume", "closeadj")
ACTIONS_COLUMNS = ("ticker", "date", "action", "value")


def _tickers_page(rows: list[list[object]], cursor: object = None) -> dict[str, object]:
    return {
        "datatable": {"columns": [{"name": name} for name in TICKERS_COLUMNS], "data": rows},
        "meta": {"next_cursor_id": cursor},
    }


def _sep_page(rows: list[list[object]], cursor: object = None) -> dict[str, object]:
    return {
        "datatable": {"columns": [{"name": name} for name in SEP_COLUMNS], "data": rows},
        "meta": {"next_cursor_id": cursor},
    }


def _actions_page(rows: list[list[object]], cursor: object = None) -> dict[str, object]:
    return {
        "datatable": {"columns": [{"name": name} for name in ACTIONS_COLUMNS], "data": rows},
        "meta": {"next_cursor_id": cursor},
    }


def _primary_row(
    ticker: str,
    listed: str = "2010-01-04",
    delisted: object = None,
    isdelisted: str = "N",
    exchange: str = "NYSE",
) -> list[object]:
    return [ticker, exchange, "Domestic Common Stock", listed, delisted, isdelisted]


def _small_config() -> ScreenConfig:
    return ScreenConfig(
        price_floor=Decimal("1"),
        dollar_volume_floor=Decimal("1"),
        dollar_volume_window=2,
        min_observed_bars=3,
    )


def _source(handler, sleeps: list[float] | None = None):
    from invest.adapters.sharadar_context_source import SharadarContextSource

    return SharadarContextSource(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=sleeps.append if sleeps is not None else lambda _: None,
    )


@pytest.fixture(autouse=True)
def _api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")


def _sessions_for(start: date, end: date) -> list[date]:
    import exchange_calendars as xcals

    calendar = xcals.get_calendar("XNYS")
    return [session.date() for session in calendar.sessions_in_range(start, end)]


def _sep_rows_for(symbols: tuple[str, ...], start: date, end: date) -> list[list[object]]:
    rows: list[list[object]] = []
    for session in _sessions_for(start, end):
        for symbol in symbols:
            rows.append(
                [
                    symbol,
                    session.isoformat(),
                    "10",
                    "11",
                    "9",
                    "10",
                    1_000_000,
                    "10",
                ]
            )
    return rows


def test_load_reuses_primary_common_and_listing_facts() -> None:
    from invest.adapters.sharadar_context_source import SharadarContextSource

    start = date(2024, 1, 2)
    end = date(2024, 1, 4)
    fetch_ranges: list[tuple[str, str, str]] = []
    action_requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal action_requests
        path = request.url.path
        if path.endswith("/TICKERS.json"):
            return httpx.Response(
                200,
                json=_tickers_page(
                    [
                        _primary_row("ACME", listed="2020-01-02"),
                        ["ETF", "NYSE", "Domestic ETF", "2010-01-04", None, "N"],
                    ]
                ),
            )
        if path.endswith("/SEP.json"):
            fetch_ranges.append(
                (
                    request.url.params["ticker"],
                    request.url.params["date.gte"],
                    request.url.params["date.lte"],
                )
            )
            gte = date.fromisoformat(request.url.params["date.gte"])
            lte = date.fromisoformat(request.url.params["date.lte"])
            return httpx.Response(200, json=_sep_page(_sep_rows_for(("ACME",), gte, lte)))
        if path.endswith("/ACTIONS.json"):
            action_requests += 1
            return httpx.Response(
                200,
                json=_actions_page([["ACME", "2024-01-03", "split", "2"]]),
            )
        raise AssertionError(f"unexpected path {path}")

    inputs = _source(handler).load(start, end, _small_config())

    assert isinstance(inputs.sessions, tuple)
    assert inputs.sessions == tuple(_sessions_for(start, end))
    assert len(inputs.listings) == 1
    listing = inputs.listings[0]
    assert listing.symbol == "ACME"
    assert listing.listing_date == date(2020, 1, 2)
    assert listing.primary_common is True
    assert listing.delisting_date == date.max
    assert all(bar.symbol == "ACME" for bar in inputs.bars)
    assert len(inputs.actions) == 1
    assert inputs.actions[0].kind == "split"
    assert inputs.actions[0].value == Decimal("2")
    assert action_requests == 1
    assert fetch_ranges  # SEP was fetched
    # Non-primary ETF must not become a listing candidate.
    assert all(item.symbol != "ETF" for item in inputs.listings)
    assert SharadarContextSource.__name__ == "SharadarContextSource"


def test_load_detects_conflicting_ticker_facts() -> None:
    start = date(2024, 1, 2)
    end = date(2024, 1, 4)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/TICKERS.json"):
            return httpx.Response(
                200,
                json=_tickers_page(
                    [
                        _primary_row("ACME", listed="2020-01-02"),
                        _primary_row("ACME", listed="2019-06-01"),  # conflict
                    ]
                ),
            )
        raise AssertionError("must fail before SEP/ACTIONS")

    with pytest.raises(MarketDataFetchError) as error:
        _source(handler).load(start, end, _small_config())

    assert error.value.reason == "malformed-response"


def test_load_coalesces_identical_duplicate_tickers() -> None:
    start = date(2024, 1, 2)
    end = date(2024, 1, 4)

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/TICKERS.json"):
            row = _primary_row("ACME", listed="2020-01-02")
            return httpx.Response(200, json=_tickers_page([row, list(row)]))
        if path.endswith("/SEP.json"):
            gte = date.fromisoformat(request.url.params["date.gte"])
            lte = date.fromisoformat(request.url.params["date.lte"])
            return httpx.Response(200, json=_sep_page(_sep_rows_for(("ACME",), gte, lte)))
        if path.endswith("/ACTIONS.json"):
            return httpx.Response(
                200, json=_actions_page([["ZZZZ", "2024-01-03", "split", "2"]])
            )
        raise AssertionError(path)

    inputs = _source(handler).load(start, end, _small_config())
    assert [listing.symbol for listing in inputs.listings] == ["ACME"]


def test_load_fetches_scanner_sufficient_preceding_xnys_sessions() -> None:
    start = date(2024, 1, 8)
    end = date(2024, 1, 10)
    config = _small_config()  # Core HISTORY_DAYS must dominate these smaller windows.
    sep_gte: list[date] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/TICKERS.json"):
            return httpx.Response(
                200, json=_tickers_page([_primary_row("ACME", listed="2010-01-04")])
            )
        if path.endswith("/SEP.json"):
            gte = date.fromisoformat(request.url.params["date.gte"])
            lte = date.fromisoformat(request.url.params["date.lte"])
            sep_gte.append(gte)
            return httpx.Response(200, json=_sep_page(_sep_rows_for(("ACME",), gte, lte)))
        if path.endswith("/ACTIONS.json"):
            return httpx.Response(
                200, json=_actions_page([["ZZZZ", "2024-01-03", "split", "2"]])
            )
        raise AssertionError(path)

    inputs = _source(handler).load(start, end, config)

    assert len(sep_gte) == 1
    expected_sessions = _sessions_for(sep_gte[0], start)
    assert len(expected_sessions) == 253
    # First fetch day must be strictly before the requested start.
    assert sep_gte[0] < start
    assert inputs.sessions[0] == start or inputs.sessions[0] >= start
    assert all(bar.date >= sep_gte[0] for bar in inputs.bars)


def test_load_batches_cohorts_sharing_clipped_listing_interval() -> None:
    start = date(2024, 1, 8)
    end = date(2024, 1, 10)
    sep_tickers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/TICKERS.json"):
            return httpx.Response(
                200,
                json=_tickers_page(
                    [
                        _primary_row("ACME", listed="2010-01-04"),
                        _primary_row("BETA", listed="2010-01-04"),
                        # Listed mid-range so its clipped window differs from ACME/BETA.
                        _primary_row("LATE", listed="2024-01-09"),
                    ]
                ),
            )
        if path.endswith("/SEP.json"):
            sep_tickers.append(request.url.params["ticker"])
            gte = date.fromisoformat(request.url.params["date.gte"])
            lte = date.fromisoformat(request.url.params["date.lte"])
            symbols = tuple(request.url.params["ticker"].split(","))
            return httpx.Response(200, json=_sep_page(_sep_rows_for(symbols, gte, lte)))
        if path.endswith("/ACTIONS.json"):
            return httpx.Response(
                200, json=_actions_page([["ZZZZ", "2024-01-03", "split", "2"]])
            )
        raise AssertionError(path)

    inputs = _source(handler).load(start, end, _small_config())

    # ACME+BETA share listing history → one cohort; LATE has a different clip.
    assert any("ACME" in tickers and "BETA" in tickers for tickers in sep_tickers)
    assert any(
        tickers == "LATE" or "LATE" in tickers.split(",") for tickers in sep_tickers
    )
    assert {listing.symbol for listing in inputs.listings} == {"ACME", "BETA", "LATE"}


def test_load_fetches_actions_exactly_once() -> None:
    start = date(2024, 1, 2)
    end = date(2024, 1, 4)
    action_hits = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal action_hits
        path = request.url.path
        if path.endswith("/TICKERS.json"):
            return httpx.Response(
                200,
                json=_tickers_page(
                    [
                        _primary_row("ACME", listed="2010-01-04"),
                        _primary_row("BETA", listed="2010-01-04"),
                    ]
                ),
            )
        if path.endswith("/SEP.json"):
            gte = date.fromisoformat(request.url.params["date.gte"])
            lte = date.fromisoformat(request.url.params["date.lte"])
            symbols = tuple(request.url.params["ticker"].split(","))
            return httpx.Response(200, json=_sep_page(_sep_rows_for(symbols, gte, lte)))
        if path.endswith("/ACTIONS.json"):
            action_hits += 1
            return httpx.Response(
                200,
                json=_actions_page(
                    [
                        ["ACME", "2024-01-03", "split", "2"],
                        ["BETA", "2024-01-03", "dividend", "0.25"],
                        ["OTHER", "2024-01-03", "split", "3"],
                    ]
                ),
            )
        raise AssertionError(path)

    inputs = _source(handler).load(start, end, _small_config())
    assert action_hits == 1
    assert sorted(action.symbol for action in inputs.actions) == ["ACME", "BETA"]


def test_load_propagates_blank_pagination_cursor() -> None:
    start = date(2024, 1, 2)
    end = date(2024, 1, 4)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/TICKERS.json"):
            return httpx.Response(200, json=_tickers_page([_primary_row("ACME")], cursor=""))
        raise AssertionError("must fail on TICKERS pagination")

    with pytest.raises(MarketDataFetchError, match="malformed-response"):
        _source(handler).load(start, end, _small_config())


def test_load_propagates_exhausted_pagination() -> None:
    start = date(2024, 1, 2)
    end = date(2024, 1, 4)
    from invest.adapters.sharadar_tickers import SharadarTickersReader

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/TICKERS.json"):
            return httpx.Response(
                200, json=_tickers_page([_primary_row("ACME")], cursor="more")
            )
        raise AssertionError("unexpected non-TICKERS request")

    # Cap pages to 1 so a continuing cursor exhausts immediately.
    original = SharadarTickersReader.MAX_PAGES
    SharadarTickersReader.MAX_PAGES = 1
    try:
        with pytest.raises(MarketDataFetchError, match="malformed-response"):
            _source(handler).load(start, end, _small_config())
    finally:
        SharadarTickersReader.MAX_PAGES = original


def test_load_rejects_missing_listed_date_as_malformed() -> None:
    start = date(2024, 1, 2)
    end = date(2024, 1, 4)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/TICKERS.json"):
            return httpx.Response(
                200,
                json=_tickers_page(
                    [["ACME", "NYSE", "Domestic Common Stock", None, None, "N"]]
                ),
            )
        raise AssertionError("must fail before SEP")

    with pytest.raises(MarketDataFetchError) as error:
        _source(handler).load(start, end, _small_config())
    assert error.value.reason == "malformed-response"


def test_load_clips_delisted_candidate_history() -> None:
    start = date(2024, 1, 2)
    end = date(2024, 1, 10)
    sep_lte: list[date] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/TICKERS.json"):
            return httpx.Response(
                200,
                json=_tickers_page(
                    [
                        _primary_row(
                            "OLD",
                            listed="2010-01-04",
                            delisted="2024-01-05",
                            isdelisted="Y",
                        )
                    ]
                ),
            )
        if path.endswith("/SEP.json"):
            gte = date.fromisoformat(request.url.params["date.gte"])
            lte = date.fromisoformat(request.url.params["date.lte"])
            sep_lte.append(lte)
            return httpx.Response(200, json=_sep_page(_sep_rows_for(("OLD",), gte, lte)))
        if path.endswith("/ACTIONS.json"):
            return httpx.Response(
                200, json=_actions_page([["ZZZZ", "2024-01-03", "split", "2"]])
            )
        raise AssertionError(path)

    inputs = _source(handler).load(start, end, _small_config())
    assert inputs.listings[0].delisting_date == date(2024, 1, 5)
    assert sep_lte
    assert sep_lte[0] == date(2024, 1, 5)


def test_load_accepts_new_listing_without_prelisting_sep() -> None:
    """Listing inside the range must not treat normal pre-listing SEP absence as malformed.

    Seasoning lookback may predate the listing, but only post-listing SEP exists.
    Generation must load (insufficient history is a later ineligible outcome).
    """
    start = date(2024, 1, 2)
    end = date(2024, 1, 12)
    listed = date(2024, 1, 8)
    config = _small_config()  # min_observed_bars=3
    sep_ranges: list[tuple[date, date]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/TICKERS.json"):
            return httpx.Response(
                200,
                json=_tickers_page([_primary_row("NEW", listed=listed.isoformat())]),
            )
        if path.endswith("/SEP.json"):
            gte = date.fromisoformat(request.url.params["date.gte"])
            lte = date.fromisoformat(request.url.params["date.lte"])
            sep_ranges.append((gte, lte))
            # Real SEP has no pre-listing rows — do not fabricate them.
            post_listing_start = max(gte, listed)
            if post_listing_start > lte:
                return httpx.Response(200, json=_sep_page([]))
            return httpx.Response(
                200, json=_sep_page(_sep_rows_for(("NEW",), post_listing_start, lte))
            )
        if path.endswith("/ACTIONS.json"):
            return httpx.Response(
                200, json=_actions_page([["ZZZZ", "2024-01-03", "split", "2"]])
            )
        raise AssertionError(path)

    inputs = _source(handler).load(start, end, config)

    assert sep_ranges
    assert all(gte >= listed for gte, _lte in sep_ranges)
    assert inputs.listings[0].symbol == "NEW"
    assert inputs.listings[0].listing_date == listed
    assert inputs.bars
    assert all(bar.date >= listed for bar in inputs.bars)


def test_new_listing_without_prelisting_sep_is_ineligible_until_seasoned() -> None:
    """Post-listing bars alone must flow to insufficient-history ineligibility, not abort."""
    from invest.application.generate_market_context import GenerateMarketContext

    start = date(2024, 1, 2)
    end = date(2024, 1, 12)
    listed = date(2024, 1, 8)
    config = _small_config()  # min_observed_bars=3

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/TICKERS.json"):
            return httpx.Response(
                200,
                json=_tickers_page([_primary_row("NEW", listed=listed.isoformat())]),
            )
        if path.endswith("/SEP.json"):
            gte = date.fromisoformat(request.url.params["date.gte"])
            lte = date.fromisoformat(request.url.params["date.lte"])
            post_listing_start = max(gte, listed)
            return httpx.Response(
                200, json=_sep_page(_sep_rows_for(("NEW",), post_listing_start, lte))
            )
        if path.endswith("/ACTIONS.json"):
            return httpx.Response(
                200, json=_actions_page([["ZZZZ", "2024-01-03", "split", "2"]])
            )
        raise AssertionError(path)

    inputs = _source(handler).load(start, end, config)
    context = GenerateMarketContext().run(inputs, config)

    assert "NEW" in context.by_symbol
    # First two post-listing sessions lack 3 observed bars; later ones are eligible.
    assert context.status("NEW", listed).eligible is False
    second = _sessions_for(listed, end)[1]
    assert context.status("NEW", second).eligible is False
    third = _sessions_for(listed, end)[2]
    assert context.status("NEW", third).eligible is True
