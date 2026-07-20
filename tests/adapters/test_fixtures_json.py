import gc
import json
import tracemalloc
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from invest.adapters.fixtures_json import FixtureValidationError, JsonFixtureReader


def write_fixture(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload))
    return path


def valid_universe() -> dict:
    return {"fixture_version": "v1", "symbols": ["ACME"]}


def valid_bars() -> dict:
    return {
        "fixture_version": "v1",
        "bars": [
            {"symbol": "ACME", "date": "2026-07-09", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 1000},
            {"symbol": "ACME", "date": "2026-07-10", "open": 11, "high": 13, "low": 10, "close": 12, "volume": 2000},
        ],
    }


def load(tmp_path: Path, universe: object, bars: object):
    return JsonFixtureReader().load(
        write_fixture(tmp_path / "universe.json", universe),
        write_fixture(tmp_path / "bars.json", bars),
    )


def test_loads_valid_versioned_fixtures(tmp_path: Path) -> None:
    inputs = load(tmp_path, valid_universe(), valid_bars())

    assert inputs.universe.fixture_version == "v1"
    assert inputs.universe.symbols == ("ACME",)
    assert [(bar.symbol, bar.date.isoformat()) for bar in inputs.bars] == [
        ("ACME", "2026-07-09"),
        ("ACME", "2026-07-10"),
    ]


def test_load_filters_bars_to_inclusive_date_window(tmp_path: Path) -> None:
    bars = valid_bars()
    bars["bars"] = [
        {**bars["bars"][0], "date": "2026-07-08"},
        bars["bars"][0],
        bars["bars"][1],
        {**bars["bars"][1], "date": "2026-07-11"},
    ]

    inputs = JsonFixtureReader().load(
        write_fixture(tmp_path / "universe.json", valid_universe()),
        write_fixture(tmp_path / "bars.json", bars),
        start=date(2026, 7, 9),
        end=date(2026, 7, 10),
    )

    assert [bar.date for bar in inputs.bars] == [date(2026, 7, 9), date(2026, 7, 10)]


def test_load_keeps_only_requested_per_symbol_warmup_before_start(tmp_path: Path) -> None:
    bars = valid_bars()
    bars["bars"] = [
        {**bars["bars"][0], "date": "2026-07-07"},
        {**bars["bars"][0], "date": "2026-07-08"},
        bars["bars"][0],
        bars["bars"][1],
        {**bars["bars"][1], "date": "2026-07-11"},
    ]

    inputs = JsonFixtureReader().load(
        write_fixture(tmp_path / "universe.json", valid_universe()),
        write_fixture(tmp_path / "bars.json", bars),
        start=date(2026, 7, 9),
        end=date(2026, 7, 10),
        warmup_bars=1,
    )

    assert [bar.date for bar in inputs.bars] == [
        date(2026, 7, 8),
        date(2026, 7, 9),
        date(2026, 7, 10),
    ]


def test_load_date_window_does_not_materialize_excluded_bars(tmp_path: Path) -> None:
    symbols = [f"S{index:02d}" for index in range(20)]
    old_start = date(2020, 1, 1)
    raw_bars = [
        {
            "symbol": symbol,
            "date": (old_start + timedelta(days=offset)).isoformat(),
            "open": 10,
            "high": 12,
            "low": 9,
            "close": 11,
            "volume": 1000,
        }
        for symbol in symbols
        for offset in range(1000)
    ]
    raw_bars.extend(
        {
            "symbol": symbol,
            "date": "2026-07-09",
            "open": 10,
            "high": 12,
            "low": 9,
            "close": 11,
            "volume": 1000,
        }
        for symbol in symbols
    )
    universe_path = write_fixture(
        tmp_path / "universe.json",
        {"fixture_version": "v1", "symbols": symbols},
    )
    bars_path = write_fixture(
        tmp_path / "bars.json",
        {"fixture_version": "v1", "bars": raw_bars},
    )
    del raw_bars
    gc.collect()

    tracemalloc.start()
    try:
        inputs = JsonFixtureReader().load(
            universe_path,
            bars_path,
            start=date(2026, 7, 9),
            end=date(2026, 7, 9),
        )
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert len(inputs.bars) == len(symbols)
    assert peak_bytes < 8_000_000


def test_load_rejects_inverted_date_window(tmp_path: Path) -> None:
    with pytest.raises(FixtureValidationError) as error:
        JsonFixtureReader().load(
            write_fixture(tmp_path / "universe.json", valid_universe()),
            write_fixture(tmp_path / "bars.json", valid_bars()),
            start=date(2026, 7, 10),
            end=date(2026, 7, 9),
        )

    assert error.value.reason.value == "fixture-invalid"


def test_load_still_validates_bars_excluded_by_date_window(tmp_path: Path) -> None:
    bars = valid_bars()
    bars["bars"][0]["volume"] = -1

    with pytest.raises(FixtureValidationError) as error:
        JsonFixtureReader().load(
            write_fixture(tmp_path / "universe.json", valid_universe()),
            write_fixture(tmp_path / "bars.json", bars),
            start=date(2026, 7, 10),
            end=date(2026, 7, 10),
        )

    assert error.value.reason.value == "fixture-invalid"


def test_loads_fractional_volume_as_canonical_decimal(tmp_path: Path) -> None:
    bars = valid_bars()
    bars["bars"][0]["volume"] = "48037.936"

    inputs = load(tmp_path, valid_universe(), bars)

    assert inputs.bars[0].volume == Decimal("48037.936")
    assert isinstance(inputs.bars[0].volume, Decimal)


def test_rejects_negative_volume_before_producing_daily_bars(tmp_path: Path) -> None:
    bars = valid_bars()
    bars["bars"][0]["volume"] = -1

    with pytest.raises(FixtureValidationError) as error:
        load(tmp_path, valid_universe(), bars)

    assert error.value.reason.value == "fixture-invalid"


@pytest.mark.parametrize(
    ("mutate", "reason"),
    [
        (lambda universe, bars: bars.update({"bars": "not-a-list"}), "fixture-invalid"),
        (lambda universe, bars: bars["bars"].append(dict(bars["bars"][0])), "duplicate-bar"),
        (lambda universe, bars: bars.update({"bars": list(reversed(bars["bars"]))}), "non-monotonic-bars"),
        (lambda universe, bars: bars["bars"][0].update({"symbol": "UNKNOWN"}), "fixture-symbol-missing"),
        (lambda universe, bars: bars.update({"fixture_version": "v2"}), "fixture-version-mismatch"),
    ],
)
def test_rejects_invalid_input_before_scanning(tmp_path: Path, mutate, reason: str) -> None:
    universe = valid_universe()
    bars = valid_bars()
    mutate(universe, bars)

    with pytest.raises(FixtureValidationError) as error:
        load(tmp_path, universe, bars)

    assert error.value.reason.value == reason


def test_rejects_malformed_json_as_fixture_invalid(tmp_path: Path) -> None:
    universe_path = tmp_path / "universe.json"
    universe_path.write_text("{")
    bars_path = write_fixture(tmp_path / "bars.json", valid_bars())

    with pytest.raises(FixtureValidationError) as error:
        JsonFixtureReader().load(universe_path, bars_path)

    assert error.value.reason.value == "fixture-invalid"


def test_rejects_large_truncated_bar_value_with_bounded_memory(tmp_path: Path) -> None:
    universe_path = write_fixture(tmp_path / "universe.json", valid_universe())
    bars_path = tmp_path / "bars.json"
    with bars_path.open("w", encoding="utf-8") as fixture_file:
        fixture_file.write('{"fixture_version":"v1","bars":["')
        fixture_file.write("x" * 8_000_000)
    gc.collect()

    tracemalloc.start()
    try:
        with pytest.raises(FixtureValidationError) as error:
            JsonFixtureReader().load(universe_path, bars_path)
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert error.value.reason.value == "fixture-invalid"
    assert peak_bytes < 5_000_000


def test_rejects_invalid_utf8_as_fixture_invalid(tmp_path: Path) -> None:
    universe_path = tmp_path / "universe.json"
    universe_path.write_bytes(b"\xff")
    bars_path = write_fixture(tmp_path / "bars.json", valid_bars())

    with pytest.raises(FixtureValidationError) as error:
        JsonFixtureReader().load(universe_path, bars_path)

    assert error.value.reason.value == "fixture-invalid"


@pytest.mark.parametrize(
    "changes",
    [
        {"symbol": ""},
        {"open": 0},
        {"high": -1},
        {"low": 0},
        {"close": -1},
        {"volume": -1},
        {"open": 13, "high": 12},
        {"close": 8, "low": 9},
        {"low": 13, "high": 12},
    ],
)
def test_rejects_invalid_bar_values_as_fixture_invalid(tmp_path: Path, changes: dict) -> None:
    bars = valid_bars()
    bars["bars"][0].update(changes)

    with pytest.raises(FixtureValidationError) as error:
        load(tmp_path, valid_universe(), bars)

    assert error.value.reason.value == "fixture-invalid"


def test_rejects_universe_symbol_without_bars(tmp_path: Path) -> None:
    universe = valid_universe()
    universe["symbols"].append("BETA")

    with pytest.raises(FixtureValidationError) as error:
        load(tmp_path, universe, valid_bars())

    assert error.value.reason.value == "fixture-symbol-missing"
