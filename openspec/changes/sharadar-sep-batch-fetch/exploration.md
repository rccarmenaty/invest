# Exploration: sharadar-sep-batch-fetch — chunk SEP ticker-param GETs to avoid HTTP 414

## Root cause (live-verified)
`invest-generate-context` and live `invest-backtest --source sharadar` fail with
`{"reason":"network-failure"}` on any realistic universe. Real cause: **HTTP 414
Request-URI Too Large**, mis-mapped to `network-failure`.

`SharadarMarketDataReader.fetch_range` (`src/invest/adapters/sharadar_market_data.py:82-125`)
issues ONE logical SEP request: `_request_params` (`:201-207`) builds
`ticker=",".join(universe.symbols)` — the FULL universe — plus date/columns. Cursor
pagination walks pages of that same ticker set (`MAX_PAGES=512`). `_send` (`:157-177`)
retries only `RequestError`/429/5xx; any other 4xx (incl. 414) hits
`if response.is_error: raise MarketDataFetchError("network-failure")` (`:174-175`) — one
shot, mislabeled.

Live evidence: TICKERS reader returns 62506 rows fine (no ticker filter — only SEP is
affected). Window 2024-10-01..2024-12-31 → `_normalize_candidates` yields 4293 candidates
→ ticker param 20,020 chars → raw SEP GET **414**. Chunk probes (~4.7 chars/ticker incl.
comma): 500=2359 chars→200, 800=3758→200, 1000=4711→200, 4293=20020→414. Suspected nginx
URI ceiling ~8KB.

## Two beneficiary call sites (both fixed by one change in fetch_range)
1. `invest-backtest --source sharadar` — `src/invest/adapters/cli.py:209-212` calls
   `fetch_range` directly on a JSON-file universe, no chunking.
2. `SharadarContextSource._fetch_sep_cohorts`
   (`src/invest/adapters/sharadar_context_source.py:119-140`) cohorts by listing *window*,
   then calls `fetch_range` per cohort — but a single cohort can still hold thousands of
   symbols. Cohorting bounds date ranges, not ticker-param size. Symbol chunking is
   orthogonal and belongs INSIDE `fetch_range`. **No change to `sharadar_context_source.py`.**

## Critical invariant to preserve (validated against code)
At `fetch_range:102-118`, once pagination exhausts, an all-or-nothing dense-rectangle check
runs over ALL accumulated bars: (1) every requested symbol appears ≥once
(`symbol-missing-at-fetch`); (2) every symbol's date set equals the union of all symbols'
dates (no partial coverage); (3) that union equals the exact XNYS sessions in `[start,end]`
(`malformed-response: incomplete date coverage`).

This is a GLOBAL invariant over the full symbol set. With chunking it MUST run exactly once,
post-merge, against the merged bars + original `universe.symbols` — never per chunk (a
per-chunk check sees only that chunk's dates). Correctness survives merge because cohort
pre-filtering guarantees every symbol in one `fetch_range` call shares the same active date
range; chunking splits symbols, never dates. Per-chunk in-page dup detection (`bar_keys`)
can stay chunk-scoped — chunks are disjoint, no `(symbol,date)` crosses chunks. `MAX_PAGES`
applies per chunk (reset per chunk), preserving the existing single-chunk test.

## Approaches
1. **Fixed symbol-count constant** (`SEP_CHUNK_SIZE=500`). Simple, mirrors `MAX_PAGES`
   pattern. But doesn't adapt to ticker-length variance (long tickers/warrants/.WI suffixes
   6-9 chars) — a count-safe chunk skewed to long tickers can still overflow. Effort: Low.
2. **Character-budget chunking** (`MAX_TICKER_PARAM_CHARS≈4000`): accumulate symbols while
   joined length stays under budget, then start a new chunk. Directly bounds the value that
   causes the 414; adapts to real ticker distribution; ~2x margin under ~8KB with headroom
   for other params. Effort: Medium. **Recommended.**

## Recommendation
Character-budget chunking inside `fetch_range`: extract the pagination loop into a per-chunk
helper (own cursor, own `MAX_PAGES`, own `bar_keys`), split `universe.symbols` into
character-budget chunks (do NOT reorder before chunking — determinism), accumulate all bars,
then run the existing missing-symbol/date-coverage validation exactly once over the full
merged result. Fixes both the context and backtest paths; zero changes to
`sharadar_context_source.py`.

## Risks
- Chunk boundaries must be deterministic given fixed `universe.symbols` order (final bars
  re-sorted, but test predictability needs stable chunking).
- Per-chunk `MAX_PAGES` raises theoretical total page count for huge universes (many chunks
  × ≤512) — acceptable; each chunk needs far fewer pages in practice.
- Optional/orthogonal: relabel 414 → distinct `request-too-large` reason for diagnostics.
  Flagged, not required for the core fix.

## Tests
Existing `tests/adapters/test_sharadar_market_data.py` uses `httpx.MockTransport` asserting
on `request.url.params["ticker"]` and cursor sequences — mirror this for chunk-boundary
tests (multi-chunk split, per-chunk pagination, post-merge validation, single-chunk
regression unchanged).

## Ready for Proposal
Yes. Engram artifact: `sdd/sharadar-sep-batch-fetch/explore` (obs 3238).
