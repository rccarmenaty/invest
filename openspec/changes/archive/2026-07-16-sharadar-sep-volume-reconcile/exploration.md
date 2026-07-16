# Exploration: Real SHARADAR/SEP Volume Mismatch

## Trigger

User asked to run a backtest. The live `invest-generate-context --start 2025-07-16 --end 2026-07-16`
pull returned a generic `{"reason": "malformed-response"}`. Root-caused by isolating each reader
(sandbox disabled so `.env` + network are reliable) and dumping raw payload rows.

## Findings

### Reader status against real data (this pull)
- **TICKERS**: OK — 62,506 rows parsed.
- **ACTIONS**: OK — after two fixes on branch `feat/sharadar-actions-reconcile`
  (schema literals + float guard; then delisting/ticker-change value handling).
- **SEP**: FAILS — `fetch_range` aborts with `malformed-response`.

### SEP root cause
`_SepRow.volume: int = Field(ge=0)` (sharadar_market_data.py:46), but real SEP `volume` is a
fractional float. Pydantic rejects non-integer floats for an `int` field. `fetch_range` catches
`(ValidationError, ValueError, TypeError)` and re-raises `MarketDataFetchError("malformed-response")
from None` (line 99-100), so one bad row kills the whole universe fetch and the original cause is
hidden.

Sample offending rows (all bucketed as `volume`):

```
BCLI 2024-09-30  open=3.339 high=3.784 low=3.18  close=3.454 volume=48037.936 closeadj=3.454
BCLI 2024-09-27  open=3.601 high=3.72  low=3.301 close=3.337 volume=36064.402 closeadj=3.337
BCLI 2024-09-26  ...                                          volume=11000.267
```

Fractional volume is the split/dividend-adjusted share count Sharadar reports in the `volume`
column. Prevalence: **536 offending rows in the first 60 of 456 cohorts** scanned — pervasive,
not an edge case.

### Column shape confirmed
SEP datatable columns: `ticker, date, open, high, low, close, volume, closeadj`. Prices arrive as
floats and already coerce to `Decimal` fine (`gt=0`). Only `volume` breaks, purely on the `int` type.

## Architectural framing

Corrected after user pushback ("how was this not treated as an adapter?"): this is an **adapter**
concern. The adapter (`SharadarMarketDataReader` / `_SepRow` / `_rows_to_bars`) is the
anti-corruption boundary whose job is to translate the external Sharadar schema into the domain
shape. Fractional external volume should be absorbed there — accept `Decimal`, quantize to the
domain's `int` — leaving `DailyBar` and the domain untouched. Widening the domain to `Decimal`
volume was rejected: volume only feeds `close * volume` for the dollar-volume median, where the
fractional part is noise against a $10M floor.

## Pattern

Third distinct real-vs-synthetic-fixture schema bug in the Sharadar data layer (after two in
ACTIONS). The layer was built entirely on synthetic fixtures and does not survive real data.
Expect the possibility of further downstream reconciles (context builder, dedup, calendar
completeness) once SEP parses; those should be tracked as separate changes.

## Reproduction scripts (ephemeral, in job tmp — not committed)
- Isolate readers with `.env` loaded and surface hidden `MarketDataFetchError` detail.
- Scan SEP cohorts, validate each raw row against `_SepRow`, bucket the failures.
