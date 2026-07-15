# Apply Progress: Sharadar SEP Market Data Adapter

## PR 1 — Backtest-only SEP Reader

**Status**: completed
**Delivery strategy**: `ask-on-risk` resolved to `feature-branch-chain`
**PR boundary**: reader and mocked reader tests only. PR 2 CLI, boundary, ignore, persistence, context-generation, and all live execution/broker/scanner paths remain out of scope.

### Completed Tasks

- [x] 1.1 Add the initial failing one-page adjusted SEP range case.
- [x] 1.2 Create the injected-client SEP reader with Pydantic column mapping and Decimal adjustment.
- [x] 1.3 Add MockTransport cursor, bound, empty-response, missing-symbol, deterministic-order cases.
- [x] 1.4 Implement bounded cursor pagination with fail-closed validation and symbol coverage.
- [x] 1.5 Add missing-key, auth, 429, and 5xx retry cases.
- [x] 1.6 Reuse `MarketDataFetchError`, implement request-only key lookup/retries, then format with reader tests green.

### TDD Cycle Evidence

| Task | Test file | Layer | Safety net | RED | GREEN | Triangulate | Refactor |
|---|---|---|---|---|---|---|---|
| 1.1 | `tests/adapters/test_sharadar_market_data.py` | Adapter integration (`httpx.MockTransport`) | N/A (new files) | `ModuleNotFoundError`; 1 failed | 1 passed | One-page, two symbols/dates, adjusted and identity factors | Included in final formatter run |
| 1.2 | `tests/adapters/test_sharadar_market_data.py` | Adapter integration | N/A (new files) | Same initial import failure | 1 passed | `fetch_range` mapping, exact Decimal outputs, deterministic sort | Included in final formatter run |
| 1.3 | `tests/adapters/test_sharadar_market_data.py` | Adapter integration | N/A (new files) | Cursor merge: expected two requests, received one; page bound: raised `AssertionError`; empty populated-columns response did not raise | 6 passed | Cursor merge/bound, two empty variants, missing symbol, sorted first-page result | Included in final formatter run |
| 1.4 | `tests/adapters/test_sharadar_market_data.py` | Adapter integration | N/A (new files) | Same 1.3 fail-closed scenarios | 6 passed | Multi-page merge and no-partial-return conditions | Included in final formatter run |
| 1.5 | `tests/adapters/test_sharadar_market_data.py` | Adapter integration | N/A (new files) | Missing key raised `KeyError`; empty key sent a request; 401/403 were `network-failure`; retry tests made one request | 12 passed | Missing/empty key; both auth statuses; 429 with `Retry-After`; 503 exponential backoff | Included in final formatter run |
| 1.6 | `tests/adapters/test_sharadar_market_data.py` | Adapter integration | N/A (new files) | Same 1.5 taxonomy failures | 12 passed | Bounded three-attempt retry and injected no-op sleep outputs | `ruff format`, then `ruff check` and tests green |

### Work Unit Evidence

| Evidence | Result |
|---|---|
| Focused test command | `uv run pytest tests/adapters/test_sharadar_market_data.py -q` → exit 0, **12 passed** |
| Static quality command | `uv run ruff check src/invest/adapters/sharadar_market_data.py tests/adapters/test_sharadar_market_data.py` → exit 0, **All checks passed!** |
| Runtime harness | MockTransport cursor/retry/validation scenarios run through injected `httpx.Client` → exit 0, **12 passed** |
| Live SEP smoke | N/A — explicitly credential-gated and out of scope; no environment file or credential was read or printed |
| Rollback boundary | Remove `src/invest/adapters/sharadar_market_data.py` and `tests/adapters/test_sharadar_market_data.py`; no existing application, CLI, execution, broker, scanner, persistence, or context-generation behavior changes |

### Files Changed

- `src/invest/adapters/sharadar_market_data.py` — new SEP-only reader.
- `tests/adapters/test_sharadar_market_data.py` — mocked behavioral coverage.
- `openspec/changes/sharadar-sep-adapter/tasks.md` — PR 1 task completion and resolved chain decision.
- `pyproject.toml` — add the `exchange-calendars` dependency.
- `uv.lock` — lock `exchange-calendars` and its resolved transitive dependencies.

### Next Steps

PR 1 is ready for the parent-owned review/lifecycle gate. PR 2 remains pending: tasks 2.1–2.4 and phase-3 verification.

## PR 2 — Explicit Backtest Source Selection and Boundaries (2026-07-15)

**Status**: completed; Phase 3 verification is recorded complete in `tasks.md`.
**Delivery strategy**: parent-authorized `auto-forecast` / `feature-branch-chain`
**PR boundary**: CLI source dispatch, its focused CLI and AST boundary tests, and `.gitignore` protections only. No reader changes, live calls, persistence, TICKERS/ACTIONS, context generation, broker/execution/scanner behavior, sync, archive, commit, push, or PR action.
**Forecast**: `git diff --numstat` reports 307 additions and 33 deletions (340 changed lines), below the 400-line PR-2 budget.

### Completed Tasks and Persisted Checkboxes

- [x] 2.1 — `tests/adapters/test_cli_backtest.py` now proves explicit `--source sharadar` dispatches `fetch_range`, default fixture and Alpaca routes are byte-identical to their explicit sources, and invalid source prints `{"reason":"source-invalid"}` with exit 2 before reader construction.
- [x] 2.2 — `src/invest/adapters/cli.py` adds `BACKTEST_SOURCES`, an additive no-choices `--source`, default-preserving inference, fail-closed validation, and a lazy Sharadar import limited to the explicit backtest route.
- [x] 2.3 — `tests/test_boundaries.py` checks source is parser-only for backtest, the lazy import is structurally confined to `backtest_main`, execution/broker/scanner files do not reference the reader, and `git check-ignore` protects the intended paths.
- [x] 2.4 — `.gitignore` protects `fixtures/snapshots/sharadar/` and `*.sqlite`.

The authoritative filesystem tasks artifact and the `sdd/sharadar-sep-adapter/tasks` Engram observation were updated to mark 2.1–2.4 `[x]`.

### TDD Cycle Evidence

| Task | Test file | Layer | Safety net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 2.1 | `tests/adapters/test_cli_backtest.py` | CLI integration with fake reader module | `uv run pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py -q` → 37 passed | Explicit Sharadar source failed: argparse rejected `--source`; invalid source then failed by constructing the context reader | Explicit dispatch and invalid-source tests passed; 4 selected source tests passed | Fixture-default and Alpaca-default output parity both passed | Typed fake `ModuleType` seam; focused suite stayed green |
| 2.2 | `tests/adapters/test_cli_backtest.py` | CLI integration | Same 37-pass baseline | Source acceptance and dispatch requirements expressed by 2.1 tests | Added additive parser flag, inference, validated dispatch, and lazy import; 4 selected tests passed | Explicit fixture and Alpaca outputs matched omitted-source outputs | Ruff formatting, then focused tests green |
| 2.3 | `tests/test_boundaries.py` | Structural/CLI boundary | Same 37-pass baseline | `git check-ignore` returned no protected paths (1 failed) | Added AST/parser and ignore assertions; 1 selected test passed after ignore rules | Separate structural test confirmed exactly one reader import under `backtest_main` and no protected-path references (2 passed) | Ruff formatting, then focused tests green |
| 2.4 | `.gitignore`, `tests/test_boundaries.py` | Repository boundary | Same 37-pass baseline | The 2.3 ignore assertion was RED | Added two ignore rules; selected boundary test passed | Both protected path forms were observed by `git check-ignore` | No behavior refactor beyond formatting |

### Verification Evidence

- `uv run pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py -q` → exit 0, 43 passed.
- `uv run pytest tests/adapters/test_sharadar_market_data.py tests/adapters/test_cli_backtest.py tests/test_boundaries.py -q` → exit 0, 66 passed.
- `uv run ruff check src/invest/adapters/cli.py tests/adapters/test_cli_backtest.py tests/test_boundaries.py` → exit 0, All checks passed.
- `uv run ruff format --check src/invest/adapters/cli.py tests/adapters/test_cli_backtest.py tests/test_boundaries.py` → exit 0, 3 files already formatted.
- `printf 'fixtures/snapshots/sharadar/bars.json\\nbacktest.sqlite\\n' | git check-ignore --stdin` → both paths emitted.
- `git diff --check` → exit 0.

### Files Changed

- `.gitignore`
- `src/invest/adapters/cli.py`
- `tests/adapters/test_cli_backtest.py`
- `tests/test_boundaries.py`
- `openspec/changes/sharadar-sep-adapter/tasks.md`
- `openspec/changes/sharadar-sep-adapter/apply-progress.md`

### Deviations and Scope Controls

- No design deviation. `SharadarMarketDataReader` is locally imported only after source validation and only for explicit `--source sharadar`; default fixture/Alpaca inference is retained.
- No live key was read, printed, or used; no live call was made.
- No reader implementation, persistence, TICKERS/ACTIONS, context generator, broker/execution/scanner behavior, or domain model was changed.
- The formatter updated pre-existing layout in the three touched Python files; the net PR-2 slice remains below 400 changed lines.

### Phase 3 Verification Status

Phase 3 tasks 3.1–3.3 are complete in the authoritative `tasks.md`; its Phase 3 evidence records the combined suite, credential-gated smoke skip, and scope audit.

### Structured Status Consumed

```yaml
changeName: sharadar-sep-adapter
nativeArtifactStore: openspec
preflightArtifactStore: both
applyState: ready
dependencies:
  apply: ready
  verify: blocked
  archive: blocked
actionContext:
  mode: repo-local
  workspaceRoot: /Users/rcty/invest
  allowedEditRoots:
    - /Users/rcty/invest
warnings: []
nextRecommendedAtStart: apply
```

The native status was authoritative because `openspec/` exists. The parent preflight selected the hybrid (`both`) artifact backend, so the task state is also synchronized to Engram. All edits are inside the allowed workspace root.
