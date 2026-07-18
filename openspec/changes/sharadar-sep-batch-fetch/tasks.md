# Tasks: Sharadar SEP Batch Fetch (chunk ticker GETs)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~260-330 (prod ~90, tests ~200) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Chunk→fetch→merge→validate-once refactor of `fetch_range` in `sharadar_market_data.py` + tests | PR 1 (single) | `uv run pytest tests/adapters/test_sharadar_market_data.py -q` | `invest-backtest --source sharadar` against a >1000-symbol universe (or MockTransport equivalent) | Revert `sharadar_market_data.py` + test file; no other files touched |

Only ONE file is modified (`src/invest/adapters/sharadar_market_data.py`) plus its test file — no cross-cutting integration, so a single PR stays reviewable if the forecast holds. If test additions grow beyond estimate, re-forecast before apply.

## Phase 1: Character-budget chunker

- [x] 1.1 RED: `_chunk_symbols` splits at budget boundary — feed symbols summing just over `MAX_TICKER_PARAM_CHARS`; assert 2 chunks, each `",".join(chunk)` ≤ budget, `union(chunks) == input`, order preserved (spec: "Oversized universe is split", "Chunk boundaries are deterministic").
- [x] 1.2 RED: `_chunk_symbols` — small universe within budget yields exactly one chunk equal to input (spec: "Small universe behaves exactly as before").
- [x] 1.3 RED: `_chunk_symbols` — single symbol longer than budget raises `MarketDataFetchError("request-too-large")` (design: fail-closed, cannot split further).
- [x] 1.4 GREEN: add `MAX_TICKER_PARAM_CHARS = 4000` class constant and implement `_chunk_symbols(self, symbols) -> Iterator[tuple[str, ...]]` in `sharadar_market_data.py`.

## Phase 2: `_fetch_chunk` extraction

- [x] 2.1 Extract `fetch_range:86-101` cursor loop into `_fetch_chunk(self, symbols, start, end) -> list[DailyBar]`: own cursor, own `range(1, MAX_PAGES+1)`, own `bar_keys` dedup; no coverage validation inside.
- [x] 2.2 Change `_request_params(self, symbols, start, end)` signature from `universe` to `symbols` (call sites updated to pass chunk symbols).
- [x] 2.3 VERIFY (no new test needed): `test_fetch_range_refuses_a_cursor_past_its_page_bound` and `test_fetch_range_merges_cursor_pages` stay green unchanged — 1-symbol universe = 1 chunk, per-chunk `MAX_PAGES` semantics preserved.

## Phase 3: Multi-chunk orchestration in `fetch_range`

- [x] 3.1 RED: over-budget universe (shrink `reader.MAX_TICKER_PARAM_CHARS` like the `MAX_PAGES=2` override trick) issues N requests; MockTransport captures each `request.url.params["ticker"]`, assert every `len(ticker) <= budget`, chunks disjoint, union == `universe.symbols` (spec: "Oversized universe is split into multiple requests").
- [x] 3.2 RED: merged bars from multi-chunk fetch are sorted `(symbol, date)`, dedup-free, equal to the unbounded-single-request expectation (spec: "Merge is complete, sorted, and duplicate-free").
- [x] 3.3 GREEN: rewrite `fetch_range` as orchestrator — `_chunk_symbols(universe.symbols)` → `_fetch_chunk` per chunk → `bars.extend(...)` → single post-loop validate+sort+return.
- [x] 3.4 REGRESSION: `test_fetch_range_maps_adjusted_sep_bars_in_deterministic_symbol_date_order` (asserts `ticker == "BETA,ACME"`) stays green unchanged — pins single-chunk contract.

## Phase 4: Per-chunk pagination ordering

- [x] 4.1 RED: a chunk spanning multiple cursor pages is fully walked (cursor sequence to `None`) before any request for the next chunk is issued (spec: "A multi-page chunk is fully walked before the next chunk").
- [x] 4.2 GREEN: confirm `_fetch_chunk` loop ordering in `fetch_range` already satisfies 4.1 (sequential `for chunk in self._chunk_symbols(...)`); adjust only if RED fails.

## Phase 5: Post-merge validation runs once

- [x] 5.1 RED: multi-chunk fetch where one symbol is missing from every chunk's SEP rows → validation fires once, post-merge, raises `symbol-missing-at-fetch` naming the symbol; no partial `FixtureInputs` (spec: "Missing symbol detected only after all chunks merge").
- [x] 5.2 RED: multi-chunk fetch with incomplete merged date coverage → `malformed-response` ("incomplete date coverage"), fired once post-merge, no partial bars (spec: "Incomplete date coverage detected only after all chunks merge").
- [x] 5.3 GREEN: move missing-symbol/date-coverage validation (`fetch_range:102-118` today) to run exactly once after the chunk loop, against merged `bars` + original `universe.symbols`.
- [x] 5.4 REGRESSION: `test_fetch_range_rejects_incomplete_symbol_date_coverage`, `test_fetch_range_rejects_an_xnys_session_missing_for_every_symbol`, `test_fetch_range_rejects_a_universe_symbol_missing_from_sep`, `test_fetch_range_rejects_duplicate_symbol_date_rows_across_cursor_pages` stay green unchanged.

## Phase 6: Optional — 414 relabel (secondary, include only if trivial)

- [x] 6.1 RED: `_send` handling an HTTP 414 response raises `MarketDataFetchError("request-too-large")` instead of `network-failure` (spec: "414 response is labeled distinctly").
- [x] 6.2 GREEN: add `if response.status_code == 414: raise MarketDataFetchError("request-too-large")` as a pre-branch guard before the generic `if response.is_error:` check in `_send`.
- [x] 6.3 REGRESSION: all existing `_send` retry/backoff/auth tests (401/403/429/5xx, network-error retry) stay green unchanged — 414 must not alter their status-code branches.

## Phase 7: Full regression sweep

- [x] 7.1 Run full `tests/adapters/test_sharadar_market_data.py` suite; confirm every test listed in design's "MUST stay green unchanged" list passes without modification.
- [x] 7.2 Confirm zero diff outside `src/invest/adapters/sharadar_market_data.py` and `tests/adapters/test_sharadar_market_data.py`.
