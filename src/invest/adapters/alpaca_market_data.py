import os
import time
import hashlib
import json
import shutil
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Callable

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from invest.domain.models import DailyBar, FixtureInputs, Universe


class MarketDataFetchError(RuntimeError):
    def __init__(self, reason: str, detail: str | None = None) -> None:
        self.reason = reason
        super().__init__(reason if detail is None else f"{reason}: {detail}")


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
    CALENDAR_BUFFER_DAYS = 40
    MAX_PAGES = 64
    MAX_ATTEMPTS = 3
    BACKOFF_BASE_SECONDS = 0.5
    BACKOFF_CAP_SECONDS = 4.0

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
        return self._paginate(universe, as_of - timedelta(days=self.CALENDAR_BUFFER_DAYS), as_of)

    def fetch_range(self, universe: Universe, start: date, end: date) -> FixtureInputs:
        """Bulk historical range fetch, additive to `fetch()`: no CALENDAR_BUFFER_DAYS trimming."""
        return self._paginate(universe, start, end)

    def _paginate(self, universe: Universe, start: date, end: date) -> FixtureInputs:
        bars_by_symbol: dict[str, list[DailyBar]] = {}
        page_token: str | None = None
        for page_number in range(1, self.MAX_PAGES + 1):
            params = self._request_params(universe, start, end)
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
            if page_number == self.MAX_PAGES:
                raise MarketDataFetchError("malformed-response")
        raise AssertionError("pagination loop must return or raise")

    def _send_with_retry(self, params: dict[str, str | int]) -> httpx.Response:
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
            if response.status_code == 429:
                if attempt == self.MAX_ATTEMPTS - 1:
                    raise MarketDataFetchError("rate-limited")
                self._sleep(self._backoff(attempt, response.headers.get("Retry-After")))
                continue
            if response.status_code >= 500:
                if attempt == self.MAX_ATTEMPTS - 1:
                    raise MarketDataFetchError("network-failure")
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

    def _request_params(self, universe: Universe, start: date, end: date) -> dict[str, str | int]:
        return {
            "symbols": ",".join(universe.symbols),
            "timeframe": "1Day",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "feed": self._feed,
            "adjustment": "split",
            "limit": 10000,
        }


class SnapshotWriter:
    def __init__(self, *, feed: str = "sip") -> None:
        self._feed = feed

    def write(self, inputs: FixtureInputs, as_of: date, out: Path) -> Path:
        missing = sorted(set(inputs.universe.symbols) - {bar.symbol for bar in inputs.bars})
        if missing:
            raise MarketDataFetchError("symbol-missing-at-fetch", ",".join(missing))

        version = as_of.isoformat()
        universe_bytes = self._json_bytes(
            {"fixture_version": version, "symbols": list(inputs.universe.symbols)}
        )
        bars_bytes = self._json_bytes(
            {
                "fixture_version": version,
                "bars": [
                    {
                        "symbol": bar.symbol,
                        "date": bar.date.isoformat(),
                        "open": str(bar.open),
                        "high": str(bar.high),
                        "low": str(bar.low),
                        "close": str(bar.close),
                        "volume": bar.volume,
                    }
                    for bar in inputs.bars
                ],
            }
        )
        provenance_bytes = self._json_bytes(
            {
                "feed": self._feed,
                "adjustment": "split",
                "timeframe": "1Day",
                "endpoint": AlpacaMarketDataReader.ENDPOINT,
                "as_of": version,
                "fetch_timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol_count": len(inputs.universe.symbols),
                "bar_count": len(inputs.bars),
                "universe_sha256": hashlib.sha256(universe_bytes).hexdigest(),
                "bars_sha256": hashlib.sha256(bars_bytes).hexdigest(),
                "fixture_version": version,
                "degraded": self._feed == "iex",
            }
        )
        directory = out / version
        if directory.exists():
            raise MarketDataFetchError("snapshot-exists")
        staging: Path | None = None
        try:
            out.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=f".{version}-", dir=out))
            (staging / "universe.json").write_bytes(universe_bytes)
            (staging / "bars.json").write_bytes(bars_bytes)
            (staging / "provenance.json").write_bytes(provenance_bytes)
            staging.replace(directory)
        except OSError:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)
            reason = "snapshot-exists" if directory.exists() else "storage-failure"
            raise MarketDataFetchError(reason) from None
        except BaseException:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)
            raise
        return directory

    @staticmethod
    def _json_bytes(payload: object) -> bytes:
        return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
