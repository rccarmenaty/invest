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
