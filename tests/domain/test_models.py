from datetime import date
from decimal import Decimal

from invest.domain.models import AccountSnapshot, OrderIntent


def test_account_snapshot_is_a_frozen_decimal_dataclass() -> None:
    snapshot = AccountSnapshot(
        equity=Decimal("100000"),
        last_equity=Decimal("100000"),
        buying_power=Decimal("100000"),
        open_position_count=0,
        deployed_value=Decimal("0"),
        trading_blocked=False,
        account_blocked=False,
    )

    assert snapshot.equity == Decimal("100000")
    assert snapshot.open_position_count == 0
    assert snapshot.trading_blocked is False
    assert snapshot.account_blocked is False

    try:
        snapshot.equity = Decimal("1")  # type: ignore[misc]
    except Exception as error:
        assert isinstance(error, Exception)
    else:
        raise AssertionError("AccountSnapshot must be frozen")


def test_order_intent_is_a_frozen_decimal_dataclass() -> None:
    intent = OrderIntent(
        symbol="ACME",
        decision_date=date(2026, 1, 1),
        qty=10,
        entry=Decimal("10.00"),
        stop=Decimal("9.00"),
        take_profit=Decimal("12.00"),
    )

    assert intent.symbol == "ACME"
    assert intent.qty == 10
    assert intent.entry == Decimal("10.00")

    try:
        intent.qty = 20  # type: ignore[misc]
    except Exception as error:
        assert isinstance(error, Exception)
    else:
        raise AssertionError("OrderIntent must be frozen")
