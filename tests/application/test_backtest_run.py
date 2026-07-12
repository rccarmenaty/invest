from datetime import date, timedelta
from decimal import Decimal

from invest.domain.models import DailyBar, FixtureInputs, Universe
from invest.domain.scanner import MomentumScanner


def _breakout_bars(symbol: str, start: date, extra_days: int = 0) -> list[DailyBar]:
    """20 flat bars (no signal) followed by one breakout bar that MomentumScanner accepts.

    History: open=10, high=10.40, low=9.60, close=10, vol=100 (ATR=0.80 per bar).
    Breakout (day 20): open=10, high=11.50, low=10, close=11.40, vol=250 -> accepted.
    compute_intent off this history yields entry=11.40, stop=10.60, take_profit=13.00, qty=1250.
    """
    bars = [
        DailyBar(symbol, start + timedelta(days=i), Decimal("10"), Decimal("10.40"), Decimal("9.60"), Decimal("10"), 100)
        for i in range(20)
    ]
    bars.append(
        DailyBar(symbol, start + timedelta(days=20), Decimal("10"), Decimal("11.50"), Decimal("10"), Decimal("11.40"), 250)
    )
    for i in range(extra_days):
        bars.append(
            DailyBar(
                symbol,
                start + timedelta(days=21 + i),
                Decimal("11.40"),
                Decimal("11.50"),
                Decimal("11.30"),
                Decimal("11.40"),
                100,
            )
        )
    return bars


class _RecordingScanner(MomentumScanner):
    def __init__(self) -> None:
        self.windows: list[tuple[DailyBar, ...]] = []

    def scan(self, universe, bars):  # type: ignore[override]
        self.windows.append(bars)
        return super().scan(universe, bars)


def test_mutating_future_bars_does_not_change_day_n_decision() -> None:
    from invest.application.backtest_run import BacktestRun

    start = date(2026, 1, 1)
    symbol = "ACME"
    bars = _breakout_bars(symbol, start, extra_days=3)
    universe = Universe("v1", (symbol,))
    day_n = start + timedelta(days=20)

    inputs_before = FixtureInputs(universe, tuple(bars))
    decisions_before = BacktestRun().scan_decisions(inputs_before)
    decision_n_before = next(d for d in decisions_before if d.decision_date == day_n)
    assert decision_n_before.accepted is True

    corrupted = list(bars)
    for index, bar in enumerate(corrupted):
        if bar.date > day_n:
            corrupted[index] = DailyBar(
                symbol, bar.date, Decimal("9999"), Decimal("10000"), Decimal("1"), Decimal("9999"), 999999
            )
    inputs_after = FixtureInputs(universe, tuple(corrupted))
    decisions_after = BacktestRun().scan_decisions(inputs_after)
    decision_n_after = next(d for d in decisions_after if d.decision_date == day_n)

    assert decision_n_after == decision_n_before


def test_each_day_window_contains_only_bars_dated_on_or_before_that_day() -> None:
    from invest.application.backtest_run import BacktestRun

    start = date(2026, 1, 1)
    symbol = "ACME"
    bars = _breakout_bars(symbol, start, extra_days=2)
    universe = Universe("v1", (symbol,))
    inputs = FixtureInputs(universe, tuple(bars))

    recorder = _RecordingScanner()
    BacktestRun(scanner=recorder).scan_decisions(inputs)

    dates = sorted({bar.date for bar in bars})
    assert len(recorder.windows) == len(dates)
    for window, d in zip(recorder.windows, dates):
        assert all(bar.date <= d for bar in window)
        assert max(bar.date for bar in window) == d


def test_entry_skipped_when_no_next_session_bar_exists() -> None:
    from invest.application.backtest_run import BacktestRun

    start = date(2026, 1, 1)
    symbol = "ACME"
    bars = _breakout_bars(symbol, start, extra_days=0)
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = BacktestRun().replay(inputs)

    assert trades == []


def test_trade_enters_at_day_n_plus_1_open() -> None:
    from invest.application.backtest_run import BacktestRun

    start = date(2026, 1, 1)
    symbol = "ACME"
    bars = _breakout_bars(symbol, start, extra_days=0)
    day_n1 = start + timedelta(days=21)
    bars.append(DailyBar(symbol, day_n1, Decimal("12.00"), Decimal("12.10"), Decimal("11.90"), Decimal("12.00"), 100))
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = BacktestRun().replay(inputs)

    assert len(trades) == 1
    trade = trades[0]
    assert trade.symbol == symbol
    assert trade.entry_date == day_n1
    assert trade.entry_price == Decimal("12.00")
    assert trade.qty == 1250


def test_take_profit_touch_exits_at_take_profit_price() -> None:
    from invest.application.backtest_run import BacktestRun

    start = date(2026, 1, 1)
    symbol = "WIN"
    bars = _breakout_bars(symbol, start)
    day1 = start + timedelta(days=21)
    day2 = start + timedelta(days=22)
    bars.append(DailyBar(symbol, day1, Decimal("11.50"), Decimal("11.60"), Decimal("11.40"), Decimal("11.50"), 100))
    bars.append(DailyBar(symbol, day2, Decimal("11.50"), Decimal("13.20"), Decimal("11.30"), Decimal("13.00"), 100))
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = BacktestRun().replay(inputs)

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == "take-profit"
    assert trade.exit_price == Decimal("13.00")
    assert trade.exit_date == day2


def test_stop_touch_exits_at_min_of_open_and_stop_gap_down_honored() -> None:
    from invest.application.backtest_run import BacktestRun

    start = date(2026, 1, 1)
    symbol = "LOSS"
    bars = _breakout_bars(symbol, start)
    day1 = start + timedelta(days=21)
    day2 = start + timedelta(days=22)
    bars.append(DailyBar(symbol, day1, Decimal("11.40"), Decimal("11.50"), Decimal("11.30"), Decimal("11.40"), 100))
    bars.append(DailyBar(symbol, day2, Decimal("11.00"), Decimal("11.20"), Decimal("10.50"), Decimal("10.60"), 100))
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = BacktestRun().replay(inputs)

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == "stop"
    assert trade.exit_price == Decimal("10.60")
    assert trade.exit_date == day2


def test_same_bar_stop_and_take_profit_tie_resolves_to_stop_wins() -> None:
    from invest.application.backtest_run import BacktestRun

    start = date(2026, 1, 1)
    symbol = "TIE"
    bars = _breakout_bars(symbol, start)
    day1 = start + timedelta(days=21)
    # low=10.00 touches stop(10.60); high=13.50 touches take_profit(13.00) on the SAME bar.
    bars.append(DailyBar(symbol, day1, Decimal("11.40"), Decimal("13.50"), Decimal("10.00"), Decimal("11.40"), 100))
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = BacktestRun().replay(inputs)

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == "stop"
    assert trade.exit_price == Decimal("10.60")  # min(open=11.40, stop=10.60) -- stop wins, never TP


def test_open_at_end_when_no_exit_trigger_before_data_ends() -> None:
    from invest.application.backtest_run import BacktestRun

    start = date(2026, 1, 1)
    symbol = "OPENEND"
    bars = _breakout_bars(symbol, start)
    day1 = start + timedelta(days=21)
    bars.append(DailyBar(symbol, day1, Decimal("11.40"), Decimal("11.50"), Decimal("11.30"), Decimal("11.45"), 100))
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = BacktestRun().replay(inputs)

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == "open-at-end"
    assert trade.exit_price == Decimal("11.45")
    assert trade.exit_date == day1


def test_replaying_same_range_twice_is_byte_identical() -> None:
    from invest.application.backtest_run import BacktestRun

    start = date(2026, 1, 1)
    symbol = "ACME"
    bars = _breakout_bars(symbol, start, extra_days=3)
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    first = BacktestRun().replay(inputs)
    second = BacktestRun().replay(inputs)

    assert first == second
