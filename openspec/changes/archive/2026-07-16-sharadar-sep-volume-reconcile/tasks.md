# Tasks: Preserve Fractional Daily-Bar Volume

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | Whole delivery ~700–1100 (SDD artifacts ~450–700 + code/tests ~200–400). Already-implemented code/tests ~200–400 uncommitted; remaining apply/verify mostly process + any packaging. |
| 400-line budget risk | High |
| Session review budget | 800 changed lines (session preflight) |
| Chained PRs recommended | Yes |
| Suggested split | Prefer single PR with `size:exception` if under session 800 authored lines; else PR1 code+tests → PR2 SDD packaging |
| Delivery strategy | single-pr |
| Chain strategy | size:exception (maintainer-approved) |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: size:exception
400-line budget risk: High

### Implementation state (planning only — apply marks completion)

| Slice | State | Notes |
|-------|-------|-------|
| Domain + 3 adapters + liquidity + listed tests | Complete (uncommitted) | Apply verified + closed negative-volume / fractional gaps |
| SDD proposal/spec/design | Done | Engram + OpenSpec |
| This tasks artifact | Done | Hybrid write; apply marked completion |
| Mark tasks / apply-progress | Done | `sdd-apply` this batch |
| Full suite + representative SEP pull | Handoff only | Owned exclusively by `sdd-verify` (not an apply checkbox) |

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Canonical `DailyBar.volume: Decimal` + adapter pass-through + dual-form snapshots + exact liquidity product + tests | PR 1 (or sole PR) | `pytest tests/adapters/test_sharadar_market_data.py tests/adapters/test_alpaca_market_data.py tests/adapters/test_fixtures_json.py tests/domain/test_liquidity_screen.py -q` | N/A — design: no new live-provider harness; SEP pull is verify-phase only | `src/invest/domain/models.py`, `src/invest/adapters/{sharadar_market_data,alpaca_market_data,fixtures_json}.py`, `src/invest/domain/liquidity_screen.py`, matching tests under `tests/` |
| 2 | SDD packaging (proposal/specs/design/tasks) if split | PR 2 optional | N/A docs-only | N/A docs-only | `openspec/changes/2026-07-16-sharadar-sep-volume-reconcile/**` |

Threat-matrix RED tasks: none (design threat matrix `N/A`).

## Phase 1: Domain contract (TDD)

- [x] 1.1 RED: extend domain/adapter tests so `DailyBar.volume` is treated as non-negative `Decimal` (not `int`).
- [x] 1.2 GREEN: set `DailyBar.volume: Decimal` in `src/invest/domain/models.py`.

## Phase 2: Provider anti-corruption (TDD)

- [x] 2.1 RED: `tests/adapters/test_sharadar_market_data.py` — SEP volume `250.125`/`48037.936` → exact `Decimal`; negative → `malformed-response`, no partial bars.
- [x] 2.2 GREEN: `src/invest/adapters/sharadar_market_data.py` — `_SepRow.volume: Decimal = Field(ge=0)`; map `volume=row.volume` unchanged.
- [x] 2.3 RED: `tests/adapters/test_alpaca_market_data.py` — fractional Alpaca volume exact `Decimal`; negative rejected before domain.
- [x] 2.4 GREEN: `src/invest/adapters/alpaca_market_data.py` — `_BarPayload.volume: Decimal = Field(ge=0)`; pass-through map.
- [x] 2.5 RED: `tests/adapters/test_fixtures_json.py` — negative fixture volume → `FixtureValidationError`, no `DailyBar`.
- [x] 2.6 GREEN: `src/invest/adapters/fixtures_json.py` — `_BarPayload.volume: Decimal = Field(ge=0)`.

## Phase 3: Snapshot dual-form + round-trip (TDD)

- [x] 3.1 RED: Alpaca/fixture tests — integral volume serializes as JSON number; fractional `"48037.936"` string; load equals `Decimal("48037.936")`; repeated round trips identical.
- [x] 3.2 GREEN: dual-form snapshot write in `src/invest/adapters/alpaca_market_data.py` (integral `int`, fractional exact decimal string); reader path via fixtures already loads `Decimal`.

## Phase 4: Liquidity exact Decimal (TDD)

- [x] 4.1 RED: `tests/domain/test_liquidity_screen.py` — fractional products pass threshold when truncated products would fail; no int/float intermediates.
- [x] 4.2 GREEN: `src/invest/domain/liquidity_screen.py` — `bar.close * bar.volume` pure `Decimal` (drop redundant `Decimal(bar.volume)`).

## Phase 5: Apply handoff (not implementation edits)

- [x] 5.1 `sdd-apply`: inspect working tree, mark completed tasks, write apply-progress only (no re-implementation unless gap).

## Verification Handoff (owned exclusively by `sdd-verify`)

Not an apply checkbox. Apply must not mark this complete and must not claim verification ran.

`sdd-verify` owns the following evidence after all apply tasks above are complete:

1. **Full automated suite** — run the project full test suite and record exact command + result.
2. **Representative SEP pull** — exercise a representative Sharadar SEP pull path and confirm fractional volume preservation.
3. **Non-regression checks** — confirm OHLC, adjustments, and bar ordering remain unchanged relative to the volume-only contract.

Why this is not an apply task: encoding verify-owned full-suite / live-path evidence as a pending apply checkbox blocked the dispatcher from leaving apply. Removing the checkbox preserves exclusive `sdd-verify` ownership while leaving all 13 apply tasks complete.
