# Sharadar SEP Market Data Specification

## Purpose

Backtest-only reader for SHARADAR/SEP daily bars from Nasdaq Data Link, returning point-in-time, split/dividend-adjusted `FixtureInputs` for replay. Never used by any live or execution path.

## Requirements

### Requirement: SEP bar fetch with bounded cursor pagination

The system MUST expose `fetch(universe, as_of)` and `fetch_range(universe, start, end)` against the SHARADAR/SEP datatable only, returning `FixtureInputs`. Pagination MUST follow `meta.next_cursor_id` in pages of up to 10,000 rows and MUST stop at a bounded page limit.

#### Scenario: Range fetch returns bars for the full universe and range

- GIVEN a universe and a date range
- WHEN `fetch_range` completes successfully
- THEN it MUST return `FixtureInputs` covering every symbol and trading day requested

#### Scenario: Unbounded pagination is refused

- GIVEN a response that keeps returning a non-null `next_cursor_id` beyond the bounded page limit
- WHEN the reader paginates
- THEN it MUST fail with reason `malformed-response` and return no partial bars

### Requirement: Deterministic OHLC adjustment

Per-bar open/high/low MUST be adjusted using factor `closeadj/close`, computed and applied with exact Decimal arithmetic before constructing `DailyBar`. `DailyBar`'s shape MUST remain unchanged.

#### Scenario: Adjustment factor scales open/high/low

- GIVEN a raw SEP bar with `close`, `closeadj`, `open`, `high`, `low`
- WHEN the reader builds the `DailyBar`
- THEN open/high/low MUST equal the raw value times `closeadj/close`, computed with Decimal precision

#### Scenario: Unadjusted bar is unchanged

- GIVEN a bar where `closeadj` equals `close`
- WHEN the adjustment is applied
- THEN open/high/low MUST equal their raw input values exactly

### Requirement: Fail-closed credential and response validation

A missing or empty `NASDAQ_DATA_LINK_API_KEY` MUST fail before any request is sent. An empty or schema-invalid API response MUST fail before any bar is returned.

#### Scenario: Missing API key fails closed

- GIVEN `NASDAQ_DATA_LINK_API_KEY` is unset or empty
- WHEN a fetch is attempted
- THEN it MUST fail with reason `auth-failure` and issue no HTTP request

#### Scenario: Malformed response fails closed

- GIVEN an empty or schema-invalid SEP response body
- WHEN validation runs
- THEN it MUST fail with reason `malformed-response` and return no partial bars

### Requirement: Fail-closed on missing universe symbols

Any universe symbol absent from the fetched SEP data MUST abort the fetch before returning `FixtureInputs`, naming the missing symbols, mirroring the existing snapshot symbol-missing guard.

#### Scenario: Missing symbol aborts the fetch

- GIVEN a universe where one or more symbols have no SEP rows in range
- WHEN `fetch`/`fetch_range` completes
- THEN it MUST fail with reason `symbol-missing-at-fetch` naming the missing symbols
- AND no partial `FixtureInputs` MUST be returned

### Requirement: Auth and retry error taxonomy

401/403 responses MUST NOT be retried. 429 and 5xx responses MUST be retried with bounded exponential backoff honoring `Retry-After`, then fail if the bound is exhausted.

#### Scenario: Authentication failure is not retried

- GIVEN the API returns 401 or 403
- WHEN the reader handles the response
- THEN it MUST fail immediately with reason `auth-failure` and make no retry attempt

#### Scenario: Rate limit and server errors retry within a bound

- GIVEN the API returns 429 or a 5xx status
- WHEN the reader retries
- THEN it MUST use bounded exponential backoff honoring `Retry-After`
- AND it MUST fail with reason `rate-limited` or `network-failure` once the bound is exhausted

### Requirement: Deterministic, clock-free output

Given the same universe, date range, and SEP responses, repeated fetches MUST return identical, symbol-and-date-sorted bars. The reader and any adjustment logic MUST NOT read the wall clock.

#### Scenario: Repeated fetch is byte-identical

- GIVEN the same universe, range, and mocked SEP responses
- WHEN `fetch_range` runs twice
- THEN both runs MUST return identically ordered, identical `FixtureInputs`

### Requirement: Backtest-only adapter boundary

`SharadarMarketDataReader` MUST NOT be imported or invoked from any execution, broker, or scanner code path.

#### Scenario: Boundary test rejects broker/execution use

- GIVEN the source tree
- WHEN boundary tests run
- THEN no execution, broker, or scanner module MUST import `SharadarMarketDataReader`
