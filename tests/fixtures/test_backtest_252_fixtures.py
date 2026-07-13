from pathlib import Path

from invest.adapters.backtest_context_json import BacktestContextJsonReader
from invest.adapters.fixtures_json import JsonFixtureReader

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


def test_backtest_252_market_context_is_complete_for_the_full_window() -> None:
    inputs = JsonFixtureReader().load(UNIVERSE, BARS)
    market_context = BacktestContextJsonReader().load(MARKET_CONTEXT)

    dates = sorted({bar.date for bar in inputs.bars})

    # Must not raise MarketContextIncompleteError/MarketContextInvalidError: fails
    # closed on any coverage/eligibility drift across the full replay window.
    market_context.require_complete(dates, inputs.universe.symbols)
