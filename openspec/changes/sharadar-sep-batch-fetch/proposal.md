# Proposal: sharadar-sep-batch-fetch

## Why
Every realistic-universe Sharadar SEP fetch currently fails. `SharadarMarketDataReader.fetch_range`
puts the entire universe into one GET `ticker=<comma list>` param. For a normal window
(2024-10-01..2024-12-31) that is 4293 symbols → a 20,020-char URL → the server returns
**HTTP 414 Request-URI Too Large**. `_send` maps any non-401/403/429/5xx `is_error` response
to `network-failure` (`sharadar_market_data.py:174-175`), so the failure is reported as a
misleading `{"reason":"network-failure"}`.

Impact: both user-facing data paths are unusable on any real universe —
`invest-generate-context` (incl. the new `--bars-out` local-fixture pull) and live
`invest-backtest --source sharadar`. Both go through the same `fetch_range`.

Live evidence: chunked raw GETs succeed (500 syms/2359 chars=200, 1000/4711=200), full
list (20020 chars)=414. Suspected nginx URI ceiling ~8KB.

## What Changes
Chunk the SEP ticker list inside `fetch_range` so each HTTP request stays under the server
URI limit, then merge results. One change fixes both call sites.

**Resolved defaults (AUTOMATIC mode — adopted from exploration):**
1. **Character-budget chunking**, not fixed count. Split `universe.symbols` into chunks whose
   comma-joined `ticker` value stays under `MAX_TICKER_PARAM_CHARS ≈ 4000` (~2x margin below
   the ~8KB ceiling, leaving headroom for `date.gte`/`date.lte`/`qopts.columns`/`api_key`).
   Rationale: bounds the exact value that causes the 414 and adapts to variable ticker length
   (warrants, `.WI` suffixes, class shares can run 6-9 chars) — a fixed count could still
   overflow on a long-ticker-skewed chunk.
2. **Per-chunk pagination**: each chunk runs its own cursor loop, its own `MAX_PAGES` budget,
   and its own in-page `bar_keys` dedup. Chunks are disjoint symbol sets, so no `(symbol,date)`
   pair crosses chunks.
3. **Do not reorder** `universe.symbols` before chunking — deterministic chunk boundaries
   (final bars are re-sorted, but stable chunking keeps tests predictable).
4. **Validation runs exactly once, post-merge.** The existing all-or-nothing missing-symbol /
   full-calendar date-coverage check (`fetch_range:102-118`) runs over the FULL merged result
   and the original `universe.symbols` — never per chunk. Correctness survives merge because
   cohort pre-filtering guarantees every symbol in one `fetch_range` call shares the same
   active date range; chunking splits symbols, never dates.
5. **Zero changes to `sharadar_context_source.py`.** The fix lives entirely in `fetch_range`.

**Optional / secondary (not blocking):** relabel a 414 response to a distinct
`request-too-large` reason in `_send` for accurate diagnostics, instead of the generic
`network-failure`.

## Scope
**In scope:** `src/invest/adapters/sharadar_market_data.py` — `fetch_range`, `_request_params`,
a new per-chunk pagination helper, chunk-splitting logic; optional `_send` 414 relabel.

**Out of scope / non-goals:**
- No changes to cohort logic, `sharadar_context_source.py`, domain, or backtest CLI wiring.
- No change to pagination semantics, retry/backoff, or the coverage-validation rules — only
  splitting one oversized request into several correctly-sized ones.
- Not a general HTTP-client refactor.

## Success Criteria
- A `fetch_range` call over a universe large enough to exceed the URI limit succeeds by
  issuing multiple chunked requests, each with a `ticker` param under the character budget.
- Merged bars are identical (sorted `(symbol,date)`, dedup-free) to what a single hypothetical
  unlimited request would return.
- The existing missing-symbol and incomplete-date-coverage validations still fire correctly,
  exactly once, over the merged result.
- The single-chunk path (small universe) behaves exactly as before — existing tests unchanged.
- Both `invest-generate-context` and `invest-backtest --source sharadar` work on a realistic
  universe.

## Impact
- Capability affected: Sharadar market-data fetch (`sharadar-market-data` reader). Delta spec
  needed for `fetch_range` chunking behavior.
- Unblocks the local-fixture pull (`context-bars-out`) and live sharadar backtests.

Exploration: `openspec/changes/sharadar-sep-batch-fetch/exploration.md` and Engram
`sdd/sharadar-sep-batch-fetch/explore` (obs 3238).
