"""Pure, clock-free exit policy for backtest replay.

Evaluates hard-stop and trailing-channel decisions from completed OHLC history
only. No wall-clock, I/O, network, or broker dependencies.
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


@dataclass(frozen=True)
class ExitPolicyConfig:
    kind: str = KIND_TEN_DAY_LOW
    channel_window: int = 10


@dataclass(frozen=True)
class ExitPolicyState:
    initial_stop: Decimal
    effective_floor: Decimal
    pending_exit_reason: str | None = None


@dataclass(frozen=True)
class ExitDecision:
    reason: str
    fill_price: Decimal


def initial_state(initial_stop: Decimal) -> ExitPolicyState:
    return ExitPolicyState(
        initial_stop=initial_stop,
        effective_floor=initial_stop,
        pending_exit_reason=None,
    )


def on_bar(
    state: ExitPolicyState,
    bar: DailyBar,
    history_through_bar: Sequence[DailyBar],
    config: ExitPolicyConfig,
) -> tuple[ExitPolicyState, ExitDecision | None]:
    """Hard-stop same-bar decision, pending next-open fill, or state/pending update.

    Priority: (1) hard stop (2) pending trailing fill (3) update + evaluate.
    """
    if bar.low <= state.initial_stop:
        return state, ExitDecision(reason=REASON_STOP, fill_price=min(bar.open, state.initial_stop))

    if state.pending_exit_reason is not None:
        return state, ExitDecision(reason=state.pending_exit_reason, fill_price=bar.open)

    if config.kind != KIND_TEN_DAY_LOW:
        return state, None

    history_before = list(history_through_bar[:-1]) if history_through_bar else []
    if len(history_before) < config.channel_window:
        return state, None

    prior_low = trailing_low(history_before, config.channel_window)
    new_floor = max(state.initial_stop, state.effective_floor, prior_low)
    pending = REASON_TRAILING_CHANNEL if bar.close < prior_low else None
    return (
        ExitPolicyState(
            initial_stop=state.initial_stop,
            effective_floor=new_floor,
            pending_exit_reason=pending,
        ),
        None,
    )
