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
    # ATR(20)=2 (uniform history) -> ATR leg = 100.50 - 2*2 = 96.50.
    # breakout_low=99 is above the ATR leg, so the ATR leg wins the min().
    history = _history(20, close=Decimal("100"), true_range=Decimal("2"))

    intent, reason = compute_intent(
        symbol="ACME",
        decision_date=date(2026, 1, 15),
        equity=Decimal("100000"),
        history=history,
        entry_price=Decimal("100.50"),
        breakout_low=Decimal("99"),
    )

    assert reason is None
    assert intent is not None
    assert intent.symbol == "ACME"
    assert intent.decision_date == date(2026, 1, 15)
    assert intent.entry == Decimal("100.50")
    assert intent.stop == Decimal("96.50")
    assert intent.take_profit == Decimal("104.50")
    # risk_capital = 100000*0.0035 = 350; stop_distance = 4.00 -> floor(350/4) = 87.
    assert intent.qty == 87


def test_compute_intent_floors_qty_on_non_integer_ratio() -> None:
    # ATR(20)=2 -> ATR leg = 100 - 4 = 96. breakout_low=94 is below it, so it wins.
    history = _history(20, close=Decimal("100"), true_range=Decimal("2"))

    intent, reason = compute_intent(
        symbol="ACME",
        decision_date=date(2026, 1, 15),
        equity=Decimal("100000"),
        history=history,
        entry_price=Decimal("100"),
        breakout_low=Decimal("94"),
    )

    assert reason is None
    assert intent is not None
    assert intent.stop == Decimal("94")
    # risk_capital=350, stop_distance=6 -> 58.33 floors to 58, not 59.
    assert intent.qty == 58


def test_compute_intent_skips_with_sizing_invalid_at_zero_qty() -> None:
    # ATR(20)=2 -> ATR leg = 100 - 4 = 96; breakout_low=99 above it, ATR leg wins,
    # stop_distance=4. risk_capital = 1000*0.0035 = 3.5 -> floor(3.5/4) == 0.
    history = _history(20, close=Decimal("100"), true_range=Decimal("2"))

    intent, reason = compute_intent(
        symbol="ACME",
        decision_date=date(2026, 1, 15),
        equity=Decimal("1000"),
        history=history,
        entry_price=Decimal("100"),
        breakout_low=Decimal("99"),
    )

    assert intent is None
    assert reason is GateReason.SIZING_INVALID


def test_compute_intent_skips_with_sizing_invalid_when_atr_makes_stop_distance_zero() -> None:
    # ATR(20)=0 (flat history) and breakout_low == entry -> both stop candidates equal entry.
    intent, reason = compute_intent(
        symbol="ACME",
        decision_date=date(2026, 1, 15),
        equity=Decimal("100000"),
        history=_history(20, close=Decimal("100"), true_range=Decimal("0")),
        entry_price=Decimal("100"),
        breakout_low=Decimal("100"),
    )

    assert intent is None
    assert reason is GateReason.SIZING_INVALID


def test_compute_intent_structural_stop_picks_the_lower_of_the_two_candidates() -> None:
    """Scenario: Structural stop picks the lower of the two candidates.

    GIVEN a breakout-day low and an entry-2*ATR(20) value where the breakout-day low
    is lower, THEN the stop MUST equal the breakout-day low, and take-profit MUST
    still be entry + 2*ATR(20), independent of which stop candidate wins.
    """
    history = _history(20, close=Decimal("100"), true_range=Decimal("2"))  # ATR(20)=2

    intent, reason = compute_intent(
        symbol="ACME",
        decision_date=date(2026, 1, 15),
        equity=Decimal("100000"),
        history=history,
        entry_price=Decimal("100"),
        breakout_low=Decimal("90"),  # far below the ATR leg (100 - 4 = 96)
    )

    assert reason is None
    assert intent is not None
    assert intent.stop == Decimal("90")
    assert intent.take_profit == Decimal("104")


def test_compute_intent_atr_leg_wins_when_breakout_low_is_the_higher_candidate() -> None:
    """Companion to the structural-stop scenario: when the ATR leg is lower than the
    breakout-day low, the ATR leg wins the min() -- and take-profit is unchanged."""
    history = _history(20, close=Decimal("100"), true_range=Decimal("2"))  # ATR(20)=2

    intent, reason = compute_intent(
        symbol="ACME",
        decision_date=date(2026, 1, 15),
        equity=Decimal("100000"),
        history=history,
        entry_price=Decimal("100"),
        breakout_low=Decimal("99"),  # above the ATR leg (100 - 4 = 96)
    )

    assert reason is None
    assert intent is not None
    assert intent.stop == Decimal("96")
    assert intent.take_profit == Decimal("104")


def test_compute_intent_gap_up_entry_resizes_from_the_actual_fill_price() -> None:
    """Scenario: Gap-up entry re-sizes from the actual fill price.

    A candidate whose fill-day open gaps above the level used at scan time must have
    entry, stop, and qty all computed from the actual fill-day open passed in.
    """
    history = _history(20, close=Decimal("100"), true_range=Decimal("2"))  # ATR(20)=2

    intent, reason = compute_intent(
        symbol="ACME",
        decision_date=date(2026, 1, 15),
        equity=Decimal("100000"),
        history=history,
        entry_price=Decimal("105"),  # gapped up from the 100 level used to build `history`
        breakout_low=Decimal("99"),
    )

    assert reason is None
    assert intent is not None
    assert intent.entry == Decimal("105")
    # ATR leg = 105 - 4 = 101, above breakout_low=99 -> breakout_low wins the min().
    assert intent.stop == Decimal("99")
    # stop_distance = 6 -> qty reflects the gapped-up entry's own distance, not scan-time.
    assert intent.qty == 58


def test_compute_intent_degenerate_stop_distance_skips_the_intent() -> None:
    """Scenario: Degenerate stop distance skips the intent (stop >= entry)."""
    intent, reason = compute_intent(
        symbol="ACME",
        decision_date=date(2026, 1, 15),
        equity=Decimal("100000"),
        history=_history(20, close=Decimal("100"), true_range=Decimal("0")),
        entry_price=Decimal("100"),
        breakout_low=Decimal("101"),  # above entry -> stop clamps to entry via ATR leg (0)
    )

    assert intent is None
    assert reason is GateReason.SIZING_INVALID


def test_compute_intent_zero_or_negative_quantity_skips_the_intent() -> None:
    """Scenario: Zero or negative quantity skips the intent."""
    history = _history(20, close=Decimal("100"), true_range=Decimal("2"))  # ATR(20)=2

    intent, reason = compute_intent(
        symbol="ACME",
        decision_date=date(2026, 1, 15),
        equity=Decimal("1000"),  # risk_capital = 3.5
        history=history,
        entry_price=Decimal("100"),
        breakout_low=Decimal("99"),  # ATR leg wins, stop_distance=4 -> floor(3.5/4)==0
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


def test_evaluate_gates_honors_override_max_concurrent_positions() -> None:
    """Phase 2 portfolio structure uses a higher predeclared cap (e.g. 20)."""
    snapshot = _snapshot()
    intent = _intent()

    allowed_at_five = evaluate_gates(
        intent,
        None,
        snapshot,
        open_position_count=5,
        deployed_value=Decimal("0"),
        max_concurrent_positions=20,
    )
    blocked_at_twenty = evaluate_gates(
        intent,
        None,
        snapshot,
        open_position_count=20,
        deployed_value=Decimal("0"),
        max_concurrent_positions=20,
    )

    assert allowed_at_five is None
    assert blocked_at_twenty is GateReason.MAX_CONCURRENT_POSITIONS


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
