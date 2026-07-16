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
    state = initial_state(initial_stop=Decimal("8.00"), entry_price=Decimal("11.00"))

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
        entry_price=Decimal("11.00"),
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
    state = initial_state(initial_stop=Decimal("8.00"), entry_price=Decimal("11.00"))

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
    state = initial_state(initial_stop=Decimal("8.00"), entry_price=Decimal("11.00"))

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
        entry_price=Decimal("11.00"),
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
        entry_price=Decimal("11.00"),
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
        entry_price=Decimal("10.00"),
        pending_exit_reason=None,
    )
    config = ExitPolicyConfig(kind="ten-day-low", channel_window=10)

    on_bar(state, signal, history + [signal], config)

    assert state.pending_exit_reason is None
    assert state.effective_floor == Decimal("8.00")


def _run_hold(
    *,
    entry: Decimal,
    stop: Decimal,
    hold_bars: list[DailyBar],
    prior_history: list[DailyBar] | None = None,
    config=None,
):
    """Replay pure on_bar across hold sessions; returns final state and last decision."""
    from invest.domain.exit_policy import ExitPolicyConfig, initial_state, on_bar

    if config is None:
        config = ExitPolicyConfig(kind="ten-day-low", channel_window=10, time_stop_sessions=20)
    state = initial_state(initial_stop=stop, entry_price=entry)
    history = list(prior_history or [])
    last_decision = None
    for bar in hold_bars:
        history = history + [bar]
        state, last_decision = on_bar(state, bar, history, config)
        if last_decision is not None:
            break
    return state, last_decision


def test_time_stop_after_20_held_sessions_without_progress() -> None:
    """After 20th held close with no +0.5R and no new prior-20 high → pending time-stop."""
    start = date(2026, 1, 1)
    entry = Decimal("10.00")
    stop = Decimal("9.00")  # R=1.00; half-R level = 10.50
    # Prior history so channel window is available but close never breaks prior low.
    prior = _flat_history(start, 20, low="9.50", high="10.20", close="10.00")
    # 20 held sessions: highs stay below 10.50; closes stay at 10.00 (no new prior-20 high).
    holds = [
        _bar(
            start + timedelta(days=20 + i),
            high="10.40",
            low="9.80",
            close="10.00",
            open_="10.00",
        )
        for i in range(20)
    ]

    state, decision = _run_hold(entry=entry, stop=stop, hold_bars=holds, prior_history=prior)

    assert decision is None  # signal only — fill next open
    assert state.sessions_held == 20
    assert state.reached_half_r is False
    assert state.printed_new_prior20_high is False
    assert state.pending_exit_reason == "time-stop"


def test_time_stop_suppressed_when_half_r_reached() -> None:
    start = date(2026, 1, 1)
    entry = Decimal("10.00")
    stop = Decimal("9.00")  # half-R = 10.50
    prior = _flat_history(start, 20, low="9.50", high="10.20", close="10.00")
    holds = [
        _bar(
            start + timedelta(days=20 + i),
            high="10.40" if i != 5 else "10.60",  # day 6 touches +0.5R
            low="9.80",
            close="10.00",
            open_="10.00",
        )
        for i in range(20)
    ]

    state, decision = _run_hold(entry=entry, stop=stop, hold_bars=holds, prior_history=prior)

    assert decision is None
    assert state.sessions_held == 20
    assert state.reached_half_r is True
    assert state.pending_exit_reason is None


def test_time_stop_suppressed_when_new_prior20_closing_high_printed() -> None:
    start = date(2026, 1, 1)
    entry = Decimal("10.00")
    stop = Decimal("9.00")
    prior = _flat_history(start, 20, low="9.50", high="10.20", close="10.00")
    holds = [
        _bar(
            start + timedelta(days=20 + i),
            high="10.40",
            low="9.80",
            # session 10 prints close above prior-20 max (10.00)
            close="10.00" if i != 9 else "10.25",
            open_="10.00",
        )
        for i in range(20)
    ]

    state, decision = _run_hold(entry=entry, stop=stop, hold_bars=holds, prior_history=prior)

    assert decision is None
    assert state.sessions_held == 20
    assert state.printed_new_prior20_high is True
    assert state.pending_exit_reason is None


def test_hard_stop_beats_pending_time_stop_on_same_bar() -> None:
    from invest.domain.exit_policy import ExitDecision, ExitPolicyConfig, ExitPolicyState, on_bar

    start = date(2026, 1, 1)
    bar = _bar(start, high="12", low="7", close="8", open_="11")
    state = ExitPolicyState(
        initial_stop=Decimal("8.00"),
        effective_floor=Decimal("9.00"),
        entry_price=Decimal("10.00"),
        sessions_held=20,
        pending_exit_reason="time-stop",
    )
    config = ExitPolicyConfig(kind="ten-day-low", channel_window=10, time_stop_sessions=20)

    _, decision = on_bar(state, bar, [bar], config)

    assert decision == ExitDecision(reason="stop", fill_price=Decimal("8.00"))


def test_pending_trailing_channel_beats_time_stop_fill() -> None:
    """If pending is trailing-channel, fill reason is trailing-channel (priority over time-stop)."""
    from invest.domain.exit_policy import ExitDecision, ExitPolicyConfig, ExitPolicyState, on_bar

    start = date(2026, 1, 1)
    bar = _bar(start, high="12", low="10", close="11", open_="10.50")
    state = ExitPolicyState(
        initial_stop=Decimal("8.00"),
        effective_floor=Decimal("9.00"),
        entry_price=Decimal("10.00"),
        sessions_held=20,
        pending_exit_reason="trailing-channel",
    )
    config = ExitPolicyConfig(kind="ten-day-low", channel_window=10, time_stop_sessions=20)

    _, decision = on_bar(state, bar, [bar], config)

    assert decision == ExitDecision(reason="trailing-channel", fill_price=Decimal("10.50"))


def test_channel_signal_on_20th_session_takes_priority_over_time_stop() -> None:
    """Same-bar evaluate: channel break sets trailing-channel, not time-stop."""
    start = date(2026, 1, 1)
    entry = Decimal("12.00")
    stop = Decimal("10.00")  # half-R = 13.00; highs stay below
    prior = _flat_history(start, 20, low="11.00", high="12.50", close="12.00")
    holds = [
        _bar(
            start + timedelta(days=20 + i),
            high="12.50",
            low="11.20",
            close="12.00",
            open_="12.00",
        )
        for i in range(19)
    ]
    # 20th session: close strictly below prior-10 low (11.00 after elevated lows roll)
    # After 19 holds with low 11.20, prior-10 low ≈ 11.20; break with close 11.00
    holds.append(
        _bar(start + timedelta(days=39), high="11.50", low="11.05", close="11.00", open_="12.00")
    )

    state, decision = _run_hold(entry=entry, stop=stop, hold_bars=holds, prior_history=prior)

    assert decision is None
    assert state.sessions_held == 20
    assert state.pending_exit_reason == "trailing-channel"


def test_pending_time_stop_fills_at_next_open() -> None:
    from invest.domain.exit_policy import ExitDecision, ExitPolicyConfig, ExitPolicyState, on_bar

    start = date(2026, 1, 1)
    bar = _bar(start, high="12", low="10", close="11", open_="10.10")
    state = ExitPolicyState(
        initial_stop=Decimal("8.00"),
        effective_floor=Decimal("9.00"),
        entry_price=Decimal("10.00"),
        sessions_held=20,
        pending_exit_reason="time-stop",
    )
    config = ExitPolicyConfig(kind="ten-day-low", channel_window=10, time_stop_sessions=20)

    _, decision = on_bar(state, bar, [bar], config)

    assert decision == ExitDecision(reason="time-stop", fill_price=Decimal("10.10"))
