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
                    ["BETA", "2024-01-02", "10", "13", "8", "10", 250, "20"],
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
            "ACME", date(2024, 1, 2), Decimal("5"), Decimal("7"), Decimal("4"), Decimal("5"), 100
        ),
        DailyBar(
            "BETA",
            date(2024, 1, 2),
            Decimal("20"),
            Decimal("26"),
            Decimal("16"),
            Decimal("20"),
            250,
        ),
    )


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


@pytest.mark.parametrize(
    ("status", "headers", "reason", "expected_sleeps"),
    [
        (429, {"Retry-After": "2"}, "rate-limited", [2.0, 2.0]),
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
