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
