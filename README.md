# invest

Deterministic, signals-only momentum scanner using validated local fixtures. This
foundation does not connect to brokers or provision infrastructure.

**Start here if you are new to this repo**: `ROADMAP.md` (current state, in-flight
work, planned change sequence), then `SPEC.md` (system specification) and
`momentum_breakout_swing_trading_research_report.md` (evidence review behind the
strategy design).

## Local scan

```sh
uv run invest-scan \
  --universe fixtures/v1/universe.json \
  --bars fixtures/v1/bars.json \
  --format json
```

## Market context generation (backtest-only)

`invest-generate-context` writes `market-context-v1` JSON from Sharadar TICKERS,
SEP, and ACTIONS. It never runs replay, broker, scanner, live, or paper paths.

```sh
uv run invest-generate-context \
  --start 2024-01-02 --end 2024-12-31 --out path/to/market-context.json
```

Core defaults: `--price-floor 10`, `--dollar-volume-floor 10000000`,
`--dollar-volume-window 20`, `--min-observed-bars 252`. Success: exit 0, silent.
Failure: exit 2, one sorted JSON reason on stdout. Generate first, then replay
with `invest-backtest --market-context …`. Tests mock transport (no live calls).

## Verify

```sh
uv run --extra dev pytest
uv run --extra dev ruff check .
```

## Container

```sh
docker build -t invest-scan .
docker run --rm invest-scan
```

The image packages only the application and fixtures. Kubernetes, Helm, cluster
provisioning, and live-trading configuration are intentionally out of scope.
