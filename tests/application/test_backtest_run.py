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
    GenerationSpan,
    MarketContext,
    MarketContextIncompleteError,
    SymbolContext,
)
from invest.domain.models import DailyBar, FixtureInputs, SkippedEntry, Universe
from invest.domain.scanner import MomentumScanner


def _breakout_bars(symbol: str, start: date, extra_days: int = 0) -> list[DailyBar]:
    """20 flat bars (no signal) followed by one breakout bar that MomentumScanner accepts.

    History: open=10, high=10.40, low=9.60, close=10, vol=100 (ATR(20)=0.80 per bar).
    Breakout (day 20): open=10, high=11.50, low=10, close=11.40, vol=250 -> accepted.
    Fill day (first extra day, open=11.40, no gap): compute_intent yields entry=11.40,
    breakout_low=10, ATR leg=11.40-2*0.80=9.80 -> stop=min(10, 9.80)=9.80 (ATR leg wins),
    take_profit=11.40+1.60=13.00, risk_capital=100000*0.0035=350, qty=floor(350/1.60)=218.
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
    generation_span: GenerationSpan | None = None,
) -> MarketContext:
    replay_dates = sorted({bar.date for bar in inputs.bars})
    start = replay_dates[0]
    end = replay_dates[-1]
    return MarketContext(
        generation_span=generation_span or GenerationSpan(start, end),
        by_symbol={
            symbol: SymbolContext(
                coverage=(CoverageWindow(start, end),),
                eligibility=(eligibility_by_symbol or {}).get(
                    symbol, (EligibilityWindow(start, end, eligible=True),)
                ),
                blockers=(blockers_by_symbol or {}).get(symbol, ()),
            )
            for symbol in inputs.universe.symbols
        },
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


def test_measurement_start_uses_warmup_without_emitting_earlier_decisions() -> None:
    start = date(2026, 1, 1)
    measurement_start = start + timedelta(days=20)
    symbol = "WARM"
    inputs = FixtureInputs(
        Universe("v1", (symbol,)),
        tuple(_breakout_bars(symbol, start, extra_days=1)),
    )

    class CumulativeMomentumScanner(MomentumScanner):
        pass

    decisions = _runner(inputs).scan_decisions(inputs, start=measurement_start)
    cumulative = _runner(inputs, scanner=CumulativeMomentumScanner()).scan_decisions(
        inputs,
        start=measurement_start,
    )

    assert [decision.decision_date for decision in decisions] == [measurement_start]
    assert cumulative == decisions
    result = _runner(inputs).replay(inputs, start=measurement_start)
    assert result.trades
    assert all(trade.entry_date >= measurement_start for trade in result.trades)


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


def test_indexed_replay_uses_bounded_per_symbol_histories_without_legacy_rescan() -> None:
    start = date(2026, 1, 1)
    symbols = ("ACME", "BETA")
    bars = tuple(
        DailyBar(
            symbol,
            start + timedelta(days=offset),
            Decimal("10"),
            Decimal("11"),
            Decimal("9"),
            Decimal("10"),
            100,
        )
        for offset in range(5)
        for symbol in symbols
    )
    inputs = FixtureInputs(Universe("v1", symbols), bars)

    class IndexedRecordingScanner:
        replay_history_bars = 2

        def __init__(self) -> None:
            self.snapshots: list[dict[str, tuple[date, ...]]] = []

        def scan(self, universe, bars):
            pytest.fail("indexed replay must not call the cumulative legacy scanner seam")

        def scan_indexed(self, universe, histories):
            self.snapshots.append(
                {
                    symbol: tuple(bar.date for bar in histories.get(symbol, ()))
                    for symbol in universe.symbols
                }
            )
            return []

    scanner = IndexedRecordingScanner()

    decisions = _runner(inputs, scanner=scanner).scan_decisions(inputs)

    assert decisions == []
    assert len(scanner.snapshots) == 5
    assert scanner.snapshots[-1] == {
        "ACME": (start + timedelta(days=3), start + timedelta(days=4)),
        "BETA": (start + timedelta(days=3), start + timedelta(days=4)),
    }


def test_indexed_replay_retains_history_while_symbol_is_ineligible() -> None:
    start = date(2026, 1, 1)
    bars = tuple(
        DailyBar(
            "ACME",
            start + timedelta(days=offset),
            Decimal("10"),
            Decimal("11"),
            Decimal("9"),
            Decimal("10"),
            100,
        )
        for offset in range(5)
    )
    inputs = FixtureInputs(Universe("v1", ("ACME",)), bars)
    context = _context_for_inputs(
        inputs,
        eligibility_by_symbol={
            "ACME": (
                EligibilityWindow(start, start + timedelta(days=2), eligible=False),
                EligibilityWindow(
                    start + timedelta(days=3),
                    start + timedelta(days=4),
                    eligible=True,
                ),
            )
        },
    )

    class IndexedRecordingScanner:
        replay_history_bars = 3

        def __init__(self) -> None:
            self.snapshots: list[tuple[date, ...]] = []

        def scan(self, universe, bars):
            pytest.fail("indexed replay must not call the cumulative legacy scanner seam")

        def scan_indexed(self, universe, histories):
            if universe.symbols:
                self.snapshots.append(
                    tuple(bar.date for bar in histories[universe.symbols[0]])
                )
            return []

    scanner = IndexedRecordingScanner()

    _runner(inputs, scanner=scanner, market_context=context).scan_decisions(inputs)

    assert scanner.snapshots[0] == (
        start + timedelta(days=1),
        start + timedelta(days=2),
        start + timedelta(days=3),
    )


def test_scan_progress_counts_days_bars_and_accepted_decisions_monotonically() -> None:
    start = date(2026, 1, 1)
    symbols = ("ACME", "BETA")
    bars = tuple(
        DailyBar(
            symbol,
            start + timedelta(days=offset),
            Decimal("10"),
            Decimal("11"),
            Decimal("9"),
            Decimal("10"),
            100,
        )
        for offset in range(5)
        for symbol in symbols
    )
    inputs = FixtureInputs(Universe("v1", symbols), bars)
    events = []

    _runner(inputs, progress_callback=events.append).scan_decisions(inputs)

    assert [event.phase for event in events] == ["scan"] * 5
    assert [event.processed_replay_days for event in events] == [1, 2, 3, 4, 5]
    assert [event.total_replay_days for event in events] == [5] * 5
    assert [event.ingested_bars for event in events] == [2, 4, 6, 8, 10]
    assert [event.accepted_decisions for event in events] == sorted(
        event.accepted_decisions for event in events
    )
    assert [event.percent for event in events] == [20, 40, 60, 80, 100]


def test_indexed_replay_work_is_bounded_instead_of_cumulative() -> None:
    start = date(2026, 1, 1)
    symbols = ("ACME", "BETA")
    replay_days = 10
    history_limit = 3
    bars = tuple(
        DailyBar(
            symbol,
            start + timedelta(days=offset),
            Decimal("10"),
            Decimal("11"),
            Decimal("9"),
            Decimal("10"),
            100,
        )
        for offset in range(replay_days)
        for symbol in symbols
    )
    inputs = FixtureInputs(Universe("v1", symbols), bars)

    class IndexedCountingScanner:
        replay_history_bars = history_limit

        def __init__(self) -> None:
            self.bar_references = 0

        def scan(self, universe, bars):
            pytest.fail("indexed replay must not call the cumulative legacy scanner seam")

        def scan_indexed(self, universe, histories):
            self.bar_references += sum(len(history) for history in histories.values())
            return []

    class LegacyCountingScanner:
        def __init__(self) -> None:
            self.bar_references = 0

        def scan(self, universe, window):
            self.bar_references += len(window)
            return []

    indexed = IndexedCountingScanner()
    legacy = LegacyCountingScanner()

    _runner(inputs, scanner=indexed).scan_decisions(inputs)
    _runner(inputs, scanner=legacy).scan_decisions(inputs)

    assert indexed.bar_references <= replay_days * len(symbols) * history_limit
    assert legacy.bar_references == len(symbols) * sum(range(1, replay_days + 1))
    assert indexed.bar_references < legacy.bar_references


def test_benchmark_indexed_replay_remembers_zero_volume_outside_rolling_history() -> None:
    start = date(2026, 1, 1)
    bars = [
        DailyBar(
            "ACME",
            start + timedelta(days=offset),
            Decimal("10"),
            Decimal("10.40"),
            Decimal("9.60"),
            Decimal("10"),
            100,
        )
        for offset in range(22)
    ]
    bars.append(
        DailyBar(
            "ACME",
            start + timedelta(days=22),
            Decimal("10"),
            Decimal("11.50"),
            Decimal("10"),
            Decimal("11.40"),
            250,
        )
    )
    first = bars[0]
    bars[0] = DailyBar(
        first.symbol,
        first.date,
        first.open,
        first.high,
        first.low,
        first.close,
        0,
    )
    inputs = FixtureInputs(Universe("v1", ("ACME",)), tuple(bars))

    class CumulativeMomentumScanner(MomentumScanner):
        pass

    indexed = _runner(inputs, scanner=MomentumScanner()).scan_decisions(inputs)
    cumulative = _runner(inputs, scanner=CumulativeMomentumScanner()).scan_decisions(inputs)

    assert indexed == cumulative


def test_benchmark_indexed_replay_remembers_invalid_bar_outside_rolling_history() -> None:
    start = date(2026, 1, 1)
    bars = [
        DailyBar(
            "ACME",
            start + timedelta(days=offset),
            Decimal("10"),
            Decimal("10.40"),
            Decimal("9.60"),
            Decimal("10"),
            100,
        )
        for offset in range(22)
    ]
    bars.append(
        DailyBar(
            "ACME",
            start + timedelta(days=22),
            Decimal("10"),
            Decimal("11.50"),
            Decimal("10"),
            Decimal("11.40"),
            250,
        )
    )
    first = bars[0]
    bars[0] = DailyBar(
        first.symbol,
        first.date,
        first.open,
        first.low,
        first.high,
        first.close,
        first.volume,
    )
    inputs = FixtureInputs(Universe("v1", ("ACME",)), tuple(bars))

    class CumulativeMomentumScanner(MomentumScanner):
        pass

    indexed = _runner(inputs, scanner=MomentumScanner()).scan_decisions(inputs)
    cumulative = _runner(inputs, scanner=CumulativeMomentumScanner()).scan_decisions(inputs)

    assert indexed == cumulative


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
    assert len(recorder.windows[-1]) == len(inputs.bars)


def test_replay_rejects_incomplete_context_before_scanning() -> None:
    start = date(2026, 1, 1)
    bars = _breakout_bars("ACME", start, extra_days=1)
    inputs = FixtureInputs(Universe("v1", ("ACME",)), tuple(bars))
    covered_end = start + timedelta(days=20)
    context = MarketContext(
        generation_span=GenerationSpan(start, start + timedelta(days=21)),
        by_symbol={
            "ACME": SymbolContext(
                coverage=(CoverageWindow(start, covered_end),),
                eligibility=(EligibilityWindow(start, covered_end, eligible=True),),
            )
        },
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


def test_warmup_bars_are_scanner_visible_but_never_replay_events() -> None:
    start = date(2026, 1, 1)
    replay_start = start + timedelta(days=20)
    bars = _breakout_bars("ACME", start, extra_days=2)
    inputs = FixtureInputs(Universe("v1", ("ACME",)), tuple(bars))
    recorder = _RecordingScanner()
    context = _context_for_inputs(
        inputs,
        generation_span=GenerationSpan(replay_start, start + timedelta(days=22)),
    )
    runner = _runner(inputs, scanner=recorder, market_context=context)

    decisions = runner.scan_decisions(inputs)
    result = runner.replay(inputs)

    assert [decision.decision_date for decision in decisions] == [replay_start]
    assert len(recorder.windows[0]) == 21
    event_dates = [trade.entry_date for trade in result.trades]
    event_dates += [trade.exit_date for trade in result.trades]
    event_dates += [entry.decision_date for entry in result.skipped_entries]
    event_dates += [entry.entry_date for entry in result.skipped_entries]
    event_dates += [outcome.date for outcome in result.context_outcomes]
    assert event_dates
    assert min(event_dates) >= replay_start
    assert result.equity_summary.trading_day_count == 3


def test_replay_checks_each_observed_in_span_date_for_every_fixture_symbol() -> None:
    start = date(2026, 1, 1)
    replay_start = start + timedelta(days=20)
    bars = _breakout_bars("ACME", start, extra_days=1)
    inputs = FixtureInputs(Universe("v1", ("ACME",)), tuple(bars))
    context = MarketContext(
        generation_span=GenerationSpan(replay_start, start + timedelta(days=21)),
        by_symbol={
            "ACME": SymbolContext(
                coverage=(CoverageWindow(replay_start, start + timedelta(days=21)),),
                eligibility=(EligibilityWindow(replay_start, replay_start, eligible=True),),
            )
        },
    )

    with pytest.raises(MarketContextIncompleteError) as error:
        _runner(inputs, market_context=context).replay(inputs)

    assert str(error.value) == "missing eligibility for ACME on 2026-01-22"


def test_replay_rejects_post_span_bars_with_stable_reason() -> None:
    start = date(2026, 1, 1)
    bars = _breakout_bars("ACME", start, extra_days=1)
    inputs = FixtureInputs(Universe("v1", ("ACME",)), tuple(bars))
    context = _context_for_inputs(
        inputs,
        generation_span=GenerationSpan(start, start + timedelta(days=20)),
    )

    with pytest.raises(ValueError) as error:
        _runner(inputs, market_context=context).replay(inputs)

    assert getattr(error.value, "reason", None) == "replay-window-invalid"


def test_replay_rejects_empty_in_span_partition_with_stable_reason() -> None:
    start = date(2026, 1, 1)
    bars = _breakout_bars("ACME", start)
    inputs = FixtureInputs(Universe("v1", ("ACME",)), tuple(bars))
    context = _context_for_inputs(
        inputs,
        generation_span=GenerationSpan(
            start + timedelta(days=30),
            start + timedelta(days=31),
        ),
    )

    with pytest.raises(ValueError) as error:
        _runner(inputs, market_context=context).replay(inputs)

    assert getattr(error.value, "reason", None) == "replay-window-invalid"


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
    # breakout_low=10, ATR leg=12.00-1.60=10.40 -> stop=min(10, 10.40)=10 (breakout_low wins).
    # stop_distance=2.00 -> qty=floor(350/2.00)=175.
    assert trade.qty == 175


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


def test_take_profit_touch_exits_at_intent_target() -> None:
    start = date(2026, 1, 1)
    symbol = "NOTP"
    bars = _breakout_bars(symbol, start)
    day1 = start + timedelta(days=21)
    day2 = start + timedelta(days=22)
    bars.append(DailyBar(symbol, day1, Decimal("11.50"), Decimal("11.60"), Decimal("11.40"), Decimal("11.50"), 100))
    # Actual fill-day open is 11.50, so the 2-ATR target is 13.10.
    bars.append(DailyBar(symbol, day2, Decimal("11.50"), Decimal("13.20"), Decimal("11.30"), Decimal("13.00"), 100))
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = _runner(inputs).replay(inputs).trades

    assert len(trades) == 1
    assert trades[0].exit_reason == "take-profit"
    assert trades[0].exit_price == Decimal("13.10")
    assert trades[0].exit_date == day2


def test_take_profit_gap_up_fills_at_target_without_gap_credit() -> None:
    start = date(2026, 1, 1)
    symbol = "TPGAP"
    bars = _breakout_bars(symbol, start)
    entry_day = start + timedelta(days=21)
    exit_day = start + timedelta(days=22)
    bars.append(
        DailyBar(
            symbol,
            entry_day,
            Decimal("11.50"),
            Decimal("11.60"),
            Decimal("11.40"),
            Decimal("11.50"),
            100,
        )
    )
    bars.append(
        DailyBar(
            symbol,
            exit_day,
            Decimal("14.00"),
            Decimal("14.20"),
            Decimal("13.80"),
            Decimal("14.00"),
            100,
        )
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trade = _runner(inputs).replay(inputs).trades[0]

    assert trade.exit_reason == "take-profit"
    assert trade.exit_price == Decimal("13.10")


def test_same_bar_stop_and_take_profit_touch_resolves_to_stop() -> None:
    start = date(2026, 1, 1)
    symbol = "TPTIE"
    bars = _breakout_bars(symbol, start)
    entry_day = start + timedelta(days=21)
    conflict_day = start + timedelta(days=22)
    bars.append(
        DailyBar(
            symbol,
            entry_day,
            Decimal("11.50"),
            Decimal("11.60"),
            Decimal("11.40"),
            Decimal("11.50"),
            100,
        )
    )
    bars.append(
        DailyBar(
            symbol,
            conflict_day,
            Decimal("11.50"),
            Decimal("13.20"),
            Decimal("9.50"),
            Decimal("11.00"),
            100,
        )
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trade = _runner(inputs).replay(inputs).trades[0]

    assert trade.exit_reason == "stop"
    assert trade.exit_price == Decimal("9.90")


def test_take_profit_not_hit_keeps_position_open() -> None:
    start = date(2026, 1, 1)
    symbol = "TPMISS"
    bars = _breakout_bars(symbol, start)
    entry_day = start + timedelta(days=21)
    final_day = start + timedelta(days=22)
    bars.append(
        DailyBar(
            symbol,
            entry_day,
            Decimal("11.50"),
            Decimal("11.60"),
            Decimal("11.40"),
            Decimal("11.50"),
            100,
        )
    )
    bars.append(
        DailyBar(
            symbol,
            final_day,
            Decimal("11.50"),
            Decimal("13.09"),
            Decimal("11.30"),
            Decimal("12.90"),
            100,
        )
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trade = _runner(inputs).replay(inputs).trades[0]

    assert trade.exit_reason == "open-at-end"
    assert trade.exit_date == final_day


def test_stop_touch_exits_at_min_of_open_and_stop_gap_down_honored() -> None:
    # entry=11.40, stop=9.80 (see _breakout_bars docstring) -> day2 gaps open below stop.
    start = date(2026, 1, 1)
    symbol = "LOSS"
    bars = _breakout_bars(symbol, start)
    day1 = start + timedelta(days=21)
    day2 = start + timedelta(days=22)
    bars.append(DailyBar(symbol, day1, Decimal("11.40"), Decimal("11.50"), Decimal("11.30"), Decimal("11.40"), 100))
    bars.append(DailyBar(symbol, day2, Decimal("9.50"), Decimal("9.70"), Decimal("9.00"), Decimal("9.20"), 100))
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = _runner(inputs).replay(inputs).trades

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == "stop"
    assert trade.exit_price == Decimal("9.50")  # min(open=9.50, stop=9.80)
    assert trade.exit_date == day2


def test_hard_stop_beats_pending_trailing_channel_on_same_bar() -> None:
    # entry=11.40, stop=9.80 (see _breakout_bars docstring).
    start = date(2026, 1, 1)
    symbol = "TIE"
    bars = _breakout_bars(symbol, start)
    bars.extend(_elevated_hold_bars(symbol, start, first_offset=21, count=10))
    signal_day = start + timedelta(days=31)
    conflict_day = start + timedelta(days=32)
    bars.append(
        DailyBar(symbol, signal_day, Decimal("11.30"), Decimal("11.40"), Decimal("11.05"), Decimal("11.00"), 100)
    )
    # Pending trail + hard-stop touch (low breaches 9.80) on the fill bar → stop wins
    bars.append(
        DailyBar(symbol, conflict_day, Decimal("11.00"), Decimal("11.20"), Decimal("9.50"), Decimal("10.50"), 100)
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = _runner(inputs).replay(inputs).trades

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == "stop"
    assert trade.exit_price == Decimal("9.80")  # min(open=11.00, stop=9.80)


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
    # entry=11.40, stop=9.80 (see _breakout_bars docstring).
    start = date(2026, 1, 1)
    symbol = "TSSTOP"
    bars = _breakout_bars(symbol, start)
    bars.extend(_elevated_hold_bars(symbol, start, first_offset=21, count=20))
    conflict_day = start + timedelta(days=41)
    bars.append(
        DailyBar(symbol, conflict_day, Decimal("11.00"), Decimal("11.20"), Decimal("9.50"), Decimal("10.50"), 100)
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))

    trades = _runner(inputs).replay(inputs).trades

    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == "stop"
    assert trade.exit_price == Decimal("9.80")  # min(open=11.00, stop=9.80)


def test_transient_corporate_action_does_not_preempt_pending_time_stop() -> None:
    start = date(2026, 1, 1)
    symbol = "TSFORCE"
    bars = _breakout_bars(symbol, start)
    bars.extend(_elevated_hold_bars(symbol, start, first_offset=21, count=20))
    blocked_day = start + timedelta(days=41)
    bars.append(
        DailyBar(symbol, blocked_day, Decimal("11.10"), Decimal("11.30"), Decimal("10.50"), Decimal("11.00"), 100)
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))
    context = _context_for_inputs(
        inputs,
        blockers_by_symbol={
            symbol: (BlockerWindow(blocked_day, blocked_day, reason=ContextReason.CORPORATE_ACTION),)
        },
    )

    result = _runner(inputs, market_context=context).replay(inputs)

    assert result.trades[0].exit_reason == "time-stop"
    assert result.trades[0].exit_date == blocked_day
    assert result.trades[0].exit_price == Decimal("11.10")
    assert result.context_outcomes == ()


def test_half_r_progress_suppresses_time_stop_in_replay() -> None:
    start = date(2026, 1, 1)
    symbol = "HALFR"
    bars = _breakout_bars(symbol, start)
    # entry=11.40, stop=9.80 -> risk=1.60, half-R level = 11.40 + 0.5*1.60 = 12.20.
    # 20 hold sessions; one bar prints high >= 12.20 (+0.5R) so time-stop must not arm
    holds = _elevated_hold_bars(symbol, start, first_offset=21, count=20)
    holds[5] = DailyBar(
        symbol,
        start + timedelta(days=26),
        Decimal("11.40"),
        Decimal("12.30"),  # >= 12.20 half-R
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


def test_transient_corporate_action_does_not_preempt_pending_trailing_channel() -> None:
    start = date(2026, 1, 1)
    symbol = "FORCE"
    bars = _breakout_bars(symbol, start)
    bars.extend(_elevated_hold_bars(symbol, start, first_offset=21, count=10))
    signal_day = start + timedelta(days=31)
    blocked_day = start + timedelta(days=32)
    bars.append(
        DailyBar(symbol, signal_day, Decimal("11.30"), Decimal("11.40"), Decimal("11.05"), Decimal("11.00"), 100)
    )
    bars.append(
        DailyBar(symbol, blocked_day, Decimal("10.80"), Decimal("11.00"), Decimal("10.50"), Decimal("10.70"), 100)
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))
    context = _context_for_inputs(
        inputs,
        blockers_by_symbol={
            symbol: (BlockerWindow(blocked_day, blocked_day, reason=ContextReason.CORPORATE_ACTION),)
        },
    )

    result = _runner(inputs, market_context=context).replay(inputs)

    assert result.trades[0].exit_reason == "trailing-channel"
    assert result.trades[0].exit_date == blocked_day
    assert result.trades[0].exit_price == Decimal("10.80")
    assert result.context_outcomes == ()


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


def _tight_stop_bars(
    symbol: str,
    start: date,
    *,
    pre_days: int,
    near_level: Decimal,
    volume: int = 100,
    breakout_volume: int | None = None,
) -> list[DailyBar]:
    """Flat `pre_days` history at `near_level` (ATR(20)=0.80), a breakout day, and a
    no-gap fill day. entry=near_level+1.40, breakout_low=near_level-0.50,
    ATR-leg=entry-1.60=near_level-0.20 -> stop=breakout_low (structural stop wins),
    stop_distance=1.90 -> ~20.5% of equity per position (tight enough that two
    same-day fills breach the 25% max-equity-deployed cap). `breakout_volume`
    defaults to 3x `volume` to clear MomentumScanner's relative-volume gate."""
    breakout_volume = volume * 3 if breakout_volume is None else breakout_volume
    bars = [
        DailyBar(
            symbol,
            start + timedelta(days=i),
            near_level,
            near_level + Decimal("0.40"),
            near_level - Decimal("0.40"),
            near_level,
            volume,
        )
        for i in range(pre_days)
    ]
    bars.append(
        DailyBar(
            symbol,
            start + timedelta(days=pre_days),
            near_level,
            near_level + Decimal("1.90"),
            near_level - Decimal("0.50"),
            near_level + Decimal("1.40"),
            breakout_volume,
        )
    )
    fill_price = near_level + Decimal("1.40")
    bars.append(
        DailyBar(
            symbol,
            start + timedelta(days=pre_days + 1),
            fill_price,
            fill_price + Decimal("0.10"),
            fill_price - Decimal("0.10"),
            fill_price,
            volume,
        )
    )
    return bars


def test_portfolio_replay_orders_same_day_entries_and_enforces_deployed_cap() -> None:
    """Scenario: Higher-momentum symbol fills first when capital admits only one.

    ALPHA and BRAVO share an identical near-term (last ~21 bars) price/ATR/stop shape
    -- so both size to the same ~20.5%-of-equity position -- but differ in their
    252-day-ago reference close, giving BRAVO a much higher 252/21-day momentum
    return. `len(w) > RANK_MOMENTUM_FAR(252)` here (253-bar window), so momentum
    ranking (not the short-history fallback) decides fill order.
    """
    start = date(2026, 1, 1)
    near_level = Decimal("110")
    far_days = 231  # bars 0..230 are the momentum far-reference window

    def _bars(symbol: str, far_close: Decimal) -> list[DailyBar]:
        far_bars = [
            DailyBar(
                symbol,
                start + timedelta(days=i),
                far_close,
                far_close + Decimal("0.40"),
                far_close - Decimal("0.40"),
                far_close,
                100,
            )
            for i in range(far_days)
        ]
        return far_bars + _tight_stop_bars(
            symbol, start + timedelta(days=far_days), pre_days=21, near_level=near_level
        )

    alpha_bars = _bars("ALPHA", far_close=Decimal("109"))  # momentum ~= 110/109 - 1 = 0.9%
    bravo_bars = _bars("BRAVO", far_close=Decimal("80"))  # momentum = 110/80 - 1 = 37.5%
    inputs = FixtureInputs(Universe("v1", ("ALPHA", "BRAVO")), tuple(alpha_bars + bravo_bars))

    result = _runner(inputs).replay(inputs)

    assert [trade.symbol for trade in result.trades] == ["BRAVO"]
    assert result.portfolio.open_position_count == 1
    assert result.gates.label == "portfolio-gates-simulated"
    assert result.gates.counts == {"max-equity-deployed": 1}
    assert result.skipped_entries[0].symbol == "ALPHA"
    assert result.skipped_entries[0].reason == "max-equity-deployed"


def test_portfolio_replay_short_history_same_day_fill_uses_liquidity_then_symbol() -> None:
    """Scenario (Benchmark-Strategy Interaction): with only ~21 bars of history
    (`len(w) <= RANK_MOMENTUM_FAR`), momentum/proximity fall back to 0 for both
    candidates, so fill order is decided by liquidity (descending) then symbol
    ascending -- NOT alphabetical. "AAA" sorts first alphabetically but has far
    lower dollar volume than "ZZZ", so "ZZZ" MUST fill first.
    """
    start = date(2026, 1, 1)
    low_liquidity = _tight_stop_bars("AAA", start, pre_days=20, near_level=Decimal("110"), volume=100)
    high_liquidity = _tight_stop_bars("ZZZ", start, pre_days=20, near_level=Decimal("110"), volume=100_000)
    inputs = FixtureInputs(Universe("v1", ("AAA", "ZZZ")), tuple(low_liquidity + high_liquidity))

    result = _runner(inputs).replay(inputs)

    assert [trade.symbol for trade in result.trades] == ["ZZZ"]
    assert result.skipped_entries[0].symbol == "AAA"
    assert result.skipped_entries[0].reason == "max-equity-deployed"


def _cooldown_fixture_bars(symbol: str, start: date) -> list[DailyBar]:
    """Breakout, fill, and hard-stop close (session T=day22, session-index 22),
    followed by flat bars so later re-signals have a stable non-degenerate entry."""
    bars = [
        DailyBar(symbol, start + timedelta(days=i), Decimal("10"), Decimal("10.40"), Decimal("9.60"), Decimal("10"), 100)
        for i in range(20)
    ]
    bars.append(
        DailyBar(symbol, start + timedelta(days=20), Decimal("10"), Decimal("11.50"), Decimal("10"), Decimal("11.40"), 250)
    )
    bars.append(
        DailyBar(
            symbol, start + timedelta(days=21), Decimal("11.40"), Decimal("11.50"), Decimal("11.30"), Decimal("11.40"), 100
        )
    )
    # day22: gap-down hard stop breach closes the day21 entry -> cooldown session T=22.
    bars.append(
        DailyBar(symbol, start + timedelta(days=22), Decimal("9.50"), Decimal("9.70"), Decimal("9.00"), Decimal("9.20"), 100)
    )
    for i in range(23, 40):
        bars.append(
            DailyBar(
                symbol, start + timedelta(days=i), Decimal("11.40"), Decimal("11.60"), Decimal("11.20"), Decimal("11.40"), 100
            )
        )
    return bars


def test_cooldown_blocks_reentry_for_ten_sessions_then_allows_at_eleven() -> None:
    """Scenario: Cooldown blocks re-entry within 10 sessions of any close.

    The day21 entry closes via hard stop on session T=day22 (session-index 22).
    Re-signals scheduled to be EVALUATED (fill-day gate check) at T+1 (day23) and
    T+10 (day32) must be skipped `cooldown-active`; a re-signal evaluated at T+11
    (day33) must be allowed to fill -- pinning the exact boundary the design
    flags as an open question (blocks sessions i+1..i+10 inclusive).
    """
    from invest.domain.models import ScanDecision

    start = date(2026, 1, 1)
    symbol = "CD"
    bars = _cooldown_fixture_bars(symbol, start)
    # Signal days chosen so their fill/gate-evaluation day lands on T+1, T+10, T+11:
    # signal day22 -> evaluated day23 (T+1); day31 -> evaluated day32 (T+10);
    # day32 -> evaluated day33 (T+11).
    signal_days = {20, 22, 31, 32}

    class ScheduledScanner(MomentumScanner):
        def scan(self, universe, bars_):  # type: ignore[override]
            current_day = max(bar.date for bar in bars_)
            for offset in signal_days:
                if current_day == start + timedelta(days=offset):
                    return [ScanDecision(symbol, current_day, True)]
            return []

    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))
    result = _runner(inputs, scanner=ScheduledScanner()).replay(inputs)

    cooldown_skips = [entry for entry in result.skipped_entries if entry.reason == "cooldown-active"]
    assert [entry.decision_date for entry in cooldown_skips] == [
        start + timedelta(days=22),  # evaluated at T+1 (day23)
        start + timedelta(days=31),  # evaluated at T+10 (day32)
    ]
    assert result.gates.counts["cooldown-active"] == 2
    assert [(trade.entry_date, trade.exit_reason) for trade in result.trades] == [
        (start + timedelta(days=21), "stop"),
        (start + timedelta(days=33), "open-at-end"),  # T+11 re-entry allowed
    ]


def test_ordinary_stop_during_transient_block_starts_cooldown() -> None:
    """A transient context block does not change ordinary stop/cooldown behavior.

    The position closes through its hard stop on session T=day22. A re-signal
    evaluated within 10 sessions (T+8, day30) remains `cooldown-active`.
    """
    from invest.domain.models import ScanDecision

    start = date(2026, 1, 1)
    symbol = "FC"
    blocked_stop_day = start + timedelta(days=22)
    bars = _cooldown_fixture_bars(symbol, start)
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))
    context = _context_for_inputs(
        inputs,
        blockers_by_symbol={
            symbol: (BlockerWindow(blocked_stop_day, blocked_stop_day, reason=ContextReason.CORPORATE_ACTION),)
        },
    )
    signal_days = {20, 29}  # day20 initial breakout; day29 -> evaluated day30 (T+8)

    class ScheduledScanner(MomentumScanner):
        def scan(self, universe, bars_):  # type: ignore[override]
            current_day = max(bar.date for bar in bars_)
            for offset in signal_days:
                if current_day == start + timedelta(days=offset):
                    return [ScanDecision(symbol, current_day, True)]
            return []

    result = _runner(inputs, scanner=ScheduledScanner(), market_context=context).replay(inputs)

    assert result.trades[0].exit_reason == "stop"
    assert result.trades[0].exit_date == blocked_stop_day
    cooldown_skips = [entry for entry in result.skipped_entries if entry.reason == "cooldown-active"]
    assert cooldown_skips == [SkippedEntry(symbol, start + timedelta(days=29), start + timedelta(days=30), "cooldown-active")]


def test_scan_decisions_ignores_cooldown_state() -> None:
    """Scenario: scan_decisions() remains unaffected by cooldown.

    A symbol inside its post-close cooldown window must still be evaluated (and
    collected if accepted) by the position-blind `scan_decisions()` collector,
    exactly as if no cooldown were active -- cooldown state is a `replay()`-local
    concept the collector never reads or writes.
    """
    from invest.domain.models import ScanDecision

    start = date(2026, 1, 1)
    symbol = "CD"
    bars = _cooldown_fixture_bars(symbol, start)
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))
    signal_days = {20, 22, 25}  # day22 closes the day21 entry; day25 is well inside the cooldown window

    class ScheduledScanner(MomentumScanner):
        def scan(self, universe, bars_):  # type: ignore[override]
            current_day = max(bar.date for bar in bars_)
            for offset in signal_days:
                if current_day == start + timedelta(days=offset):
                    return [ScanDecision(symbol, current_day, True)]
            return []

    runner = _runner(inputs, scanner=ScheduledScanner())
    decisions = runner.scan_decisions(inputs)
    result = runner.replay(inputs)

    # scan_decisions() collects every accepted decision, regardless of cooldown state.
    assert {decision.decision_date for decision in decisions} == {
        start + timedelta(days=20),
        start + timedelta(days=22),
        start + timedelta(days=25),
    }
    # replay(), by contrast, blocks the day25 candidate's fill (day26 evaluation, T+4).
    cooldown_skips = [entry for entry in result.skipped_entries if entry.reason == "cooldown-active"]
    assert start + timedelta(days=25) in {entry.decision_date for entry in cooldown_skips}


def test_same_day_round_trip_close_starts_cooldown() -> None:
    """RELIABILITY-001 regression: a position that opens AND closes on the same day
    (same-day stop-out via `_exit_for_bar`) must still start the cooldown.

    The cooldown-recording loop runs at the TOP of each day's iteration (it must
    stay there -- it also blocks same-day re-entry after a morning exit), but a
    same-day close is appended to `trades` LATER in that same iteration (inside
    the pending-entries loop), after that day's cooldown snapshot was already
    taken -- so the close was never recorded as a cooldown source.
    """
    from invest.domain.models import ScanDecision

    start = date(2026, 1, 1)
    symbol = "SD"
    bars = [
        DailyBar(symbol, start + timedelta(days=i), Decimal("10"), Decimal("10.40"), Decimal("9.60"), Decimal("10"), 100)
        for i in range(20)
    ]
    bars.append(
        DailyBar(symbol, start + timedelta(days=20), Decimal("10"), Decimal("11.50"), Decimal("10"), Decimal("11.40"), 250)
    )
    # day21: fill day's own low also breaches the stop -> same-day round trip close.
    bars.append(
        DailyBar(symbol, start + timedelta(days=21), Decimal("11.40"), Decimal("11.50"), Decimal("9.50"), Decimal("10.00"), 100)
    )
    for i in range(22, 40):
        bars.append(
            DailyBar(
                symbol, start + timedelta(days=i), Decimal("11.40"), Decimal("11.60"), Decimal("11.20"), Decimal("11.40"), 100
            )
        )

    # day20 initial breakout; day22 -> evaluated day23 (T+2, must be cooldown-blocked);
    # day30 -> evaluated day31 (T+10, the last blocked session);
    # day31 -> evaluated day32 (T+11, must be eligible again).
    signal_days = {20, 22, 30, 31}

    class ScheduledScanner(MomentumScanner):
        def scan(self, universe, bars_):  # type: ignore[override]
            current_day = max(bar.date for bar in bars_)
            for offset in signal_days:
                if current_day == start + timedelta(days=offset):
                    return [ScanDecision(symbol, current_day, True)]
            return []

    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))
    result = _runner(inputs, scanner=ScheduledScanner()).replay(inputs)

    same_day_trade = next(trade for trade in result.trades if trade.entry_date == start + timedelta(days=21))
    assert same_day_trade.exit_date == start + timedelta(days=21)
    assert same_day_trade.exit_reason == "stop"

    cooldown_skips = {entry.decision_date for entry in result.skipped_entries if entry.reason == "cooldown-active"}
    assert start + timedelta(days=22) in cooldown_skips
    assert start + timedelta(days=30) in cooldown_skips
    assert any(trade.entry_date == start + timedelta(days=32) for trade in result.trades)


def test_portfolio_replay_records_insufficient_buying_power_as_visible_skip() -> None:
    # entry=11.40, qty=218 -> notional ~2485.20; buying_power set below that.
    start = date(2026, 1, 1)
    bars = _breakout_bars("CASH", start, extra_days=1)
    inputs = FixtureInputs(Universe("v1", ("CASH",)), tuple(bars))

    result = _runner(inputs, equity=Decimal("100000"), buying_power=Decimal("2000")).replay(inputs)

    assert result.trades == ()
    assert result.gates.counts == {"insufficient-buying-power": 1}
    assert result.skipped_entries[0].symbol == "CASH"
    assert result.skipped_entries[0].reason == "insufficient-buying-power"


def test_portfolio_replay_releases_cash_on_exit_and_uses_prior_equity_for_kill_switch() -> None:
    """0.35%-risk sizing caps a normal-stop loss around ~2.5% of equity, too small to
    breach the -3% kill-switch on its own -- so this fixture uses a wide structural
    stop (tight ATR, low breakout_low) to raise qty enough that a catastrophic gap
    breaches the kill-switch threshold, matching the original scenario's intent."""
    from invest.domain.models import ScanDecision

    start = date(2026, 1, 1)
    loss_bars = [
        DailyBar("LOSS", start + timedelta(days=i), Decimal("100"), Decimal("100.10"), Decimal("99.90"), Decimal("100"), 1000)
        for i in range(20)
    ]
    loss_bars.append(
        DailyBar("LOSS", start + timedelta(days=20), Decimal("100"), Decimal("105"), Decimal("99"), Decimal("104"), 2000)
    )
    loss_bars.append(
        DailyBar("LOSS", start + timedelta(days=21), Decimal("104"), Decimal("104.20"), Decimal("103.80"), Decimal("104"), 100)
    )
    loss_bars.append(
        DailyBar("LOSS", start + timedelta(days=22), Decimal("1"), Decimal("2"), Decimal("0.50"), Decimal("1"), 100)
    )
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
    assert result.trades[0].qty == 70  # risk_capital=350, stop_distance=5.00 -> floor(350/5)=70
    assert result.trades[0].exit_price == Decimal("1")  # min(open=1, stop=99) since breakout_low=99 wins
    assert result.portfolio.cash == Decimal("92786.3250")
    assert result.gates.counts == {"kill-switch": 1}
    assert result.skipped_entries[0].symbol == "NEXT"


def test_portfolio_cash_and_equity_use_configured_entry_slippage() -> None:
    start = date(2026, 1, 1)
    bars = _breakout_bars("COST", start, extra_days=1)
    inputs = FixtureInputs(Universe("v1", ("COST",)), tuple(bars))

    result = _runner(inputs, slippage_bps=Decimal("100"), tax_rate=Decimal("0")).replay(inputs)

    assert result.portfolio.cash == Decimal("97489.9480")
    assert result.portfolio.equity == Decimal("99950.2960")


def test_permanently_missing_open_position_bar_fails_closed() -> None:
    from invest.application.backtest_run import ReplayWindowInvalidError
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

    with pytest.raises(ReplayWindowInvalidError) as error:
        _runner(inputs, scanner=GapSignalScanner()).replay(inputs)

    assert str(error.value) == (
        "open position GAP last trustworthy bar 2026-01-22 "
        "predates replay end 2026-01-23"
    )


def test_transient_missing_position_bar_resumes_without_forced_liquidation() -> None:
    from invest.domain.models import ScanDecision

    start = date(2026, 1, 1)
    missing_date = start + timedelta(days=22)
    gap_bars = _breakout_bars("GAP", start, extra_days=4)
    clock_bar = DailyBar(
        "CLOCK",
        missing_date,
        Decimal("10"),
        Decimal("10"),
        Decimal("10"),
        Decimal("10"),
        100,
    )

    class GapSignalScanner(MomentumScanner):
        def scan(self, universe, bars):  # type: ignore[override]
            current_day = max(bar.date for bar in bars)
            return (
                [ScanDecision("GAP", current_day, True)]
                if current_day == start + timedelta(days=20)
                else []
            )

    inputs = FixtureInputs(
        Universe("v1", ("GAP", "CLOCK")),
        tuple(bar for bar in gap_bars if bar.date != missing_date) + (clock_bar,),
    )

    result = _runner(inputs, scanner=GapSignalScanner()).replay(inputs)

    assert result.trades[0].exit_reason == "open-at-end"
    assert result.trades[0].exit_date == start + timedelta(days=24)
    assert "missing-bar-carried-forward" in result.warnings


def test_entry_gap_is_rejected_when_actual_next_open_cost_exceeds_cash() -> None:
    start = date(2026, 1, 1)
    bars = _breakout_bars("GAP", start, extra_days=1)
    entry_day = start + timedelta(days=21)
    bars[-1] = DailyBar("GAP", entry_day, Decimal("12"), Decimal("12.10"), Decimal("11.90"), Decimal("12"), 100)
    inputs = FixtureInputs(Universe("v1", ("GAP",)), tuple(bars))

    # gapped entry=12.00, qty=175 -> notional=2100; buying_power set below that.
    result = _runner(inputs, buying_power=Decimal("2000")).replay(inputs)

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

    assert [(trade.entry_date, trade.qty) for trade in result.trades] == [(start + timedelta(days=21), 218)]
    assert result.portfolio.cash == Decimal("97513.557400")
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


def test_pending_entry_fails_closed_when_symbol_becomes_ineligible_on_fill_day() -> None:
    start = date(2026, 1, 1)
    symbol = "ENTRY-INELIGIBLE"
    signal_day = start + timedelta(days=20)
    entry_day = start + timedelta(days=21)
    bars = _breakout_bars(symbol, start, extra_days=1)
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))
    context = _context_for_inputs(
        inputs,
        eligibility_by_symbol={
            symbol: (
                EligibilityWindow(start, signal_day, eligible=True),
                EligibilityWindow(entry_day, entry_day, eligible=False),
            )
        },
    )

    result = _runner(inputs, market_context=context).replay(inputs)

    assert result.trades == ()
    assert result.context_outcomes == (
        ContextOutcome(
            outcome_type=ContextOutcomeType.ENTRY_BLOCKED,
            reason=ContextReason.SYMBOL_INELIGIBLE,
            symbol=symbol,
            date=entry_day,
        ),
    )
    assert result.gates.counts == {}


def test_open_position_carries_through_corporate_action_and_exits_normally_later() -> None:
    start = date(2026, 1, 1)
    bars = _breakout_bars("HOLD", start)
    entry_day = start + timedelta(days=21)
    blocked_day = start + timedelta(days=22)
    stop_day = start + timedelta(days=23)
    bars.append(DailyBar("HOLD", entry_day, Decimal("11.40"), Decimal("11.50"), Decimal("11.30"), Decimal("11.40"), 100))
    bars.append(DailyBar("HOLD", blocked_day, Decimal("11.40"), Decimal("11.50"), Decimal("11.20"), Decimal("11.40"), 100))
    bars.append(DailyBar("HOLD", stop_day, Decimal("9.50"), Decimal("9.70"), Decimal("9.00"), Decimal("9.20"), 100))
    inputs = FixtureInputs(Universe("v1", ("HOLD",)), tuple(bars))
    context = _context_for_inputs(
        inputs,
        blockers_by_symbol={
            "HOLD": (
                BlockerWindow(blocked_day, blocked_day, reason=ContextReason.CORPORATE_ACTION),
            )
        },
    )

    result = _runner(inputs, market_context=context).replay(inputs)

    assert result.trades[0].exit_reason == "stop"
    assert result.trades[0].exit_date == stop_day
    assert result.trades[0].exit_price == Decimal("9.50")
    assert result.context_outcomes == ()


def test_open_position_carries_through_temporary_ineligibility_until_bars_resume() -> None:
    start = date(2026, 1, 1)
    symbol = "RESUME"
    entry_day = start + timedelta(days=21)
    ineligible_day = start + timedelta(days=22)
    resumed_day = start + timedelta(days=23)
    bars = _breakout_bars(symbol, start)
    bars.append(
        DailyBar(
            symbol,
            entry_day,
            Decimal("11.40"),
            Decimal("11.50"),
            Decimal("11.30"),
            Decimal("11.40"),
            100,
        )
    )
    bars.append(
        DailyBar(
            symbol,
            ineligible_day,
            Decimal("11.40"),
            Decimal("11.50"),
            Decimal("11.20"),
            Decimal("11.40"),
            100,
        )
    )
    bars.append(
        DailyBar(
            symbol,
            resumed_day,
            Decimal("9.50"),
            Decimal("9.70"),
            Decimal("9.00"),
            Decimal("9.20"),
            100,
        )
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))
    context = _context_for_inputs(
        inputs,
        eligibility_by_symbol={
            symbol: (
                EligibilityWindow(start, entry_day, eligible=True),
                EligibilityWindow(ineligible_day, ineligible_day, eligible=False),
                EligibilityWindow(resumed_day, resumed_day, eligible=True),
            )
        },
    )

    result = _runner(inputs, market_context=context).replay(inputs)

    assert result.trades[0].exit_reason == "stop"
    assert result.trades[0].exit_date == resumed_day
    assert result.context_outcomes == ()


def test_ineligibility_without_terminal_evidence_carries_position_to_end_of_run() -> None:
    start = date(2026, 1, 1)
    symbol = "NO-TERMINAL-EVIDENCE"
    entry_day = start + timedelta(days=21)
    ineligible_start = start + timedelta(days=22)
    final_day = start + timedelta(days=23)
    bars = _breakout_bars(symbol, start)
    for current_date in (entry_day, ineligible_start, final_day):
        bars.append(
            DailyBar(
                symbol,
                current_date,
                Decimal("11.40"),
                Decimal("11.50"),
                Decimal("11.20"),
                Decimal("11.40"),
                100,
            )
        )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))
    context = _context_for_inputs(
        inputs,
        eligibility_by_symbol={
            symbol: (
                EligibilityWindow(start, entry_day, eligible=True),
                EligibilityWindow(ineligible_start, final_day, eligible=False),
            )
        },
    )

    result = _runner(inputs, market_context=context).replay(inputs)

    assert result.trades[0].exit_reason == "open-at-end"
    assert result.trades[0].exit_date == final_day
    assert result.context_outcomes == ()


def test_carried_position_remains_deployed_while_pending_entry_uses_cash_and_equity() -> None:
    from invest.domain.models import ScanDecision

    start = date(2026, 1, 1)
    entry_day = start + timedelta(days=21)
    blocked_day = start + timedelta(days=22)
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
        blocked_day,
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
                    blocked_day,
                    blocked_day,
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
        ("HOLD", "open-at-end", 32),
        ("NEXT", "open-at-end", 31),
    ]
    assert result.skipped_entries == ()
    assert result.gates.counts == {}
    assert result.context_outcomes == ()
    assert result.portfolio.cash == Decimal("14307.40")
    assert result.portfolio.equity == Decimal("15025.60")


def test_context_block_does_not_authorize_terminal_position_liquidation() -> None:
    from invest.application.backtest_run import ReplayWindowInvalidError
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

    with pytest.raises(ReplayWindowInvalidError):
        _runner(inputs, scanner=GapSignalScanner(), market_context=context).replay(inputs)


def test_atr_exit_policy_can_produce_atr_trail_next_open_fill() -> None:
    from invest.domain.exit_policy import ExitPolicyConfig, KIND_ATR_3_HIGH_WATER

    start = date(2026, 1, 1)
    symbol = "ATR"
    bars = _breakout_bars(symbol, start)
    # Entry day 21
    bars.append(
        DailyBar(symbol, start + timedelta(days=21), Decimal("11.40"), Decimal("11.50"), Decimal("11.30"), Decimal("11.40"), 100)
    )
    # Raise the high-water below the take-profit and use a tight ATR trail so it arms.
    bars.append(
        DailyBar(symbol, start + timedelta(days=22), Decimal("11.40"), Decimal("12.90"), Decimal("11.20"), Decimal("12.00"), 100)
    )
    # Next session open is the next-open fill if day-22 armed atr-trail
    fill_day = start + timedelta(days=23)
    bars.append(
        DailyBar(symbol, fill_day, Decimal("15.00"), Decimal("16.00"), Decimal("11.00"), Decimal("11.50"), 100)
    )
    bars.append(
        DailyBar(
            symbol, start + timedelta(days=24), Decimal("11.20"), Decimal("11.40"), Decimal("11.00"), Decimal("11.30"), 100
        )
    )
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))
    config = ExitPolicyConfig(kind=KIND_ATR_3_HIGH_WATER, atr_mult=Decimal("0.5"))

    trades = _runner(inputs, exit_policy=config).replay(inputs).trades

    assert len(trades) == 1
    assert trades[0].exit_reason == "atr-trail"
    assert trades[0].exit_price == Decimal("15.00")  # raw next open after signal
    assert trades[0].exit_date == fill_day


def test_replay_records_exit_policy_provenance_for_both_kinds() -> None:
    from invest.domain.exit_policy import ExitPolicyConfig, KIND_ATR_3_HIGH_WATER, KIND_TEN_DAY_LOW

    start = date(2026, 1, 1)
    bars = _breakout_bars("META", start, extra_days=1)
    inputs = FixtureInputs(Universe("v1", ("META",)), tuple(bars))

    channel = _runner(inputs, exit_policy=ExitPolicyConfig(kind=KIND_TEN_DAY_LOW)).replay(inputs)
    atr = _runner(inputs, exit_policy=ExitPolicyConfig(kind=KIND_ATR_3_HIGH_WATER)).replay(inputs)

    assert channel.exit_policy["kind"] == KIND_TEN_DAY_LOW
    assert atr.exit_policy["kind"] == KIND_ATR_3_HIGH_WATER
    assert channel.exit_policy["channel_window"] == 10
    assert atr.exit_policy["atr_mult"] == "3"
    assert list(channel.exit_policy.keys()) == sorted(channel.exit_policy.keys())


def test_mutating_future_bars_does_not_change_day_n_exit_under_atr_policy() -> None:
    from invest.domain.exit_policy import ExitPolicyConfig, KIND_ATR_3_HIGH_WATER

    start = date(2026, 1, 1)
    symbol = "NOLAATR"
    bars = _breakout_bars(symbol, start)
    bars.append(
        DailyBar(symbol, start + timedelta(days=21), Decimal("11.40"), Decimal("11.50"), Decimal("11.30"), Decimal("11.40"), 100)
    )
    bars.append(
        DailyBar(symbol, start + timedelta(days=22), Decimal("11.40"), Decimal("12.90"), Decimal("11.20"), Decimal("12.00"), 100)
    )
    fill_day = start + timedelta(days=23)
    bars.append(
        DailyBar(symbol, fill_day, Decimal("15.00"), Decimal("16.00"), Decimal("11.00"), Decimal("11.50"), 100)
    )
    bars.append(
        DailyBar(
            symbol, start + timedelta(days=24), Decimal("11.20"), Decimal("11.40"), Decimal("11.00"), Decimal("11.30"), 100
        )
    )
    bars.append(
        DailyBar(symbol, start + timedelta(days=25), Decimal("50"), Decimal("60"), Decimal("40"), Decimal("55"), 999)
    )
    inputs_before = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))
    config = ExitPolicyConfig(kind=KIND_ATR_3_HIGH_WATER, atr_mult=Decimal("0.5"))
    exit_before = _runner(inputs_before, exit_policy=config).replay(inputs_before).trades[0]
    assert exit_before.exit_date == fill_day
    assert exit_before.exit_reason == "atr-trail"

    corrupted = list(bars)
    for index, bar in enumerate(corrupted):
        if bar.date > fill_day:
            corrupted[index] = DailyBar(
                symbol, bar.date, Decimal("9999"), Decimal("10000"), Decimal("1"), Decimal("9999"), 999999
            )
    inputs_after = FixtureInputs(Universe("v1", (symbol,)), tuple(corrupted))
    exit_after = _runner(inputs_after, exit_policy=config).replay(inputs_after).trades[0]

    assert exit_after == exit_before


def test_replaying_same_range_twice_is_byte_identical_for_atr_policy() -> None:
    from invest.domain.exit_policy import ExitPolicyConfig, KIND_ATR_3_HIGH_WATER

    start = date(2026, 1, 1)
    symbol = "TWINATR"
    bars = _breakout_bars(symbol, start, extra_days=5)
    inputs = FixtureInputs(Universe("v1", (symbol,)), tuple(bars))
    config = ExitPolicyConfig(kind=KIND_ATR_3_HIGH_WATER)

    first = _runner(inputs, exit_policy=config).replay(inputs)
    second = _runner(inputs, exit_policy=config).replay(inputs)

    assert first == second
