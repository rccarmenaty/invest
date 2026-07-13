```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:da1ac30a63faacf5fd3f0ba83eff8c08370ad72b2cc500099504acd803ad529f
verdict: pass-with-warnings
blockers: 0
critical_findings: 0
requirements: 9/9
scenarios: 14/15
test_command: uv run --extra dev pytest -q
test_exit_code: 0
test_output_hash: sha256:da1ac30a63faacf5fd3f0ba83eff8c08370ad72b2cc500099504acd803ad529f
build_command: uv run --extra dev ruff check .
build_exit_code: 0
build_output_hash: sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18
```

## Verification Report

**Change**: momentum-selection-scanner
**Version**: N/A (initial capability + trading-system delta)
**Mode**: Strict TDD

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 15 |
| Tasks complete | 15 |
| Tasks incomplete | 0 |

All 15 checkboxes in `openspec/changes/momentum-selection-scanner/tasks.md` are `[x]` and each is backed by a real artifact (new/modified source file, new/modified test file, or fixture), cross-checked against `git status`/file reads, not just the checkbox marks.

### Build & Tests Execution
**Build/Lint**: ✅ Passed
```text
$ uv run --extra dev ruff check .
All checks passed!
```

**Tests**: ✅ 238 passed / ❌ 0 failed / ⚠️ 3 skipped (pre-existing live/paper-execute markers, unrelated to this change)
```text
$ uv run --extra dev pytest -q
238 passed, 3 skipped in 2.02s
```

**Coverage**: Coverage analysis skipped — no coverage tool detected (`pytest-cov` not installed).

### Runtime Harness Evidence
| Harness | Command | Result |
|---|---|---|
| Core strategy, 253+-bar fixtures | `invest-backtest --universe fixtures/backtest-252/universe.json --bars fixtures/backtest-252/bars.json --market-context fixtures/backtest-252/market-context.json --strategy core --split-date 2020-06-01 --format json` | exit 0; `gates.counts["max-equity-deployed"] == 7`; all 7 skipped entries are `MOMLONG` — proves the Core scanner actually ran end-to-end and was sized/gated, not a silent benchmark fallback |
| Default vs explicit `benchmark`, existing fixtures | `invest-backtest --universe fixtures/backtest/universe.json --bars fixtures/backtest/bars.json --market-context fixtures/backtest/market-context.json --split-date 2024-01-23 --format json` (no flag) vs same + `--strategy benchmark` | both exit 0; `diff` of stdout → **byte-identical** — confirms no behavior change to the existing benchmark path |
| Unknown strategy | same + `--strategy bogus` | exit 2; stdout `{"reason": "strategy-invalid"}` — fails closed before any replay |

### Spec Compliance Matrix

**Domain: momentum-selection-scanner**

| Requirement | Scenario | Test | Result |
|---|---|---|---|
| Minimum history gate | Reject a short history | `tests/domain/test_momentum_selection_scanner.py::test_rejects_insufficient_history_and_excludes_it_from_ranking` | ✅ COMPLIANT |
| Cross-sectional momentum ranking with top-15% ceiling | Top-15% ceiling keeps at least one candidate | `...::test_ceil_fifteen_percent_cutoff_retains_at_least_one_in_a_small_pool` | ✅ COMPLIANT |
| Cross-sectional momentum ranking with top-15% ceiling | Deterministic tie-break | `...::test_tie_break_is_deterministic_by_symbol_ascending_and_stable_across_runs` | ✅ COMPLIANT |
| Cross-sectional momentum ranking with top-15% ceiling | Reject below the momentum-rank cutoff | `...::test_ceil_fifteen_percent_cutoff_retains_exactly_k_in_a_larger_pool` | ✅ COMPLIANT |
| 52-week-high proximity filter | Reject on low 52-week-high proximity | `...::test_rejects_below_52_week_high_proximity` | ✅ COMPLIANT |
| Trend filter with rising SMA200 | Reject a falling or flat SMA200 | `...::test_rejects_non_rising_sma200_trend_filter` | ✅ COMPLIANT |
| Trend filter with rising SMA200 | Reject a broken moving-average order | `...::test_rejects_broken_moving_average_order_trend_filter` | ✅ COMPLIANT |
| 20-day-high breakout trigger reuse | Accept a candidate passing every layer | `...::test_accepts_a_candidate_passing_every_layer` | ✅ COMPLIANT |
| 20-day-high breakout trigger reuse | Reject a candidate failing only the breakout trigger | `...::test_rejects_no_signal_when_only_the_breakout_trigger_fails` | ✅ COMPLIANT |
| Granular per-layer rejection reasons | Rejection reason identifies the failing layer | (see note below) | ⚠️ PARTIAL |
| Deterministic Decimal-only output | Repeated runs are identical | `...::test_tie_break_is_deterministic_by_symbol_ascending_and_stable_across_runs` (asserts `scan()` called twice, `first == second`) | ✅ COMPLIANT |

**Note (PARTIAL)**: The scenario literally reads "GIVEN candidates rejected at different filter layers **in the same run**". Every individual `RejectionReason` (`INSUFFICIENT_HISTORY`, `NOT_TOP_MOMENTUM_RANK`, `BELOW_52_WEEK_HIGH_PROXIMITY`, `TREND_FILTER_FAILED`, `NO_SIGNAL`) is separately proven to fire correctly (one-symbol-per-test), and `tests/domain/test_rejection.py::test_momentum_selection_scanner_reasons_are_mutually_distinct` proves the reason values are distinct. But no single test exercises a `scan()` call with a multi-symbol universe whose candidates are rejected at ≥2 *different* layers in one run and asserts the reasons differ within that one result set. Behaviorally the requirement is satisfied (each layer's rejection is real and distinct), but the exact integration scenario as written has no single covering test. **WARNING**, not CRITICAL — no code path violates the requirement; this is a test-suite gap.

**Domain: trading-system (delta)**

| Requirement | Scenario | Test | Result |
|---|---|---|---|
| Backtest strategy selection | Default and explicit benchmark are identical | `tests/adapters/test_cli_backtest.py::test_backtest_default_and_explicit_benchmark_strategy_are_byte_identical` (unit-test level) + live CLI diff (runtime harness, see above) | ✅ COMPLIANT |
| Backtest strategy selection | Core strategy replays through the same harness | `tests/adapters/test_cli_backtest.py::test_backtest_strategy_core_replays_through_the_same_harness` + live CLI run | ✅ COMPLIANT |
| Backtest strategy selection | Unknown strategy value is rejected | `tests/adapters/test_cli_backtest.py::test_backtest_rejects_unknown_strategy_value_with_one_json_error_before_any_replay` + live CLI run | ✅ COMPLIANT |
| Strategy flag stays backtest-only | Execute and scan parsers reject the flag | `tests/test_boundaries.py::test_strategy_flag_is_backtest_only_and_absent_from_execute_and_scan_parsers` | ✅ COMPLIANT |

**Compliance summary**: 14/15 scenarios COMPLIANT, 1/15 PARTIAL (test-coverage gap, not a code defect). 9/9 requirements have every constituent behavior covered by at least one passing test.

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|---|---|---|
| 5-stage pipeline order (history → rank → proximity → trend → breakout) | ✅ Implemented | `src/invest/domain/momentum_selection_scanner.py:33-60` matches design.md's Data Flow exactly |
| `ceil(0.15 × pool)` cutoff, ≥1 guarantee | ✅ Implemented | `momentum_selection_scanner.py:50` — `ceil(TOP_MOMENTUM_PERCENT * len(ranked))`; empty pool guarded (`if ranked else 0`) |
| Tie-break: return desc, symbol asc | ✅ Implemented | `momentum_selection_scanner.py:46-49` sort key `(-momentum_return(...), item[0])` |
| Proximity: close ≥ 0.95 × trailing 252-day high, candidate excluded | ✅ Implemented | `momentum_selection_scanner.py:79-83` — `history = symbol_bars[:-1]` excludes candidate before calling `trailing_high` |
| Trend: close > SMA50 > SMA200 AND SMA200 rising, candidate excluded | ✅ Implemented | `momentum_selection_scanner.py:85-90`, same `history` slice |
| Breakout: close > prior 20-day high | ✅ Implemented | `momentum_selection_scanner.py:92-93` |
| Decimal-only, no floats/randomness | ✅ Implemented | `indicators.py` and `momentum_selection_scanner.py` use only `Decimal`/`ceil`; `tests/test_boundaries.py::test_domain_has_no_outward_dependencies_or_nondeterministic_calls` globs `src/invest/domain/*.py` (auto-covers the two new/modified files) and forbids `random` imports — passes |
| Sorted `(decision_date, symbol)` output | ✅ Implemented | `momentum_selection_scanner.py:60` |
| `ScannerPort` Protocol seam | ✅ Implemented | `src/invest/application/ports.py:14-19`; `BacktestRun.__init__` type hint loosened at `backtest_run.py:73` |
| `--strategy` flag, backtest-only | ✅ Implemented | `cli.py:154` (`_backtest_parser` only); absent from `_parser()` (scan) and `_execute_parser()` |
| Fixture Decimal-only | ✅ Implemented | Spot-checked `fixtures/backtest-252/bars.json` — every numeric field (`open`/`high`/`low`/`close`) is a JSON string, parsed as `Decimal` by pydantic; only `volume` is int |

### Coherence (Design)
| Decision | Followed? | Notes |
|---|---|---|
| New sibling scanner behind existing `scan()` shape | ✅ Yes | `MomentumSelectionScanner.scan(universe, bars) -> list[ScanDecision]`, identical shape to `MomentumScanner`; `MomentumScanner` itself untouched (`git diff` confirms zero changes to `scanner.py`) |
| Cross-sectional rank inside the scanner (no `BacktestRun` replay-loop change) | ✅ Yes | `backtest_run.py`'s `scan_decisions`/`replay` methods are unchanged except the `scanner` type hint |
| `ScannerPort` Protocol + loosened type hint | ✅ Yes | Annotation-only change, confirmed by reading `backtest_run.py:73,81` |
| Per-layer rejection reasons (3 new enum members) | ✅ Yes | `rejection.py:15-17` |
| Indicators as windowed reducers, scanner owns offset/exclusion | ✅ Yes | `indicators.py` functions are pure slice reducers; `momentum_selection_scanner.py` does all `[:-1]` slicing |
| No separate `invest-backtest-core` entrypoint | ✅ Yes | Single `_backtest_parser`/`backtest_main`, strategy selected via flag |
| No `--scanner-config path.json` | ✅ Yes | Not present in `cli.py` |
| 3-slice chained-PR delivery | ⚠️ Partial | apply-progress reports all 3 slices implemented in a single working-tree pass with no branches/commits/PRs created yet ("per explicit instruction"); this is a delivery-mechanics deviation, not a code/spec deviation — the code itself is structured so the 3 slices remain independently revertible per the documented rollback boundaries |

### Documented Deviation Judgment: `--strategy` manual validation vs. design's `choices=`-style notation

**Verdict: ACCEPTABLE — not a spec violation.**

- Spec text (trading-system delta, "Unknown strategy value is rejected"): *"WHEN `invest-backtest` starts / THEN it MUST fail with a machine-readable error and exit non-zero before any replay begins."* The spec only constrains observable behavior (machine-readable error, non-zero exit, before replay) — it does not mandate argparse `choices=` as the mechanism.
- Design's Interfaces/Contracts section (`--strategy {benchmark,core}`) is Python-signature-style shorthand, not an explicit architecture decision entry; the Architecture Decisions table has no row constraining the validation *mechanism*.
- Verified in `cli.py:167-168`: `if args.strategy not in BACKTEST_STRATEGIES: return _backtest_strategy_error()` runs inside `backtest_main`'s try block, **before** `JsonFixtureReader().load(...)`, before market-data fetch, before split-date validation, and before `BacktestRun(...).replay(...)` — i.e., strictly before any replay begins, matching the scenario text exactly.
- `_backtest_strategy_error()` returns `{"reason": "strategy-invalid"}` with exit code 2 — a machine-readable error, non-zero exit, consistent with the CLI's established convention for `cost-model-invalid`, `split-date-invalid`, and `market-context-missing`.
- Rationale for avoiding argparse `choices=`: it would raise `SystemExit` directly from `parser.parse_args()`, which happens **outside** `backtest_main`'s try/except, breaking the "always returns an int, never raises" contract that the rest of the CLI test suite depends on (confirmed: every other `_backtest_parser` validation in this file uses the same manual-JSON-error pattern, none use `choices=` for a value that needs a JSON error body).
- Runtime harness confirms the exact behavior: `--strategy bogus` → exit 2, `{"reason": "strategy-invalid"}`, no replay side effects.

This is a legitimate, well-reasoned implementation-detail deviation from a non-binding piece of design shorthand. It satisfies both the spec scenario and the project's established CLI error-handling convention.

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | ✅ | Full "TDD Cycle Evidence" table present in `apply-progress.md` for all 15 tasks |
| All tasks have tests | ✅ | 15/15 tasks map to an existing test file (or are paired RED/GREEN with a sibling task's test file) |
| RED confirmed (tests exist) | ✅ | All test files listed in the evidence table exist and were read directly: `test_indicators.py`, `test_rejection.py`, `test_backtest_252_fixtures.py`, `test_momentum_selection_scanner.py`, `test_cli_backtest.py`, `test_boundaries.py` |
| GREEN confirmed (tests pass) | ✅ | 238/238 non-skipped tests pass on independent rerun (`uv run --extra dev pytest -q`), matching apply-progress's reported counts exactly |
| Triangulation adequate | ✅ | Indicators: 2 cases/function; scanner: 11 distinct scenarios (small-pool + larger-pool cutoff added beyond the task's literal wording, deliberately triangulating `ceil()` generality); CLI: 3 distinct scenarios; rejection enum: structural (documented "triangulation skipped" is correctly justified — a StrEnum member has one possible output) |
| Safety Net for modified files | ✅ | Baseline counts reported per slice (9/15/33/238-before-Slice-3's-own-RED) and independently plausible given the final 238-passed total |

**TDD Compliance**: 6/6 checks passed

---

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 24 | 4 (`test_indicators.py`, `test_rejection.py`, `test_backtest_252_fixtures.py`, `test_momentum_selection_scanner.py`) | pytest |
| Integration | 4 | 2 (`test_cli_backtest.py`, `test_boundaries.py`) | pytest + argparse/AST |
| E2E | 0 | 0 | not installed |
| **Total** | **28** | **6** | |

---

### Changed File Coverage
Coverage analysis skipped — no coverage tool detected (`pytest-cov` not installed in this project's dev extras).

---

### Assertion Quality
Reviewed `tests/domain/test_momentum_selection_scanner.py`, `tests/domain/test_indicators.py`, `tests/domain/test_rejection.py`, `tests/fixtures/test_backtest_252_fixtures.py`, and the new assertions in `tests/adapters/test_cli_backtest.py` / `tests/test_boundaries.py`.

- No tautologies found.
- No assertions that skip production code — every test calls `MomentumSelectionScanner().scan(...)`, an indicator function, `cli.backtest_main(...)`, or inspects real `argparse` parser objects.
- The two `for symbol in (...)` / `for run in (...)` loops (`test_ceil_fifteen_percent_cutoff_retains_exactly_k_in_a_larger_pool`, `test_tie_break_is_deterministic_by_symbol_ascending_and_stable_across_runs`) iterate over **hardcoded, non-empty static tuples**, not over a queryAll/filter result that could be empty — not a ghost-loop pattern.
- Each test asserts differing expected values (accept vs. distinct `RejectionReason` members, byte-identical vs. non-identical outputs) — well-triangulated, no "all assert empty" pattern.
- `test_backtest_default_and_explicit_benchmark_strategy_are_byte_identical` and the live-CLI diff both assert *equality of full output*, not a subset — a genuinely strong regression guard for the byte-parity requirement.

**Assertion quality**: ✅ All assertions verify real behavior

---

### Quality Metrics
**Linter**: ✅ No errors (`ruff check .` — all checks passed)
**Type Checker**: ➖ Not available (no `mypy`/`pyright` configured in this project)

### Issues Found
**CRITICAL**: None
**WARNING**: 1 — "Granular per-layer rejection reasons" scenario has no single test exercising a multi-symbol run with candidates rejected at ≥2 different layers in the same `scan()` call; requirement is behaviorally satisfied by the sum of per-layer tests, but the literal integration scenario is untested. Recommend (non-blocking): add one combined-universe test to `test_momentum_selection_scanner.py` asserting distinct reasons across ≥2 layers in one `scan()` result.
**SUGGESTION**: None

### Verdict
**PASS WITH WARNINGS** — 15/15 tasks complete with real artifacts; 238/238 tests pass; `ruff check .` clean; all 3 runtime harnesses (Core replay, default/benchmark byte-parity, unknown-strategy fail-closed) confirmed live; the documented `--strategy` manual-validation deviation is judged ACCEPTABLE (matches spec's observable-behavior requirement and the CLI's established error convention); the sole open item is a single WARNING-level test-coverage gap on one scenario's literal wording, with zero CRITICAL findings and zero code-level spec violations.
