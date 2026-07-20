"""Pure, clock-free exit policy for backtest replay.

Evaluates hard-stop, trailing-channel / ATR-trail, and conditional time-stop
decisions from completed OHLC history only. No wall-clock, I/O, network, or
broker dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from invest.domain.indicators import average_true_range, trailing_low
from invest.domain.models import DailyBar

KIND_TEN_DAY_LOW = "ten-day-low"
KIND_ATR_3_HIGH_WATER = "atr-3-high-water"
KIND_FIXED_HORIZON = "fixed-horizon"
REASON_STOP = "stop"
REASON_TRAILING_CHANNEL = "trailing-channel"
REASON_ATR_TRAIL = "atr-trail"
REASON_TIME_STOP = "time-stop"
REASON_FIXED_HORIZON = "fixed-horizon"
PRIOR_HIGH_WINDOW = 20


@dataclass(frozen=True)
class ExitPolicyConfig:
    kind: str = KIND_TEN_DAY_LOW
    channel_window: int = 10
    time_stop_sessions: int = 20
    half_r: Decimal = Decimal("0.5")
    atr_mult: Decimal = Decimal("3")
    horizon_sessions: int = 60


@dataclass(frozen=True)
class ExitPolicyState:
    initial_stop: Decimal
    effective_floor: Decimal
    entry_price: Decimal
    pending_exit_reason: str | None = None
    sessions_held: int = 0
    reached_half_r: bool = False
    printed_new_prior20_high: bool = False
    high_water: Decimal | None = None


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
        high_water=None,
    )


def policy_provenance(config: ExitPolicyConfig) -> dict[str, str | int]:
    """Stable report-facing policy parameters (JSON-serializable, sort_keys-friendly)."""
    return {
        "atr_mult": str(config.atr_mult),
        "channel_window": config.channel_window,
        "half_r": str(config.half_r),
        "horizon_sessions": config.horizon_sessions,
        "kind": config.kind,
        "time_stop_sessions": config.time_stop_sessions,
    }


def resolve_exit_policy(kind: str) -> ExitPolicyConfig:
    if kind == KIND_ATR_3_HIGH_WATER:
        return ExitPolicyConfig(kind=KIND_ATR_3_HIGH_WATER)
    if kind == KIND_TEN_DAY_LOW:
        return ExitPolicyConfig(kind=KIND_TEN_DAY_LOW)
    if kind == KIND_FIXED_HORIZON:
        return ExitPolicyConfig(kind=KIND_FIXED_HORIZON)
    raise ValueError(f"unknown exit policy kind: {kind}")


def allows_price_path_exits(config: ExitPolicyConfig) -> bool:
    """False for fixed-horizon: no hard stop in policy and no take-profit in replay."""
    return config.kind != KIND_FIXED_HORIZON


def on_bar(
    state: ExitPolicyState,
    bar: DailyBar,
    history_through_bar: Sequence[DailyBar],
    config: ExitPolicyConfig,
) -> tuple[ExitPolicyState, ExitDecision | None]:
    """Hard-stop same-bar decision, pending next-open fill, or state/pending update.

    Priority: (1) hard stop (skipped for fixed-horizon) (2) pending fill (3) update + evaluate.
    Trail/ATR pending outranks time-stop when both would apply on the evaluate step.
    Fixed-horizon: no stop/trail/TP; after horizon_sessions, pending fixed-horizon → next open.
    """
    if config.kind != KIND_FIXED_HORIZON and bar.low <= state.initial_stop:
        return state, ExitDecision(reason=REASON_STOP, fill_price=min(bar.open, state.initial_stop))

    if state.pending_exit_reason is not None:
        return state, ExitDecision(reason=state.pending_exit_reason, fill_price=bar.open)

    sessions_held = state.sessions_held + 1

    if config.kind == KIND_FIXED_HORIZON:
        pending = (
            REASON_FIXED_HORIZON if sessions_held >= config.horizon_sessions else None
        )
        return (
            ExitPolicyState(
                initial_stop=state.initial_stop,
                effective_floor=state.effective_floor,
                entry_price=state.entry_price,
                pending_exit_reason=pending,
                sessions_held=sessions_held,
                reached_half_r=state.reached_half_r,
                printed_new_prior20_high=state.printed_new_prior20_high,
                high_water=state.high_water,
            ),
            None,
        )

    risk = state.entry_price - state.initial_stop
    half_r_level = state.entry_price + config.half_r * risk
    reached_half_r = state.reached_half_r or (bar.high >= half_r_level)

    history_before = list(history_through_bar[:-1]) if history_through_bar else []
    printed_new_prior20_high = state.printed_new_prior20_high
    if len(history_before) >= PRIOR_HIGH_WINDOW:
        prior_closes = [item.close for item in history_before[-PRIOR_HIGH_WINDOW:]]
        if bar.close > max(prior_closes):
            printed_new_prior20_high = True

    high_water = state.high_water
    new_floor = state.effective_floor
    trail_pending: str | None = None

    if config.kind == KIND_TEN_DAY_LOW:
        if len(history_before) >= config.channel_window:
            prior_low = trailing_low(history_before, config.channel_window)
            new_floor = max(state.initial_stop, state.effective_floor, prior_low)
            if bar.close < prior_low:
                trail_pending = REASON_TRAILING_CHANNEL
    elif config.kind == KIND_ATR_3_HIGH_WATER:
        high_water = bar.high if high_water is None else max(high_water, bar.high)
        history_list = list(history_through_bar)
        if history_list:
            atr = average_true_range(history_list)
            candidate = high_water - config.atr_mult * atr
            new_floor = max(state.initial_stop, state.effective_floor, candidate)
            if bar.close < new_floor:
                trail_pending = REASON_ATR_TRAIL
    else:
        return state, None

    pending = trail_pending
    if pending is None and (
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
            high_water=high_water,
        ),
        None,
    )
