import json
from pathlib import Path

import pytest

from invest.adapters import cli


UNIVERSE = Path("fixtures/backtest/universe.json")
BARS = Path("fixtures/backtest/bars.json")

DAY0_DISCLAIMER = (
    "DAY-0 MECHANICS ONLY: measures current day-0 paper-trading entry mechanics, "
    "NOT SPEC §2.4 confirmed-entry edge."
)
SURVIVORSHIP_DISCLAIMER = (
    "SURVIVORSHIP-BIASED UNIVERSE: fixed historical screen, NOT point-in-time index "
    "membership; results are optimistically biased."
)
COST_MODEL_DISCLAIMER = (
    "COST MODEL IS AN APPROXIMATION: fixed-bps slippage + zero commission + flat tax "
    "haircut, not precision accounting."
)


def test_backtest_bars_run_prints_one_report_with_metrics_and_disclaimers_and_touches_no_broker(
    capsys, monkeypatch
) -> None:
    monkeypatch.setattr(
        cli, "AlpacaBroker", lambda *a, **k: pytest.fail("BrokerPort must never be constructed")
    )

    result = cli.backtest_main(["--universe", str(UNIVERSE), "--bars", str(BARS), "--format", "json"])

    captured = capsys.readouterr()
    assert result == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["disclaimers"]["day0"] == DAY0_DISCLAIMER
    assert payload["disclaimers"]["survivorship"] == SURVIVORSHIP_DISCLAIMER
    assert payload["disclaimers"]["cost_model"] == COST_MODEL_DISCLAIMER


def test_backtest_report_has_exact_top_level_snake_case_metric_keys(capsys) -> None:
    result = cli.backtest_main(["--universe", str(UNIVERSE), "--bars", str(BARS), "--format", "json"])

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert {"hit_rate", "expectancy", "max_drawdown", "trade_count", "net_pnl"} <= payload.keys()
    assert payload["trade_count"] == 3


def test_backtest_missing_fixture_prints_exactly_one_record_and_exits_two(tmp_path, capsys) -> None:
    missing_universe = tmp_path / "missing-universe.json"
    missing_bars = tmp_path / "missing-bars.json"

    result = cli.backtest_main(
        ["--universe", str(missing_universe), "--bars", str(missing_bars), "--format", "json"]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out.count("\n") == 1
    payload = json.loads(captured.out)
    assert "reason" in payload
    assert captured.err == ""


def test_backtest_malformed_bars_fails_with_one_record(tmp_path, capsys) -> None:
    universe = tmp_path / "universe.json"
    universe.write_text('{"fixture_version":"v1","symbols":["ACME"]}', encoding="utf-8")
    bars = tmp_path / "bars.json"
    bars.write_text("not-json", encoding="utf-8")

    result = cli.backtest_main(["--universe", str(universe), "--bars", str(bars), "--format", "json"])

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out) == {"reason": "fixture-invalid"}
    assert captured.err == ""


def test_backtest_live_range_infra_failure_prints_one_record_and_exits_two(monkeypatch, capsys) -> None:
    from invest.adapters.alpaca_market_data import MarketDataFetchError

    class FailingReader:
        def __init__(self, **kwargs) -> None:
            pass

        def fetch_range(self, universe, start, end):
            raise MarketDataFetchError("auth-failure")

    monkeypatch.setattr(cli, "AlpacaMarketDataReader", FailingReader)

    result = cli.backtest_main(
        ["--universe", str(UNIVERSE), "--start", "2024-01-01", "--end", "2024-12-31", "--format", "json"]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out) == {"reason": "auth-failure"}
    assert captured.err == ""


def test_backtest_live_range_success_uses_fetch_range(monkeypatch, capsys) -> None:
    from invest.adapters.fixtures_json import JsonFixtureReader
    from invest.domain.models import FixtureInputs, Universe

    loaded_inputs = JsonFixtureReader().load(UNIVERSE, BARS)

    class FetchRangeReader:
        def __init__(self, **kwargs) -> None:
            pass

        def fetch_range(self, universe: Universe, start, end) -> FixtureInputs:
            return loaded_inputs

    monkeypatch.setattr(cli, "AlpacaMarketDataReader", FetchRangeReader)

    result = cli.backtest_main(
        ["--universe", str(UNIVERSE), "--start", "2024-01-01", "--end", "2024-12-31", "--format", "json"]
    )

    captured = capsys.readouterr()
    assert result == 0
    payload = json.loads(captured.out)
    assert payload["trade_count"] == 3
