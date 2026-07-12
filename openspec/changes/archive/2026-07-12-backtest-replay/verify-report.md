```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:0e2bbbe82308b8382cb016536e2d4ef2e5383cc6a6b79ed6975a341328e2a875
verdict: pass
blockers: 0
critical_findings: 0
requirements: 9/9
scenarios: 14/14
test_command: uv run --extra dev pytest
test_exit_code: 0
test_output_hash: sha256:d687f979b252ad6137861fbb49100c8b0149d501a368700227670d1888cadfb1
build_command: uv run --extra dev ruff check .
build_exit_code: 0
build_output_hash: sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18
```

## Verification Report

**Change**: backtest-replay
**Version**: delta on `trading-system` (9 ADDED requirements)
**Mode**: Strict TDD

**Evidence base**: `proposal.md`, `exploration.md`, `specs/trading-system/spec.md` (9 requirements / 14 scenarios, counted directly from headings), `design.md`, `tasks.md` (27 tasks, 7 phases). **No `apply-progress.md` exists** — this is a graceful-degradation case, not a failure: implementation evidence lives in `tasks.md`'s inline RED/GREEN annotations (specific `AttributeError`/`ModuleNotFoundError` messages, pass counts per task) plus merged PR #17 (implementation, `size:exception`) and PR #18 (4R correction: BRISK-001, BRES-001). HEAD `4fc94bd`, clean tree, confirmed via `git status --porcelain` / `git rev-parse HEAD`.

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 27 |
| Tasks complete | 27 |
| Tasks incomplete | 0 |

All 27 checkboxes in `tasks.md` are `[x]`. Cross-checked task claims against actual source (`alpaca_market_data.py`, `backtest_run.py`, `backtest_metrics.py`, `cli.py`, `models.py`, `test_boundaries.py`) — every task's claimed artifact exists and behaves as described. Task 5.2's documented judgment call (using `design.md`'s literal `cost_model` disclaimer string verbatim instead of composing a new one) was verified byte-for-byte against the live CLI probe output — matches exactly.

### Build & Tests Execution
**Build**: PASSED
```text
$ uv run --extra dev ruff check .
All checks passed!
```

**Tests**: 159 passed / 0 failed / 3 skipped
```text
$ uv run --extra dev pytest -q
................s....................................................... [ 44%]
............ss.......................................................... [ 88%]
..................                                                       [100%]
159 passed, 3 skipped in 9.00s
```
Matches the expected 159/3 exactly.

**Coverage**: Not available — no coverage tool detected in `pyproject.toml`/`--extra dev`. Skipped, not a failure.

### Harness Probes (live evidence)
```text
$ uv run invest-backtest --universe fixtures/backtest/universe.json --bars fixtures/backtest/bars.json --format json
exit 0, trade_count=3
disclaimers.day0        == "DAY-0 MECHANICS ONLY: measures current day-0 paper-trading entry mechanics, NOT SPEC §2.4 confirmed-entry edge."  (verbatim match)
disclaimers.survivorship == "SURVIVORSHIP-BIASED UNIVERSE: fixed historical screen, NOT point-in-time index membership; results are optimistically biased."  (verbatim match)
disclaimers.cost_model   == "COST MODEL IS AN APPROXIMATION: fixed-bps slippage + zero commission + flat tax haircut, not precision accounting."  (verbatim match)
trades: WIN/take-profit, LOSS/stop, OPENEND/open-at-end

$ uv run invest-scan --universe fixtures/v1/universe.json --bars fixtures/v1/bars.json --format json
exit 0 — MOMO accepted (candidate.accepted.v1), ACME rejected (insufficient-history) — pre-existing regression path unaffected.
```

### Spec Compliance Matrix
| Requirement | Scenario | Test | Result |
|---|---|---|---|
| Bulk historical range fetch | Range fetch returns validated multi-day bars | `test_alpaca_market_data.py::test_fetch_range_returns_untrimmed_caller_supplied_window`, `::test_fetch_range_paginates_and_shares_retry_machinery` | ✅ COMPLIANT |
| Bulk historical range fetch | Existing fetch is unchanged | `test_alpaca_market_data.py::test_fetch_regression_baseline_params_and_output_unchanged_before_refactor` | ✅ COMPLIANT |
| Bulk historical range fetch | Range fetch failure uses the existing taxonomy | `test_auth_failure_is_stable_and_not_retried`, `test_malformed_response_is_stable_and_not_retried`, `test_retryable_statuses_exhaust_three_attempts`, `test_timeout_exhausts_three_attempts` (exercise the literal shared `_paginate`/`_send_with_retry` method `fetch_range` calls unmodified — same object, not duplicated logic) | ✅ COMPLIANT |
| Deterministic day-by-day replay without look-ahead | Replaying the same range twice is identical | `test_backtest_run.py::test_replaying_same_range_twice_is_byte_identical` | ✅ COMPLIANT |
| Deterministic day-by-day replay without look-ahead | Each day sees only its own history | `test_backtest_run.py::test_each_day_window_contains_only_bars_dated_on_or_before_that_day` | ✅ COMPLIANT |
| Look-ahead prevention is a testable property | Mutating future bars does not change a past decision | `test_backtest_run.py::test_mutating_future_bars_does_not_change_day_n_decision` (killer test) | ✅ COMPLIANT |
| Day-0-only mechanics labeling | Report carries the day-0 label | `test_cli_backtest.py::test_backtest_bars_run_prints_one_report_with_metrics_and_disclaimers_and_touches_no_broker` + live probe | ✅ COMPLIANT |
| Survivorship-bias disclaimer | Report carries the survivorship disclaimer | same test + live probe | ✅ COMPLIANT |
| Cost model reported as approximation | Report labels the cost model as approximate | same test + live probe | ✅ COMPLIANT |
| Pure backtest metrics | Same trade log yields identical metrics | No literal double-invocation test of `compute_metrics`; determinism instead proven structurally by `test_boundaries.py::test_domain_has_no_outward_dependencies_or_nondeterministic_calls` (AST-forbids `random`/wall-clock/I-O in `domain/*.py`, which includes `backtest_metrics.py`) plus pure-Decimal, stateless implementation | ⚠️ PARTIAL (structurally proven, not scenario-literal) |
| `invest-backtest` CLI never touches BrokerPort | Successful run prints one machine-readable report | `test_cli_backtest.py::test_backtest_bars_run_prints_one_report_with_metrics_and_disclaimers_and_touches_no_broker` (monkeypatches `AlpacaBroker` to `pytest.fail` if constructed) + live probe | ✅ COMPLIANT |
| `invest-backtest` CLI never touches BrokerPort | Failure prints one machine-readable record | `test_cli_backtest.py::test_backtest_missing_fixture_prints_exactly_one_record_and_exits_two`, `::test_backtest_malformed_bars_fails_with_one_record` | ✅ COMPLIANT |
| Out-of-scope guard | No gap-trading, confirmation, or live-trading code is added | `test_boundaries.py::test_out_of_scope_guard_no_gap_strategy_confirmation_module_or_live_trading_url`; independently confirmed via `rg -n "alpaca_broker|BrokerPort"` on `backtest_run.py`/`backtest_metrics.py` (zero hits) and `fd`+`rg` scan for `gap`/`confirmation` stems under `src/invest` (zero hits) | ✅ COMPLIANT |

**Compliance summary**: 13/14 scenarios fully COMPLIANT, 1/14 PARTIAL (structurally proven, not literal-double-call tested) — 0 UNTESTED, 0 FAILING.

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|---|---|---|
| `fetch_range` additive, `fetch()` untouched | ✅ Implemented | `_paginate`/`_request_params` extraction confirmed in `alpaca_market_data.py:46-165`; `fetch()` is a 1-line call, `fetch_range` a 1-line call, both delegate to the same `_paginate`. |
| Day-by-day window, scanner unchanged | ✅ Implemented | `BacktestRun.scan_decisions` builds `window = bars[date<=d]` per day, calls unmodified `MomentumScanner.scan()`; verified via `_RecordingScanner` test. |
| Trade simulation (entry/exit/tie-break) | ✅ Implemented | Next-open entry, bar-touch stop/TP, stop-wins tie-break, open-at-end — all 4 scenarios individually tested and passing. |
| `backtest_metrics.py` pure functions | ✅ Implemented | `ExitReason` StrEnum, `apply_costs`, `compute_metrics` — hand-computed fixture assertions pass; domain-purity AST boundary enforced. |
| Disclaimers (3 literal strings) | ✅ Implemented | All three verbatim strings confirmed present via test assertions AND live CLI probe output. |
| `invest-backtest` CLI, BrokerPort-free | ✅ Implemented | `backtest_main`/`_backtest_parser`/`_backtest_report` scoped boundary check passes; live probe confirms trade_count=3, exit 0. |
| Out-of-scope guard | ✅ Implemented | No gap-trading/confirmation module; independently re-confirmed via direct grep. |

### Coherence (Design)
| Decision | Followed? | Notes |
|---|---|---|
| Named Decision 1: Day-0-only backtest, loud label | ✅ Yes | Verbatim disclaimer present in every report; no confirmation-service code introduced. |
| Named Decision 2: Survivorship-biased universe, loud disclaimer | ✅ Yes | Verbatim disclaimer present; no point-in-time provider added (correctly out of scope). |
| Named Decision 3: Gap-trading rejected | ✅ Yes | No `gap`-stem module exists anywhere under `src/invest` (grep-confirmed). |
| `fetch_range` via extracted `_paginate` | ✅ Yes | Matches design.md's decision exactly; regression test proves `fetch()` byte-identical pre/post extraction. |
| Stop-wins tie-break, TP gap not credited | ✅ Yes | `test_same_bar_stop_and_take_profit_tie_resolves_to_stop_wins` matches design formula exactly. |
| All cost application in pure `backtest_metrics.py` | ✅ Yes | `BacktestRun` records raw prices only; `apply_costs`/`compute_metrics` own slippage/tax/drawdown math. |

### TDD Compliance
| Check | Result | Details |
|---|---|---|
| TDD Evidence reported | ⚠️ Partial | No separate `apply-progress.md`/TDD-Cycle-Evidence table exists (noted absence per orchestrator context, not treated as failure). Equivalent evidence found inline in `tasks.md`: every RED task cites the exact failure (`AttributeError`, `ModuleNotFoundError`) and every GREEN task cites a pass count. |
| All tasks have tests | ✅ | 27/27 tasks map to an identifiable test file/function; verified by reading `test_alpaca_market_data.py`, `test_backtest_run.py`, `test_backtest_metrics.py`, `test_cli_backtest.py`, `test_boundaries.py` directly. |
| RED confirmed (tests exist) | ✅ | All cited test files exist with the claimed test functions (verified via `rg "^def test_"` against tasks.md's per-task references). |
| GREEN confirmed (tests pass) | ✅ | 159/159 non-skipped tests pass on live execution — matches every GREEN claim in `tasks.md`. |
| Triangulation adequate | ✅ | Multi-scenario requirements (trade simulation, fetch error taxonomy, disclaimers) each have 2+ distinct test cases with differing expected values (stop vs. TP vs. open-at-end; auth vs. malformed vs. timeout). |
| Safety Net for modified files | ✅ | `alpaca_market_data.py` (modified, not new): task 1.5 explicitly re-ran the pre-refactor regression pin post-refactor and confirmed byte-identical output before proceeding. |

**TDD Compliance**: 5/6 checks fully passed, 1/6 partial (missing dedicated apply-progress artifact, compensated by inline task evidence — WARNING, not blocking).

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|---|---|---|---|
| Unit | ~50 (new/modified for this change: fetch_range, backtest_run, backtest_metrics, cli_backtest, boundaries) | 5 | `pytest` |
| Integration | 0 | 0 | not installed |
| E2E | 2 (manual harness probes, not part of the automated suite) | — | shell/CLI |
| **Total (project-wide)** | **159 passed + 3 skipped** | — | `pytest` |

### Changed File Coverage
Coverage analysis skipped — no coverage tool detected in the `dev` extra.

### Assertion Quality
No CRITICAL or WARNING violations found in the reviewed test files (`test_backtest_run.py`, `test_cli_backtest.py`, `test_backtest_metrics.py`). All assertions call production code (`BacktestRun`, `compute_metrics`, `apply_costs`, `cli.backtest_main`) and assert specific, hand-computed, non-trivial values (exact prices, exact reasons, exact JSON keys) — no tautologies, no ghost loops over possibly-empty collections (the one loop, in `test_each_day_window_contains_only_bars_dated_on_or_before_that_day`, iterates a non-empty `dates` list derived from the fixture's own bars, and is paired with a length-equality assertion outside the loop).

**Assertion quality**: ✅ All assertions verify real behavior

### Quality Metrics
**Linter**: ✅ No errors (`uv run --extra dev ruff check .` → `All checks passed!`)
**Type Checker**: ➖ Not available (no type-checker configured in `dev` extra)

### Bounded Review Receipt
Lineage `backtest-replay-clean` at commit `4fc94bd` (matches current HEAD). `reviews/ledger.json` contains 6 findings, **all `status: info`** (2 WARNING resolved-in-PR#18 confirmations — BRISK-001 evadable-boundary fix, BRES-001 fail-closed-on-missing-symbol fix; 3 WARNING open follow-ups — scope-guard evadability, malformed-response/MAX_PAGES conflation, O(days×bars) rescan; 1 SUGGESTION — readability cleanup backlog). Zero open CRITICAL/BLOCKER findings. Independently spot-checked: `test_strengthened_broker_reference_checker_catches_module_attribute_evasion` (BRISK-001 fix) and `test_backtest_live_range_missing_symbol_bars_fails_closed_with_one_record` (BRES-001 fix) both exist and pass.

### Issues Found
**CRITICAL**: None

**WARNING**:
1. No dedicated `apply-progress.md`/TDD-Cycle-Evidence artifact exists for this change — evidence is inline in `tasks.md` per-task annotations instead. Functionally equivalent but non-standard; recommend the next change in this project produce a dedicated apply-progress artifact for cleaner downstream auditability.
2. "Pure backtest metrics — same trade log yields identical metrics" scenario has no literal test that calls `compute_metrics` twice on the same log and diffs the two results; determinism is proven structurally (domain-purity AST boundary forbidding randomness/wall-clock/I-O) rather than by a scenario-literal test. Low risk given the AST-level guarantee, but a direct triangulating test would close the gap cleanly.
3. Three open follow-ups already tracked and accepted in `reviews/ledger.json` (TBTR-003 scope-guard evadable-by-rename, TBTR-004 malformed-response/MAX_PAGES conflation, TBTR-006 readability cleanup) — carried forward by design, not new findings from this verify pass.

**SUGGESTION**:
1. `TBTR-005` (ledger): `scan_decisions` rescans the full merged bar window per trading day (O(days × total_bars)) — fine for the current fixture scale, would need attention before a real multi-year/multi-symbol backtest run.

### Verdict
**PASS WITH WARNINGS** — All 9 requirements and 14 scenarios have implementation evidence; 13/14 scenarios have direct literal covering tests that pass, 1/14 is structurally (not literally) proven. All 27 tasks are complete and truthful against the code. Full test suite (159 passed, 3 skipped) and lint (`ruff check .`) are green. Both harness probes match expected output exactly, including all three verbatim disclaimer strings. Boundary/out-of-scope guards pass and were independently re-verified by direct source grep. Zero CRITICAL findings; zero open BLOCKER/CRITICAL items in the bounded-review ledger. Safe to proceed to `sdd-archive`.
