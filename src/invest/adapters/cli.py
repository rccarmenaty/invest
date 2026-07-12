import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Sequence

from invest.adapters.fixtures_json import FixtureValidationError, JsonFixtureReader
from invest.adapters.alpaca_market_data import (
    AlpacaMarketDataReader,
    MarketDataFetchError,
    SnapshotWriter,
)
from invest.adapters.journal_memory import MemoryJournal
from invest.application.scan_run import ScanRun
from invest.contracts.events import FailedScan
from invest.domain.rejection import RejectionReason, UnsupportedInputError
from invest.domain.scanner import MomentumScanner
from invest.domain.models import Universe

RULE_VERSION = "momentum-v1"


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
        payload = json.loads(args.universe.read_text(encoding="utf-8"))
        universe = Universe(
            fixture_version=str(payload["fixture_version"]),
            symbols=tuple(str(symbol) for symbol in payload["symbols"]),
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


def _failed(reason: RejectionReason) -> FailedScan:
    event_id = hashlib.sha256(f"1|scan.failed.v1|{reason.value}".encode()).hexdigest()
    return FailedScan(schema_version="1", event_type="scan.failed.v1", event_id=event_id, symbol=None, decision_date=date.min, fixture_version="unknown", rule_version=RULE_VERSION, decision="failed", reason=reason.value)


if __name__ == "__main__":
    raise SystemExit(main())
