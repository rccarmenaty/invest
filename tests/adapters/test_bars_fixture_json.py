"""Tests for BarsFixtureWriter — --bars-out fixture pair export."""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from invest.adapters.bars_fixture_json import (
    BarsFixtureDuplicateBarError,
    BarsFixtureExistsError,
    BarsFixtureStorageError,
    BarsFixtureSymbolMismatchError,
    BarsFixtureWriter,
)
from invest.adapters.fixtures_json import JsonFixtureReader
from invest.domain.models import DailyBar, FixtureInputs, Universe


def _bar(symbol: str, day: date, *, volume: Decimal | int = 1_000_000) -> DailyBar:
    close = Decimal("10")
    return DailyBar(symbol, day, close, close + Decimal("0.5"), close - Decimal("0.5"), close, volume)


def test_round_trip_via_json_fixture_reader(tmp_path) -> None:
    start = date(2024, 1, 2)
    bars = tuple(_bar("ACME", start + timedelta(days=i)) for i in range(3))
    universe = Universe("2024-01-04", ("ACME",))
    inputs = FixtureInputs(universe, bars)

    directory = BarsFixtureWriter().write(inputs, tmp_path / "fixtures")

    loaded = JsonFixtureReader().load(directory / "universe.json", directory / "bars.json")
    assert loaded.universe == universe
    assert loaded.bars == bars


def test_ragged_coverage_round_trips_without_full_calendar(tmp_path) -> None:
    start = date(2024, 1, 2)
    acme_bars = tuple(_bar("ACME", start + timedelta(days=i)) for i in range(5))
    late_ipo_bars = tuple(_bar("NEWCO", start + timedelta(days=i)) for i in range(2, 4))
    bars = acme_bars + late_ipo_bars
    universe = Universe("2024-01-06", ("ACME", "NEWCO"))
    inputs = FixtureInputs(universe, bars)

    directory = BarsFixtureWriter().write(inputs, tmp_path / "fixtures")

    loaded = JsonFixtureReader().load(directory / "universe.json", directory / "bars.json")
    assert {bar.symbol for bar in loaded.bars if bar.symbol == "NEWCO"} == {"NEWCO"}
    assert sum(1 for bar in loaded.bars if bar.symbol == "NEWCO") == 2
    assert sum(1 for bar in loaded.bars if bar.symbol == "ACME") == 5


@pytest.mark.parametrize(
    ("universe_symbols", "bars"),
    [
        (("ACME", "NEWCO"), (_bar("ACME", date(2024, 1, 2)),)),
        (("ACME",), (_bar("ACME", date(2024, 1, 2)), _bar("NEWCO", date(2024, 1, 2)))),
        (("ACME",), ()),
    ],
    ids=["universe-symbol-without-bars", "bar-not-in-universe", "empty-bars"],
)
def test_symbol_set_mismatch_fails_closed(tmp_path, universe_symbols, bars) -> None:
    out = tmp_path / "fixtures"
    universe = Universe("2024-01-04", universe_symbols)
    inputs = FixtureInputs(universe, bars)

    with pytest.raises(BarsFixtureSymbolMismatchError) as caught:
        BarsFixtureWriter().write(inputs, out)

    assert caught.value.reason == "bars-universe-mismatch"
    assert not out.exists()
    assert list(tmp_path.iterdir()) == []


def test_preexisting_directory_refused_and_untouched(tmp_path) -> None:
    out = tmp_path / "fixtures"
    out.mkdir()
    (out / "sentinel.txt").write_text("keep", encoding="utf-8")

    bars = (_bar("ACME", date(2024, 1, 2)),)
    inputs = FixtureInputs(Universe("2024-01-04", ("ACME",)), bars)

    with pytest.raises(BarsFixtureExistsError) as caught:
        BarsFixtureWriter().write(inputs, out)

    assert caught.value.reason == "bars-out-exists"
    assert (out / "sentinel.txt").read_text(encoding="utf-8") == "keep"
    assert list(out.iterdir()) == [out / "sentinel.txt"]


def test_write_failure_leaves_no_partial_directory(tmp_path, monkeypatch) -> None:
    original = Path.write_bytes
    writes = 0

    def fail_second_write(path: Path, data: bytes) -> int:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("disk full")
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_second_write)

    out = tmp_path / "fixtures"
    bars = (_bar("ACME", date(2024, 1, 2)),)
    inputs = FixtureInputs(Universe("2024-01-04", ("ACME",)), bars)

    with pytest.raises(BarsFixtureStorageError) as caught:
        BarsFixtureWriter().write(inputs, out)

    assert caught.value.reason == "storage-failure"
    assert not out.exists()
    assert list(tmp_path.iterdir()) == []


def test_serialization_ohlc_and_volume_and_determinism(tmp_path) -> None:
    fractional_bar = DailyBar(
        "ACME", date(2024, 1, 2), Decimal("10.25"), Decimal("11.5"), Decimal("9.75"),
        Decimal("10.5"), Decimal("1234.5"),
    )
    whole_bar = DailyBar(
        "ACME", date(2024, 1, 3), Decimal("10.25"), Decimal("11.5"), Decimal("9.75"),
        Decimal("10.5"), Decimal("1000000"),
    )
    universe = Universe("2024-01-04", ("ACME",))
    inputs = FixtureInputs(universe, (fractional_bar, whole_bar))
    out = tmp_path / "fixtures"

    directory = BarsFixtureWriter().write(inputs, out)

    bars_payload = json.loads((directory / "bars.json").read_text(encoding="utf-8"))
    by_date = {row["date"]: row for row in bars_payload["bars"]}
    assert by_date["2024-01-02"]["open"] == "10.25"
    assert by_date["2024-01-02"]["volume"] == "1234.5"
    assert by_date["2024-01-03"]["volume"] == 1000000

    raw_bytes = (directory / "bars.json").read_bytes()
    expected = (
        json.dumps(bars_payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    assert raw_bytes == expected


def test_unsorted_input_round_trips_via_json_fixture_reader(tmp_path) -> None:
    start = date(2024, 1, 2)
    shuffled_bars = (
        _bar("NEWCO", start + timedelta(days=1)),
        _bar("ACME", start + timedelta(days=2)),
        _bar("NEWCO", start),
        _bar("ACME", start),
        _bar("ACME", start + timedelta(days=1)),
    )
    universe = Universe("2024-01-04", ("ACME", "NEWCO"))
    inputs = FixtureInputs(universe, shuffled_bars)

    directory = BarsFixtureWriter().write(inputs, tmp_path / "fixtures")

    loaded = JsonFixtureReader().load(directory / "universe.json", directory / "bars.json")
    assert {bar.symbol for bar in loaded.bars} == {"ACME", "NEWCO"}
    assert sum(1 for bar in loaded.bars if bar.symbol == "ACME") == 3
    assert sum(1 for bar in loaded.bars if bar.symbol == "NEWCO") == 2


def test_duplicate_symbol_date_fails_closed(tmp_path) -> None:
    out = tmp_path / "fixtures"
    day = date(2024, 1, 2)
    bars = (_bar("ACME", day), _bar("ACME", day))
    inputs = FixtureInputs(Universe("2024-01-04", ("ACME",)), bars)

    with pytest.raises(BarsFixtureDuplicateBarError) as caught:
        BarsFixtureWriter().write(inputs, out)

    assert caught.value.reason == "duplicate-bar"
    assert not out.exists()
    assert list(tmp_path.iterdir()) == []


def test_fixture_version_shared_across_both_payloads(tmp_path) -> None:
    universe = Universe("2024-06-30", ("ACME",))
    inputs = FixtureInputs(universe, (_bar("ACME", date(2024, 1, 2)),))
    out = tmp_path / "fixtures"

    directory = BarsFixtureWriter().write(inputs, out)

    universe_payload = json.loads((directory / "universe.json").read_text(encoding="utf-8"))
    bars_payload = json.loads((directory / "bars.json").read_text(encoding="utf-8"))
    assert universe_payload["fixture_version"] == "2024-06-30"
    assert bars_payload["fixture_version"] == "2024-06-30"
