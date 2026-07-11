from collections import defaultdict
from datetime import date
from decimal import Decimal

from invest.domain.models import DailyBar, ScanDecision, Universe
from invest.domain.rejection import RejectionReason

HISTORY_DAYS = 20
ATR_DAYS = 14
RELATIVE_VOLUME_MULTIPLIER = Decimal("2")
UPWARD_MOVE_ATR_MULTIPLIER = Decimal("1.5")
MAX_MOVING_AVERAGE_MULTIPLIER = Decimal("1.15")


class MomentumScanner:
    def scan(self, universe: Universe, bars: tuple[DailyBar, ...]) -> list[ScanDecision]:
        grouped: dict[str, list[DailyBar]] = defaultdict(list)
        for bar in sorted(bars, key=lambda item: (item.symbol, item.date)):
            grouped[bar.symbol].append(bar)

        unsupported = set(grouped).difference(universe.symbols)
        forced_reason = RejectionReason.UNSUPPORTED_INPUT if unsupported else None
        decisions = [
            self._scan_symbol(symbol, grouped.get(symbol, []), forced_reason) for symbol in universe.symbols
        ]
        return sorted(decisions, key=lambda item: (item.decision_date, item.symbol))

    def _scan_symbol(
        self,
        symbol: str,
        bars: list[DailyBar],
        forced_reason: RejectionReason | None = None,
    ) -> ScanDecision:
        decision_date = bars[-1].date if bars else date.min
        if forced_reason is not None:
            return ScanDecision(symbol, decision_date, False, forced_reason)
        if len(bars) < HISTORY_DAYS + 1:
            return ScanDecision(symbol, decision_date, False, RejectionReason.INSUFFICIENT_HISTORY)
        if any(bar.volume == 0 for bar in bars):
            return ScanDecision(symbol, decision_date, False, RejectionReason.MISSING_DATA)
        if any(not self._valid_bar(bar) for bar in bars):
            return ScanDecision(
                symbol,
                decision_date,
                False,
                RejectionReason.DOMAIN_INVARIANT_VIOLATION,
            )
        candidate = bars[-1]
        history = bars[-(HISTORY_DAYS + 1) : -1]
        average_volume = Decimal(sum(bar.volume for bar in history)) / len(history)
        moving_average = sum((bar.close for bar in history), Decimal()) / len(history)
        prior_high = max(bar.high for bar in history)
        atr = self._average_true_range(history)
        accepted = (
            Decimal(candidate.volume) >= RELATIVE_VOLUME_MULTIPLIER * average_volume
            and candidate.close - history[-1].close >= UPWARD_MOVE_ATR_MULTIPLIER * atr
            and candidate.close > prior_high
            and candidate.close < MAX_MOVING_AVERAGE_MULTIPLIER * moving_average
        )
        return ScanDecision(
            symbol=symbol,
            decision_date=candidate.date,
            accepted=accepted,
            reason=None if accepted else RejectionReason.NO_SIGNAL,
        )

    @staticmethod
    def _average_true_range(history: list[DailyBar]) -> Decimal:
        ranges: list[Decimal] = []
        for index, bar in enumerate(history):
            previous_close = history[index - 1].close if index else bar.open
            ranges.append(max(bar.high - bar.low, abs(bar.high - previous_close), abs(bar.low - previous_close)))
        recent_ranges = ranges[-ATR_DAYS:]
        return sum(recent_ranges, Decimal()) / len(recent_ranges)

    @staticmethod
    def _valid_bar(bar: DailyBar) -> bool:
        return (
            bar.open > 0
            and bar.high > 0
            and bar.low > 0
            and bar.close > 0
            and bar.volume >= 0
            and bar.low <= bar.open <= bar.high
            and bar.low <= bar.close <= bar.high
        )
