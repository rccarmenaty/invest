"""Core 52-Week-High Momentum Breakout candidate-selection layer.

Cross-sectional 5-stage pipeline (see design.md's Data Flow):
history gate -> momentum rank -> 52-week-high proximity -> trend -> breakout.
Implements SPEC `momentum-selection-scanner` sections on ranking, proximity,
trend, and breakout, reusing the Slice 1 indicator reducers and rejection
reasons. Drops into the same `scan(universe, bars) -> list[ScanDecision]`
seam as `MomentumScanner` (no changes to that sibling scanner).
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from math import ceil

from invest.domain.indicators import momentum_return, simple_moving_average, sma_is_rising, trailing_high
from invest.domain.models import DailyBar, ScanDecision, Universe
from invest.domain.rejection import RejectionReason, UnsupportedInputError

HISTORY_DAYS = 253
MOMENTUM_FAR_DAYS = 252
MOMENTUM_NEAR_DAYS = 21
TOP_MOMENTUM_PERCENT = Decimal("0.15")
PROXIMITY_WINDOW_DAYS = 252
PROXIMITY_THRESHOLD = Decimal("0.95")
TREND_SMA_SHORT_DAYS = 50
TREND_SMA_LONG_DAYS = 200
TREND_SMA_LOOKBACK_DAYS = 20
BREAKOUT_WINDOW_DAYS = 20


class MomentumSelectionScanner:
    def scan(self, universe: Universe, bars: tuple[DailyBar, ...]) -> list[ScanDecision]:
        grouped = self._group_by_symbol(universe, bars)

        decisions: dict[str, ScanDecision] = {}
        eligible: dict[str, list[DailyBar]] = {}
        for symbol in universe.symbols:
            symbol_bars = grouped.get(symbol, [])
            if len(symbol_bars) < HISTORY_DAYS:
                decision_date = symbol_bars[-1].date if symbol_bars else date.min
                decisions[symbol] = ScanDecision(symbol, decision_date, False, RejectionReason.INSUFFICIENT_HISTORY)
                continue
            if any(bar.volume == 0 for bar in symbol_bars):
                decisions[symbol] = ScanDecision(symbol, symbol_bars[-1].date, False, RejectionReason.MISSING_DATA)
                continue
            if any(not self._valid_bar(bar) for bar in symbol_bars):
                decisions[symbol] = ScanDecision(
                    symbol,
                    symbol_bars[-1].date,
                    False,
                    RejectionReason.DOMAIN_INVARIANT_VIOLATION,
                )
                continue
            eligible[symbol] = symbol_bars

        ranked = sorted(
            eligible.items(),
            key=lambda item: (-momentum_return(item[1], far=MOMENTUM_FAR_DAYS, near=MOMENTUM_NEAR_DAYS), item[0]),
        )
        cutoff = ceil(TOP_MOMENTUM_PERCENT * len(ranked)) if ranked else 0
        top_symbols = {symbol for symbol, _ in ranked[:cutoff]}

        for symbol, symbol_bars in ranked:
            candidate = symbol_bars[-1]
            if symbol not in top_symbols:
                decisions[symbol] = ScanDecision(symbol, candidate.date, False, RejectionReason.NOT_TOP_MOMENTUM_RANK)
                continue
            decisions[symbol] = self._evaluate_candidate(symbol, symbol_bars)

        return sorted(decisions.values(), key=lambda item: (item.decision_date, item.symbol))

    @staticmethod
    def _group_by_symbol(universe: Universe, bars: tuple[DailyBar, ...]) -> dict[str, list[DailyBar]]:
        """Group bars per symbol (sorted, chronological) and fail closed on any
        bar for a symbol outside the universe -- mirrors `MomentumScanner`'s
        grouping/validation shape without importing from or modifying it."""
        grouped: dict[str, list[DailyBar]] = defaultdict(list)
        for bar in sorted(bars, key=lambda item: (item.symbol, item.date)):
            grouped[bar.symbol].append(bar)

        unsupported = set(grouped).difference(universe.symbols)
        if unsupported:
            raise UnsupportedInputError(tuple(sorted(unsupported)))
        return grouped

    @staticmethod
    def _valid_bar(bar: DailyBar) -> bool:
        """Mirrors `MomentumScanner._valid_bar` without importing from or
        modifying the sibling scanner (same convention as `_group_by_symbol`)."""
        return (
            bar.open > 0
            and bar.high > 0
            and bar.low > 0
            and bar.close > 0
            and bar.volume >= 0
            and bar.low <= bar.open <= bar.high
            and bar.low <= bar.close <= bar.high
        )

    @staticmethod
    def _evaluate_candidate(symbol: str, symbol_bars: list[DailyBar]) -> ScanDecision:
        candidate = symbol_bars[-1]
        history = symbol_bars[:-1]

        trailing_252_high = trailing_high(history, PROXIMITY_WINDOW_DAYS)
        if candidate.close < PROXIMITY_THRESHOLD * trailing_252_high:
            return ScanDecision(symbol, candidate.date, False, RejectionReason.BELOW_52_WEEK_HIGH_PROXIMITY)

        sma_short = simple_moving_average(history, TREND_SMA_SHORT_DAYS)
        sma_long = simple_moving_average(history, TREND_SMA_LONG_DAYS)
        long_sma_rising = sma_is_rising(history, TREND_SMA_LONG_DAYS, TREND_SMA_LOOKBACK_DAYS)
        order_holds = candidate.close > sma_short > sma_long
        if not (order_holds and long_sma_rising):
            return ScanDecision(symbol, candidate.date, False, RejectionReason.TREND_FILTER_FAILED)

        prior_high = trailing_high(history, BREAKOUT_WINDOW_DAYS)
        accepted = candidate.close > prior_high
        return ScanDecision(
            symbol=symbol,
            decision_date=candidate.date,
            accepted=accepted,
            reason=None if accepted else RejectionReason.NO_SIGNAL,
        )
