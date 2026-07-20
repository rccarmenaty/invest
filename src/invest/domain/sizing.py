from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum

from invest.domain.indicators import average_true_range
from invest.domain.models import AccountSnapshot, DailyBar, OrderIntent

RISK_PER_TRADE = Decimal("0.0035")
STOP_ATR_DAYS = 20
STOP_ATR_MULTIPLIER = Decimal("2")
TAKE_PROFIT_ATR_MULTIPLIER = Decimal("2")
WHOLE_CENT_TICK = Decimal("0.01")
SUB_PENNY_TICK = Decimal("0.0001")
SUB_PENNY_THRESHOLD = Decimal("1")
MAX_CONCURRENT_POSITIONS = 5
MAX_EQUITY_DEPLOYED_RATIO = Decimal("0.25")
KILL_SWITCH_DRAWDOWN = Decimal("-0.03")


class GateReason(StrEnum):
    KILL_SWITCH = "kill-switch"
    BROKER_ACCOUNT_RESTRICTED = "broker-account-restricted"
    MAX_CONCURRENT_POSITIONS = "max-concurrent-positions"
    SIZING_INVALID = "sizing-invalid"
    MAX_EQUITY_DEPLOYED = "max-equity-deployed"
    INSUFFICIENT_BUYING_POWER = "insufficient-buying-power"
    ALREADY_SUBMITTED = "already-submitted"


def quantize_price(price: Decimal) -> Decimal:
    tick = WHOLE_CENT_TICK if price >= SUB_PENNY_THRESHOLD else SUB_PENNY_TICK
    return price.quantize(tick, rounding=ROUND_HALF_EVEN)


def compute_intent(
    symbol: str,
    decision_date: date,
    equity: Decimal,
    history: list[DailyBar],
    entry_price: Decimal,
    breakout_low: Decimal,
) -> tuple[OrderIntent | None, GateReason | None]:
    risk_capital = equity * RISK_PER_TRADE
    atr = average_true_range(history, period=STOP_ATR_DAYS)
    entry = quantize_price(entry_price)
    stop = quantize_price(min(quantize_price(breakout_low), entry - STOP_ATR_MULTIPLIER * atr))
    take_profit = quantize_price(entry + TAKE_PROFIT_ATR_MULTIPLIER * atr)

    stop_distance = entry - stop
    if stop_distance <= 0:
        return None, GateReason.SIZING_INVALID

    qty = int(risk_capital // stop_distance)
    if qty <= 0:
        return None, GateReason.SIZING_INVALID

    intent = OrderIntent(
        symbol=symbol,
        decision_date=decision_date,
        qty=qty,
        entry=entry,
        stop=stop,
        take_profit=take_profit,
    )
    return intent, None


def evaluate_halt_gates(snapshot: AccountSnapshot) -> GateReason | None:
    """Evaluated once from the account snapshot, before any candidate sizing."""
    if snapshot.last_equity <= 0:
        return GateReason.KILL_SWITCH
    drawdown = (snapshot.equity - snapshot.last_equity) / snapshot.last_equity
    if drawdown <= KILL_SWITCH_DRAWDOWN:
        return GateReason.KILL_SWITCH
    if snapshot.trading_blocked or snapshot.account_blocked:
        return GateReason.BROKER_ACCOUNT_RESTRICTED
    return None


def evaluate_gates(
    intent: OrderIntent | None,
    sizing_reason: GateReason | None,
    snapshot: AccountSnapshot,
    open_position_count: int,
    deployed_value: Decimal,
    available_buying_power: Decimal | None = None,
    max_concurrent_positions: int = MAX_CONCURRENT_POSITIONS,
) -> GateReason | None:
    """Per-candidate predicate chain; first failure wins.

    `open_position_count`/`deployed_value` are a running projection seeded from the
    snapshot and incremented per accepted candidate within a run, so intra-run caps hold.
    `max_concurrent_positions` defaults to the live day-0 cap; backtests may raise it
    (Phase 2 portfolio structure uses a predeclared higher slot cap).
    """
    if open_position_count >= max_concurrent_positions:
        return GateReason.MAX_CONCURRENT_POSITIONS
    if intent is None or sizing_reason is not None:
        return sizing_reason if sizing_reason is not None else GateReason.SIZING_INVALID
    if deployed_value + intent.qty * intent.entry >= MAX_EQUITY_DEPLOYED_RATIO * snapshot.equity:
        return GateReason.MAX_EQUITY_DEPLOYED
    if intent.qty * intent.entry > (
        snapshot.buying_power if available_buying_power is None else available_buying_power
    ):
        return GateReason.INSUFFICIENT_BUYING_POWER
    return None
