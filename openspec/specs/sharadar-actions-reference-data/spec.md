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

Each returned event MUST contain a ticker, effective date, event kind, and optional value. The reader MUST map the mapped ACTIONS literals `split`, `adrratiosplit`, `dividend`, `spinoffdividend`, `delisted`, `regulatorydelisting`, `voluntarydelisting`, `bankruptcyliquidation`, `tickerchangeto`, and `tickerchangefrom` to typed events: `split` and `adrratiosplit` MUST both produce a split event; `dividend` and `spinoffdividend` MUST both produce a dividend event; `delisted`, `regulatorydelisting`, `voluntarydelisting`, and `bankruptcyliquidation` MUST all produce a delisted event; `tickerchangeto` and `tickerchangefrom` MUST both produce a ticker-change event (directionality is not preserved). Every present monetary or ratio value MUST be represented as an exact `Decimal`, including values supplied as JSON floats, coerced without precision loss. An absent value MUST remain absent. A delisted or ticker-change row MAY carry a source value (the live SHARADAR/ACTIONS feed attaches a contra/last price); the reader MUST accept the row and normalize its value to absent, since the kind-blind context builder never uses it. Non-finite or non-positive values on a split or dividend event MUST fail closed rather than be silently reclassified.
(Previously: only the literals `split`, `dividend`, `delisting`, and `tickerchange` were mapped — two of which never occur in real data — and any row whose `value` was a JSON float was rejected outright.)

#### Scenario: Mapped literals parse to their normalized kind

- GIVEN ACTIONS rows using each of the ten mapped literals: `split`, `adrratiosplit`, `dividend`, `spinoffdividend`, `delisted`, `regulatorydelisting`, `voluntarydelisting`, `bankruptcyliquidation`, `tickerchangeto`, `tickerchangefrom`
- WHEN the reader converts the rows to events
- THEN `split` and `adrratiosplit` rows MUST both produce split events
- AND `dividend` and `spinoffdividend` rows MUST both produce dividend events
- AND `delisted`, `regulatorydelisting`, `voluntarydelisting`, and `bankruptcyliquidation` rows MUST all produce delisted events
- AND `tickerchangeto` and `tickerchangefrom` rows MUST both produce ticker-change events

#### Scenario: Float values coerce to exact Decimals

- GIVEN a dividend row with value `9.00009000090001` and a split row with value `0.04545`, both supplied as JSON floats
- WHEN the reader converts the rows to events
- THEN each event's value MUST be an exact `Decimal` matching the source float's full decimal representation with no precision loss

#### Scenario: Valueless kinds accept and drop any source value

- GIVEN a delisted or ticker-change row that carries any value (a contra/last price, zero, negative, or null)
- WHEN the reader converts the row to an event
- THEN it MUST produce the event with an absent value
- AND it MUST NOT fail the fetch

#### Scenario: Non-finite or non-positive values still fail closed

- GIVEN a split or dividend row with a non-finite, zero, or negative value
- WHEN the reader validates the row
- THEN it MUST fail with reason `malformed-response`

### Requirement: ACTIONS retrieval does not adjust market prices

ACTIONS retrieval MUST report corporate-action events only. It MUST NOT adjust SEP OHLC data, mutate input bars, or alter the behavior or contract of the SEP market-data reader.

#### Scenario: Fetching actions leaves bar handling unchanged

- GIVEN valid ACTIONS rows and independently supplied SEP bars
- WHEN ACTIONS retrieval completes
- THEN the result MUST contain corporate-action events only
- AND the supplied SEP bars MUST remain unchanged

### Requirement: Fail-closed ACTIONS validation and authentication

A missing or empty `NASDAQ_DATA_LINK_API_KEY` MUST fail before any HTTP request and MUST NOT be logged. An empty, malformed, incomplete, or schema-invalid ACTIONS response MUST fail with reason `malformed-response`; no partial events MAY be returned. A row with missing required columns/fields, an invalid value type, or an invalid value for its mapped kind MUST also fail with reason `malformed-response`. A row whose event-kind literal is outside the mapped set (including the explicit skip set and any unrecognized literal) MUST NOT be treated as invalid; it MUST be silently dropped per the skip-unknown policy instead of failing the response.
(Previously: any row with an event-kind literal outside the 4-member mapped set was treated as malformed and aborted the entire fetch.)

#### Scenario: Missing credential fails before transport

- GIVEN `NASDAQ_DATA_LINK_API_KEY` is unset or empty
- WHEN an ACTIONS fetch is attempted
- THEN it MUST fail with reason `auth-failure`
- AND the supplied HTTP client MUST receive no request

#### Scenario: Invalid response fails closed

- GIVEN an ACTIONS response with missing required columns, an empty table, or a mapped-kind row with an invalid value
- WHEN the reader validates it
- THEN it MUST fail with reason `malformed-response`
- AND it MUST return no partial events

### Requirement: Skip-unknown ACTIONS row policy

The reader MUST silently drop, without producing a normalized event and without aborting the fetch, any ACTIONS row whose event-kind literal is in the explicit skip set (`listed`, `relation`, `acquisitionby`, `acquisitionof`, `mergerto`, `mergerfrom`, `spinoff`, `spunofffrom`) or is any other literal outside the mapped set. Dropping a row MUST NOT raise, retry, or fail the containing page or request; all remaining valid rows on that page and on subsequent pages MUST still be returned in the deterministic order required for event retrieval.

#### Scenario: Skipped known literals produce no events

- GIVEN an ACTIONS page containing rows for `listed`, `relation`, `acquisitionby`, `acquisitionof`, `mergerto`, `mergerfrom`, `spinoff`, and `spunofffrom`
- WHEN the reader converts the page to events
- THEN it MUST return zero events for those rows
- AND it MUST NOT fail the fetch

#### Scenario: Unrecognized literal is silently skipped

- GIVEN an ACTIONS page containing one row with a literal outside both the mapped and skip sets, alongside valid mapped rows
- WHEN the reader fetches and converts the page
- THEN the unrecognized row MUST produce no event
- AND the fetch MUST succeed and return events for the valid rows

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
