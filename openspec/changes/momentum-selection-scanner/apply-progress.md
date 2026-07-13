# Apply Progress: Momentum Selection Scanner

**Change**: `momentum-selection-scanner`
**Mode**: Strict TDD
**Delivery**: implemented in the working tree only (per explicit instruction) — no branches, no commits, no PRs were created this pass
**Chain Strategy**: `feature-branch-chain` (recorded for the delivery step; not yet materialized as branches)
**Boundary**: all 3 slices (indicators/rejections/fixtures → domain scanner → port/CLI/boundary) completed in a single working-tree pass
**Review Budget**: forecast was 750–950 authored lines across the chain; actual authored diff (git diff --stat on modified files + `wc -l` on new files, fixture JSON excluded per forecast convention) totals ≈603 lines (221 changed in modified files + 379 in new files) — under forecast

## Completed Tasks

- [x] 1.1 RED: Extended `tests/domain/test_indicators.py` with hand-computed-value tests for `simple_moving_average`, `trailing_high`, `momentum_return`, `sma_is_rising`.
- [x] 1.2 GREEN: Added `simple_moving_average`, `trailing_high`, `momentum_return`, `sma_is_rising` to `src/invest/domain/indicators.py`; `average_true_range` unchanged.
- [x] 1.3 RED: Created `tests/domain/test_rejection.py` asserting the three new `RejectionReason` members exist with distinct string values.
- [x] 1.4 GREEN: Added `NOT_TOP_MOMENTUM_RANK`, `BELOW_52_WEEK_HIGH_PROXIMITY`, `TREND_FILTER_FAILED` to `src/invest/domain/rejection.py`.
- [x] 1.5 RED: Created `tests/fixtures/test_backtest_252_fixtures.py` asserting fixture existence, ≥253 bars/symbol, and `MarketContext.require_complete()` success.
- [x] 1.6 GREEN: Authored `fixtures/backtest-252/{universe,bars,market-context}.json` — deterministic, generated, Decimal-only (3 symbols × 260 bars: `MOMLONG` strong uptrend, `FLATLINE` flat, `DOWNTREND` decline; 260 = 253-day minimum-history gate + 7 extra days so an accepted Core decision has subsequent entry bars in Slice 3's replay harness).
- [x] 1.7 REFACTOR: Confirmed Decimal-only/no-float fixture values; reran Slice 1 focused command.
- [x] 2.1 RED: Created `tests/domain/test_momentum_selection_scanner.py` with in-code 253-bar builders covering insufficient-history, ceil(0.15×pool) cutoff (small-pool guarantee + larger-pool exact-k), deterministic tie-break, proximity rejection, both trend-filter rejection shapes, breakout accept/NO_SIGNAL reject, one-decision-per-symbol + `(decision_date, symbol)` sort, and unsupported-symbol guard.
- [x] 2.2 GREEN: Created `src/invest/domain/momentum_selection_scanner.py` implementing `MomentumSelectionScanner.scan()` as the 5-stage pipeline.
- [x] 2.3 REFACTOR: Extracted `_group_by_symbol` static helper (self-contained in the new module; `MomentumScanner` untouched); reran Slice 2 focused command.
- [x] 3.1 RED: Extended `tests/adapters/test_cli_backtest.py` — `--strategy core` replay assertion via `fixtures/backtest-252`, default-vs-explicit-`benchmark` byte-parity, and unknown-`--strategy` machine-readable-error test.
- [x] 3.2 RED: Extended `tests/test_boundaries.py` asserting `strategy` is defined only on `_backtest_parser`.
- [x] 3.3 GREEN: Added `ScannerPort` Protocol to `src/invest/application/ports.py`; loosened `BacktestRun`'s `scanner` type hint to `ScannerPort | None` in `src/invest/application/backtest_run.py` (annotation-only).
- [x] 3.4 GREEN: Added `--strategy` (default `benchmark`, manually validated against `{benchmark, core}` before any replay, matching the CLI's existing JSON-error convention rather than argparse `choices=`) to `_backtest_parser`; `backtest_main` now constructs `MomentumScanner()` or `MomentumSelectionScanner()` accordingly.
- [x] 3.5 REFACTOR: Confirmed benchmark path byte-identical via both the test and a live CLI invocation; ran full `pytest` + `ruff` + the Slice 3 runtime harness; confirmed `strategy` stays backtest-only.

15/15 tasks complete.

## Files Changed

| File | Action | What Was Done |
|---|---|---|
| `src/invest/domain/indicators.py` | Modified | Added `simple_moving_average`, `trailing_high`, `momentum_return`, `sma_is_rising` windowed reducers; `average_true_range` unchanged. |
| `src/invest/domain/rejection.py` | Modified | Added `NOT_TOP_MOMENTUM_RANK`, `BELOW_52_WEEK_HIGH_PROXIMITY`, `TREND_FILTER_FAILED`. |
| `src/invest/domain/momentum_selection_scanner.py` | Created | Core 5-stage cross-sectional scanner (history gate → momentum rank → proximity → trend → breakout). |
| `src/invest/application/ports.py` | Modified | Added `ScannerPort` Protocol. |
| `src/invest/application/backtest_run.py` | Modified | Loosened `scanner: MomentumScanner \| None` → `ScannerPort \| None`; no behavior change. |
| `src/invest/adapters/cli.py` | Modified | Added `--strategy` to `_backtest_parser` (backtest-only), manual validation + JSON error, scanner selection in `backtest_main`. |
| `fixtures/backtest-252/universe.json` | Created | 3-symbol universe (generated). |
| `fixtures/backtest-252/bars.json` | Created | 260-bar/symbol deterministic Decimal-only bar set (generated). |
| `fixtures/backtest-252/market-context.json` | Created | Full coverage/eligibility, no blockers, for the full window (generated). |
| `tests/domain/test_indicators.py` | Modified | Added hand-computed tests for the 4 new indicator functions (2 cases each). |
| `tests/domain/test_rejection.py` | Created | Asserts the 3 new rejection reasons exist and are distinct. |
| `tests/fixtures/test_backtest_252_fixtures.py` | Created | Validates fixture existence, bar-count floor, and market-context completeness. |
| `tests/domain/test_momentum_selection_scanner.py` | Created | Full scanner behavior coverage (11 tests). |
| `tests/adapters/test_cli_backtest.py` | Modified | Added `--strategy core` harness test, benchmark byte-parity test, unknown-strategy error test. |
| `tests/test_boundaries.py` | Modified | Added `--strategy` backtest-only boundary test. |
| `openspec/changes/momentum-selection-scanner/tasks.md` | Modified | Marked all 15 tasks `[x]`. |

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1 | `tests/domain/test_indicators.py` | Unit | ✅ `pytest tests/domain/test_indicators.py tests/domain/test_scanner.py` → 9 passed (baseline) | ✅ `ImportError: cannot import name 'momentum_return'` | ✅ `pytest tests/domain/test_indicators.py` → 10 passed | ✅ 2 cases per function (8 new tests total) | ➖ None needed |
| 1.2 | `src/invest/domain/indicators.py` | — | ✅ Same baseline | Paired with 1.1 | Paired with 1.1 | Paired with 1.1 | ➖ None needed |
| 1.3 | `tests/domain/test_rejection.py` | Unit | N/A (new file) | ✅ `AttributeError: type object 'RejectionReason' has no attribute 'NOT_TOP_MOMENTUM_RANK'` | ✅ `pytest tests/domain/test_rejection.py` → 2 passed | ➖ Structural (enum members); "Triangulation skipped: constant definition, one possible output" | ➖ None needed |
| 1.4 | `src/invest/domain/rejection.py` | — | N/A (new members) | Paired with 1.3 | Paired with 1.3 | Paired with 1.3 | ➖ None needed |
| 1.5 | `tests/fixtures/test_backtest_252_fixtures.py` | Unit | N/A (new file) | ✅ fixtures temporarily moved aside → 3 failed (`FixtureValidationError: fixture-invalid`) | ✅ fixtures restored → `pytest tests/fixtures/test_backtest_252_fixtures.py` → 3 passed | ✅ 3 distinct assertions (existence, bar-count floor, context completeness) | ➖ None needed |
| 1.6 | `fixtures/backtest-252/*.json` | — | N/A (new fixtures) | Paired with 1.5 | Paired with 1.5 | Paired with 1.5 | ✅ Decimal-only strings confirmed; no floats/randomness in generator |
| 1.7 | — | — | — | — | — | — | ✅ `pytest tests/domain/test_indicators.py tests/domain/test_rejection.py tests/fixtures/test_backtest_252_fixtures.py` → 15 passed |
| 2.1 | `tests/domain/test_momentum_selection_scanner.py` | Unit | N/A (new file) | ✅ `ModuleNotFoundError: No module named 'invest.domain.momentum_selection_scanner'` | ✅ `pytest tests/domain/test_momentum_selection_scanner.py` → 11 passed (first attempt, numerically pre-verified fixture shapes via the real indicator functions before writing assertions) | ✅ 11 distinct scenarios (insufficient-history, small/large-pool cutoff, tie-break×2-runs, proximity, non-rising-SMA, broken-order, accept, NO_SIGNAL, sort/count, unsupported-symbol) | ➖ Deferred to 2.3 |
| 2.2 | `src/invest/domain/momentum_selection_scanner.py` | — | N/A (new file) | Paired with 2.1 | Paired with 2.1 | Paired with 2.1 | Deferred to 2.3 |
| 2.3 | `src/invest/domain/momentum_selection_scanner.py` | — | ✅ 11/11 before refactor | N/A (refactor, not new behavior) | N/A | N/A | ✅ Extracted `_group_by_symbol`; `pytest tests/domain/test_momentum_selection_scanner.py` → still 11 passed; `ruff check` clean |
| 3.1 | `tests/adapters/test_cli_backtest.py` | Integration | ✅ `pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py` → 33 passed (baseline) | ✅ 3 new tests failed (`SystemExit: 2` unrecognized `--strategy` argument) | ✅ `pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py` → 37 passed | ✅ 3 distinct scenarios (core replay, benchmark byte-parity, unknown-value rejection) | Deferred to 3.5 |
| 3.2 | `tests/test_boundaries.py` | Integration | ✅ Same 33-test baseline | ✅ `AssertionError: assert 'strategy' in {...}` (flag absent) | Paired with 3.1's rerun → 37 passed | ✅ Checks all 3 parsers (backtest/execute/scan) | Deferred to 3.5 |
| 3.3 | `src/invest/application/ports.py`, `backtest_run.py` | — | ✅ Baseline full suite 238 passed after Slice 1+2 (234 before Slice 3's own RED) | Paired with 3.1/3.2 (annotation-only, no new test needed — Protocol shape proven by 3.1's harness test actually running Core through `BacktestRun`) | Paired with 3.1 rerun | N/A (type-hint loosening) | Deferred to 3.5 |
| 3.4 | `src/invest/adapters/cli.py` | — | Same baseline | Paired with 3.1/3.2 | `pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py` → 37 passed | Paired with 3.1's 3 scenarios | Deferred to 3.5 |
| 3.5 | — | — | — | — | — | — | ✅ Full suite 238 passed, 3 skipped; `ruff check .` all checks passed; live CLI byte-parity confirmed (`diff` of default vs `--strategy benchmark` stdout identical); live `--strategy core` run against `fixtures/backtest-252` exit 0, `gates.counts.max-equity-deployed == 7`; live unknown-strategy run exit 2, `{"reason": "strategy-invalid"}` |

## Test Summary

- **Total tests written**: 28 (8 indicator + 2 rejection + 3 fixture-validation + 11 scanner + 3 CLI + 1 boundary)
- **Total tests passing**: 28/28 new, 238/241 full suite (3 pre-existing `skip` markers for live/paper-execute tests, unrelated to this change)
- **Layers used**: Unit (24), Integration (4)
- **Approval tests** (refactoring): None — no refactoring-of-existing-behavior tasks; Slice 2.3/3.5 refactors were extract-and-rerun, not approval-tested
- **Pure functions created**: 4 (`simple_moving_average`, `trailing_high`, `momentum_return`, `sma_is_rising`) plus the pure `MomentumSelectionScanner.scan()`/`_evaluate_candidate` pipeline

## Chained Review Slice Handoff

| Slice | Planned PR boundary | Focused test command and exact result | Runtime harness command/scenario and exact result | Rollback boundary |
|---|---|---|---|---|
| 1 — Indicators, rejections, fixtures | Child PR 1; base = tracker `feat/momentum-selection-scanner` (not yet created) | `uv run --extra dev pytest tests/domain/test_indicators.py tests/domain/test_rejection.py tests/fixtures/test_backtest_252_fixtures.py` → 15 passed | `N/A` — pure domain reducers + static fixture validation, no CLI wiring yet | Revert `indicators.py` additions, `rejection.py` additions, `tests/domain/test_rejection.py`, `tests/fixtures/test_backtest_252_fixtures.py`, and `fixtures/backtest-252/*` |
| 2 — Domain scanner | Child PR 2; base = Slice 1 branch | `uv run --extra dev pytest tests/domain/test_momentum_selection_scanner.py` → 11 passed | `N/A` — pure domain scanner exercised only through unit tests until Slice 3 wires the CLI | Remove `src/invest/domain/momentum_selection_scanner.py` and its test file; Slice 1 indicators/rejections/fixtures remain intact |
| 3 — Port, CLI wiring, boundary safety | Child PR 3; base = Slice 2 branch | `uv run --extra dev pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py` → 37 passed | `uv run --extra dev invest-backtest --universe fixtures/backtest-252/universe.json --bars fixtures/backtest-252/bars.json --market-context fixtures/backtest-252/market-context.json --strategy core --split-date 2020-06-01 --format json` → exit 0, `gates.counts.max-equity-deployed == 7`; repeated with `--strategy benchmark` and no flag against `fixtures/backtest` → byte-identical stdout; repeated with `--strategy bogus` → exit 2, `{"reason": "strategy-invalid"}` | Revert `--strategy` flag, `ScannerPort`, the `backtest_run.py` type-hint loosening, and the CLI/boundary test additions; Slices 1–2 remain intact |

## Work Unit Evidence

| Unit | Focused test command and exact result | Runtime harness command/scenario and exact result | Rollback boundary |
|---|---|---|---|
| 1 | `uv run --extra dev pytest tests/domain/test_indicators.py tests/domain/test_rejection.py tests/fixtures/test_backtest_252_fixtures.py` → 15 passed | `N/A` — pure domain reducers + static fixture validation | Revert `indicators.py`/`rejection.py` additions, `tests/domain/test_rejection.py`, `tests/fixtures/test_backtest_252_fixtures.py`, `fixtures/backtest-252/*` |
| 2 | `uv run --extra dev pytest tests/domain/test_momentum_selection_scanner.py` → 11 passed | `N/A` — pure domain scanner, unit-tested only | Remove `src/invest/domain/momentum_selection_scanner.py` and its test file |
| 3 | `uv run --extra dev pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py` → 37 passed | See Slice 3 runtime harness above (exit 0/0/2 across core/benchmark/invalid) | Revert `--strategy`, `ScannerPort`, `backtest_run.py` annotation change, CLI/boundary test additions |

## Deviations from Design

- Design's Interfaces/Contracts section writes `--strategy {benchmark,core}` in argparse-`choices`-like notation. I implemented it as a plain string argument with **manual** validation inside `backtest_main` (returning `{"reason": "strategy-invalid"}` with exit 2), instead of argparse's `choices=` kwarg. Rationale: every other CLI validation error in `backtest_main` (cost model, split-date, market-context) uses this same manual JSON-error convention with `captured.err == ""`; argparse's `choices=` raises `SystemExit` directly from `parse_args()`, which is uncaught by `backtest_main`'s try/except and would break the established "always returns an int, never raises" contract the rest of the test suite relies on. Behavior (fail closed, non-zero exit, before any replay) is unchanged from design intent; only the mechanism differs.
- `fixtures/backtest-252` uses 260 bars/symbol rather than exactly 253. The extra 7 days give an accepted Core decision a subsequent entry-session bar in the Slice 3 replay harness test (with exactly 253 days, the sole accepted decision would fire on the very last available day, with no next-day bar to enter on). This does not change any Slice 1 acceptance criterion (still ≥253 bars/symbol).
- Task 2.1's cutoff test set includes an additional larger-pool (7-symbol) scenario beyond the small-pool guarantee explicitly named in the task, to triangulate that `ceil(0.15 × pool)` is computed generally (yielding k=2) rather than hardcoded to k=1. Also added one extra `UnsupportedInputError` test to ground the (design-implied, sibling-consistent) grouping/validation reuse in an actual RED/GREEN cycle rather than leaving it untested.

## Issues Found

None.

## Remaining Tasks

None — 15/15 complete.

## Workload / PR Boundary

- **Mode**: chained PRs, `feature-branch-chain` (per user-confirmed `ask-on-risk` resolution) — not yet materialized as branches this pass, per explicit instruction to implement working-tree-only with no branches/commits/PRs
- **Current work unit**: all 3 slices implemented; ready for the delivery step to materialize the chain (branch/commit/PR creation) using the handoff table above
- **Boundary**: Slice 1 (indicators/rejections/fixtures) → Slice 2 (domain scanner) → Slice 3 (port/CLI/boundary), each independently revertible per the rollback boundaries above
- **Estimated review budget impact**: forecast 750–950 authored lines; actual ≈603 authored lines (221 changed in modified files + 379 in new files, fixture JSON excluded) — under forecast; no single slice approaches the 400-line budget in isolation

## Status

15/15 tasks complete. Full `pytest` suite: 238 passed, 3 skipped. `ruff check .`: all checks passed. Ready for `sdd-verify`.
