# Sharadar Tickers Reference Data Specification

## Purpose

Provide backtest-only, point-in-time listing metadata as plain reference-data facts while containing provider-specific classification vocabulary within the adapter.

## Requirements

### Requirement: TICKERS reference-data retrieval

`SharadarTickersReader` MUST retrieve records from the SHARADAR/TICKERS datatable through a caller-supplied HTTP client and MUST use `NASDAQ_DATA_LINK_API_KEY` only to authenticate requests. It MUST follow every non-null `meta.next_cursor_id`, combine all pages, and stop at a bounded page limit. It MUST return records in deterministic ticker order.

#### Scenario: Cursor pages are combined deterministically

- GIVEN two valid TICKERS response pages where the first contains a next cursor
- WHEN the reader fetches reference data through a mocked HTTP client
- THEN it MUST request the continuation cursor and return the combined records in ticker order

#### Scenario: Pagination bound is exceeded

- GIVEN valid TICKERS pages that continue beyond the page limit
- WHEN the reader fetches reference data
- THEN it MUST fail with reason `malformed-response`
- AND it MUST return no partial records

### Requirement: Plain ticker listing facts

Each returned ticker record MUST contain its ticker, `is_primary_common_stock`, `is_listed`, `listed_date`, and `delisted_date`. Classification MUST be translated inside the adapter: raw SHARADAR category and exchange values MUST NOT be exposed in the returned reference-data contract or required by domain logic. A record MUST be marked primary common stock only when its recognized provider classification represents a primary common-stock listing; unrecognized or non-primary classifications MUST NOT be marked primary common stock. A delisted record MUST report its delisting date when provided, and a currently listed record MUST NOT report a delisting date.

#### Scenario: Provider classifications become plain facts

- GIVEN valid TICKERS rows for a recognized primary common-stock listing, a delisted primary common-stock listing, and a non-primary security
- WHEN the reader translates the rows
- THEN the returned records MUST expose only the plain listing facts
- AND the primary and listing flags and listing/delisting dates MUST reflect those rows
- AND the non-primary security MUST have `is_primary_common_stock` set to false

### Requirement: Fail-closed TICKERS validation and authentication

A missing or empty `NASDAQ_DATA_LINK_API_KEY` MUST fail before any HTTP request and MUST NOT be logged. An empty, malformed, incomplete, or schema-invalid TICKERS response or row MUST fail with reason `malformed-response`; no partial records MAY be returned.

#### Scenario: Missing credential fails before transport

- GIVEN `NASDAQ_DATA_LINK_API_KEY` is unset or empty
- WHEN a TICKERS fetch is attempted
- THEN it MUST fail with reason `auth-failure`
- AND the supplied HTTP client MUST receive no request

#### Scenario: Invalid response fails closed

- GIVEN a TICKERS response with missing required columns, an empty table, or an invalid row
- WHEN the reader validates it
- THEN it MUST fail with reason `malformed-response`
- AND it MUST return no partial records

### Requirement: TICKERS retry taxonomy

TICKERS authentication responses (401 and 403) MUST fail immediately with reason `auth-failure` and MUST NOT be retried. Rate-limit responses (429), 5xx responses, and transport request failures MUST use bounded retry with exponential backoff that honors a valid `Retry-After` delay. On exhaustion, 429 MUST fail with reason `rate-limited`; 5xx and transport failures MUST fail with reason `network-failure`.

#### Scenario: Authentication response is not retried

- GIVEN the TICKERS service responds with 401 or 403
- WHEN the reader handles the response
- THEN it MUST make exactly one request and fail with reason `auth-failure`

#### Scenario: Retryable failure is bounded

- GIVEN the TICKERS service returns 429 or 5xx responses until the retry bound is exhausted
- WHEN the reader fetches reference data
- THEN it MUST perform no more than the bounded number of attempts
- AND it MUST fail with `rate-limited` for 429 or `network-failure` for 5xx
