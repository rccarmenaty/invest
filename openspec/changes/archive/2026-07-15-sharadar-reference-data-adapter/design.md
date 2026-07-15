# Design: Sharadar Reference Data Adapters

## Summary

Implement two independent, backtest-only adapter modules at the reference-data seam:

- `SharadarTickersReader.fetch() -> tuple[SharadarTicker, ...]`
- `SharadarActionsReader.fetch() -> tuple[SharadarAction, ...]`

Each is a deep module: callers learn one no-argument fetch operation and receive immutable, provider-neutral facts/events; request construction, credentials, cursor pagination, retries, envelope validation, provider translation, and deterministic ordering remain internal. They deliberately duplicate the established SEP transport pattern. Extracting shared pagination/retry plumbing or altering `SharadarMarketDataReader` is deferred.

No CLI route, generator, liquidity screen, market-context logic, domain model, SEP behavior, execution path, or live/paper path is added or changed.

## Public typed contracts

Both constructors accept a caller-supplied `httpx.Client` at construction and an injectable `sleep` callable (defaulting to `time.sleep`); they do not construct transport during a fetch. `fetch()` has no arguments and returns an immutable tuple only after every page has validated.

```python
@dataclass(frozen=True)
class SharadarTicker:
    ticker: str
    is_primary_common_stock: bool
    is_listed: bool
    listed_date: date | None
    delisted_date: date | None

class SharadarActionKind(StrEnum):
    SPLIT = "split"
    DIVIDEND = "dividend"
    DELISTING = "delisting"
    TICKER_CHANGE = "ticker-change"

@dataclass(frozen=True)
class SharadarAction:
    ticker: str
    effective_date: date
    kind: SharadarActionKind
    value: Decimal | None
```

`SharadarTicker` exposes no raw `category` or `exchange`. `SharadarAction` exposes a closed event kind rather than the provider's arbitrary action string. `Decimal` values are never converted through `float`. `MarketDataFetchError` remains the sole retrieval failure type, with reasons `auth-failure`, `rate-limited`, `network-failure`, and `malformed-response` as applicable.

## Data flow and validation

For either reader:

1. Build the SHARADAR datatables request with its fixed `qopts.columns`; read `NASDAQ_DATA_LINK_API_KEY` only while building that request and append it as the provider authentication parameter. Missing or empty key raises `MarketDataFetchError("auth-failure")` before `client.send`; neither logs nor returns the key.
2. Send the request through the injected client using bounded retry. Validate JSON into the local datatable envelope (`columns`, `data`, `meta.next_cursor_id`), require a nonempty table and all required columns, then validate every row with a table-local strict Pydantic model.
3. Translate a fully valid page to local public records/events, append it only to the in-memory aggregate, and follow its nonempty continuation cursor. A null cursor finalizes the aggregate by sorting and returning a tuple. A malformed page at any point raises and returns no aggregate.
4. A continuation after `MAX_PAGES` (512) is `malformed-response`; page loops never return partial data. Null/empty/malformed cursors and rows shorter than the declared column list are malformed.

TICKERS requests `ticker,exchange,category,firstpricedate,lastpricedate,isdelisted`. `is_listed` is the inverse of the validated provider delisted flag. A currently listed record has `delisted_date=None`; a delisted record carries `lastpricedate` when supplied. `listed_date` maps `firstpricedate` when supplied.

Classification is a closed adapter-local mapping: only the recognized domestic-primary/common categories (`Domestic Common Stock`, `Domestic Common Stock Primary Class`) on recognized US listing exchanges (`AMEX`, `ARCA`, `NASDAQ`, `NYSE`) produce `is_primary_common_stock=True`. A recognized non-primary or any unrecognized category/exchange is `False`, never guessed or exposed. Missing/empty classification fields are malformed. This is deliberately conservative, while preserving the specification's rule that unknown classifications are non-primary rather than silently promoted.

ACTIONS requests `ticker,date,action,value`. It maps exactly these provider literals, without case folding: `split`, `dividend`, `delisting`, and `tickerchange` to the four `SharadarActionKind` members above. Any other action is `malformed-response`. A present value must parse as a finite `Decimal`; split ratios must be positive. An absent value remains `None`; this permits the provider's valueless delisting/ticker-change events and does not invent a value. The adapter neither receives nor imports SEP bars and performs no OHLC adjustment or mutation.

## Determinism and retry policy

Both readers use the SEP constants: `MAX_ATTEMPTS=3`, exponential fallback sleeps of `0.5`, `1.0` seconds (capped at `4.0`), and `MAX_PAGES=512`. Status 401/403 is immediate `auth-failure` with one request. Status 429 retries through the bound then raises `rate-limited`; 5xx and `httpx.RequestError` retry through the bound then raise `network-failure`. Other error statuses are immediate `network-failure`.

A valid finite numeric `Retry-After` is clamped to `[0, BACKOFF_CAP_SECONDS]` and used for that retry; malformed, HTTP-date, `NaN`, and infinite values use the deterministic exponential fallback. Sleep is never called after the final failed attempt.

Final TICKERS ordering is `(ticker,)`. Final ACTIONS ordering is `(ticker, effective_date, kind.value)`; ties are additionally ordered by a stable `value` representation so page order cannot affect results. Validation and aggregation happen before sort, so no transport ordering leaks through the interface.

## Reconciliation of the interrupted preliminary implementation

The existing uncommitted modules/tests are useful scaffolding but are not yet specification-complete. The implementation phase must retain their approved architecture while reconciling these gaps through tests-first changes:

| Area | Preliminary state | Required reconciliation |
|---|---|---|
| Transport seam | `client` is optional and a reader can construct `httpx.Client`. | Require the caller-supplied client; preserve injected sleep and no live test transport. |
| TICKERS contract | Record shape and conservative category/exchange mapping are present. | Keep the plain facts, make cursor validation explicit, and add missing-column, empty-table, short/invalid-row, page-bound, no-partial, unknown-classification, and non-finite retry-delay coverage. |
| ACTIONS contract | `SharadarAction.action: str` passes raw action through; no kind validation; field is `date`. | Replace with `effective_date` plus closed `SharadarActionKind`; map `tickerchange` to `ticker-change`, add `delisting`, and reject unsupported kinds/non-finite or invalid values. |
| Pagination | Both modules sort and follow normal two-page fixtures. | Add bound-exhaustion and malformed second-page/no-partial tests; reject invalid cursor metadata instead of relying on eventual looping. |
| Retry | Normal status taxonomy and basic success/exhaustion tests exist. | Characterize all three retry sources, exact attempts/sleeps, valid/invalid `Retry-After`, and final-attempt behavior consistently in both readers. |
| Isolation | The new name check covers five broker/execution/scanner files only. | Expand an explicit parametrized AST guard to CLI, broker/execution/scanner, live/paper-reachable paths, and protected `market_context.py`, `backtest_run.py`, and `backtest_context_json.py`; assert neither reader is selected or referenced there. |

Do not "fix" this by wiring either reader into `backtest_main`: that would violate the approved no-CLI/no-context-generation scope. Do not modify the SEP reader merely to deduplicate this implementation.

## Files and tests

| File | Change |
|---|---|
| `src/invest/adapters/sharadar_tickers.py` | Reconcile the typed ticker contract, strict envelope/row/cursor validation, conservative classification mapping, pagination, and retry behavior. |
| `src/invest/adapters/sharadar_actions.py` | Reconcile the closed typed-event contract and event mapping with equivalent retrieval safeguards; no bar imports or adjustment logic. |
| `tests/adapters/test_sharadar_tickers.py` | Mocked-`httpx` contract tests for request/auth, deterministic cursor/sort, mapping, malformed/no-partial cases, pagination bound, and retry matrix. |
| `tests/adapters/test_sharadar_actions.py` | Equivalent transport tests plus all four event kinds, exact Decimal/None behavior, unsupported-kind/value rejection, and a supplied-bar non-mutation regression check. |
| `tests/test_boundaries.py` | Explicit AST isolation tests for both names/modules and protected paths; assert no CLI selection or protected-module change in behavior. |

Tests use `httpx.MockTransport` exclusively. TDD order is: write the missing contract/failure test, observe it fail against the preliminary code, make the smallest local adapter change, then run the targeted reader test file; finish each slice with `pytest tests/adapters/test_sharadar_tickers.py tests/adapters/test_sharadar_actions.py tests/test_boundaries.py` and `ruff check src tests`. Existing SEP and general suite tests remain regression gates.

## Chained PR and rollout plan

Keep every review slice at or below 600 changed lines (including tests), and make PR 2 depend on PR 1 without changing its public ticker contract:

1. **PR 1 — TICKERS reference facts (target 350–500 lines):** reconcile `sharadar_tickers.py` and its mocked transport/mapping/failure tests; introduce the generic/parametrized boundary-test helper with the ticker reader case. This establishes the reference-data seam without any consumer wiring.
2. **PR 2 — ACTIONS typed events (target 350–500 lines):** reconcile `sharadar_actions.py` and its tests, add the actions case to the already-merged boundary helper, and verify the no-price-adjustment regression. This supplies the second independent adapter only.

Before merge, run the targeted tests and the full suite in CI with no credentials and no live marker. Rollout is code availability only: operators need `NASDAQ_DATA_LINK_API_KEY` only when a future backtest-only caller elects to use a reader; this change adds no scheduled request or CLI configuration. Rollback is removal of the two modules, their tests, and the two boundary cases; no persisted data, migration, existing runtime behavior, or domain contract needs reversal.

## Scope guard

This design intentionally leaves `sharadar_market_data.py`, `market_context.py`, `backtest_run.py`, `backtest_context_json.py`, domain models, CLI parsers/scripts, liquidity screening, market-context generation, JSON writing, execution, and live/paper trading untouched. The adapters remain unselected backtest-only infrastructure for a later context-generation change.
