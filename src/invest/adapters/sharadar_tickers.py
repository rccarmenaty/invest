import math
import os
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from invest.adapters.alpaca_market_data import MarketDataFetchError


@dataclass(frozen=True)
class SharadarTicker:
    ticker: str
    is_primary_common_stock: bool
    is_listed: bool
    listed_date: date | None
    delisted_date: date | None


class _Column(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str


class _Datatable(BaseModel):
    model_config = ConfigDict(extra="ignore")
    columns: list[_Column]
    data: list[list[Any]]


class _Meta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    next_cursor_id: str | None = None


class _TickersResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    datatable: _Datatable
    meta: _Meta


class _TickerRow(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    ticker: str = Field(min_length=1)
    exchange: str = Field(min_length=1)
    category: str = Field(min_length=1)
    firstpricedate: date | None = None
    lastpricedate: date | None = None
    isdelisted: bool


class SharadarTickersReader:
    ENDPOINT = "https://data.nasdaq.com/api/v3/datatables/SHARADAR/TICKERS.json"
    COLUMNS = ("ticker", "exchange", "category", "firstpricedate", "lastpricedate", "isdelisted")
    MAX_PAGES = 512
    MAX_ATTEMPTS = 3
    BACKOFF_BASE_SECONDS = 0.5
    BACKOFF_CAP_SECONDS = 4.0
    _PRIMARY_COMMON_STOCK_CATEGORIES = frozenset(
        {"Domestic Common Stock", "Domestic Common Stock Primary Class"}
    )
    _US_LISTING_EXCHANGES = frozenset({"AMEX", "ARCA", "NASDAQ", "NYSE"})

    def __init__(
        self,
        *,
        client: httpx.Client,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._sleep = sleep

    def fetch(self) -> tuple[SharadarTicker, ...]:
        tickers: list[SharadarTicker] = []
        cursor: str | None = None
        for page_number in range(1, self.MAX_PAGES + 1):
            params = self._request_params()
            if cursor is not None:
                params["qopts.cursor_id"] = cursor
            try:
                payload = _TickersResponse.model_validate(self._send(params).json())
                tickers.extend(self._rows_to_tickers(payload))
            except ValidationError:
                # Pydantic's rendering is a multi-line schema dump; keep it out of the reason.
                raise MarketDataFetchError("malformed-response") from None
            except (ValueError, TypeError) as error:
                raise MarketDataFetchError("malformed-response", str(error)) from None
            cursor = payload.meta.next_cursor_id
            if cursor is not None and not cursor.strip():
                raise MarketDataFetchError("malformed-response", "blank pagination cursor")
            if cursor is None:
                return tuple(sorted(tickers, key=lambda ticker: ticker.ticker))
            if page_number == self.MAX_PAGES:
                raise MarketDataFetchError(
                    "malformed-response", f"page cap of {self.MAX_PAGES} exhausted"
                )
        raise AssertionError("pagination loop must return or raise")

    def _rows_to_tickers(self, payload: _TickersResponse) -> list[SharadarTicker]:
        if not payload.datatable.columns or not payload.datatable.data:
            raise ValueError("empty TICKERS response")
        columns = {column.name: index for index, column in enumerate(payload.datatable.columns)}
        if set(self.COLUMNS) - columns.keys():
            raise ValueError("required TICKERS columns missing")
        tickers: list[SharadarTicker] = []
        for values in payload.datatable.data:
            if len(values) < len(payload.datatable.columns):
                raise ValueError("TICKERS row is shorter than its columns")
            row = _TickerRow.model_validate(
                {
                    column: values[index]
                    for column, index in columns.items()
                    if column in self.COLUMNS
                }
            )
            is_listed = not row.isdelisted
            tickers.append(
                SharadarTicker(
                    ticker=row.ticker,
                    is_primary_common_stock=(
                        row.category in self._PRIMARY_COMMON_STOCK_CATEGORIES
                        and row.exchange in self._US_LISTING_EXCHANGES
                    ),
                    is_listed=is_listed,
                    listed_date=row.firstpricedate,
                    delisted_date=row.lastpricedate if not is_listed else None,
                )
            )
        return tickers

    def _send(self, params: dict[str, str]) -> httpx.Response:
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                response = self._client.send(self._build_request(params))
            except httpx.RequestError:
                if attempt == self.MAX_ATTEMPTS - 1:
                    raise MarketDataFetchError("network-failure") from None
                self._sleep(self._backoff(attempt, None))
                continue
            if response.status_code in {401, 403}:
                raise MarketDataFetchError("auth-failure")
            if response.status_code in {429, *range(500, 600)}:
                reason = "rate-limited" if response.status_code == 429 else "network-failure"
                if attempt == self.MAX_ATTEMPTS - 1:
                    raise MarketDataFetchError(reason)
                self._sleep(self._backoff(attempt, response.headers.get("Retry-After")))
                continue
            if response.is_error:
                raise MarketDataFetchError("network-failure")
            return response
        raise AssertionError("retry loop must return or raise")

    def _backoff(self, attempt: int, retry_after: str | None) -> float:
        """Return a bounded finite Retry-After delay or deterministic exponential fallback.

        HTTP-date values are intentionally not converted: doing so requires a wall-clock read.
        Infinite and NaN values fall back rather than clamping to the cap, so a nonsense header
        cannot buy a longer wait than the retry schedule already allows.
        """
        if retry_after is not None:
            try:
                delay = float(retry_after)
            except ValueError:
                delay = None
            if delay is not None and math.isfinite(delay):
                return min(max(delay, 0.0), self.BACKOFF_CAP_SECONDS)
        return min(self.BACKOFF_BASE_SECONDS * (2**attempt), self.BACKOFF_CAP_SECONDS)

    def _build_request(self, params: dict[str, str]) -> httpx.Request:
        api_key = os.environ.get("NASDAQ_DATA_LINK_API_KEY")
        if not api_key:
            raise MarketDataFetchError("auth-failure")
        return self._client.build_request(
            "GET", self.ENDPOINT, params={**params, "api_key": api_key}
        )

    def _request_params(self) -> dict[str, str]:
        return {"qopts.columns": ",".join(self.COLUMNS)}
