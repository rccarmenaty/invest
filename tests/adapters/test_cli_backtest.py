import json
import sys
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

from invest.adapters import cli


UNIVERSE = Path("fixtures/backtest/universe.json")
BARS = Path("fixtures/backtest/bars.json")
MARKET_CONTEXT = Path("fixtures/backtest/market-context.json")

UNIVERSE_252 = Path("fixtures/backtest-252/universe.json")
BARS_252 = Path("fixtures/backtest-252/bars.json")
MARKET_CONTEXT_252 = Path("fixtures/backtest-252/market-context.json")

DAY0_DISCLAIMER = (
    "DAY-0 MECHANICS ONLY: measures current day-0 paper-trading entry mechanics, "
    "NOT SPEC §2.4 confirmed-entry edge."
)
COST_MODEL_DISCLAIMER = (
    "COST MODEL IS AN APPROXIMATION: fixed-bps slippage + zero commission + flat tax "
    "haircut, not precision accounting."
)


class _FakeSharadarModule(ModuleType):
    SharadarMarketDataReader: type[object]


def _backtest_args(*extra: str) -> list[str]:
    return [
        "--universe",
        str(UNIVERSE),
        "--bars",
        str(BARS),
        "--market-context",
        str(MARKET_CONTEXT),
        "--end",
        "2024-01-23",
        *extra,
    ]


def _context_with_span(tmp_path: Path, start: str, end: str) -> Path:
    payload = json.loads(MARKET_CONTEXT.read_text(encoding="utf-8"))
    payload["schema_version"] = "market-context-v2"
    payload["generation_span"] = {"start": start, "end": end}
    path = tmp_path / f"market-context-{start}-{end}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


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


def test_backtest_progress_is_structured_stderr_and_keeps_stdout_json_clean(
    capsys, monkeypatch
) -> None:
    ticks = iter(float(value) for value in range(1000))
    monkeypatch.setattr(cli, "monotonic", lambda: next(ticks))

    result = cli.backtest_main(
        _backtest_args("--split-date", "2024-01-23", "--format", "json", "--progress")
    )

    captured = capsys.readouterr()
    report = json.loads(captured.out)
    progress = [json.loads(line) for line in captured.err.splitlines()]
    assert result == 0
    assert captured.out.count("\n") == 1
    assert "trade_count" in report
    assert progress
    assert [event["processed_replay_days"] for event in progress] == sorted(
        event["processed_replay_days"] for event in progress
    )
    assert [event["accepted_decisions"] for event in progress] == sorted(
        event["accepted_decisions"] for event in progress
    )
    assert progress[-1]["event"] == "backtest-progress"
    assert progress[-1]["phase"] == "scan"
    assert progress[-1]["processed_replay_days"] == progress[-1]["total_replay_days"]
    assert progress[-1]["percent"] == 100
    assert progress[-1]["ingested_bars"] > 0
    assert progress[-1]["elapsed_seconds"] >= 0
    assert progress[-1]["eta_seconds"] == 0


def test_backtest_fixture_passes_date_window_to_streaming_reader(capsys, monkeypatch) -> None:
    reader_type = cli.JsonFixtureReader
    calls: list[tuple[date | None, date | None, int]] = []

    class RecordingReader:
        def load(self, universe_path, bars_path, *, start=None, end=None, warmup_bars=0):
            calls.append((start, end, warmup_bars))
            return reader_type().load(
                universe_path,
                bars_path,
                start=start,
                end=end,
                warmup_bars=warmup_bars,
            )

    monkeypatch.setattr(cli, "JsonFixtureReader", RecordingReader)

    result = cli.backtest_main(
        _backtest_args(
            "--start",
            "2024-01-02",
            "--end",
            "2024-01-23",
            "--split-date",
            "2024-01-23",
        )
    )

    assert result == 0
    assert calls == [(date(2024, 1, 2), date(2024, 1, 23), 20)]
    assert json.loads(capsys.readouterr().out)["trade_count"] == 3


def test_core_fixture_requests_252_pre_start_warmup_bars(capsys, monkeypatch) -> None:
    reader_type = cli.JsonFixtureReader
    requested_warmup: list[int] = []

    class RecordingReader:
        def load(self, universe_path, bars_path, **kwargs):
            requested_warmup.append(kwargs["warmup_bars"])
            return reader_type().load(universe_path, bars_path, **kwargs)

    monkeypatch.setattr(cli, "JsonFixtureReader", RecordingReader)

    result = cli.backtest_main(
        _backtest_args(
            "--strategy",
            "core",
            "--start",
            "2024-01-02",
            "--end",
            "2024-01-24",
            "--split-date",
            "2024-01-23",
        )
    )

    assert result == 0
    assert requested_warmup == [252]
    json.loads(capsys.readouterr().out)


def test_backtest_report_has_exact_top_level_snake_case_metric_keys(capsys) -> None:
    result = cli.backtest_main(_backtest_args("--split-date", "2024-01-23", "--format", "json"))

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert {"hit_rate", "expectancy", "max_drawdown", "trade_count", "net_pnl"} <= payload.keys()
    # 0.35%-risk/ATR20 sizing produces much smaller positions than the old 1%/ATR14
    # model, so all 3 candidates now fit under the 25% max-equity-deployed cap.
    assert payload["trade_count"] == 3


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


def test_backtest_live_range_infra_failure_prints_one_record_and_exits_two(
    monkeypatch, capsys
) -> None:
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
            "2024-01-02",
            "--end",
            "2024-01-24",
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


def test_backtest_live_range_missing_symbol_bars_fails_closed_with_one_record(
    monkeypatch, capsys
) -> None:
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
            "2024-01-02",
            "--end",
            "2024-01-24",
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

    loaded_inputs = JsonFixtureReader().load(UNIVERSE, BARS, end=date(2024, 1, 23))

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
            "2024-01-02",
            "--end",
            "2024-01-24",
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
    # 0.35%-risk/ATR20 sizing produces much smaller positions than the old 1%/ATR14
    # model, so all 3 candidates now fit under the 25% max-equity-deployed cap.
    assert payload["trade_count"] == 3


def test_backtest_explicit_sharadar_source_fetches_the_requested_range(monkeypatch, capsys) -> None:
    from invest.adapters.fixtures_json import JsonFixtureReader

    loaded_inputs = JsonFixtureReader().load(UNIVERSE, BARS, end=date(2024, 1, 23))
    fetch_calls: list[tuple[tuple[str, ...], date, date]] = []

    class FakeSharadarReader:
        def fetch_range(self, universe, start: date, end: date):
            fetch_calls.append((universe.symbols, start, end))
            return loaded_inputs

    module = _FakeSharadarModule("invest.adapters.sharadar_market_data")
    module.SharadarMarketDataReader = FakeSharadarReader
    monkeypatch.setitem(sys.modules, module.__name__, module)

    result = cli.backtest_main(
        [
            "--universe",
            str(UNIVERSE),
            "--source",
            "sharadar",
            "--start",
            "2024-01-02",
            "--end",
            "2024-01-24",
            "--market-context",
            str(MARKET_CONTEXT),
            "--split-date",
            "2024-01-23",
        ]
    )

    assert result == 0
    # 0.35%-risk/ATR20 sizing produces much smaller positions than the old 1%/ATR14
    # model, so all 3 candidates now fit under the 25% max-equity-deployed cap.
    assert json.loads(capsys.readouterr().out)["trade_count"] == 3
    assert fetch_calls == [(loaded_inputs.universe.symbols, date(2024, 1, 2), date(2024, 1, 24))]


def test_backtest_default_fixture_source_is_byte_identical_to_explicit_fixture(capsys) -> None:
    default_result = cli.backtest_main(_backtest_args("--split-date", "2024-01-23"))
    default_output = capsys.readouterr().out

    explicit_result = cli.backtest_main(
        _backtest_args("--split-date", "2024-01-23", "--source", "fixture")
    )
    explicit_output = capsys.readouterr().out

    assert default_result == explicit_result == 0
    assert default_output == explicit_output


def test_backtest_default_alpaca_source_is_byte_identical_to_explicit_alpaca(
    monkeypatch, capsys
) -> None:
    from invest.adapters.fixtures_json import JsonFixtureReader

    loaded_inputs = JsonFixtureReader().load(UNIVERSE, BARS, end=date(2024, 1, 23))

    class FakeAlpacaReader:
        def fetch_range(self, universe, start: date, end: date):
            return loaded_inputs

    monkeypatch.setattr(cli, "AlpacaMarketDataReader", FakeAlpacaReader)
    range_args = [
        "--universe",
        str(UNIVERSE),
        "--start",
        "2024-01-02",
        "--end",
        "2024-01-24",
        "--market-context",
        str(MARKET_CONTEXT),
        "--split-date",
        "2024-01-23",
    ]

    default_result = cli.backtest_main(range_args)
    default_output = capsys.readouterr().out
    explicit_result = cli.backtest_main([*range_args, "--source", "alpaca"])
    explicit_output = capsys.readouterr().out

    assert default_result == explicit_result == 0
    assert default_output == explicit_output


def test_backtest_invalid_source_fails_before_constructing_any_reader(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "BacktestContextJsonReader",
        lambda: pytest.fail("invalid source must stop before reader construction"),
    )

    result = cli.backtest_main(_backtest_args("--source", "unknown"))

    assert result == 2
    assert json.loads(capsys.readouterr().out) == {"reason": "source-invalid"}


def test_backtest_explicit_empty_source_fails_closed(capsys) -> None:
    result = cli.backtest_main(_backtest_args("--source", ""))

    assert result == 2
    assert json.loads(capsys.readouterr().out) == {"reason": "source-invalid"}


def test_backtest_fixture_source_without_bars_returns_invalid_input(capsys) -> None:
    result = cli.backtest_main(
        [
            "--universe",
            str(UNIVERSE),
            "--source",
            "fixture",
            "--market-context",
            str(MARKET_CONTEXT),
        ]
    )

    assert result == 2
    assert json.loads(capsys.readouterr().out) == {"reason": "fixture-invalid"}


def test_backtest_requires_market_context_as_one_json_error(capsys) -> None:
    result = cli.backtest_main(
        ["--universe", str(UNIVERSE), "--bars", str(BARS), "--format", "json"]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out) == {"reason": "market-context-missing"}
    assert captured.err == ""


def test_backtest_missing_context_takes_precedence_over_invalid_cost_model(capsys) -> None:
    result = cli.backtest_main(
        [
            "--universe",
            str(UNIVERSE),
            "--bars",
            str(BARS),
            "--tax-rate",
            "Infinity",
            "--format",
            "json",
        ]
    )

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


def test_backtest_accepts_exact_observed_in_span_split_date(tmp_path, capsys) -> None:
    context = _context_with_span(tmp_path, "2024-01-10", "2024-01-24")

    result = cli.backtest_main(
        [
            "--universe",
            str(UNIVERSE),
            "--bars",
            str(BARS),
            "--market-context",
            str(context),
            "--end",
            "2024-01-23",
            "--split-date",
            "2024-01-23",
        ]
    )

    assert result == 0
    assert "trade_count" in json.loads(capsys.readouterr().out)


def test_backtest_rejects_warmup_split_date_with_replay_window_record(tmp_path, capsys) -> None:
    context = _context_with_span(tmp_path, "2024-01-10", "2024-01-24")

    result = cli.backtest_main(
        [
            "--universe",
            str(UNIVERSE),
            "--bars",
            str(BARS),
            "--market-context",
            str(context),
            "--split-date",
            "2024-01-02",
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out) == {"reason": "replay-window-invalid"}


def test_backtest_rejects_unobserved_in_span_split_date(tmp_path, capsys) -> None:
    bars_payload = json.loads(BARS.read_text(encoding="utf-8"))
    bars_payload["bars"] = [bar for bar in bars_payload["bars"] if bar["date"] != "2024-01-10"]
    bars = tmp_path / "bars.json"
    bars.write_text(json.dumps(bars_payload), encoding="utf-8")
    context = _context_with_span(tmp_path, "2024-01-02", "2024-01-24")

    result = cli.backtest_main(
        [
            "--universe",
            str(UNIVERSE),
            "--bars",
            str(bars),
            "--market-context",
            str(context),
            "--split-date",
            "2024-01-10",
        ]
    )

    assert result == 2
    assert json.loads(capsys.readouterr().out) == {"reason": "replay-window-invalid"}


def test_backtest_rejects_post_span_bar_with_one_replay_window_record(tmp_path, capsys) -> None:
    context = _context_with_span(tmp_path, "2024-01-02", "2024-01-23")

    result = cli.backtest_main(
        [
            "--universe",
            str(UNIVERSE),
            "--bars",
            str(BARS),
            "--market-context",
            str(context),
            "--split-date",
            "2024-01-23",
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out) == {"reason": "replay-window-invalid"}


def test_backtest_live_range_must_exactly_match_declared_span(tmp_path, monkeypatch, capsys) -> None:
    context = _context_with_span(tmp_path, "2024-01-02", "2024-01-24")

    class UnexpectedReader:
        def __init__(self, **kwargs) -> None:
            pytest.fail("range mismatch must fail before fetching bars")

    monkeypatch.setattr(cli, "AlpacaMarketDataReader", UnexpectedReader)
    result = cli.backtest_main(
        [
            "--universe",
            str(UNIVERSE),
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-24",
            "--market-context",
            str(context),
            "--split-date",
            "2024-01-23",
        ]
    )

    assert result == 2
    assert json.loads(capsys.readouterr().out) == {"reason": "replay-window-invalid"}


@pytest.mark.parametrize(
    "split_date,reason",
    [
        ("not-a-date", "split-date-invalid"),
        ("2023-12-31", "replay-window-invalid"),
        ("2025-01-01", "replay-window-invalid"),
    ],
)
def test_backtest_rejects_malformed_or_out_of_range_split_date(
    split_date, reason, capsys
) -> None:
    result = cli.backtest_main(_backtest_args("--split-date", split_date, "--format", "json"))

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out) == {"reason": reason}
    assert captured.err == ""


def test_backtest_report_exposes_portfolio_contract_and_all_limitations(
    capsys, monkeypatch
) -> None:
    monkeypatch.setattr(
        cli, "AlpacaBroker", lambda *a, **k: pytest.fail("BrokerPort must never be constructed")
    )

    result = cli.backtest_main(_backtest_args("--split-date", "2024-01-23", "--format", "json"))

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert {
        "portfolio",
        "gates",
        "equity",
        "segments",
        "warnings",
        "context_outcomes",
    } <= payload.keys()
    assert set(payload["segments"]) == {"is", "oos"}
    assert set(payload["disclaimers"]) == {
        "day0",
        "cost_model",
        "portfolio_gates",
        "point_in_time_market_context",
        "execution_realism",
    }
    assert payload["context_outcomes"] == []
    # The bounded CLI fixture ends on the last common trustworthy session.
    assert set(payload["warnings"]) == {
        "portfolio-gates-simulated",
        "point-in-time-market-context-validated",
        "broker-execution-realism-out-of-scope",
    }


def test_backtest_report_serializes_non_empty_context_outcomes(tmp_path, capsys) -> None:
    context_payload = json.loads(MARKET_CONTEXT.read_text(encoding="utf-8"))
    win_context = next(
        symbol_context
        for symbol_context in context_payload["symbols"]
        if symbol_context["symbol"] == "WIN"
    )
    win_context["blockers"] = [
        {
            "start": "2024-01-23",
            "end": "2024-01-23",
            "reason": "corporate-action",
        }
    ]
    market_context = tmp_path / "market-context.json"
    market_context.write_text(json.dumps(context_payload), encoding="utf-8")

    result = cli.backtest_main(
        [
            "--universe",
            str(UNIVERSE),
            "--bars",
            str(BARS),
            "--market-context",
            str(market_context),
            "--end",
            "2024-01-23",
            "--split-date",
            "2024-01-23",
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["context_outcomes"] == [
        {
            "type": "context-entry-blocked",
            "reason": "corporate-action",
            "symbol": "WIN",
            "date": "2024-01-23",
        }
    ]


def test_backtest_invalid_market_context_prints_one_context_error_and_no_partial_report(
    tmp_path, capsys
) -> None:
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


def test_backtest_invalid_context_takes_precedence_over_invalid_cost_model(
    tmp_path, capsys
) -> None:
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
            "--slippage-bps",
            "NaN",
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out) == {"reason": "market-context-invalid"}
    assert captured.err == ""


def test_backtest_incomplete_market_context_prints_one_context_error_and_no_partial_report(
    tmp_path, capsys
) -> None:
    incomplete_context = tmp_path / "market-context.json"
    incomplete_context.write_text(
        json.dumps(
            {
                "schema_version": "market-context-v2",
                "generation_span": {"start": "2024-01-02", "end": "2024-01-24"},
                "symbols": [
                    {
                        "symbol": "WIN",
                        "coverage": [{"start": "2024-01-02", "end": "2024-01-24"}],
                        "eligibility": [
                            {"start": "2024-01-02", "end": "2024-01-24", "eligible": True}
                        ],
                        "blockers": [],
                    },
                    {
                        "symbol": "LOSS",
                        "coverage": [{"start": "2024-01-02", "end": "2024-01-24"}],
                        "eligibility": [
                            {"start": "2024-01-02", "end": "2024-01-24", "eligible": True}
                        ],
                        "blockers": [],
                    },
                    {
                        "symbol": "OPENEND",
                        "coverage": [{"start": "2024-01-02", "end": "2024-01-23"}],
                        "eligibility": [
                            {"start": "2024-01-02", "end": "2024-01-22", "eligible": True}
                        ],
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
def test_backtest_rejects_invalid_cost_model_values_with_one_json_error(
    capsys, option, value
) -> None:
    result = cli.backtest_main(_backtest_args("--split-date", "2024-01-23", option, value))

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out) == {"reason": "cost-model-invalid"}
    assert captured.err == ""


def test_backtest_strategy_core_replays_through_the_same_harness(capsys) -> None:
    result = cli.backtest_main(
        [
            "--universe",
            str(UNIVERSE_252),
            "--bars",
            str(BARS_252),
            "--market-context",
            str(MARKET_CONTEXT_252),
            "--split-date",
            "2020-09-12",
            "--strategy",
            "core",
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert {
        "hit_rate",
        "expectancy",
        "max_drawdown",
        "trade_count",
        "net_pnl",
        "trades",
        "skipped_entries",
        "gates",
    } <= payload.keys()
    # MOMLONG is the sole momentum-rank/proximity/trend/breakout survivor in this
    # fixture set (see fixtures/backtest-252): the Core scanner must have actually
    # identified and attempted to size it -- proving --strategy core really ran
    # the Core scanner through the harness, not silently defaulting to benchmark.
    assert payload["gates"]["counts"].get("max-equity-deployed") == 7
    assert {entry["symbol"] for entry in payload["skipped_entries"]} == {"MOMLONG"}


def test_backtest_default_and_explicit_benchmark_strategy_are_byte_identical(capsys) -> None:
    default_result = cli.backtest_main(
        _backtest_args("--split-date", "2024-01-23", "--format", "json")
    )
    default_output = capsys.readouterr().out

    explicit_result = cli.backtest_main(
        _backtest_args("--split-date", "2024-01-23", "--format", "json", "--strategy", "benchmark")
    )
    explicit_output = capsys.readouterr().out

    assert default_result == 0
    assert explicit_result == 0
    assert default_output == explicit_output


def test_backtest_rejects_unknown_strategy_value_with_one_json_error_before_any_replay(
    capsys,
) -> None:
    result = cli.backtest_main(
        _backtest_args("--split-date", "2024-01-23", "--format", "json", "--strategy", "bogus")
    )

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out) == {"reason": "strategy-invalid"}
    assert captured.err == ""


def test_backtest_exit_policy_flag_defaults_to_ten_day_low_and_is_in_report(capsys) -> None:
    result = cli.backtest_main(_backtest_args("--split-date", "2024-01-23", "--format", "json"))

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert "exit_policy" in payload
    assert payload["exit_policy"]["kind"] == "ten-day-low"
    assert list(payload["exit_policy"].keys()) == sorted(payload["exit_policy"].keys())
    assert payload["exit_policy"]["channel_window"] == 10
    assert payload["exit_policy"]["atr_mult"] == "3"


def test_backtest_exit_policy_atr_variant_recorded_in_report_metadata(capsys) -> None:
    result = cli.backtest_main(
        _backtest_args(
            "--split-date",
            "2024-01-23",
            "--format",
            "json",
            "--exit-policy",
            "atr-3-high-water",
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 0
    assert payload["exit_policy"]["kind"] == "atr-3-high-water"
    assert list(payload["exit_policy"].keys()) == sorted(payload["exit_policy"].keys())


def test_backtest_exit_policy_default_and_explicit_ten_day_low_are_byte_identical(capsys) -> None:
    default_result = cli.backtest_main(
        _backtest_args("--split-date", "2024-01-23", "--format", "json")
    )
    default_output = capsys.readouterr().out

    explicit_result = cli.backtest_main(
        _backtest_args(
            "--split-date",
            "2024-01-23",
            "--format",
            "json",
            "--exit-policy",
            "ten-day-low",
        )
    )
    explicit_output = capsys.readouterr().out

    assert default_result == 0
    assert explicit_result == 0
    assert default_output == explicit_output


def test_backtest_parser_accepts_exit_policy_choices() -> None:
    options = {action.dest: action for action in cli._backtest_parser()._actions}
    assert "exit_policy" in options
    assert set(options["exit_policy"].choices) == {
        "ten-day-low",
        "atr-3-high-water",
        "fixed-horizon",
    }
