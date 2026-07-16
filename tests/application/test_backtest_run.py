from datetime import date, timedelta
from decimal import Decimal

import pytest

from invest.domain.market_context import (
    BlockerWindow,
    ContextOutcome,
    ContextOutcomeType,
    ContextReason,
    CoverageWindow,
    EligibilityWindow,
    MarketContext,
    MarketContextIncompleteError,
    SymbolContext,
)
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
        self.universes: list[tuple[date, tuple[str, ...]]] = []

    def scan(self, universe, bars):  # type: ignore[override]
        self.windows.append(bars)
        if bars:
            self.universes.append((max(bar.date for bar in bars), universe.symbols))
        return super().scan(universe, bars)


def _context_for_inputs(
    inputs: FixtureInputs,
    *,
    eligibility_by_symbol: dict[str, tuple[EligibilityWindow, ...]] | None = None,
    blockers_by_symbol: dict[str, tuple[BlockerWindow, ...]] | None = None,
) -> MarketContext:
    replay_dates = sorted({bar.date for bar in inputs.bars})
    start = replay_dates[0]
    end = replay_dates[-1]
    return MarketContext(
        {
            symbol: SymbolContext(
                coverage=(CoverageWindow(start, end),),
                eligibility=(eligibility_by_symbol or {}).get(
                    symbol, (EligibilityWindow(start, end, eligible=True),)
                ),
                blockers=(blockers_by_symbol or {}).get(symbol, ()),
            )
            for symbol in inputs.universe.symbols
        }
    )


def _runner(inputs: FixtureInputs, **kwargs):
    from invest.application.backtest_run import BacktestRun

    market_context = kwargs.pop("market_context", _context_for_inputs(inputs))
    return BacktestRun(market_context=market_context, **kwargs)


def test_mutating_future_bars_does_not_change_day_n_decision() -> None:
    start = date(2026, 1, 1)
    symbol = "ACME"
    bars = _breakout_bars(symbol, start, extra_days=3)
    universe = Universe("v1", (symbol,))
    day_n = start + timedelta(days=20)

    inputs_before = FixtureInputs(universe, tuple(bars))
    decisions_before = _runner(inputs_before).scan_decisions(inputs_before)
    decision_n_before = next(d for d in decisions_before if d.decision_date == day_n)
    assert decision_n_before.accepted is True

    corrupted = list(bars)
    for index, bar in enumerate(corrupted):
        if bar.date > day_n:
            corrupted[index] = DailyBar(
                symbol, bar.date, Decimal("9999"), Decimal("10000"), Decimal("1"), Decimal("9999"), 999999
            )
    inputs_after = FixtureInputs(universe, tuple(corrupted))
    decisions_after = _runner(inputs_after).scan_decisions(inputs_after)
    decision_n_after = next(d for d in decisions_after if d.decision_date == day_n)

    assert decision_n_after == decision_n_before


def test_each_day_window_contains_only_bars_dated_on_or_before_that_day() -> None:
    start = date(2026, 1, 1)
    symbol = "ACME"
    bars = _breakout_bars(symbol, start, extra_days=2)
    universe = Universe("v1", (symbol,))
    inputs = FixtureInputs(universe, tuple(bars))

    recorder = _RecordingScanner()
    _runner(inputs, scanner=recorder).scan_decisions(inputs)

    dates = sorted({bar.date for bar in bars})
    assert len(recorder.windows) == len(dates)
    for window, d in zip(recorder.windows, dates):
        assert all(bar.date <= d for bar in window)
        assert max(bar.date for bar in window) == d


def test_scan_filters_universe_by_date_effective_eligibility() -> None:
    start = date(2026, 1, 1)
    bars = _breakout_bars("ACME", start, extra_days=1) + _breakout_bars("LATE", start, extra_days=1)
    inputs = FixtureInputs(Universe("v1", ("ACME", "LATE")), tuple(bars))
    recorder = _RecordingScanner()
    context = _context_for_inputs(
        inputs,
        eligibility_by_symbol={
            "LATE": (
                EligibilityWindow(start, start + timedelta(days=20), eligible=False),
                EligibilityWindow(start + timedelta(days=21), start + timedelta(days=21), eligible=True),
            )
        },
    )

    runner = _runner(inputs, scanner=recorder, market_context=context)
    decisions = runner.scan_decisions(inputs)
    result = runner.replay(inputs)

    assert [decision.symbol for decision in decisions] == ["ACME"]
    assert [trade.symbol for trade in result.trades] == ["ACME"]
    universes_by_date = dict(recorder.universes)
    assert universes_by_date[start + timedelta(days=20)] == ("ACME",)
    assert universes_by_date[start + timedelta(days=21)] == ("ACME", "LATE")


def test_replay_rejects_incomplete_context_before_scanning() -> None:
    start = date(2026, 1, 1)
    bars = _breakout_bars("ACME", start, extra_days=1)
    inputs = FixtureInputs(Universe("v1", ("ACME",)), tuple(bars))
    covered_end = start + timedelta(days=20)
    context = MarketContext(
        {
            "ACME": SymbolContext(
                coverage=(CoverageWindow(start, covered_end),),
                eligibility=(EligibilityWindow(start, covered_end, eligible=True),),
            )
        }
    )

    class CountingScanner(MomentumScanner):
        def __init__(self) -> None:
            self.calls = 0

        def scan(self, universe, bars):  # type: ignore[override]
            self.calls += 1
            return []

    scanner = CountingScanner()

    with pytest.raises(MarketContextIncompleteError) as error:
        _runner(inputs, scanner=scanner, market_context=context).replay(inputs)

    assert error.value.reason == "market-context-incomplete"
    assert scanner.calls == 0


def test_entry_skipped_when_no_next_session_bar_exists() -> None:
    start = date(2026, 1, 1)
    symbol = "ACME"
    bars = _breakout_bars(symbol, start, extra_days=0)
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = _runner(inputs).replay(inputs).trades

    assert trades == ()


def test_trade_enters_at_day_n_plus_1_open() -> None:
    start = date(2026, 1, 1)
    symbol = "ACME"
    bars = _breakout_bars(symbol, start, extra_days=0)
    day_n1 = start + timedelta(days=21)
    bars.append(DailyBar(symbol, day_n1, Decimal("12.00"), Decimal("12.10"), Decimal("11.90"), Decimal("12.00"), 100))
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = _runner(inputs).replay(inputs).trades

    assert len(trades) == 1
    trade = trades[0]
    assert trade.symbol == symbol
    assert trade.entry_date == day_n1
    assert trade.entry_price == Decimal("12.00")
    assert trade.qty == 1250


def _elevated_hold_bars(symbol: str, start: date, first_offset: int, count: int) -> list[DailyBar]:
    """Post-entry bars with lows above the default 1-ATR stop so channel can arm."""
    return [
        DailyBar(
            symbol,
            start + timedelta(days=first_offset + i),
            Decimal("11.40"),
            Decimal("11.60"),
            Decimal("11.20"),
            Decimal("11.40"),
            100,
        )
        for i in range(count)
    ]


def test_trailing_channel_close_below_prior_low_exits_at_next_open() -> None:
    """Close strictly below prior-10 low → pending; fill raw next open (slippage in metrics)."""
    start = date(2026, 1, 1)
    symbol = "TRAIL"
    bars = _breakout_bars(symbol, start)
    # entry day 21 + 9 elevated holds → prior-10 window on day 31 is all elevated lows (11.20)
    bars.extend(_elevated_hold_bars(symbol, start, first_offset=21, count=10))
    signal_day = start + timedelta(days=31)
    fill_day = start + timedelta(days=32)
    # close 11.00 < prior-10 low 11.20; low 11.05 > stop 10.60 so hard stop does not fire
    bars.append(
        DailyBar(symbol, signal_day, Decimal("11.30"), Decimal("11.40"), Decimal("11.05"), Decimal("11.00"), 100)
    )
    bars.append(
        DailyBar(symbol, fill_day, Decimal("10.80"), Decimal("11.00"), Decimal("10.70"), Decimal("10.90"), 100)
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = _runner(inputs).replay(inputs).trades

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == "trailing-channel"
    assert trade.exit_price == Decimal("10.80")  # raw next open
    assert trade.exit_date == fill_day


def test_trailing_channel_trade_records_raw_entry_price_for_single_entry_slippage() -> None:
    """Regression: SimulatedTrade.entry_price must be raw open, never pre-slipped entry_fill.

    metrics.apply_costs / exit_proceeds apply entry_fill(trade.entry_price) once. If the
    harness stored entry_fill as entry_price, costs would double-count entry slippage
    (understate tax on winners, distort cash/P&L).
    """
    from invest.domain.backtest_metrics import DEFAULT_SLIPPAGE_BPS, apply_costs, entry_fill

    start = date(2026, 1, 1)
    symbol = "RAWENT"
    bars = _breakout_bars(symbol, start)
    bars.extend(_elevated_hold_bars(symbol, start, first_offset=21, count=10))
    signal_day = start + timedelta(days=31)
    fill_day = start + timedelta(days=32)
    bars.append(
        DailyBar(symbol, signal_day, Decimal("11.30"), Decimal("11.40"), Decimal("11.05"), Decimal("11.00"), 100)
    )
    bars.append(
        DailyBar(symbol, fill_day, Decimal("10.80"), Decimal("11.00"), Decimal("10.70"), Decimal("10.90"), 100)
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))
    slippage = DEFAULT_SLIPPAGE_BPS

    result = _runner(inputs, slippage_bps=slippage, tax_rate=Decimal("0")).replay(inputs)
    trade = result.trades[0]
    raw_entry_open = Decimal("11.40")  # entry bar open from elevated/entry path
    slipped_entry = entry_fill(raw_entry_open, slippage)

    assert trade.exit_reason == "trailing-channel"
    assert trade.entry_price == raw_entry_open
    assert trade.entry_price != slipped_entry
    # Hand-computed single-slippage net (tax_rate=0): exit_fill*qty - entry_fill*qty
    expected_net = (
        trade.exit_price * (Decimal("1") - slippage / Decimal("10000")) * trade.qty
        - slipped_entry * trade.qty
    )
    assert apply_costs(trade, slippage, Decimal("0")) == expected_net
    assert result.metrics.net_pnl == expected_net
    # Cash: start - entry_cost + exit_fill*qty (loss path, tax_rate=0)
    assert result.portfolio.cash == Decimal("100000") + expected_net


def test_intent_take_profit_is_ignored_for_replay_exits() -> None:
    """High that would have hit the old 2-ATR TP must not close the trade as take-profit."""
    start = date(2026, 1, 1)
    symbol = "NOTP"
    bars = _breakout_bars(symbol, start)
    day1 = start + timedelta(days=21)
    day2 = start + timedelta(days=22)
    bars.append(DailyBar(symbol, day1, Decimal("11.50"), Decimal("11.60"), Decimal("11.40"), Decimal("11.50"), 100))
    # high 13.20 would hit intent TP 13.00 under the old model
    bars.append(DailyBar(symbol, day2, Decimal("11.50"), Decimal("13.20"), Decimal("11.30"), Decimal("13.00"), 100))
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = _runner(inputs).replay(inputs).trades

    assert len(trades) == 1
    assert trades[0].exit_reason != "take-profit"
    assert trades[0].exit_reason == "open-at-end"


def test_stop_touch_exits_at_min_of_open_and_stop_gap_down_honored() -> None:
    start = date(2026, 1, 1)
    symbol = "LOSS"
    bars = _breakout_bars(symbol, start)
    day1 = start + timedelta(days=21)
    day2 = start + timedelta(days=22)
    bars.append(DailyBar(symbol, day1, Decimal("11.40"), Decimal("11.50"), Decimal("11.30"), Decimal("11.40"), 100))
    bars.append(DailyBar(symbol, day2, Decimal("11.00"), Decimal("11.20"), Decimal("10.50"), Decimal("10.60"), 100))
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = _runner(inputs).replay(inputs).trades

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == "stop"
    assert trade.exit_price == Decimal("10.60")
    assert trade.exit_date == day2


def test_hard_stop_beats_pending_trailing_channel_on_same_bar() -> None:
    start = date(2026, 1, 1)
    symbol = "TIE"
    bars = _breakout_bars(symbol, start)
    bars.extend(_elevated_hold_bars(symbol, start, first_offset=21, count=10))
    signal_day = start + timedelta(days=31)
    conflict_day = start + timedelta(days=32)
    bars.append(
        DailyBar(symbol, signal_day, Decimal("11.30"), Decimal("11.40"), Decimal("11.05"), Decimal("11.00"), 100)
    )
    # Pending trail + hard-stop touch on the fill bar → stop wins
    bars.append(
        DailyBar(symbol, conflict_day, Decimal("11.00"), Decimal("11.20"), Decimal("10.00"), Decimal("10.50"), 100)
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = _runner(inputs).replay(inputs).trades

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == "stop"
    assert trade.exit_price == Decimal("10.60")  # min(open=11.00, stop=10.60)


def test_open_at_end_when_no_exit_trigger_before_data_ends() -> None:
    start = date(2026, 1, 1)
    symbol = "OPENEND"
    bars = _breakout_bars(symbol, start)
    day1 = start + timedelta(days=21)
    bars.append(DailyBar(symbol, day1, Decimal("11.40"), Decimal("11.50"), Decimal("11.30"), Decimal("11.45"), 100))
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = _runner(inputs).replay(inputs).trades

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == "open-at-end"
    assert trade.exit_price == Decimal("11.45")
    assert trade.exit_date == day1


def test_trailing_signal_without_next_session_uses_open_at_end_and_warns() -> None:
    start = date(2026, 1, 1)
    symbol = "TAIL"
    bars = _breakout_bars(symbol, start)
    bars.extend(_elevated_hold_bars(symbol, start, first_offset=21, count=10))
    signal_day = start + timedelta(days=31)
    bars.append(
        DailyBar(symbol, signal_day, Decimal("11.30"), Decimal("11.40"), Decimal("11.05"), Decimal("11.00"), 100)
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    result = _runner(inputs).replay(inputs)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "open-at-end"
    assert trade.exit_date == signal_day
    assert trade.exit_price == Decimal("11.00")  # last close
    assert "missing-next-session-after-exit-signal" in result.warnings


def test_time_stop_exits_at_next_open_after_20_held_sessions_without_progress() -> None:
    """20 held sessions without +0.5R / new prior-20 high → time-stop fill at next raw open."""
    start = date(2026, 1, 1)
    symbol = "TSTOP"
    bars = _breakout_bars(symbol, start)
    # entry day 21 = session 1 … day 40 = session 20 → pending time-stop
    # elevated high 11.60 < half-R 11.80 (entry 11.40, stop 10.60, R=0.80)
    bars.extend(_elevated_hold_bars(symbol, start, first_offset=21, count=20))
    fill_day = start + timedelta(days=41)
    bars.append(
        DailyBar(symbol, fill_day, Decimal("11.10"), Decimal("11.30"), Decimal("11.00"), Decimal("11.20"), 100)
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = _runner(inputs).replay(inputs).trades

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == "time-stop"
    assert trade.exit_price == Decimal("11.10")  # raw next open
    assert trade.exit_date == fill_day
    assert trade.entry_price == Decimal("11.40")  # raw entry open


def test_time_stop_signal_without_next_session_uses_open_at_end_and_warns() -> None:
    start = date(2026, 1, 1)
    symbol = "TSTAIL"
    bars = _breakout_bars(symbol, start)
    bars.extend(_elevated_hold_bars(symbol, start, first_offset=21, count=20))
    signal_day = start + timedelta(days=40)  # last elevated day = 20th held session
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    result = _runner(inputs).replay(inputs)

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "open-at-end"
    assert trade.exit_date == signal_day
    assert "missing-next-session-after-exit-signal" in result.warnings


def test_hard_stop_beats_pending_time_stop_on_fill_bar() -> None:
    start = date(2026, 1, 1)
    symbol = "TSSTOP"
    bars = _breakout_bars(symbol, start)
    bars.extend(_elevated_hold_bars(symbol, start, first_offset=21, count=20))
    conflict_day = start + timedelta(days=41)
    bars.append(
        DailyBar(symbol, conflict_day, Decimal("11.00"), Decimal("11.20"), Decimal("10.00"), Decimal("10.50"), 100)
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = _runner(inputs).replay(inputs).trades

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == "stop"
    assert trade.exit_price == Decimal("10.60")


def test_forced_close_beats_pending_time_stop() -> None:
    start = date(2026, 1, 1)
    symbol = "TSFORCE"
    bars = _breakout_bars(symbol, start)
    bars.extend(_elevated_hold_bars(symbol, start, first_offset=21, count=20))
    forced_day = start + timedelta(days=41)
    bars.append(
        DailyBar(symbol, forced_day, Decimal("11.10"), Decimal("11.30"), Decimal("10.50"), Decimal("11.00"), 100)
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))
    context = _context_for_inputs(
        inputs,
        blockers_by_symbol={
            symbol: (BlockerWindow(forced_day, forced_day, reason=ContextReason.CORPORATE_ACTION),)
        },
    )

    result = _runner(inputs, market_context=context).replay(inputs)

    assert result.trades[0].exit_reason == "context-position-forced-closed"
    assert result.trades[0].exit_date == forced_day
    assert result.trades[0].exit_price == Decimal("10.50")


def test_half_r_progress_suppresses_time_stop_in_replay() -> None:
    start = date(2026, 1, 1)
    symbol = "HALFR"
    bars = _breakout_bars(symbol, start)
    # 20 hold sessions; one bar prints high >= 11.80 (+0.5R) so time-stop must not arm
    holds = _elevated_hold_bars(symbol, start, first_offset=21, count=20)
    holds[5] = DailyBar(
        symbol,
        start + timedelta(days=26),
        Decimal("11.40"),
        Decimal("12.00"),  # >= 11.80 half-R
        Decimal("11.20"),
        Decimal("11.40"),
        100,
    )
    bars.extend(holds)
    bars.append(
        DailyBar(
            symbol,
            start + timedelta(days=41),
            Decimal("11.10"),
            Decimal("11.30"),
            Decimal("11.00"),
            Decimal("11.20"),
            100,
        )
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = _runner(inputs).replay(inputs).trades

    assert len(trades) == 1
    assert trades[0].exit_reason == "open-at-end"
    assert trades[0].exit_reason != "time-stop"


def test_forced_close_beats_pending_trailing_channel() -> None:
    start = date(2026, 1, 1)
    symbol = "FORCE"
    bars = _breakout_bars(symbol, start)
    bars.extend(_elevated_hold_bars(symbol, start, first_offset=21, count=10))
    signal_day = start + timedelta(days=31)
    forced_day = start + timedelta(days=32)
    bars.append(
        DailyBar(symbol, signal_day, Decimal("11.30"), Decimal("11.40"), Decimal("11.05"), Decimal("11.00"), 100)
    )
    bars.append(
        DailyBar(symbol, forced_day, Decimal("10.80"), Decimal("11.00"), Decimal("10.50"), Decimal("10.70"), 100)
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))
    context = _context_for_inputs(
        inputs,
        blockers_by_symbol={
            symbol: (BlockerWindow(forced_day, forced_day, reason=ContextReason.CORPORATE_ACTION),)
        },
    )

    result = _runner(inputs, market_context=context).replay(inputs)

    assert result.trades[0].exit_reason == "context-position-forced-closed"
    assert result.trades[0].exit_date == forced_day
    assert result.trades[0].exit_price == Decimal("10.50")


def test_mutating_future_bars_does_not_change_day_n_exit() -> None:
    start = date(2026, 1, 1)
    symbol = "NOLA"
    bars = _breakout_bars(symbol, start)
    bars.extend(_elevated_hold_bars(symbol, start, first_offset=21, count=10))
    signal_day = start + timedelta(days=31)
    fill_day = start + timedelta(days=32)
    bars.append(
        DailyBar(symbol, signal_day, Decimal("11.30"), Decimal("11.40"), Decimal("11.05"), Decimal("11.00"), 100)
    )
    bars.append(
        DailyBar(symbol, fill_day, Decimal("10.80"), Decimal("11.00"), Decimal("10.70"), Decimal("10.90"), 100)
    )
    # extra future bar after the exit
    bars.append(
        DailyBar(
            symbol,
            start + timedelta(days=33),
            Decimal("50"),
            Decimal("60"),
            Decimal("40"),
            Decimal("55"),
            999,
        )
    )
    inputs_before = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))
    exit_before = _runner(inputs_before).replay(inputs_before).trades[0]
    assert exit_before.exit_date == fill_day

    corrupted = list(bars)
    for index, bar in enumerate(corrupted):
        if bar.date > fill_day:
            corrupted[index] = DailyBar(
                symbol, bar.date, Decimal("9999"), Decimal("10000"), Decimal("1"), Decimal("9999"), 999999
            )
    inputs_after = FixtureInputs(Universe("v1", (symbol,)), tuple(corrupted))
    exit_after = _runner(inputs_after).replay(inputs_after).trades[0]

    assert exit_after == exit_before


def test_replaying_same_range_twice_is_byte_identical() -> None:
    start = date(2026, 1, 1)
    symbol = "ACME"
    bars = _breakout_bars(symbol, start, extra_days=3)
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    first = _runner(inputs).replay(inputs)
    second = _runner(inputs).replay(inputs)

    assert first == second


def test_portfolio_replay_orders_same_day_entries_and_enforces_deployed_cap() -> None:
    start = date(2026, 1, 1)
    symbols = ("ALPHA", "BRAVO")
    bars = [bar for symbol in symbols for bar in _breakout_bars(symbol, start, extra_days=1)]
    inputs = FixtureInputs(Universe("v1", symbols), tuple(bars))

    result = _runner(inputs).replay(inputs, split_date=start + timedelta(days=21))

    assert [trade.symbol for trade in result.trades] == ["ALPHA"]
    assert result.portfolio.open_position_count == 1
    assert result.gates.label == "portfolio-gates-simulated"
    assert result.gates.counts == {"max-equity-deployed": 1}
    assert result.equity_summary.trading_day_count == 22


def test_portfolio_replay_records_insufficient_buying_power_as_visible_skip() -> None:
    start = date(2026, 1, 1)
    bars = _breakout_bars("CASH", start, extra_days=1)
    inputs = FixtureInputs(Universe("v1", ("CASH",)), tuple(bars))

    result = _runner(inputs, equity=Decimal("100000"), buying_power=Decimal("10000")).replay(inputs)

    assert result.trades == ()
    assert result.gates.counts == {"insufficient-buying-power": 1}
    assert result.skipped_entries[0].symbol == "CASH"
    assert result.skipped_entries[0].reason == "insufficient-buying-power"


def test_portfolio_replay_releases_cash_on_exit_and_uses_prior_equity_for_kill_switch() -> None:
    from invest.domain.models import ScanDecision

    start = date(2026, 1, 1)
    loss_bars = _breakout_bars("LOSS", start, extra_days=2)
    loss_bars[-1] = DailyBar(loss_bars[-1].symbol, loss_bars[-1].date, Decimal("8"), Decimal("9"), Decimal("7"), Decimal("8"), 100)
    next_bars = _breakout_bars("NEXT", start, extra_days=2)

    class ScannerWithScheduledSignals(MomentumScanner):
        def scan(self, universe, bars):  # type: ignore[override]
            current_day = max(bar.date for bar in bars)
            if current_day == start + timedelta(days=20):
                return [ScanDecision("LOSS", current_day, True)]
            if current_day == start + timedelta(days=21):
                return [ScanDecision("NEXT", current_day, True)]
            return []

    inputs = FixtureInputs(Universe("v1", ("LOSS", "NEXT")), tuple(loss_bars + next_bars))
    result = _runner(inputs, scanner=ScannerWithScheduledSignals()).replay(inputs)

    assert result.trades[0].exit_reason == "stop"
    assert result.portfolio.cash == Decimal("95737.875")
    assert result.gates.counts == {"kill-switch": 1}
    assert result.skipped_entries[0].symbol == "NEXT"


def test_portfolio_cash_and_equity_use_configured_entry_slippage() -> None:
    start = date(2026, 1, 1)
    bars = _breakout_bars("COST", start, extra_days=1)
    inputs = FixtureInputs(Universe("v1", ("COST",)), tuple(bars))

    result = _runner(inputs, slippage_bps=Decimal("100"), tax_rate=Decimal("0")).replay(inputs)

    assert result.portfolio.cash == Decimal("85607.500")
    assert result.portfolio.equity == Decimal("99715.000")


def test_open_position_without_daily_bar_carries_last_valuation_with_warning() -> None:
    from invest.domain.models import ScanDecision

    start = date(2026, 1, 1)
    gap_bars = _breakout_bars("GAP", start, extra_days=2)
    missing_date = start + timedelta(days=22)
    clock_bar = DailyBar("CLOCK", missing_date, Decimal("10"), Decimal("10"), Decimal("10"), Decimal("10"), 100)

    class GapSignalScanner(MomentumScanner):
        def scan(self, universe, bars):  # type: ignore[override]
            current_day = max(bar.date for bar in bars)
            return [ScanDecision("GAP", current_day, True)] if current_day == start + timedelta(days=20) else []

    inputs = FixtureInputs(
        Universe("v1", ("GAP", "CLOCK")),
        tuple(bar for bar in gap_bars if bar.date != missing_date) + (clock_bar,),
    )

    result = _runner(inputs, scanner=GapSignalScanner()).replay(inputs)

    assert result.portfolio.equity == Decimal("99985.75000")
    assert "missing-bar-carried-forward" in result.warnings


def test_entry_gap_is_rejected_when_actual_next_open_cost_exceeds_cash() -> None:
    start = date(2026, 1, 1)
    bars = _breakout_bars("GAP", start, extra_days=1)
    entry_day = start + timedelta(days=21)
    bars[-1] = DailyBar("GAP", entry_day, Decimal("12"), Decimal("12.10"), Decimal("11.90"), Decimal("12"), 100)
    inputs = FixtureInputs(Universe("v1", ("GAP",)), tuple(bars))

    result = _runner(inputs, buying_power=Decimal("15000")).replay(inputs)

    assert result.trades == ()
    assert result.gates.counts == {"insufficient-buying-power": 1}
    assert result.portfolio.cash == Decimal("100000")


def test_repeated_accepted_signal_does_not_overwrite_open_position_or_cash() -> None:
    from invest.domain.models import ScanDecision

    start = date(2026, 1, 1)
    bars = _breakout_bars("REPEAT", start, extra_days=2)

    class RepeatedSignalScanner(MomentumScanner):
        def scan(self, universe, bars):  # type: ignore[override]
            current_day = max(bar.date for bar in bars)
            if current_day in {start + timedelta(days=20), start + timedelta(days=21)}:
                return [ScanDecision("REPEAT", current_day, True)]
            return []

    inputs = FixtureInputs(Universe("v1", ("REPEAT",)), tuple(bars))
    result = _runner(inputs, scanner=RepeatedSignalScanner()).replay(inputs)

    assert [(trade.entry_date, trade.qty) for trade in result.trades] == [(start + timedelta(days=21), 1250)]
    assert result.portfolio.cash == Decimal("85742.87500")
    assert result.gates.counts == {"already-submitted": 1}
    assert result.skipped_entries[-1].reason == "already-submitted"


def test_blocked_entry_records_context_outcome_without_touching_portfolio_gates() -> None:
    start = date(2026, 1, 1)
    bars = _breakout_bars("BLOCKED", start, extra_days=1)
    inputs = FixtureInputs(Universe("v1", ("BLOCKED",)), tuple(bars))
    entry_day = start + timedelta(days=21)
    context = _context_for_inputs(
        inputs,
        blockers_by_symbol={
            "BLOCKED": (
                BlockerWindow(entry_day, entry_day, reason=ContextReason.CORPORATE_ACTION),
            )
        },
    )

    result = _runner(inputs, market_context=context).replay(inputs)

    assert result.trades == ()
    assert result.skipped_entries == ()
    assert result.gates.counts == {}
    assert result.context_outcomes == (
        ContextOutcome(
            outcome_type=ContextOutcomeType.ENTRY_BLOCKED,
            reason=ContextReason.CORPORATE_ACTION,
            symbol="BLOCKED",
            date=entry_day,
        ),
    )


def test_unsafe_position_forces_close_before_ordinary_exit_at_bar_low() -> None:
    start = date(2026, 1, 1)
    bars = _breakout_bars("HOLD", start)
    entry_day = start + timedelta(days=21)
    unsafe_day = start + timedelta(days=22)
    bars.append(DailyBar("HOLD", entry_day, Decimal("11.40"), Decimal("11.50"), Decimal("11.30"), Decimal("11.40"), 100))
    bars.append(DailyBar("HOLD", unsafe_day, Decimal("11.40"), Decimal("13.50"), Decimal("10.20"), Decimal("13.00"), 100))
    inputs = FixtureInputs(Universe("v1", ("HOLD",)), tuple(bars))
    context = _context_for_inputs(
        inputs,
        blockers_by_symbol={
            "HOLD": (
                BlockerWindow(unsafe_day, unsafe_day, reason=ContextReason.EARNINGS_CONTEXT_MISSING),
            )
        },
    )

    result = _runner(inputs, market_context=context).replay(inputs)

    assert result.trades[0].exit_reason == "context-position-forced-closed"
    assert result.trades[0].exit_price == Decimal("10.20")
    assert result.context_outcomes == (
        ContextOutcome(
            outcome_type=ContextOutcomeType.POSITION_FORCED_CLOSED,
            reason=ContextReason.EARNINGS_CONTEXT_MISSING,
            symbol="HOLD",
            date=unsafe_day,
        ),
    )


def test_forced_close_settles_before_pending_entry_uses_cash_equity_and_buying_power() -> None:
    from invest.domain.models import ScanDecision

    start = date(2026, 1, 1)
    entry_day = start + timedelta(days=21)
    forced_close_day = start + timedelta(days=22)
    hold_bars = _breakout_bars("HOLD", start, extra_days=2)
    hold_bars[-2] = DailyBar(
        "HOLD",
        entry_day,
        Decimal("10.60"),
        Decimal("11.50"),
        Decimal("10.61"),
        Decimal("11.40"),
        100,
    )
    hold_bars[-1] = DailyBar(
        "HOLD",
        forced_close_day,
        Decimal("11.40"),
        Decimal("11.50"),
        Decimal("10.30"),
        Decimal("11.40"),
        100,
    )
    next_bars = _breakout_bars("NEXT", start, extra_days=2)

    class ScannerWithConcurrentExitAndEntry(MomentumScanner):
        def scan(self, universe, bars):  # type: ignore[override]
            current_day = max(bar.date for bar in bars)
            if current_day == start + timedelta(days=20):
                return [ScanDecision("HOLD", current_day, True)]
            if current_day == entry_day:
                return [ScanDecision("NEXT", current_day, True)]
            return []

    inputs = FixtureInputs(Universe("v1", ("HOLD", "NEXT")), tuple(hold_bars + next_bars))
    context = _context_for_inputs(
        inputs,
        blockers_by_symbol={
            "HOLD": (
                BlockerWindow(
                    forced_close_day,
                    forced_close_day,
                    reason=ContextReason.CORPORATE_ACTION,
                ),
            )
        },
    )

    result = _runner(
        inputs,
        scanner=ScannerWithConcurrentExitAndEntry(),
        market_context=context,
        equity=Decimal("100000"),
        cash=Decimal("15000"),
        buying_power=Decimal("2000"),
        slippage_bps=Decimal("0"),
        tax_rate=Decimal("0"),
    ).replay(inputs)

    assert [(trade.symbol, trade.exit_reason, trade.qty) for trade in result.trades] == [
        ("HOLD", "context-position-forced-closed", 187),
        ("NEXT", "open-at-end", 175),
    ]
    assert result.skipped_entries == ()
    assert result.gates.counts == {}
    assert result.portfolio.cash == Decimal("12948.90")
    assert result.portfolio.equity == Decimal("14943.90")


def test_unsafe_position_without_same_day_bar_aborts_as_market_context_incomplete() -> None:
    from invest.domain.models import ScanDecision

    start = date(2026, 1, 1)
    gap_bars = _breakout_bars("GAP", start, extra_days=2)
    missing_date = start + timedelta(days=22)
    clock_bar = DailyBar("CLOCK", missing_date, Decimal("10"), Decimal("10"), Decimal("10"), Decimal("10"), 100)

    class GapSignalScanner(MomentumScanner):
        def scan(self, universe, bars):  # type: ignore[override]
            current_day = max(bar.date for bar in bars)
            return [ScanDecision("GAP", current_day, True)] if current_day == start + timedelta(days=20) else []

    inputs = FixtureInputs(
        Universe("v1", ("GAP", "CLOCK")),
        tuple(bar for bar in gap_bars if bar.date != missing_date) + (clock_bar,),
    )
    context = _context_for_inputs(
        inputs,
        blockers_by_symbol={
            "GAP": (
                BlockerWindow(missing_date, missing_date, reason=ContextReason.CORPORATE_ACTION),
            )
        },
    )

    with pytest.raises(MarketContextIncompleteError) as error:
        _runner(inputs, scanner=GapSignalScanner(), market_context=context).replay(inputs)

    assert error.value.reason == "market-context-incomplete"
