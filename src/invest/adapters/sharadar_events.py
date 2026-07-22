"""Nasdaq Data Link SHARADAR/EVENTS adapter.

The EVENTS table is date-granular.  This adapter deliberately exposes only
the provider fields needed by the EVENTS-22 F0 audit; event interpretation and
known-time policy live in the application layer.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
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
class SharadarEvent:
    ticker: str
    event_date: date
    event_code: int
    source_row_id: str


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


class _EventsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    datatable: _Datatable
    meta: _Meta


class _EventRow(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    ticker: str = Field(min_length=1)
    date: date
    eventcode: int = Field(ge=1)


class SharadarEventsReader:
    ENDPOINT = "https://data.nasdaq.com/api/v3/datatables/SHARADAR/EVENTS.json"
    COLUMNS = ("ticker", "date", "eventcode")
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

    def fetch(self, *, event_code: int) -> tuple[SharadarEvent, ...]:
        events: list[SharadarEvent] = []
        occurrences: Counter[tuple[str, date, int]] = Counter()
        cursor: str | None = None
        for page_number in range(1, self.MAX_PAGES + 1):
            params = self._request_params(event_code)
            if cursor is not None:
                params["qopts.cursor_id"] = cursor
            try:
                payload = _EventsResponse.model_validate(self._send(params).json())
                events.extend(
                    self._rows_to_events(payload, expected_code=event_code, occurrences=occurrences)
                )
            except ValidationError:
                raise MarketDataFetchError("malformed-response") from None
            except (TypeError, ValueError) as error:
                raise MarketDataFetchError("malformed-response", str(error)) from None
            cursor = payload.meta.next_cursor_id
            if cursor is not None and not cursor.strip():
                raise MarketDataFetchError("malformed-response", "blank pagination cursor")
            if cursor is None:
                return tuple(sorted(events, key=lambda event: (event.event_date, event.ticker)))
            if page_number == self.MAX_PAGES:
                raise MarketDataFetchError(
                    "malformed-response", f"page cap of {self.MAX_PAGES} exhausted"
                )
        raise AssertionError("pagination loop must return or raise")

    def _rows_to_events(
        self,
        payload: _EventsResponse,
        *,
        expected_code: int,
        occurrences: Counter[tuple[str, date, int]],
    ) -> list[SharadarEvent]:
        if not payload.datatable.columns or not payload.datatable.data:
            raise ValueError("empty EVENTS response")
        columns = {column.name: index for index, column in enumerate(payload.datatable.columns)}
        if set(self.COLUMNS) - columns.keys():
            raise ValueError("required EVENTS columns missing")
        events: list[SharadarEvent] = []
        for values in payload.datatable.data:
            if len(values) < len(payload.datatable.columns):
                raise ValueError("EVENTS row is shorter than its columns")
            row = _EventRow.model_validate(
                {
                    column: values[index]
                    for column, index in columns.items()
                    if column in self.COLUMNS
                }
            )
            if row.eventcode != expected_code:
                raise ValueError(
                    f"EVENTS response included code {row.eventcode}; expected {expected_code}"
                )
            key = (row.ticker, row.date, row.eventcode)
            occurrences[key] += 1
            source_row_id = (
                "sharadar-events:"
                + sha256(
                    f"{row.ticker}|{row.date.isoformat()}|{row.eventcode}|{occurrences[key]}".encode()
                ).hexdigest()
            )
            events.append(SharadarEvent(row.ticker, row.date, row.eventcode, source_row_id))
        return events

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

    def _request_params(self, event_code: int) -> dict[str, str]:
        if event_code < 1:
            raise ValueError("event_code must be positive")
        return {
            "eventcode": str(event_code),
            "qopts.columns": ",".join(self.COLUMNS),
        }
