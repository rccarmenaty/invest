import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from invest.adapters import cli
from invest.adapters.alpaca_market_data import MarketDataFetchError
from invest.domain.models import DailyBar, FixtureInputs


def _universe(path: Path) -> None:
    path.write_text('{"fixture_version":"v1","symbols":["ACME"]}', encoding="utf-8")


def test_fetch_requires_as_of_before_constructing_reader(tmp_path, monkeypatch) -> None:
    universe = tmp_path / "universe.json"
    _universe(universe)
    monkeypatch.setattr(cli, "AlpacaMarketDataReader", lambda **kwargs: pytest.fail("fetch attempted"), raising=False)
    with pytest.raises(SystemExit) as caught:
        cli.fetch_main(["--universe", str(universe)])
    assert caught.value.code == 2


def test_fetch_success_writes_snapshot(tmp_path, monkeypatch, capsys) -> None:
    universe = tmp_path / "universe.json"
    out = tmp_path / "snapshots"
    _universe(universe)

    class Reader:
        def __init__(self, **kwargs): pass
        def fetch(self, requested, as_of):
            return FixtureInputs(requested, (DailyBar("ACME", date(2026, 6, 1), Decimal("10"), Decimal("11"), Decimal("9"), Decimal("10"), 100),))

    monkeypatch.setattr(cli, "AlpacaMarketDataReader", Reader, raising=False)
    assert cli.fetch_main(["--universe", str(universe), "--as-of", "2026-06-01", "--out", str(out)]) == 0
    assert (out / "2026-06-01" / "provenance.json").is_file()
    assert capsys.readouterr().err == ""


def test_fetch_failure_is_one_machine_record_and_no_files(tmp_path, monkeypatch, capsys) -> None:
    universe = tmp_path / "universe.json"
    out = tmp_path / "snapshots"
    _universe(universe)

    class Reader:
        def __init__(self, **kwargs): pass
        def fetch(self, requested, as_of): raise MarketDataFetchError("auth-failure")

    monkeypatch.setattr(cli, "AlpacaMarketDataReader", Reader, raising=False)
    assert cli.fetch_main(["--universe", str(universe), "--as-of", "2026-06-01", "--out", str(out)]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"reason": "auth-failure"}
    assert captured.out.count("\n") == 1
    assert captured.err == ""
    assert not out.exists()


@pytest.mark.parametrize(
    ("filename", "contents"),
    [
        ("missing.json", None),
        ("malformed.json", "{not-json"),
        ("missing-symbols.json", '{"fixture_version":"v1"}'),
    ],
)
def test_invalid_universe_fails_once_before_network(
    tmp_path, monkeypatch, capsys, filename: str, contents: str | None
) -> None:
    universe = tmp_path / filename
    if contents is not None:
        universe.write_text(contents, encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "AlpacaMarketDataReader",
        lambda **kwargs: pytest.fail("network reader constructed"),
    )

    assert cli.fetch_main(["--universe", str(universe), "--as-of", "2026-06-01"]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"reason": "fixture-invalid"}
    assert captured.out.count("\n") == 1
    assert captured.err == ""


def test_symbol_gap_failure_record_names_missing_symbols(tmp_path, monkeypatch, capsys) -> None:
    universe = tmp_path / "universe.json"
    out = tmp_path / "snapshots"
    _universe(universe)

    class Reader:
        def __init__(self, **kwargs): pass
        def fetch(self, requested, as_of):
            raise MarketDataFetchError("symbol-missing-at-fetch", "ACME")

    monkeypatch.setattr(cli, "AlpacaMarketDataReader", Reader)
    assert cli.fetch_main(["--universe", str(universe), "--as-of", "2026-06-01", "--out", str(out)]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {
        "reason": "symbol-missing-at-fetch",
        "message": "symbol-missing-at-fetch: ACME",
    }
    assert captured.out.count("\n") == 1
    assert captured.err == ""
    assert not out.exists()


def test_existing_snapshot_is_untouched_and_fails_once(tmp_path, monkeypatch, capsys) -> None:
    universe = tmp_path / "universe.json"
    out = tmp_path / "snapshots"
    existing = out / "2026-06-01"
    existing.mkdir(parents=True)
    marker = existing / "keep.txt"
    marker.write_text("original", encoding="utf-8")
    _universe(universe)

    class Reader:
        def __init__(self, **kwargs): pass
        def fetch(self, requested, as_of):
            return FixtureInputs(requested, _one_bar())

    monkeypatch.setattr(cli, "AlpacaMarketDataReader", Reader)
    assert cli.fetch_main(["--universe", str(universe), "--as-of", "2026-06-01", "--out", str(out)]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"reason": "snapshot-exists"}
    assert captured.out.count("\n") == 1
    assert captured.err == ""
    assert marker.read_text(encoding="utf-8") == "original"
    assert list(existing.iterdir()) == [marker]


def test_storage_failure_is_one_machine_record_and_no_partial_files(
    tmp_path, monkeypatch, capsys
) -> None:
    universe = tmp_path / "universe.json"
    out = tmp_path / "snapshots"
    _universe(universe)

    class Reader:
        def __init__(self, **kwargs): pass
        def fetch(self, requested, as_of):
            return FixtureInputs(requested, _one_bar())

    class Writer:
        def __init__(self, **kwargs): pass
        def write(self, inputs, as_of, destination):
            raise MarketDataFetchError("storage-failure")

    monkeypatch.setattr(cli, "AlpacaMarketDataReader", Reader)
    monkeypatch.setattr(cli, "SnapshotWriter", Writer)
    assert cli.fetch_main(["--universe", str(universe), "--as-of", "2026-06-01", "--out", str(out)]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"reason": "storage-failure"}
    assert captured.out.count("\n") == 1
    assert captured.err == ""
    assert not out.exists()


def _one_bar() -> tuple[DailyBar, ...]:
    return (DailyBar("ACME", date(2026, 6, 1), Decimal("10"), Decimal("11"), Decimal("9"), Decimal("10"), 100),)
