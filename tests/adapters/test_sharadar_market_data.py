from datetime import date
from decimal import Decimal

import httpx
import pytest

from invest.adapters.alpaca_market_data import MarketDataFetchError
from invest.adapters.sharadar_market_data import SharadarMarketDataReader
from invest.domain.models import DailyBar, Universe

COLUMNS = ("ticker", "date", "open", "high", "low", "close", "volume", "closeadj")


def _sep_page(rows: list[list[object]], cursor: str | None = None) -> dict[str, object]:
    return {
        "datatable": {
            "columns": [{"name": name} for name in COLUMNS],
            "data": rows,
        },
        "meta": {"next_cursor_id": cursor},
    }


def test_chunk_symbols_splits_at_the_character_budget_boundary() -> None:
    """Symbols that together exceed the budget split into ordered, in-budget chunks."""
    reader = SharadarMarketDataReader(client=httpx.Client())
    reader.MAX_TICKER_PARAM_CHARS = 9
    symbols = ("AAAA", "BBBB", "CCCC")

    chunks = list(reader._chunk_symbols(symbols))

    assert chunks == [("AAAA", "BBBB"), ("CCCC",)]
    assert all(len(",".join(chunk)) <= reader.MAX_TICKER_PARAM_CHARS for chunk in chunks)
    assert set().union(*chunks) == set(symbols)


def test_chunk_symbols_yields_one_chunk_when_within_budget() -> None:
    """A universe that fits inside the default budget stays a single chunk."""
    reader = SharadarMarketDataReader(client=httpx.Client())
    symbols = ("AAAA", "BBBB", "CCCC")

    chunks = list(reader._chunk_symbols(symbols))

    assert chunks == [symbols]


def test_chunk_symbols_fails_closed_for_a_single_symbol_over_budget() -> None:
    """A lone symbol that alone exceeds the budget cannot be split further."""
    reader = SharadarMarketDataReader(client=httpx.Client())
    reader.MAX_TICKER_PARAM_CHARS = 3

    with pytest.raises(MarketDataFetchError) as caught:
        list(reader._chunk_symbols(("AAAA",)))

    assert caught.value.reason == "request-too-large"


def test_fetch_uses_calendar_buffer_window_bounded_by_as_of(monkeypatch) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["date.gte"] == "2026-04-22"
        assert request.url.params["date.lte"] == "2026-06-01"
        sessions = SharadarMarketDataReader.XNYS_CALENDAR.sessions_in_range(
            date(2026, 4, 22), date(2026, 6, 1)
        )
        rows = [
            ["ACME", session.date().isoformat(), 10, 12, 9, 10, 100, 10] for session in sessions
        ]
        return httpx.Response(200, json=_sep_page(rows))

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = reader.fetch(Universe("v1", ("ACME",)), date(2026, 6, 1))

    assert result.universe == Universe("v1", ("ACME",))
    assert result.bars[0].date == date(2026, 4, 22)
    assert result.bars[-1].date == date(2026, 6, 1)


def test_fetch_range_maps_adjusted_sep_bars_in_deterministic_symbol_date_order(monkeypatch) -> None:
    """SEP's adjusted close drives adjusted O/H/L and deterministic FixtureInputs."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/SHARADAR/SEP.json")
        assert request.url.params["ticker"] == "BETA,ACME"
        assert request.url.params["date.gte"] == "2024-01-01"
        assert request.url.params["date.lte"] == "2024-01-02"
        assert (
            request.url.params["qopts.columns"] == "ticker,date,open,high,low,close,volume,closeadj"
        )
        assert request.url.params["api_key"] == "test-key"
        return httpx.Response(
            200,
            json=_sep_page(
                [
                    ["BETA", "2024-01-02", "10", "13", "8", "10", 250.125, "20"],
                    ["ACME", "2024-01-02", "5", "7", "4", "5", 100, "5"],
                ]
            ),
        )

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = reader.fetch_range(
        Universe("v1", ("BETA", "ACME")), date(2024, 1, 1), date(2024, 1, 2)
    )

    assert result.universe == Universe("v1", ("BETA", "ACME"))
    assert result.bars == (
        DailyBar(
            "ACME",
            date(2024, 1, 2),
            Decimal("5"),
            Decimal("7"),
            Decimal("4"),
            Decimal("5"),
            Decimal("100"),
        ),
        DailyBar(
            "BETA",
            date(2024, 1, 2),
            Decimal("20"),
            Decimal("26"),
            Decimal("16"),
            Decimal("20"),
            Decimal("250.125"),
        ),
    )
    assert isinstance(result.bars[1].volume, Decimal)
    assert result.bars[1].volume == Decimal("250.125")


def test_fetch_range_preserves_exact_fractional_sep_volume(monkeypatch) -> None:
    """Real adjusted SEP volume like 48037.936 must survive as exact Decimal."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_sep_page(
                [["ACME", "2024-01-02", "10", "11", "9", "10", "48037.936", "10"]]
            ),
        )

    result = SharadarMarketDataReader(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    ).fetch_range(Universe("v1", ("ACME",)), date(2024, 1, 2), date(2024, 1, 2))

    assert result.bars[0].volume == Decimal("48037.936")
    assert isinstance(result.bars[0].volume, Decimal)


def test_fetch_range_keeps_adjusted_ohlc_envelope_when_high_equals_close(
    monkeypatch,
) -> None:
    """Live GSBD 2024-12-13: high==close and closeadj ratio yields high slightly below close.

    Without an envelope clamp, bars fail JsonFixtureReader OHLC validation and
    offline backtest reports fixture-invalid.
    """
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_sep_page(
                # open, high, low, close, volume, closeadj — live GSBD shape
                [["GSBD", "2024-12-13", 12.83, 12.87, 12.75, 12.87, 622000.0, 9.711]]
            ),
        )

    result = SharadarMarketDataReader(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    ).fetch_range(Universe("v1", ("GSBD",)), date(2024, 12, 13), date(2024, 12, 13))

    bar = result.bars[0]
    assert bar.close == Decimal("9.711")
    assert bar.low <= bar.open <= bar.high
    assert bar.low <= bar.close <= bar.high
    assert bar.high >= bar.close



def test_fetch_range_reconciles_null_volume_as_a_retained_zero_volume_bar(monkeypatch) -> None:
    """A real SEP no-trade row remains complete and uses exact Decimal zero volume."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_sep_page(
                [["BAYA", "2024-12-31", "10.68", "10.68", "10.68", "10.68", None, "10.68"]]
            ),
        )

    result = SharadarMarketDataReader(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    ).fetch_range(Universe("v1", ("BAYA",)), date(2024, 12, 31), date(2024, 12, 31))

    assert result.bars == (
        DailyBar(
            "BAYA",
            date(2024, 12, 31),
            Decimal("10.68"),
            Decimal("10.68"),
            Decimal("10.68"),
            Decimal("10.68"),
            Decimal("0"),
        ),
    )
    assert isinstance(result.bars[0].volume, Decimal)


def test_fetch_range_rejects_null_non_volume_field_without_partial_bars(monkeypatch) -> None:
    """Null reconciliation is limited to volume; required prices remain fail-closed."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_sep_page([["BAYA", "2024-12-31", None, "10.68", "10.68", "10.68", 0, "10.68"]]),
        )

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("BAYA",)), date(2024, 12, 31), date(2024, 12, 31))

    assert caught.value.reason == "malformed-response"
    assert getattr(caught.value, "bars", None) is None


def test_fetch_range_rejects_negative_volume_without_partial_bars(monkeypatch) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_sep_page(
                [
                    ["ACME", "2024-01-02", 10, 11, 9, 10, 100, 10],
                    ["BETA", "2024-01-02", 10, 11, 9, 10, -1, 10],
                ]
            ),
        )

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("ACME", "BETA")), date(2024, 1, 2), date(2024, 1, 2))

    assert caught.value.reason == "malformed-response"
    assert getattr(caught.value, "bars", None) is None


def test_fetch_range_rejects_absent_volume_field_without_partial_bars(monkeypatch) -> None:
    """A missing volume column fails closed; null-volume reconciliation is not absence."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    columns_without_volume = (
        "ticker",
        "date",
        "open",
        "high",
        "low",
        "close",
        "closeadj",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "datatable": {
                    "columns": [{"name": name} for name in columns_without_volume],
                    "data": [["ACME", "2024-01-02", 10, 11, 9, 10, 10]],
                },
                "meta": {"next_cursor_id": None},
            },
        )

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("ACME",)), date(2024, 1, 2), date(2024, 1, 2))

    assert caught.value.reason == "malformed-response"
    assert getattr(caught.value, "bars", None) is None


def test_fetch_range_splits_an_oversized_universe_into_multiple_in_budget_requests(
    monkeypatch,
) -> None:
    """An over-budget universe issues N disjoint, in-budget ticker requests."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    captured_tickers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ticker_param = request.url.params["ticker"]
        captured_tickers.append(ticker_param)
        rows = [
            [ticker, "2024-01-02", 10, 11, 9, 10, 100, 10] for ticker in ticker_param.split(",")
        ]
        return httpx.Response(200, json=_sep_page(rows))

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    reader.MAX_TICKER_PARAM_CHARS = 9
    universe = Universe("v1", ("AAAA", "BBBB", "CCCC"))

    result = reader.fetch_range(universe, date(2024, 1, 2), date(2024, 1, 2))

    assert captured_tickers == ["AAAA,BBBB", "CCCC"]
    assert all(len(ticker) <= reader.MAX_TICKER_PARAM_CHARS for ticker in captured_tickers)
    requested_symbols = {symbol for ticker in captured_tickers for symbol in ticker.split(",")}
    assert requested_symbols == set(universe.symbols)
    assert {bar.symbol for bar in result.bars} == set(universe.symbols)


def test_fetch_range_merges_multi_chunk_bars_sorted_and_duplicate_free(monkeypatch) -> None:
    """Merged multi-chunk bars equal the unbounded-single-request expectation."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        ticker_param = request.url.params["ticker"]
        rows = [
            [ticker, "2024-01-02", 10, 11, 9, 10, 100, 10] for ticker in ticker_param.split(",")
        ]
        return httpx.Response(200, json=_sep_page(rows))

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    reader.MAX_TICKER_PARAM_CHARS = 9
    universe = Universe("v1", ("AAAA", "BBBB", "CCCC"))

    result = reader.fetch_range(universe, date(2024, 1, 2), date(2024, 1, 2))

    expected_bars = tuple(
        DailyBar(symbol, date(2024, 1, 2), Decimal("10"), Decimal("11"), Decimal("9"), Decimal("10"), Decimal("100"))
        for symbol in ("AAAA", "BBBB", "CCCC")
    )
    assert result.bars == expected_bars
    assert len({(bar.symbol, bar.date) for bar in result.bars}) == len(result.bars)
    assert list(result.bars) == sorted(result.bars, key=lambda bar: (bar.symbol, bar.date))


def test_fetch_range_fully_walks_a_multi_page_chunk_before_the_next_chunk(monkeypatch) -> None:
    """A chunk spanning multiple cursor pages is drained before the next chunk is fetched."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    call_order: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ticker_param = request.url.params["ticker"]
        cursor = request.url.params.get("qopts.cursor_id")
        call_order.append(f"{ticker_param}:{cursor}")
        if ticker_param == "AAAA,BBBB":
            if cursor is None:
                rows = [
                    ["AAAA", "2024-01-02", 10, 11, 9, 10, 100, 10],
                    ["BBBB", "2024-01-02", 10, 11, 9, 10, 100, 10],
                ]
                return httpx.Response(200, json=_sep_page(rows, "page-2"))
            rows = [
                ["AAAA", "2024-01-03", 10, 11, 9, 10, 100, 10],
                ["BBBB", "2024-01-03", 10, 11, 9, 10, 100, 10],
            ]
            return httpx.Response(200, json=_sep_page(rows))
        rows = [
            ["CCCC", "2024-01-02", 10, 11, 9, 10, 100, 10],
            ["CCCC", "2024-01-03", 10, 11, 9, 10, 100, 10],
        ]
        return httpx.Response(200, json=_sep_page(rows))

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    reader.MAX_TICKER_PARAM_CHARS = 9
    universe = Universe("v1", ("AAAA", "BBBB", "CCCC"))

    reader.fetch_range(universe, date(2024, 1, 2), date(2024, 1, 3))

    assert call_order == ["AAAA,BBBB:None", "AAAA,BBBB:page-2", "CCCC:None"]


def test_fetch_range_reports_a_symbol_missing_across_every_chunk_only_after_merge(
    monkeypatch,
) -> None:
    """Missing-symbol validation fires once, post-merge — not per chunk."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    requested_tickers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ticker_param = request.url.params["ticker"]
        requested_tickers.append(ticker_param)
        if ticker_param == "AAAA,BBBB":
            rows = [["AAAA", "2024-01-02", 10, 11, 9, 10, 100, 10]]
        else:
            rows = [["CCCC", "2024-01-02", 10, 11, 9, 10, 100, 10]]
        return httpx.Response(200, json=_sep_page(rows))

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    reader.MAX_TICKER_PARAM_CHARS = 9
    universe = Universe("v1", ("AAAA", "BBBB", "CCCC"))

    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(universe, date(2024, 1, 2), date(2024, 1, 2))

    assert caught.value.reason == "symbol-missing-at-fetch"
    assert "BBBB" in str(caught.value)
    assert requested_tickers == ["AAAA,BBBB", "CCCC"]


def test_fetch_range_reports_incomplete_merged_date_coverage_only_after_merge(
    monkeypatch,
) -> None:
    """Date-coverage validation fires once, post-merge — not per chunk."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    requested_tickers: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ticker_param = request.url.params["ticker"]
        requested_tickers.append(ticker_param)
        if ticker_param == "AAAA,BBBB":
            rows = [
                ["AAAA", "2024-01-02", 10, 11, 9, 10, 100, 10],
                ["BBBB", "2024-01-02", 10, 11, 9, 10, 100, 10],
                ["AAAA", "2024-01-03", 10, 11, 9, 10, 100, 10],
                ["BBBB", "2024-01-03", 10, 11, 9, 10, 100, 10],
            ]
        else:
            rows = [["CCCC", "2024-01-02", 10, 11, 9, 10, 100, 10]]
        return httpx.Response(200, json=_sep_page(rows))

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    reader.MAX_TICKER_PARAM_CHARS = 9
    universe = Universe("v1", ("AAAA", "BBBB", "CCCC"))

    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(universe, date(2024, 1, 2), date(2024, 1, 3))

    assert caught.value.reason == "malformed-response"
    assert "incomplete date coverage" in str(caught.value)
    assert requested_tickers == ["AAAA,BBBB", "CCCC"]


def test_fetch_range_merges_cursor_pages(monkeypatch) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    cursors: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("qopts.cursor_id")
        cursors.append(cursor)
        if cursor is None:
            return httpx.Response(
                200, json=_sep_page([["ACME", "2024-01-02", 10, 11, 9, 10, 100, 10]], "page-2")
            )
        assert cursor == "page-2"
        return httpx.Response(
            200, json=_sep_page([["ACME", "2024-01-03", 11, 12, 10, 11, 200, 11]])
        )

    result = SharadarMarketDataReader(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    ).fetch_range(Universe("v1", ("ACME",)), date(2024, 1, 1), date(2024, 1, 3))

    assert cursors == [None, "page-2"]
    assert [bar.date for bar in result.bars] == [date(2024, 1, 2), date(2024, 1, 3)]


def test_fetch_range_refuses_a_cursor_past_its_page_bound(monkeypatch) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            200,
            json=_sep_page([["ACME", "2024-01-02", 10, 11, 9, 10, 100, 10]], f"page-{requests}"),
        )

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    reader.MAX_PAGES = 2
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("ACME",)), date(2024, 1, 1), date(2024, 1, 31))

    assert caught.value.reason == "malformed-response"
    assert requests == 2


@pytest.mark.parametrize(
    "datatable",
    [
        {"columns": [], "data": []},
        {
            "columns": [{"name": name} for name in COLUMNS],
            "data": [],
        },
    ],
)
def test_fetch_range_fails_closed_for_empty_sep_responses(
    monkeypatch, datatable: dict[str, object]
) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"datatable": datatable, "meta": {"next_cursor_id": None}})

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("ACME",)), date(2024, 1, 1), date(2024, 1, 31))

    assert caught.value.reason == "malformed-response"


def test_fetch_range_rejects_rows_shorter_than_declared_columns(monkeypatch) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_sep_page([["ACME", "2024-01-02", 10, 11, 9, 10, 100]]))

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("ACME",)), date(2024, 1, 1), date(2024, 1, 5))

    assert caught.value.reason == "malformed-response"


def test_fetch_range_rejects_duplicate_symbol_date_rows(monkeypatch) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_sep_page(
                [
                    ["ACME", "2024-01-02", 10, 11, 9, 10, 100, 10],
                    ["ACME", "2024-01-02", 11, 12, 10, 11, 200, 11],
                ]
            ),
        )

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("ACME",)), date(2024, 1, 2), date(2024, 1, 2))

    assert caught.value.reason == "malformed-response"


def test_fetch_range_rejects_duplicate_symbol_date_rows_across_cursor_pages(monkeypatch) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("qopts.cursor_id") is None:
            return httpx.Response(
                200, json=_sep_page([["ACME", "2024-01-02", 10, 11, 9, 10, 100, 10]], "page-2")
            )
        assert request.url.params["qopts.cursor_id"] == "page-2"
        return httpx.Response(200, json=_sep_page([["ACME", "2024-01-02", 10, 11, 9, 10, 100, 10]]))

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("ACME",)), date(2024, 1, 2), date(2024, 1, 2))

    assert caught.value.reason == "malformed-response"


def test_fetch_range_rejects_incomplete_symbol_date_coverage(monkeypatch) -> None:
    """A reported trading date must contain a bar for every requested symbol."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_sep_page(
                [
                    ["ACME", "2024-01-02", 10, 11, 9, 10, 100, 10],
                    ["BETA", "2024-01-02", 10, 11, 9, 10, 100, 10],
                    ["BETA", "2024-01-03", 11, 12, 10, 11, 200, 11],
                ]
            ),
        )

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("ACME", "BETA")), date(2024, 1, 1), date(2024, 1, 5))

    assert caught.value.reason == "malformed-response"


def test_fetch_range_rejects_an_xnys_session_missing_for_every_symbol(monkeypatch) -> None:
    """Every requested XNYS session needs a complete universe response."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_sep_page(
                [
                    ["ACME", "2024-01-02", 10, 11, 9, 10, 100, 10],
                    ["BETA", "2024-01-02", 10, 11, 9, 10, 100, 10],
                ]
            ),
        )

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("ACME", "BETA")), date(2024, 1, 2), date(2024, 1, 3))

    assert caught.value.reason == "malformed-response"
    assert "incomplete date coverage" in str(caught.value)


def test_fetch_range_does_not_require_bars_for_non_xnys_session_dates(monkeypatch) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_sep_page([["ACME", "2023-07-03", 10, 11, 9, 10, 100, 10]]))

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = reader.fetch_range(Universe("v1", ("ACME",)), date(2023, 7, 3), date(2023, 7, 4))

    assert [bar.date for bar in result.bars] == [date(2023, 7, 3)]


def test_fetch_range_rejects_a_universe_symbol_missing_from_sep(monkeypatch) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_sep_page([["ACME", "2024-01-02", 10, 11, 9, 10, 100, 10]]))

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("ACME", "MISSING")), date(2024, 1, 1), date(2024, 1, 31))

    assert caught.value.reason == "symbol-missing-at-fetch"
    assert "MISSING" in str(caught.value)


@pytest.mark.parametrize("key", [None, ""])
def test_fetch_range_rejects_absent_or_empty_nasdaq_key_before_request(
    monkeypatch, key: str | None
) -> None:
    if key is None:
        monkeypatch.delenv("NASDAQ_DATA_LINK_API_KEY", raising=False)
    else:
        monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", key)

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("a missing key must stop before the HTTP request")

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("ACME",)), date(2024, 1, 1), date(2024, 1, 31))

    assert caught.value.reason == "auth-failure"


def test_send_labels_a_414_response_as_request_too_large_without_retry(monkeypatch) -> None:
    """A 414 (URI too long) is a distinct, non-retryable reason from generic network-failure."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(414, json={"error": "uri too long"})

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("ACME",)), date(2024, 1, 1), date(2024, 1, 31))

    assert caught.value.reason == "request-too-large"
    assert attempts == 1


@pytest.mark.parametrize("status", [401, 403])
def test_auth_responses_fail_without_retry(monkeypatch, status: int) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status, json={"error": "unauthorized"})

    reader = SharadarMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("ACME",)), date(2024, 1, 1), date(2024, 1, 31))

    assert caught.value.reason == "auth-failure"
    assert attempts == 1


def test_retryable_status_uses_deterministic_backoff_for_http_date_retry_after(monkeypatch) -> None:
    """HTTP-date Retry-After values need a clock, so they use the bounded fallback."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    attempts = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(429, headers={"Retry-After": "Tue, 14 Jul 2036 12:00:00 GMT"})

    reader = SharadarMarketDataReader(
        client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=sleeps.append
    )
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("ACME",)), date(2024, 1, 1), date(2024, 1, 31))

    assert caught.value.reason == "rate-limited"
    assert attempts == 3
    assert sleeps == [0.5, 1.0]


def test_request_errors_retry_then_raise_network_failure(monkeypatch) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    attempts = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("connection refused", request=request)

    reader = SharadarMarketDataReader(
        client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=sleeps.append
    )
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("ACME",)), date(2024, 1, 1), date(2024, 1, 31))

    assert caught.value.reason == "network-failure"
    assert attempts == 3
    assert sleeps == [0.5, 1.0]


@pytest.mark.parametrize(
    ("status", "headers", "reason", "expected_sleeps"),
    [
        (429, {"Retry-After": "2"}, "rate-limited", [2.0, 2.0]),
        (429, {"Retry-After": "-2"}, "rate-limited", [0.0, 0.0]),
        (429, {"Retry-After": "NaN"}, "rate-limited", [0.5, 1.0]),
        (503, {}, "network-failure", [0.5, 1.0]),
    ],
)
def test_retryable_statuses_use_bounded_retry_and_retry_after(
    monkeypatch,
    status: int,
    headers: dict[str, str],
    reason: str,
    expected_sleeps: list[float],
) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    attempts = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status, headers=headers)

    reader = SharadarMarketDataReader(
        client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=sleeps.append
    )
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch_range(Universe("v1", ("ACME",)), date(2024, 1, 1), date(2024, 1, 31))

    assert caught.value.reason == reason
    assert attempts == 3
    assert sleeps == expected_sleeps
