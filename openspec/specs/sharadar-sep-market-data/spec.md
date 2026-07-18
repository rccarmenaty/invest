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

Per-bar open/high/low MUST be computed as the raw value times factor `closeadj/close` with exact Decimal arithmetic, then minimally re-enveloped before constructing `DailyBar`: high MUST become `max(high, open, close, low)` and low MUST become `min(low, open, close, high)`, so every adjusted bar satisfies `low <= min(open, close)` and `high >= max(open, close)`. The re-envelope MUST NOT alter open or close, and adjusted values MUST deviate from the exact Decimal products only when the exact products themselves violate the OHLC envelope (Decimal rounding/ULP drift, e.g. raw `high == close` combined with a fractional `closeadj/close` ratio). The adjustment MUST remain deterministic, and `DailyBar`'s shape MUST remain unchanged.

#### Scenario: Adjustment factor scales open/high/low

- GIVEN a raw SEP bar with `close`, `closeadj`, `open`, `high`, `low` whose exact Decimal products already satisfy the OHLC envelope
- WHEN the reader builds the `DailyBar`
- THEN open/high/low MUST equal the raw value times `closeadj/close` exactly, computed with Decimal precision, with no re-envelope deviation

#### Scenario: Unadjusted bar is unchanged

- GIVEN a bar where `closeadj` equals `close`
- WHEN the adjustment is applied
- THEN open/high/low MUST equal their raw input values exactly

#### Scenario: Envelope drift clamps adjusted high minimally

- GIVEN the live GSBD 2024-12-13 bar shape where raw `high` equals raw `close` (open `12.83`, high `12.87`, low `12.75`, close `12.87`, closeadj `9.711`) and the exact Decimal product for high falls below `closeadj` by rounding drift
- WHEN the reader builds the `DailyBar`
- THEN adjusted high MUST equal the maximum of the four adjusted candidates — exactly `closeadj` here — and not any wider value
- AND adjusted open and low MUST remain their exact Decimal products

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

### Requirement: Fractional SEP volume preservation

The reader MUST preserve non-negative SEP volume as canonical `Decimal` in `DailyBar.volume` without rounding, truncation, or quantization. Negative volume MUST fail closed. OHLC, adjustments, pagination, and unrelated reconciliation MUST remain unchanged.

#### Scenario: Preserve valid fractional volume

- GIVEN an SEP row whose adjusted volume is `48037.936`
- WHEN the reader constructs its `DailyBar`
- THEN `DailyBar.volume` MUST equal `Decimal("48037.936")` exactly

#### Scenario: Reject negative volume

- GIVEN an SEP row whose volume is negative
- WHEN response validation runs
- THEN the fetch MUST fail with reason `malformed-response`
- AND no partial bars MUST be returned

#### Scenario: Preserve unrelated SEP behavior

- GIVEN otherwise identical SEP rows
- WHEN the changed reader produces bars
- THEN OHLC, adjustments, and ordering MUST remain unchanged
