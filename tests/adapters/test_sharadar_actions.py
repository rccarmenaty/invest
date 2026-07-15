import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from invest.adapters.alpaca_market_data import MarketDataFetchError


COLUMNS = ("ticker", "date", "action", "value")


def _page(rows: list[list[object]], cursor: object = None) -> dict[str, object]:
    return {
        "datatable": {"columns": [{"name": name} for name in COLUMNS], "data": rows},
        "meta": {"next_cursor_id": cursor},
    }


def _reader(handler, sleeps: list[float] | None = None):
    from invest.adapters.sharadar_actions import SharadarActionsReader

    return SharadarActionsReader(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=sleeps.append if sleeps is not None else lambda _: None,
    )


def test_request_error_exhaustion_attempts_three_times_and_never_sleeps_after_final_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public reader contract bounds transport failure and its backoff."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    attempts, sleeps = 0, []

    def offline(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(MarketDataFetchError, match="network-failure"):
        _reader(offline, sleeps).fetch()
    assert attempts == 3
    assert sleeps == [0.5, 1.0]


@pytest.mark.parametrize(("action", "value"), [("split", "2"), ("dividend", "0.25")])
def test_fetch_returns_typed_events(
    monkeypatch: pytest.MonkeyPatch, action: str, value: str
) -> None:
    from invest.adapters.sharadar_actions import SharadarActionKind

    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    events = _reader(
        lambda _: httpx.Response(200, json=_page([["ACME", "2024-02-15", action, value]]))
    ).fetch()

    assert isinstance(events, tuple)
    assert len(events) == 1
    event = events[0]
    assert event.ticker == "ACME"
    assert event.effective_date == date(2024, 2, 15)
    assert event.kind is SharadarActionKind(action)
    assert event.value == Decimal(value)


def test_fetch_maps_all_provider_literals_to_closed_frozen_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from invest.adapters.sharadar_actions import SharadarActionKind

    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    events = _reader(
        lambda _: httpx.Response(
            200,
            json=_page(
                [
                    ["ACME", "2024-02-15", "split", "2"],
                    ["ACME", "2024-02-16", "dividend", "0.25"],
                    ["ACME", "2024-02-17", "delisting", None],
                    ["ACME", "2024-02-18", "tickerchange", None],
                ]
            ),
        )
    ).fetch()

    assert [event.kind.value for event in events] == [
        "split",
        "dividend",
        "delisting",
        "ticker-change",
    ]
    assert [event.value for event in events] == [Decimal("2"), Decimal("0.25"), None, None]
    with pytest.raises(AttributeError):
        setattr(events[0], "kind", SharadarActionKind.DIVIDEND)


@pytest.mark.parametrize(
    ("action", "value"),
    [
        ("split", "0"),
        ("split", "-2"),
        ("dividend", "NaN"),
        ("dividend", "Infinity"),
        ("dividend", 0.1),
        ("dividend", None),
        ("tickerchange", "1"),
        ("unsupported", "1"),
        ("SPLIT", "2"),
    ],
)
def test_fetch_rejects_invalid_or_unsupported_action_rows(
    monkeypatch: pytest.MonkeyPatch, action: str, value: object
) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    with pytest.raises(MarketDataFetchError, match="malformed-response"):
        _reader(
            lambda _: httpx.Response(200, json=_page([["ACME", "2024-02-15", action, value]]))
        ).fetch()


@pytest.mark.parametrize(
    ("action", "value", "detail"),
    [
        ("split", "-2", "split ratio must be positive"),
        ("dividend", None, "valued ACTIONS action has no finite value"),
        ("delisting", "3", "valueless ACTIONS action has a value"),
        ("merger", "1", "unsupported ACTIONS action"),
    ],
)
def test_rejected_rows_report_why_they_were_rejected(
    monkeypatch: pytest.MonkeyPatch, action: str, value: object, detail: str
) -> None:
    """Every validation rule has a distinct cause; triage must not see one opaque reason."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")

    with pytest.raises(MarketDataFetchError) as caught:
        _reader(
            lambda _: httpx.Response(200, json=_page([["ACME", "2024-02-15", action, value]]))
        ).fetch()

    assert caught.value.reason == "malformed-response"
    assert detail in str(caught.value)


def test_page_cap_exhaustion_is_distinguishable_from_corrupt_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dataset exceeding the cap and a corrupt payload need different remediation."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    reader = _reader(
        lambda _: httpx.Response(200, json=_page([["ACME", "2024-02-15", "split", "2"]], "more"))
    )
    reader.MAX_PAGES = 2  # type: ignore[assignment]

    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch()

    assert caught.value.reason == "malformed-response"
    assert "page cap" in str(caught.value)


def test_fetch_combines_valid_pages_in_stable_event_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            assert request.url.params["qopts.columns"] == ",".join(COLUMNS)
            return httpx.Response(
                200, json=_page([["ZED", "2024-02-15", "dividend", "1.0"]], "next")
            )
        assert request.url.params["qopts.cursor_id"] == "next"
        return httpx.Response(
            200,
            json=_page(
                [["ACME", "2024-02-15", "split", "2"], ["ZED", "2024-02-15", "dividend", "1"]]
            ),
        )

    events = _reader(handler).fetch()
    assert len(events) == 3
    assert [event.ticker for event in events] == ["ACME", "ZED", "ZED"]
    assert [event.effective_date for event in events] == [date(2024, 2, 15)] * 3
    assert [event.kind.value for event in events] == ["split", "dividend", "dividend"]
    assert [event.value for event in events] == [Decimal("2"), Decimal("1"), Decimal("1.0")]
    assert requests == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"datatable": {"columns": [], "data": []}, "meta": {}},
        _page([]),
        {"datatable": {"columns": [{"name": "ticker"}], "data": [["ACME"]]}, "meta": {}},
        _page([["ACME", "2024-02-15"]]),
        _page([["", "not-a-date", "split", "2"]]),
    ],
)
def test_fetch_rejects_malformed_pages_without_returning_events(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]
) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    with pytest.raises(MarketDataFetchError, match="malformed-response"):
        _reader(lambda _: httpx.Response(200, json=payload)).fetch()


@pytest.mark.parametrize("cursor", ["", " ", 3])
def test_fetch_rejects_invalid_continuation_cursor_before_another_request(
    monkeypatch: pytest.MonkeyPatch, cursor: object
) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    requests = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json=_page([["ACME", "2024-02-15", "split", "2"]], cursor))

    with pytest.raises(MarketDataFetchError, match="malformed-response"):
        _reader(handler).fetch()
    assert requests == 1


def test_fetch_fails_closed_for_whitespace_only_ticker_without_partial_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    responses = iter(
        [
            _page([["ACME", "2024-02-15", "split", "2"]], "next"),
            _page([["   ", "2024-02-16", "dividend", "0.25"]]),
        ]
    )
    events = None
    with pytest.raises(MarketDataFetchError, match="malformed-response"):
        events = _reader(lambda _: httpx.Response(200, json=next(responses))).fetch()
    assert events is None


def test_fetch_fails_closed_for_malformed_second_page_and_page_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from invest.adapters.sharadar_actions import SharadarActionsReader

    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    responses = iter([_page([["ACME", "2024-02-15", "split", "2"]], "next"), _page([])])
    with pytest.raises(MarketDataFetchError, match="malformed-response"):
        _reader(lambda _: httpx.Response(200, json=next(responses))).fetch()

    monkeypatch.setattr(SharadarActionsReader, "MAX_PAGES", 1)
    with pytest.raises(MarketDataFetchError, match="malformed-response"):
        _reader(
            lambda _: httpx.Response(
                200, json=_page([["ACME", "2024-02-15", "split", "2"]], "next")
            )
        ).fetch()


@pytest.mark.parametrize("key", [None, ""])
def test_fetch_rejects_missing_key_before_transport(
    monkeypatch: pytest.MonkeyPatch, key: str | None
) -> None:
    if key is None:
        monkeypatch.delenv("NASDAQ_DATA_LINK_API_KEY", raising=False)
    else:
        monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", key)
    with pytest.raises(MarketDataFetchError, match="auth-failure"):
        _reader(lambda _: pytest.fail("transport must not be called")).fetch()


@pytest.mark.parametrize("status", [401, 403])
def test_auth_responses_are_not_retried(monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    attempts = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status)

    with pytest.raises(MarketDataFetchError, match="auth-failure"):
        _reader(handler).fetch()
    assert attempts == 1


@pytest.mark.parametrize(
    ("status", "headers", "reason", "expected"),
    [
        (429, {"Retry-After": "2"}, "rate-limited", [2.0, 2.0]),
        (503, {}, "network-failure", [0.5, 1.0]),
    ],
)
def test_retryable_responses_have_bounded_taxonomy_and_no_final_sleep(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    headers: dict[str, str],
    reason: str,
    expected: list[float],
) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    attempts, sleeps = 0, []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status, headers=headers)

    with pytest.raises(MarketDataFetchError, match=reason):
        _reader(handler, sleeps).fetch()
    assert attempts == 3
    assert sleeps == expected


@pytest.mark.parametrize(
    "retry_after", ["-2", "9", "not-a-delay", "Wed, 21 Oct 2015 07:28:00 GMT", "NaN", "Infinity"]
)
def test_retry_after_clamps_or_falls_back_before_retry_success(
    monkeypatch: pytest.MonkeyPatch, retry_after: str
) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    attempts, sleeps = 0, []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return (
            httpx.Response(429, headers={"Retry-After": retry_after})
            if attempts == 1
            else httpx.Response(200, json=_page([["ACME", "2024-02-15", "split", "2"]]))
        )

    assert _reader(handler, sleeps).fetch()[0].value == Decimal("2")
    assert sleeps == [{"-2": 0.0, "9": 4.0}.get(retry_after, 0.5)]


def test_non_retryable_http_error_is_network_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    with pytest.raises(MarketDataFetchError, match="network-failure"):
        _reader(lambda _: httpx.Response(418)).fetch()


def test_actions_source_has_no_sep_or_daily_bar_import() -> None:
    """ACTIONS cannot mutate bars it neither accepts nor imports."""
    tree = ast.parse(Path("src/invest/adapters/sharadar_actions.py").read_text(encoding="utf-8"))
    imports = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
        if node.module in {"invest.domain.models", "invest.adapters.sharadar_market_data"}
    ]
    assert imports == []
