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
    value: Decimal | None = None


# Real SHARADAR/ACTIONS literals folded onto the closed 4-kind SharadarActionKind enum.
# No consumer branches on kind (the builder is kind-blind), so mapping many raw literals
# onto few kinds is deliberate: fewer states, no downstream churn.
_ACTION_KINDS = {
    "split": SharadarActionKind.SPLIT,
    "adrratiosplit": SharadarActionKind.SPLIT,
    "dividend": SharadarActionKind.DIVIDEND,
    "spinoffdividend": SharadarActionKind.DIVIDEND,
    "delisted": SharadarActionKind.DELISTING,
    "regulatorydelisting": SharadarActionKind.DELISTING,
    "voluntarydelisting": SharadarActionKind.DELISTING,
    "bankruptcyliquidation": SharadarActionKind.DELISTING,
    "tickerchangeto": SharadarActionKind.TICKER_CHANGE,
    "tickerchangefrom": SharadarActionKind.TICKER_CHANGE,
}

# Explicit, deliberate skips: high-frequency noise that must never abort a fetch and must
# never become a spurious blocker. Documented (not just dropped-as-unknown) so the intent is
# testable. Any literal outside _ACTION_KINDS and _SKIPPED_ACTIONS is also dropped (forward
# compatibility against provider vocabulary drift).
_SKIPPED_ACTIONS = frozenset(
    {
        "listed",
        "relation",
        "acquisitionby",
        "acquisitionof",
        "mergerto",
        "mergerfrom",
        "spinoff",
        "spunofffrom",
    }
)


class SharadarActionsReader:
    ENDPOINT = "https://data.nasdaq.com/api/v3/datatables/SHARADAR/ACTIONS.json"
    COLUMNS = ("ticker", "date", "action", "value")
    MAX_PAGES = 512
    MAX_ATTEMPTS = 3
    BACKOFF_BASE_SECONDS = 0.5
    BACKOFF_CAP_SECONDS = 4.0

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
            except ValidationError:
                # Pydantic's rendering is a multi-line schema dump; keep it out of the reason.
                raise MarketDataFetchError("malformed-response") from None
            except (InvalidOperation, KeyError, TypeError, ValueError) as error:
                raise MarketDataFetchError("malformed-response", str(error)) from None
            cursor = payload.meta.next_cursor_id
            if cursor is not None and not cursor.strip():
                raise MarketDataFetchError("malformed-response", "blank pagination cursor")
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
                raise MarketDataFetchError(
                    "malformed-response", f"page cap of {self.MAX_PAGES} exhausted"
                )
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
            kind = _ACTION_KINDS.get(values[columns["action"]])
            if kind is None:
                # Skip-unknown: explicit skip literals and any unrecognized drift both drop
                # silently here, before validation, so odd fields on a dropped row can never
                # abort the multi-page fetch.
                continue
            row = _ActionRow.model_validate(
                {
                    column: values[index]
                    for column, index in columns.items()
                    if column in {"ticker", "date", "value"}
                }
            )
            if not row.ticker.strip():
                raise ValueError("ACTIONS ticker must not be whitespace-only")
            value = row.value
            if kind in {SharadarActionKind.DELISTING, SharadarActionKind.TICKER_CHANGE}:
                # Real ACTIONS attach a contra/last price to delisting and ticker-change
                # rows; the kind-blind context builder never uses it, so drop it rather
                # than fail the fetch.
                value = None
            elif value is None or not value.is_finite():
                raise ValueError("valued ACTIONS action has no finite value")
            elif value <= 0:
                raise ValueError("valued ACTIONS ratio/amount must be positive")
            actions.append(SharadarAction(row.ticker, row.date, kind, value))
        return actions

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
