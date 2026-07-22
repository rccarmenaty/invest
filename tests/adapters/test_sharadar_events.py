from __future__ import annotations

from datetime import date
from hashlib import sha256

import httpx
import pytest

from invest.adapters.alpaca_market_data import MarketDataFetchError
from invest.adapters.sharadar_events import SharadarEvent, SharadarEventsReader


def _event(ticker: str, event_date: date, occurrence: int = 1) -> SharadarEvent:
    source_row_id = (
        "sharadar-events:"
        + sha256(f"{ticker}|{event_date.isoformat()}|22|{occurrence}".encode()).hexdigest()
    )
    return SharadarEvent(ticker, event_date, 22, source_row_id)


def _page(rows: list[list[object]], cursor: str | None = None) -> dict:
    return {
        "datatable": {
            "columns": [
                {"name": "ticker"},
                {"name": "date"},
                {"name": "eventcode"},
            ],
            "data": rows,
        },
        "meta": {"next_cursor_id": cursor},
    }


@pytest.fixture(autouse=True)
def _api_key(monkeypatch) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")


def test_fetch_returns_only_requested_events_in_deterministic_order() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=_page(
                [
                    ["BETA", "2024-02-02", 22],
                    ["ACME", "2024-01-03", 22],
                ]
            ),
        )

    reader = SharadarEventsReader(client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert reader.fetch(event_code=22) == (
        _event("ACME", date(2024, 1, 3)),
        _event("BETA", date(2024, 2, 2)),
    )
    assert requests[0].url.params["eventcode"] == "22"
    assert requests[0].url.params["qopts.columns"] == "ticker,date,eventcode"


def test_fetch_retries_transient_failures_without_losing_the_page() -> None:
    attempts = 0
    sleeps: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return httpx.Response(503)
        return httpx.Response(200, json=_page([["ACME", "2024-01-03", 22]]))

    reader = SharadarEventsReader(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=sleeps.append,
    )

    assert reader.fetch(event_code=22) == (_event("ACME", date(2024, 1, 3)),)
    assert attempts == 3
    assert sleeps == [0.5, 1.0]


def test_fetch_follows_provider_cursor_without_mixing_pages() -> None:
    cursors: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("qopts.cursor_id")
        cursors.append(cursor)
        if cursor is None:
            return httpx.Response(200, json=_page([["BETA", "2024-02-02", 22]], "page-2"))
        return httpx.Response(200, json=_page([["ACME", "2024-01-03", 22]]))

    reader = SharadarEventsReader(client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert reader.fetch(event_code=22) == (
        _event("ACME", date(2024, 1, 3)),
        _event("BETA", date(2024, 2, 2)),
    )
    assert cursors == [None, "page-2"]


def test_fetch_fails_closed_if_provider_returns_an_unrequested_code() -> None:
    reader = SharadarEventsReader(
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json=_page([["ACME", "2024-01-03", 21]]))
            )
        )
    )

    with pytest.raises(MarketDataFetchError, match="malformed-response"):
        reader.fetch(event_code=22)


def test_fetch_assigns_stable_distinct_ids_to_duplicate_provider_rows() -> None:
    reader = SharadarEventsReader(
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    json=_page(
                        [
                            ["ACME", "2024-01-03", 22],
                            ["ACME", "2024-01-03", 22],
                        ]
                    ),
                )
            )
        )
    )

    assert reader.fetch(event_code=22) == (
        _event("ACME", date(2024, 1, 3), 1),
        _event("ACME", date(2024, 1, 3), 2),
    )


def test_fetch_bounds_numeric_retry_after() -> None:
    attempts = 0
    sleeps: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "10"})
        return httpx.Response(200, json=_page([["ACME", "2024-01-03", 22]]))

    reader = SharadarEventsReader(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=sleeps.append,
    )

    assert reader.fetch(event_code=22) == (_event("ACME", date(2024, 1, 3)),)
    assert sleeps == [4.0]
