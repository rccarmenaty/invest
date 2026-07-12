"""Day-by-day replay harness: proves scanner/sizing edge without look-ahead.

Design (openspec/changes/backtest-replay/design.md): the harness holds the full
sorted bar history and, for each trading day `d`, slices a window of bars dated
`<= d` before calling the UNCHANGED `MomentumScanner.scan()`. Bars dated after
`d` are physically absent from that call, so no future data can influence day
`d`'s decision -- look-ahead is prevented structurally by the window, not by
any scanner change. See `tests/application/test_backtest_run.py`'s killer test.

Portfolio construction (`evaluate_gates`, concurrency/equity caps) is
deliberately NOT simulated here (reconcile item 4): every accepted signal is
sized independently at a fixed nominal equity to isolate scanner+sizing edge,
not portfolio construction.
"""

from collections import defaultdict
from decimal import Decimal

from invest.domain.models import DailyBar, FixtureInputs, ScanDecision, SimulatedTrade
from invest.domain.scanner import MomentumScanner
from invest.domain.sizing import compute_intent

NOMINAL_EQUITY = Decimal("100000")


class BacktestRun:
    def __init__(self, *, scanner: MomentumScanner | None = None, equity: Decimal = NOMINAL_EQUITY) -> None:
        self._scanner = scanner or MomentumScanner()
        self._equity = equity

    def scan_decisions(self, inputs: FixtureInputs) -> list[ScanDecision]:
        """Replay day-by-day, collecting every ACCEPTED decision recorded on its own day.

        A decision is only collected when `decision.decision_date == d`: since the
        scanner's candidate bar is always `window[-1]`, this fires exactly once per
        symbol per day, the day its bar first enters the window.
        """
        bars = sorted(inputs.bars, key=lambda bar: (bar.date, bar.symbol))
        dates = sorted({bar.date for bar in bars})
        collected: list[ScanDecision] = []
        for d in dates:
            window = tuple(bar for bar in bars if bar.date <= d)
            for decision in self._scanner.scan(inputs.universe, window):
                if decision.accepted and decision.decision_date == d:
                    collected.append(decision)
        return collected

    def replay(self, inputs: FixtureInputs) -> list[SimulatedTrade]:
        decisions = self.scan_decisions(inputs)
        by_symbol: dict[str, list[DailyBar]] = defaultdict(list)
        for bar in sorted(inputs.bars, key=lambda item: (item.symbol, item.date)):
            by_symbol[bar.symbol].append(bar)

        trades: list[SimulatedTrade] = []
        for decision in decisions:
            trade = self._simulate_trade(decision.symbol, decision.decision_date, by_symbol[decision.symbol])
            if trade is not None:
                trades.append(trade)
        return trades

    def _simulate_trade(
        self, symbol: str, signal_date, symbol_bars: list[DailyBar]
    ) -> SimulatedTrade | None:
        signal_index = next(index for index, bar in enumerate(symbol_bars) if bar.date == signal_date)
        if signal_index + 1 >= len(symbol_bars):
            return None  # no next-session bar to enter on

        history = symbol_bars[:signal_index]
        signal_bar = symbol_bars[signal_index]
        intent, sizing_reason = compute_intent(symbol, signal_date, self._equity, history, signal_bar.close)
        if intent is None or sizing_reason is not None:
            return None

        entry_bar = symbol_bars[signal_index + 1]
        entry_date = entry_bar.date
        entry_price = entry_bar.open

        for bar in symbol_bars[signal_index + 1 :]:
            stop_touched = bar.low <= intent.stop
            take_profit_touched = bar.high >= intent.take_profit
            if stop_touched:
                # Same-bar tie (both stop and take-profit touched intraday): STOP WINS.
                # Conservative, deterministic tie-break -- with OHLC-only data we cannot
                # know the intrabar sequencing, so we never over-credit a favorable
                # outcome when both levels were touched on the same bar.
                exit_price = min(bar.open, intent.stop)
                return SimulatedTrade(symbol, entry_date, bar.date, entry_price, exit_price, intent.qty, "stop")
            if take_profit_touched:
                return SimulatedTrade(
                    symbol, entry_date, bar.date, entry_price, intent.take_profit, intent.qty, "take-profit"
                )

        last_bar = symbol_bars[-1]
        return SimulatedTrade(symbol, entry_date, last_bar.date, entry_price, last_bar.close, intent.qty, "open-at-end")
