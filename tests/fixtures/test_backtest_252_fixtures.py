import json
from pathlib import Path

import pytest

from invest.adapters.backtest_context_json import BacktestContextJsonReader
from invest.adapters.fixtures_json import JsonFixtureReader
from invest.application.backtest_run import BacktestRun
from invest.domain.market_context import MarketContextIncompleteError
from invest.domain.momentum_selection_scanner import MomentumSelectionScanner

BASE = Path("fixtures/backtest-252")
UNIVERSE = BASE / "universe.json"
BARS = BASE / "bars.json"
MARKET_CONTEXT = BASE / "market-context.json"

MINIMUM_HISTORY_DAYS = 253


def test_backtest_252_fixture_files_exist() -> None:
    assert UNIVERSE.is_file()
    assert BARS.is_file()
    assert MARKET_CONTEXT.is_file()


def test_backtest_252_every_symbol_has_at_least_253_bars() -> None:
    inputs = JsonFixtureReader().load(UNIVERSE, BARS)

    bars_per_symbol: dict[str, int] = {}
    for bar in inputs.bars:
        bars_per_symbol[bar.symbol] = bars_per_symbol.get(bar.symbol, 0) + 1

    assert set(bars_per_symbol) == set(inputs.universe.symbols)
    for symbol, count in bars_per_symbol.items():
        assert count >= MINIMUM_HISTORY_DAYS, f"{symbol} has only {count} bars"


def test_backtest_252_v2_span_partitions_warmup_and_complete_replay_window() -> None:
    inputs = JsonFixtureReader().load(UNIVERSE, BARS)
    market_context = BacktestContextJsonReader().load(MARKET_CONTEXT)
    payload = json.loads(MARKET_CONTEXT.read_text(encoding="utf-8"))

    dates = sorted({bar.date for bar in inputs.bars})
    span = market_context.generation_span
    warmup_dates = [day for day in dates if day < span.start]
    replay_dates = [day for day in dates if span.start <= day <= span.end]

    assert payload["schema_version"] == "market-context-v2"
    assert payload["generation_span"] == {
        "start": span.start.isoformat(),
        "end": span.end.isoformat(),
    }
    assert warmup_dates
    assert replay_dates
    market_context.require_complete(replay_dates, inputs.universe.symbols)
    with pytest.raises(MarketContextIncompleteError):
        market_context.status(inputs.universe.symbols[0], warmup_dates[-1])


def test_backtest_252_replay_emits_no_pre_span_events() -> None:
    inputs = JsonFixtureReader().load(UNIVERSE, BARS)
    market_context = BacktestContextJsonReader().load(MARKET_CONTEXT)
    span = market_context.generation_span
    replay_dates = sorted(
        {bar.date for bar in inputs.bars if span.start <= bar.date <= span.end}
    )
    split_date = replay_dates[len(replay_dates) // 2]
    runner = BacktestRun(
        market_context=market_context,
        scanner=MomentumSelectionScanner(),
    )

    decisions = runner.scan_decisions(inputs)
    result = runner.replay(inputs, split_date=split_date)

    assert decisions
    assert all(span.start <= decision.decision_date <= span.end for decision in decisions)
    event_dates = [trade.entry_date for trade in result.trades]
    event_dates += [trade.exit_date for trade in result.trades]
    event_dates += [entry.decision_date for entry in result.skipped_entries]
    event_dates += [entry.entry_date for entry in result.skipped_entries]
    event_dates += [outcome.date for outcome in result.context_outcomes]
    assert event_dates
    assert all(span.start <= day <= span.end for day in event_dates)
    assert result.equity_summary.trading_day_count == len(replay_dates)
