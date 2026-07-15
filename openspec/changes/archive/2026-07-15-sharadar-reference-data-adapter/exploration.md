# Exploration: Sharadar reference data + point-in-time MarketContext generation

**Umbrella (change 2)**: generate the point-in-time `MarketContext` from Sharadar SEP/TICKERS/ACTIONS + a liquidity screen, replacing the hand-authored `market-context.json`.
**Date**: 2026-07-15
**Engram**: `sdd/sharadar-context-generator/explore` (obs #3034)
**Branch**: feat/sharadar-context-generator

Prior decisions (settled): Engram `architecture/backtest-data-layer` (#2966), `reference/backtest-data-providers` (#2965). Change 1 (`sharadar-sep-adapter`, SEP reader + `--source`) is DONE + archived.

## First change scope (this folder)

Per the slicing below, the **first change = reference-data readers only**: `SharadarTickersReader` + `SharadarActionsReader` sibling adapters + their boundary tests. The pure liquidity-screen domain module, the window builder, the JSON writer, and the CLI generator are FOLLOW-ON changes. This keeps the first change change-1-sized (~600–850 lines) and a clean apply target.

## Current State

- `src/invest/adapters/sharadar_market_data.py` (`SharadarMarketDataReader`): SEP-only, `fetch`/`fetch_range` → `FixtureInputs`. Requires a small pre-known `Universe.symbols`. Generic Nasdaq datatables envelope (`datatable.columns`/`data`, `meta.next_cursor_id`), injected `httpx.Client`, bounded retry (401/403 no-retry; 429/5xx backoff), `MarketDataFetchError` reused from `alpaca_market_data.py`. `.gitignore` already covers `fixtures/snapshots/sharadar/` and `*.sqlite`.
- `src/invest/domain/market_context.py`: frozen value objects `CoverageWindow`, `EligibilityWindow(eligible)`, `BlockerWindow(reason)`, `SymbolContext`, `MarketContext`. Invariants: (1) `BlockerWindow.__post_init__` REJECTS `SYMBOL_INELIGIBLE` — delisting/ineligibility must be an `EligibilityWindow(eligible=False)`, never a blocker; (2) a blocker cannot overlap an ineligible interval; (3) eligibility/blockers nest inside coverage; (4) no overlapping windows within a symbol. Only `CORPORATE_ACTION`/`EARNINGS_CONTEXT_MISSING` are valid blocker reasons — this change has no earnings source, so emits zero `EARNINGS_CONTEXT_MISSING`.
- `src/invest/adapters/backtest_context_json.py` (`BacktestContextJsonReader`): strict Pydantic parser of `market-context-v1` JSON → `MarketContext`. `fixtures/backtest/market-context.json` is today's hand-authored fixture.
- `src/invest/application/backtest_run.py` (`BacktestRun.replay`): calls `market_context.require_complete(replay_dates, universe.symbols)` up front (fail-closed across the full roster), narrows per-day via `eligible_symbols`. `Universe.symbols` is a flat, non-time-varying tuple — point-in-time behavior lives entirely in `MarketContext`.
- `src/invest/adapters/cli.py`: `backtest_main` requires `--market-context <path>` → `BacktestContextJsonReader`. Each entrypoint (`main`/`fetch_main`/`execute_main`/`backtest_main`) is a sibling with its own `_xxx_parser()`; `pyproject.toml [project.scripts]` maps one console script each.
- `tests/test_boundaries.py`: AST-enforced hex purity for `src/invest/domain/*.py`. Its Sharadar-isolation check is HARDCODED to the literal name `SharadarMarketDataReader` — new reader classes are NOT automatically covered; add explicit boundary checks for new reader names.
- Change 1 (`openspec/changes/archive/2026-07-15-sharadar-sep-adapter/`) shipped SEP-only at ~650–900 lines ("High risk", 2 chained PRs), and explicitly deferred extracting shared retry/pagination plumbing (duplication accepted).

## Affected Areas (first change)

- New `src/invest/adapters/sharadar_tickers.py` (`SharadarTickersReader`) — fetch SHARADAR/TICKERS; adapter-side translation of Sharadar `category`/`exchange` vocabulary into plain flags (`is_primary_common_stock`, `is_listed`, `listed_date`, `delisted_date`), keeping domain free of Sharadar literals.
- New `src/invest/adapters/sharadar_actions.py` (`SharadarActionsReader`) — fetch SHARADAR/ACTIONS (splits/dividends/delist); typed events, no OHLC adjustment.
- New `tests/adapters/test_sharadar_tickers.py`, `test_sharadar_actions.py` — mocked-httpx, cursor pagination, validation, retry taxonomy (mirror `test_sharadar_market_data.py`).
- `tests/test_boundaries.py` — add explicit Sharadar-isolation checks for the two new reader class names.
- Do NOT modify `sharadar_market_data.py`, `market_context.py`, `backtest_context_json.py`, `backtest_run.py`, or `backtest_main`.

## Follow-on changes (not this one)

- `src/invest/domain/liquidity_screen.py` (pure, Decimal-only) — price floor, median N-day dollar-volume floor (`price * Decimal(volume)`), primary-common-stock check, IPO seasoning as observed-bar count (not calendar days). All thresholds explicit parameters.
- `src/invest/domain/market_context_builder.py` (pure) — run-length-encode per-day eligibility/blocker decisions into windows; delisting → `EligibilityWindow(eligible=False)`; corporate-action → `BlockerWindow(CORPORATE_ACTION)` filtered out of ineligible windows; merge same-day multi-event actions.
- `BacktestContextJsonWriter` (mirror `SnapshotWriter`) — serialize generated context to `market-context-v1` JSON; reader/`MarketContext`/`BacktestRun` unchanged.
- `invest-generate-context` CLI entrypoint (`generate_context_main`/`_generate_context_parser`).

## Threshold conflict — resolved (not silently picked)

SPEC.md §2.1 "Live universe" (price > $5, dollar volume > $10M) governs the LIVE/paper execution universe — different concept. Research report §6.2 is the source for THIS backtest liquidity screen: primary-listed common stock; price ≥ $10; median 20-day dollar volume ≥ $10M; exclude ETFs/funds/preferred/warrants/recent IPOs; test grid (price 5/10/20; dollar volume 5/10/25M; IPO seasoning 126/252 days). SPEC's $5/$10M is one point on that grid, not a contradiction. **Default to report §6.2 baseline (price ≥ $10, 20-day median dollar volume ≥ $10M, primary common stock, 252-trading-day IPO seasoning); expose every threshold as a parameter.** (Applies to the later liquidity-screen change.)

## Non-obvious finding — two-pass universe (later changes)

Today's `Universe.symbols` is small/pre-known; this feature inverts it: TICKERS discovery (~8,000 listings → ~600–800 survive) → SEP fetch across candidates → liquidity screen → union of ever-eligible symbols becomes the roster → reuse the same SEP bars as backtest input. Operational/design concern for real runs, not for mocked tests.

## Scope / Slicing

Full change 2 ≈ **2000–3000+ authored lines**. Split into two SDD changes, each internally chained:

| Sub-change | Contents | Rough lines |
|---|---|---|
| 2a `sharadar-reference-data-adapter` | TICKERS reader, ACTIONS reader, (+ liquidity screen in the exploration's version) | ~1000–1450 |
| 2b `market-context-generator` | window builder, JSON writer, CLI wiring, e2e test | ~1100–1750 |

**Orchestrator decision**: narrow the FIRST change further to just the **TICKERS + ACTIONS readers** (~600–850 lines, change-1-sized), deferring the liquidity screen to its own change. 2b follows after.

## Risks

- `tests/test_boundaries.py` Sharadar-isolation guard is hardcoded to `SharadarMarketDataReader` — new readers need explicit boundary tests or they silently escape it.
- Real TICKERS/ACTIONS pagination cardinality unverified against the live API (same open question as change 1's `MAX_PAGES`).
- Broad ~8,000-ticker data volume (later changes) needs a design-phase sizing/cadence decision.

## Ready for Proposal

Yes — for the first change (`sharadar-reference-data-adapter`, TICKERS + ACTIONS readers). Liquidity screen, builder, writer, and CLI follow as later changes.
