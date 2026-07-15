# Proposal: Sharadar Reference Data Adapters

## Intent

Backtests need point-in-time security metadata and corporate-action history alongside Sharadar SEP bars without leaking Sharadar-specific vocabulary into later domain logic. Add backtest-only `SharadarTickersReader` and `SharadarActionsReader` sibling adapters for SHARADAR/TICKERS and SHARADAR/ACTIONS, establishing the reference-data seam while deferring liquidity screening and market-context generation.

## Scope

### In Scope
- `SharadarTickersReader` in `src/invest/adapters/sharadar_tickers.py`: fetch SHARADAR/TICKERS through cursor pagination with an injected `httpx.Client`, reuse `MarketDataFetchError`, and mirror the SEP reader's retry taxonomy (401/403 no-retry; 429/5xx bounded backoff).
- Adapter-side translation of raw Sharadar `category` and `exchange` values into plain reference-data flags: `is_primary_common_stock`, `is_listed`, `listed_date`, and `delisted_date`.
- `SharadarActionsReader` in `src/invest/adapters/sharadar_actions.py`: fetch SHARADAR/ACTIONS split, dividend, delisting, and ticker-change rows as typed events with `Decimal` monetary or ratio values; do not adjust OHLC data.
- Mocked-httpx tests for both readers covering pagination, validation, retry behavior, and failure taxonomy; no live API calls.
- Explicit isolation checks in `tests/test_boundaries.py` for both new reader class names because the existing guard is hardcoded to `SharadarMarketDataReader`.

### Out of Scope
- Liquidity-screen domain module.
- Market-context window builder.
- JSON writer or CLI generator.
- Any change to `market_context.py`, `backtest_run.py`, `backtest_context_json.py`, or the SEP reader.
- Execution paths or any live-trading use; Sharadar remains backtest-only.

## Proposal Question Round

The exploration's first-change scope and seams are authoritative. Recorded assumptions: both readers use `NASDAQ_DATA_LINK_API_KEY`, the key is never logged, tests use mocked `httpx` only, raw Sharadar classification vocabulary is translated inside the TICKERS adapter, ACTIONS values remain `Decimal`, and all context-generation behavior is deferred.

## Capabilities

### New Capabilities
- `sharadar-tickers-reference-data`: cursor-paginated, fail-closed TICKERS retrieval that exposes plain listing and primary-common-stock facts without Sharadar vocabulary escaping the adapter.
- `sharadar-actions-reference-data`: cursor-paginated, fail-closed ACTIONS retrieval as typed split, dividend, delisting, and ticker-change events with `Decimal` values and no price adjustment.

### Modified Capabilities
- `trading-system`: backtest-only isolation coverage is extended to `SharadarTickersReader` and `SharadarActionsReader`; production execution paths and runtime behavior remain unchanged.

## Approach

Mirror `sharadar_market_data.py` in two sibling modules: injected `httpx.Client`, Nasdaq datatables `datatable.columns`/`data` parsing, `meta.next_cursor_id` cursor pagination, bounded page loops, environment-based authentication, Pydantic validation, and the existing retry/backoff taxonomy with `MarketDataFetchError`. Keep table-specific row models and translation local to each adapter. TICKERS converts provider categories and exchanges to plain flags and dates; ACTIONS emits typed events using `Decimal` for numeric values and never adjusts SEP OHLC. Preserve the SEP reader unchanged rather than extracting shared plumbing in this change. Implement under strict TDD with mocked HTTP only.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `src/invest/adapters/sharadar_tickers.py` | New | TICKERS reader, pagination, validation, and provider-vocabulary translation |
| `src/invest/adapters/sharadar_actions.py` | New | ACTIONS reader and typed split/dividend/delisting/ticker-change events |
| `tests/adapters/test_sharadar_tickers.py` | New | Mocked-httpx pagination, translation, validation, and retry coverage |
| `tests/adapters/test_sharadar_actions.py` | New | Mocked-httpx event parsing, Decimal, pagination, validation, and retry coverage |
| `tests/test_boundaries.py` | Modified | Explicit backtest-only isolation checks for both new reader class names |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| ~600–850 authored lines exceeds the 400-line review budget | High | Flag chained-PR planning in `sdd-tasks`, with reader/test slices kept reviewable |
| Live TICKERS/ACTIONS pagination cardinality is unverified | Med | Bound pagination and test cursor continuation and exhaustion deterministically |
| Sharadar category/exchange or action vocabulary is broader than fixtures | Med | Centralize explicit adapter mappings and fail closed on unsupported or malformed rows |
| Existing isolation guard misses new class names | High | Add dedicated boundary assertions for `SharadarTickersReader` and `SharadarActionsReader` |

## Rollback Plan

Revert the two new adapter modules, their mocked-httpx tests, and the two explicit boundary checks. No existing reader, domain model, CLI, execution path, persisted data, or migration is changed, so rollback restores the prior behavior directly.

## Dependencies

- Nasdaq Data Link API key in `NASDAQ_DATA_LINK_API_KEY`; it is read only when building requests and is never logged.
- Existing `MarketDataFetchError` from `alpaca_market_data.py` and the retry/pagination pattern in `sharadar_market_data.py`.
- Nasdaq Data Link SHARADAR/TICKERS and SHARADAR/ACTIONS datatable schemas.

## Success Criteria

- [ ] `SharadarTickersReader` follows every `meta.next_cursor_id`, enforces a bounded page loop, and returns validated reference records from mocked TICKERS responses.
- [ ] TICKERS category/exchange values are translated adapter-side into `is_primary_common_stock`, `is_listed`, `listed_date`, and `delisted_date`; raw Sharadar vocabulary does not enter domain modules.
- [ ] `SharadarActionsReader` returns typed split, dividend, delisting, and ticker-change events with `Decimal` values and performs no OHLC adjustment.
- [ ] Both readers use injected `httpx.Client`, `NASDAQ_DATA_LINK_API_KEY`, and the SEP reader's retry taxonomy while reusing `MarketDataFetchError`; the API key is never logged.
- [ ] Mocked-httpx tests cover pagination, validation, retries, and terminal failures for both readers with no live network calls.
- [ ] Boundary tests explicitly prove both new reader classes remain isolated from execution paths and backtest-only.
- [ ] No changes are made to the liquidity screen, market-context builder, JSON writer, CLI generator, `market_context.py`, `backtest_run.py`, `backtest_context_json.py`, or the SEP reader.
