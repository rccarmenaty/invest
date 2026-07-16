"""Pure exit policy unit tests — clock/I/O free domain evaluation."""

from datetime import date, timedelta
from decimal import Decimal

from invest.domain.models import DailyBar


def _bar(
    day: date,
    *,
    high: str = "12",
    low: str = "10",
    close: str = "11",
    open_: str | None = None,
    symbol: str = "ACME",
) -> DailyBar:
    return DailyBar(
        symbol=symbol,
        date=day,
        open=Decimal(open_ if open_ is not None else close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=1000,
    )


def _flat_history(
    start: date,
    days: int,
    *,
    low: str = "10",
    high: str = "12",
    close: str = "11",
) -> list[DailyBar]:
    return [
        _bar(start + timedelta(days=i), high=high, low=low, close=close, open_=close) for i in range(days)
    ]


def test_floor_ratchets_up_to_prior_channel_low() -> None:
    from invest.domain.exit_policy import ExitPolicyConfig, initial_state, on_bar

    start = date(2026, 1, 1)
    history = _flat_history(start, 10, low="9.50", high="12", close="11")
    signal = _bar(start + timedelta(days=10), high="12", low="10", close="11", open_="11")
    config = ExitPolicyConfig(kind="ten-day-low", channel_window=10)
    state = initial_state(initial_stop=Decimal("8.00"))

    new_state, decision = on_bar(state, signal, history + [signal], config)

    assert decision is None
    assert new_state.effective_floor == Decimal("9.50")
    assert new_state.pending_exit_reason is None


def test_floor_only_ratchets_up_when_candidate_is_lower() -> None:
    from invest.domain.exit_policy import ExitPolicyConfig, ExitPolicyState, on_bar

    start = date(2026, 1, 1)
    # Prior floor already at 10.00; prior-10 lows are all 9.00 → candidate 9.00 must not loosen.
    history = _flat_history(start, 10, low="9.00", high="12", close="11")
    signal = _bar(start + timedelta(days=10), high="12", low="10", close="11", open_="11")
    state = ExitPolicyState(
        initial_stop=Decimal("8.00"),
        effective_floor=Decimal("10.00"),
        pending_exit_reason=None,
    )
    config = ExitPolicyConfig(kind="ten-day-low", channel_window=10)

    new_state, decision = on_bar(state, signal, history + [signal], config)

    assert decision is None
    assert new_state.effective_floor == Decimal("10.00")


def test_channel_strict_below_prior_low_sets_pending_trailing_channel() -> None:
    from invest.domain.exit_policy import ExitPolicyConfig, initial_state, on_bar

    start = date(2026, 1, 1)
    history = _flat_history(start, 10, low="10", high="12", close="11")
    # close strictly below prior-10 low (10)
    signal = _bar(start + timedelta(days=10), high="11", low="9.5", close="9.5", open_="10.5")
    config = ExitPolicyConfig(kind="ten-day-low", channel_window=10)
    state = initial_state(initial_stop=Decimal("8.00"))

    new_state, decision = on_bar(state, signal, history + [signal], config)

    assert decision is None  # close-signal only — fill is next open
    assert new_state.pending_exit_reason == "trailing-channel"


def test_channel_equal_close_to_prior_low_does_not_signal() -> None:
    from invest.domain.exit_policy import ExitPolicyConfig, initial_state, on_bar

    start = date(2026, 1, 1)
    history = _flat_history(start, 10, low="10", high="12", close="11")
    # close equal to prior-10 low → no signal
    signal = _bar(start + timedelta(days=10), high="11", low="9.5", close="10", open_="10.5")
    config = ExitPolicyConfig(kind="ten-day-low", channel_window=10)
    state = initial_state(initial_stop=Decimal("8.00"))

    new_state, decision = on_bar(state, signal, history + [signal], config)

    assert decision is None
    assert new_state.pending_exit_reason is None


def test_hard_stop_same_bar_beats_pending_trailing_channel() -> None:
    from invest.domain.exit_policy import ExitDecision, ExitPolicyConfig, ExitPolicyState, on_bar

    start = date(2026, 1, 1)
    # Pending trail from prior session; this bar also touches hard stop.
    bar = _bar(start, high="12", low="7", close="8", open_="11")
    state = ExitPolicyState(
        initial_stop=Decimal("8.00"),
        effective_floor=Decimal("9.00"),
        pending_exit_reason="trailing-channel",
    )
    config = ExitPolicyConfig(kind="ten-day-low", channel_window=10)

    _, decision = on_bar(state, bar, [bar], config)

    assert decision == ExitDecision(reason="stop", fill_price=Decimal("8.00"))
    assert decision.fill_price == min(bar.open, state.initial_stop)


def test_pending_trailing_channel_fills_at_next_open_when_no_hard_stop() -> None:
    from invest.domain.exit_policy import ExitDecision, ExitPolicyConfig, ExitPolicyState, on_bar

    start = date(2026, 1, 1)
    bar = _bar(start, high="12", low="10", close="11", open_="10.25")
    state = ExitPolicyState(
        initial_stop=Decimal("8.00"),
        effective_floor=Decimal("9.00"),
        pending_exit_reason="trailing-channel",
    )
    config = ExitPolicyConfig(kind="ten-day-low", channel_window=10)

    _, decision = on_bar(state, bar, [bar], config)

    assert decision == ExitDecision(reason="trailing-channel", fill_price=Decimal("10.25"))


def test_on_bar_does_not_mutate_input_state() -> None:
    from invest.domain.exit_policy import ExitPolicyConfig, ExitPolicyState, on_bar

    start = date(2026, 1, 1)
    history = _flat_history(start, 10, low="10", high="12", close="11")
    signal = _bar(start + timedelta(days=10), high="11", low="9.5", close="9.5", open_="10.5")
    state = ExitPolicyState(
        initial_stop=Decimal("8.00"),
        effective_floor=Decimal("8.00"),
        pending_exit_reason=None,
    )
    config = ExitPolicyConfig(kind="ten-day-low", channel_window=10)

    on_bar(state, signal, history + [signal], config)

    assert state.pending_exit_reason is None
    assert state.effective_floor == Decimal("8.00")
