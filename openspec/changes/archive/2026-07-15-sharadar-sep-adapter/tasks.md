# Tasks: Sharadar SEP Market Data Adapter

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 650–900 authored lines |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 reader; PR 2 CLI, boundary, ignore rules |
| Delivery strategy | ask-on-risk (resolved) |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No (resolved: feature-branch-chain, PR 1 reader)
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Backtest-only SEP reader | PR 1 | `pytest tests/adapters/test_sharadar_market_data.py` | MockTransport cursor/retry scenarios; live smoke N/A (credential-gated) | New reader and its test file |
| 2 | Explicit backtest source selection | PR 2 | `pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py` | Parse `invest-backtest --source sharadar` with mocked reader | CLI, boundary tests, `.gitignore` entries |

## Phase 1: SEP Reader (PR 1)

- [x] 1.1 **RED:** Add a failing `tests/adapters/test_sharadar_market_data.py` case for a one-page SEP range result whose Decimal-adjusted O/H/L and `closeadj` close form sorted `FixtureInputs`.
- [x] 1.2 **GREEN:** Create `src/invest/adapters/sharadar_market_data.py` with injected HTTP client, column-name mapping, Pydantic validation, `_adjust`, and `fetch`/`fetch_range` for SEP only.
- [x] 1.3 **RED:** Add failing MockTransport cases for cursor merge, cursor beyond `MAX_PAGES`, malformed/empty columns, missing universe symbols, and repeatable sort order.
- [x] 1.4 **GREEN:** Implement bounded `meta.next_cursor_id` pagination and fail-closed `malformed-response` / `symbol-missing-at-fetch` handling with no partial return.
- [x] 1.5 **RED:** Add failing cases for absent/empty `NASDAQ_DATA_LINK_API_KEY`, 401/403 no-retry, and exhausted 429/5xx retry with `Retry-After` and no-op sleep.
- [x] 1.6 **GREEN:** Reuse `MarketDataFetchError` and implement request-only env lookup plus bounded retry taxonomy; refactor only while all reader tests are green.

## Phase 2: Backtest Wiring and Boundaries (PR 2)

- [x] 2.1 **RED:** Add failing CLI tests proving explicit `--source sharadar` calls `fetch_range`, omitted `--source` is byte-identical, and an unknown source returns machine-readable `source-invalid` / exit 2 before fetching.
- [x] 2.2 **GREEN:** Update `src/invest/adapters/cli.py` with `BACKTEST_SOURCES`, additive `--source` (no argparse choices), and default-preserving source resolution.
- [x] 2.3 **RED:** Extend `tests/test_boundaries.py` with failing AST checks that `--source` is backtest-only and no execute/broker/scanner path references the Sharadar reader; add a failing `git check-ignore` assertion for `fixtures/snapshots/sharadar/` and `*.sqlite`.
- [x] 2.4 **GREEN:** Add the two `.gitignore` protections and satisfy the boundary checks; refactor only after focused tests are green.

## Phase 3: Verification

- [x] 3.1 Ran `uv run pytest tests/adapters/test_sharadar_market_data.py tests/adapters/test_cli_backtest.py tests/test_boundaries.py` → exit 0, **66 passed in 1.06s**. This combines the PR 1 reader suite (23 tests) and PR 2 CLI/boundary suites (31 and 12 tests).
- [x] 3.2 Credential-gated live SEP smoke skipped: a presence-only shell check found `NASDAQ_DATA_LINK_API_KEY` absent. Its value was not read or printed, and no live request or smoke command was made.
- [x] 3.3 Scope audit passed: the reader contains no TICKERS/ACTIONS, persistence, or context-generator dependency; the only Sharadar reader import is lazy inside `backtest_main`; protected execution/broker/scanner modules contain no reader reference. `.gitignore` protects future snapshots but adds no persistence behavior. The merged clock-free retry fix (`a64e1e5`) has no wall-time call (`datetime.now`/`utcnow`, `date.today`, `time.time`, `monotonic`, or `perf_counter`).

### Phase 3 Evidence (2026-07-15)

| Command / check | Result |
|---|---|
| `uv run pytest tests/adapters/test_sharadar_market_data.py tests/adapters/test_cli_backtest.py tests/test_boundaries.py` | exit 0 — 66 passed in 1.06s |
| `uv run pytest` | exit 0 — 270 passed, 3 skipped in 13.53s |
| `uv run ruff check src/invest/adapters/sharadar_market_data.py src/invest/adapters/cli.py tests/adapters/test_sharadar_market_data.py tests/adapters/test_cli_backtest.py tests/test_boundaries.py` | exit 0 — All checks passed |
| `uv run ruff format --check src/invest/adapters/sharadar_market_data.py src/invest/adapters/cli.py tests/adapters/test_sharadar_market_data.py tests/adapters/test_cli_backtest.py tests/test_boundaries.py` | exit 0 — 5 files already formatted |
| `git diff --check` | exit 0 |
| Credential gate | `NASDAQ_DATA_LINK_API_KEY` absent by presence-only check; skipped without reading/printing the value or making a request |
| Wall-time AST audit | no prohibited wall-time calls in `src/invest/adapters/sharadar_market_data.py` |

Non-blocking repository-wide formatter note: `uv run ruff format --check src tests` exited 1 because 29 pre-existing, non-slice files would be reformatted; the five changed reader/CLI/test files above are formatted.
