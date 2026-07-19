"""Uncapped-capital signal-edge experiment.

Same fixture, scanner, exit policy, and cost model as the baseline run, but:
- equity = 1e9 with RISK_PER_TRADE patched to 1e-6, so risk capital per trade
  stays 1,000 (identical sizing to the baseline's 1% of 100k) while the
  max-equity-deployed gate (25% of 1e9), kill-switch (-3% of 1e9), and buying
  power (cash 1e9) can never bind;
- MAX_CONCURRENT_POSITIONS patched effectively off.

Result: every scanner signal that passes context/sizing checks becomes a trade.
Measures the raw cross-sectional edge with statistical power (n ~ thousands).
"""

import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import invest.domain.sizing as sizing

sizing.RISK_PER_TRADE = Decimal("0.000001")
sizing.MAX_CONCURRENT_POSITIONS = 10**9

from invest.adapters.backtest_context_json import BacktestContextJsonReader
from invest.adapters.fixtures_json import JsonFixtureReader
from invest.application.backtest_run import BacktestRun
from invest.domain.backtest_metrics import (
    DEFAULT_SLIPPAGE_BPS,
    DEFAULT_TAX_RATE,
    compute_metrics,
    compute_segment_metrics,
)
from invest.domain.exit_policy import resolve_exit_policy
from invest.domain.momentum_selection_scanner import MomentumSelectionScanner

FIXTURES = Path("/Users/rcty/invest/fixtures/real-continuous")
SPLIT = date(2023, 1, 3)
EQUITY = Decimal("1000000000")

market_context = BacktestContextJsonReader().load(FIXTURES / "market-context.json")
inputs = JsonFixtureReader().load(FIXTURES / "bars" / "universe.json", FIXTURES / "bars" / "bars.json")

result = BacktestRun(
    market_context=market_context,
    scanner=MomentumSelectionScanner(),
    equity=EQUITY,
    exit_policy=resolve_exit_policy("ten-day-low"),
).replay(inputs, split_date=SPLIT)

trades = list(result.trades)
metrics = compute_metrics(trades, DEFAULT_SLIPPAGE_BPS, DEFAULT_TAX_RATE)
segments = compute_segment_metrics(trades, SPLIT, DEFAULT_SLIPPAGE_BPS, DEFAULT_TAX_RATE)

report = {
    "experiment": "uncapped-capital",
    "trade_count": metrics.trade_count,
    "net_pnl": str(metrics.net_pnl),
    "hit_rate": str(metrics.hit_rate),
    "expectancy": str(metrics.expectancy),
    "max_drawdown": str(metrics.max_drawdown),
    "segments": {
        name: {
            "trade_count": seg.trade_count,
            "net_pnl": str(seg.net_pnl),
            "hit_rate": str(seg.hit_rate),
            "expectancy": str(seg.expectancy),
        }
        for name, seg in segments.items()
    },
    "gates": dict(result.gates.counts),
    "skipped_entries": len(result.skipped_entries),
    "trades": [
        {
            "symbol": t.symbol,
            "entry_date": t.entry_date.isoformat(),
            "exit_date": t.exit_date.isoformat(),
            "entry_price": str(t.entry_price),
            "exit_price": str(t.exit_price),
            "qty": t.qty,
            "exit_reason": t.exit_reason,
        }
        for t in trades
    ],
}
json.dump(report, sys.stdout, sort_keys=True)
print()
