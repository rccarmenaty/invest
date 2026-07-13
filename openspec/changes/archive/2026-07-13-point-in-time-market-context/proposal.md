# Proposal: Point-in-Time Market Context

## Intent

Make backtest eligibility historically defensible without inventing provider capability. A validated file becomes authoritative for date-effective symbol eligibility and `corporate-action` / `earnings-context-missing` blocker windows; absent coverage is unsafe. Paper-first gates remain unchanged.

## Scope

### In Scope
- Add a backtest-only `MarketContext` seam and JSON adapter.
- Derive each replay day's eligible symbols; record visible blocked-entry skips and forced closes.
- Require valid `invest-backtest` context; fail once when absent, invalid, or incomplete.

### Out of Scope
- Live provider/vendor adapters and actual earnings-provider selection.
- Changes to `MomentumScanner`, Alpaca bars, portfolio accounting, broker paths, costs, or live gates.
- Reading or changing `.env` or root `universe.json`.

## Proposal Question Round

Automatic preflight assumes inclusive windows, fail-closed undeclared coverage, and conservative forced-close pricing resolved in design. Replace static-universe warnings only for fully covered replays.

## Capabilities

### New Capabilities
- `point-in-time-market-context`: File-backed date-effective eligibility, blocker-window validation, and deterministic safety queries.

### Modified Capabilities
- `trading-system`: Backtests require complete market context and expose context-driven skip/forced-close outcomes without changing scanner, accounting, data, or broker behavior.

## Approach

Inject a clock-free `MarketContext` interface into `BacktestRun`; keep parsing in an adapter. Filter scanner universes by date, check blockers before entry and for open positions, and separate context reasons from `GateReason`. The CLI loads context explicitly and fails closed. Forecast: 500–750 authored lines, within the 800-line budget.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `src/invest/domain/market_context.py` | New | Context interface |
| `src/invest/adapters/backtest_context_json.py` | New | File adapter |
| `src/invest/application/backtest_run.py` | Modified | Eligibility, skips, forced closes |
| `src/invest/adapters/cli.py` | Modified | Required context and reporting |
| `tests/application/test_backtest_run.py` | Modified | Replay safety tests |
| `tests/adapters/test_cli_backtest.py` | Modified | CLI safety tests |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Curated files are incomplete | Med | Validate range/symbol coverage; fail closed |
| Forced closes overstate price certainty | Med | Use conservative deterministic rules and explicit reasons |
| Context reasons blur portfolio gates | Low | Separate outcome taxonomy and telemetry |

## Rollback Plan

Revert context injection, CLI option, schemas, and tests; restore the static-universe warning. No state migration is involved.

## Dependencies

- Externally prepared eligibility and blocker-window files; Alpaca remains authoritative only for bars.

## Success Criteria

- [x] Eligible symbols vary deterministically by replay date with no future leakage.
- [x] Corporate-action and missing-earnings windows produce visible skips or forced closes.
- [x] Missing, invalid, or incomplete context aborts CLI replay with one machine-readable error.
- [x] Existing scanner, Alpaca, portfolio, and broker behavior remains unchanged.
