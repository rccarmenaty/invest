# Design: Reconcile Null SHARADAR/SEP Volume

## Technical Approach

Keep reconciliation inside the private SEP ingestion module. Add a Pydantic `field_validator("volume", mode="before")` on `_SepRow` that returns `Decimal("0")` only when the raw value `is None`; every other value passes unchanged into the existing required `Decimal = Field(ge=0)` validation. `_rows_to_bars`, `DailyBar`, coverage validation, public reader methods, and downstream callers remain unchanged.

## Architecture Decisions

| Decision | Alternatives | Tradeoff and rationale |
|---|---|---|
| Normalize at the `_SepRow.volume` provider seam | Normalize in `_rows_to_bars`; make domain volume optional | This gives the SEP adapter locality: one private rule reconciles one provider representation before canonical validation. It avoids leaking nullability into the domain or hiding field policy in generic row mapping. |
| Match exact `None` only | Coerce any falsey/invalid value; assign a default | `value is None` accepts the observed no-trade sentinel without accepting missing fields, empty strings, NaN, negative values, or malformed values. No default is added, so an absent volume still fails. |
| Retain the row with exact Decimal zero | Drop the row; keep rejecting it | Retention preserves the complete XNYS-session invariant. Dropping it would convert valid no-trade data into incomplete date coverage. `Decimal("0")` preserves the existing domain type and exactness. |
| Preserve current error masking | Expose Pydantic parse details | Keeping `_fetch_chunk`'s `malformed-response` contract makes this a narrow data reconciliation. Better diagnostics are separate scope. |

## Data Flow

```text
SEP JSON row
  -> _SepResponse structural validation
  -> _rows_to_bars column mapping
  -> _SepRow pre-validation: volume None -> Decimal("0")
  -> existing Decimal/non-negative and OHLC validation
  -> DailyBar
  -> complete-universe and complete-XNYS-date validation
  -> FixtureInputs
```

All invalid paths continue through `_fetch_chunk` to `MarketDataFetchError("malformed-response")`; no partial bars escape.

## File Changes

| File | Action | Description |
|---|---|---|
| `tests/adapters/test_sharadar_market_data.py` | Modify | Add the public-seam RED regression for the BAYA-shaped row and a non-volume-null guard where existing coverage is insufficient. |
| `src/invest/adapters/sharadar_market_data.py` | Modify | Import `field_validator` and add the exact-`None` private volume reconciliation. |

No domain, port, CLI, fixture, pagination, adjustment, scanner, broker, or execution file changes are planned.

## Interfaces / Contracts

There are no new or changed public interfaces. `_SepRow` remains private and presents the same canonical post-validation interface: required, non-negative `Decimal` volume. `SharadarMarketDataReader.fetch`, `fetch_range`, `FixtureInputs`, and `DailyBar` retain their signatures and shapes. The only implementation contract added is: an explicit raw SEP `volume=None` means exact zero; missing or otherwise invalid input does not.

## Testing Strategy

Strict TDD uses the existing public `fetch_range` seam with `httpx.MockTransport`:

1. **RED**: replay `BAYA`, `2024-12-31`, valid OHLC/closeadj, and `volume=None` for that one-session XNYS range. Assert one retained bar, the original symbol/date/prices, `volume == Decimal("0")`, and `isinstance(volume, Decimal)`. Record the focused test failing with `malformed-response` before production edits.
2. **GREEN**: add only the before-validator; rerun the focused regression and record its pass.
3. **REFACTOR/guards**: run adapter tests. Existing fractional-volume, negative-volume, short-row/missing-value, ordering, pagination, and coverage tests must remain green. Add or retain a case proving `open=None` still returns `malformed-response` and no partial bars.

Evidence commands:

```bash
uv run pytest tests/adapters/test_sharadar_market_data.py -k null_volume
uv run pytest tests/adapters/test_sharadar_market_data.py
uv run pytest
uv run ruff check src tests
```

## Validation Invariants

- Only explicit volume `None` changes meaning; non-null values follow existing Decimal coercion and `ge=0` validation unchanged.
- Missing volume, negative volume, null/malformed price fields, impossible OHLC, malformed columns/rows, and incomplete coverage fail closed without partial results.
- The retained zero-volume bar participates in duplicate detection, adjustment, sorting, chunk merging, and full-calendar coverage exactly like any other bar.
- SEP remains a backtest adapter; paper-first and no-live-before-validation gates are untouched.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary changes.

## Migration / Rollout / Rollback

No migration, feature flag, or persisted-data rewrite is required. Deploy with the focused and full test evidence above. Roll back atomically by reverting the validator and its tests/spec delta; explicit null-volume rows then return to the prior fail-closed behavior. No stored data needs restoration.

## Open Questions

None.
