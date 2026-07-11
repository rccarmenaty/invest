import json
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
