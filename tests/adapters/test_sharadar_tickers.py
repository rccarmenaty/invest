from datetime import date

import httpx
import pytest

from invest.adapters.alpaca_market_data import MarketDataFetchError
from invest.adapters.sharadar_tickers import SharadarTicker, SharadarTickersReader


COLUMNS = ("ticker", "exchange", "category", "firstpricedate", "lastpricedate", "isdelisted")
ROW = ["ACME", "NYSE", "Domestic Common Stock", "2010-01-04", None, "N"]


def _page(rows: list[list[object]], cursor: object = None, columns: tuple[str, ...] = COLUMNS):
    return {
        "datatable": {"columns": [{"name": name} for name in columns], "data": rows},
        "meta": {"next_cursor_id": cursor},
    }


def _reader(handler, sleeps: list[float] | None = None) -> SharadarTickersReader:
    return SharadarTickersReader(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=sleeps.append if sleeps is not None else lambda _: None,
    )


@pytest.fixture(autouse=True)
def _api_key(monkeypatch) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")


def test_reader_requires_a_client_and_uses_only_the_fixed_request_shape() -> None:
    with pytest.raises(TypeError):
        SharadarTickersReader()  # type: ignore[call-arg]

    requests: list[httpx.Request] = []
    reader = _reader(lambda request: (requests.append(request), httpx.Response(401))[1])
    with pytest.raises(TypeError):
        reader.fetch("unexpected")  # type: ignore[call-arg]
    with pytest.raises(MarketDataFetchError, match="auth-failure"):
        reader.fetch()

    assert len(requests) == 1
    assert requests[0].url.params["qopts.columns"] == ",".join(COLUMNS)
    assert requests[0].url.params["api_key"] == "test-key"


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        (ROW, SharadarTicker("ACME", True, True, date(2010, 1, 4), None)),
        (
            ["OLD", "NASDAQ", "Domestic Common Stock", "2000-01-03", "2022-12-30", "Y"],
            SharadarTicker("OLD", True, False, date(2000, 1, 3), date(2022, 12, 30)),
        ),
        (
            ["ETF", "NYSE", "Domestic ETF", "2010-01-04", None, "N"],
            SharadarTicker("ETF", False, True, date(2010, 1, 4), None),
        ),
        (
            ["LSE", "LSE", "Domestic Common Stock", "2010-01-04", None, "N"],
            SharadarTicker("LSE", False, True, date(2010, 1, 4), None),
        ),
        (
            ["UNK", "NYSE", "Unknown", "2010-01-04", None, "N"],
            SharadarTicker("UNK", False, True, date(2010, 1, 4), None),
        ),
    ],
)
def test_fetch_translates_closed_classifications_and_dates(row, expected) -> None:
    result = _reader(lambda _: httpx.Response(200, json=_page([row]))).fetch()
    assert isinstance(result, tuple)
    assert len(result) == 1
    assert result[0] == expected
    assert set(SharadarTicker.__dataclass_fields__) == {
        "ticker",
        "is_primary_common_stock",
        "is_listed",
        "listed_date",
        "delisted_date",
    }
    assert "category" not in SharadarTicker.__dataclass_fields__
    assert "exchange" not in SharadarTicker.__dataclass_fields__


def test_fetch_follows_cursor_and_sorts_tickers() -> None:
    cursors: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cursors.append(request.url.params.get("qopts.cursor_id"))
        return httpx.Response(
            200, json=_page([["BETA", *ROW[1:]]], "two") if len(cursors) == 1 else _page([ROW])
        )

    result = _reader(handler).fetch()
    assert cursors == [None, "two"]
    assert [ticker.ticker for ticker in result] == ["ACME", "BETA"]


@pytest.mark.parametrize(
    "payload",
    [
        _page([], columns=()),
        _page([["ACME"]], columns=("ticker",)),
        _page([["ACME", "NYSE"]]),
        _page([["   ", *ROW[1:]]]),
        _page([["ACME", "", *ROW[2:]]]),
    ],
)
def test_fetch_rejects_empty_incomplete_or_schema_invalid_pages(payload) -> None:
    with pytest.raises(MarketDataFetchError, match="malformed-response"):
        _reader(lambda _: httpx.Response(200, json=payload)).fetch()


@pytest.mark.parametrize("cursor", ["", "   ", 42])
def test_fetch_rejects_invalid_cursor_without_a_continuation_request(cursor) -> None:
    requests = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json=_page([ROW], cursor))

    with pytest.raises(MarketDataFetchError, match="malformed-response"):
        _reader(handler).fetch()
    assert requests == 1


def test_fetch_rejects_a_malformed_second_page_without_a_partial_result() -> None:
    responses = [_page([ROW], "two"), {"datatable": {}}]
    with pytest.raises(MarketDataFetchError, match="malformed-response"):
        _reader(lambda _: httpx.Response(200, json=responses.pop(0))).fetch()
    assert responses == []


def test_fetch_rejects_a_cursor_after_the_page_bound() -> None:
    requests = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json=_page([ROW], "more"))

    reader = _reader(handler)
    reader.MAX_PAGES = 2  # type: ignore[assignment]
    with pytest.raises(MarketDataFetchError, match="malformed-response"):
        reader.fetch()
    assert requests == 2


@pytest.mark.parametrize("key", [None, ""])
def test_missing_or_empty_key_fails_before_transport(monkeypatch, key) -> None:
    if key is None:
        monkeypatch.delenv("NASDAQ_DATA_LINK_API_KEY")
    else:
        monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", key)
    with pytest.raises(MarketDataFetchError, match="auth-failure"):
        _reader(lambda _: pytest.fail("transport must not be called")).fetch()


@pytest.mark.parametrize(
    ("respond", "reason"),
    [
        (lambda _: httpx.Response(401), "auth-failure"),
        (lambda _: httpx.Response(429), "rate-limited"),
        (lambda _: httpx.Response(500), "network-failure"),
        (lambda _: httpx.Response(200, json={"unexpected": "shape"}), "malformed-response"),
    ],
)
def test_no_error_reason_exposes_the_api_key(respond, reason) -> None:
    """The key travels in the query string, so every raise path must stay key-free."""
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return respond(request)

    with pytest.raises(MarketDataFetchError, match=reason) as caught:
        _reader(handler).fetch()

    assert "test-key" in str(sent[0].url)
    assert "test-key" not in str(caught.value)


@pytest.mark.parametrize("status", [401, 403])
def test_auth_responses_are_not_retried(status) -> None:
    attempts, sleeps = 0, []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status)

    with pytest.raises(MarketDataFetchError, match="auth-failure"):
        _reader(handler, sleeps).fetch()
    assert attempts == 1
    assert sleeps == []


@pytest.mark.parametrize(("status", "reason"), [(429, "rate-limited"), (503, "network-failure")])
def test_retryable_http_errors_have_exact_attempts_timing_and_taxonomy(status, reason) -> None:
    attempts, sleeps = 0, []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status)

    with pytest.raises(MarketDataFetchError, match=reason):
        _reader(handler, sleeps).fetch()
    assert attempts == 3
    assert sleeps == [0.5, 1.0]


@pytest.mark.parametrize(
    ("retry_after", "delay"),
    [
        ("2", 2.0),
        ("-2", 0.0),
        ("99", 4.0),
        ("NaN", 0.5),
        ("inf", 0.5),
        ("-inf", 0.5),
        ("Tue, 15 Nov 1994 08:12:31 GMT", 0.5),
    ],
)
def test_retry_after_only_uses_finite_numeric_values(retry_after, delay) -> None:
    attempts, sleeps = 0, []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return (
            httpx.Response(429, headers={"Retry-After": retry_after})
            if attempts == 1
            else httpx.Response(200, json=_page([ROW]))
        )

    assert _reader(handler, sleeps).fetch()[0].ticker == "ACME"
    assert attempts == 2
    assert sleeps == [delay]


@pytest.mark.parametrize("status", [400, 418])
def test_other_http_errors_fail_immediately(status) -> None:
    attempts, sleeps = 0, []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status)

    with pytest.raises(MarketDataFetchError, match="network-failure"):
        _reader(handler, sleeps).fetch()
    assert attempts == 1
    assert sleeps == []


def test_request_errors_retry_and_succeed_or_exhaust_with_no_final_sleep() -> None:
    attempts, sleeps = 0, []

    def succeeds(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(200, json=_page([ROW]))

    assert _reader(succeeds, sleeps).fetch()[0].ticker == "ACME"
    assert attempts == 2
    assert sleeps == [0.5]

    attempts, sleeps = 0, []

    def exhausts(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(MarketDataFetchError, match="network-failure"):
        _reader(exhausts, sleeps).fetch()
    assert attempts == 3
    assert sleeps == [0.5, 1.0]
