# Proposal: Reconcile Null SHARADAR/SEP Volume

## Intent

Real SHARADAR/SEP no-trade rows can contain `volume=null` while ticker, date, OHLC, and adjusted close remain valid. The reader currently rejects the row as `malformed-response`, blocking otherwise complete point-in-time backtest data. Reconcile only this provider sentinel to exact Decimal zero and retain the bar. SEP remains authoritative only for this backtest adapter; paper/live gates and broker/account rules are unchanged.

## Scope

### In Scope
- Characterize the real BAYA-shaped row at the public `fetch_range` seam.
- Normalize exact SEP `volume=None` to `Decimal("0")` at `_SepRow` validation.
- Preserve the bar, full XNYS coverage, exact non-null volumes, and fail-closed validation.
- Minimal adjusted-OHLC re-envelope in `_rows_to_bars`: after exact Decimal adjustment, `high := max(high, open, close, low)` and `low := min(low, open, close, high)` so Decimal-drift bars (live GSBD 2024-12-13) satisfy the OHLC envelope and `JsonFixtureReader` validation.
- Accept exact-zero values on valued ACTIONS rows in `sharadar_actions.py` (guard narrowed to `value < 0`), retaining live zero-amount dividends (RVPH 2026-02-23) as typed events.

> Scope amended during review (REL-102): the adjusted-OHLC re-envelope and the ACTIONS zero-value acceptance ship in this change's diff and are formalized into this change rather than reverted or split out.

### Out of Scope
- Normalizing missing, empty, NaN, negative, or non-volume invalid fields.
- Changing broad parse-error masking or auditing all SEP/ACTIONS nullability.
- Changing the adjustment factor/formula (`closeadj/close` exact Decimal) beyond the minimal post-adjustment re-envelope above.
- Changing pagination, chunking, domain models, fixtures, or live/execution paths.

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
| `src/invest/adapters/sharadar_market_data.py` | Modified | Provider-boundary normalization plus minimal adjusted-OHLC re-envelope. |
| `tests/adapters/test_sharadar_market_data.py` | Modified | Null-volume regression, fail-closed guards, and envelope-clamp/exact-product pins. |
| `openspec/specs/sharadar-sep-market-data/spec.md` | Modified | Delta defines the reconciliation and re-envelope contracts. |
| `src/invest/adapters/sharadar_actions.py` | Modified | Valued-action guard narrowed to reject only negative values (review-absorbed). |
| `tests/adapters/test_sharadar_actions.py` | Modified | Exact-zero valued-action regressions. |
| `openspec/specs/sharadar-actions-reference-data/spec.md` | Modified | Zero-value acceptance documented in-place with a Previously note. |

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
