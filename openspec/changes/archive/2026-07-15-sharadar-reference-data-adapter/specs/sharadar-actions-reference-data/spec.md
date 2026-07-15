# Sharadar Actions Reference Data Specification

## Purpose

Provide backtest-only corporate-action history as typed, point-in-time events without changing price data or execution behavior.

## Requirements

### Requirement: ACTIONS event retrieval

`SharadarActionsReader` MUST retrieve records from the SHARADAR/ACTIONS datatable through a caller-supplied HTTP client and MUST use `NASDAQ_DATA_LINK_API_KEY` only to authenticate requests. It MUST follow every non-null `meta.next_cursor_id`, combine all pages, and stop at a bounded page limit. It MUST return events in deterministic ticker, effective-date, and event-kind order.

#### Scenario: Cursor pages are combined deterministically

- GIVEN two valid ACTIONS response pages where the first contains a next cursor
- WHEN the reader fetches events through a mocked HTTP client
- THEN it MUST request the continuation cursor and return all events in deterministic order

#### Scenario: Pagination bound is exceeded

- GIVEN valid ACTIONS pages that continue beyond the page limit
- WHEN the reader fetches events
- THEN it MUST fail with reason `malformed-response`
- AND it MUST return no partial events

### Requirement: Typed corporate-action events

Each returned event MUST contain a ticker, effective date, event kind, and optional value. The reader MUST represent split, dividend, delisting, and ticker-change rows as typed events. Every present monetary or ratio value MUST be represented as an exact `Decimal`; an absent value MUST remain absent. Unsupported or invalid event kinds and invalid values MUST fail closed rather than be silently reclassified.

#### Scenario: Corporate-action values retain Decimal precision

- GIVEN valid split, dividend, delisting, and ticker-change rows, including a decimal dividend and a ratio-valued split
- WHEN the reader converts the rows to events
- THEN it MUST return the corresponding typed events
- AND every present monetary or ratio value MUST be a `Decimal`
- AND an absent event value MUST remain absent

#### Scenario: Unsupported event fails closed

- GIVEN an ACTIONS row with an unsupported event kind or invalid value
- WHEN the reader validates the row
- THEN it MUST fail with reason `malformed-response`
- AND it MUST return no partial events

### Requirement: ACTIONS retrieval does not adjust market prices

ACTIONS retrieval MUST report corporate-action events only. It MUST NOT adjust SEP OHLC data, mutate input bars, or alter the behavior or contract of the SEP market-data reader.

#### Scenario: Fetching actions leaves bar handling unchanged

- GIVEN valid ACTIONS rows and independently supplied SEP bars
- WHEN ACTIONS retrieval completes
- THEN the result MUST contain corporate-action events only
- AND the supplied SEP bars MUST remain unchanged

### Requirement: Fail-closed ACTIONS validation and authentication

A missing or empty `NASDAQ_DATA_LINK_API_KEY` MUST fail before any HTTP request and MUST NOT be logged. An empty, malformed, incomplete, or schema-invalid ACTIONS response or row MUST fail with reason `malformed-response`; no partial events MAY be returned.

#### Scenario: Missing credential fails before transport

- GIVEN `NASDAQ_DATA_LINK_API_KEY` is unset or empty
- WHEN an ACTIONS fetch is attempted
- THEN it MUST fail with reason `auth-failure`
- AND the supplied HTTP client MUST receive no request

#### Scenario: Invalid response fails closed

- GIVEN an ACTIONS response with missing required columns, an empty table, or an invalid row
- WHEN the reader validates it
- THEN it MUST fail with reason `malformed-response`
- AND it MUST return no partial events

### Requirement: ACTIONS retry taxonomy

ACTIONS authentication responses (401 and 403) MUST fail immediately with reason `auth-failure` and MUST NOT be retried. Rate-limit responses (429), 5xx responses, and transport request failures MUST use bounded retry with exponential backoff that honors a valid `Retry-After` delay. On exhaustion, 429 MUST fail with reason `rate-limited`; 5xx and transport failures MUST fail with reason `network-failure`.

#### Scenario: Authentication response is not retried

- GIVEN the ACTIONS service responds with 401 or 403
- WHEN the reader handles the response
- THEN it MUST make exactly one request and fail with reason `auth-failure`

#### Scenario: Retryable failure is bounded

- GIVEN the ACTIONS service returns 429 or 5xx responses until the retry bound is exhausted
- WHEN the reader fetches events
- THEN it MUST perform no more than the bounded number of attempts
- AND it MUST fail with `rate-limited` for 429 or `network-failure` for 5xx
