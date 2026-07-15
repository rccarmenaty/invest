# Proposal: Sharadar SEP Market Data Adapter

## Intent

Backtests currently fetch bars from Alpaca, which cannot provide survivorship-free history. Add a backtest-only `SharadarMarketDataReader` against the SHARADAR/SEP datatable so replays use point-in-time, adjustment-correct daily bars. This is change 1 of 3 in the `sharadar-sep-data-layer` feature (adapter → liquidity-screen context generator → SQLite snapshot store).

## Scope

### In Scope
- `SharadarMarketDataReader` sibling of `AlpacaMarketDataReader`: `fetch(universe, as_of)` and `fetch_range(universe, start, end)` → `FixtureInputs`, SEP table only (`data.nasdaq.com/api/v3/datatables/SHARADAR/SEP`), cursor pagination (`meta.next_cursor_id`, 10,000-row pages, bounded page loop), reusing the retry/backoff/injected-httpx pattern.
- OHLC adjustment as a pure Decimal helper: per-bar factor = `closeadj/close` applied to open/high/low adapter-side before constructing `DailyBar`. `DailyBar` unchanged.
- Additive `--source {fixture,alpaca,sharadar}` on `_backtest_parser`; default preserves today's implicit inference (existing CLI tests stay byte-identical).
- `.gitignore` entries for the future snapshot dir and `*.sqlite` (protect licensed data before change 3).

### Out of Scope
- TICKERS/ACTIONS tables and the liquidity-screen context generator (change 2).
- SQLite snapshot store / any new persistence — fetch returns in-memory `FixtureInputs` (change 3).
- Execution/broker paths, scanner, sizing, `market_context` domain, replay engine.
- Any live-trading use — Sharadar is backtest-only.

## Proposal Question Round

Scope boundary user-approved upstream; recorded assumptions: API key read from `NASDAQ_DATA_LINK_API_KEY` (standard `nasdaqdatalink` convention; user must align `.env`; key never read or printed by tooling), persistence fully deferred to change 3, tests use mocked httpx with any live smoke `@pytest.mark.live`-gated.

## Capabilities

### New Capabilities
- `sharadar-sep-market-data`: backtest-only SEP bar fetching with cursor pagination, split/dividend-adjusted OHLC, and fail-closed data validation.

### Modified Capabilities
- `trading-system`: backtest CLI gains explicit `--source` selection with default-preserving inference; Sharadar path must never reference `BrokerPort` (new boundary test).

## Approach

Mirror `alpaca_market_data.py`: injected `httpx.Client`, `_send_with_retry` (exp backoff, `Retry-After`, 401/403 no-retry), Pydantic response models with OHLC sanity checks, `MAX_PAGES` bound — but with SEP cursor pagination, not token pagination. Adjustment stays a pure Decimal function so momentum signals use adjusted prices without touching the domain. Strict TDD; hexagonal purity preserved.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `src/invest/adapters/sharadar_market_data.py` | New | Reader, pagination, adjustment helper |
| `src/invest/adapters/cli.py` | Modified | `--source` flag, default-preserving |
| `tests/adapters/test_sharadar_market_data.py` | New | Mocked-httpx suite + live-gated smoke |
| `tests/adapters/test_cli_backtest.py` | Modified | `--source sharadar` + default regression |
| `tests/test_boundaries.py` | Modified | Sharadar-is-backtest-only guard |
| `.gitignore` | Modified | Snapshot dir + `*.sqlite` |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| ~650–900 authored lines exceeds 400-line budget | High | `sdd-tasks` must plan chained PRs |
| Cursor pagination diverges from Alpaca template | Med | Dedicated pagination tests, bounded loop |
| Env var name mismatch with user's `.env` | Low | Documented name; fail closed with clear error |

## Rollback Plan

Revert new adapter module, tests, CLI flag, and `.gitignore` lines. Default CLI behavior is unchanged, so rollback restores exact prior behavior; no state or data migration.

## Dependencies

- Nasdaq Data Link API key in `NASDAQ_DATA_LINK_API_KEY` (live smoke only; CI uses mocks).
- Settled decisions: Engram #2966 (SEP-only architecture), #2965 (SEP schema).

## Success Criteria

- [ ] `fetch`/`fetch_range` return `FixtureInputs` with adjusted OHLC bars from mocked SEP responses, Decimal-only.
- [ ] Cursor pagination follows `meta.next_cursor_id` and stops at bound; partial/missing data fails closed.
- [ ] `--source` default keeps every existing CLI test passing unmodified.
- [ ] Boundary test proves the Sharadar path never touches `BrokerPort`.
- [ ] No secrets in repo; `.gitignore` protects snapshots and `*.sqlite`.
