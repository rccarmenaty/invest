import argparse
import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

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
from invest.application.backtest_run import BacktestRun
from invest.application.execute_run import ExecuteRun
from invest.application.scan_run import ScanRun
from invest.contracts.events import FailedScan
from invest.domain.backtest_metrics import DEFAULT_SLIPPAGE_BPS, DEFAULT_TAX_RATE, compute_metrics
from invest.domain.rejection import RejectionReason, UnsupportedInputError
from invest.domain.scanner import MomentumScanner
from invest.domain.models import Universe

RULE_VERSION = "momentum-v1"

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
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--format", choices=("json",), default="json")
    parser.add_argument("--slippage-bps", type=Decimal, default=DEFAULT_SLIPPAGE_BPS)
    parser.add_argument("--tax-rate", type=Decimal, default=DEFAULT_TAX_RATE)
    return parser


def backtest_main(argv: Sequence[str] | None = None) -> int:
    """`invest-backtest`: day-by-day replay harness. Never constructs/calls BrokerPort."""
    args = _backtest_parser().parse_args(argv)
    try:
        if args.bars is not None:
            inputs = JsonFixtureReader().load(args.universe, args.bars)
        else:
            if args.start is None or args.end is None:
                raise MarketDataFetchError("fixture-invalid", "either --bars or --start/--end is required")
            try:
                payload = _UniversePayload.model_validate_json(
                    args.universe.read_text(encoding="utf-8")
                )
            except (OSError, UnicodeError, ValidationError):
                raise MarketDataFetchError("fixture-invalid") from None
            universe = Universe(fixture_version=payload.fixture_version, symbols=tuple(payload.symbols))
            inputs = AlpacaMarketDataReader().fetch_range(universe, args.start, args.end)

        trades = BacktestRun().replay(inputs)
        metrics = compute_metrics(trades, args.slippage_bps, args.tax_rate)
        report = _backtest_report(metrics, trades)
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


def _backtest_report(metrics, trades) -> dict:
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
            for trade in trades
        ],
        "disclaimers": {
            "day0": DAY0_DISCLAIMER,
            "survivorship": SURVIVORSHIP_DISCLAIMER,
            "cost_model": COST_MODEL_DISCLAIMER,
        },
    }


def _failed(reason: RejectionReason) -> FailedScan:
    event_id = hashlib.sha256(f"1|scan.failed.v1|{reason.value}".encode()).hexdigest()
    return FailedScan(schema_version="1", event_type="scan.failed.v1", event_id=event_id, symbol=None, decision_date=date.min, fixture_version="unknown", rule_version=RULE_VERSION, decision="failed", reason=reason.value)


if __name__ == "__main__":
    raise SystemExit(main())
