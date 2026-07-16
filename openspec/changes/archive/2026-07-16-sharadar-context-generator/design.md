# Design: Sharadar Market Context Generator

## Technical Approach

Add backtest-only `invest-generate-context`: discover TICKERS, fetch SEP/ACTIONS, derive point-in-time `MarketContext`, atomically write `market-context-v1`; never replay.

## Architecture Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Reference seam | `adapters/sharadar_context_source.py` is the only allowed importer/caller of `SharadarTickersReader` and `SharadarActionsReader`. | Exact opt-in preserves default-deny isolation. |
| Domain | `domain/liquidity_screen.py` owns `ScreenConfig` and daily eligibility; `domain/market_context_builder.py` owns RLE windows. | Pure Decimal/date policy, independently testable. |
| Application/adapters | `application/generate_market_context.py` coordinates normalized inputs; source, writer, and CLI remain adapters. | Direction: adapters → application → domain; no SDK/filesystem/clock in domain. |

The source may call unchanged `SharadarMarketDataReader.fetch_range` in deterministic listing-period cohorts. Do not refactor or deduplicate SEP transport.

## Data Flow and Point-in-Time Semantics

```
CLI → SharadarContextSource → GenerateMarketContext → Builder → JSON writer
       TICKERS / SEP cohorts / ACTIONS                 ↘ MarketContext
```

1. Fetch and ticker-sort TICKERS. Coalesce identical duplicates; fail on conflicting/reused ticker facts. Reuse—not reclassify—the reader's primary-common, listing, and delisting facts.
2. For each primary candidate whose listing interval intersects the range, fetch SEP in cohorts sharing the clipped listing/history interval. Fetch enough preceding XNYS sessions for `max(min_bars, volume_window)` and require unique symbol-date keys and complete cohort coverage.
3. Fetch ACTIONS once; validate/deduplicate `(ticker, effective_date, kind, value)`. Use an action only on its exact effective output session; never shift or anticipate it.
4. On each requested session, a listing is active inclusively from listing through delisting. Eligibility needs active primary-common status, current adjusted close >= floor, observed-bar count, and trailing-inclusive median `adjusted close × volume` >= floor. No later bar participates. Emit the deterministic union of ever-eligible symbols, each with every requested session covered.
5. Run-length encode equal eligibility. Same-day actions collapse to one `corporate-action` blocker only when eligible; emit no earnings blocker. Sort symbols/windows and serialize compact canonical JSON plus newline; reader-validate before publication.

Listing, liquidity, and history failure are `eligible=false`, never blockers. The builder preserves coverage completeness, one eligibility decision per day, nesting, non-overlap, and no blocker over ineligibility; `MarketContext` remains the final invariant check.

## CLI, Errors, and Output

Required: `invest-generate-context --start YYYY-MM-DD --end YYYY-MM-DD --out PATH`. Optional defaults: `--price-floor 10`, `--dollar-volume-floor 10000000`, `--dollar-volume-window 20`, `--min-observed-bars 252`. Require ordered dates; finite positive decimals; positive counts; seasoning >= volume window; a non-existent `--out` in an existing writable directory. There is no source, replay, universe, overwrite, AUM, ADV-fraction, or impact option.

Success exits 0, writes one file, and prints nothing. Failure exits 2 with one sorted JSON line on stdout and no stderr: `invalid-arguments`, `market-context-invalid`, stable reader reasons, `reference-data-incomplete`, `output-exists`, or `storage-failure`. Never expose keys or partial data. After fetch/build validation, write and fsync a same-directory temporary file, reader-validate it, atomically create the final path without replacement, and clean the temporary file on every failure; no output artifact survives.

## Interfaces / Contracts

The application source interface returns immutable normalized listing/action facts, adjusted `DailyBar`s, and requested sessions. `GenerateMarketContext.run(inputs, config) -> MarketContext`; `BacktestContextJsonWriter.write(context, out) -> Path`. Raw Sharadar classes never enter application/domain.

## File Changes

| File | Action | Purpose |
|---|---|---|
| `src/invest/domain/liquidity_screen.py`, `market_context_builder.py` | Create | Pure screen and invariant-preserving builder. |
| `src/invest/application/generate_market_context.py` | Create | Use case and normalized contracts. |
| `src/invest/adapters/sharadar_context_source.py`, `generate_context_cli.py` | Create | Provider source and dedicated entrypoint. |
| `src/invest/adapters/backtest_context_json.py`, `pyproject.toml`, `tests/test_boundaries.py` | Modify | Writer, console script, one-path allowlist. |
| `tests/domain/`, `tests/application/`, `tests/adapters/` | Create/Modify | Strict TDD coverage. |

## Testing Strategy

| Layer | RED-first coverage |
|---|---|
| Unit | Threshold/history/no-look-ahead; listing/delisting; RLE, action merge/omission, completeness and overlap rejection. |
| Adapter/application | Mocked reader/HTTP pagination, duplicates/partials, cohort coverage, error mapping, atomic cleanup, determinism, reader round-trip. |
| CLI/boundary | Arguments/error record; no replay/broker calls; AST permits only source module. No network tests. |

## Threat Matrix

| Boundary | Applicability | Response / RED tests |
|---|---|---|
| Documentation paths | N/A — no classification/execution | N/A |
| Git selection | N/A — no VCS operation | N/A |
| Commit state | N/A — no commit operation | N/A |
| Push state | N/A — no push operation | N/A |
| PR commands | N/A — no PR operation | N/A |

## Chained Review Forecast and Rollout

No migration. **PR 1** (<=360 lines): pure screen/builder plus unit RED→GREEN tests; rollback removes domain modules. **PR 2** (<=400): source/writer plus mocked-reader and atomic tests; depends on PR 1, independently removable. **PR 3** (<=360): console script, allowlist, CLI integration tests/docs; depends on PR 2, rollback restores empty allowlist. Each is a force-chained slice.

## Deferred Decisions

Broad-data volume is bounded by pagination/cohort completeness but needs operational sizing before a full-history run. ADR/dual-class policy stays the reader's exclusion; survivor cap and rolling-ADV metadata are deferred. AUM-dependent ADV/impact gating, live/paper/broker/scanner work, replay, and SEP transport refactoring are excluded.
