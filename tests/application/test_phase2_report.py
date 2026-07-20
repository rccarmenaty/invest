"""Phase 2 research report: after-cost books, folds, FC segregation, go/no-go."""

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


def test_decimal_median_stays_decimal_for_even_trade_counts() -> None:
    """Even n must not route through statistics.median (float average)."""
    from invest.application.phase2_report import summarize_book

    trades = [
        _t("A", date(2021, 1, 4), date(2021, 4, 1), "100", "110"),
        _t("B", date(2021, 1, 5), date(2021, 4, 2), "100", "90"),
    ]
    book = summarize_book(trades, slippage_bps=Decimal("0"), tax_rate=Decimal("0"))
    assert isinstance(book.median_expectancy, Decimal)
    assert book.median_expectancy == Decimal("0")  # (+10 + -10) / 2


def test_summarize_book_reports_mean_and_median_pre_tax_after_cost_expectancy() -> None:
    """Primary metric: 5 bps/side, tax=0 — mean and median of per-trade nets."""
    from invest.application.phase2_report import summarize_book

    trades = [
        _t("A", date(2021, 1, 4), date(2021, 4, 1), "100", "110"),  # win
        _t("B", date(2021, 1, 5), date(2021, 4, 2), "100", "90"),  # loss
        _t("C", date(2022, 1, 4), date(2022, 4, 1), "100", "105"),  # small win
    ]
    book = summarize_book(
        trades, slippage_bps=Decimal("5"), tax_rate=Decimal("0")
    )

    assert book.trade_count == 3
    # Hand-check first trade nets with 5 bps both sides, no tax.
    from invest.domain.backtest_metrics import apply_costs

    nets = [apply_costs(t, Decimal("5"), Decimal("0")) for t in trades]
    assert book.net_pnl == sum(nets, Decimal("0"))
    assert book.mean_expectancy == book.net_pnl / 3
    ordered = sorted(nets)
    assert book.median_expectancy == ordered[1]
    assert book.hit_rate == Decimal("2") / Decimal("3")


def test_fc_segregation_excludes_forced_close_trades_from_alpha_book() -> None:
    from invest.application.phase2_report import (
        FC_EXIT_REASON,
        fc_trades,
        non_fc_trades,
        summarize_book,
    )

    trades = [
        _t("A", date(2021, 1, 4), date(2021, 4, 1), "100", "120", reason="fixed-horizon"),
        _t("B", date(2021, 1, 5), date(2021, 2, 1), "100", "150", reason=FC_EXIT_REASON),
        _t("C", date(2021, 1, 6), date(2021, 4, 2), "100", "80", reason="fixed-horizon"),
    ]
    alpha = non_fc_trades(trades)
    forced = fc_trades(trades)
    assert len(alpha) == 2
    assert len(forced) == 1
    assert forced[0].symbol == "B"
    alpha_book = summarize_book(alpha, slippage_bps=Decimal("0"), tax_rate=Decimal("0"))
    full_book = summarize_book(trades, slippage_bps=Decimal("0"), tax_rate=Decimal("0"))
    # FC winner inflates full book; alpha book must not include it.
    assert full_book.net_pnl > alpha_book.net_pnl
    assert alpha_book.trade_count == 2


def test_by_entry_year_and_walk_forward_fold_summaries() -> None:
    from invest.application.phase2_report import (
        by_entry_year,
        summarize_book,
        walk_forward_folds,
    )

    trades = [
        _t("A", date(2020, 6, 1), date(2020, 8, 1), "100", "110"),
        _t("B", date(2021, 6, 1), date(2021, 8, 1), "100", "90"),
        _t("C", date(2021, 7, 1), date(2021, 9, 1), "100", "95"),
        _t("D", date(2022, 6, 1), date(2022, 8, 1), "100", "108"),
    ]
    years = by_entry_year(trades)
    assert set(years) == {2020, 2021, 2022}
    assert len(years[2021]) == 2

    folds = walk_forward_folds(
        trades,
        years=(2020, 2021, 2022, 2023),
        slippage_bps=Decimal("0"),
        tax_rate=Decimal("0"),
    )
    assert "2020" in folds and "2021" in folds and "2022" in folds
    assert folds["2023"].trade_count == 0
    assert folds["2020"].mean_expectancy > 0
    assert folds["2021"].mean_expectancy < 0
    # Fold book matches year partition
    assert folds["2021"].trade_count == 2
    assert folds["2021"].net_pnl == summarize_book(
        years[2021], slippage_bps=Decimal("0"), tax_rate=Decimal("0")
    ).net_pnl


def test_year_profit_share_flags_concentration_above_25pct() -> None:
    from invest.application.phase2_report import max_year_profit_share

    # Two years: 2020 makes +80, 2021 makes +20 → 2020 is 80% of profit
    trades = [
        _t("A", date(2020, 1, 2), date(2020, 3, 1), "100", "180"),  # +80
        _t("B", date(2021, 1, 2), date(2021, 3, 1), "100", "120"),  # +20
    ]
    share, peak_year = max_year_profit_share(
        trades, slippage_bps=Decimal("0"), tax_rate=Decimal("0")
    )
    assert peak_year == 2020
    assert share == Decimal("0.8")


def test_evaluate_phase2_gates_go_when_majority_folds_positive_fc_ok_year_ok() -> None:
    from invest.application.phase2_report import evaluate_phase2_gates

    # 3 years positive, 1 year slightly negative → majority positive
    # No FC trades; years reasonably balanced
    trades = [
        _t("A", date(2020, 1, 2), date(2020, 3, 1), "100", "110"),
        _t("B", date(2021, 1, 2), date(2021, 3, 1), "100", "112"),
        _t("C", date(2022, 1, 2), date(2022, 3, 1), "100", "111"),
        _t("D", date(2023, 1, 2), date(2023, 3, 1), "100", "99"),  # small loss year
    ]
    result = evaluate_phase2_gates(
        trades,
        fold_years=(2020, 2021, 2022, 2023),
        slippage_bps=Decimal("0"),
        tax_rate=Decimal("0"),
        max_year_share=Decimal("0.25"),
    )
    # With 3/4 positive years, majority holds; year share may fail if one year dominates.
    # Force balanced profits: recreate with equal wins.
    trades = [
        _t("A", date(2020, 1, 2), date(2020, 3, 1), "100", "110"),
        _t("B", date(2021, 1, 2), date(2021, 3, 1), "100", "110"),
        _t("C", date(2022, 1, 2), date(2022, 3, 1), "100", "110"),
        _t("D", date(2023, 1, 2), date(2023, 3, 1), "100", "110"),
    ]
    result = evaluate_phase2_gates(
        trades,
        fold_years=(2020, 2021, 2022, 2023),
        slippage_bps=Decimal("0"),
        tax_rate=Decimal("0"),
        max_year_share=Decimal("0.25"),
    )
    assert result.passed is True
    assert result.decision == "GO"
    assert result.majority_folds_positive is True
    assert result.fc_segregated_holds is True
    assert result.year_concentration_ok is True


def test_evaluate_phase2_gates_nogo_when_majority_folds_non_positive() -> None:
    from invest.application.phase2_report import evaluate_phase2_gates

    trades = [
        _t("A", date(2020, 1, 2), date(2020, 3, 1), "100", "90"),
        _t("B", date(2021, 1, 2), date(2021, 3, 1), "100", "88"),
        _t("C", date(2022, 1, 2), date(2022, 3, 1), "100", "110"),
    ]
    result = evaluate_phase2_gates(
        trades,
        fold_years=(2020, 2021, 2022),
        slippage_bps=Decimal("0"),
        tax_rate=Decimal("0"),
    )
    assert result.passed is False
    assert result.decision == "NO-GO"
    assert result.majority_folds_positive is False


def test_evaluate_phase2_gates_nogo_when_edge_depends_on_forced_closes() -> None:
    from invest.application.phase2_report import FC_EXIT_REASON, evaluate_phase2_gates

    # Full book: wins via FC; non-FC folds all lose → FC segregation fails
    trades = [
        _t("A", date(2020, 1, 2), date(2020, 2, 1), "100", "150", reason=FC_EXIT_REASON),
        _t("B", date(2021, 1, 2), date(2021, 2, 1), "100", "150", reason=FC_EXIT_REASON),
        _t("C", date(2022, 1, 2), date(2022, 2, 1), "100", "150", reason=FC_EXIT_REASON),
        _t("D", date(2020, 3, 1), date(2020, 5, 1), "100", "90"),
        _t("E", date(2021, 3, 1), date(2021, 5, 1), "100", "90"),
        _t("F", date(2022, 3, 1), date(2022, 5, 1), "100", "90"),
    ]
    result = evaluate_phase2_gates(
        trades,
        fold_years=(2020, 2021, 2022),
        slippage_bps=Decimal("0"),
        tax_rate=Decimal("0"),
    )
    assert result.passed is False
    assert result.fc_segregated_holds is False
    assert result.decision == "NO-GO"


def test_build_phase2_report_includes_required_sections_and_provenance() -> None:
    from invest.application.phase2_report import build_phase2_report

    trades = [
        _t("A", date(2020, 1, 2), date(2020, 3, 1), "100", "110"),
        _t("B", date(2021, 1, 2), date(2021, 3, 1), "100", "110"),
    ]
    report = build_phase2_report(
        trades=trades,
        provenance={
            "scanner": "momentum-naive-§2.5",
            "strategy": "benchmark",
            "exit_policy": {"kind": "fixed-horizon", "horizon_sessions": 60},
            "admission": {
                "kind": "seeded-random",
                "max_concurrent_positions": 20,
                "seed": 42,
            },
            "costs": {"slippage_bps": "5", "tax_rate": "0.15"},
            "fixture_span": {"start": "2019-01-02", "end": "2025-12-31"},
        },
        fold_years=(2020, 2021),
    )
    assert report["experiment"] == "phase2-fixed-horizon-structure"
    assert "after_cost_pre_tax" in report
    assert "mean_expectancy" in report["after_cost_pre_tax"]
    assert "median_expectancy" in report["after_cost_pre_tax"]
    assert "walk_forward_folds" in report
    assert "by_year" in report
    assert "fc_segregated" in report
    assert "non_fc" in report["fc_segregated"]
    assert "go_no_go" in report
    assert report["provenance"]["admission"]["seed"] == 42
    assert report["primary_metric"] == "pre-tax after 5 bps/side"
    assert "tax_secondary" in report
