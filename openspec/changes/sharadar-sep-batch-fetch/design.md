# Design: Sharadar SEP Batch Fetch (chunk ticker GETs)

## Technical Approach

Split the current single oversized SEP `ticker=` GET into several under-budget
requests **inside `SharadarMarketDataReader.fetch_range` only**. Extract today's
single-ticker-set cursor loop (`fetch_range:86-101`) into a private per-chunk
helper `_fetch_chunk`. `fetch_range` becomes an orchestrator: split
`universe.symbols` into character-budget chunks, call `_fetch_chunk` per chunk,
merge into one `bars` list, run the EXISTING all-or-nothing coverage validation
(`:102-118`) **exactly once** over the merged bars against the original
`universe.symbols`, then sort/return `FixtureInputs`. Zero changes to
`sharadar_context_source.py` — one fix serves both the cohort path and the
direct `invest-backtest --source sharadar` CLI path. Maps to proposal defaults 1-5.

## Architecture Decisions

### Decision: Character-budget chunking, not fixed count

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Fixed `SEP_CHUNK_SIZE=500` | Simple, but a long-ticker-skewed chunk (`.WI`, class shares 6-9 chars) can still overflow the URI ceiling | Rejected |
| Character budget `MAX_TICKER_PARAM_CHARS=4000` | Directly bounds the value that causes the 414; adapts to real ticker-length variance; ~2x margin below suspected ~8KB ceiling | **Chosen** |

**Rationale**: empirical data confirms safety at 4711 chars (1000 syms) and
414 at 20020. A char budget bounds the exact failing quantity; leaves ~200-300
char headroom for `date.gte`/`date.lte`/`qopts.columns`/`api_key`/`qopts.cursor_id`.

### Decision: Per-chunk pagination state (MAX_PAGES, bar_keys)

**Choice**: Each `_fetch_chunk` call owns its cursor, its own `range(1, MAX_PAGES+1)`
budget, and its own `bar_keys` dedup set.
**Alternatives considered**: global page counter / global dedup across all chunks.
**Rationale**: Chunks partition `universe.symbols` into **disjoint** sets, so no
`(symbol,date)` pair can appear in two chunks — cross-chunk dups are structurally
impossible; per-chunk dedup suffices. Per-chunk `MAX_PAGES` preserves the existing
`test_fetch_range_refuses_a_cursor_past_its_page_bound` (1-symbol = 1 chunk,
`reader.MAX_PAGES=2`) unmodified and gives each chunk the same generous budget.

### Decision: Validation runs once, post-merge; no symbol reordering

**Choice**: Missing-symbol + XNYS-calendar coverage check relocates verbatim from
inside the loop to `fetch_range` after all chunks merge; symbols are chunked in
caller-supplied order (no sort before chunking).
**Alternatives considered**: per-chunk validation; sort-then-chunk.
**Rationale**: Per-chunk validation is WRONG — a chunk's `reported_dates` union
only reflects that chunk's symbols. The global invariant holds post-merge because
cohort pre-filtering guarantees every symbol in one `fetch_range` call shares the
same active date window; chunking splits symbols never dates. Deterministic chunk
boundaries keep MockTransport tests predictable (final bars are re-sorted anyway).

## Data Flow

    universe.symbols (order preserved)
         │  _chunk_symbols() — char budget
         ▼
    [chunk₁] [chunk₂] ... [chunkₙ]   (disjoint, ∪ = symbols)
         │        │            │
         ▼        ▼            ▼      _fetch_chunk: own cursor loop,
     bars₁     bars₂    ...  barsₙ    own MAX_PAGES, own bar_keys
         └────────┴──── extend ───────┘
                     │
                     ▼  merged bars + ORIGINAL universe.symbols/start/end
         validate ONCE (missing-symbol / incomplete-coverage)
                     │
                     ▼  tuple(sorted(bars, key=(symbol,date)))
              FixtureInputs(universe=<original>, bars=…)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/invest/adapters/sharadar_market_data.py` | Modify | Add `MAX_TICKER_PARAM_CHARS=4000` constant; add `_chunk_symbols` + `_fetch_chunk`; refactor `fetch_range` to split→fetch→merge→validate-once; change `_request_params` to take `symbols`; OPTIONAL 414 relabel in `_send` |
| `tests/adapters/test_sharadar_market_data.py` | Modify | Add chunk-splitting + multi-chunk fetch tests (RED first); all existing tests stay green unchanged |

## Interfaces / Contracts

```python
MAX_TICKER_PARAM_CHARS = 4000  # class constant, sibling of MAX_PAGES

def _chunk_symbols(self, symbols: tuple[str, ...]) -> Iterator[tuple[str, ...]]:
    """Yield chunks (input order preserved) whose ",".join(chunk) length
    stays <= MAX_TICKER_PARAM_CHARS. A single symbol longer than the budget
    is a programmer/data error -> raise MarketDataFetchError("request-too-large")
    (cannot be split further; must never silently emit an over-budget request)."""

def _fetch_chunk(self, symbols: tuple[str, ...], start: date, end: date) -> list[DailyBar]:
    """Own cursor loop, own range(1, MAX_PAGES+1), own bar_keys dedup.
    Returns this chunk's bars. Does NOT run coverage validation."""

def _request_params(self, symbols: tuple[str, ...], start: date, end: date) -> dict[str, str]:
    return {"ticker": ",".join(symbols), ...}   # was universe; now a given chunk
```

`fetch_range` calls `_request_params(symbols, …)` indirectly through `_fetch_chunk`.
Merge is `bars.extend(...)` per chunk; final `tuple(sorted(bars, key=lambda b:(b.symbol,b.date)))`
is chunk-order-independent so no cross-chunk sort concern. `FixtureInputs.universe`
stays the ORIGINAL unchunked `Universe` (chunking is invisible to callers/tests).

### OPTIONAL: 414 relabel in `_send`

Before the generic `if response.is_error:` branch (`:174`), add:
```python
if response.status_code == 414:
    raise MarketDataFetchError("request-too-large")
```
Low-risk, diagnostic-only, scoped to this file. Include only if it stays trivial;
chunking should make 414 not occur in practice.

## Testing Strategy (Strict TDD — RED first)

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `_chunk_symbols` boundary at budget | Feed symbols summing just over `MAX_TICKER_PARAM_CHARS`; assert 2 chunks, each `",".join` ≤ budget, union == input, order preserved |
| Unit | Single over-budget symbol | One symbol longer than budget → `MarketDataFetchError("request-too-large")` |
| Integration | Multi-chunk issues N in-budget requests | MockTransport captures each `request.url.params["ticker"]`; assert every captured `len(ticker) <= budget`, chunks disjoint, ∪ = universe.symbols (shrink budget via `reader.MAX_TICKER_PARAM_CHARS = small`, mirroring the `reader.MAX_PAGES=2` override trick) |
| Integration | Per-chunk pagination walked fully | Each chunk drives its own `qopts.cursor_id` sequence to `None`; assert both chunks paginated independently |
| Integration | Post-merge validation fires ONCE | (a) symbol missing in one chunk → `symbol-missing-at-fetch`; (b) date coverage mismatch across chunks → `malformed-response` "incomplete date coverage" |
| Regression | Single-chunk path identical | Small universe → exactly one request, one `ticker` param, behavior unchanged |
| Regression | Determinism | Same `universe.symbols` order → identical chunk boundaries across runs |

**Existing tests that MUST stay green unchanged**: `test_fetch_range_maps_adjusted_sep_bars_in_deterministic_symbol_date_order`
(asserts `ticker == "BETA,ACME"` — single chunk), `test_fetch_range_merges_cursor_pages`,
`test_fetch_range_refuses_a_cursor_past_its_page_bound` (`MAX_PAGES=2`, 1 chunk),
`test_fetch_range_rejects_duplicate_symbol_date_rows_across_cursor_pages`,
`test_fetch_range_rejects_incomplete_symbol_date_coverage`,
`test_fetch_range_rejects_an_xnys_session_missing_for_every_symbol`,
`test_fetch_range_rejects_a_universe_symbol_missing_from_sep`, and all `_send`
retry/backoff/auth tests. These pin the single-chunk contract that the refactor
must preserve byte-for-byte.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file
classification, or process-integration boundary. Change is internal HTTP
request-shaping over the existing `httpx.Client`.

## Migration / Rollout

No migration required. Pure internal refactor; public `fetch_range`/`fetch`
signatures and `FixtureInputs` output are unchanged.

## Open Questions

- [ ] None blocking. `MAX_TICKER_PARAM_CHARS=4000` is a conservative default from
      empirical probes; adjustable later without contract change.
