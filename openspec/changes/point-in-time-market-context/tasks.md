# Tasks: Point-in-Time Market Context

## Review Workload Forecast

| Field | Value |
|---|---|
| Materialized review load | 1,702 changed lines across the local chain (593 + 327 + 782) |
| 800-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | Child PR 1 → Child PR 2 → Child PR 3, coordinated by a draft/no-merge tracker |
| Delivery strategy | User-selected chained PRs |
| Chain strategy | feature-branch-chain |
| Verification snapshot | source chain full suite 202 passed, 3 skipped; Ruff passed. Integrated candidate full suite 210 passed, 3 skipped; Ruff passed; runtime harness exit 0; clean tree. |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
800-line budget risk: High

The tracker branch accumulates the integrated feature and is the only branch intended to merge to main. Child PR 1 targets the tracker branch; Child PR 2 targets Child PR 1's branch; Child PR 3 targets Child PR 2's branch. Retarget or rebase any child whose diff includes prior slices. The local-only feature-branch chain is now materialized: tracker `feat/point-in-time-market-context` @ `70f4be0`; domain child `feat/pit-market-context-domain` @ `dd444b8`; replay child `feat/pit-market-context-replay` @ `6bdd9bb`; CLI child `feat/pit-market-context-cli` @ `1a39a4f` (current branch). No pushes or PRs exist.

### Materialized Local Chain

| Slice | Base | Local branch | Commit | Review size | Remote / PR state |
|---|---|---|---|---|---|
| Tracker | `main` | `feat/point-in-time-market-context` | `70f4be0` | N/A | Local only; no push / no PR |
| Domain / JSON | tracker | `feat/pit-market-context-domain` | `dd444b8` | 593 | Local only; no push / no PR |
| Replay integration | domain child | `feat/pit-market-context-replay` | `6bdd9bb` | 327 | Local only; no push / no PR |
| CLI / boundaries | replay child | `feat/pit-market-context-cli` | `1a39a4f` | 782 | Local only; current branch; no push / no PR |

### Integrated Candidate

- Integrated branch: `feat/point-in-time-market-context-integrated` @ `3141020a08170c589d8847892d5f5a9cfdb2776b`
- Cherry-picked reviewed corrections with matching patch IDs: domain `d2ca0bf3989e974ae133a2ca5ebcfca55ffc92fe`; replay `a95daafe7dd46b5b7458270d156c3f1ebcb495c5`; CLI `3141020a08170c589d8847892d5f5a9cfdb2776b`
- Source review lineages are terminal `approved`: domain chain identity `sha256:5c4a6b76c36b43c15a4a8d0f44aa146db23f44e7e05fa56a28be7795d59cf2d1`; replay chain identity `sha256:13b0eb8ee82333f68b7c1f452c0d172e9975cddc3762f4325bad86070e93cb06`; CLI chain identity `sha256:c85c2687d2e8607406b9b49e74b692f2f0869975059fa85b44e9e237982e1616`
- Integrated verification evidence: full `pytest` previously recorded as `210 passed, 3 skipped`; Ruff passed; runtime harness exit `0`; worktree clean after verification
- Remote state: no push / no PR; independent `sdd-verify` remains pending for this integrated candidate

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Immutable `MarketContext` plus JSON adapter, fixture, and tests | Child PR 1; base = tracker `feat/point-in-time-market-context` @ `70f4be0`; local child = `feat/pit-market-context-domain` @ `dd444b8`; review size 593 | `pytest tests/domain/test_market_context.py tests/adapters/test_backtest_context_json.py` | N/A: pure domain/file-decoder boundary | Remove the context domain, JSON adapter, fixture, and their tests |
| 2 | Replay integration plus context outcomes and tests | Child PR 2; base = `feat/pit-market-context-domain` @ `dd444b8`; local child = `feat/pit-market-context-replay` @ `6bdd9bb`; review size 327 | `pytest tests/application/test_backtest_run.py` | N/A: application behavior is exercised through focused replay tests | Revert `backtest_run.py`, `models.py`, and replay-test additions while retaining Unit 1 |
| 3 | CLI/reporting plus boundary safety and tests | Child PR 3; base = `feat/pit-market-context-replay` @ `6bdd9bb`; local child = `feat/pit-market-context-cli` @ `1a39a4f` (current branch); review size 782 | `pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py tests/application/test_execute_run.py tests/adapters/test_cli_execute.py tests/adapters/test_alpaca_broker.py` | `invest-backtest --universe fixtures/backtest/universe.json --bars fixtures/backtest/bars.json --market-context fixtures/backtest/market-context.json --split-date 2024-01-23 --format json` | Atomic rollback: revert Units 3 and 2 together, including CLI/reporting, replay wiring, and their tests, while retaining the Unit 1 domain/JSON seam. Never retain replay wiring that requires `MarketContext` without the runnable CLI context loader. |

## Phase 1: Context Domain and File Adapter

- [x] 1.1 RED: Create `tests/domain/test_market_context.py` for complete/missing/contradictory matrices, future-mutation immunity, inclusive blockers, and exact outcome/reason values.
- [x] 1.2 GREEN: Create `src/invest/domain/market_context.py` with immutable `status()`/`require_complete()` semantics and stable incomplete/invalid failures.
- [x] 1.3 RED: Create `tests/adapters/test_backtest_context_json.py` for unreadable, malformed, unsupported-version, overlapping, and semantically incomplete JSON.
- [x] 1.4 GREEN: Create strict `src/invest/adapters/backtest_context_json.py` and fully covered `fixtures/backtest/market-context.json`.
- [x] 1.5 REFACTOR: Keep Pydantic/file concerns out of `market_context.py`; rerun Unit 1 tests.

## Phase 2: Replay Integration

- [x] 2.1 RED: Extend `tests/application/test_backtest_run.py` for date-filtered scans, blocked entries, first-unsafe-date forced closes before exits/entries at `bar.low`, missing-D-bar abort, determinism, and all-eligible parity.
- [x] 2.2 GREEN: Update `src/invest/domain/models.py` and `src/invest/application/backtest_run.py` to require coverage, expose context outcomes, and preserve scanner, accounting, costs, and gate telemetry.
- [x] 2.3 REFACTOR: Centralize date/context sequencing without modifying scanner, provider, broker, execution, accounting, or cost modules; rerun Unit 2 tests.

## Phase 3: CLI and Boundary Safety

- [x] 3.1 RED: Extend `tests/adapters/test_cli_backtest.py` for required context, one exit-2 context error, no partial report, PIT statement replacement, outcomes, and zero broker calls.
- [x] 3.2 RED: Extend `tests/test_boundaries.py`, `tests/application/test_execute_run.py`, `tests/adapters/test_cli_execute.py`, and `tests/adapters/test_alpaca_broker.py` to preserve bars-only Alpaca, `--execute`, paper endpoint, and live gates.
- [x] 3.3 GREEN: Update `src/invest/adapters/cli.py` to load `--market-context`, map stable failures, and emit one PIT report with context outcomes.
- [x] 3.4 REFACTOR: Keep context backtest-only; run all focused commands, full `pytest`, and the Unit 3 runtime harness.
