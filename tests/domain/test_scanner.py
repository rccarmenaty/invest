from datetime import date, timedelta
from decimal import Decimal

import pytest

from invest.domain.models import DailyBar, IndexedBarHistories, Universe
from invest.domain.scanner import MomentumScanner
from invest.domain.rejection import RejectionReason, UnsupportedInputError


def _bar(symbol: str, day: date, close: str, volume: int = 100) -> DailyBar:
    price = Decimal(close)
    return DailyBar(
        symbol=symbol,
        date=day,
        open=price,
        high=price + Decimal("0.1"),
        low=price - Decimal("0.1"),
        close=price,
        volume=volume,
    )


def _accepted_history(symbol: str, start: date) -> tuple[DailyBar, ...]:
    history = tuple(_bar(symbol, start + timedelta(days=index), "10") for index in range(20))
    candidate = _bar(symbol, start + timedelta(days=20), "11.4", volume=250)
    return (*history, candidate)


def test_scanner_accepts_momentum_candidate_deterministically() -> None:
    universe = Universe(fixture_version="v1", symbols=("BETA", "ACME"))
    bars = (*_accepted_history("BETA", date(2026, 1, 1)), *_accepted_history("ACME", date(2026, 1, 1)))
    scanner = MomentumScanner()

    first = scanner.scan(universe, tuple(reversed(bars)))
    second = scanner.scan(universe, tuple(reversed(bars)))

    assert first == second
    assert [(decision.symbol, decision.accepted, decision.reason) for decision in first] == [
        ("ACME", True, None),
        ("BETA", True, None),
    ]


def test_indexed_scan_matches_flat_scan_for_required_history() -> None:
    universe = Universe(fixture_version="v1", symbols=("BETA", "ACME"))
    histories = {
        symbol: _accepted_history(symbol, date(2026, 1, 1))
        for symbol in universe.symbols
    }
    scanner = MomentumScanner()

    indexed = scanner.scan_indexed(universe, histories)
    flat = scanner.scan(universe, tuple(bar for bars in histories.values() for bar in bars))

    assert scanner.replay_history_bars == 21
    assert indexed == flat


def test_scanner_rejects_insufficient_history() -> None:
    bars = tuple(_bar("ACME", date(2026, 1, 1) + timedelta(days=index), "10") for index in range(20))

    decision = MomentumScanner().scan(Universe("v1", ("ACME",)), bars)[0]

    assert (decision.symbol, decision.accepted, decision.reason) == (
        "ACME",
        False,
        RejectionReason.INSUFFICIENT_HISTORY,
    )


def test_scanner_rejects_zero_volume_as_missing_data() -> None:
    bars = list(_accepted_history("ACME", date(2026, 1, 1)))
    bars[5] = _bar("ACME", bars[5].date, "10", volume=0)

    decision = MomentumScanner().scan(Universe("v1", ("ACME",)), tuple(bars))[0]

    assert decision.reason is RejectionReason.MISSING_DATA


def test_scanner_raises_for_bars_outside_universe() -> None:
    bars = (*_accepted_history("ACME", date(2026, 1, 1)), *_accepted_history("UNKNOWN", date(2026, 1, 1)))

    with pytest.raises(UnsupportedInputError) as error:
        MomentumScanner().scan(Universe("v1", ("ACME",)), bars)

    assert error.value.reason is RejectionReason.UNSUPPORTED_INPUT
    assert error.value.symbols == ("UNKNOWN",)


def test_indexed_scanner_raises_for_sticky_metadata_outside_universe() -> None:
    universe = Universe("v1", ("ACME",))
    histories = IndexedBarHistories(
        by_symbol={"ACME": _accepted_history("ACME", date(2026, 1, 1))},
        zero_volume_symbols=frozenset(("UNKNOWN",)),
    )

    with pytest.raises(UnsupportedInputError) as error:
        MomentumScanner().scan_indexed(universe, histories)

    assert error.value.symbols == ("UNKNOWN",)


@pytest.mark.parametrize("corruption", ["zero-volume", "invalid-ohlc"])
def test_indexed_sticky_rejection_matches_cumulative_after_bad_bar_ages_out(
    corruption: str,
) -> None:
    start = date(2026, 1, 1)
    bars = [
        _bar("ACME", start + timedelta(days=offset), "10")
        for offset in range(22)
    ]
    bars.append(_bar("ACME", start + timedelta(days=22), "11.4", volume=250))
    first = bars[0]
    if corruption == "zero-volume":
        bars[0] = _bar("ACME", first.date, "10", volume=0)
    else:
        bars[0] = DailyBar(
            first.symbol,
            first.date,
            first.open,
            first.low,
            first.high,
            first.close,
            first.volume,
        )
    universe = Universe("v1", ("ACME",))
    scanner = MomentumScanner()

    for count in range(scanner.replay_history_bars, len(bars) + 1):
        cumulative = tuple(bars[:count])
        histories = IndexedBarHistories(
            by_symbol={"ACME": cumulative[-scanner.replay_history_bars :]},
            zero_volume_symbols=(
                frozenset(("ACME",))
                if corruption == "zero-volume"
                else frozenset()
            ),
            invalid_bar_symbols=(
                frozenset(("ACME",))
                if corruption == "invalid-ohlc"
                else frozenset()
            ),
        )

        assert scanner.scan_indexed(universe, histories) == scanner.scan(
            universe, cumulative
        )


def test_scanner_rejects_domain_invariant_violation() -> None:
    bars = list(_accepted_history("ACME", date(2026, 1, 1)))
    invalid = bars[3]
    bars[3] = DailyBar(
        symbol=invalid.symbol,
        date=invalid.date,
        open=invalid.open,
        high=invalid.low,
        low=invalid.high,
        close=invalid.close,
        volume=invalid.volume,
    )

    decision = MomentumScanner().scan(Universe("v1", ("ACME",)), tuple(bars))[0]

    assert decision.reason is RejectionReason.DOMAIN_INVARIANT_VIOLATION


def test_scanner_rejects_valid_candidate_without_signal() -> None:
    bars = list(_accepted_history("ACME", date(2026, 1, 1)))
    bars[-1] = _bar("ACME", bars[-1].date, "10.05", volume=250)

    decision = MomentumScanner().scan(Universe("v1", ("ACME",)), tuple(bars))[0]

    assert decision.reason is RejectionReason.NO_SIGNAL


def _oscillating_history(symbol: str, start: date) -> list[DailyBar]:
    bars: list[DailyBar] = []
    price = Decimal("50")
    for index in range(20):
        day = start + timedelta(days=index)
        high = price + Decimal("1.5") if index % 2 == 0 else price + Decimal("0.5")
        low = price - Decimal("1.0") if index % 2 == 0 else price - Decimal("0.3")
        close = price + Decimal("0.2")
        bars.append(DailyBar(symbol=symbol, date=day, open=price, high=high, low=low, close=close, volume=1000))
        price = close
    return bars


def test_scanner_regression_snapshot_survives_atr_extraction() -> None:
    """Baseline snapshot captured against the pre-extraction scanner (ATR still inline).

    Locks in exact decisions on ATR-sensitive data so the byte-mechanical move of
    `_average_true_range` into `domain/indicators.py` cannot silently change scan output.
    """
    start = date(2026, 1, 1)

    accepted_bars = _oscillating_history("REG1", start)
    breakout_price = accepted_bars[-1].close
    accepted_bars.append(
        DailyBar(
            symbol="REG1",
            date=start + timedelta(days=20),
            open=breakout_price,
            high=breakout_price + Decimal("5"),
            low=breakout_price - Decimal("0.1"),
            close=breakout_price + Decimal("4.5"),
            volume=5000,
        )
    )

    no_signal_bars = _oscillating_history("REG2", start)
    weak_price = no_signal_bars[-1].close
    no_signal_bars.append(
        DailyBar(
            symbol="REG2",
            date=start + timedelta(days=20),
            open=weak_price,
            high=weak_price + Decimal("0.3"),
            low=weak_price - Decimal("0.1"),
            close=weak_price + Decimal("0.05"),
            volume=500,
        )
    )

    universe = Universe(fixture_version="v1", symbols=("REG1", "REG2"))
    bars = tuple(accepted_bars + no_signal_bars)

    decisions = MomentumScanner().scan(universe, bars)

    assert [(decision.symbol, decision.decision_date, decision.accepted, decision.reason) for decision in decisions] == [
        ("REG1", start + timedelta(days=20), True, None),
        ("REG2", start + timedelta(days=20), False, RejectionReason.NO_SIGNAL),
    ]
