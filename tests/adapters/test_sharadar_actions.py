import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from invest.adapters.alpaca_market_data import MarketDataFetchError


COLUMNS = ("ticker", "date", "action", "value")

MAPPED_LITERALS = (
    ("split", "SPLIT"),
    ("adrratiosplit", "SPLIT"),
    ("dividend", "DIVIDEND"),
    ("spinoffdividend", "DIVIDEND"),
    ("delisted", "DELISTING"),
    ("regulatorydelisting", "DELISTING"),
    ("voluntarydelisting", "DELISTING"),
    ("bankruptcyliquidation", "DELISTING"),
    ("tickerchangeto", "TICKER_CHANGE"),
    ("tickerchangefrom", "TICKER_CHANGE"),
)

SKIPPED_LITERALS = (
    "listed",
    "relation",
    "acquisitionby",
    "acquisitionof",
    "mergerto",
    "mergerfrom",
    "spinoff",
    "spunofffrom",
)


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


@pytest.mark.parametrize(("literal", "kind_name"), MAPPED_LITERALS)
def test_fetch_maps_each_mapped_literal_to_its_normalized_kind(
    monkeypatch: pytest.MonkeyPatch, literal: str, kind_name: str
) -> None:
    """All 10 real ACTIONS literals fold onto the closed 4-kind enum per the mapping table."""
    from invest.adapters.sharadar_actions import SharadarActionKind

    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    expected_kind = SharadarActionKind[kind_name]
    value = None if expected_kind in {SharadarActionKind.DELISTING, SharadarActionKind.TICKER_CHANGE} else "2"

    events = _reader(
        lambda _: httpx.Response(200, json=_page([["ACME", "2024-02-15", literal, value]]))
    ).fetch()

    assert len(events) == 1
    assert events[0].kind is expected_kind
    assert events[0].value == (None if value is None else Decimal(value))
    with pytest.raises(AttributeError):
        setattr(events[0], "kind", SharadarActionKind.DIVIDEND)


@pytest.mark.parametrize("literal", [*SKIPPED_LITERALS, "some-brand-new-literal-2027"])
def test_skipped_and_unknown_literals_produce_no_events_and_do_not_abort(
    monkeypatch: pytest.MonkeyPatch, literal: str
) -> None:
    """Explicit skip literals and unrecognized drift both drop silently, never raise."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    events = _reader(
        lambda _: httpx.Response(200, json=_page([["ACME", "2024-02-15", literal, None]]))
    ).fetch()

    assert events == ()


def test_mixed_page_keeps_only_mapped_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """A page mixing mapped, skipped, and unknown literals returns only the mapped rows."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    events = _reader(
        lambda _: httpx.Response(
            200,
            json=_page(
                [
                    ["ACME", "2024-02-15", "split", "2"],
                    ["ACME", "2024-02-16", "listed", None],
                    ["ACME", "2024-02-17", "totally-unknown", None],
                    ["ACME", "2024-02-18", "dividend", "0.25"],
                ]
            ),
        )
    ).fetch()

    assert [event.ticker for event in events] == ["ACME", "ACME"]
    assert [event.value for event in events] == [Decimal("2"), Decimal("0.25")]


def test_unknown_literal_on_first_page_does_not_abort_multipage_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unknown literal on page 1 must not kill the multi-page pull; page 2 still returns."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            return httpx.Response(
                200, json=_page([["ACME", "2024-02-15", "totally-unknown", None]], "next")
            )
        return httpx.Response(200, json=_page([["ZED", "2024-02-16", "split", "3"]]))

    events = _reader(handler).fetch()
    assert requests == 2
    assert len(events) == 1
    assert events[0].ticker == "ZED"
    assert events[0].value == Decimal("3")


@pytest.mark.parametrize(
    "raw_value",
    [0.1, 0.25, 123.456789012345],
)
def test_float_values_coerce_to_exact_decimals_matching_source_repr(
    monkeypatch: pytest.MonkeyPatch, raw_value: float
) -> None:
    """The real API sends every value as a JSON float; it must coerce without precision loss."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    events = _reader(
        lambda _: httpx.Response(
            200, json=_page([["ACME", "2024-02-15", "dividend", raw_value]])
        )
    ).fetch()

    assert len(events) == 1
    assert events[0].value == Decimal(str(raw_value))


def test_live_shaped_float_fixture_has_no_precision_loss(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live-shaped fixture from the spec's float scenario: dividend + split values."""
    monkeypatch.setenv("NASDAQ_DATA_LINK_API_KEY", "test-key")
    events = _reader(
        lambda _: httpx.Response(
            200,
            json=_page(
                [
                    ["ACME", "2024-02-15", "dividend", 9.00009000090001],
                    ["ACME", "2024-02-16", "split", 0.04545],
                ]
            ),
        )
    ).fetch()

    assert [event.value for event in events] == [
        Decimal("9.00009000090001"),
        Decimal("0.04545"),
    ]


@pytest.mark.parametrize(
    ("action", "value"),
    [
        ("split", "0"),
        ("split", "-2"),
        ("dividend", "0"),
        ("dividend", "-2"),
        ("dividend", "NaN"),
        ("dividend", "Infinity"),
        ("dividend", None),
        ("tickerchangeto", "1"),
    ],
)
def test_fetch_rejects_invalid_action_rows(
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
        ("split", "-2", "valued ACTIONS ratio/amount must be positive"),
        ("dividend", "-2", "valued ACTIONS ratio/amount must be positive"),
        ("dividend", None, "valued ACTIONS action has no finite value"),
        ("delisted", "3", "valueless ACTIONS action has a value"),
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


def test_action_kinds_and_skipped_actions_are_disjoint() -> None:
    """Mapped literals and the explicit skip set must never overlap (boundary)."""
    from invest.adapters.sharadar_actions import _ACTION_KINDS, _SKIPPED_ACTIONS

    assert _ACTION_KINDS.keys() & _SKIPPED_ACTIONS == set()


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
