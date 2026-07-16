# Apply Progress: 2026-07-16-sharadar-sep-volume-reconcile

**Change**: 2026-07-16-sharadar-sep-volume-reconcile
**Mode**: Strict TDD
**Artifact store**: hybrid (OpenSpec + Engram)
**Delivery**: single-pr with maintainer-approved `size:exception` (session review budget 800)
**Batch**: continuation — convert mis-encoded 5.2 checkbox into Verification Handoff (merged with prior apply-progress)

## Completed Tasks

- [x] 1.1 RED: domain/adapter tests treat `DailyBar.volume` as non-negative `Decimal`
- [x] 1.2 GREEN: `DailyBar.volume: Decimal` in `src/invest/domain/models.py`
- [x] 2.1 RED: SEP fractional `250.125` / `48037.936` exact Decimal; negative → `malformed-response`
- [x] 2.2 GREEN: `_SepRow.volume: Decimal = Field(ge=0)`; pass-through map
- [x] 2.3 RED: Alpaca fractional volume exact Decimal; negative rejected before domain
- [x] 2.4 GREEN: Alpaca `_BarPayload.volume: Decimal = Field(ge=0)`; pass-through
- [x] 2.5 RED: negative fixture volume → `FixtureValidationError`, no `DailyBar`
- [x] 2.6 GREEN: fixtures `_BarPayload.volume: Decimal = Field(ge=0)`
- [x] 3.1 RED: integral JSON number; fractional string; load equality; repeated round trips
- [x] 3.2 GREEN: dual-form snapshot write in Alpaca `SnapshotWriter`
- [x] 4.1 RED: fractional liquidity products pass when truncated would fail
- [x] 4.2 GREEN: pure `bar.close * bar.volume` Decimal product
- [x] 5.1 `sdd-apply` inspect, gap-fill, mark tasks, write apply-progress

## Verification Handoff (owned exclusively by `sdd-verify`)

Not an apply checkbox. Not marked complete. Verification was not run in apply.

`sdd-verify` must produce:

1. Full automated suite evidence (exact command + result)
2. Representative SEP pull evidence
3. Confirmation that OHLC / adjustments / ordering are unchanged

**Why this correction preserves exclusive `sdd-verify` ownership**: Task 5.2 incorrectly encoded sdd-verify-owned final verification as a pending apply checkbox (`- [ ] 5.2`), which blocked the dispatcher from advancing to the verify phase. Converting it to a non-checkbox handoff section leaves all 13 apply tasks complete without claiming verify evidence, so apply no longer owns or pretends to complete full-suite / representative SEP pull work.

## Remaining Apply Tasks

None — all 13 apply checkboxes are complete. Next phase is `sdd-verify`.

## Files Changed

| File | Action | What Was Done |
|------|--------|---------------|
| `src/invest/domain/models.py` | Modified (prior unit) | `DailyBar.volume: Decimal` |
| `src/invest/adapters/sharadar_market_data.py` | Modified (prior unit) | `_SepRow.volume: Decimal = Field(ge=0)` |
| `src/invest/adapters/alpaca_market_data.py` | Modified (prior unit) | Decimal volume + dual-form snapshot |
| `src/invest/adapters/fixtures_json.py` | Modified (prior unit) | Decimal volume `ge=0` |
| `src/invest/domain/liquidity_screen.py` | Modified (prior unit) | pure Decimal product |
| `tests/adapters/test_sharadar_market_data.py` | Modified | fractional + negative SEP coverage |
| `tests/adapters/test_alpaca_market_data.py` | Modified | fractional fetch, negative reject, repeated RT |
| `tests/adapters/test_fixtures_json.py` | Modified | fractional load + explicit negative reject |
| `tests/domain/test_liquidity_screen.py` | Modified | fractional vs truncated product eligibility |
| `openspec/changes/.../tasks.md` | Modified | checkboxes + `size:exception` decision; 5.2 demoted from apply checkbox to Verification Handoff |
| `openspec/changes/.../apply-progress.md` | Modified | merged continuation batch documenting handoff repair |

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1–1.2 | adapter/domain tests | Unit | ✅ 87/87 prior focused | ✅ Written (prior + verify) | ✅ Passed | ✅ integral + fractional | ➖ Domain type only |
| 2.1–2.2 | `tests/adapters/test_sharadar_market_data.py` | Unit | ✅ 87/87 | ✅ Written gap: `48037.936` + negative | ✅ Passed (existing `Field(ge=0)`) | ✅ `250.125` + `48037.936` + negative | ➖ None needed |
| 2.3–2.4 | `tests/adapters/test_alpaca_market_data.py` | Unit | ✅ 87/87 | ✅ Written gap: fractional fetch + negative | ✅ Passed | ✅ integral + fractional + negative | ➖ None needed |
| 2.5–2.6 | `tests/adapters/test_fixtures_json.py` | Unit | ✅ 87/87 | ✅ Param + explicit negative test | ✅ Passed | ✅ fractional load + negative reject | ➖ None needed |
| 3.1–3.2 | `tests/adapters/test_alpaca_market_data.py` | Unit | ✅ 87/87 | ✅ Repeated round-trip assert | ✅ Passed | ✅ integral number + fractional string | ➖ None needed |
| 4.1–4.2 | `tests/domain/test_liquidity_screen.py` | Unit | ✅ 87/87 | ✅ truncated-product contrast | ✅ Passed | ✅ exact vs truncated | ➖ None needed |
| 5.1 | process | N/A | N/A | N/A process | N/A | N/A | N/A |
| handoff repair | process | N/A | N/A | N/A — no code/tests changed | N/A | N/A | N/A |

### Test Summary

- **Focused command**: `uv run pytest tests/adapters/test_sharadar_market_data.py tests/adapters/test_alpaca_market_data.py tests/adapters/test_fixtures_json.py tests/domain/test_liquidity_screen.py -q`
- **Exact result**: `92 passed, 1 skipped in 0.93s` (exit 0) — retained from prior apply batch; this continuation batch did not re-run tests
- **Layers used**: Unit (all)
- **Approval tests**: None — no pure-refactor tasks
- **Pure functions created**: 0 (liquidity product already pure after cast drop)
- **This batch**: Strict TDD remains active; no TDD cycle occurred because no code or test was changed

## Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `uv run pytest tests/adapters/test_sharadar_market_data.py tests/adapters/test_alpaca_market_data.py tests/adapters/test_fixtures_json.py tests/domain/test_liquidity_screen.py -q` → **92 passed, 1 skipped**, exit 0 (prior batch; retained) |
| Runtime harness command/scenario and exact result | **N/A** — design threat matrix N/A; no new live-provider harness; representative SEP pull owned exclusively by `sdd-verify` (Verification Handoff) |
| Rollback boundary | `src/invest/domain/models.py`, `src/invest/adapters/{sharadar_market_data,alpaca_market_data,fixtures_json}.py`, `src/invest/domain/liquidity_screen.py`, matching tests under `tests/adapters/` and `tests/domain/test_liquidity_screen.py`, plus `openspec/changes/2026-07-16-sharadar-sep-volume-reconcile/**` |

## Deviations from Design

None — implementation matches design. This continuation only repaired SDD task encoding: removed a mis-encoded verify-owned checkbox so the dispatcher can leave apply.

## Issues Found

None blocking. Prior working tree already had principal Decimal implementation; apply gap-fill confirmed negative-volume rejection was enforced by `Field(ge=0)` but lacked explicit SEP/Alpaca behavioral tests until the previous batch. The remaining process issue was task 5.2 incorrectly living as an apply checkbox — fixed this batch.

## Workload / PR Boundary

- Mode: `size:exception` (single PR, maintainer-approved)
- Current work unit: Unit 1 (canonical Decimal volume end-to-end) — apply complete
- Boundary: domain + 3 adapters + liquidity + tests + SDD packaging under one PR
- Estimated review budget impact: code/tests ~230 authored lines this tree; full change with SDD artifacts may approach session 800 budget — exception recorded
- This batch: process-only artifact edit (tasks handoff + apply-progress merge); no runtime/code/test behavior change

## Status

13/13 apply tasks complete. Ready for verify (`sdd-verify`). Verification evidence not claimed.
