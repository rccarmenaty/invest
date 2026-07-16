from datetime import date
import os
from decimal import Decimal
import traceback

import httpx
import pytest

from invest.adapters.alpaca_market_data import AlpacaMarketDataReader, MarketDataFetchError
from invest.application.ports import MarketDataReader
from invest.domain.models import DailyBar, FixtureInputs, Universe


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("ALPACA_API_KEY_ID"), reason="requires Alpaca credentials")
def test_live_market_data_smoke() -> None:
    result = AlpacaMarketDataReader().fetch(Universe("live", ("AAPL",)), date(2026, 6, 1))
    assert result.bars


def test_fetch_regression_baseline_params_and_output_unchanged_before_refactor(monkeypatch) -> None:
    """Pins fetch()'s existing params/output as a baseline the _paginate/fetch_range
    extraction must preserve byte-identically."""
    monkeypatch.setenv("ALPACA_API_KEY_ID", "key-id")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["start"] == "2026-04-22"
        assert request.url.params["end"] == "2026-06-01"
        return httpx.Response(
            200,
            json={
                "bars": {
                    "ACME": [
                        {"t": "2026-05-29T04:00:00Z", "o": 10, "h": 12, "l": 9, "c": 11, "v": 1234}
                    ]
                },
                "next_page_token": None,
            },
        )

    reader = AlpacaMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = reader.fetch(Universe("v1", ("ACME",)), date(2026, 6, 1))

    assert result == FixtureInputs(
        universe=Universe("v1", ("ACME",)),
        bars=(
            DailyBar(
                symbol="ACME",
                date=date(2026, 5, 29),
                open=Decimal("10"),
                high=Decimal("12"),
                low=Decimal("9"),
                close=Decimal("11"),
                volume=1234,
            ),
        ),
    )


def test_fetch_range_returns_untrimmed_caller_supplied_window(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY_ID", "key-id")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["start"] == "2024-01-01"
        assert request.url.params["end"] == "2024-12-31"
        assert request.url.params["symbols"] == "ACME"
        return httpx.Response(
            200,
            json={
                "bars": {
                    "ACME": [
                        {"t": "2024-06-15T04:00:00Z", "o": 10, "h": 12, "l": 9, "c": 11, "v": 500}
                    ]
                },
                "next_page_token": None,
            },
        )

    reader = AlpacaMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = reader.fetch_range(Universe("v1", ("ACME",)), date(2024, 1, 1), date(2024, 12, 31))

    assert result == FixtureInputs(
        universe=Universe("v1", ("ACME",)),
        bars=(
            DailyBar(
                symbol="ACME",
                date=date(2024, 6, 15),
                open=Decimal("10"),
                high=Decimal("12"),
                low=Decimal("9"),
                close=Decimal("11"),
                volume=500,
            ),
        ),
    )


def test_fetch_range_paginates_and_shares_retry_machinery(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY_ID", "key-id")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret-key")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        token = request.url.params.get("page_token")
        if token is None:
            return httpx.Response(
                200,
                json={
                    "bars": {"ACME": [{"t": "2024-01-02T04:00:00Z", "o": 9, "h": 11, "l": 8, "c": 10, "v": 100}]},
                    "next_page_token": "page-2",
                },
            )
        assert token == "page-2"
        return httpx.Response(
            200,
            json={
                "bars": {"ACME": [{"t": "2024-01-03T04:00:00Z", "o": 10, "h": 12, "l": 9, "c": 11, "v": 200}]},
                "next_page_token": None,
            },
        )

    reader = AlpacaMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = reader.fetch_range(Universe("v1", ("ACME",)), date(2024, 1, 1), date(2024, 12, 31))

    assert len(requests) == 2
    assert [bar.date for bar in result.bars] == [date(2024, 1, 2), date(2024, 1, 3)]


def test_reader_satisfies_port_and_maps_single_page(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY_ID", "key-id")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["symbols"] == "ACME"
        assert request.url.params["timeframe"] == "1Day"
        assert request.url.params["start"] == "2026-04-22"
        assert request.url.params["end"] == "2026-06-01"
        assert request.url.params["feed"] == "sip"
        assert request.url.params["adjustment"] == "split"
        assert request.url.params["limit"] == "10000"
        assert request.headers["APCA-API-KEY-ID"] == "key-id"
        assert request.headers["APCA-API-SECRET-KEY"] == "secret-key"
        return httpx.Response(
            200,
            json={
                "bars": {
                    "ACME": [
                        {
                            "t": "2026-05-29T04:00:00Z",
                            "o": 10,
                            "h": 12,
                            "l": 9,
                            "c": 11,
                            "v": 1234,
                        }
                    ]
                },
                "next_page_token": None,
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    reader = AlpacaMarketDataReader(client=client)
    assert isinstance(reader, MarketDataReader)

    result = reader.fetch(Universe("v1", ("ACME",)), date(2026, 6, 1))

    assert result == FixtureInputs(
        universe=Universe("v1", ("ACME",)),
        bars=(
            DailyBar(
                symbol="ACME",
                date=date(2026, 5, 29),
                open=Decimal("10"),
                high=Decimal("12"),
                low=Decimal("9"),
                close=Decimal("11"),
                volume=1234,
            ),
        ),
    )
    assert isinstance(result.bars[0].volume, Decimal)
    assert result.bars[0].volume == Decimal("1234")


def test_reader_preserves_fractional_alpaca_volume_as_exact_decimal(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY_ID", "key-id")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "bars": {
                    "ACME": [
                        {
                            "t": "2026-05-29T04:00:00Z",
                            "o": 10,
                            "h": 12,
                            "l": 9,
                            "c": 11,
                            "v": 48037.936,
                        }
                    ]
                },
                "next_page_token": None,
            },
        )

    result = AlpacaMarketDataReader(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    ).fetch(Universe("v1", ("ACME",)), date(2026, 6, 1))

    assert isinstance(result.bars[0].volume, Decimal)
    assert result.bars[0].volume == Decimal("48037.936")


def test_reader_rejects_negative_volume_before_domain(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY_ID", "key-id")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "bars": {
                    "ACME": [
                        {
                            "t": "2026-05-29T04:00:00Z",
                            "o": 10,
                            "h": 12,
                            "l": 9,
                            "c": 11,
                            "v": -1,
                        }
                    ]
                },
                "next_page_token": None,
            },
        )

    reader = AlpacaMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch(Universe("v1", ("ACME",)), date(2026, 6, 1))

    assert caught.value.reason == "malformed-response"


def test_reader_merges_paginated_bars(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY_ID", "key-id")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret-key")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        token = request.url.params.get("page_token")
        if token is None:
            return httpx.Response(
                200,
                json={
                    "bars": {"ACME": [{"t": "2026-05-28T04:00:00Z", "o": 9, "h": 11, "l": 8, "c": 10, "v": 100}]},
                    "next_page_token": "page-2",
                },
            )
        assert token == "page-2"
        return httpx.Response(
            200,
            json={
                "bars": {"ACME": [{"t": "2026-05-29T04:00:00Z", "o": 10, "h": 12, "l": 9, "c": 11, "v": 200}]},
                "next_page_token": None,
            },
        )

    reader = AlpacaMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = reader.fetch(Universe("v1", ("ACME",)), date(2026, 6, 1))

    assert len(requests) == 2
    assert [bar.date for bar in result.bars] == [date(2026, 5, 28), date(2026, 5, 29)]


def test_reader_refuses_unbounded_pagination(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY_ID", "key-id")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret-key")
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            200,
            json={"bars": {"ACME": []}, "next_page_token": f"page-{requests + 1}"},
        )

    reader = AlpacaMarketDataReader(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch(Universe("v1", ("ACME",)), date(2026, 6, 1))

    assert caught.value.reason == "malformed-response"
    assert requests == AlpacaMarketDataReader.MAX_PAGES


@pytest.mark.parametrize("status", [401, 403])
def test_auth_failure_is_stable_and_not_retried(monkeypatch, status: int) -> None:
    monkeypatch.setenv("ALPACA_API_KEY_ID", "key-id")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret-key")
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status, json={"message": "unauthorized"})

    reader = AlpacaMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch(Universe("v1", ("ACME",)), date(2026, 6, 1))

    assert caught.value.reason == "auth-failure"
    assert str(caught.value) == "auth-failure"
    assert attempts == 1


def test_malformed_response_is_stable_and_not_retried(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY_ID", "key-id")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret-key")
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(200, json={"bars": {"ACME": [{"invalid": "bar"}]}})

    reader = AlpacaMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch(Universe("v1", ("ACME",)), date(2026, 6, 1))

    assert caught.value.reason == "malformed-response"
    assert str(caught.value) == "malformed-response"
    assert attempts == 1


@pytest.mark.parametrize(
    ("status", "headers", "reason", "expected_sleeps"),
    [
        (429, {}, "rate-limited", [0.5, 1.0]),
        (429, {"Retry-After": "10"}, "rate-limited", [4.0, 4.0]),
        (503, {}, "network-failure", [0.5, 1.0]),
    ],
)
def test_retryable_statuses_exhaust_three_attempts(
    monkeypatch,
    status: int,
    headers: dict[str, str],
    reason: str,
    expected_sleeps: list[float],
) -> None:
    monkeypatch.setenv("ALPACA_API_KEY_ID", "key-id")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret-key")
    attempts = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status, headers=headers)

    reader = AlpacaMarketDataReader(
        client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=sleeps.append
    )
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch(Universe("v1", ("ACME",)), date(2026, 6, 1))

    assert caught.value.reason == reason
    assert attempts == 3
    assert sleeps == expected_sleeps


def test_timeout_exhausts_three_attempts(monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_API_KEY_ID", "key-id")
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", "secret-key")
    attempts = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timed out", request=request)

    reader = AlpacaMarketDataReader(
        client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=sleeps.append
    )
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch(Universe("v1", ("ACME",)), date(2026, 6, 1))

    assert caught.value.reason == "network-failure"
    assert attempts == 3
    assert sleeps == [0.5, 1.0]


def test_secret_values_are_redacted_from_failure_output(monkeypatch) -> None:
    key_id = "visible-key-id"
    secret_key = "visible-secret-key"
    monkeypatch.setenv("ALPACA_API_KEY_ID", key_id)
    monkeypatch.setenv("ALPACA_API_SECRET_KEY", secret_key)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"failed using {key_id} and {secret_key}", request=request)

    reader = AlpacaMarketDataReader(
        client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=lambda _: None
    )
    with pytest.raises(MarketDataFetchError) as caught:
        reader.fetch(Universe("v1", ("ACME",)), date(2026, 6, 1))

    output = "".join(traceback.format_exception(caught.value))
    assert caught.value.reason == "network-failure"
    assert key_id not in output
    assert secret_key not in output


def test_snapshot_rejects_missing_symbol_before_file_io(tmp_path) -> None:
    from invest.adapters.alpaca_market_data import SnapshotWriter

    inputs = FixtureInputs(
        Universe("source", ("ACME", "MISSING")),
        (DailyBar("ACME", date(2026, 6, 1), Decimal("10"), Decimal("11"), Decimal("9"), Decimal("10"), 100),),
    )
    with pytest.raises(MarketDataFetchError) as caught:
        SnapshotWriter().write(inputs, date(2026, 6, 1), tmp_path)
    assert caught.value.reason == "symbol-missing-at-fetch"
    assert "MISSING" in str(caught.value)
    assert not any(tmp_path.iterdir())


def _bars(symbol: str, *, zero_volume: bool = False) -> tuple[DailyBar, ...]:
    return tuple(
        DailyBar(
            symbol,
            date(2026, 5, 12) + __import__("datetime").timedelta(days=index),
            Decimal("10"), Decimal("11"), Decimal("9"), Decimal("10"),
            0 if zero_volume and index == 10 else 100,
        )
        for index in range(21)
    )


def test_snapshot_writes_schema_provenance_and_round_trips(tmp_path) -> None:
    import hashlib
    import json
    from invest.adapters.alpaca_market_data import SnapshotWriter
    from invest.adapters.fixtures_json import JsonFixtureReader
    from invest.domain.scanner import MomentumScanner

    inputs = FixtureInputs(Universe("source", ("ACME",)), _bars("ACME"))
    directory = SnapshotWriter(feed="sip").write(inputs, date(2026, 6, 1), tmp_path)
    universe_path, bars_path = directory / "universe.json", directory / "bars.json"
    universe_payload = json.loads(universe_path.read_text())
    bars_payload = json.loads(bars_path.read_text())
    provenance = json.loads((directory / "provenance.json").read_text())
    assert universe_payload == {"fixture_version": "2026-06-01", "symbols": ["ACME"]}
    assert bars_payload["fixture_version"] == "2026-06-01"
    assert bars_payload["bars"][0]["volume"] == 100
    assert set(provenance) == {"feed", "adjustment", "timeframe", "endpoint", "as_of", "fetch_timestamp", "symbol_count", "bar_count", "universe_sha256", "bars_sha256", "fixture_version", "degraded"}
    expected = {"feed": "sip", "adjustment": "split", "timeframe": "1Day", "endpoint": AlpacaMarketDataReader.ENDPOINT, "as_of": "2026-06-01", "symbol_count": 1, "bar_count": 21, "fixture_version": "2026-06-01", "degraded": False}
    assert expected.items() <= provenance.items()
    assert provenance["universe_sha256"] == hashlib.sha256(universe_path.read_bytes()).hexdigest()
    assert provenance["bars_sha256"] == hashlib.sha256(bars_path.read_bytes()).hexdigest()
    loaded = JsonFixtureReader().load(universe_path, bars_path)
    assert len(MomentumScanner().scan(loaded.universe, loaded.bars)) == 1


def test_snapshot_round_trips_fractional_canonical_volume(tmp_path) -> None:
    import json

    from invest.adapters.alpaca_market_data import SnapshotWriter
    from invest.adapters.fixtures_json import JsonFixtureReader

    inputs = FixtureInputs(
        Universe("source", ("ACME",)),
        (
            DailyBar(
                "ACME",
                date(2026, 6, 1),
                Decimal("10"),
                Decimal("11"),
                Decimal("9"),
                Decimal("10"),
                Decimal("48037.936"),
            ),
        ),
    )

    first_dir = SnapshotWriter().write(inputs, date(2026, 6, 1), tmp_path / "first")
    first_payload = json.loads((first_dir / "bars.json").read_text())
    first_loaded = JsonFixtureReader().load(first_dir / "universe.json", first_dir / "bars.json")

    assert first_payload["bars"][0]["volume"] == "48037.936"
    assert first_loaded.bars[0].volume == Decimal("48037.936")

    second_dir = SnapshotWriter().write(first_loaded, date(2026, 6, 1), tmp_path / "second")
    second_payload = json.loads((second_dir / "bars.json").read_text())
    second_loaded = JsonFixtureReader().load(
        second_dir / "universe.json", second_dir / "bars.json"
    )

    assert second_payload["bars"][0]["volume"] == first_payload["bars"][0]["volume"]
    assert second_loaded.bars[0].volume == first_loaded.bars[0].volume


def test_iex_is_degraded_and_zero_volume_is_snapshot_not_fetch_gap(tmp_path) -> None:
    import json
    from invest.adapters.alpaca_market_data import SnapshotWriter
    from invest.adapters.fixtures_json import JsonFixtureReader
    from invest.domain.rejection import RejectionReason
    from invest.domain.scanner import MomentumScanner

    inputs = FixtureInputs(Universe("source", ("HALT",)), _bars("HALT", zero_volume=True))
    directory = SnapshotWriter(feed="iex").write(inputs, date(2026, 6, 1), tmp_path)
    assert json.loads((directory / "provenance.json").read_text())["degraded"] is True
    loaded = JsonFixtureReader().load(directory / "universe.json", directory / "bars.json")
    assert MomentumScanner().scan(loaded.universe, loaded.bars)[0].reason is RejectionReason.MISSING_DATA


def test_calendar_buffer_yields_at_least_21_trading_bars_across_holidays() -> None:
    from datetime import timedelta

    as_of = date(2026, 1, 5)
    holidays = {date(2025, 12, 25), date(2026, 1, 1)}

    def handler(request: httpx.Request) -> httpx.Response:
        assert AlpacaMarketDataReader.CALENDAR_BUFFER_DAYS == 40
        assert request.url.params["start"] == "2025-11-26"
        current = date.fromisoformat(request.url.params["start"])
        rows = []
        while current <= as_of:
            if current.weekday() < 5 and current not in holidays:
                rows.append({"t": f"{current.isoformat()}T05:00:00Z", "o": 10, "h": 11, "l": 9, "c": 10, "v": 100})
            current += timedelta(days=1)
        return httpx.Response(200, json={"bars": {"ACME": rows}, "next_page_token": None})

    reader = AlpacaMarketDataReader(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert len(reader.fetch(Universe("v1", ("ACME",)), as_of).bars) >= 21


def test_snapshot_write_failure_leaves_no_partial_snapshot(tmp_path, monkeypatch) -> None:
    from pathlib import Path
    from invest.adapters.alpaca_market_data import SnapshotWriter

    original = Path.write_bytes
    writes = 0

    def fail_second_write(path: Path, data: bytes) -> int:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("disk full")
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_second_write)
    inputs = FixtureInputs(Universe("source", ("ACME",)), _bars("ACME"))
    with pytest.raises(MarketDataFetchError) as caught:
        SnapshotWriter().write(inputs, date(2026, 6, 1), tmp_path)
    assert caught.value.reason == "storage-failure"
    assert str(caught.value) == "storage-failure"
    assert not (tmp_path / "2026-06-01").exists()
    assert list(tmp_path.iterdir()) == []


def test_snapshot_publication_race_maps_to_snapshot_exists(tmp_path, monkeypatch) -> None:
    from pathlib import Path
    from invest.adapters.alpaca_market_data import SnapshotWriter

    original_replace = Path.replace
    destination = tmp_path / "2026-06-01"

    def race_replace(staging: Path, target: Path) -> Path:
        target.mkdir()
        (target / "winner.txt").write_text("winner", encoding="utf-8")
        return original_replace(staging, target)

    monkeypatch.setattr(Path, "replace", race_replace)
    inputs = FixtureInputs(Universe("source", ("ACME",)), _bars("ACME"))
    with pytest.raises(MarketDataFetchError) as caught:
        SnapshotWriter().write(inputs, date(2026, 6, 1), tmp_path)

    assert caught.value.reason == "snapshot-exists"
    assert (destination / "winner.txt").read_text(encoding="utf-8") == "winner"
    assert list(tmp_path.iterdir()) == [destination]
