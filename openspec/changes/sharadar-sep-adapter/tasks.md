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

- [ ] 2.1 **RED:** Add failing CLI tests proving explicit `--source sharadar` calls `fetch_range`, omitted `--source` is byte-identical, and an unknown source returns machine-readable `source-invalid` / exit 2 before fetching.
- [ ] 2.2 **GREEN:** Update `src/invest/adapters/cli.py` with `BACKTEST_SOURCES`, additive `--source` (no argparse choices), and default-preserving source resolution.
- [ ] 2.3 **RED:** Extend `tests/test_boundaries.py` with failing AST checks that `--source` is backtest-only and no execute/broker/scanner path references the Sharadar reader; add a failing `git check-ignore` assertion for `fixtures/snapshots/sharadar/` and `*.sqlite`.
- [ ] 2.4 **GREEN:** Add the two `.gitignore` protections and satisfy the boundary checks; refactor only after focused tests are green.

## Phase 3: Verification

- [ ] 3.1 Run `pytest tests/adapters/test_sharadar_market_data.py tests/adapters/test_cli_backtest.py tests/test_boundaries.py`; record focused evidence for each PR slice.
- [ ] 3.2 Run the live SEP smoke only when `NASDAQ_DATA_LINK_API_KEY` is set; otherwise record it as skipped without reading or printing the key.
- [ ] 3.3 Confirm no TICKERS/ACTIONS, snapshot persistence, context generator, or execution/scanner behavior entered this change.
