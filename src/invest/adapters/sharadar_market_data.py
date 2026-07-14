import os
import time
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Callable

import exchange_calendars as xcals
import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from invest.adapters.alpaca_market_data import MarketDataFetchError
from invest.domain.models import DailyBar, FixtureInputs, Universe


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


class _SepResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    datatable: _Datatable
    meta: _Meta


class _SepRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str = Field(min_length=1)
    date: date
    open: Decimal = Field(gt=0)
    high: Decimal = Field(gt=0)
    low: Decimal = Field(gt=0)
    close: Decimal = Field(gt=0)
    volume: int = Field(ge=0)
    closeadj: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def validate_price_relationships(self) -> "_SepRow":
        if (
            self.low > self.high
            or not self.low <= self.open <= self.high
            or not self.low <= self.close <= self.high
        ):
            raise ValueError("OHLC prices have an impossible relationship")
        return self


class SharadarMarketDataReader:
    ENDPOINT = "https://data.nasdaq.com/api/v3/datatables/SHARADAR/SEP.json"
    COLUMNS = ("ticker", "date", "open", "high", "low", "close", "volume", "closeadj")
    XNYS_CALENDAR = xcals.get_calendar("XNYS")
    CALENDAR_BUFFER_DAYS = 40
    MAX_PAGES = 512
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

    def fetch(self, universe: Universe, as_of: date) -> FixtureInputs:
        return self.fetch_range(universe, as_of - timedelta(days=self.CALENDAR_BUFFER_DAYS), as_of)

    def fetch_range(self, universe: Universe, start: date, end: date) -> FixtureInputs:
        bars: list[DailyBar] = []
        cursor: str | None = None
        for page_number in range(1, self.MAX_PAGES + 1):
            params = self._request_params(universe, start, end)
            if cursor is not None:
                params["qopts.cursor_id"] = cursor
            try:
                payload = _SepResponse.model_validate(self._send(params).json())
                bars.extend(self._rows_to_bars(payload))
            except (ValidationError, ValueError, TypeError):
                raise MarketDataFetchError("malformed-response") from None
            cursor = payload.meta.next_cursor_id
            if cursor is None:
                missing = sorted(set(universe.symbols) - {bar.symbol for bar in bars})
                if missing:
                    raise MarketDataFetchError("symbol-missing-at-fetch", ",".join(missing))
                dates_by_symbol = {
                    symbol: {bar.date for bar in bars if bar.symbol == symbol}
                    for symbol in universe.symbols
                }
                reported_dates = set().union(*dates_by_symbol.values())
                incomplete = sorted(
                    symbol for symbol, dates in dates_by_symbol.items() if dates != reported_dates
                )
                expected_dates = {
                    session.date() for session in self.XNYS_CALENDAR.sessions_in_range(start, end)
                }
                if incomplete or reported_dates != expected_dates:
                    raise MarketDataFetchError("malformed-response", "incomplete date coverage")
                return FixtureInputs(
                    universe=universe,
                    bars=tuple(sorted(bars, key=lambda bar: (bar.symbol, bar.date))),
                )
            if page_number == self.MAX_PAGES:
                raise MarketDataFetchError("malformed-response")
        raise AssertionError("pagination loop must return or raise")

    def _rows_to_bars(self, payload: _SepResponse) -> list[DailyBar]:
        if not payload.datatable.columns or not payload.datatable.data:
            raise ValueError("empty SEP response")
        columns = {column.name: index for index, column in enumerate(payload.datatable.columns)}
        if set(self.COLUMNS) - columns.keys():
            raise ValueError("required SEP columns missing")
        bars: list[DailyBar] = []
        for values in payload.datatable.data:
            if len(values) < len(payload.datatable.columns):
                raise ValueError("SEP row is shorter than its columns")
            row = _SepRow.model_validate(
                {
                    column: values[index]
                    for column, index in columns.items()
                    if column in self.COLUMNS
                }
            )
            bars.append(
                DailyBar(
                    symbol=row.ticker,
                    date=row.date,
                    open=_adjust(row.open, row.close, row.closeadj),
                    high=_adjust(row.high, row.close, row.closeadj),
                    low=_adjust(row.low, row.close, row.closeadj),
                    close=row.closeadj,
                    volume=row.volume,
                )
            )
        return bars

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

    @classmethod
    def _backoff(cls, attempt: int, retry_after: str | None) -> float:
        if retry_after is not None:
            try:
                return min(max(float(retry_after), 0.0), cls.BACKOFF_CAP_SECONDS)
            except ValueError:
                pass
        return min(cls.BACKOFF_BASE_SECONDS * (2**attempt), cls.BACKOFF_CAP_SECONDS)

    def _build_request(self, params: dict[str, str]) -> httpx.Request:
        api_key = os.environ.get("NASDAQ_DATA_LINK_API_KEY")
        if not api_key:
            raise MarketDataFetchError("auth-failure")
        return self._client.build_request(
            "GET", self.ENDPOINT, params={**params, "api_key": api_key}
        )

    def _request_params(self, universe: Universe, start: date, end: date) -> dict[str, str]:
        return {
            "ticker": ",".join(universe.symbols),
            "date.gte": start.isoformat(),
            "date.lte": end.isoformat(),
            "qopts.columns": ",".join(self.COLUMNS),
        }


def _adjust(raw: Decimal, close: Decimal, closeadj: Decimal) -> Decimal:
    return raw * (closeadj / close)
