from datetime import date, timedelta
from decimal import Decimal

from invest.domain.indicators import (
    average_true_range,
    momentum_return,
    simple_moving_average,
    sma_is_rising,
    trailing_high,
)
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


def _series(closes: list[str]) -> list[DailyBar]:
    start = date(2026, 1, 1)
    return [
        _bar(start + timedelta(days=index), high=close, low=close, close=close)
        for index, close in enumerate(closes)
    ]


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


def test_simple_moving_average_matches_hand_computed_mean_of_last_window() -> None:
    bars = _series(["1", "2", "3", "4", "5"])

    assert simple_moving_average(bars, 3) == (Decimal("3") + Decimal("4") + Decimal("5")) / 3


def test_simple_moving_average_ignores_bars_outside_the_window() -> None:
    bars = _series(["100", "100", "2", "4", "6"])

    assert simple_moving_average(bars, 2) == (Decimal("4") + Decimal("6")) / 2


def test_trailing_high_matches_hand_computed_max_of_last_window_highs() -> None:
    start = date(2026, 1, 1)
    bars = [
        _bar(start, high="10", low="1", close="5"),
        _bar(start + timedelta(days=1), high="20", low="1", close="5"),
        _bar(start + timedelta(days=2), high="5", low="1", close="5"),
        _bar(start + timedelta(days=3), high="15", low="1", close="5"),
        _bar(start + timedelta(days=4), high="8", low="1", close="5"),
    ]

    assert trailing_high(bars, 3) == Decimal("15")


def test_trailing_high_ignores_higher_bars_outside_the_window() -> None:
    start = date(2026, 1, 1)
    bars = [
        _bar(start, high="1000", low="1", close="5"),
        _bar(start + timedelta(days=1), high="9", low="1", close="5"),
        _bar(start + timedelta(days=2), high="7", low="1", close="5"),
    ]

    assert trailing_high(bars, 2) == Decimal("9")


def test_momentum_return_matches_hand_computed_offset_close_ratio() -> None:
    bars = _series(["10", "20", "30", "40", "50"])

    assert momentum_return(bars, far=4, near=1) == Decimal("40") / Decimal("10") - Decimal("1")


def test_momentum_return_produces_negative_return_for_a_declining_series() -> None:
    bars = _series(["50", "40", "30", "20", "10"])

    assert momentum_return(bars, far=4, near=1) == Decimal("20") / Decimal("50") - Decimal("1")


def test_sma_is_rising_true_when_recent_sma_exceeds_earlier_sma() -> None:
    bars = _series(["1", "1", "3", "5"])

    assert sma_is_rising(bars, window=2, lookback=2) is True


def test_sma_is_rising_false_when_recent_sma_does_not_exceed_earlier_sma() -> None:
    bars = _series(["5", "3", "1", "1"])

    assert sma_is_rising(bars, window=2, lookback=2) is False
