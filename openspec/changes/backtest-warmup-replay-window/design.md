# Design: Backtest Warmup Replay Window

## Technical Approach

Make the context artifact the sole temporal authority. Generation carries its normalized, non-empty requested session bounds into a first-class domain span; JSON round-trips that span; replay partitions bars once before validation or scanning. Completeness, decisions, portfolio processing, and reporting use only observed in-span replay dates, while scanners may see earlier bars as history.

## Architecture Decisions

| Decision | Choice and rationale |
|---|---|
| Schema label | **Bump to `market-context-v2`.** The current Pydantic payload is strict and accepts only the literal v1 shape (`src/invest/adapters/backtest_context_json.py:65-77`). Making `generation_span` required intentionally rejects every old document, so retaining v1 would disguise a breaking contract. Both fixture sets are regenerated either way; v2 makes the migration explicit. |
| Domain authority | **Add immutable `GenerationSpan(start, end)` as a required first-class `MarketContext` field.** `MarketContext` already owns context invariants and all status/completeness queries (`src/invest/domain/market_context.py:131-179`), and the builder returns it directly (`src/invest/domain/market_context_builder.py:62-83`). A document wrapper would split temporal authority between adapter and domain. Construction rejects inverted spans; status outside the span fails closed. |
| Post-window bars | **Reject with application input error reason `replay-window-invalid`; CLI emits exactly `{"reason":"replay-window-invalid"}`.** Existing backtest errors are stable one-record reasons (`src/invest/adapters/cli.py:250-265`). Do not ignore or truncate post-span data. The same reason covers no observed in-span session; messages remain diagnostic internals. |
| 253 ownership | **Directly import the domain module constant `HISTORY_DAYS` into `sharadar_context_source.py` and compute `max(config.min_observed_bars, config.dollar_volume_window, HISTORY_DAYS)`.** The adapter already depends inward on domain configuration/models (`src/invest/adapters/sharadar_context_source.py:21-27`) and currently derives depth locally (`:119-133`). The actual authority is module-level `HISTORY_DAYS = 253`, consumed by the scanner gate (`src/invest/domain/momentum_selection_scanner.py:20-40`), not a class attribute. Capability plumbing would add false configurability for a fixed Core contract. |
| Split semantics | **Require exact membership in observed in-span replay dates.** The current extrema check accepts weekends and other unobserved dates (`src/invest/adapters/cli.py:225-233`). Exact-session membership is the clearest deterministic acceptance policy and makes trading-day segment boundaries reproducible; warmup dates cannot qualify. |

## Data Flow and Replay Partition

`generate_context_cli --start/--end` → `SharadarContextSource.load` normalizes XNYS sessions (`src/invest/adapters/sharadar_context_source.py:54-74`) → `GeneratorInputs.sessions` (`src/invest/application/generate_market_context.py:49-54`) → `GenerateMarketContext.run` → builder derives `GenerationSpan(first_session,last_session)` (`:57-70`; `src/invest/domain/market_context_builder.py:62-68`) → `MarketContext` → v2 writer `generation_span` → reader → `BacktestRun`.

At the start of `BacktestRun.replay`, before the current all-bar completeness calculation (`src/invest/application/backtest_run.py:117-120`), a private partition helper returns sorted warmup bars, replay bars, and replay dates; it rejects post-span bars and an empty replay partition. `require_complete` receives replay dates × fixture symbols. `scan_decisions` iterates only replay dates but forms each scanner window from **all** bars dated `<= d`, preserving warmup history (current window behavior at `:105-114`). `bars_by_date` and the portfolio loop use replay bars only (current construction/loop at `:125-146`). Live `--start/--end` must exactly equal the declared span; fixture mode derives coherence solely from partitioning. `--split-date` must be one replay date.

## File Changes

Modify the eight production files named in `exploration.md`: domain span/invariants and builder propagation; v2 JSON; generation/source/CLI propagation; replay partition; Core warmup depth. Also update `tests/adapters/test_cli_backtest.py` for CLI records and range/split coherence.

## Strict TDD Strategy

Write failing tests first, then minimal implementation, then refactor, in this order: `tests/domain/test_market_context.py` (span/inversion/out-of-span), `test_market_context_builder.py` (bounds propagation), `tests/adapters/test_backtest_context_json.py` (required v2 span, old-v1/malformed rejection, deterministic round-trip), `tests/application/test_backtest_run.py` (partition, warmup-visible scanner, no pre-span events, gap/no-replay/post-span errors), `tests/adapters/test_cli_backtest.py` (exact split, exact live range, reason record), `test_sharadar_context_source.py` (253 and listing clipping), `test_generate_context_cli.py` (paired outputs/span), `tests/domain/test_momentum_selection_scanner.py` (253 contract unchanged), then `tests/fixtures/test_backtest_252_fixtures.py` (real replay regression).

## Threat Matrix

N/A — no shell, subprocess, VCS, executable classification, routing, or process-integration boundary changes.

## Migration / Rollout

Regenerate every `fixtures/real-years/**/market-context.json` as v2, retaining warmup bars in paired fixtures. Regenerate `fixtures/backtest-252` context/goldens and verify all events remain in-span. Old v1 files fail closed; no compatibility reader or inferred span is provided.

## Open Questions

None. Residual migration risk is limited to unavailable Sharadar credentials; checked-in deterministic fixtures remain the fallback verification input.
