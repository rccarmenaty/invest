import argparse
import hashlib
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from time import monotonic
from typing import Callable, Sequence

from dotenv import load_dotenv
from pydantic import ValidationError

from invest.adapters.backtest_context_json import BacktestContextJsonReader
from invest.adapters.fixtures_json import (
    FixtureValidationError,
    JsonFixtureReader,
    _UniversePayload,
)
from invest.adapters.alpaca_market_data import (
    AlpacaMarketDataReader,
    MarketDataFetchError,
    SnapshotWriter,
)
from invest.adapters.alpaca_broker import AlpacaBroker, BrokerFetchError
from invest.adapters.journal_memory import MemoryJournal
from invest.application.backtest_run import (
    BacktestRun,
    BacktestProgress,
    POINT_IN_TIME_CONTEXT_VALIDATED,
    ReplayWindowInvalidError,
)
from invest.application.execute_run import ExecuteRun
from invest.application.scan_run import ScanRun
from invest.contracts.events import FailedScan
from invest.domain.backtest_metrics import (
    DEFAULT_SLIPPAGE_BPS,
    DEFAULT_TAX_RATE,
    compute_metrics,
    compute_segment_metrics,
)
from invest.domain.exit_policy import (
    KIND_ATR_3_HIGH_WATER,
    KIND_TEN_DAY_LOW,
    resolve_exit_policy,
)
from invest.domain.rejection import RejectionReason, UnsupportedInputError
from invest.domain.scanner import MomentumScanner
from invest.domain.momentum_selection_scanner import MomentumSelectionScanner
from invest.domain.market_context import MarketContextError
from invest.domain.models import Universe

load_dotenv()

RULE_VERSION = "momentum-v1"
BACKTEST_STRATEGIES = ("benchmark", "core")
BACKTEST_SOURCES = ("fixture", "alpaca", "sharadar")
BACKTEST_EXIT_POLICIES = (KIND_TEN_DAY_LOW, KIND_ATR_3_HIGH_WATER)

DAY0_DISCLAIMER = (
    "DAY-0 MECHANICS ONLY: measures current day-0 paper-trading entry mechanics, "
    "NOT SPEC §2.4 confirmed-entry edge."
)
SURVIVORSHIP_DISCLAIMER = (
    "SURVIVORSHIP-BIASED UNIVERSE: fixed historical screen, NOT point-in-time index "
    "membership; results are optimistically biased."
)
COST_MODEL_DISCLAIMER = (
    "COST MODEL IS AN APPROXIMATION: fixed-bps slippage + zero commission + flat tax "
    "haircut, not precision accounting."
)
PORTFOLIO_GATES_DISCLAIMER = "PORTFOLIO GATES SIMULATED: not broker or account enforcement."
STATIC_UNIVERSE_OOS_DISCLAIMER = "OOS USES STATIC UNIVERSE: survivorship bias remains."
EXECUTION_REALISM_DISCLAIMER = "BROKER EXECUTION REALISM IS OUT OF SCOPE."
POINT_IN_TIME_CONTEXT_DISCLAIMER = (
    "POINT-IN-TIME CONTEXT VALIDATED: externally prepared date/symbol coverage was "
    "supplied for every replay day."
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="invest-scan")
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--bars", type=Path, required=True)
    parser.add_argument("--format", choices=("json",), default="json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        inputs = JsonFixtureReader().load(args.universe, args.bars)
        events = ScanRun(MomentumScanner(), MemoryJournal(), RULE_VERSION).execute(inputs)
        print(json.dumps([event.model_dump(mode="json") for event in events], sort_keys=True))
        return 0
    except (FixtureValidationError, UnsupportedInputError) as error:
        print(json.dumps(_failed(error.reason).model_dump(mode="json"), sort_keys=True))
        return 2


def _fetch_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="invest-fetch")
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--feed", choices=("sip", "iex"), default="sip")
    parser.add_argument("--out", type=Path, default=Path("fixtures/snapshots"))
    return parser


def fetch_main(argv: Sequence[str] | None = None) -> int:
    args = _fetch_parser().parse_args(argv)
    try:
        try:
            payload = _UniversePayload.model_validate_json(
                args.universe.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, ValidationError):
            raise MarketDataFetchError("fixture-invalid") from None
        universe = Universe(
            fixture_version=payload.fixture_version,
            symbols=tuple(payload.symbols),
        )
        inputs = AlpacaMarketDataReader(feed=args.feed).fetch(universe, args.as_of)
        SnapshotWriter(feed=args.feed).write(inputs, args.as_of, args.out)
        return 0
    except MarketDataFetchError as error:
        failure = {"reason": error.reason}
        if str(error) != error.reason:
            failure["message"] = str(error)
        print(json.dumps(failure, sort_keys=True))
        return 2


def _execute_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="invest-execute")
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--bars", type=Path, required=True)
    parser.add_argument("--format", choices=("json",), default="json")
    parser.add_argument("--execute", action="store_true")
    return parser


def execute_main(argv: Sequence[str] | None = None) -> int:
    args = _execute_parser().parse_args(argv)
    try:
        inputs = JsonFixtureReader().load(args.universe, args.bars)
        broker = AlpacaBroker()
        run = ExecuteRun(MomentumScanner(), MemoryJournal(), broker, RULE_VERSION)
        events = run.execute(inputs, execute=args.execute)
        print(json.dumps([event.model_dump(mode="json") for event in events], sort_keys=True))
        return 2 if run.failed_reason is not None else 0
    except (FixtureValidationError, UnsupportedInputError) as error:
        print(json.dumps({"reason": error.reason.value}, sort_keys=True))
        return 2
    except BrokerFetchError as error:
        print(json.dumps({"reason": error.reason}, sort_keys=True))
        return 2


def _backtest_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="invest-backtest")
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--bars", type=Path)
    parser.add_argument("--market-context", type=Path)
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--format", choices=("json",), default="json")
    parser.add_argument("--slippage-bps", type=Decimal, default=DEFAULT_SLIPPAGE_BPS)
    parser.add_argument("--tax-rate", type=Decimal, default=DEFAULT_TAX_RATE)
    parser.add_argument("--split-date")
    parser.add_argument("--strategy", default="benchmark")
    parser.add_argument("--source")
    parser.add_argument(
        "--progress",
        action="store_true",
        help="emit structured backtest progress records to stderr",
    )
    parser.add_argument(
        "--exit-policy",
        dest="exit_policy",
        choices=BACKTEST_EXIT_POLICIES,
        default=KIND_TEN_DAY_LOW,
    )
    return parser


def backtest_main(argv: Sequence[str] | None = None) -> int:
    """`invest-backtest`: day-by-day replay harness. Never constructs/calls BrokerPort."""
    args = _backtest_parser().parse_args(argv)
    source = (
        ("fixture" if args.bars is not None else "alpaca") if args.source is None else args.source
    )
    if source not in BACKTEST_SOURCES:
        return _backtest_source_error()
    try:
        if args.market_context is None:
            return _backtest_context_error("market-context-missing")
        market_context = BacktestContextJsonReader().load(args.market_context)
        if not _valid_cost_model(args.slippage_bps, args.tax_rate):
            return _backtest_cost_model_error()
        if args.strategy not in BACKTEST_STRATEGIES:
            return _backtest_strategy_error()
        scanner = MomentumSelectionScanner() if args.strategy == "core" else MomentumScanner()
        if source == "fixture":
            if args.bars is None:
                raise MarketDataFetchError("fixture-invalid")
            inputs = JsonFixtureReader().load(
                args.universe,
                args.bars,
                start=args.start,
                end=args.end,
                warmup_bars=max(0, scanner.replay_history_bars - 1),
            )
        else:
            if args.start is None or args.end is None:
                raise MarketDataFetchError(
                    "fixture-invalid", "either --bars or --start/--end is required"
                )
            span = market_context.generation_span
            if args.start != span.start or args.end != span.end:
                raise ReplayWindowInvalidError(
                    "live range must exactly match the declared generation span"
                )
            try:
                payload = _UniversePayload.model_validate_json(
                    args.universe.read_text(encoding="utf-8")
                )
            except (OSError, UnicodeError, ValidationError):
                raise MarketDataFetchError("fixture-invalid") from None
            universe = Universe(
                fixture_version=payload.fixture_version, symbols=tuple(payload.symbols)
            )
            if source == "sharadar":
                from invest.adapters.sharadar_market_data import SharadarMarketDataReader

                inputs = SharadarMarketDataReader().fetch_range(universe, args.start, args.end)
            else:
                inputs = AlpacaMarketDataReader().fetch_range(universe, args.start, args.end)
            missing = sorted(set(inputs.universe.symbols) - {bar.symbol for bar in inputs.bars})
            if missing:
                # Alpaca can silently omit a symbol (delisted ticker, feed gap, partial
                # upstream omission -- not an HTTP error): fetch_range then returns
                # FixtureInputs with zero bars for it, and the scanner would just reject
                # it as INSUFFICIENT_HISTORY, vanishing from decisions with no trace. Fail
                # closed instead, mirroring SnapshotWriter's identical guard in
                # alpaca_market_data.py.
                raise MarketDataFetchError("symbol-missing-at-fetch", ",".join(missing))

        if args.split_date is None:
            return _backtest_split_error()
        try:
            split_date = date.fromisoformat(args.split_date)
        except ValueError:
            return _backtest_split_error()
        exit_policy = resolve_exit_policy(args.exit_policy)
        result = BacktestRun(
            market_context=market_context,
            scanner=scanner,
            slippage_bps=args.slippage_bps,
            tax_rate=args.tax_rate,
            exit_policy=exit_policy,
            progress_callback=_backtest_progress_callback() if args.progress else None,
        ).replay(inputs, split_date=split_date, start=args.start)
        metrics = compute_metrics(list(result.trades), args.slippage_bps, args.tax_rate)
        segments = compute_segment_metrics(
            list(result.trades), split_date, args.slippage_bps, args.tax_rate
        )
        report = _backtest_report(result, metrics, segments)
        print(json.dumps(report, sort_keys=True))
        return 0
    except (FixtureValidationError, UnsupportedInputError) as error:
        print(json.dumps({"reason": error.reason.value}, sort_keys=True))
        return 2
    except MarketDataFetchError as error:
        failure = {"reason": error.reason}
        if str(error) != error.reason:
            failure["message"] = str(error)
        print(json.dumps(failure, sort_keys=True))
        return 2
    except MarketContextError as error:
        return _backtest_context_error(error.reason)
    except ReplayWindowInvalidError:
        return _backtest_replay_window_error()


def _backtest_split_error() -> int:
    print(json.dumps({"reason": "split-date-invalid"}, sort_keys=True))
    return 2


def _backtest_replay_window_error() -> int:
    print(json.dumps({"reason": "replay-window-invalid"}, sort_keys=True))
    return 2


def _backtest_cost_model_error() -> int:
    print(json.dumps({"reason": "cost-model-invalid"}, sort_keys=True))
    return 2


def _backtest_strategy_error() -> int:
    print(json.dumps({"reason": "strategy-invalid"}, sort_keys=True))
    return 2


def _backtest_source_error() -> int:
    print(json.dumps({"reason": "source-invalid"}, sort_keys=True))
    return 2


def _backtest_context_error(reason: str) -> int:
    print(json.dumps({"reason": reason}, sort_keys=True))
    return 2


def _valid_cost_model(slippage_bps: Decimal, tax_rate: Decimal) -> bool:
    return (
        slippage_bps.is_finite()
        and tax_rate.is_finite()
        and Decimal("0") <= slippage_bps <= Decimal("10000")
        and Decimal("0") <= tax_rate <= Decimal("1")
    )


def _backtest_progress_callback() -> Callable[[BacktestProgress], None]:
    started_at = monotonic()

    def report(progress: BacktestProgress) -> None:
        elapsed = max(0.0, monotonic() - started_at)
        if progress.processed_replay_days == 0:
            eta = 0.0
        else:
            remaining_days = progress.total_replay_days - progress.processed_replay_days
            eta = elapsed * remaining_days / progress.processed_replay_days
        payload = {
            "event": "backtest-progress",
            "phase": progress.phase,
            "processed_replay_days": progress.processed_replay_days,
            "total_replay_days": progress.total_replay_days,
            "accepted_decisions": progress.accepted_decisions,
            "percent": progress.percent,
            "ingested_bars": progress.ingested_bars,
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": round(eta, 1),
        }
        print(json.dumps(payload, sort_keys=True), file=sys.stderr)

    return report


def _backtest_report(result, metrics, segments) -> dict:
    disclaimers = {
        "day0": DAY0_DISCLAIMER,
        "cost_model": COST_MODEL_DISCLAIMER,
        "portfolio_gates": PORTFOLIO_GATES_DISCLAIMER,
        "execution_realism": EXECUTION_REALISM_DISCLAIMER,
    }
    if POINT_IN_TIME_CONTEXT_VALIDATED in result.warnings:
        disclaimers["point_in_time_market_context"] = POINT_IN_TIME_CONTEXT_DISCLAIMER
    else:
        disclaimers["survivorship"] = SURVIVORSHIP_DISCLAIMER
        disclaimers["static_universe_oos"] = STATIC_UNIVERSE_OOS_DISCLAIMER

    return {
        "hit_rate": str(metrics.hit_rate),
        "expectancy": str(metrics.expectancy),
        "max_drawdown": str(metrics.max_drawdown),
        "trade_count": metrics.trade_count,
        "net_pnl": str(metrics.net_pnl),
        "trades": [
            {
                "symbol": trade.symbol,
                "entry_date": trade.entry_date.isoformat(),
                "exit_date": trade.exit_date.isoformat(),
                "entry_price": str(trade.entry_price),
                "exit_price": str(trade.exit_price),
                "qty": trade.qty,
                "exit_reason": trade.exit_reason,
            }
            for trade in result.trades
        ],
        "skipped_entries": [
            {
                "symbol": entry.symbol,
                "decision_date": entry.decision_date.isoformat(),
                "entry_date": entry.entry_date.isoformat(),
                "reason": entry.reason,
            }
            for entry in result.skipped_entries
        ],
        "context_outcomes": [
            {
                "type": outcome.outcome_type.value,
                "reason": outcome.reason.value,
                "symbol": outcome.symbol,
                "date": outcome.date.isoformat(),
            }
            for outcome in result.context_outcomes
        ],
        "portfolio": {
            "starting_capital": str(result.portfolio.starting_capital),
            "cash": str(result.portfolio.cash),
            "equity": str(result.portfolio.equity),
            "open_position_count": result.portfolio.open_position_count,
            "deployed_capital": str(result.portfolio.deployed_capital),
            "closed_trade_count": result.portfolio.closed_trade_count,
        },
        "gates": {"label": result.gates.label, "counts": dict(result.gates.counts)},
        "equity": {
            "starting_equity": str(result.equity_summary.starting_equity),
            "ending_equity": str(result.equity_summary.ending_equity),
            "min_equity": str(result.equity_summary.min_equity),
            "max_equity": str(result.equity_summary.max_equity),
            "max_drawdown": str(result.equity_summary.max_drawdown),
            "total_return": str(result.equity_summary.total_return),
            "trading_day_count": result.equity_summary.trading_day_count,
        },
        "segments": {
            name: {
                "hit_rate": str(segment.hit_rate),
                "expectancy": str(segment.expectancy),
                "max_drawdown": str(segment.max_drawdown),
                "trade_count": segment.trade_count,
                "net_pnl": str(segment.net_pnl),
            }
            for name, segment in segments.items()
        },
        "warnings": list(result.warnings),
        "disclaimers": disclaimers,
        "exit_policy": dict(result.exit_policy),
    }


def _failed(reason: RejectionReason) -> FailedScan:
    event_id = hashlib.sha256(f"1|scan.failed.v1|{reason.value}".encode()).hexdigest()
    return FailedScan(
        schema_version="1",
        event_type="scan.failed.v1",
        event_id=event_id,
        symbol=None,
        decision_date=date.min,
        fixture_version="unknown",
        rule_version=RULE_VERSION,
        decision="failed",
        reason=reason.value,
    )


if __name__ == "__main__":
    raise SystemExit(main())
