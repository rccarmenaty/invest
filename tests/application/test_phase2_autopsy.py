"""Phase 2b concentration autopsy: leave-year book, S2 SPY match, K2 residual hope."""

from datetime import date
from decimal import Decimal

from invest.domain.models import SimulatedTrade

FC = "context-position-forced-closed"


def _t(
    symbol: str,
    entry: date,
    exit_: date,
    entry_px: str,
    exit_px: str,
    qty: int = 1,
    reason: str = "fixed-horizon",
) -> SimulatedTrade:
    return SimulatedTrade(
        symbol=symbol,
        entry_date=entry,
        exit_date=exit_,
        entry_price=Decimal(entry_px),
        exit_price=Decimal(exit_px),
        qty=qty,
        exit_reason=reason,
    )


def test_simulated_trades_from_records_round_trips_phase2_json_shape() -> None:
    from invest.application.phase2_report import simulated_trades_from_records

    records = [
        {
            "symbol": "DLTR",
            "entry_date": "2019-01-08",
            "exit_date": "2019-04-04",
            "entry_price": "98.325",
            "exit_price": "104.72",
            "qty": 76,
            "exit_reason": "fixed-horizon",
        }
    ]
    trades = simulated_trades_from_records(records)
    assert len(trades) == 1
    assert trades[0].symbol == "DLTR"
    assert trades[0].entry_date == date(2019, 1, 8)
    assert trades[0].qty == 76
    assert trades[0].entry_price == Decimal("98.325")


def test_trades_excluding_entry_year_drops_only_that_calendar_year() -> None:
    from invest.application.phase2_report import trades_excluding_entry_year

    trades = [
        _t("A", date(2020, 6, 1), date(2020, 8, 1), "100", "110"),
        _t("B", date(2021, 6, 1), date(2021, 8, 1), "100", "90"),
        _t("C", date(2019, 6, 1), date(2019, 8, 1), "100", "105"),
        _t("D", date(2020, 1, 2), date(2020, 3, 1), "50", "60", qty=2),
    ]
    left = trades_excluding_entry_year(trades, 2020)
    assert [t.symbol for t in left] == ["B", "C"]


def test_k2_dies_when_leave_year_mean_not_positive() -> None:
    from invest.application.phase2_report import evaluate_k2_residual_hope

    # Leave-2020: only losses → mean ≤ 0
    trades = [
        _t("W", date(2020, 1, 2), date(2020, 3, 1), "100", "200"),  # dropped
        _t("A", date(2021, 1, 2), date(2021, 3, 1), "100", "90"),
        _t("B", date(2022, 1, 2), date(2022, 3, 1), "100", "80"),
    ]
    full_mean = Decimal("10")  # irrelevant; leave mean is negative
    result = evaluate_k2_residual_hope(
        trades,
        leave_year=2020,
        full_book_mean_expectancy=full_mean,
        fold_years=(2021, 2022),
        slippage_bps=Decimal("0"),
        tax_rate=Decimal("0"),
        spy_opens={
            date(2021, 1, 2): Decimal("100"),
            date(2021, 3, 1): Decimal("100"),
            date(2022, 1, 2): Decimal("100"),
            date(2022, 3, 1): Decimal("100"),
        },
    )
    assert result.residual_hope == "die"
    assert result.leave_year_mean_positive is False
    assert any("mean" in r.lower() or "≤ 0" in r or "<= 0" in r for r in result.reasons)


def test_k2_dies_when_leave_year_mean_at_or_below_half_full_book_mean() -> None:
    from invest.application.phase2_report import (
        evaluate_k2_residual_hope,
        summarize_book,
        trades_excluding_entry_year,
    )

    # Full book mean will be high because of 2020 winner; leave-2020 is thin +5 each year
    trades = [
        _t("W", date(2020, 1, 2), date(2020, 3, 1), "100", "200"),  # +100
        _t("A", date(2021, 1, 2), date(2021, 3, 1), "100", "105"),  # +5
        _t("B", date(2022, 1, 2), date(2022, 3, 1), "100", "105"),  # +5
        _t("C", date(2023, 1, 2), date(2023, 3, 1), "100", "105"),  # +5
    ]
    full = summarize_book(trades, slippage_bps=Decimal("0"), tax_rate=Decimal("0"))
    leave = summarize_book(
        trades_excluding_entry_year(trades, 2020),
        slippage_bps=Decimal("0"),
        tax_rate=Decimal("0"),
    )
    # half full mean: full mean = (100+5+5+5)/4 = 28.75; half = 14.375; leave mean = 5 → die
    assert leave.mean_expectancy <= full.mean_expectancy / 2

    flat_spy = {
        date(2020, 1, 2): Decimal("100"),
        date(2020, 3, 1): Decimal("100"),
        date(2021, 1, 2): Decimal("100"),
        date(2021, 3, 1): Decimal("100"),
        date(2022, 1, 2): Decimal("100"),
        date(2022, 3, 1): Decimal("100"),
        date(2023, 1, 2): Decimal("100"),
        date(2023, 3, 1): Decimal("100"),
    }
    result = evaluate_k2_residual_hope(
        trades,
        leave_year=2020,
        full_book_mean_expectancy=full.mean_expectancy,
        fold_years=(2021, 2022, 2023),
        slippage_bps=Decimal("0"),
        tax_rate=Decimal("0"),
        spy_opens=flat_spy,
    )
    assert result.residual_hope == "die"
    assert result.half_mean_ok is False


def test_k2_dies_when_remaining_folds_fail_majority() -> None:
    from invest.application.phase2_report import evaluate_k2_residual_hope

    # Leave-2020: two loss years, one win → majority fails (1/3)
    # Make leave mean still positive and above half of a small full_mean by using big win
    trades = [
        _t("W", date(2020, 1, 2), date(2020, 3, 1), "100", "101"),
        _t("A", date(2021, 1, 2), date(2021, 3, 1), "100", "90"),   # -10
        _t("B", date(2022, 1, 2), date(2022, 3, 1), "100", "90"),   # -10
        _t("C", date(2023, 1, 2), date(2023, 3, 1), "100", "200"),  # +100
    ]
    # leave mean = 80/3 ≈ 26.7 > 0; full mean similar; set full_mean low so half-mean ok
    spy = {
        d: Decimal("100")
        for d in (
            date(2020, 1, 2),
            date(2020, 3, 1),
            date(2021, 1, 2),
            date(2021, 3, 1),
            date(2022, 1, 2),
            date(2022, 3, 1),
            date(2023, 1, 2),
            date(2023, 3, 1),
        )
    }
    result = evaluate_k2_residual_hope(
        trades,
        leave_year=2020,
        full_book_mean_expectancy=Decimal("1"),  # half=0.5; leave mean >> 0.5
        fold_years=(2021, 2022, 2023),
        slippage_bps=Decimal("0"),
        tax_rate=Decimal("0"),
        spy_opens=spy,
    )
    assert result.residual_hope == "die"
    assert result.majority_folds_positive is False


def test_matched_spy_pnl_uses_open_to_open_return_on_entry_notional() -> None:
    from invest.application.phase2_report import matched_spy_pnl

    trade = _t("A", date(2021, 1, 4), date(2021, 4, 5), "50", "60", qty=10)
    # notional = 50*10 = 500; SPY 100 → 110 = +10% → matched = +50
    spy_opens = {
        date(2021, 1, 4): Decimal("100"),
        date(2021, 4, 5): Decimal("110"),
    }
    assert matched_spy_pnl(trade, spy_opens) == Decimal("50")


def test_k2_dies_when_mean_trade_minus_spy_not_positive() -> None:
    from invest.application.phase2_report import evaluate_k2_residual_hope

    # Leave-2020 trades: stock +10 each, SPY also +10 on same notional → excess 0 → die
    trades = [
        _t("W", date(2020, 1, 2), date(2020, 3, 1), "100", "100"),
        _t("A", date(2021, 1, 2), date(2021, 3, 1), "100", "110"),
        _t("B", date(2022, 1, 2), date(2022, 3, 1), "100", "110"),
        _t("C", date(2023, 1, 2), date(2023, 3, 1), "100", "110"),
    ]
    spy = {
        date(2020, 1, 2): Decimal("100"),
        date(2020, 3, 1): Decimal("100"),
        date(2021, 1, 2): Decimal("100"),
        date(2021, 3, 1): Decimal("110"),
        date(2022, 1, 2): Decimal("100"),
        date(2022, 3, 1): Decimal("110"),
        date(2023, 1, 2): Decimal("100"),
        date(2023, 3, 1): Decimal("110"),
    }
    result = evaluate_k2_residual_hope(
        trades,
        leave_year=2020,
        full_book_mean_expectancy=Decimal("5"),  # half=2.5; leave mean=10 > 2.5
        fold_years=(2021, 2022, 2023),
        slippage_bps=Decimal("0"),
        tax_rate=Decimal("0"),
        spy_opens=spy,
    )
    assert result.residual_hope == "die"
    assert result.spy_excess_ok is False
    assert result.mean_spy_excess is not None
    assert result.mean_spy_excess <= 0


def test_k2_survives_when_all_legs_clear() -> None:
    from invest.application.phase2_report import evaluate_k2_residual_hope

    # Stock +20 each year; SPY flat → excess positive; full mean small so half-mean ok
    trades = [
        _t("W", date(2020, 1, 2), date(2020, 3, 1), "100", "101"),
        _t("A", date(2021, 1, 2), date(2021, 3, 1), "100", "120"),
        _t("B", date(2022, 1, 2), date(2022, 3, 1), "100", "120"),
        _t("C", date(2023, 1, 2), date(2023, 3, 1), "100", "120"),
    ]
    spy = {
        d: Decimal("100")
        for d in (
            date(2020, 1, 2),
            date(2020, 3, 1),
            date(2021, 1, 2),
            date(2021, 3, 1),
            date(2022, 1, 2),
            date(2022, 3, 1),
            date(2023, 1, 2),
            date(2023, 3, 1),
        )
    }
    result = evaluate_k2_residual_hope(
        trades,
        leave_year=2020,
        full_book_mean_expectancy=Decimal("5"),
        fold_years=(2021, 2022, 2023),
        slippage_bps=Decimal("0"),
        tax_rate=Decimal("0"),
        spy_opens=spy,
    )
    assert result.residual_hope == "survive"
    assert result.leave_year_mean_positive is True
    assert result.half_mean_ok is True
    assert result.majority_folds_positive is True
    assert result.spy_excess_ok is True
    assert result.mean_spy_excess is not None and result.mean_spy_excess > 0


def test_build_autopsy_report_never_emits_promotion_go() -> None:
    from invest.application.phase2_report import build_phase2_concentration_autopsy_report

    trades = [
        _t("W", date(2020, 1, 2), date(2020, 3, 1), "100", "200"),
        _t("A", date(2021, 1, 2), date(2021, 3, 1), "100", "120"),
        _t("B", date(2022, 1, 2), date(2022, 3, 1), "100", "120"),
        _t("C", date(2023, 1, 2), date(2023, 3, 1), "100", "120"),
    ]
    spy = {
        d: Decimal("100")
        for d in (
            date(2020, 1, 2),
            date(2020, 3, 1),
            date(2021, 1, 2),
            date(2021, 3, 1),
            date(2022, 1, 2),
            date(2022, 3, 1),
            date(2023, 1, 2),
            date(2023, 3, 1),
        )
    }
    report = build_phase2_concentration_autopsy_report(
        trades=trades,
        leave_year=2020,
        full_book_mean_expectancy=Decimal("5"),
        fold_years=(2021, 2022, 2023),
        spy_opens=spy,
        provenance={"source": "test"},
        slippage_bps=Decimal("0"),
        tax_rate=Decimal("0"),
    )
    assert report["experiment"] == "phase2-concentration-autopsy"
    assert report["residual_hope"] in ("die", "survive")
    assert report["residual_hope"] != "go"
    assert "promotion" not in report.get("decision", "").lower()
    assert "leave_year_book" in report
    assert "s2_trade_window_spy" in report
    assert report["provenance"]["source"] == "test"
    assert report["k2"]["full_book_mean_expectancy"] == "5"
    # FC included in S2 set; segregated tables present
    assert "fc_segregated" in report
