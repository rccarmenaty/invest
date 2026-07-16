from datetime import date
from decimal import Decimal

from invest.domain.models import SimulatedTrade


def _trade(symbol: str, entry_date: date, exit_date: date, entry: str, exit_: str, qty: int, reason: str) -> SimulatedTrade:
    return SimulatedTrade(symbol, entry_date, exit_date, Decimal(entry), Decimal(exit_), qty, reason)


def test_compute_metrics_hand_computed_hit_rate_expectancy_drawdown_trade_count() -> None:
    from invest.domain.backtest_metrics import compute_metrics

    trades = [
        _trade("A", date(2026, 1, 2), date(2026, 1, 5), "100", "110", 10, "take-profit"),  # net = +100
        _trade("B", date(2026, 1, 3), date(2026, 1, 6), "100", "90", 10, "stop"),  # net = -100
        _trade("C", date(2026, 1, 4), date(2026, 1, 7), "100", "105", 10, "take-profit"),  # net = +50
    ]
    # exit order: A(1/5)=+100, B(1/6)=-100, C(1/7)=+50
    # cumulative: 100, 0, 50 ; peak: 100, 100, 100 ; drawdown: 0, 100, 50 -> max = 100

    metrics = compute_metrics(trades, slippage_bps=Decimal("0"), tax_rate=Decimal("0"))

    assert metrics.trade_count == 3
    assert metrics.hit_rate == Decimal("2") / Decimal("3")
    assert metrics.net_pnl == Decimal("50")
    assert metrics.expectancy == Decimal("50") / Decimal("3")
    assert metrics.max_drawdown == Decimal("100")


def test_compute_metrics_empty_trade_log_is_all_zeros() -> None:
    from invest.domain.backtest_metrics import compute_metrics

    metrics = compute_metrics([], slippage_bps=Decimal("5"), tax_rate=Decimal("0.15"))

    assert metrics.trade_count == 0
    assert metrics.hit_rate == Decimal("0")
    assert metrics.expectancy == Decimal("0")
    assert metrics.max_drawdown == Decimal("0")
    assert metrics.net_pnl == Decimal("0")


def test_apply_costs_hand_computed_slippage_both_sides_and_tax_on_gains_only() -> None:
    from invest.domain.backtest_metrics import apply_costs

    trade = _trade("A", date(2026, 1, 2), date(2026, 1, 5), "100", "110", 10, "take-profit")
    slippage_bps = Decimal("5")
    tax_rate = Decimal("0.15")

    net = apply_costs(trade, slippage_bps, tax_rate)

    entry_fill = Decimal("100") * (Decimal("1") + slippage_bps / Decimal("10000"))  # 100.05
    exit_fill = Decimal("110") * (Decimal("1") - slippage_bps / Decimal("10000"))  # 109.945
    gross = (exit_fill - entry_fill) * 10  # 98.95
    expected = gross * (Decimal("1") - tax_rate)  # gain -> tax haircut applies

    assert gross > 0
    assert net == expected


def test_apply_costs_no_tax_haircut_on_a_losing_trade() -> None:
    from invest.domain.backtest_metrics import apply_costs

    trade = _trade("A", date(2026, 1, 2), date(2026, 1, 5), "100", "90", 10, "stop")
    slippage_bps = Decimal("5")
    tax_rate = Decimal("0.15")

    net = apply_costs(trade, slippage_bps, tax_rate)

    entry_fill = Decimal("100") * (Decimal("1") + slippage_bps / Decimal("10000"))
    exit_fill = Decimal("90") * (Decimal("1") - slippage_bps / Decimal("10000"))
    gross = (exit_fill - entry_fill) * 10

    assert gross <= 0
    assert net == gross  # no tax on losses -- tax applies to net gains only


def test_exit_reason_enum_matches_exact_contract_set() -> None:
    from invest.domain.backtest_metrics import ExitReason

    # Active contract set after trailing-exit units (no take-profit).
    assert {reason.value for reason in ExitReason} == {
        "stop",
        "trailing-channel",
        "time-stop",
        "atr-trail",
        "open-at-end",
    }
    assert "take-profit" not in {reason.value for reason in ExitReason}


def test_equity_summary_reports_drawdown_and_is_deterministic() -> None:
    from invest.domain.backtest_metrics import compute_equity_summary

    samples = [
        (date(2026, 1, 2), Decimal("100")),
        (date(2026, 1, 3), Decimal("120")),
        (date(2026, 1, 4), Decimal("90")),
        (date(2026, 1, 5), Decimal("110")),
    ]

    first = compute_equity_summary(samples)
    second = compute_equity_summary(samples)

    assert first == second
    assert first.starting_equity == Decimal("100")
    assert first.ending_equity == Decimal("110")
    assert first.min_equity == Decimal("90")
    assert first.max_equity == Decimal("120")
    assert first.max_drawdown == Decimal("30")
    assert first.total_return == Decimal("0.10")
    assert first.trading_day_count == 4


def test_segment_metrics_classifies_split_date_entries_as_oos() -> None:
    from invest.domain.backtest_metrics import compute_segment_metrics

    trades = [
        _trade("IS", date(2026, 1, 2), date(2026, 1, 4), "10", "12", 1, "take-profit"),
        _trade("OOS", date(2026, 1, 5), date(2026, 1, 6), "10", "8", 1, "stop"),
        _trade("AFTER", date(2026, 1, 6), date(2026, 1, 7), "10", "11", 1, "take-profit"),
    ]

    segments = compute_segment_metrics(trades, date(2026, 1, 5), Decimal("0"), Decimal("0"))

    assert segments["is"].trade_count == 1
    assert segments["is"].net_pnl == Decimal("2")
    assert segments["oos"].trade_count == 2
    assert segments["oos"].net_pnl == Decimal("-1")
