import math
import os
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Callable

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from invest.adapters.alpaca_market_data import MarketDataFetchError


class SharadarActionKind(StrEnum):
    SPLIT = "split"
    DIVIDEND = "dividend"
    DELISTING = "delisting"
    TICKER_CHANGE = "ticker-change"


@dataclass(frozen=True)
class SharadarAction:
    ticker: str
    effective_date: date
    kind: SharadarActionKind
    value: Decimal | None


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


class _ActionsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    datatable: _Datatable
    meta: _Meta


class _ActionRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str = Field(min_length=1)
    date: date
    action: str = Field(min_length=1)
    value: Decimal | None = None


class SharadarActionsReader:
    ENDPOINT = "https://data.nasdaq.com/api/v3/datatables/SHARADAR/ACTIONS.json"
    COLUMNS = ("ticker", "date", "action", "value")
    MAX_PAGES = 512
    MAX_ATTEMPTS = 3
    BACKOFF_BASE_SECONDS = 0.5
    BACKOFF_CAP_SECONDS = 4.0
    _ACTION_KINDS = {
        "split": SharadarActionKind.SPLIT,
        "dividend": SharadarActionKind.DIVIDEND,
        "delisting": SharadarActionKind.DELISTING,
        "tickerchange": SharadarActionKind.TICKER_CHANGE,
    }

    def __init__(
        self,
        *,
        client: httpx.Client,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._sleep = sleep

    def fetch(self) -> tuple[SharadarAction, ...]:
        actions: list[SharadarAction] = []
        cursor: str | None = None
        for page_number in range(1, self.MAX_PAGES + 1):
            params = self._request_params()
            if cursor is not None:
                params["qopts.cursor_id"] = cursor
            try:
                payload = _ActionsResponse.model_validate(self._send(params).json())
                page_actions = self._rows_to_actions(payload)
            except (InvalidOperation, KeyError, TypeError, ValidationError, ValueError):
                raise MarketDataFetchError("malformed-response") from None
            cursor = payload.meta.next_cursor_id
            if cursor is not None and not cursor.strip():
                raise MarketDataFetchError("malformed-response")
            actions.extend(page_actions)
            if cursor is None:
                return tuple(
                    sorted(
                        actions,
                        key=lambda action: (
                            action.ticker,
                            action.effective_date,
                            action.kind.value,
                            "" if action.value is None else str(action.value),
                        ),
                    )
                )
            if page_number == self.MAX_PAGES:
                raise MarketDataFetchError("malformed-response")
        raise AssertionError("pagination loop must return or raise")

    def _rows_to_actions(self, payload: _ActionsResponse) -> list[SharadarAction]:
        if not payload.datatable.columns or not payload.datatable.data:
            raise ValueError("empty ACTIONS response")
        columns = {column.name: index for index, column in enumerate(payload.datatable.columns)}
        if set(self.COLUMNS) - columns.keys():
            raise ValueError("required ACTIONS columns missing")
        actions: list[SharadarAction] = []
        for values in payload.datatable.data:
            if len(values) < len(payload.datatable.columns):
                raise ValueError("ACTIONS row is shorter than its columns")
            raw_value = values[columns["value"]]
            if isinstance(raw_value, float):
                raise ValueError("ACTIONS values must not be floats")
            row = _ActionRow.model_validate(
                {
                    column: values[index]
                    for column, index in columns.items()
                    if column in self.COLUMNS
                }
            )
            if not row.ticker.strip():
                raise ValueError("ACTIONS ticker must not be whitespace-only")
            kind = self._ACTION_KINDS.get(row.action)
            if kind is None:
                raise ValueError("unsupported ACTIONS action")
            if kind in {SharadarActionKind.DELISTING, SharadarActionKind.TICKER_CHANGE}:
                if row.value is not None:
                    raise ValueError("valueless ACTIONS action has a value")
            elif row.value is None or not row.value.is_finite():
                raise ValueError("valued ACTIONS action has no finite value")
            elif kind is SharadarActionKind.SPLIT and row.value <= 0:
                raise ValueError("split ratio must be positive")
            actions.append(SharadarAction(row.ticker, row.date, kind, row.value))
        return actions

    def _send(self, params: dict[str, str]) -> httpx.Response:
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                response = self._client.send(self._build_request(params))
            except (httpx.RequestError,):
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

    def _request_params(self) -> dict[str, str]:
        return {"qopts.columns": ",".join(self.COLUMNS)}
