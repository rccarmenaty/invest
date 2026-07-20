"""Phase 2 continuous-fixture structure measurement + go/no-go.

Runs the composed Phase 2 config (#61): §2.5 naïve scanner + fixed-horizon
exit + slot-cap seeded random admission + 5 bps/side.

Outputs: fixtures/real-continuous/reports/phase2-structure.json

SEQUENTIAL ONLY on 16GB hosts — do not parallel with other multi-GB bar loads.

Primary metric: pre-tax after-cost expectancy (tax secondary).
Gates (PRD #58): majority WF folds after-cost exp>0; FC-segregated holds;
no single year >~25% of total profit. Ranking is not the accept path.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import date
from decimal import Decimal
from pathlib import Path

from invest.adapters.backtest_context_json import BacktestContextJsonReader
from invest.adapters.cli import (
    PHASE2_MAX_CONCURRENT_POSITIONS,
    SCANNER_BY_STRATEGY,
)
from invest.adapters.fixtures_json import JsonFixtureReader
from invest.application.backtest_run import BacktestProgress, BacktestRun, ReplayWindowInvalidError
from invest.application.phase2_report import (
    DEFAULT_SLIPPAGE_BPS,
    PRIMARY_TAX_RATE,
    SECONDARY_TAX_RATE,
    WALK_FORWARD_YEARS,
    build_phase2_report,
)
from invest.domain.exit_policy import KIND_FIXED_HORIZON, resolve_exit_policy
from invest.domain.market_context import MarketContextError, MarketContextIncompleteError
from invest.domain.scanner import MomentumScanner

FIXTURES = Path(__file__).resolve().parents[1]
REPORTS = Path(__file__).resolve().parent
OUT_PATH = REPORTS / "phase2-structure.json"
LOG_PATH = REPORTS / "phase2-run.log"

# Frozen Phase 2 research seed (provenance).
ADMISSION_SEED = 42
STRATEGY = "benchmark"
# Valid replay date inside continuous fixture (segments only; folds are annual).
SPLIT_DATE = date(2023, 1, 3)


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, file=sys.stderr, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _progress(progress: BacktestProgress) -> None:
    if progress.processed_replay_days % 50 == 0 or progress.processed_replay_days == progress.total_replay_days:
        log(
            f"replay {progress.phase} "
            f"{progress.processed_replay_days}/{progress.total_replay_days} "
            f"({progress.percent}%) accepted={progress.accepted_decisions}"
        )


def _fail_closed(reason: str, detail: str | None = None) -> dict:
    """No P&L claim when the continuous run cannot complete cleanly."""
    payload: dict = {
        "experiment": "phase2-fixed-horizon-structure",
        "status": "fail-closed",
        "reason": reason,
        "go_no_go": {
            "passed": False,
            "decision": "NO-GO",
            "reasons": [f"run fail-closed: {reason}; no P&L claim"],
        },
        "primary_metric": "pre-tax after 5 bps/side",
        "note": "Fail-closed: do not treat missing or partial numbers as edge evidence.",
    }
    if detail:
        payload["detail"] = detail
    return payload


def main() -> int:
    LOG_PATH.write_text("", encoding="utf-8")
    log("Phase 2 continuous structure run starting (sequential only)")
    try:
        log("loading market context")
        market_context = BacktestContextJsonReader().load(FIXTURES / "market-context.json")
        span = market_context.generation_span
        log(f"context span {span.start}..{span.end}")

        log("loading bars (slow; ~1.3GB fixture — keep other multi-GB loads off)")
        inputs = JsonFixtureReader().load(
            FIXTURES / "bars" / "universe.json",
            FIXTURES / "bars" / "bars.json",
        )
        log(f"bars loaded: {len(inputs.bars)}")

        exit_policy = resolve_exit_policy(KIND_FIXED_HORIZON)
        log(
            f"replay Phase 2: strategy={STRATEGY} exit={exit_policy.kind} "
            f"slots={PHASE2_MAX_CONCURRENT_POSITIONS} seed={ADMISSION_SEED} "
            f"slippage_bps={DEFAULT_SLIPPAGE_BPS}"
        )
        result = BacktestRun(
            market_context=market_context,
            scanner=MomentumScanner(),
            slippage_bps=DEFAULT_SLIPPAGE_BPS,
            tax_rate=SECONDARY_TAX_RATE,  # engine accounting; primary report uses tax=0
            exit_policy=exit_policy,
            max_concurrent_positions=PHASE2_MAX_CONCURRENT_POSITIONS,
            admission_seed=ADMISSION_SEED,
            progress_callback=_progress,
        ).replay(inputs, split_date=SPLIT_DATE)

        trades = list(result.trades)
        log(f"trades={len(trades)} skips={len(result.skipped_entries)}")

        provenance = {
            "scanner": SCANNER_BY_STRATEGY[STRATEGY],
            "strategy": STRATEGY,
            "exit_policy": dict(result.exit_policy),
            "admission": dict(result.admission),
            "costs": {
                "slippage_bps": str(DEFAULT_SLIPPAGE_BPS),
                "tax_rate_primary": str(PRIMARY_TAX_RATE),
                "tax_rate_secondary": str(SECONDARY_TAX_RATE),
            },
            "fixture_span": {
                "start": span.start.isoformat(),
                "end": span.end.isoformat(),
            },
            "split_date": SPLIT_DATE.isoformat(),
            "walk_forward_years": list(WALK_FORWARD_YEARS),
            "admission_seed": ADMISSION_SEED,
            "max_concurrent_positions": PHASE2_MAX_CONCURRENT_POSITIONS,
            "ranking_accept_path": False,
            "gates_telemetry": {
                "label": result.gates.label,
                "counts": dict(result.gates.counts),
            },
            "equity": {
                "starting_equity": str(result.equity_summary.starting_equity),
                "ending_equity": str(result.equity_summary.ending_equity),
                "max_drawdown": str(result.equity_summary.max_drawdown),
                "total_return": str(result.equity_summary.total_return),
            },
            "warnings": list(result.warnings),
        }

        report = build_phase2_report(
            trades=trades,
            provenance=provenance,
            fold_years=WALK_FORWARD_YEARS,
            slippage_bps=DEFAULT_SLIPPAGE_BPS,
            primary_tax_rate=PRIMARY_TAX_RATE,
            secondary_tax_rate=SECONDARY_TAX_RATE,
        )
        report["status"] = "complete"
        report["trade_count"] = len(trades)
        report["trades"] = [
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
        ]
        report["skipped_entry_count"] = len(result.skipped_entries)
        report["exit_reason_counts"] = _count_reasons(trades)

        OUT_PATH.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
        log(f"wrote {OUT_PATH}")

        go = report["go_no_go"]
        primary = report["after_cost_pre_tax"]
        summary = {
            "decision": go["decision"],
            "passed": go["passed"],
            "reasons": go["reasons"],
            "after_cost_pre_tax": primary,
            "fc_segregated_non_fc": report["fc_segregated"]["non_fc"],
            "positive_folds": f"{go['positive_fold_count']}/{go['evaluated_fold_count']}",
            "max_year_profit_share": go.get("max_year_profit_share"),
            "peak_profit_year": go.get("peak_profit_year"),
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        log(f"go/no-go: {go['decision']}")
        return 0 if go["passed"] else 1

    except (MarketContextError, MarketContextIncompleteError, ReplayWindowInvalidError) as error:
        reason = getattr(error, "reason", type(error).__name__)
        log(f"FAIL-CLOSED: {reason}: {error}")
        report = _fail_closed(str(reason), detail=str(error))
        report["provenance_attempted"] = {
            "strategy": STRATEGY,
            "exit_policy": KIND_FIXED_HORIZON,
            "max_concurrent_positions": PHASE2_MAX_CONCURRENT_POSITIONS,
            "admission_seed": ADMISSION_SEED,
            "slippage_bps": str(DEFAULT_SLIPPAGE_BPS),
            "rejection": "R4-stale-terminal-or-context-incomplete",
        }
        OUT_PATH.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
        print(json.dumps(report["go_no_go"], indent=2, sort_keys=True))
        return 2
    except Exception as error:  # noqa: BLE001 — research driver: publish fail-closed
        log(f"FAIL-CLOSED unexpected: {error}")
        log(traceback.format_exc())
        report = _fail_closed("unexpected-error", detail=str(error))
        OUT_PATH.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
        print(json.dumps(report["go_no_go"], indent=2, sort_keys=True))
        return 2


def _count_reasons(trades) -> dict[str, int]:
    counts: dict[str, int] = {}
    for t in trades:
        counts[t.exit_reason] = counts.get(t.exit_reason, 0) + 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    raise SystemExit(main())
