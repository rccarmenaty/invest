# Proposal: Reconcile Null SHARADAR/SEP Volume

## Intent

Real SHARADAR/SEP no-trade rows can contain `volume=null` while ticker, date, OHLC, and adjusted close remain valid. The reader currently rejects the row as `malformed-response`, blocking otherwise complete point-in-time backtest data. Reconcile only this provider sentinel to exact Decimal zero and retain the bar. SEP remains authoritative only for this backtest adapter; paper/live gates and broker/account rules are unchanged.

## Scope

### In Scope
- Characterize the real BAYA-shaped row at the public `fetch_range` seam.
- Normalize exact SEP `volume=None` to `Decimal("0")` at `_SepRow` validation.
- Preserve the bar, full XNYS coverage, exact non-null volumes, and fail-closed validation.

### Out of Scope
- Normalizing missing, empty, NaN, negative, or non-volume invalid fields.
- Changing broad parse-error masking or auditing all SEP/ACTIONS nullability.
- Changing adjustment, pagination, chunking, domain models, fixtures, or live/execution paths.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sharadar-sep-market-data`: define volume-only null reconciliation for legitimate no-trade bars while preserving strict validation for every other row shape.

## Approach

Use strict TDD: first replay the real one-day SEP row and require a retained `DailyBar` with exact zero volume. Then add a narrowly named Pydantic `mode="before"` validator on `_SepRow.volume` that maps only `None` to `Decimal(0)` and delegates every other value to existing Decimal and non-negative validation.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/invest/adapters/sharadar_market_data.py` | Modified | Provider-boundary normalization only. |
| `tests/adapters/test_sharadar_market_data.py` | Modified | Null-volume regression and fail-closed guards. |
| `openspec/specs/sharadar-sep-market-data/spec.md` | Modified | Delta defines the reconciliation contract. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Invalid data is mistaken for no trades | Low | Match exact `None` only. |
| Bar is dropped and coverage fails | Low | Assert bar retention through `fetch_range`. |
| Fractional or negative behavior regresses | Low | Retain exactness and rejection tests. |

## Rollback Plan

Revert the validator, regression tests, and delta spec together. No migration or persisted-data rollback is required; null-volume rows return to existing fail-closed behavior.

## Dependencies

- Existing Pydantic validation, XNYS calendar coverage, and pytest harness.
- Confirmed SEP example: BAYA on 2024-12-31.

## Success Criteria

- [ ] The BAYA-shaped row is retained with `volume == Decimal("0")`.
- [ ] Integer and fractional volumes remain exact; negative volume still fails closed.
- [ ] Missing or non-volume invalid fields remain `malformed-response` with no partial bars.
- [ ] Backtest-only, paper-first, and no-live-before-validation boundaries remain unchanged.
