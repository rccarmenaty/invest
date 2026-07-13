# Tasks: Portfolio-Aware Backtest

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 500-700 |
| 800-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR: portfolio replay, metrics, CLI contract, fixtures/tests |
| Delivery strategy | auto-forecast |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
800-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Portfolio replay plus reporting contract | PR 1 | `pytest tests/application/test_backtest_run.py tests/domain/test_backtest_metrics.py tests/adapters/test_cli_backtest.py` | `invest-backtest --split-date <fixture-date>` JSON report; if CLI unavailable, run equivalent test harness | Revert `backtest_run.py`, `models.py`, `backtest_metrics.py`, `cli.py`, and backtest fixtures/tests |

## Phase 1: Domain Contracts and Metric RED Tests

- [x] 1.1 RED: In `tests/domain/test_backtest_metrics.py`, cover equity summary fields, drawdown math, and deterministic repeated output.
- [x] 1.2 RED: In `tests/domain/test_backtest_metrics.py`, cover IS/OOS segmentation by `entry_date`, including split-date trades as OOS.
- [x] 1.3 Add frozen result/summary/telemetry value objects in `src/invest/domain/models.py` for `BacktestResult`, `PortfolioSummary`, gate counts, segments, and warnings.
- [x] 1.4 Implement pure helpers in `src/invest/domain/backtest_metrics.py` for equity summary and segment metrics without full curve serialization.

## Phase 2: Portfolio Replay RED Tests and Core Accounting

- [x] 2.1 RED: In `tests/application/test_backtest_run.py`, cover overlapping entries consuming cash/deployed capacity and deterministic same-day ordering.
- [x] 2.2 RED: In `tests/application/test_backtest_run.py`, cover `insufficient-buying-power`, max concurrency, max deployed equity, and skipped-entry trade-log visibility.
- [x] 2.3 RED: In `tests/application/test_backtest_run.py`, cover exits releasing cash/equity/deployed capital and kill-switch blocking from prior-session equity.
- [x] 2.4 Extend `fixtures/backtest/*` only as needed for contention, exits, gate pressure, kill-switch, and split-date cases. (Existing fixtures were sufficient.)
- [x] 2.5 Modify `src/invest/application/backtest_run.py` so `BacktestRun.replay(..., split_date=None)` tracks cash, equity, open positions, deployed capital, exits, and daily summaries.
- [x] 2.6 Reuse `compute_intent`, `evaluate_halt_gates`, and `evaluate_gates` unchanged in `backtest_run.py`; count stable `GateReason` values as `portfolio-gates-simulated` telemetry.

## Phase 3: CLI Contract and Safety Boundaries

- [x] 3.1 RED: In `tests/adapters/test_cli_backtest.py`, require `--split-date`, malformed/out-of-range split errors as one JSON record, and non-zero exit.
- [x] 3.2 RED: In `tests/adapters/test_cli_backtest.py`, assert JSON includes top-level compatibility metrics plus `portfolio`, `gates`, `equity`, `segments`, and warnings.
- [x] 3.3 RED: In `tests/adapters/test_cli_backtest.py`, assert mandatory limitation labels and no construction/call of `BrokerPort` or live-trading path.
- [x] 3.4 Modify `src/invest/adapters/cli.py` to parse `--split-date`, fail closed, render stable JSON, and preserve day-0/static-universe/approximate-cost warnings plus new simulated-gate/OOS warnings.

## Phase 4: Verification

- [x] 4.1 Run focused pytest command for all touched test files; record unavailable harness honestly if project tooling is absent.
- [x] 4.2 Run `invest-backtest --split-date <fixture-date>` or the closest available fixture harness and verify deterministic JSON output.
