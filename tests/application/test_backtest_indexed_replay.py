from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from invest.adapters.backtest_context_json import BacktestContextJsonReader
from invest.adapters.fixtures_json import JsonFixtureReader
from invest.application.backtest_run import BacktestRun
from invest.domain.market_context import (
    CoverageWindow,
    EligibilityWindow,
    GenerationSpan,
    MarketContext,
    SymbolContext,
)
from invest.domain.models import DailyBar, FixtureInputs, Universe
from invest.domain.momentum_selection_scanner import MomentumSelectionScanner
from invest.domain.scanner import MomentumScanner


class _LegacyMomentumScanner(MomentumScanner):
    """No concrete capability declaration: exercises cumulative fallback."""


class _LegacyMomentumSelectionScanner(MomentumSelectionScanner):
    """No concrete capability declaration: exercises cumulative fallback."""


def _core_inputs(*, invalid: bool = False, zero_volume: bool = False) -> FixtureInputs:
    start = date(2025, 1, 1)
    bars = [
        DailyBar(
            "ACME",
            start + timedelta(days=offset),
            Decimal("100") + offset,
            Decimal("100.4") + offset,
            Decimal("99.6") + offset,
            Decimal("100") + offset,
            1000,
        )
        for offset in range(256)
    ]
    first = bars[0]
    if zero_volume:
        bars[0] = DailyBar(
            first.symbol,
            first.date,
            first.open,
            first.high,
            first.low,
            first.close,
            0,
        )
    if invalid:
        bars[0] = DailyBar(
            first.symbol,
            first.date,
            first.open,
            first.low,
            first.high,
            first.close,
            first.volume,
        )
    return FixtureInputs(Universe("v1", ("ACME",)), tuple(bars))


def _context(inputs: FixtureInputs) -> MarketContext:
    start = inputs.bars[0].date
    end = inputs.bars[-1].date
    return MarketContext(
        generation_span=GenerationSpan(start, end),
        by_symbol={
            "ACME": SymbolContext(
                coverage=(CoverageWindow(start, end),),
                eligibility=(EligibilityWindow(start, end, eligible=True),),
            )
        },
    )


@pytest.mark.parametrize(
    ("fixture", "indexed_scanner", "legacy_scanner"),
    [
        (Path("fixtures/backtest"), MomentumScanner, _LegacyMomentumScanner),
        (
            Path("fixtures/backtest-252"),
            MomentumSelectionScanner,
            _LegacyMomentumSelectionScanner,
        ),
    ],
)
def test_indexed_and_cumulative_replay_emit_exactly_equal_decisions(
    fixture, indexed_scanner, legacy_scanner
) -> None:
    inputs = JsonFixtureReader().load(fixture / "universe.json", fixture / "bars.json")
    market_context = BacktestContextJsonReader().load(fixture / "market-context.json")

    indexed = BacktestRun(
        market_context=market_context,
        scanner=indexed_scanner(),
    ).scan_decisions(inputs)
    cumulative = BacktestRun(
        market_context=market_context,
        scanner=legacy_scanner(),
    ).scan_decisions(inputs)

    assert indexed == cumulative


def test_core_indexed_replay_remembers_zero_volume_outside_rolling_history() -> None:
    inputs = _core_inputs(zero_volume=True)
    market_context = _context(inputs)

    indexed = BacktestRun(
        market_context=market_context,
        scanner=MomentumSelectionScanner(),
    ).scan_decisions(inputs)
    cumulative = BacktestRun(
        market_context=market_context,
        scanner=_LegacyMomentumSelectionScanner(),
    ).scan_decisions(inputs)

    assert indexed == cumulative


def test_core_indexed_replay_remembers_invalid_bar_outside_rolling_history() -> None:
    inputs = _core_inputs(invalid=True)
    market_context = _context(inputs)

    indexed = BacktestRun(
        market_context=market_context,
        scanner=MomentumSelectionScanner(),
    ).scan_decisions(inputs)
    cumulative = BacktestRun(
        market_context=market_context,
        scanner=_LegacyMomentumSelectionScanner(),
    ).scan_decisions(inputs)

    assert indexed == cumulative
