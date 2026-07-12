from datetime import date, timedelta
from decimal import Decimal

from invest.domain.indicators import average_true_range
from invest.domain.models import DailyBar


def _bar(day: date, high: str, low: str, close: str, open_: str | None = None) -> DailyBar:
    return DailyBar(
        symbol="ACME",
        date=day,
        open=Decimal(open_ if open_ is not None else close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=1000,
    )


def test_average_true_range_matches_hand_computed_value() -> None:
    start = date(2026, 1, 1)
    history = (
        _bar(start, high="11", low="9", close="10", open_="10"),
        _bar(start + timedelta(days=1), high="12", low="10", close="11"),
        _bar(start + timedelta(days=2), high="10", low="8", close="9"),
    )

    atr = average_true_range(list(history))

    # day0: high-low=2 (no previous close, uses own open) -> true range = max(2, |11-10|, |9-10|) = 2
    # day1: true range = max(2, |12-10|, |10-10|) = 2
    # day2: true range = max(2, |10-11|, |8-11|) = 3
    assert atr == (Decimal("2") + Decimal("2") + Decimal("3")) / 3


def test_average_true_range_slices_to_atr_days_window() -> None:
    start = date(2026, 1, 1)
    # 16 bars: the first (outlier) bar and its immediate successor's contaminated range are
    # dropped by the last-ATR_DAYS(14) slice, leaving only the uniform tail to average.
    history = [_bar(start, high="1000", low="0", close="500", open_="500")]
    history += [
        _bar(start + timedelta(days=1 + index), high="10", low="9", close="9.5", open_="9.5") for index in range(15)
    ]

    atr = average_true_range(history)

    assert atr == Decimal("1")
