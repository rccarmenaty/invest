# Tasks: Momentum Selection Scanner

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 750–950 authored lines across the 3-slice chain (~230 + ~480 + ~200); generated fixture JSON excluded |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | Child PR 1 → Child PR 2 → Child PR 3, coordinated by a draft/no-merge tracker |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

Slice 2 (scanner + its 253-bar-builder unit tests covering 5 stages, ties, and determinism) is individually likely to approach or exceed the 400-line budget on its own; keep it isolated as its own child PR rather than folding it into Slice 1 or 3.

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Indicator helpers (SMA/trailing-high/momentum-return/SMA-rising), 3 new `RejectionReason` members, paired `fixtures/backtest-252` set | Child PR 1; base = tracker `feat/momentum-selection-scanner` | `pytest tests/domain/test_indicators.py tests/domain/test_rejection.py tests/fixtures/test_backtest_252_fixtures.py` | N/A: pure domain reducers + static fixture validation, no CLI wiring yet | Revert `indicators.py` additions, `rejection.py` additions, `tests/domain/test_rejection.py`, the fixture-validation test, and `fixtures/backtest-252/*` |
| 2 | `MomentumSelectionScanner` 5-stage cross-sectional domain scanner | Child PR 2; base = Unit 1 branch | `pytest tests/domain/test_momentum_selection_scanner.py` | N/A: pure domain scanner exercised only through unit tests until Slice 3 wires the CLI | Remove `src/invest/domain/momentum_selection_scanner.py` and its test file; Unit 1 indicators/rejections/fixtures remain intact |
| 3 | `ScannerPort`, `--strategy` CLI flag, benchmark byte-parity, boundary guard | Child PR 3; base = Unit 2 branch | `pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py` | `invest-backtest --universe fixtures/backtest-252/universe.json --bars fixtures/backtest-252/bars.json --market-context fixtures/backtest-252/market-context.json --strategy core --format json` (repeat with `--strategy benchmark` and no flag for byte-parity) | Revert `--strategy` flag, `ScannerPort`, the `backtest_run.py` type loosening, and the CLI/boundary test additions; Units 1–2 remain intact |

## Phase 1: Indicators, Rejections, and Fixtures (Slice 1)

- [x] 1.1 RED: Extend `tests/domain/test_indicators.py` with hand-computed-value tests for `simple_moving_average`, `trailing_high`, `momentum_return`, `sma_is_rising` (exact values, offset/exclusion conventions, Decimal-only).
- [x] 1.2 GREEN: Add `simple_moving_average`, `trailing_high`, `momentum_return`, `sma_is_rising` to `src/invest/domain/indicators.py`; keep `average_true_range` unchanged.
- [x] 1.3 RED: Create `tests/domain/test_rejection.py` asserting `RejectionReason.NOT_TOP_MOMENTUM_RANK`, `.BELOW_52_WEEK_HIGH_PROXIMITY`, `.TREND_FILTER_FAILED` exist with distinct string values.
- [x] 1.4 GREEN: Add the three new members to `src/invest/domain/rejection.py`.
- [x] 1.5 RED: Create `tests/fixtures/test_backtest_252_fixtures.py` asserting `fixtures/backtest-252/{universe,bars,market-context}.json` exist, every symbol has ≥253 bars, and `MarketContext.require_complete()` succeeds for the full window (fails closed on any coverage/eligibility drift).
- [x] 1.6 GREEN: Author `fixtures/backtest-252/universe.json`, `bars.json` (deterministic 253+-bar/symbol set), and `market-context.json` (full coverage/eligibility, no blockers) so 1.5 passes.
- [x] 1.7 REFACTOR: Confirm Decimal-only bar values and no floats/randomness in the new fixtures; rerun Slice 1 focused test command.

## Phase 2: Domain Scanner (Slice 2)

- [x] 2.1 RED: Create `tests/domain/test_momentum_selection_scanner.py` with in-code 253-bar builders (mirroring `test_scanner.py`) covering: `insufficient-history` rejection; `ceil(0.15×pool)` cutoff including the small-pool ≥1 guarantee; deterministic tie-break (return desc, symbol asc, stable across repeated runs); 52-week-high proximity rejection; trend-filter rejection for both a non-rising SMA200 and a broken `close>SMA50>SMA200` order; breakout-trigger acceptance and its `NO_SIGNAL` rejection; exactly one `ScanDecision` per universe symbol; decisions sorted `(decision_date, symbol)`.
- [x] 2.2 GREEN: Create `src/invest/domain/momentum_selection_scanner.py` implementing `MomentumSelectionScanner.scan()` as the 5-stage pipeline (history gate → momentum rank → proximity → trend → breakout) using the Slice 1 indicator helpers and rejection reasons.
- [x] 2.3 REFACTOR: Extract any grouping/sort logic shared with `MomentumScanner` without modifying `MomentumScanner` itself; rerun Slice 2 focused test command.

## Phase 3: Port, CLI Wiring, and Boundary Safety (Slice 3)

- [x] 3.1 RED: Extend `tests/adapters/test_cli_backtest.py` — add `--strategy core` replay assertion through the full harness using `fixtures/backtest-252`; add default-vs-explicit-`benchmark` byte-parity assertion (scan decisions, trade logs, metrics); add unknown `--strategy` value rejected with a machine-readable error and non-zero exit before any replay begins.
- [x] 3.2 RED: Extend `tests/test_boundaries.py` to assert `--strategy` is defined only on `_backtest_parser` and absent from the execute and scan CLI parsers.
- [x] 3.3 GREEN: Add `ScannerPort` Protocol to `src/invest/application/ports.py`; loosen `BacktestRun`'s `scanner: MomentumScanner | None` to `ScannerPort | None` in `src/invest/application/backtest_run.py` (annotation-only, no behavior change).
- [x] 3.4 GREEN: Add `--strategy {benchmark,core}` (default `benchmark`) to `_backtest_parser` in `src/invest/adapters/cli.py`; in `backtest_main`, construct `MomentumScanner()` or `MomentumSelectionScanner()` accordingly and pass it into `BacktestRun`.
- [x] 3.5 REFACTOR: Confirm the benchmark path stays byte-identical to pre-change output; run the full `pytest` suite plus the Slice 3 runtime harness; confirm `strategy` stays backtest-only.
