# Proposal: Reconcile SharadarActionsReader with the Real SHARADAR/ACTIONS Schema

## Intent

`SharadarActionsReader` was built against synthetic fixtures and cannot parse the live Nasdaq Data Link ACTIONS payload: (1) `_ACTION_KINDS` maps only 4 literals, two of which (`delisting`, `tickerchange`) do not exist in real data, and any unmapped row raises and kills the entire multi-page fetch; (2) an `isinstance(raw_value, float)` guard rejects float values, but the real API sends every `value` as a JSON float. Consequence: no real ACTIONS pull can succeed, blocking the whole `invest-generate-context` broad-market pull and the backtest.

## Scope

### In Scope
- Map these literals to normalized actions (each can produce a same-day entry blocker): `split`, `adrratiosplit`, `dividend`, `spinoffdividend`, `delisted`, `regulatorydelisting`, `voluntarydelisting`, `bankruptcyliquidation`, `tickerchangeto`, `tickerchangefrom`.
- Explicitly skip: `listed`, `relation`, `acquisitionby`, `acquisitionof`, `mergerto`, `mergerfrom`, `spinoff`, `spunofffrom`.
- Skip-unknown policy: any literal outside the mapped set is silently dropped per-row (forward-compatible against provider vocabulary drift). Flips the existing reject-on-unknown test (`("merger","1")`).
- Remove the float-value guard; rely on pydantic v2 float→Decimal coercion (str-based, precision-preserving) plus existing finite/positive checks — the exact `_SepRow` precedent in `sharadar_market_data.py`.
- Test-first rewrite of `tests/adapters/test_sharadar_actions.py` against real literals and payload shapes (strict TDD).

### Out of Scope
- Modeling merger/spinoff/acquisition semantics or ticker-continuity across renames.
- Making `market_context_builder.py` kind-aware (it is kind-blind today: only `effective_date` + eligibility drive blockers; splits are price-adjusted via SEP `closeadj`).
- Any TICKERS, SEP, domain, or application-layer changes.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `sharadar-actions-reference-data`: real-vocabulary mapping, skip-unknown row policy, float value acceptance.

## Approach

Minimal schema-parity fix (exploration Approach 1), confined to `src/invest/adapters/sharadar_actions.py` + its test file. Because the domain builder never branches on `kind`, the mapped-literal set IS the blocker policy — hence the explicit mapped/skipped split above. Open design detail for sdd-design: fold the 10 mapped literals onto the existing closed 4-kind `SharadarActionKind` enum (delisting variants → `delisted`; directional `tickerchangeto`/`tickerchangefrom` → one kind, losing directionality) versus extending the enum for directional ticker-change.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `src/invest/adapters/sharadar_actions.py` | Modified | Literal map, skip-unknown, float guard removal |
| `tests/adapters/test_sharadar_actions.py` | Modified | Rewrite wrong fixture assumptions |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| High-frequency noise (`listed`, `relation`) becoming spurious blockers | High if mismapped | Explicit skip list; tests assert dropped |
| Skip-unknown hides genuinely new relevant literals | Low | Bounded explicit mapped set; revisit when builder becomes kind-aware |
| Float→Decimal precision loss | Low | Live-shaped fixture test during apply |

## Rollback Plan

Revert the single adapter + test-file commit; no schema, domain, or consumer changes to unwind.

## Dependencies

- Shipped TICKERS null-field fix on `main`; existing SEP/`closeadj` adjustment path.

## Success Criteria

- [ ] A real `invest-generate-context` broad-market pull for 2025-07-16..2026-07-16 succeeds end-to-end. (Not verified during apply — requires a live `NASDAQ_DATA_LINK_API_KEY` and network access, which the apply sandbox does not have. Remains an open manual verification step.)
- [x] Unknown literals never abort a fetch; skipped literals produce no normalized actions.
- [x] Float values parse to exact Decimals; all adapter tests pass rewritten against real literals.
