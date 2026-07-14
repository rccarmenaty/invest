# Exploration: Sharadar SEP survivorship-free backtest data layer

**Umbrella feature**: `sharadar-sep-data-layer` (this doc) → recommended first change: `sharadar-sep-adapter`
**Date**: 2026-07-14
**Engram**: `sdd/sharadar-sep-data-layer/explore` (obs #2980)
**Branch**: feat/sharadar-sep-data-layer

Prior decisions (settled): Engram `architecture/backtest-data-layer` (#2966 — SEP-only, liquidity-screen universe, SQLite snapshot), `reference/backtest-data-providers` (#2965 — confirmed SEP schema).

## Current State

Hexagonal package `src/invest/`: `domain/` (pure, Decimal/date-only, AST-enforced by `tests/test_boundaries.py`), `application/` (orchestration + `ports.py` Protocols), `adapters/` (IO). Nothing Sharadar-related exists yet.

1. `adapters/alpaca_market_data.py` (239 lines) is the adapter template: `fetch`/`fetch_range` → `_paginate` → `_send_with_retry` (3 attempts, exp backoff capped 4s, honors `Retry-After`, 401/403 no-retry, 429/5xx retried), `MAX_PAGES=64`. Credentials via `os.environ.get(...)` only in the request builder. Pydantic models validate raw JSON + OHLC sanity. `httpx.Client` injected → fully mockable; one `@pytest.mark.live`-gated smoke test. `SnapshotWriter` does atomic versioned JSON writes with sha256 provenance, fails closed on missing symbols. Test file is 487 lines — the whole shape is testable without live calls.
2. `application/ports.py::MarketDataReader` = `fetch(universe, as_of) -> FixtureInputs` only; `fetch_range` is duck-typed, not in the Protocol. A Sharadar reader needs no Protocol change.
3. `adapters/cli.py::backtest_main` branches on `args.bars is not None` (fixture) vs `args.start/args.end` (Alpaca) — **no `--source` flag**; source is inferred implicitly. Many `tests/adapters/test_cli_backtest.py` tests rely on this implicit inference with no `--source`.
4. `tests/test_boundaries.py` enforces: domain has zero adapter/SDK/wall-clock imports; `market_context`/`strategy` flags exist only on `_backtest_parser`; the backtest path never references broker symbols (AST checker catching import-evasion). A new `--source`-is-backtest-only boundary test is expected.
5. `domain/market_context.py` (pure frozen dataclasses): `CoverageWindow`/`EligibilityWindow`/`BlockerWindow`. **Invariant**: `BlockerWindow.__post_init__` rejects `SYMBOL_INELIGIBLE` as a blocker reason. `BacktestRun.replay()`'s day-by-day `eligible_symbols` filtering is how survivorship-free exclusion already happens — by removing symbols from a day's replay universe, not via scanner changes.
6. `adapters/backtest_context_json.py` (87 lines) is the only way `MarketContext` is built today — parses hand-authored `market-context.json` (schema `market-context-v1`). Smallest integration seam for a generator to target unchanged.
7. `domain/models.py::DailyBar` has one OHLCV shape — no adjusted/unadjusted concept in the domain today.
8. No `sqlite3` usage exists; stdlib `sqlite3` is NOT in `FORBIDDEN_IMPORT_ROOTS` (only `sqlalchemy` is) → safe zero-dependency choice for adapters.
9. `.gitignore` has NO entry for a snapshot dir or `*.sqlite` — a gap to close before any change writes real snapshots (licensed Sharadar data must never be committable).
10. SHARADAR/SEP datatables paginate via cursor (`meta.next_cursor_id`), 10,000-row limit per call — structurally different from Alpaca's `next_page_token` body field. Retry/backoff/httpx-injection machinery is reusable; the pagination/response-model code is NOT a drop-in copy.
11. Research report §6.2 baseline screen: primary-listed common stock, price ≥ $10 (test 5/10/20), median 20-day dollar volume ≥ $10M (test 5/10/25M), IPO seasoning 126/252 days. **Conflicts numerically** with SPEC.md §2.1 (price > $5, dollar volume > $10M) — must be resolved in change 2, not silently defaulted.
12. Env var name for the Nasdaq key unconfirmed (`.env` deliberately not opened; key never read/printed).

## Affected Areas

- `adapters/alpaca_market_data.py` — pattern template (not modified)
- `tests/adapters/test_alpaca_market_data.py` — test-pattern template
- `application/ports.py` — no change (`fetch_range` stays duck-typed)
- `adapters/cli.py::backtest_main/_backtest_parser` — additive, default-preserving `--source`
- `tests/adapters/test_cli_backtest.py` — `--source sharadar` tests + byte-identical-default regression
- `tests/test_boundaries.py` — `--source`-is-backtest-only parity test
- `domain/models.py::DailyBar` — decision: reuse unchanged (adjust adapter-side) vs extend
- `domain/market_context.py` — `BlockerWindow` invariant constrains delisting modeling (eligibility boundary, not blocker) — mostly change 2
- `adapters/backtest_context_json.py` + `fixtures/backtest/market-context.json` — smallest seam for a screen generator (change 2)
- `.gitignore` — missing snapshot/`*.sqlite` protection
- `pyproject.toml` — no new dependency (stdlib `sqlite3` + existing `httpx`/`pydantic`)

## Scope / Slicing

Full 5-piece feature ≈ **2000–3200+ authored lines** = 2.5–4× the 800-line budget. Split into **3 sequenced changes** (matches repo precedent: market-data-adapter → point-in-time-market-context → momentum-selection-scanner were separately sequenced):

- **Change 1 — `sharadar-sep-adapter`** (propose now, ~650–900 lines): `SharadarMarketDataReader.fetch/fetch_range` against SEP only (no TICKERS/ACTIONS) with cursor pagination; OHLC adjustment as a pure Decimal helper (factor = closeadj/close, applied adapter-side before building `DailyBar`, `DailyBar` unchanged); additive `--source {fixture,alpaca,sharadar}` defaulting to today's implicit inference; add `.gitignore` snapshot/`*.sqlite` protection. Excludes TICKERS/ACTIONS, liquidity screen, SQLite storage.
- **Change 2 — liquidity-screen context generator** (~700–1200 lines, likely needs its own chaining): SEP master + TICKERS + ACTIONS → eligibility/coverage/blocker windows consumed by existing `MarketContext`. Resolves the §2.1-vs-§6.2 threshold conflict. Delisting modeled as an eligibility-window boundary (not a blocker, per the invariant).
- **Change 3 — local versioned SQLite snapshot store**: evolve `SnapshotWriter` to SQLite (bars/actions/tickers, `(symbol,date)` index, one hash-stamped `.sqlite` per snapshot version), backtest reads a frozen snapshot vs live fetch.

## Change 1 forecast

- Rough estimate ~650–900 authored lines (source ~250–350, tests ~400–550).
- 400-line budget risk: Medium–High → chained PRs likely if real count > ~700 once `sdd-tasks` scopes it.
- Decisions to settle in propose/design: env var name (confirm without printing), whether change 1 carries any snapshot writer or defers all persistence to change 3 (recommend: defer; fetch → in-memory `FixtureInputs`, reuse existing JSON `SnapshotWriter` if any freeze is needed).

## Risks

- SPEC §2.1 vs report §6.2 threshold conflict — resolve explicitly in change 2.
- `BlockerWindow` forbids `SYMBOL_INELIGIBLE` as a blocker → delisting = eligibility-window boundary (change 2).
- Nasdaq env var name unconfirmed (`.env` not opened).
- `.gitignore` has zero snapshot/`*.sqlite` protection today — add in change 1.
- Cursor-based SEP pagination ≠ drop-in copy of Alpaca's token pagination.
- Change 2 very likely exceeds the 800-line budget on its own.

## Ready for Proposal

Yes — for the narrowed change 1 (`sharadar-sep-adapter`). Changes 2 and 3 proposed separately after change 1 lands.
