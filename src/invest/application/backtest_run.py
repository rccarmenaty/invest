"""Day-by-day replay harness: proves scanner/sizing edge without look-ahead.

Design (openspec/changes/backtest-replay/design.md): the harness orders bars by
date and ingests each bar once into chronological per-symbol histories. The two
production scanners explicitly declare their required bounded history and scan
those indexed histories plus sticky validation facts from older discarded bars;
unknown/custom scanners retain the original cumulative window fallback. Bars
dated after replay day `d` are physically absent from both paths, so no future
data can influence day `d`'s decision. See
`tests/application/test_backtest_run.py`'s killer test.

Portfolio construction (`evaluate_gates`, concurrency/equity caps) is
deliberately NOT simulated here (reconcile item 4): every accepted signal is
sized independently at a fixed nominal equity to isolate scanner+sizing edge,
not portfolio construction.
"""

from collections import Counter, defaultdict, deque
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from statistics import median
from typing import Callable, Mapping, Sequence, cast

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
    allows_price_path_exits,
    initial_state,
    on_bar,
    policy_provenance,
)
from invest.domain.indicators import momentum_return, trailing_high
from invest.domain.market_context import (
    ContextOutcome,
    ContextOutcomeType,
    MarketContext,
)
from invest.domain.models import (
    AccountSnapshot,
    BacktestResult,
    DailyBar,
    FixtureInputs,
    GateTelemetry,
    IndexedBarHistories,
    PortfolioSummary,
    ScanDecision,
    SimulatedTrade,
    SkippedEntry,
    Universe,
    daily_bar_is_valid,
)
from invest.domain.scanner import MomentumScanner
from invest.domain.sizing import GateReason, compute_intent, evaluate_gates, evaluate_halt_gates
from invest.application.ports import ScannerPort

NOMINAL_EQUITY = Decimal("100000")
POINT_IN_TIME_CONTEXT_VALIDATED = "point-in-time-market-context-validated"
MISSING_NEXT_SESSION_AFTER_EXIT_SIGNAL = "missing-next-session-after-exit-signal"
DEFAULT_EXIT_POLICY = ExitPolicyConfig(kind="ten-day-low", channel_window=10)
RANK_MOMENTUM_FAR = 252
RANK_MOMENTUM_NEAR = 21
RANK_PROXIMITY_WINDOW = 252
RANK_LIQUIDITY_WINDOW = 20
COOLDOWN_SESSIONS = 10
COOLDOWN_SKIP_REASON = "cooldown-active"


class ReplayWindowInvalidError(ValueError):
    def __init__(self, message: str) -> None:
        self.reason = "replay-window-invalid"
        super().__init__(message)


@dataclass(frozen=True)
class BacktestProgress:
    phase: str
    processed_replay_days: int
    total_replay_days: int
    accepted_decisions: int
    percent: int
    ingested_bars: int


@dataclass(frozen=True)
class _ReplayPartition:
    all_bars: tuple[DailyBar, ...]
    warmup_bars: tuple[DailyBar, ...]
    replay_bars: tuple[DailyBar, ...]
    replay_dates: tuple[date, ...]


@dataclass
class _OpenPosition:
    symbol: str
    entry_date: date
    entry_price: Decimal
    qty: int
    entry_fill: Decimal
    take_profit: Decimal
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
        progress_callback: Callable[[BacktestProgress], None] | None = None,
    ) -> None:
        self._market_context = market_context
        self._scanner = scanner or MomentumScanner()
        self._equity = equity
        self._cash = equity if cash is None else cash
        self._buying_power = buying_power
        self._slippage_bps = slippage_bps
        self._tax_rate = tax_rate
        self._exit_policy = exit_policy if exit_policy is not None else DEFAULT_EXIT_POLICY
        self._progress_callback = progress_callback

    def scan_decisions(
        self,
        inputs: FixtureInputs,
        *,
        start: date | None = None,
    ) -> list[ScanDecision]:
        """Replay day-by-day, collecting every ACCEPTED decision recorded on its own day.

        A decision is only collected when `decision.decision_date == d`: since the
        scanner's candidate bar is always `window[-1]`, this fires exactly once per
        symbol per day, the day its bar first enters the window.
        """
        partition = self._partition_bars(inputs.bars, start=start)
        return self._scan_decisions(inputs.universe, partition)

    def _scan_decisions(
        self,
        universe: Universe,
        partition: _ReplayPartition,
    ) -> list[ScanDecision]:
        indexed = self._indexed_replay_scanner()
        if indexed is not None:
            history_limit, scan_indexed = indexed
            histories: dict[str, deque[DailyBar]] = defaultdict(
                lambda: deque(maxlen=history_limit)
            )
            next_bar = 0
            zero_volume_symbols: set[str] = set()
            invalid_bar_symbols: set[str] = set()
            collected: list[ScanDecision] = []
            for day_number, d in enumerate(partition.replay_dates, start=1):
                while (
                    next_bar < len(partition.all_bars)
                    and partition.all_bars[next_bar].date <= d
                ):
                    bar = partition.all_bars[next_bar]
                    histories[bar.symbol].append(bar)
                    if bar.volume == 0:
                        zero_volume_symbols.add(bar.symbol)
                    if not daily_bar_is_valid(bar):
                        invalid_bar_symbols.add(bar.symbol)
                    next_bar += 1
                replay_universe = self._filtered_universe(universe, d)
                snapshots = IndexedBarHistories(
                    by_symbol={
                        symbol: tuple(histories.get(symbol, ()))
                        for symbol in replay_universe.symbols
                    },
                    zero_volume_symbols=frozenset(
                        zero_volume_symbols.intersection(replay_universe.symbols)
                    ),
                    invalid_bar_symbols=frozenset(
                        invalid_bar_symbols.intersection(replay_universe.symbols)
                    ),
                )
                for decision in scan_indexed(replay_universe, snapshots):
                    if decision.accepted and decision.decision_date == d:
                        collected.append(decision)
                self._report_scan_progress(
                    day_number=day_number,
                    total_days=len(partition.replay_dates),
                    accepted_decisions=len(collected),
                    ingested_bars=next_bar,
                )
            return collected

        collected: list[ScanDecision] = []
        ingested_bars = 0
        for day_number, d in enumerate(partition.replay_dates, start=1):
            while (
                ingested_bars < len(partition.all_bars)
                and partition.all_bars[ingested_bars].date <= d
            ):
                ingested_bars += 1
            replay_universe = self._filtered_universe(universe, d)
            eligible_symbols = set(replay_universe.symbols)
            window = tuple(
                bar
                for bar in partition.all_bars
                if bar.date <= d and bar.symbol in eligible_symbols
            )
            for decision in self._scanner.scan(replay_universe, window):
                if decision.accepted and decision.decision_date == d:
                    collected.append(decision)
            self._report_scan_progress(
                day_number=day_number,
                total_days=len(partition.replay_dates),
                accepted_decisions=len(collected),
                ingested_bars=ingested_bars,
            )
        return collected

    def _report_scan_progress(
        self,
        *,
        day_number: int,
        total_days: int,
        accepted_decisions: int,
        ingested_bars: int,
    ) -> None:
        if self._progress_callback is None:
            return
        self._progress_callback(
            BacktestProgress(
                phase="scan",
                processed_replay_days=day_number,
                total_replay_days=total_days,
                accepted_decisions=accepted_decisions,
                percent=(day_number * 100) // total_days,
                ingested_bars=ingested_bars,
            )
        )

    def _indexed_replay_scanner(
        self,
    ) -> tuple[
        int,
        Callable[
            [Universe, Mapping[str, Sequence[DailyBar]]],
            list[ScanDecision],
        ],
    ] | None:
        """Return an explicitly opted-in indexed scanner capability.

        The capability must be declared on the concrete class. Scanner
        subclasses therefore keep the correctness-preserving cumulative
        fallback unless they explicitly confirm that bounded replay history is
        sufficient for their own implementation.
        """
        declarations = vars(type(self._scanner))
        history_limit = declarations.get("replay_history_bars")
        if type(history_limit) is not int or history_limit <= 0:
            return None
        if "scan_indexed" not in declarations:
            return None
        scan_indexed = getattr(self._scanner, "scan_indexed")
        return history_limit, cast(
            Callable[
                [Universe, Mapping[str, Sequence[DailyBar]]],
                list[ScanDecision],
            ],
            scan_indexed,
        )

    def replay(
        self,
        inputs: FixtureInputs,
        *,
        split_date: date | None = None,
        start: date | None = None,
    ) -> BacktestResult:
        partition = self._partition_bars(inputs.bars, start=start)
        if split_date is not None and split_date not in partition.replay_dates:
            raise ReplayWindowInvalidError(
                f"split date {split_date.isoformat()} is not an observed replay date"
            )
        self._market_context.require_complete(partition.replay_dates, inputs.universe.symbols)
        decisions = self._scan_decisions(inputs.universe, partition)
        by_symbol: dict[str, list[DailyBar]] = defaultdict(list)
        for bar in sorted(partition.all_bars, key=lambda item: (item.symbol, item.date)):
            by_symbol[bar.symbol].append(bar)

        bars_by_date: dict[date, dict[str, DailyBar]] = defaultdict(dict)
        for bar in partition.replay_bars:
            bars_by_date[bar.date][bar.symbol] = bar
        pending: dict[date, list[ScanDecision]] = defaultdict(list)
        for decision in decisions:
            symbol_bars = by_symbol[decision.symbol]
            signal_index = self._signal_index(symbol_bars, decision)
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
        cooldown_release: dict[str, int] = {}

        for session_index, current_date in enumerate(sorted(bars_by_date)):
            todays_bars = bars_by_date[current_date]
            day_start = len(trades)
            # Context is authoritative for entry eligibility, but the current
            # model has no independently verified terminal-position state.
            # Existing positions therefore remain under ordinary exit policy
            # through transient blockers and eligibility changes.
            self._process_exits(positions, todays_bars, trades, by_symbol)
            cash = self._settle_closed_positions(current_date, positions, trades, cash)
            # Any ordinary close (trailing exit, hard stop, or time stop) recorded
            # today starts a COOLDOWN_SESSIONS-session cooldown for that symbol.
            for trade in trades[day_start:]:
                if trade.exit_reason != "open-at-end":
                    cooldown_release[trade.symbol] = session_index + COOLDOWN_SESSIONS + 1

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
            for decision in sorted(pending[current_date], key=lambda item: self._fill_rank_key(item, by_symbol)):
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
                if session_index < cooldown_release.get(decision.symbol, -1):
                    gate_counts[COOLDOWN_SKIP_REASON] += 1
                    skipped_entries.append(
                        SkippedEntry(decision.symbol, decision.decision_date, current_date, COOLDOWN_SKIP_REASON)
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
                signal_index = self._signal_index(symbol_bars, decision)
                intent, sizing_reason = compute_intent(
                    decision.symbol,
                    decision.decision_date,
                    marked_equity,
                    symbol_bars[:signal_index],
                    entry_bar.open,
                    symbol_bars[signal_index].low,
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
                position = _OpenPosition(
                    symbol=decision.symbol,
                    entry_date=current_date,
                    entry_price=raw_entry,
                    qty=intent.qty,
                    entry_fill=slipped_entry,
                    take_profit=intent.take_profit,
                    marked_value=entry_cost,
                    policy=initial_state(initial_stop=intent.stop, entry_price=raw_entry),
                )
                positions[decision.symbol] = position
                deployed += entry_cost
                history_through = [bar for bar in by_symbol[decision.symbol] if bar.date <= current_date]
                closed = self._exit_for_bar(position, entry_bar, history_through)
                if closed is not None:
                    trades.append(closed)
                    # Same-day round trip: this close happens AFTER the day's cooldown
                    # snapshot (top of the loop) already ran, so it must be recorded here.
                    cooldown_release[closed.symbol] = session_index + COOLDOWN_SESSIONS + 1
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

        replay_end = partition.replay_dates[-1]
        for position in positions.values():
            last_bar = by_symbol[position.symbol][-1]
            if last_bar.date < replay_end:
                raise ReplayWindowInvalidError(
                    f"open position {position.symbol} last trustworthy bar "
                    f"{last_bar.date.isoformat()} predates replay end "
                    f"{replay_end.isoformat()}"
                )

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

    @staticmethod
    def _signal_index(symbol_bars: list[DailyBar], decision: ScanDecision) -> int:
        return next(index for index, bar in enumerate(symbol_bars) if bar.date == decision.decision_date)

    def _fill_rank_key(
        self, decision: ScanDecision, by_symbol: dict[str, list[DailyBar]]
    ) -> tuple[Decimal, Decimal, Decimal, str]:
        """Same-day pending fill order: momentum rank (desc), 52-week-high proximity
        (desc), liquidity (desc), symbol (asc) -- SPEC §2.4. Short-history candidates
        (benchmark's ~21-bar window) fall back to momentum=proximity=0, so liquidity
        then symbol decide their order (see design's Benchmark-Strategy Interaction)."""
        symbol_bars = by_symbol[decision.symbol]
        signal_index = self._signal_index(symbol_bars, decision)
        window = symbol_bars[: signal_index + 1]
        if len(window) > RANK_MOMENTUM_FAR:
            momentum = momentum_return(window, far=RANK_MOMENTUM_FAR, near=RANK_MOMENTUM_NEAR)
            proximity = window[-1].close / trailing_high(window[:-1], RANK_PROXIMITY_WINDOW)
        else:
            momentum = proximity = Decimal(0)
        liquidity = median(bar.close * bar.volume for bar in window[-RANK_LIQUIDITY_WINDOW:])
        return (-momentum, -proximity, -liquidity, decision.symbol)

    def _partition_bars(
        self,
        bars: tuple[DailyBar, ...],
        *,
        start: date | None = None,
    ) -> _ReplayPartition:
        ordered = tuple(sorted(bars, key=lambda bar: (bar.date, bar.symbol)))
        span = self._market_context.generation_span
        replay_start = span.start if start is None else max(span.start, start)
        warmup: list[DailyBar] = []
        replay: list[DailyBar] = []
        for bar in ordered:
            if bar.date < replay_start:
                warmup.append(bar)
            elif bar.date <= span.end:
                replay.append(bar)
            else:
                raise ReplayWindowInvalidError(
                    f"bar for {bar.symbol} on {bar.date.isoformat()} is after generation span"
                )
        if not replay:
            raise ReplayWindowInvalidError("no bars fall inside generation span")
        return _ReplayPartition(
            all_bars=ordered,
            warmup_bars=tuple(warmup),
            replay_bars=tuple(replay),
            replay_dates=tuple(sorted({bar.date for bar in replay})),
        )

    def _filtered_universe(self, universe: Universe, as_of: date) -> Universe:
        return Universe(
            fixture_version=universe.fixture_version,
            symbols=self._market_context.eligible_symbols(universe.symbols, as_of),
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
        if (
            decision is None
            and allows_price_path_exits(self._exit_policy)
            and bar.high >= position.take_profit
        ):
            return SimulatedTrade(
                symbol=position.symbol,
                entry_date=position.entry_date,
                exit_date=bar.date,
                entry_price=position.entry_price,
                exit_price=position.take_profit,
                qty=position.qty,
                exit_reason="take-profit",
            )
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
