# Design: Sharadar SEP Market Data Adapter

## Technical Approach

Add `SharadarMarketDataReader` as a sibling of `AlpacaMarketDataReader` in a new `adapters/sharadar_market_data.py`. It reuses the proven injected-`httpx.Client` + `_send_with_retry` machinery (exp backoff, `Retry-After`, 401/403 no-retry, `MAX_ATTEMPTS=3`) but replaces token pagination with SEP **cursor** pagination. Pydantic models validate the datatable envelope; a pure Decimal helper adjusts OHLC before building the unchanged `DailyBar`. `fetch`/`fetch_range` return in-memory `FixtureInputs` — no persistence (deferred to change 3). CLI gains an additive, default-preserving `--source`. Domain stays pure/clock-free (specs sharadar-sep-market-data §1-7, trading-system §1-2).

## Architecture Decisions

| Decision | Rejected alternative | Rationale |
|---|---|---|
| Reuse `MarketDataFetchError` by importing it from `alpaca_market_data` | New error type; extract shared module now | CLI's single `except MarketDataFetchError` already handles both readers; adapter→adapter import is allowed; extraction is churn best deferred |
| Column-name→index map built from response `datatable.columns` | Positional read of fixed `qopts.columns` order | Robust to column reordering/extras; fails closed if a required column is missing |
| `DailyBar.close = closeadj` (adjusted close), O/H/L scaled by `closeadj/close` | Keep raw `close`, only scale O/H/L | Keeps the bar internally consistent: uniform positive factor preserves `low<=open,close<=high`; `closeadj` *is* the adjusted close. Volume left raw (not requested) |
| `--source` validated in `backtest_main` (no argparse `choices`) returning int `2` | `choices=(...)` raising `SystemExit(2)` | Mirrors `--strategy`: machine-readable `{"reason":"source-invalid"}`, exit non-zero, before any fetch/replay (trading-system §1) |
| Source resolution falls back to today's inference when `--source` absent | Branch rewrite | Preserves byte-identical default: `None`→`fixture` if `--bars` else `alpaca` |
| Bounded `MAX_PAGES` cursor guard (e.g. 512) | Alpaca's 64 | 10k-row pages over a screened universe×range need more headroom; still fails closed (`malformed-response`) if cursor stays non-null at the bound |

## Data Flow

    invest-backtest --source sharadar --start --end --universe
        │  resolve source → validate (source-invalid if unknown)
        ▼
    SharadarMarketDataReader.fetch_range(universe, start, end)
        │  loop: GET SHARADAR/SEP.json (qopts.cursor_id) ─▶ _send_with_retry
        │  Pydantic _SepResponse → column map → _SepRow(gt=0 prices)
        │  _adjust_ohl(raw, close, closeadj) → DailyBar(close=closeadj)
        │  follow meta.next_cursor_id until null | fail at MAX_PAGES
        ▼
    symbol-missing guard (name absent symbols) ─▶ symbol-missing-at-fetch
        ▼
    FixtureInputs (symbol+date sorted) → unchanged BacktestRun.replay

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/invest/adapters/sharadar_market_data.py` | Create | Reader, cursor pagination, Pydantic SEP models, pure `_adjust`/`_daily_bar` helper |
| `src/invest/adapters/cli.py` | Modify | `--source` arg (default `None`, no `choices`), `BACKTEST_SOURCES`, resolution + `source-invalid` error |
| `tests/adapters/test_sharadar_market_data.py` | Create | MockTransport suite + `@pytest.mark.live` smoke |
| `tests/adapters/test_cli_backtest.py` | Modify | `--source sharadar` routing + byte-identical default regression + `source-invalid` |
| `tests/test_boundaries.py` | Modify | `--source` backtest-only parity + Sharadar-not-in-execution/broker/scanner guard |
| `.gitignore` | Modify | `fixtures/snapshots/sharadar/` and `*.sqlite` |

## Interfaces / Contracts

Endpoint `https://data.nasdaq.com/api/v3/datatables/SHARADAR/SEP.json`. Params: `ticker` (comma-join), `date.gte`/`date.lte` (ISO), `qopts.columns=ticker,date,open,high,low,close,volume,closeadj`, `qopts.cursor_id` (subsequent pages), `api_key=os.environ["NASDAQ_DATA_LINK_API_KEY"]` set only in the request builder, never logged. Missing/empty key → `auth-failure` before any request.

Response models: `_SepResponse{ datatable:{ columns:[{name}], data:[[...]] }, meta:{ next_cursor_id } }`; each row → `_SepRow` (Decimal prices `gt=0`, `closeadj gt=0`, `volume ge=0`). Adjustment: `_adjust(raw, close, closeadj) = raw * (closeadj/close)`; `closeadj==close` yields exactly `Decimal("1")` so O/H/L are unchanged.

Error taxonomy (`MarketDataFetchError`, CLI exit 2): `auth-failure` (missing key, 401/403); `malformed-response` (empty/schema-invalid body, missing column, unbounded pagination past `MAX_PAGES`); `symbol-missing-at-fetch` (named absent symbols); `rate-limited` (429 exhausted); `network-failure` (5xx/timeout exhausted).

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Single/multi-page cursor merge; unbounded→`malformed-response`; adjust math + `closeadj==close` identity; missing key→`auth-failure`; 401→no-retry; 429/5xx bounded retry with injected no-op sleep; missing symbol; determinism/sort | `httpx.MockTransport` (no new dep), injected `sleep` |
| CLI | `--source sharadar` routes to `fetch_range`; byte-identical default (no `--source`); unknown→`source-invalid` exit 2 | `_backtest_parser`/`backtest_main` with MockTransport reader |
| Boundary | `--source` only on backtest parser; Sharadar never referenced by execute/scan/broker | Extend `tests/test_boundaries.py` (AST) |
| Smoke | Real tiny SEP fetch | `@pytest.mark.live`, skipped unless key set |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, or executable-file classification. Adds one outbound HTTPS client; secrets are env-only reads, never logged/persisted, covered by boundary + redaction tests.

## Migration / Rollout

No data migration. Rollback removes the new module/tests, the `--source` flag, and the two `.gitignore` lines; default CLI behavior is unchanged.

## Slicing Note (for sdd-tasks)

Forecast ~650–900 authored lines exceeds the 400-line budget (**risk: High**). Recommend chained PRs: (1) adapter + reader tests; (2) `--source` CLI wiring + CLI/boundary tests + `.gitignore`. Each slice is independently verifiable and revertible.

## Open Questions

- [ ] `MAX_PAGES` exact value — confirm during apply against a realistic universe×range (guard-only; does not affect correctness).
