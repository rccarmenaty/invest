"""Standalone backtest-only market-context generator entrypoint.

Orchestrates source → GenerateMarketContext → JSON writer. Never invokes
replay, broker, execution, scanner, live, or paper paths.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Sequence

import httpx
from dotenv import load_dotenv

from invest.adapters.alpaca_market_data import MarketDataFetchError
from invest.adapters.backtest_context_json import (
    BacktestContextJsonWriter,
    ContextOutputExistsError,
    ContextStorageFailureError,
)
from invest.adapters.sharadar_context_source import SharadarContextSource
from invest.application.generate_market_context import (
    GenerateMarketContext,
    ReferenceDataIncompleteError,
)
from invest.domain.liquidity_screen import ScreenConfig
from invest.domain.market_context import MarketContextError

load_dotenv()


class InvalidArgumentsError(ValueError):
    def __init__(self, message: str = "invalid arguments") -> None:
        self.reason = "invalid-arguments"
        super().__init__(message)


def _parser() -> argparse.ArgumentParser:
    defaults = ScreenConfig.core_defaults()
    parser = argparse.ArgumentParser(prog="invest-generate-context")
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--price-floor", type=Decimal, default=defaults.price_floor)
    parser.add_argument(
        "--dollar-volume-floor", type=Decimal, default=defaults.dollar_volume_floor
    )
    parser.add_argument(
        "--dollar-volume-window", type=int, default=defaults.dollar_volume_window
    )
    parser.add_argument(
        "--min-observed-bars", type=int, default=defaults.min_observed_bars
    )
    return parser


def _fail(reason: str) -> int:
    print(json.dumps({"reason": reason}, sort_keys=True))
    return 2


def _validate(args: argparse.Namespace) -> tuple[ScreenConfig, Path]:
    if args.end < args.start:
        raise InvalidArgumentsError("end precedes start")
    try:
        config = ScreenConfig(
            price_floor=args.price_floor,
            dollar_volume_floor=args.dollar_volume_floor,
            dollar_volume_window=args.dollar_volume_window,
            min_observed_bars=args.min_observed_bars,
        )
    except (ValueError, TypeError, InvalidOperation) as error:
        raise InvalidArgumentsError(str(error)) from error

    out = Path(args.out)
    if out.exists():
        raise ContextOutputExistsError(out)
    parent = out.parent if out.parent.as_posix() not in {"", "."} else Path.cwd()
    if not parent.is_dir() or not os.access(parent, os.W_OK):
        raise InvalidArgumentsError(f"output parent not writable: {parent}")
    return config, out


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as error:
        code = error.code if isinstance(error.code, int) else 2
        return 0 if code == 0 else _fail("invalid-arguments")

    try:
        config, out = _validate(args)
        with httpx.Client() as client:
            inputs = SharadarContextSource(client=client).load(args.start, args.end, config)
            context = GenerateMarketContext().run(inputs, config)
            BacktestContextJsonWriter().write(context, out)
        return 0
    except InvalidArgumentsError:
        return _fail("invalid-arguments")
    except ContextOutputExistsError:
        return _fail("output-exists")
    except ContextStorageFailureError:
        return _fail("storage-failure")
    except ReferenceDataIncompleteError as error:
        return _fail(error.reason)
    except MarketContextError as error:
        return _fail(error.reason)
    except MarketDataFetchError as error:
        return _fail(error.reason)
    except (ValueError, TypeError, InvalidOperation, OSError):
        return _fail("invalid-arguments")


if __name__ == "__main__":
    sys.exit(main())
