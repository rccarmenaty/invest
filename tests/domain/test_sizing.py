from datetime import date, timedelta
from decimal import Decimal

from invest.domain.models import AccountSnapshot, DailyBar, OrderIntent
from invest.domain.sizing import (
    GateReason,
    compute_intent,
    evaluate_gates,
    evaluate_halt_gates,
    quantize_price,
)


def _history(day_count: int, close: Decimal, true_range: Decimal) -> list[DailyBar]:
    half = true_range / 2
    return [
        DailyBar(
            symbol="ACME",
            date=date(2026, 1, 1) + timedelta(days=index),
            open=close,
            high=close + half,
            low=close - half,
            close=close,
            volume=1000,
        )
        for index in range(day_count)
    ]


def test_compute_intent_sizes_a_valid_bracket() -> None:
    history = _history(14, close=Decimal("100"), true_range=Decimal("2"))

    intent, reason = compute_intent(
        symbol="ACME",
        decision_date=date(2026, 1, 15),
        equity=Decimal("100000"),
        history=history,
        last_close=Decimal("100.50"),
    )

    assert reason is None
    assert intent is not None
    assert intent.symbol == "ACME"
    assert intent.decision_date == date(2026, 1, 15)
    assert intent.entry == Decimal("100.50")
    assert intent.stop == Decimal("98.50")
    assert intent.take_profit == Decimal("104.50")
    assert intent.qty == 500


def test_compute_intent_floors_qty_on_non_integer_ratio() -> None:
    history = _history(14, close=Decimal("100"), true_range=Decimal("3"))

    intent, reason = compute_intent(
        symbol="ACME",
        decision_date=date(2026, 1, 15),
        equity=Decimal("100000"),
        history=history,
        last_close=Decimal("100"),
    )

    assert reason is None
    assert intent is not None
    # risk_capital=1000, stop_distance=3 -> 333.33 floors to 333, not 334.
    assert intent.qty == 333


def test_compute_intent_skips_with_sizing_invalid_at_zero_qty() -> None:
    history = _history(14, close=Decimal("100"), true_range=Decimal("20"))

    intent, reason = compute_intent(
        symbol="ACME",
        decision_date=date(2026, 1, 15),
        equity=Decimal("1000"),
        history=history,
        last_close=Decimal("100"),
    )

    # risk_capital=10, stop_distance=20 -> floor(10/20) == 0.
    assert intent is None
    assert reason is GateReason.SIZING_INVALID


def test_compute_intent_skips_with_sizing_invalid_when_atr_makes_stop_distance_zero() -> None:
    intent, reason = compute_intent(
        symbol="ACME",
        decision_date=date(2026, 1, 15),
        equity=Decimal("100000"),
        history=_history(14, close=Decimal("100"), true_range=Decimal("0")),
        last_close=Decimal("100"),
    )

    assert intent is None
    assert reason is GateReason.SIZING_INVALID


def test_quantize_price_uses_whole_cents_at_or_above_one_dollar() -> None:
    quantized = quantize_price(Decimal("1.00"))

    assert quantized == Decimal("1.00")
    assert quantized.as_tuple().exponent == -2


def test_quantize_price_uses_four_decimals_below_one_dollar() -> None:
    quantized = quantize_price(Decimal("0.9999"))

    assert quantized == Decimal("0.9999")
    assert quantized.as_tuple().exponent == -4


def test_quantize_price_rounds_half_to_even() -> None:
    assert quantize_price(Decimal("1.005")) == Decimal("1.00")
    assert quantize_price(Decimal("1.015")) == Decimal("1.02")


def _snapshot(**overrides: object) -> AccountSnapshot:
    defaults: dict[str, object] = dict(
        equity=Decimal("100000"),
        last_equity=Decimal("100000"),
        buying_power=Decimal("100000"),
        open_position_count=0,
        deployed_value=Decimal("0"),
        trading_blocked=False,
        account_blocked=False,
    )
    defaults.update(overrides)
    return AccountSnapshot(**defaults)  # type: ignore[arg-type]


def _intent(qty: int = 10, entry: Decimal = Decimal("100")) -> OrderIntent:
    return OrderIntent(
        symbol="ACME",
        decision_date=date(2026, 1, 15),
        qty=qty,
        entry=entry,
        stop=entry - Decimal("2"),
        take_profit=entry + Decimal("4"),
    )


def test_gate_reason_enum_matches_exact_contract_set() -> None:
    assert {reason.value for reason in GateReason} == {
        "kill-switch",
        "broker-account-restricted",
        "max-concurrent-positions",
        "sizing-invalid",
        "max-equity-deployed",
        "insufficient-buying-power",
        "already-submitted",
    }


def test_evaluate_gates_blocks_at_max_concurrent_positions() -> None:
    snapshot = _snapshot()
    intent = _intent()

    reason = evaluate_gates(intent, None, snapshot, open_position_count=5, deployed_value=Decimal("0"))

    assert reason is GateReason.MAX_CONCURRENT_POSITIONS


def test_evaluate_gates_blocks_at_sizing_invalid() -> None:
    snapshot = _snapshot()

    reason = evaluate_gates(None, GateReason.SIZING_INVALID, snapshot, open_position_count=0, deployed_value=Decimal("0"))

    assert reason is GateReason.SIZING_INVALID


def test_evaluate_gates_blocks_at_max_equity_deployed() -> None:
    snapshot = _snapshot(equity=Decimal("100000"))
    intent = _intent(qty=300, entry=Decimal("100"))  # 30000 > 25% of 100000 == 25000

    reason = evaluate_gates(intent, None, snapshot, open_position_count=0, deployed_value=Decimal("0"))

    assert reason is GateReason.MAX_EQUITY_DEPLOYED


def test_evaluate_gates_blocks_at_insufficient_buying_power() -> None:
    snapshot = _snapshot(equity=Decimal("1000000"), buying_power=Decimal("100"))
    intent = _intent(qty=10, entry=Decimal("100"))  # notional 1000 > buying_power 100, deployed check clears

    reason = evaluate_gates(intent, None, snapshot, open_position_count=0, deployed_value=Decimal("0"))

    assert reason is GateReason.INSUFFICIENT_BUYING_POWER


def test_evaluate_gates_passes_when_all_checks_clear() -> None:
    snapshot = _snapshot()
    intent = _intent(qty=10, entry=Decimal("100"))

    reason = evaluate_gates(intent, None, snapshot, open_position_count=0, deployed_value=Decimal("0"))

    assert reason is None


def test_evaluate_gates_first_failure_wins_when_multiple_conditions_true() -> None:
    # both max-concurrent-positions and sizing-invalid would apply; gate order picks
    # max-concurrent-positions since it is evaluated first.
    snapshot = _snapshot()

    reason = evaluate_gates(None, GateReason.SIZING_INVALID, snapshot, open_position_count=5, deployed_value=Decimal("0"))

    assert reason is GateReason.MAX_CONCURRENT_POSITIONS


def test_max_concurrent_positions_boundary_exactly_five_blocks_four_does_not() -> None:
    snapshot = _snapshot()
    intent = _intent()

    blocked = evaluate_gates(intent, None, snapshot, open_position_count=5, deployed_value=Decimal("0"))
    allowed = evaluate_gates(intent, None, snapshot, open_position_count=4, deployed_value=Decimal("0"))

    assert blocked is GateReason.MAX_CONCURRENT_POSITIONS
    assert allowed is None


def test_max_equity_deployed_boundary_exactly_twenty_five_percent_blocks_just_under_does_not() -> None:
    snapshot = _snapshot(equity=Decimal("100000"))
    at_boundary = _intent(qty=250, entry=Decimal("100"))  # 25000 == 25% of 100000
    just_under = _intent(qty=249, entry=Decimal("100"))  # 24900 < 25000

    blocked = evaluate_gates(at_boundary, None, snapshot, open_position_count=0, deployed_value=Decimal("0"))
    allowed = evaluate_gates(just_under, None, snapshot, open_position_count=0, deployed_value=Decimal("0"))

    assert blocked is GateReason.MAX_EQUITY_DEPLOYED
    assert allowed is None


def test_evaluate_gates_running_projection_blocks_second_candidate_combined_with_first() -> None:
    snapshot = _snapshot(equity=Decimal("100000"))
    first_intent = _intent(qty=200, entry=Decimal("100"))  # notional 20000, alone clears 25%
    second_intent = _intent(qty=100, entry=Decimal("100"))  # notional 10000, alone also clears 25%

    alone_reason = evaluate_gates(second_intent, None, snapshot, open_position_count=0, deployed_value=Decimal("0"))
    assert alone_reason is None

    running_deployed = Decimal("0") + first_intent.qty * first_intent.entry
    running_count = 1

    combined_reason = evaluate_gates(
        second_intent, None, snapshot, open_position_count=running_count, deployed_value=running_deployed
    )

    assert combined_reason is GateReason.MAX_EQUITY_DEPLOYED


def test_evaluate_halt_gates_kill_switch_boundary_exactly_negative_three_percent() -> None:
    at_boundary = _snapshot(equity=Decimal("97000"), last_equity=Decimal("100000"))
    just_above = _snapshot(equity=Decimal("97001"), last_equity=Decimal("100000"))

    assert evaluate_halt_gates(at_boundary) is GateReason.KILL_SWITCH
    assert evaluate_halt_gates(just_above) is None


def test_evaluate_halt_gates_broker_account_restricted_when_trading_blocked() -> None:
    snapshot = _snapshot(trading_blocked=True)

    assert evaluate_halt_gates(snapshot) is GateReason.BROKER_ACCOUNT_RESTRICTED


def test_evaluate_halt_gates_broker_account_restricted_when_account_blocked() -> None:
    snapshot = _snapshot(account_blocked=True)

    assert evaluate_halt_gates(snapshot) is GateReason.BROKER_ACCOUNT_RESTRICTED


def test_evaluate_halt_gates_passes_when_account_healthy() -> None:
    assert evaluate_halt_gates(_snapshot()) is None


def test_evaluate_halt_gates_fails_closed_without_positive_drawdown_baseline() -> None:
    assert evaluate_halt_gates(_snapshot(last_equity=Decimal("0"))) is GateReason.KILL_SWITCH
    assert evaluate_halt_gates(_snapshot(last_equity=Decimal("-1"))) is GateReason.KILL_SWITCH
