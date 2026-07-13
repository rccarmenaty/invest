# Apply Progress: Portfolio-Aware Backtest

## Status

Implementation tasks 1.1-3.4 are complete in Strict TDD mode. Final verification tasks 4.1-4.2 remain pending for `sdd-verify`.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1-1.4 | `tests/domain/test_backtest_metrics.py` | Unit | 21 focused tests passed | Import error for `compute_equity_summary` | 6/6 passed | Equity paths plus empty/default metric path | Pure summary/segment helpers |
| 2.1-2.6 | `tests/application/test_backtest_run.py` | Integration | 21 focused tests passed | `replay(..., split_date=...)` rejected | 11/11 passed | deployed cap, buying power, exit, kill-switch | Removed unused exit helper argument |
| 3.1-3.4 | `tests/adapters/test_cli_backtest.py` | Integration | 21 focused tests passed | Mandatory warnings assertion failed | 12/12 passed | missing, malformed, and out-of-range split dates | Stable nested JSON report |

## Focused Development Evidence

The following evidence was captured during implementation. It is retained as focused development evidence and does not complete the independent final verification phase.

| Evidence | Result |
|---|---|
| Focused test command and exact result | `uv run --extra dev pytest tests/domain/test_backtest_metrics.py tests/application/test_backtest_run.py tests/adapters/test_cli_backtest.py` — exit 0, 31 passed. |
| Runtime harness command/scenario and exact result | Two identical invocations of `uv run invest-backtest --universe fixtures/backtest/universe.json --bars fixtures/backtest/bars.json --split-date 2024-01-23 --format json` — exit 0; byte-identical JSON included portfolio, gates, equity, segments, and limitation labels. |
| Rollback boundary | Revert `src/invest/application/backtest_run.py`, `src/invest/domain/models.py`, `src/invest/domain/backtest_metrics.py`, `src/invest/adapters/cli.py`, and their focused tests; no fixture or broker changes are required. |

## Completion

- Completed implementation: 1.1-1.4, 2.1-2.6, 3.1-3.4
- Pending final verification: 4.1-4.2 (`sdd-verify` must independently run and record the focused suite and deterministic CLI harness).
- Deferred by scope: point-in-time universe, confirmation logic, and execution realism.
- Delivery: one approved PR slice; current diff is within the 800-line budget.
