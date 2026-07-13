# Apply Progress: Point-in-Time Market Context

**Change**: `point-in-time-market-context`
**Mode**: Strict TDD
**Delivery**: local feature-branch chain materialized and re-integrated as a clean candidate
**Chain Strategy**: `feature-branch-chain`
**Boundary**: completed implementation remains materialized as three dependent local review slices: domain/JSON → replay integration → CLI/reporting and boundary safety; the reviewed correction deltas are now cherry-picked onto a clean integrated branch
**Review Budget**: integrated tracker→CLI diff = 1,702 changed lines; materialized slice reviews = 593 / 327 / 782; the CLI slice remains 382 lines above the default 400-line review budget
**Source Chain State**: tracker `feat/point-in-time-market-context` @ `70f4be0`; domain child `feat/pit-market-context-domain` @ `dd444b8` (review size 593); replay child `feat/pit-market-context-replay` @ `6bdd9bb` (review size 327); CLI child `feat/pit-market-context-cli` @ `1a39a4f` (review size 782, current branch); no pushes or PRs
**Integrated Candidate**: `feat/point-in-time-market-context-integrated` @ `3141020a08170c589d8847892d5f5a9cfdb2776b`; reviewed corrections cherry-picked as `d2ca0bf3989e974ae133a2ca5ebcfca55ffc92fe`, `a95daafe7dd46b5b7458270d156c3f1ebcb495c5`, and `3141020a08170c589d8847892d5f5a9cfdb2776b`; no push / no PR

## Completed Tasks

- [x] 1.1 RED: Create `tests/domain/test_market_context.py` for complete/missing/contradictory matrices, future-mutation immunity, inclusive blockers, and exact outcome/reason values.
- [x] 1.2 GREEN: Create `src/invest/domain/market_context.py` with immutable `status()`/`require_complete()` semantics and stable incomplete/invalid failures.
- [x] 1.3 RED: Create `tests/adapters/test_backtest_context_json.py` for unreadable, malformed, unsupported-version, overlapping, and semantically incomplete JSON.
- [x] 1.4 GREEN: Create strict `src/invest/adapters/backtest_context_json.py` and fully covered `fixtures/backtest/market-context.json`.
- [x] 1.5 REFACTOR: Keep Pydantic/file concerns out of `market_context.py`; rerun Unit 1 tests.
- [x] 2.1 RED: Extend `tests/application/test_backtest_run.py` for date-filtered scans, blocked entries, first-unsafe-date forced closes before exits/entries at `bar.low`, missing-D-bar abort, determinism, and all-eligible parity.
- [x] 2.2 GREEN: Update `src/invest/domain/models.py` and `src/invest/application/backtest_run.py` to require coverage, expose context outcomes, and preserve scanner, accounting, costs, and gate telemetry.
- [x] 2.3 REFACTOR: Centralize date/context sequencing without modifying scanner, provider, broker, execution, accounting, or cost modules; rerun Unit 2 tests.
- [x] 3.1 RED: Extend `tests/adapters/test_cli_backtest.py` for required context, one exit-2 context error, no partial report, PIT statement replacement, outcomes, and zero broker calls.
- [x] 3.2 RED: Extend `tests/test_boundaries.py`, `tests/application/test_execute_run.py`, `tests/adapters/test_cli_execute.py`, and `tests/adapters/test_alpaca_broker.py` to preserve bars-only Alpaca, `--execute`, paper endpoint, and live gates.
- [x] 3.3 GREEN: Update `src/invest/adapters/cli.py` to load `--market-context`, map stable failures, and emit one PIT report with context outcomes.
- [x] 3.4 REFACTOR: Keep context backtest-only; run all focused commands, full `pytest`, and the Unit 3 runtime harness.

## Files Changed

| File | Action | What was done |
|---|---|---|
| `src/invest/domain/market_context.py` | Created | Added immutable PIT context windows, status/outcome enums, and fail-closed validation errors. |
| `src/invest/adapters/backtest_context_json.py` | Created | Added strict JSON v1 loader that builds domain `MarketContext` instances. |
| `fixtures/backtest/market-context.json` | Created | Added deterministic fully covered CLI fixture context. |
| `src/invest/application/backtest_run.py` | Modified | Required context coverage, filtered scan windows, emitted context outcomes, and forced-closed unsafe positions before normal exits/entries. |
| `src/invest/domain/models.py` | Modified | Added `context_outcomes` to `BacktestResult`. |
| `src/invest/adapters/cli.py` | Modified | Required `--market-context`, mapped context errors, and emitted PIT reporting/disclaimers. |
| `tests/domain/test_market_context.py` | Created | Added domain RED/GREEN coverage for complete/incomplete/contradictory PIT semantics. |
| `tests/adapters/test_backtest_context_json.py` | Created | Added strict loader/error mapping tests for JSON market-context files. |
| `tests/application/test_backtest_run.py` | Modified | Added PIT replay tests for eligibility filtering, entry blocking, forced closes, and incomplete unsafe-bar aborts. |
| `tests/adapters/test_cli_backtest.py` | Modified | Added backtest CLI requirements for market-context failures, PIT labels, and context outcomes. |
| `tests/test_boundaries.py` | Modified | Added boundary regression proving market-context stays backtest-only. |
| `tests/application/test_execute_run.py` | Modified | Added regression guard that execution flow stays free of market-context dependency. |
| `tests/adapters/test_cli_execute.py` | Modified | Added regression guard that execute CLI does not accept backtest market-context input. |
| `tests/adapters/test_alpaca_broker.py` | Modified | Added regression guard that broker adapter remains market-context-free. |
| `openspec/changes/point-in-time-market-context/tasks.md` | Modified | Marked all 12 tasks complete and synchronized the exact local review-chain and integrated-candidate branch, commit, verification, approval, and no-remote state. |
| `openspec/changes/point-in-time-market-context/apply-progress.md` | Modified | Preserved TDD/review-boundary evidence and appended the integrated candidate branch, lineage, verification, and pending-verify metadata. |

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1 | `tests/domain/test_market_context.py` | Unit | N/A (new) | `uv run --extra dev pytest tests/domain/test_market_context.py` → 0 collected, `ModuleNotFoundError` | Paired with 1.2 → 5 passed | 5 cases across safe/blocked/ineligible/incomplete/inclusive paths | Paired with 1.5 → Unit 1 command 11 passed |
| 1.2 | `tests/domain/test_market_context.py` | Unit | N/A (new) | Covered by 1.1 | `uv run --extra dev pytest tests/domain/test_market_context.py` → 5 passed | Domain tests cover multiple statuses and future-mutation behavior | Domain stayed adapter-free; later Unit 1 rerun stayed green |
| 1.3 | `tests/adapters/test_backtest_context_json.py` | Unit | N/A (new) | `uv run --extra dev pytest tests/adapters/test_backtest_context_json.py` → 0 collected, `ModuleNotFoundError` | Paired with 1.4 → Unit 1 command 11 passed | Added unreadable, malformed, unsupported, overlapping, and incomplete cases | Paired with 1.5 → Unit 1 command 11 passed |
| 1.4 | `tests/adapters/test_backtest_context_json.py` | Unit | N/A (new) | Covered by 1.3 | `uv run --extra dev pytest tests/domain/test_market_context.py tests/adapters/test_backtest_context_json.py` → 11 passed | Loader and domain assertions cover distinct schema and semantic paths | Fixture coverage corrected to full replay-date matrix; Unit 1 rerun stayed green |
| 1.5 | `tests/domain/test_market_context.py`, `tests/adapters/test_backtest_context_json.py` | Unit | N/A (new) | Covered by 1.1/1.3 | `uv run --extra dev pytest tests/domain/test_market_context.py tests/adapters/test_backtest_context_json.py` → 11 passed | Multiple domain + loader paths still green | Pydantic/file concerns remained isolated to adapter; no domain adapter imports |
| 2.1 | `tests/application/test_backtest_run.py` | Unit | ✅ Baseline `uv run --extra dev pytest tests/application/test_backtest_run.py tests/domain/test_models.py` → 18 passed | `uv run --extra dev pytest tests/application/test_backtest_run.py` → 20 failed after PIT test additions | Paired with 2.2 → 20 passed | Added date-filtered scan, blocked-entry, forced-close, missing-bar, determinism, and parity paths | Paired with 2.3 → focused command stayed green |
| 2.2 | `tests/application/test_backtest_run.py` | Unit | ✅ Same 18-test baseline | Covered by 2.1 | `uv run --extra dev pytest tests/application/test_backtest_run.py` → 20 passed | Existing parity assertions plus new PIT branches forced real replay sequencing logic | Extracted filtered-universe / unsafe-position settlement helpers in 2.3 |
| 2.3 | `tests/application/test_backtest_run.py` | Unit | ✅ Same 18-test baseline | Covered by 2.1 | `uv run --extra dev pytest tests/application/test_backtest_run.py` → 20 passed | 20 passing cases cover old and new branches | Centralized context sequencing without touching scanner/provider/broker/execute/accounting/cost modules |
| 3.1 | `tests/adapters/test_cli_backtest.py` | Integration | ✅ Baseline `uv run --extra dev pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py tests/application/test_execute_run.py tests/adapters/test_cli_execute.py tests/adapters/test_alpaca_broker.py` → 60 passed | Focused command after new CLI/boundary tests → 22 failures (`--market-context` missing in parser / wrong error precedence) | Paired with 3.3/3.4 → focused command 67 passed | Added missing/invalid/incomplete context, PIT labels, runtime report, and zero-broker assertions | Paired with 3.4 → focused, full suite, ruff, and runtime harness all green |
| 3.2 | `tests/test_boundaries.py`, `tests/application/test_execute_run.py`, `tests/adapters/test_cli_execute.py`, `tests/adapters/test_alpaca_broker.py` | Integration | ✅ Same 60-test baseline | Focused command after new boundary tests → 22 failures | Paired with 3.3/3.4 → 67 passed | Added parser/source guards across backtest-only boundary surfaces | Backtest-only boundary held after refactor and runtime evidence |
| 3.3 | `tests/adapters/test_cli_backtest.py` | Integration | ✅ Same 60-test baseline | Covered by 3.1/3.2 | `uv run --extra dev pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py tests/application/test_execute_run.py tests/adapters/test_cli_execute.py tests/adapters/test_alpaca_broker.py` → 67 passed | CLI tests span fixture, live-range stub, invalid/incomplete context, and PIT-report paths | Market-context kept inside backtest CLI only |
| 3.4 | `tests/adapters/test_cli_backtest.py`, boundary suites | Integration | ✅ Same 60-test baseline | Covered by 3.1/3.2 | Focused command 67 passed; full suite `uv run --extra dev pytest` → 202 passed, 3 skipped | Runtime harness and full suite exercised separate CLI/reporting paths beyond focused tests | `uv run --extra dev ruff check .` → all checks passed; runtime harness exit 0 |

## Test Summary

- **Total tests written/expanded**: 2 new test files plus PIT regressions in 6 existing test files
- **Focused commands**:
  - `uv run --extra dev pytest tests/domain/test_market_context.py tests/adapters/test_backtest_context_json.py` → 12 passed in 0.15s
  - `uv run --extra dev pytest tests/application/test_backtest_run.py` → 20 passed in 0.06s
  - `uv run --extra dev pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py tests/application/test_execute_run.py tests/adapters/test_cli_execute.py tests/adapters/test_alpaca_broker.py` → 67 passed in 0.34s
- **Full suite**: `uv run --extra dev pytest` → 202 passed, 3 skipped in 7.43s
- **Linter**: `uv run --extra dev ruff check .` → all checks passed
- **Runtime harness**: `uv run --extra dev invest-backtest --universe fixtures/backtest/universe.json --bars fixtures/backtest/bars.json --market-context fixtures/backtest/market-context.json --split-date 2024-01-23 --format json` → exit 0; `trade_count=1`; `context_outcomes=[]`; warnings include `point-in-time-market-context-validated`
- **Integrated candidate verification**: clean linked worktree `feat/point-in-time-market-context-integrated` @ `3141020a08170c589d8847892d5f5a9cfdb2776b` previously recorded `uv run --extra dev pytest` → 210 passed, 3 skipped; `uv run --extra dev ruff check .` → all checks passed; runtime harness exit 0; clean tree after verification.
- **Command provenance**: focused commands, runtime harness, full suite, and Ruff above were recorded during local chain materialization; integrated candidate verification was recorded later in the clean linked worktree; no commands were run during this artifact synchronization pass.

## Materialized Local Review Chain

- **Implementation completion**: 12/12 tasks remain complete; no implementation code, tests, or fixtures changed in this artifact synchronization pass.
- **Resolved delivery path**: user selected chained PRs with `feature-branch-chain`; the local chain is materialized and the strategy must not change.
- **Local chain state**: tracker `feat/point-in-time-market-context` @ `70f4be0`; domain child `feat/pit-market-context-domain` @ `dd444b8` (review size 593); replay child `feat/pit-market-context-replay` @ `6bdd9bb` (review size 327); CLI child `feat/pit-market-context-cli` @ `1a39a4f` (review size 782, current branch).
- **Remote state**: no matching remote heads and no PRs exist for the tracker or child branches.
- **Verification snapshot**: full suite `202 passed, 3 skipped`; `uv run --extra dev ruff check .` passed.
- **Next phase constraint**: preserve the local review slices as source evidence; independent `sdd-verify` remains pending against the clean integrated candidate.

## Integrated Candidate

- **Branch / HEAD**: `feat/point-in-time-market-context-integrated` @ `3141020a08170c589d8847892d5f5a9cfdb2776b`
- **Cherry-picked reviewed corrections**: domain `d2ca0bf3989e974ae133a2ca5ebcfca55ffc92fe`; replay `a95daafe7dd46b5b7458270d156c3f1ebcb495c5`; CLI `3141020a08170c589d8847892d5f5a9cfdb2776b`; matching patch IDs were confirmed during integration.
- **Source lineage terminal receipts**: domain `approved` with chain identity `sha256:5c4a6b76c36b43c15a4a8d0f44aa146db23f44e7e05fa56a28be7795d59cf2d1`; replay `approved` with chain identity `sha256:13b0eb8ee82333f68b7c1f452c0d172e9975cddc3762f4325bad86070e93cb06`; CLI `approved` with chain identity `sha256:c85c2687d2e8607406b9b49e74b692f2f0869975059fa85b44e9e237982e1616`.
- **Integrated verification evidence**: full `pytest` previously recorded as `210 passed, 3 skipped`; Ruff passed; runtime harness exit `0`; worktree remained clean after verification.
- **Remote / verify state**: no push / no PR; independent `sdd-verify` remains pending for this integrated candidate.

## Materialized Branch Ledger

| Slice | Base | Local branch | Commit | Review size | Remote / PR state |
|---|---|---|---|---|---|
| Tracker | `main` | `feat/point-in-time-market-context` | `70f4be0` | N/A | Local only; no push / no PR |
| Domain / JSON | tracker | `feat/pit-market-context-domain` | `dd444b8` | 593 | Local only; no push / no PR |
| Replay integration | domain child | `feat/pit-market-context-replay` | `6bdd9bb` | 327 | Local only; no push / no PR |
| CLI / boundaries | replay child | `feat/pit-market-context-cli` | `1a39a4f` | 782 | Local only; current branch; no push / no PR |

## Chained Review Slice Handoff

| Slice | Planned PR boundary | Focused test command and exact result | Runtime harness command/scenario and exact result | Rollback boundary |
|---|---|---|---|---|
| Domain / JSON | Child PR 1; base = tracker `feat/point-in-time-market-context` @ `70f4be0`; local child = `feat/pit-market-context-domain` @ `dd444b8`; review size 593; scope = immutable `MarketContext`, JSON adapter, fixture, and tests | `uv run --extra dev pytest tests/domain/test_market_context.py tests/adapters/test_backtest_context_json.py` → 12 passed in 0.15s | `N/A` — pure domain/file-decoder boundary; no runtime surface beyond focused tests | Remove `src/invest/domain/market_context.py`, `src/invest/adapters/backtest_context_json.py`, `fixtures/backtest/market-context.json`, `tests/domain/test_market_context.py`, and `tests/adapters/test_backtest_context_json.py` |
| Replay integration | Child PR 2; base = `feat/pit-market-context-domain` @ `dd444b8`; local child = `feat/pit-market-context-replay` @ `6bdd9bb`; review size 327; scope = replay sequencing, coverage enforcement, and `context_outcomes` | `uv run --extra dev pytest tests/application/test_backtest_run.py` → 20 passed in 0.06s | `N/A` — replay behavior is directly exercised through focused application tests | Revert `src/invest/application/backtest_run.py`, `src/invest/domain/models.py`, and PIT additions in `tests/application/test_backtest_run.py` while retaining Domain / JSON |
| CLI / boundaries | Child PR 3; base = `feat/pit-market-context-replay` @ `6bdd9bb`; local child = `feat/pit-market-context-cli` @ `1a39a4f` (current branch); review size 782; scope = required CLI context, PIT reporting, and backtest-only regressions | `uv run --extra dev pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py tests/application/test_execute_run.py tests/adapters/test_cli_execute.py tests/adapters/test_alpaca_broker.py` → 67 passed in 0.34s | `uv run --extra dev invest-backtest --universe fixtures/backtest/universe.json --bars fixtures/backtest/bars.json --market-context fixtures/backtest/market-context.json --split-date 2024-01-23 --format json` → exit 0; one report with PIT disclaimer key, no legacy static-universe disclaimer keys, empty `context_outcomes`, and zero broker construction | Atomic rollback: revert Units 3 and 2 together, including CLI/reporting, replay wiring, and their tests, while retaining the Unit 1 domain/JSON seam. Never retain replay wiring that requires `MarketContext` without the runnable CLI context loader. |

## Work Unit Evidence

| Unit | Focused test command and exact result | Runtime harness command/scenario and exact result | Rollback boundary |
|---|---|---|---|
| 1 | `uv run --extra dev pytest tests/domain/test_market_context.py tests/adapters/test_backtest_context_json.py` → 12 passed in 0.15s | `N/A` — pure domain/file-decoder boundary; no runtime surface beyond focused tests | Remove `src/invest/domain/market_context.py`, `src/invest/adapters/backtest_context_json.py`, `fixtures/backtest/market-context.json`, `tests/domain/test_market_context.py`, and `tests/adapters/test_backtest_context_json.py` |
| 2 | `uv run --extra dev pytest tests/application/test_backtest_run.py` → 20 passed in 0.06s | `N/A` — replay behavior is directly exercised through focused application tests | Revert `src/invest/application/backtest_run.py`, `src/invest/domain/models.py`, and PIT additions in `tests/application/test_backtest_run.py` |
| 3 | `uv run --extra dev pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py tests/application/test_execute_run.py tests/adapters/test_cli_execute.py tests/adapters/test_alpaca_broker.py` → 67 passed in 0.34s | `uv run --extra dev invest-backtest --universe fixtures/backtest/universe.json --bars fixtures/backtest/bars.json --market-context fixtures/backtest/market-context.json --split-date 2024-01-23 --format json` → exit 0; one report with PIT disclaimer key, no legacy static-universe disclaimer keys, empty `context_outcomes`, and zero broker construction | Atomic rollback: revert Units 3 and 2 together, including CLI/reporting, replay wiring, and their tests, while retaining the Unit 1 domain/JSON seam. Never retain replay wiring that requires `MarketContext` without the runnable CLI context loader. |

## Deviations from Design

None — implementation matches design.

## Issues Found

- The previous artifact snapshot stopped at local chain materialization and omitted the clean integrated candidate plus approved lineage identities; this sync records both without changing implementation files.
- The initial frozen `MarketContext` exposed a mutable dictionary; chain materialization wrapped it in `MappingProxyType` and added a regression test.
- The initial PIT report retained a legacy fixed-screen survivorship warning; chain materialization now replaces both legacy static-universe disclaimer keys with the PIT statement.

## Remaining Tasks

None.

## Workload / PR Boundary

- **Mode**: local feature-branch chain (`feature-branch-chain`)
- **Current work unit**: artifact synchronization only; implementation already exists as three local work-unit commits plus the clean integrated candidate
- **Boundary**: tracker `feat/point-in-time-market-context` @ `70f4be0` → domain child `dd444b8` → replay child `6bdd9bb` → CLI child `1a39a4f` → integrated candidate `feat/point-in-time-market-context-integrated` @ `3141020a08170c589d8847892d5f5a9cfdb2776b`
- **Review status**: slice reviews = 593 / 327 / 782; integrated tracker→CLI diff = 1,702 changed lines; the CLI slice still exceeds the 400-line target by 382
- **Chain state**: source review chain retained for evidence; integrated branch `feat/point-in-time-market-context-integrated`; no pushes or PRs

## Status

12/12 tasks complete. Local chain state, TDD evidence, and integrated candidate verification metadata are synchronized; independent `sdd-verify` remains pending.
