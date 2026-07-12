import os
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Callable

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from invest.domain.models import DailyBar, FixtureInputs, Universe


class MarketDataFetchError(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class _BarPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    timestamp: datetime = Field(alias="t")
    open: Decimal = Field(alias="o", gt=0)
    high: Decimal = Field(alias="h", gt=0)
    low: Decimal = Field(alias="l", gt=0)
    close: Decimal = Field(alias="c", gt=0)
    volume: int = Field(alias="v", ge=0)

    @model_validator(mode="after")
    def validate_price_relationships(self) -> "_BarPayload":
        if self.low > self.high or not self.low <= self.open <= self.high or not self.low <= self.close <= self.high:
            raise ValueError("OHLC prices have an impossible relationship")
        return self


class _BarsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    bars: dict[str, list[_BarPayload]]
    next_page_token: str | None = None


class AlpacaMarketDataReader:
    ENDPOINT = "https://data.alpaca.markets/v2/stocks/bars"

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        feed: str = "sip",
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client or httpx.Client()
        self._feed = feed
        self._sleep = sleep

    def fetch(self, universe: Universe, as_of: date) -> FixtureInputs:
        bars_by_symbol: dict[str, list[DailyBar]] = {}
        page_token: str | None = None
        while True:
            params = self._request_params(universe, as_of)
            if page_token is not None:
                params["page_token"] = page_token
            response = self._send_with_retry(params)
            try:
                payload = _BarsResponse.model_validate(response.json())
            except (ValidationError, ValueError, TypeError):
                raise MarketDataFetchError("malformed-response") from None
            for symbol, symbol_bars in payload.bars.items():
                bars_by_symbol.setdefault(symbol, []).extend(
                    DailyBar(
                        symbol=symbol,
                        date=bar.timestamp.date(),
                        open=bar.open,
                        high=bar.high,
                        low=bar.low,
                        close=bar.close,
                        volume=bar.volume,
                    )
                    for bar in symbol_bars
                )
            page_token = payload.next_page_token
            if page_token is None:
                bars = tuple(
                    bar
                    for symbol in universe.symbols
                    for bar in bars_by_symbol.get(symbol, ())
                )
                return FixtureInputs(universe=universe, bars=bars)

    def _send_with_retry(self, params: dict[str, str | int]) -> httpx.Response:
        for attempt in range(3):
            try:
                response = self._client.send(self._build_request(params))
            except httpx.RequestError:
                if attempt == 2:
                    raise MarketDataFetchError("network-failure") from None
                self._sleep(self._backoff(attempt, None))
                continue

            if response.status_code in {401, 403}:
                raise MarketDataFetchError("auth-failure")
            if response.status_code == 429:
                if attempt == 2:
                    raise MarketDataFetchError("rate-limited")
                self._sleep(self._backoff(attempt, response.headers.get("Retry-After")))
                continue
            if response.status_code >= 500:
                if attempt == 2:
                    raise MarketDataFetchError("network-failure")
                self._sleep(self._backoff(attempt, response.headers.get("Retry-After")))
                continue
            if response.is_error:
                raise MarketDataFetchError("network-failure")
            return response
        raise AssertionError("retry loop must return or raise")

    @staticmethod
    def _backoff(attempt: int, retry_after: str | None) -> float:
        if retry_after is not None:
            try:
                return min(max(float(retry_after), 0.0), 4.0)
            except ValueError:
                pass
        return min(0.5 * (2**attempt), 4.0)

    def _build_request(self, params: dict[str, str | int]) -> httpx.Request:
        return self._client.build_request(
            "GET",
            self.ENDPOINT,
            params=params,
            headers={
                "APCA-API-KEY-ID": os.environ.get("ALPACA_API_KEY_ID", ""),
                "APCA-API-SECRET-KEY": os.environ.get("ALPACA_API_SECRET_KEY", ""),
            },
        )

    def _request_params(self, universe: Universe, as_of: date) -> dict[str, str | int]:
        return {
            "symbols": ",".join(universe.symbols),
            "timeframe": "1Day",
            "start": (as_of - timedelta(days=40)).isoformat(),
            "end": as_of.isoformat(),
            "feed": self._feed,
            "adjustment": "split",
            "limit": 10000,
        }
