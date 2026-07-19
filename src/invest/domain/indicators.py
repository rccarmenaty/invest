from decimal import Decimal
from typing import Sequence

from invest.domain.models import DailyBar

ATR_DAYS = 14


def average_true_range(history: list[DailyBar], period: int = ATR_DAYS) -> Decimal:
    ranges: list[Decimal] = []
    for index, bar in enumerate(history):
        previous_close = history[index - 1].close if index else bar.open
        ranges.append(max(bar.high - bar.low, abs(bar.high - previous_close), abs(bar.low - previous_close)))
    recent_ranges = ranges[-period:]
    return sum(recent_ranges, Decimal()) / len(recent_ranges)


def simple_moving_average(bars: Sequence[DailyBar], window: int) -> Decimal:
    """Mean close price over the last `window` bars of the passed slice.

    The caller (scanner) owns any candidate-day exclusion by slicing `bars`
    before calling -- this reducer always uses the slice's own last elements.
    """
    recent = bars[-window:]
    return sum((bar.close for bar in recent), Decimal()) / len(recent)


def trailing_high(bars: Sequence[DailyBar], window: int) -> Decimal:
    """Highest high over the last `window` bars of the passed slice."""
    recent = bars[-window:]
    return max(bar.high for bar in recent)


def trailing_low(bars: Sequence[DailyBar], window: int) -> Decimal:
    """Lowest low over the last `window` bars of the passed slice.

    The caller owns any signal-day exclusion by slicing `bars` before calling —
    this reducer always uses the slice's own last elements.
    """
    recent = bars[-window:]
    return min(bar.low for bar in recent)


def momentum_return(bars: Sequence[DailyBar], far: int, near: int) -> Decimal:
    """Return of the close `near` bars before the slice's end vs `far` bars before it.

    Offsets are relative to `bars[-1]` (the candidate day), matching the spec's
    "N trading days before the candidate day" convention: pass the full window
    including the candidate, unlike `trailing_high`/`sma_is_rising`.
    """
    near_close = bars[-1 - near].close
    far_close = bars[-1 - far].close
    return near_close / far_close - Decimal("1")


def sma_is_rising(bars: Sequence[DailyBar], window: int, lookback: int) -> bool:
    """Whether the SMA ending at the slice's last bar exceeds the same-window SMA
    ending `lookback` bars earlier in the same slice."""
    recent_sma = simple_moving_average(bars, window)
    earlier_slice = bars[:-lookback] if lookback else bars
    earlier_sma = simple_moving_average(earlier_slice, window)
    return recent_sma > earlier_sma
