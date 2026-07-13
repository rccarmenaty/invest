import json
from pathlib import Path

import pytest

from invest.adapters import cli


UNIVERSE = Path("fixtures/backtest/universe.json")
BARS = Path("fixtures/backtest/bars.json")
MARKET_CONTEXT = Path("fixtures/backtest/market-context.json")

DAY0_DISCLAIMER = (
    "DAY-0 MECHANICS ONLY: measures current day-0 paper-trading entry mechanics, "
    "NOT SPEC §2.4 confirmed-entry edge."
)
COST_MODEL_DISCLAIMER = (
    "COST MODEL IS AN APPROXIMATION: fixed-bps slippage + zero commission + flat tax "
    "haircut, not precision accounting."
)


def _backtest_args(*extra: str) -> list[str]:
    return [
        "--universe",
        str(UNIVERSE),
        "--bars",
        str(BARS),
        "--market-context",
        str(MARKET_CONTEXT),
        *extra,
    ]


def test_backtest_bars_run_prints_one_report_with_metrics_and_disclaimers_and_touches_no_broker(
    capsys, monkeypatch
) -> None:
    monkeypatch.setattr(
        cli, "AlpacaBroker", lambda *a, **k: pytest.fail("BrokerPort must never be constructed")
    )

    result = cli.backtest_main(_backtest_args("--split-date", "2024-01-23", "--format", "json"))

    captured = capsys.readouterr()
    assert result == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["disclaimers"]["day0"] == DAY0_DISCLAIMER
    assert payload["disclaimers"]["cost_model"] == COST_MODEL_DISCLAIMER
    assert payload["disclaimers"]["point_in_time_market_context"].startswith(
        "POINT-IN-TIME CONTEXT VALIDATED"
    )
    assert "survivorship" not in payload["disclaimers"]
    assert "static_universe_oos" not in payload["disclaimers"]


def test_backtest_report_has_exact_top_level_snake_case_metric_keys(capsys) -> None:
    result = cli.backtest_main(_backtest_args("--split-date", "2024-01-23", "--format", "json"))

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert {"hit_rate", "expectancy", "max_drawdown", "trade_count", "net_pnl"} <= payload.keys()
    assert payload["trade_count"] == 1


def test_backtest_missing_fixture_prints_exactly_one_record_and_exits_two(tmp_path, capsys) -> None:
    missing_universe = tmp_path / "missing-universe.json"
    missing_bars = tmp_path / "missing-bars.json"

    result = cli.backtest_main(
        [
            "--universe",
            str(missing_universe),
            "--bars",
            str(missing_bars),
            "--market-context",
            str(MARKET_CONTEXT),
            "--format",
            "json",
        ]
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

    result = cli.backtest_main(
        [
            "--universe",
            str(universe),
            "--bars",
            str(bars),
            "--market-context",
            str(MARKET_CONTEXT),
            "--format",
            "json",
        ]
    )

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
        [
            "--universe",
            str(UNIVERSE),
            "--start",
            "2024-01-01",
            "--end",
            "2024-12-31",
            "--market-context",
            str(MARKET_CONTEXT),
            "--split-date",
            "2024-01-23",
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out) == {"reason": "auth-failure"}
    assert captured.err == ""


def test_backtest_live_range_missing_symbol_bars_fails_closed_with_one_record(monkeypatch, capsys) -> None:
    """A universe symbol that Alpaca silently omits (delisted, feed gap, partial upstream
    omission) must never be silently dropped from the report: fail closed instead of
    printing a complete-looking report that omitted a symbol without a trace."""
    from datetime import date as date_cls
    from decimal import Decimal

    from invest.domain.models import DailyBar, FixtureInputs, Universe

    universe = Universe(fixture_version="v1", symbols=("WIN", "LOSS"))
    bars = (
        DailyBar(
            symbol="WIN",
            date=date_cls(2024, 1, 2),
            open=Decimal("10"),
            high=Decimal("10.40"),
            low=Decimal("9.60"),
            close=Decimal("10"),
            volume=100,
        ),
    )
    incomplete_inputs = FixtureInputs(universe=universe, bars=bars)

    class MissingSymbolReader:
        def __init__(self, **kwargs) -> None:
            pass

        def fetch_range(self, universe, start, end) -> FixtureInputs:
            return incomplete_inputs

    monkeypatch.setattr(cli, "AlpacaMarketDataReader", MissingSymbolReader)

    result = cli.backtest_main(
        [
            "--universe",
            str(UNIVERSE),
            "--start",
            "2024-01-01",
            "--end",
            "2024-12-31",
            "--market-context",
            str(MARKET_CONTEXT),
            "--split-date",
            "2024-01-23",
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out.count("\n") == 1
    payload = json.loads(captured.out)
    assert payload["reason"] == "symbol-missing-at-fetch"
    assert "LOSS" in payload.get("message", "")
    assert "trade_count" not in payload
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
        [
            "--universe",
            str(UNIVERSE),
            "--start",
            "2024-01-01",
            "--end",
            "2024-12-31",
            "--market-context",
            str(MARKET_CONTEXT),
            "--split-date",
            "2024-01-23",
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    payload = json.loads(captured.out)
    assert payload["trade_count"] == 1


def test_backtest_requires_market_context_as_one_json_error(capsys) -> None:
    result = cli.backtest_main(["--universe", str(UNIVERSE), "--bars", str(BARS), "--format", "json"])

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out) == {"reason": "market-context-missing"}
    assert captured.err == ""


def test_backtest_requires_valid_in_range_split_date_as_one_json_error(capsys) -> None:
    result = cli.backtest_main(_backtest_args("--format", "json"))

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out) == {"reason": "split-date-invalid"}
    assert captured.err == ""


@pytest.mark.parametrize("split_date", ["not-a-date", "2023-12-31", "2025-01-01"])
def test_backtest_rejects_malformed_or_out_of_range_split_date(split_date, capsys) -> None:
    result = cli.backtest_main(_backtest_args("--split-date", split_date, "--format", "json"))

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out) == {"reason": "split-date-invalid"}
    assert captured.err == ""


def test_backtest_report_exposes_portfolio_contract_and_all_limitations(capsys, monkeypatch) -> None:
    monkeypatch.setattr(cli, "AlpacaBroker", lambda *a, **k: pytest.fail("BrokerPort must never be constructed"))

    result = cli.backtest_main(_backtest_args("--split-date", "2024-01-23", "--format", "json"))

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert {"portfolio", "gates", "equity", "segments", "warnings", "context_outcomes"} <= payload.keys()
    assert set(payload["segments"]) == {"is", "oos"}
    assert set(payload["disclaimers"]) == {
        "day0",
        "cost_model",
        "portfolio_gates",
        "point_in_time_market_context",
        "execution_realism",
    }
    assert payload["context_outcomes"] == []
    assert set(payload["warnings"]) == {
        "portfolio-gates-simulated",
        "point-in-time-market-context-validated",
        "broker-execution-realism-out-of-scope",
    }


def test_backtest_invalid_market_context_prints_one_context_error_and_no_partial_report(tmp_path, capsys) -> None:
    invalid_context = tmp_path / "market-context.json"
    invalid_context.write_text("not-json", encoding="utf-8")

    result = cli.backtest_main(
        [
            "--universe",
            str(UNIVERSE),
            "--bars",
            str(BARS),
            "--market-context",
            str(invalid_context),
            "--split-date",
            "2024-01-23",
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 2
    assert payload == {"reason": "market-context-invalid"}


def test_backtest_incomplete_market_context_prints_one_context_error_and_no_partial_report(
    tmp_path, capsys
) -> None:
    incomplete_context = tmp_path / "market-context.json"
    incomplete_context.write_text(
        json.dumps(
            {
                "schema_version": "market-context-v1",
                "symbols": [
                    {
                        "symbol": "WIN",
                        "coverage": [{"start": "2024-01-02", "end": "2024-01-24"}],
                        "eligibility": [{"start": "2024-01-02", "end": "2024-01-24", "eligible": True}],
                        "blockers": [],
                    },
                    {
                        "symbol": "LOSS",
                        "coverage": [{"start": "2024-01-02", "end": "2024-01-24"}],
                        "eligibility": [{"start": "2024-01-02", "end": "2024-01-24", "eligible": True}],
                        "blockers": [],
                    },
                    {
                        "symbol": "OPENEND",
                        "coverage": [{"start": "2024-01-02", "end": "2024-01-23"}],
                        "eligibility": [{"start": "2024-01-02", "end": "2024-01-22", "eligible": True}],
                        "blockers": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    result = cli.backtest_main(
        [
            "--universe",
            str(UNIVERSE),
            "--bars",
            str(BARS),
            "--market-context",
            str(incomplete_context),
            "--split-date",
            "2024-01-23",
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 2
    assert payload == {"reason": "market-context-incomplete"}


@pytest.mark.parametrize(
    "option,value",
    [
        ("--slippage-bps", "-1"),
        ("--slippage-bps", "10000.01"),
        ("--slippage-bps", "NaN"),
        ("--tax-rate", "-0.01"),
        ("--tax-rate", "1.01"),
        ("--tax-rate", "Infinity"),
    ],
)
def test_backtest_rejects_invalid_cost_model_values_with_one_json_error(capsys, option, value) -> None:
    result = cli.backtest_main(
        _backtest_args("--split-date", "2024-01-23", option, value)
    )

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out) == {"reason": "cost-model-invalid"}
    assert captured.err == ""
