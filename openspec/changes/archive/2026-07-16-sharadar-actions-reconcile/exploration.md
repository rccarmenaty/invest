# Exploration: Reconcile SharadarActionsReader with the real SHARADAR/ACTIONS API schema

**Change**: `sharadar-actions-reconcile`

## Current State

**Bug 1 — action-vocabulary mismatch** (`src/invest/adapters/sharadar_actions.py:16-21,68-73,143-145`): `SharadarActionKind` defines only `split`/`dividend`/`delisting`/`ticker-change`; `_ACTION_KINDS` maps only literals `split`, `dividend`, `delisting`, `tickerchange`. Line 143-145 raises `ValueError("unsupported ACTIONS action")` on any unmapped row, which propagates up through `fetch()` (line 98) as `MarketDataFetchError("malformed-response")` and kills the **entire multi-page fetch**. Real API literals: `dividend`, `listed`, `relation`, `delisted`, `split`, `tickerchangeto`, `tickerchangefrom`, `acquisitionby/of`, `regulatorydelisting`, `bankruptcyliquidation`, `adrratiosplit`, `spinoff`, `spunofffrom`, `voluntarydelisting`, `spinoffdividend`, `mergerto/from`. Only `split`/`dividend` overlap; `delisting`/`tickerchange` (the code's literals) don't exist in real data — the real ones are `delisted`/`tickerchangeto`/`tickerchangefrom`.

**Bug 2 — float-value guard** (lines 58, 131-133): `_ActionRow.value: Decimal | None` would coerce floats fine via pydantic, but `_rows_to_actions` raises `ValueError("ACTIONS values must not be floats")` on `isinstance(raw_value, float)` before that coercion matters — and the real API sends every value as JSON float. Same failure mode as Bug 1.

**Precedent** (`src/invest/adapters/sharadar_market_data.py:38-47`): `_SepRow` declares `Decimal = Field(gt=0)` fields directly with **no float guard at all** — pydantic coercion + `Field(gt=0)`/`model_validator` do all validation. This is the pattern to replicate for Bug 2.

**Downstream — key non-obvious finding**: `market_context_builder.py::_build_blockers` (lines 131-143) is **completely kind-blind**. It reads `action.effective_date` and eligibility only — `action.kind` is never inspected there or anywhere in the domain layer. Any action, regardless of kind, becomes a same-day `CORPORATE_ACTION` blocker iff that day is otherwise eligible. No price adjustment happens from `split` values — SEP's `closeadj` already bakes in adjustment (`sharadar_market_data.py:148-153,210-211`). `kind` flows as an opaque `str` through `sharadar_context_source.py::_fetch_actions` → `generate_market_context.py::NormalizedAction`/`CorporateActionEvent` with zero branching. A protective side-effect already exists: `_build_blockers` only fires when `per_day.get(effective_date, False)` is `True`, so a `delisted`-kind row landing on an already-ineligible delisting day (TICKERS-driven `NormalizedListing.delisting_date`) is automatically excluded — no new invariant work needed there.

## Affected Areas
- `src/invest/adapters/sharadar_actions.py` — enum, mapping dict, float guard, unknown-action policy.
- `tests/adapters/test_sharadar_actions.py` — encodes wrong assumptions in ~5 places (float-rejection case line 107; non-existent `delisting`/`tickerchange` literals lines 82-94; `("tickerchange","1")` line 109; `("merger","1")` reject-unknown case line 130).
- `src/invest/adapters/sharadar_context_source.py`, `src/invest/application/generate_market_context.py`, `src/invest/domain/market_context_builder.py`, `src/invest/domain/market_context.py` — read/confirmed, **no code changes expected**.
- `tests/test_boundaries.py` (lines 341/388/423/446) — existing AST boundary checks already name `SharadarActionsReader`; unaffected unless a new mapping-layer class is introduced.

## Approaches

### 1. Minimal schema-parity fix (recommended)
Remove the float guard; remap `delisting`→`delisted`, `tickerchange`→`tickerchangeto`+`tickerchangefrom`; explicitly skip (not raise on) a bounded set of known-but-out-of-scope literals (`listed`, `relation`, `acquisitionby/of`, `regulatorydelisting`, `bankruptcyliquidation`, `adrratiosplit`, `spinoff`, `spunofffrom`, `spinoffdividend`, `mergerto/from`).
- **Pros**: unblocks real ACTIONS/broad-market pull with smallest diff; preserves existing kind-blind blocker semantics for the same conceptual classes already covered; strict-TDD friendly.
- **Cons**: real merger/spinoff/acquisition events stay invisible to the backtest (acceptable under YAGNI).
- **Effort**: Low.

### 2. Broad vocabulary modeling
Expand the enum/mapping to most literals with strict reject-unknown.
- **Pros**: maximal fidelity.
- **Cons**: disproportionate to the goal, forces premature corporate-identity-continuity decisions the domain model can't represent, larger diff, no behavioral payoff since the builder stays kind-blind either way.
- **Effort**: Medium-High.

## Recommendation
Approach 1 — smallest change, confined to `sharadar_actions.py` + its test file, ships as one strict-TDD change (test rewrite first).

## Open Design Questions (for propose/design)
- **(a) Which kinds to model vs skip**: recommend `split`/`dividend`/`delisted`/`tickerchangeto`+`tickerchangefrom`; open call on whether `regulatorydelisting`/`voluntarydelisting`/`bankruptcyliquidation` fold into `delisted` (TICKERS already independently drives delisting eligibility, so this would be redundant, not authoritative).
- **(b) Skip-unknown (forward-compatible) vs reject-unknown (fail-closed)** for future new literals — genuine behavior decision, not silently decidable here; flips the `("merger","1")` test assertion.
- **(c) Float-guard removal** — low risk; pydantic v2 float→Decimal coercion is precision-preserving via `str()`; recommend one live-shaped fixture confirmation during apply.
- **(d) Whether `SharadarActionKind` needs expanding at all vs a mapping layer** — given the builder is fully kind-blind today, recommend keeping the closed 4-kind enum until/unless a future change makes the builder kind-aware.

## Risks
- Builder's kind-blindness means any literal added to the mapped set becomes a same-day blocker — must NOT accidentally include high-frequency reference-noise (`listed`, `relation`).
- Skip vs reject-unknown requires explicit user sign-off and flips one existing test.
- Test file rewrite is the bulk of the diff, not the adapter code.
- `TICKER_CHANGE` currently models an undirected kind for a nonexistent literal; real API is directional (`tickerchangeto`/`tickerchangefrom`) — enum shape is an open call.
- No live-shaped fixture yet confirms float→Decimal precision end-to-end.

## Ready for Proposal
Yes.
