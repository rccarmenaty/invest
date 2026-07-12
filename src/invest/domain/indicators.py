from decimal import Decimal

from invest.domain.models import DailyBar

ATR_DAYS = 14


def average_true_range(history: list[DailyBar]) -> Decimal:
    ranges: list[Decimal] = []
    for index, bar in enumerate(history):
        previous_close = history[index - 1].close if index else bar.open
        ranges.append(max(bar.high - bar.low, abs(bar.high - previous_close), abs(bar.low - previous_close)))
    recent_ranges = ranges[-ATR_DAYS:]
    return sum(recent_ranges, Decimal()) / len(recent_ranges)
