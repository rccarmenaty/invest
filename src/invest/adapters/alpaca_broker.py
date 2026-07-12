import os
import time
from decimal import Decimal
from typing import Callable

import httpx
from pydantic import BaseModel, ConfigDict

from invest.domain.models import AccountSnapshot, BrokerAck, OrderIntent


class BrokerFetchError(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class _OrderResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str


class _AccountResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    equity: Decimal
    last_equity: Decimal
    buying_power: Decimal
    trading_blocked: bool
    account_blocked: bool


class _PositionResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    market_value: Decimal


class AlpacaBroker:
    BASE_URL = "https://paper-api.alpaca.markets"
    MAX_ATTEMPTS = 3
    BACKOFF_BASE_SECONDS = 0.5
    BACKOFF_CAP_SECONDS = 4.0

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client or httpx.Client()
        self._sleep = sleep

    def find_order(self, client_order_id: str) -> str | None:
        response = self._get(
            "/v2/orders:by_client_order_id",
            params={"client_order_id": client_order_id},
            not_found=True,
        )
        if response is None:
            return None
        try:
            return _OrderResponse.model_validate(response.json()).id
        except (ValueError, TypeError):
            raise BrokerFetchError("malformed-response") from None

    def snapshot(self) -> AccountSnapshot:
        account_response = self._get("/v2/account")
        positions_response = self._get("/v2/positions")
        assert account_response is not None and positions_response is not None
        try:
            account = _AccountResponse.model_validate(account_response.json())
            positions = [
                _PositionResponse.model_validate(position) for position in positions_response.json()
            ]
            return AccountSnapshot(
                equity=account.equity,
                last_equity=account.last_equity,
                buying_power=account.buying_power,
                open_position_count=len(positions),
                deployed_value=sum(
                    (position.market_value for position in positions),
                    start=Decimal("0"),
                ),
                trading_blocked=account.trading_blocked,
                account_blocked=account.account_blocked,
            )
        except (ValueError, TypeError):
            raise BrokerFetchError("malformed-response") from None

    def submit_bracket(self, intent: OrderIntent, client_order_id: str) -> BrokerAck:
        existing = self.find_order(client_order_id)
        if existing is not None:
            return BrokerAck(broker_order_id=existing, status="already-submitted")
        payload = {
            "symbol": intent.symbol,
            "qty": str(intent.qty),
            "side": "buy",
            "type": "market",
            "time_in_force": "day",
            "order_class": "bracket",
            "take_profit": {"limit_price": str(intent.take_profit)},
            "stop_loss": {"stop_price": str(intent.stop)},
            "client_order_id": client_order_id,
        }
        try:
            response = self._client.send(self._request("POST", "/v2/orders", json=payload))
        except httpx.RequestError:
            raise BrokerFetchError("submission-uncertain") from None
        if response.status_code == 422:
            try:
                rejection = response.json()
            except (ValueError, TypeError):
                raise BrokerFetchError("malformed-response") from None
            if not isinstance(rejection, dict):
                raise BrokerFetchError("malformed-response") from None
            return BrokerAck(
                broker_order_id=None,
                status="rejected",
                reason=str(rejection.get("message", "rejected")),
            )
        self._raise_for_status(response)
        try:
            order_id = _OrderResponse.model_validate(response.json()).id
        except (ValueError, TypeError):
            raise BrokerFetchError("malformed-response") from None
        return BrokerAck(broker_order_id=order_id, status="submitted")

    def _get(
        self,
        path: str,
        *,
        params: dict[str, str] | None = None,
        not_found: bool = False,
    ) -> httpx.Response | None:
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                response = self._client.send(self._request("GET", path, params=params))
            except httpx.RequestError:
                if attempt == self.MAX_ATTEMPTS - 1:
                    raise BrokerFetchError("network-failure") from None
                self._sleep(self._backoff(attempt, None))
                continue
            if not_found and response.status_code == 404:
                return None
            if response.status_code in {401, 403}:
                raise BrokerFetchError("auth-failure")
            if response.status_code in {429} or response.status_code >= 500:
                if attempt == self.MAX_ATTEMPTS - 1:
                    reason = "rate-limited" if response.status_code == 429 else "network-failure"
                    raise BrokerFetchError(reason)
                self._sleep(self._backoff(attempt, response.headers.get("Retry-After")))
                continue
            if response.is_error:
                raise BrokerFetchError("network-failure")
            return response
        raise AssertionError("retry loop must return or raise")

    @classmethod
    def _backoff(cls, attempt: int, retry_after: str | None) -> float:
        if retry_after is not None:
            try:
                return min(max(float(retry_after), 0.0), cls.BACKOFF_CAP_SECONDS)
            except ValueError:
                pass
        return min(cls.BACKOFF_BASE_SECONDS * (2**attempt), cls.BACKOFF_CAP_SECONDS)

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code in {401, 403}:
            raise BrokerFetchError("auth-failure")
        if response.status_code == 429:
            raise BrokerFetchError("rate-limited")
        if response.is_error:
            raise BrokerFetchError("network-failure")

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: object | None = None,
    ) -> httpx.Request:
        return self._client.build_request(
            method,
            f"{self.BASE_URL}{path}",
            params=params,
            json=json,
            headers={
                "APCA-API-KEY-ID": os.environ.get("ALPACA_API_KEY_ID", ""),
                "APCA-API-SECRET-KEY": os.environ.get("ALPACA_API_SECRET_KEY", ""),
            },
        )
