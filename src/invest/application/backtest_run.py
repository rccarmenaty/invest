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

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from invest.domain.backtest_metrics import (
    DEFAULT_SLIPPAGE_BPS,
    DEFAULT_TAX_RATE,
    compute_equity_summary,
    compute_metrics,
    compute_segment_metrics,
    entry_fill,
    exit_proceeds,
)
from invest.domain.exit_policy import (
    ExitPolicyConfig,
    ExitPolicyState,
    initial_state,
    on_bar,
    policy_provenance,
)
from invest.domain.market_context import (
    ContextOutcome,
    ContextOutcomeType,
    MarketContext,
    MarketContextIncompleteError,
)
from invest.domain.models import (
    AccountSnapshot,
    BacktestResult,
    DailyBar,
    FixtureInputs,
    GateTelemetry,
    PortfolioSummary,
    ScanDecision,
    SimulatedTrade,
    SkippedEntry,
    Universe,
)
from invest.domain.scanner import MomentumScanner
from invest.domain.sizing import GateReason, compute_intent, evaluate_gates, evaluate_halt_gates
from invest.application.ports import ScannerPort

NOMINAL_EQUITY = Decimal("100000")
POINT_IN_TIME_CONTEXT_VALIDATED = "point-in-time-market-context-validated"
MISSING_NEXT_SESSION_AFTER_EXIT_SIGNAL = "missing-next-session-after-exit-signal"
DEFAULT_EXIT_POLICY = ExitPolicyConfig(kind="ten-day-low", channel_window=10)


@dataclass
class _OpenPosition:
    symbol: str
    entry_date: date
    entry_price: Decimal
    qty: int
    entry_fill: Decimal
    marked_value: Decimal
    policy: ExitPolicyState


class BacktestRun:
    def __init__(
        self,
        *,
        market_context: MarketContext,
        scanner: ScannerPort | None = None,
        equity: Decimal = NOMINAL_EQUITY,
        cash: Decimal | None = None,
        buying_power: Decimal | None = None,
        slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
        tax_rate: Decimal = DEFAULT_TAX_RATE,
        exit_policy: ExitPolicyConfig | None = None,
    ) -> None:
        self._market_context = market_context
        self._scanner = scanner or MomentumScanner()
        self._equity = equity
        self._cash = equity if cash is None else cash
        self._buying_power = buying_power
        self._slippage_bps = slippage_bps
        self._tax_rate = tax_rate
        self._exit_policy = exit_policy if exit_policy is not None else DEFAULT_EXIT_POLICY

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
            replay_universe = self._filtered_universe(inputs.universe, d)
            eligible_symbols = set(replay_universe.symbols)
            window = tuple(bar for bar in bars if bar.date <= d and bar.symbol in eligible_symbols)
            for decision in self._scanner.scan(replay_universe, window):
                if decision.accepted and decision.decision_date == d:
                    collected.append(decision)
        return collected

    def replay(self, inputs: FixtureInputs, *, split_date: date | None = None) -> BacktestResult:
        replay_dates = sorted({bar.date for bar in inputs.bars})
        self._market_context.require_complete(replay_dates, inputs.universe.symbols)
        decisions = self.scan_decisions(inputs)
        by_symbol: dict[str, list[DailyBar]] = defaultdict(list)
        for bar in sorted(inputs.bars, key=lambda item: (item.symbol, item.date)):
            by_symbol[bar.symbol].append(bar)

        bars_by_date: dict[date, dict[str, DailyBar]] = defaultdict(dict)
        for bar in inputs.bars:
            bars_by_date[bar.date][bar.symbol] = bar
        pending: dict[date, list[ScanDecision]] = defaultdict(list)
        for decision in decisions:
            symbol_bars = by_symbol[decision.symbol]
            signal_index = next(index for index, bar in enumerate(symbol_bars) if bar.date == decision.decision_date)
            if signal_index + 1 < len(symbol_bars):
                pending[symbol_bars[signal_index + 1].date].append(decision)

        trades: list[SimulatedTrade] = []
        skipped_entries: list[SkippedEntry] = []
        context_outcomes: list[ContextOutcome] = []
        gate_counts: Counter[str] = Counter()
        positions: dict[str, _OpenPosition] = {}
        cash = self._cash
        previous_equity = self._equity
        daily_equity: list[tuple[date, Decimal]] = []
        missing_bar_carried_forward = False
        exit_warnings: list[str] = []

        for current_date in sorted(bars_by_date):
            todays_bars = bars_by_date[current_date]
            self._process_unsafe_positions(current_date, positions, todays_bars, trades, context_outcomes)
            cash = self._settle_closed_positions(current_date, positions, trades, cash)
            self._process_exits(positions, todays_bars, trades, by_symbol)
            cash = self._settle_closed_positions(current_date, positions, trades, cash)

            missing_bar_carried_forward |= any(symbol not in todays_bars for symbol in positions)
            marked_equity = cash + self._mark_positions(positions, todays_bars)
            deployed = sum(position.entry_fill * position.qty for position in positions.values())
            snapshot = AccountSnapshot(
                equity=marked_equity,
                last_equity=previous_equity,
                buying_power=cash if self._buying_power is None else min(cash, self._buying_power),
                open_position_count=len(positions),
                deployed_value=deployed,
                trading_blocked=False,
                account_blocked=False,
            )
            halt_reason = evaluate_halt_gates(snapshot)
            for decision in sorted(pending[current_date], key=lambda item: item.symbol):
                if decision.symbol in positions:
                    gate_counts[GateReason.ALREADY_SUBMITTED.value] += 1
                    skipped_entries.append(
                        SkippedEntry(
                            decision.symbol,
                            decision.decision_date,
                            current_date,
                            GateReason.ALREADY_SUBMITTED.value,
                        )
                    )
                    continue
                status = self._market_context.status(decision.symbol, current_date)
                if not status.is_safe:
                    context_outcomes.append(
                        ContextOutcome.from_status(status, ContextOutcomeType.ENTRY_BLOCKED)
                    )
                    continue
                entry_bar = todays_bars[decision.symbol]
                symbol_bars = by_symbol[decision.symbol]
                signal_index = next(index for index, bar in enumerate(symbol_bars) if bar.date == decision.decision_date)
                intent, sizing_reason = compute_intent(
                    decision.symbol,
                    decision.decision_date,
                    marked_equity,
                    symbol_bars[:signal_index],
                    symbol_bars[signal_index].close,
                )
                adjusted_intent = (
                    None if intent is None else replace(intent, entry=entry_fill(entry_bar.open, self._slippage_bps))
                )
                reason = halt_reason or evaluate_gates(
                    adjusted_intent,
                    sizing_reason,
                    snapshot,
                    len(positions),
                    deployed,
                    cash if self._buying_power is None else min(cash, self._buying_power),
                )
                if reason is not None:
                    gate_counts[reason.value] += 1
                    skipped_entries.append(
                        SkippedEntry(decision.symbol, decision.decision_date, current_date, reason.value)
                    )
                    continue
                assert intent is not None
                raw_entry = entry_bar.open  # SimulatedTrade.entry_price is RAW; metrics apply entry_fill once
                slipped_entry = entry_fill(raw_entry, self._slippage_bps)
                entry_cost = intent.qty * slipped_entry
                cash -= entry_cost
                # Backtest ignores OrderIntent.take_profit for exits; hard stop uses intent.stop.
                position = _OpenPosition(
                    symbol=decision.symbol,
                    entry_date=current_date,
                    entry_price=raw_entry,
                    qty=intent.qty,
                    entry_fill=slipped_entry,
                    marked_value=entry_cost,
                    policy=initial_state(initial_stop=intent.stop, entry_price=raw_entry),
                )
                positions[decision.symbol] = position
                deployed += entry_cost
                history_through = [bar for bar in by_symbol[decision.symbol] if bar.date <= current_date]
                closed = self._exit_for_bar(position, entry_bar, history_through)
                if closed is not None:
                    trades.append(closed)
                    cash += exit_proceeds(
                        position.entry_price,
                        closed.exit_price,
                        closed.qty,
                        self._slippage_bps,
                        self._tax_rate,
                    )
                    positions.pop(closed.symbol)
            marked_equity = cash + self._mark_positions(positions, todays_bars)
            daily_equity.append((current_date, marked_equity))
            previous_equity = marked_equity

        for position in sorted(positions.values(), key=lambda item: item.symbol):
            last_bar = by_symbol[position.symbol][-1]
            if position.policy.pending_exit_reason is not None:
                exit_warnings.append(MISSING_NEXT_SESSION_AFTER_EXIT_SIGNAL)
            trades.append(
                SimulatedTrade(
                    symbol=position.symbol,
                    entry_date=position.entry_date,
                    exit_date=last_bar.date,
                    entry_price=position.entry_price,
                    exit_price=last_bar.close,
                    qty=position.qty,
                    exit_reason="open-at-end",
                )
            )
        ordered_trades = tuple(sorted(trades, key=lambda trade: (trade.entry_date, trade.symbol, trade.exit_date)))
        metrics = compute_metrics(list(ordered_trades), self._slippage_bps, self._tax_rate)
        base_warnings = (
            "portfolio-gates-simulated",
            POINT_IN_TIME_CONTEXT_VALIDATED,
            "broker-execution-realism-out-of-scope",
        )
        extra_warnings: list[str] = []
        if missing_bar_carried_forward:
            extra_warnings.append("missing-bar-carried-forward")
        # Deduplicate exit warnings while preserving stable order
        for warning in exit_warnings:
            if warning not in extra_warnings:
                extra_warnings.append(warning)
        return BacktestResult(
            trades=ordered_trades,
            skipped_entries=tuple(skipped_entries),
            context_outcomes=tuple(context_outcomes),
            metrics=metrics,
            portfolio=PortfolioSummary(
                starting_capital=self._equity,
                cash=cash,
                equity=daily_equity[-1][1] if daily_equity else self._equity,
                open_position_count=len(positions),
                deployed_capital=sum(position.entry_fill * position.qty for position in positions.values()),
                closed_trade_count=len([trade for trade in ordered_trades if trade.exit_reason != "open-at-end"]),
            ),
            gates=GateTelemetry("portfolio-gates-simulated", dict(sorted(gate_counts.items()))),
            equity_summary=compute_equity_summary(daily_equity),
            segments=(
                compute_segment_metrics(list(ordered_trades), split_date, self._slippage_bps, self._tax_rate)
                if split_date
                else {}
            ),
            warnings=base_warnings + tuple(extra_warnings),
            exit_policy=policy_provenance(self._exit_policy),
        )

    def _filtered_universe(self, universe: Universe, as_of: date) -> Universe:
        return Universe(
            fixture_version=universe.fixture_version,
            symbols=self._market_context.eligible_symbols(universe.symbols, as_of),
        )

    def _process_unsafe_positions(
        self,
        current_date: date,
        positions: dict[str, _OpenPosition],
        bars: dict[str, DailyBar],
        trades: list[SimulatedTrade],
        context_outcomes: list[ContextOutcome],
    ) -> None:
        for symbol, position in sorted(positions.items()):
            status = self._market_context.status(symbol, current_date)
            if status.is_safe:
                continue
            bar = bars.get(symbol)
            if bar is None:
                raise MarketContextIncompleteError(
                    f"unsafe position missing same-day bar for {symbol} on {current_date.isoformat()}"
                )
            trades.append(
                SimulatedTrade(
                    symbol=position.symbol,
                    entry_date=position.entry_date,
                    exit_date=current_date,
                    entry_price=position.entry_price,  # raw open; never pre-slipped
                    exit_price=bar.low,
                    qty=position.qty,
                    exit_reason=ContextOutcomeType.POSITION_FORCED_CLOSED.value,
                )
            )
            context_outcomes.append(
                ContextOutcome.from_status(status, ContextOutcomeType.POSITION_FORCED_CLOSED)
            )

    def _settle_closed_positions(
        self,
        current_date: date,
        positions: dict[str, _OpenPosition],
        trades: list[SimulatedTrade],
        cash: Decimal,
    ) -> Decimal:
        for trade in trades:
            if trade.exit_date != current_date or trade.symbol not in positions:
                continue
            position = positions.pop(trade.symbol)
            cash += exit_proceeds(
                position.entry_price,
                trade.exit_price,
                trade.qty,
                self._slippage_bps,
                self._tax_rate,
            )
        return cash

    def _mark_positions(self, positions: dict[str, _OpenPosition], bars: dict[str, DailyBar]) -> Decimal:
        for position in positions.values():
            bar = bars.get(position.symbol)
            if bar is not None:
                position.marked_value = exit_proceeds(
                    position.entry_price,
                    bar.close,
                    position.qty,
                    self._slippage_bps,
                    self._tax_rate,
                )
        return sum((position.marked_value for position in positions.values()), Decimal("0"))

    def _process_exits(
        self,
        positions: dict[str, _OpenPosition],
        bars: dict[str, DailyBar],
        trades: list[SimulatedTrade],
        by_symbol: dict[str, list[DailyBar]],
    ) -> None:
        for symbol, position in sorted(positions.items()):
            bar = bars.get(symbol)
            if bar is None:
                continue
            history_through = [item for item in by_symbol[symbol] if item.date <= bar.date]
            closed = self._exit_for_bar(position, bar, history_through)
            if closed is not None:
                trades.append(closed)

    def _exit_for_bar(
        self,
        position: _OpenPosition,
        bar: DailyBar,
        history_through_bar: list[DailyBar],
    ) -> SimulatedTrade | None:
        new_state, decision = on_bar(position.policy, bar, history_through_bar, self._exit_policy)
        position.policy = new_state
        if decision is None:
            return None
        return SimulatedTrade(
            symbol=position.symbol,
            entry_date=position.entry_date,
            exit_date=bar.date,
            entry_price=position.entry_price,  # raw open; metrics apply entry_fill once
            exit_price=decision.fill_price,
            qty=position.qty,
            exit_reason=decision.reason,
        )
