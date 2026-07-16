"""Pure, clock-free exit policy for backtest replay.

Evaluates hard-stop, trailing-channel, and conditional time-stop decisions from
completed OHLC history only. No wall-clock, I/O, network, or broker dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from invest.domain.indicators import trailing_low
from invest.domain.models import DailyBar

KIND_TEN_DAY_LOW = "ten-day-low"
REASON_STOP = "stop"
REASON_TRAILING_CHANNEL = "trailing-channel"
REASON_TIME_STOP = "time-stop"
PRIOR_HIGH_WINDOW = 20


@dataclass(frozen=True)
class ExitPolicyConfig:
    kind: str = KIND_TEN_DAY_LOW
    channel_window: int = 10
    time_stop_sessions: int = 20
    half_r: Decimal = Decimal("0.5")


@dataclass(frozen=True)
class ExitPolicyState:
    initial_stop: Decimal
    effective_floor: Decimal
    entry_price: Decimal
    pending_exit_reason: str | None = None
    sessions_held: int = 0
    reached_half_r: bool = False
    printed_new_prior20_high: bool = False


@dataclass(frozen=True)
class ExitDecision:
    reason: str
    fill_price: Decimal


def initial_state(*, initial_stop: Decimal, entry_price: Decimal) -> ExitPolicyState:
    return ExitPolicyState(
        initial_stop=initial_stop,
        effective_floor=initial_stop,
        entry_price=entry_price,
        pending_exit_reason=None,
        sessions_held=0,
        reached_half_r=False,
        printed_new_prior20_high=False,
    )


def on_bar(
    state: ExitPolicyState,
    bar: DailyBar,
    history_through_bar: Sequence[DailyBar],
    config: ExitPolicyConfig,
) -> tuple[ExitPolicyState, ExitDecision | None]:
    """Hard-stop same-bar decision, pending next-open fill, or state/pending update.

    Priority: (1) hard stop (2) pending fill (3) update + evaluate.
    Pending fill reason preserves trail > time-stop ordering via which reason was set.
    """
    if bar.low <= state.initial_stop:
        return state, ExitDecision(reason=REASON_STOP, fill_price=min(bar.open, state.initial_stop))

    if state.pending_exit_reason is not None:
        return state, ExitDecision(reason=state.pending_exit_reason, fill_price=bar.open)

    if config.kind != KIND_TEN_DAY_LOW:
        return state, None

    sessions_held = state.sessions_held + 1
    risk = state.entry_price - state.initial_stop
    half_r_level = state.entry_price + config.half_r * risk
    reached_half_r = state.reached_half_r or (bar.high >= half_r_level)

    history_before = list(history_through_bar[:-1]) if history_through_bar else []
    printed_new_prior20_high = state.printed_new_prior20_high
    if len(history_before) >= PRIOR_HIGH_WINDOW:
        prior_closes = [item.close for item in history_before[-PRIOR_HIGH_WINDOW:]]
        if bar.close > max(prior_closes):
            printed_new_prior20_high = True

    new_floor = state.effective_floor
    channel_pending = False
    if len(history_before) >= config.channel_window:
        prior_low = trailing_low(history_before, config.channel_window)
        new_floor = max(state.initial_stop, state.effective_floor, prior_low)
        channel_pending = bar.close < prior_low

    pending: str | None = None
    if channel_pending:
        pending = REASON_TRAILING_CHANNEL
    elif (
        sessions_held >= config.time_stop_sessions
        and not reached_half_r
        and not printed_new_prior20_high
    ):
        pending = REASON_TIME_STOP

    return (
        ExitPolicyState(
            initial_stop=state.initial_stop,
            effective_floor=new_floor,
            entry_price=state.entry_price,
            pending_exit_reason=pending,
            sessions_held=sessions_held,
            reached_half_r=reached_half_r,
            printed_new_prior20_high=printed_new_prior20_high,
        ),
        None,
    )
