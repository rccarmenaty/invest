from datetime import date, timedelta
from decimal import Decimal

import pytest

from invest.domain.models import DailyBar, IndexedBarHistories, Universe
from invest.domain.momentum_selection_scanner import HISTORY_DAYS, MomentumSelectionScanner
from invest.domain.rejection import RejectionReason, UnsupportedInputError


def _bar(symbol: str, day: date, close: Decimal) -> DailyBar:
    high = close + Decimal("0.4")
    low = close - Decimal("0.4")
    return DailyBar(symbol=symbol, date=day, open=close, high=high, low=low, close=close, volume=1000)


def _uptrend_history(symbol: str, start: date, slope: Decimal, count: int = 253) -> tuple[DailyBar, ...]:
    """Monotonic uptrend: close(t) = 100 + slope * t.

    Hand-verified (via the real `indicators` functions) that every slope in
    [1, 10] passes the proximity/trend/rising/breakout layers identically --
    only the momentum-rank stage differs across symbols built this way, so
    this builder isolates ranking cutoff/tie-break behavior from every other
    filter layer.
    """
    return tuple(_bar(symbol, start + timedelta(days=t), Decimal("100") + slope * t) for t in range(count))


def _proximity_reject_history(symbol: str, start: date) -> tuple[DailyBar, ...]:
    """253-bar slope=1 uptrend whose candidate closes far below its trailing
    252-day high (a deep one-day drop), isolating a proximity-stage rejection."""
    history = [_bar(symbol, start + timedelta(days=t), Decimal("100") + t) for t in range(252)]
    candidate = _bar(symbol, start + timedelta(days=252), Decimal("100"))
    return tuple(history + [candidate])


def _non_rising_sma_reject_history(symbol: str, start: date) -> tuple[DailyBar, ...]:
    """253 bars with an early 20-day spike plateau (t=32..51) that the recent
    SMA200 window has since rolled past, so SMA200(t-1) <= SMA200(t-21) while
    close > SMA50 > SMA200 still holds at the candidate day."""
    history = []
    for t in range(252):
        close = Decimal("400") if 32 <= t <= 51 else Decimal("100") + t
        history.append(_bar(symbol, start + timedelta(days=t), close))
    candidate = _bar(symbol, start + timedelta(days=252), Decimal("405"))
    return tuple(history + [candidate])


def _broken_order_reject_history(symbol: str, start: date) -> tuple[DailyBar, ...]:
    """253 bars with the last 50 days plateaued high enough that SMA50 exceeds
    the candidate's own close, breaking close > SMA50 > SMA200 while proximity
    still passes (candidate stays within 5% of the plateau-driven 252-day high)."""
    history = []
    for t in range(252):
        close = Decimal("500") if 202 <= t <= 251 else Decimal("100") + t
        history.append(_bar(symbol, start + timedelta(days=t), close))
    candidate = _bar(symbol, start + timedelta(days=252), Decimal("480"))
    return tuple(history + [candidate])


def _no_signal_breakout_reject_history(symbol: str, start: date) -> tuple[DailyBar, ...]:
    """253 bars: slope=1 uptrend flattens for the last 20 days before the
    candidate, then the candidate closes AT the flattened prior-20-day high
    (not above it) -- passes every layer except the breakout trigger."""
    history = []
    for t in range(252):
        close = Decimal("335") if 232 <= t <= 251 else Decimal("100") + t
        history.append(_bar(symbol, start + timedelta(days=t), close))
    candidate = _bar(symbol, start + timedelta(days=252), Decimal("335"))
    return tuple(history + [candidate])


def test_rejects_insufficient_history_and_excludes_it_from_ranking() -> None:
    assert HISTORY_DAYS == 253
    start = date(2026, 1, 1)
    short_history = _uptrend_history("SHORT", start, Decimal("1"), count=252)
    sufficient_history = _uptrend_history("LONG", start, Decimal("1"), count=253)
    universe = Universe("v1", ("SHORT", "LONG"))

    decisions = MomentumSelectionScanner().scan(universe, short_history + sufficient_history)
    by_symbol = {decision.symbol: decision for decision in decisions}

    assert by_symbol["SHORT"].accepted is False
    assert by_symbol["SHORT"].reason is RejectionReason.INSUFFICIENT_HISTORY
    # LONG is the only sufficient-history symbol: a pool of 1 always clears the
    # momentum-rank cutoff, so its acceptance proves SHORT never entered ranking.
    assert by_symbol["LONG"].accepted is True
    assert by_symbol["LONG"].reason is None


def test_ceil_fifteen_percent_cutoff_retains_at_least_one_in_a_small_pool() -> None:
    start = date(2026, 1, 1)
    slopes = {"AAA": Decimal("10"), "BBB": Decimal("9"), "CCC": Decimal("1")}
    bars = tuple(bar for symbol, slope in slopes.items() for bar in _uptrend_history(symbol, start, slope))
    universe = Universe("v1", tuple(sorted(slopes)))

    decisions = MomentumSelectionScanner().scan(universe, bars)
    by_symbol = {decision.symbol: decision for decision in decisions}

    # Pool of 3: ceil(0.15 * 3) = 1 -> only the single highest-momentum symbol clears rank.
    assert by_symbol["AAA"].accepted is True
    assert by_symbol["AAA"].reason is None
    assert by_symbol["BBB"].reason is RejectionReason.NOT_TOP_MOMENTUM_RANK
    assert by_symbol["CCC"].reason is RejectionReason.NOT_TOP_MOMENTUM_RANK


def test_indexed_scan_matches_flat_scan_for_required_history() -> None:
    start = date(2026, 1, 1)
    universe = Universe("v1", ("AAA", "BBB", "CCC"))
    histories = {
        "AAA": _uptrend_history("AAA", start, Decimal("10")),
        "BBB": _uptrend_history("BBB", start, Decimal("9")),
        "CCC": _uptrend_history("CCC", start, Decimal("1")),
    }
    scanner = MomentumSelectionScanner()

    indexed = scanner.scan_indexed(universe, histories)
    flat = scanner.scan(universe, tuple(bar for bars in histories.values() for bar in bars))

    assert scanner.replay_history_bars == HISTORY_DAYS
    assert indexed == flat


def test_ceil_fifteen_percent_cutoff_retains_exactly_k_in_a_larger_pool() -> None:
    start = date(2026, 1, 1)
    slopes = {
        "S10": Decimal("10"),
        "S9": Decimal("9"),
        "S8": Decimal("8"),
        "S7": Decimal("7"),
        "S6": Decimal("6"),
        "S5": Decimal("5"),
        "S4": Decimal("4"),
    }
    bars = tuple(bar for symbol, slope in slopes.items() for bar in _uptrend_history(symbol, start, slope))
    universe = Universe("v1", tuple(sorted(slopes)))

    decisions = MomentumSelectionScanner().scan(universe, bars)
    by_symbol = {decision.symbol: decision for decision in decisions}

    # Pool of 7: ceil(0.15 * 7) = 2 -> only the two highest-momentum symbols clear rank.
    assert by_symbol["S10"].accepted is True
    assert by_symbol["S9"].accepted is True
    for symbol in ("S8", "S7", "S6", "S5", "S4"):
        assert by_symbol[symbol].reason is RejectionReason.NOT_TOP_MOMENTUM_RANK


def test_tie_break_is_deterministic_by_symbol_ascending_and_stable_across_runs() -> None:
    start = date(2026, 1, 1)
    slopes = {"AAA": Decimal("10"), "BBB": Decimal("10"), "CCC": Decimal("1")}
    bars = tuple(bar for symbol, slope in slopes.items() for bar in _uptrend_history(symbol, start, slope))
    universe = Universe("v1", tuple(sorted(slopes)))
    scanner = MomentumSelectionScanner()

    first = {decision.symbol: decision for decision in scanner.scan(universe, bars)}
    second = {decision.symbol: decision for decision in scanner.scan(universe, bars)}

    for run in (first, second):
        # AAA and BBB have IDENTICAL momentum return; only symbol-ascending
        # tie-break can deterministically pick AAA for the single k=1 slot.
        assert run["AAA"].accepted is True
        assert run["AAA"].reason is None
        assert run["BBB"].reason is RejectionReason.NOT_TOP_MOMENTUM_RANK
        assert run["CCC"].reason is RejectionReason.NOT_TOP_MOMENTUM_RANK
    assert first == second


def test_rejects_below_52_week_high_proximity() -> None:
    start = date(2026, 1, 1)
    bars = _proximity_reject_history("PROX", start)

    decision = MomentumSelectionScanner().scan(Universe("v1", ("PROX",)), bars)[0]

    assert decision.accepted is False
    assert decision.reason is RejectionReason.BELOW_52_WEEK_HIGH_PROXIMITY


def test_rejects_non_rising_sma200_trend_filter() -> None:
    start = date(2026, 1, 1)
    bars = _non_rising_sma_reject_history("TREND1", start)

    decision = MomentumSelectionScanner().scan(Universe("v1", ("TREND1",)), bars)[0]

    assert decision.accepted is False
    assert decision.reason is RejectionReason.TREND_FILTER_FAILED


def test_rejects_broken_moving_average_order_trend_filter() -> None:
    start = date(2026, 1, 1)
    bars = _broken_order_reject_history("TREND2", start)

    decision = MomentumSelectionScanner().scan(Universe("v1", ("TREND2",)), bars)[0]

    assert decision.accepted is False
    assert decision.reason is RejectionReason.TREND_FILTER_FAILED


def test_accepts_a_candidate_passing_every_layer() -> None:
    start = date(2026, 1, 1)
    bars = _uptrend_history("WIN", start, Decimal("1"))

    decision = MomentumSelectionScanner().scan(Universe("v1", ("WIN",)), bars)[0]

    assert decision.accepted is True
    assert decision.reason is None


def test_rejects_no_signal_when_only_the_breakout_trigger_fails() -> None:
    start = date(2026, 1, 1)
    bars = _no_signal_breakout_reject_history("FLATTOP", start)

    decision = MomentumSelectionScanner().scan(Universe("v1", ("FLATTOP",)), bars)[0]

    assert decision.accepted is False
    assert decision.reason is RejectionReason.NO_SIGNAL


def test_emits_exactly_one_decision_per_universe_symbol_sorted_by_date_then_symbol() -> None:
    start = date(2026, 1, 1)
    # ZZZ's candidate day is earlier than AAA's despite the alphabetically later
    # symbol name -- proves the sort key is (decision_date, symbol), not symbol-only.
    zzz_bars = _uptrend_history("ZZZ", start, Decimal("1"), count=253)
    aaa_bars = _uptrend_history("AAA", start, Decimal("1"), count=254)
    universe = Universe("v1", ("AAA", "ZZZ"))

    decisions = MomentumSelectionScanner().scan(universe, zzz_bars + aaa_bars)

    assert {decision.symbol for decision in decisions} == {"AAA", "ZZZ"}
    assert [decision.symbol for decision in decisions] == ["ZZZ", "AAA"]
    assert decisions[0].decision_date < decisions[1].decision_date


def test_raises_for_bars_outside_universe() -> None:
    start = date(2026, 1, 1)
    bars = _uptrend_history("KNOWN", start, Decimal("1")) + _uptrend_history("UNKNOWN", start, Decimal("1"))

    with pytest.raises(UnsupportedInputError) as error:
        MomentumSelectionScanner().scan(Universe("v1", ("KNOWN",)), bars)

    assert error.value.reason is RejectionReason.UNSUPPORTED_INPUT
    assert error.value.symbols == ("UNKNOWN",)


def test_indexed_scanner_raises_for_sticky_metadata_outside_universe() -> None:
    universe = Universe("v1", ("KNOWN",))
    histories = IndexedBarHistories(
        by_symbol={"KNOWN": _uptrend_history("KNOWN", date(2026, 1, 1), Decimal("1"))},
        invalid_bar_symbols=frozenset(("UNKNOWN",)),
    )

    with pytest.raises(UnsupportedInputError) as error:
        MomentumSelectionScanner().scan_indexed(universe, histories)

    assert error.value.symbols == ("UNKNOWN",)


@pytest.mark.parametrize("corruption", ["zero-volume", "invalid-ohlc"])
def test_indexed_sticky_rejection_matches_cumulative_after_bad_bar_ages_out(
    corruption: str,
) -> None:
    start = date(2026, 1, 1)
    bars = list(_uptrend_history("ACME", start, Decimal("1"), count=256))
    first = bars[0]
    if corruption == "zero-volume":
        bars[0] = DailyBar(
            first.symbol,
            first.date,
            first.open,
            first.high,
            first.low,
            first.close,
            0,
        )
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
    scanner = MomentumSelectionScanner()

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


def test_single_run_rejects_candidates_at_different_layers() -> None:
    start = date(2026, 1, 1)
    short_bars = _uptrend_history("SHORT", start, Decimal("1"), count=252)
    prox_bars = _proximity_reject_history("PROX", start)
    low_bars = tuple(
        bar
        for symbol in ("LOW1", "LOW2", "LOW3")
        for bar in _uptrend_history(symbol, start, Decimal("0.1"))
    )
    universe = Universe("v1", ("SHORT", "PROX", "LOW1", "LOW2", "LOW3"))

    decisions = MomentumSelectionScanner().scan(universe, short_bars + prox_bars + low_bars)

    reasons = {decision.symbol: decision.reason for decision in decisions}
    assert reasons["SHORT"] is RejectionReason.INSUFFICIENT_HISTORY
    assert reasons["PROX"] is RejectionReason.BELOW_52_WEEK_HIGH_PROXIMITY
    assert reasons["LOW1"] is RejectionReason.NOT_TOP_MOMENTUM_RANK
    assert reasons["LOW2"] is RejectionReason.NOT_TOP_MOMENTUM_RANK
    assert reasons["LOW3"] is RejectionReason.NOT_TOP_MOMENTUM_RANK
    assert not any(decision.accepted for decision in decisions)


def test_rejects_zero_volume_bars_as_missing_data_and_excludes_from_ranking() -> None:
    start = date(2026, 1, 1)
    corrupted = list(_uptrend_history("ZVOL", start, Decimal("9")))
    broken = corrupted[100]
    corrupted[100] = DailyBar(
        symbol="ZVOL",
        date=broken.date,
        open=broken.open,
        high=broken.high,
        low=broken.low,
        close=broken.close,
        volume=0,
    )
    clean = _uptrend_history("WIN", start, Decimal("1"))
    universe = Universe("v1", ("ZVOL", "WIN"))

    decisions = {decision.symbol: decision for decision in MomentumSelectionScanner().scan(universe, tuple(corrupted) + clean)}

    assert not decisions["ZVOL"].accepted
    assert decisions["ZVOL"].reason is RejectionReason.MISSING_DATA
    assert decisions["WIN"].accepted


def test_rejects_invalid_ohlc_bars_as_domain_invariant_violation() -> None:
    start = date(2026, 1, 1)
    corrupted = list(_uptrend_history("BAD", start, Decimal("1")))
    broken = corrupted[50]
    corrupted[50] = DailyBar(
        symbol="BAD",
        date=broken.date,
        open=broken.open,
        high=broken.low,
        low=broken.high,
        close=broken.close,
        volume=1000,
    )

    decisions = MomentumSelectionScanner().scan(Universe("v1", ("BAD",)), tuple(corrupted))

    assert len(decisions) == 1
    assert not decisions[0].accepted
    assert decisions[0].reason is RejectionReason.DOMAIN_INVARIANT_VIOLATION
