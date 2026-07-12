from datetime import date, timedelta
from decimal import Decimal

import pytest

from invest.domain.models import DailyBar, Universe
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
