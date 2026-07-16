# Delta for Sharadar SEP Market Data

## MODIFIED Requirements

### Requirement: SEP bar fetch with bounded cursor pagination

The system MUST expose `fetch(universe, as_of)` and `fetch_range(universe, start, end)` against the SHARADAR/SEP datatable only, returning `FixtureInputs`. When the comma-joined `ticker` param for `universe.symbols` exceeds `MAX_TICKER_PARAM_CHARS`, `fetch_range` MUST split the universe into ordered chunks and fetch each chunk with its own independent cursor pagination loop, following `meta.next_cursor_id` in pages of up to 10,000 rows, stopping at its own bounded `MAX_PAGES` limit before the next chunk is fetched.
(Previously: pagination was a single cursor loop over one request covering the whole universe.)

#### Scenario: Range fetch returns bars for the full universe and range

- GIVEN a universe and a date range
- WHEN `fetch_range` completes successfully
- THEN it MUST return `FixtureInputs` covering every symbol and trading day requested

#### Scenario: Unbounded pagination is refused

- GIVEN a chunk's response that keeps returning a non-null `next_cursor_id` beyond the bounded page limit
- WHEN the reader paginates that chunk
- THEN it MUST fail with reason `malformed-response` and return no partial bars

#### Scenario: A multi-page chunk is fully walked before the next chunk

- GIVEN a chunk whose ticker set spans multiple pages
- WHEN `fetch_range` fetches that chunk
- THEN it MUST walk all pages of that chunk to completion (or fail) before issuing any request for the next chunk

## ADDED Requirements

### Requirement: Character-budget chunking of the ticker parameter

`fetch_range` MUST split `universe.symbols` into ordered chunks so that no single HTTP request's comma-joined `ticker` param exceeds `MAX_TICKER_PARAM_CHARS`. Chunk boundaries MUST be derived from `universe.symbols` order without reordering symbols first.

#### Scenario: Oversized universe is split into multiple requests

- GIVEN a universe whose comma-joined `ticker` value exceeds `MAX_TICKER_PARAM_CHARS`
- WHEN `fetch_range` runs
- THEN it MUST issue multiple HTTP requests
- AND each request's `ticker` param MUST be within `MAX_TICKER_PARAM_CHARS`

#### Scenario: Small universe behaves exactly as before

- GIVEN a universe whose comma-joined `ticker` value fits within `MAX_TICKER_PARAM_CHARS`
- WHEN `fetch_range` runs
- THEN it MUST issue exactly one logical chunk request, identical to pre-chunking behavior

#### Scenario: Chunk boundaries are deterministic

- GIVEN the same `universe.symbols` and `MAX_TICKER_PARAM_CHARS`
- WHEN `fetch_range` computes chunks on repeated calls
- THEN symbols MUST retain `universe.symbols` order and produce identical chunk boundaries each time

### Requirement: Merged multi-chunk result equivalence

Bars fetched across multiple chunks MUST be merged into a single result equivalent to what one unbounded request would return: every requested symbol and date, sorted by `(symbol, date)`, with no duplicate `(symbol, date)` pair.

#### Scenario: Merge is complete, sorted, and duplicate-free

- GIVEN a universe split into multiple chunks, each returning disjoint symbol bars
- WHEN `fetch_range` merges the chunk results
- THEN the merged bars MUST cover every symbol and date returned across all chunks
- AND MUST contain no duplicate `(symbol, date)` pair
- AND MUST be sorted by `(symbol, date)`

### Requirement: Missing-symbol and date-coverage validation runs once, post-merge

The existing all-or-nothing missing-symbol and date-coverage validation MUST run exactly once, after every chunk has been fetched and merged — never per chunk.

#### Scenario: Missing symbol detected only after all chunks merge

- GIVEN a multi-chunk fetch where one requested symbol has no SEP rows in any chunk
- WHEN `fetch_range` finishes fetching and merging all chunks
- THEN validation MUST run once over the merged result
- AND MUST fail with reason `symbol-missing-at-fetch` naming the missing symbol
- AND no partial `FixtureInputs` MUST be returned

#### Scenario: Incomplete date coverage detected only after all chunks merge

- GIVEN a multi-chunk fetch where the merged result has incomplete date coverage for a symbol
- WHEN validation runs over the merged result
- THEN it MUST fail with reason `malformed-response` ("incomplete date coverage")
- AND no partial bars MUST be returned

### Requirement: Oversized-request response is distinguishable

The system MAY map an HTTP 414 response to a distinct reason `request-too-large`, instead of the generic `network-failure`.

#### Scenario: 414 response is labeled distinctly

- GIVEN the SEP API returns HTTP 414
- WHEN `_send` handles the response
- THEN it MAY fail with reason `request-too-large` rather than `network-failure`
