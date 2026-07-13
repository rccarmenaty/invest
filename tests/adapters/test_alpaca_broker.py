import json
import traceback
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from invest.domain.models import AccountSnapshot, BrokerAck, OrderIntent


def test_broker_uses_only_hardcoded_paper_url(monkeypatch) -> None:
    from invest.adapters.alpaca_broker import AlpacaBroker

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"id": "order-1"})

    monkeypatch.setenv("ALPACA_API_KEY_ID", "key")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret")
    broker = AlpacaBroker(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert broker.find_order("intent-1") == "order-1"
    assert seen == [
        "https://paper-api.alpaca.markets/v2/orders:by_client_order_id?client_order_id=intent-1"
    ]

    sources = "".join(path.read_text() for path in Path("src").rglob("*.py"))
    assert '"https://api.alpaca.markets' not in sources
    assert "'https://api.alpaca.markets" not in sources


def test_snapshot_maps_account_and_positions() -> None:
    from invest.adapters.alpaca_broker import AlpacaBroker

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/account":
            return httpx.Response(
                200,
                json={
                    "equity": "100000.25",
                    "last_equity": "99000.00",
                    "buying_power": "50000.50",
                    "trading_blocked": False,
                    "account_blocked": True,
                },
            )
        assert request.url.path == "/v2/positions"
        return httpx.Response(200, json=[{"market_value": "1200.10"}, {"market_value": "-50.05"}])

    broker = AlpacaBroker(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert broker.snapshot() == AccountSnapshot(
        equity=Decimal("100000.25"),
        last_equity=Decimal("99000.00"),
        buying_power=Decimal("50000.50"),
        open_position_count=2,
        deployed_value=Decimal("1150.05"),
        trading_blocked=False,
        account_blocked=True,
    )


def test_find_order_returns_none_for_404() -> None:
    from invest.adapters.alpaca_broker import AlpacaBroker

    broker = AlpacaBroker(
        client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404)))
    )
    assert broker.find_order("missing") is None


def test_submit_bracket_uses_verified_stop_market_shape() -> None:
    from invest.adapters.alpaca_broker import AlpacaBroker

    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(404)
        payloads.append(json.loads(request.content))
        return httpx.Response(201, json={"id": "broker-1"})

    broker = AlpacaBroker(client=httpx.Client(transport=httpx.MockTransport(handler)))
    intent = OrderIntent(
        "AAPL", date(2025, 1, 2), 12, Decimal("100.00"), Decimal("98.50"), Decimal("103.00")
    )
    assert broker.submit_bracket(intent, client_order_id="intent-1") == BrokerAck(
        broker_order_id="broker-1", status="submitted"
    )
    assert payloads == [
        {
            "symbol": "AAPL",
            "qty": "12",
            "side": "buy",
            "type": "market",
            "time_in_force": "day",
            "order_class": "bracket",
            "take_profit": {"limit_price": "103.00"},
            "stop_loss": {"stop_price": "98.50"},
            "client_order_id": "intent-1",
        }
    ]


def test_submit_bracket_reports_existing_order_without_post() -> None:
    from invest.adapters.alpaca_broker import AlpacaBroker

    methods: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(200, json={"id": "broker-existing"})

    broker = AlpacaBroker(client=httpx.Client(transport=httpx.MockTransport(handler)))
    intent = OrderIntent("AAPL", date(2025, 1, 2), 1, Decimal("10"), Decimal("9"), Decimal("12"))
    assert broker.submit_bracket(intent, client_order_id="intent-1") == BrokerAck(
        broker_order_id="broker-existing", status="already-submitted"
    )
    assert methods == ["GET"]


def test_submit_bracket_never_retries_timeout() -> None:
    from invest.adapters.alpaca_broker import AlpacaBroker, BrokerFetchError

    post_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal post_count
        if request.method == "GET":
            return httpx.Response(404)
        post_count += 1
        raise httpx.ConnectTimeout("uncertain", request=request)

    broker = AlpacaBroker(client=httpx.Client(transport=httpx.MockTransport(handler)))
    intent = OrderIntent("AAPL", date(2025, 1, 2), 1, Decimal("10"), Decimal("9"), Decimal("12"))
    with pytest.raises(BrokerFetchError) as caught:
        broker.submit_bracket(intent, client_order_id="intent-1")
    assert caught.value.reason == "submission-uncertain"
    assert post_count == 1


def test_submit_bracket_returns_422_rejection_payload() -> None:
    from invest.adapters.alpaca_broker import AlpacaBroker

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(404)
        return httpx.Response(422, json={"code": 42210000, "message": "invalid order"})

    broker = AlpacaBroker(client=httpx.Client(transport=httpx.MockTransport(handler)))
    intent = OrderIntent("AAPL", date(2025, 1, 2), 1, Decimal("10"), Decimal("9"), Decimal("12"))
    assert broker.submit_bracket(intent, client_order_id="intent-1") == BrokerAck(
        broker_order_id=None, status="rejected", reason="invalid order"
    )


@pytest.mark.parametrize(
    ("status", "reason", "attempts"),
    [
        (401, "auth-failure", 1),
        (403, "auth-failure", 1),
        (429, "rate-limited", 3),
        (503, "network-failure", 3),
    ],
)
def test_get_error_taxonomy_and_bounded_retry(status: int, reason: str, attempts: int) -> None:
    from invest.adapters.alpaca_broker import AlpacaBroker, BrokerFetchError

    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(status, headers={"Retry-After": "1.75"})

    broker = AlpacaBroker(
        client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=sleeps.append
    )
    with pytest.raises(BrokerFetchError) as caught:
        broker.find_order("intent-1")
    assert caught.value.reason == reason
    assert calls == attempts
    assert sleeps == ([1.75, 1.75] if attempts == 3 else [])


def test_get_retries_connection_failure_with_exponential_backoff() -> None:
    from invest.adapters.alpaca_broker import AlpacaBroker, BrokerFetchError

    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("down", request=request)

    broker = AlpacaBroker(
        client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=sleeps.append
    )
    with pytest.raises(BrokerFetchError) as caught:
        broker.find_order("intent-1")
    assert caught.value.reason == "network-failure"
    assert calls == 3
    assert sleeps == [0.5, 1.0]


@pytest.mark.parametrize("payload", [b"not-json", b"[]", b'{"unexpected":true}'])
def test_get_bad_json_or_schema_is_malformed_response(payload: bytes) -> None:
    from invest.adapters.alpaca_broker import AlpacaBroker, BrokerFetchError

    broker = AlpacaBroker(
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, content=payload))
        )
    )
    with pytest.raises(BrokerFetchError) as caught:
        broker.find_order("intent-1")
    assert caught.value.reason == "malformed-response"


def test_credentials_are_redacted_from_formatted_traceback(monkeypatch) -> None:
    from invest.adapters.alpaca_broker import AlpacaBroker, BrokerFetchError

    key = "key-must-not-leak"
    secret = "secret-must-not-leak"
    monkeypatch.setenv("ALPACA_API_KEY_ID", key)
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", secret)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["APCA-API-KEY-ID"] == key
        assert request.headers["APCA-API-SECRET-KEY"] == secret
        raise httpx.ConnectError(f"failed with {key}/{secret}", request=request)

    broker = AlpacaBroker(
        client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda _: None
    )
    try:
        broker.find_order("intent-1")
    except BrokerFetchError as error:
        output = "".join(traceback.format_exception(error))
    else:
        pytest.fail("expected BrokerFetchError")
    assert key not in output
    assert secret not in output
    assert output.rstrip().endswith("BrokerFetchError: network-failure")


def test_broker_source_has_no_market_context_dependency() -> None:
    source = Path("src/invest/adapters/alpaca_broker.py").read_text(encoding="utf-8")

    assert "market_context" not in source
