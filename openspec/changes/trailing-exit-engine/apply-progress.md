# Apply Progress: trailing-exit-engine

**Change**: trailing-exit-engine  
**Mode**: Strict TDD  
**Work unit**: Unit 1 / PR 1 — pure 10-day-low engine + replay wiring  
**Branch**: `feat/trailing-exit-engine-01-channel` (child of tracker `feat/trailing-exit-engine`)  
**Note**: Git cannot host both `feat/trailing-exit-engine` and `feat/trailing-exit-engine/01-channel`; child uses hyphen form per chained-pr skill convention (`feat/X-01-slice`).

## Completed Tasks

- [x] 1.1 RED: `tests/domain/test_indicators.py` — `trailing_low` hand windows; caller excludes signal day
- [x] 1.2 GREEN: `src/invest/domain/indicators.py` — add `trailing_low` mirroring `trailing_high`
- [x] 1.3 RED: `tests/domain/test_exit_policy.py` — pure ratchet never loosens; channel strict `<` (equal no signal); hard-stop same-bar beats pending trail
- [x] 1.4 GREEN: `src/invest/domain/exit_policy.py` — `ExitPolicyConfig`, state helpers, `on_bar` (hard-stop | update+pending `trailing-channel`); clock/I/O-free
- [x] 1.5 RED: `tests/domain/test_backtest_metrics.py` — `ExitReason` adds `trailing-channel`; drop active `take-profit` from contract set
- [x] 1.6 GREEN: `src/invest/domain/backtest_metrics.py` — update `ExitReason`
- [x] 1.7 RED: `tests/application/test_backtest_run.py` — replace TP cases; next-open fill+slippage; missing-next → `open-at-end` + `missing-next-session-after-exit-signal`; forced-close beats trail; ignore intent TP; no-look-ahead mutate post-N; twin-run identity
- [x] 1.8 GREEN: `src/invest/application/backtest_run.py` — `_OpenPosition` policy fields; inject default ten-day-low; replace `_exit_for_bar` TP path; delete `_simulate_trade`; priority forced-close → hard-stop → pending trail → open-at-end
- [x] 1.9 REFACTOR: pure module seams only; paper/execute/sizing/`OrderIntent.take_profit` untouched
- [x] 1.10 Verify unit 1 focused command green; paper baselines unchanged

## Remaining Tasks

- [ ] 2.1–2.6 Unit 2 — Conditional 20-session time stop
- [ ] 3.1–3.10 Unit 3 — 3-ATR variant + CLI/report isolation

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `tests/domain/test_indicators.py` | Unit | ✅ 17 domain baseline | ✅ Written (ImportError) | ✅ `trailing_low` | ✅ 3 cases (hand min, outside window, signal-day exclude) | ➖ Mirror of `trailing_high` |
| 1.2 | (impl of 1.1) | Unit | — | — | ✅ 13/13 indicators | — | ✅ Clean |
| 1.3 | `tests/domain/test_exit_policy.py` | Unit | N/A (new) | ✅ Written | ✅ `exit_policy.py` | ✅ 7 cases (ratchet up/hold, strict/equal, stop>pending, next-open, purity) | ✅ Pure frozen state |
| 1.4 | (impl of 1.3) | Unit | — | — | ✅ 7/7 exit_policy | — | ✅ Clean |
| 1.5 | `tests/domain/test_backtest_metrics.py` | Unit | ✅ metrics baseline | ✅ Written (enum set fail) | ✅ ExitReason update | ➖ Single contract set | ➖ None needed |
| 1.6 | (impl of 1.5) | Unit | — | — | ✅ 7/7 metrics | — | ➖ None needed |
| 1.7 | `tests/application/test_backtest_run.py` | Integration | ✅ 39 backtest baseline | ✅ Written (TP path fail) | ✅ BacktestRun wiring | ✅ next-open, ignore TP, stop>pending, missing-next warn, forced-close, no-look-ahead, twin | ✅ Policy on position |
| 1.8 | (impl of 1.7) | Integration | — | — | ✅ 53 focused green | — | ✅ Deleted `_simulate_trade` |
| 1.9 | seams | — | — | — | ✅ sizing/execute/broker green | — | ✅ Paper/intent TP untouched |
| 1.10 | verify | — | — | — | ✅ Focused 53 + boundaries 19 | — | — |

### Test Summary

- **Total tests written/updated (Unit 1)**: ~15 new behavioral tests + contract updates
- **Focused suite passing**: 53
- **Layers used**: Unit (indicators, exit_policy, metrics), Integration (BacktestRun.replay)
- **Approval tests**: N/A — behavior change (TP → trailing), not pure refactor
- **Pure functions created**: `trailing_low`, `initial_state`, `on_bar` (+ frozen config/state/decision)

## Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `uv run pytest tests/domain/test_indicators.py tests/domain/test_exit_policy.py tests/domain/test_backtest_metrics.py tests/application/test_backtest_run.py -q` → **53 passed** |
| Runtime harness | `N/A` — pure domain + in-memory `BacktestRun.replay` only; no broker/CLI runtime boundary in Unit 1 |
| Rollback boundary | Revert `src/invest/domain/exit_policy.py`, `trailing_low` in `indicators.py`, `ExitReason` in `backtest_metrics.py`, `backtest_run.py` wiring; restore fixed-TP tests in `test_backtest_run.py` / `test_backtest_metrics.py`; paper/execute/sizing untouched |
| Paper/execute baseline | `uv run pytest tests/domain/test_sizing.py tests/application/test_execute_run.py tests/adapters/test_alpaca_broker.py -q` → **pass** (sizing + execute + broker); `tests/test_boundaries.py` → **19 passed** |

## Files Changed

| File | Action | What Was Done |
|------|--------|---------------|
| `src/invest/domain/indicators.py` | Modified | Added `trailing_low` |
| `src/invest/domain/exit_policy.py` | Created | Pure 10-day-low policy (`ExitPolicyConfig`, state, `on_bar`) |
| `src/invest/domain/backtest_metrics.py` | Modified | `ExitReason`: `trailing-channel` replaces `take-profit` |
| `src/invest/application/backtest_run.py` | Modified | Policy state on `_OpenPosition`; default ten-day-low; delete `_simulate_trade`; missing-next warning |
| `tests/domain/test_indicators.py` | Modified | `trailing_low` RED cases |
| `tests/domain/test_exit_policy.py` | Created | Pure policy unit tests |
| `tests/domain/test_backtest_metrics.py` | Modified | ExitReason contract set |
| `tests/application/test_backtest_run.py` | Modified | Replace TP cases; trail/next-open/priority/determinism |

## Workload / PR Boundary

- Mode: chained PR slice (feature-branch-chain)
- Current work unit: Unit 1 / PR 1
- Boundary: pure 10-day-low + replay wiring only; no time-stop, ATR, CLI flag, paper changes
- Authored impact: ~587 lines (tracked + new); under session budget 800; above ideal 400 (expected for Unit 1 forecast 350–500)
- Tracker: `feat/trailing-exit-engine`
- Child: `feat/trailing-exit-engine-01-channel` → targets tracker

## Deviations from Design

- Branch name uses hyphen child (`feat/trailing-exit-engine-01-channel`) instead of slash path because Git refs cannot nest under an existing branch name; matches chained-pr skill examples.
- Unit 1 does not yet add time-stop / ATR state fields on policy state (deferred to Units 2–3 per tasks).

## Issues Found

- None blocking.

## Bounded review correction (CRITICAL — raw entry_price / single entry slippage)

**Claim**: trailing exits record pre-slipped `entry_fill` as `SimulatedTrade.entry_price`, causing double entry slippage in metrics/settlement.

**Verification**: At apply time, `_OpenPosition` already stored `entry_price=entry_bar.open` (raw) and `entry_fill=entry_fill(open)` separately. Runtime probe: trailing trade `entry_price=11.40` (raw), not `11.4057` (slipped). Cash/metrics matched single-slippage hand math.

**Correction applied (defensive, behavior-preserving)**:
1. RED regression: `test_trailing_channel_trade_records_raw_entry_price_for_single_entry_slippage` — asserts raw entry, ≠ slipped fill, hand-computed `apply_costs`/cash identity.
2. Keyword-arg construction for `_OpenPosition` and all `SimulatedTrade` exit paths; local names `raw_entry` / `slipped_entry` so positional reorder cannot reintroduce the defect.

**Evidence**:
```
uv run pytest tests/application/test_backtest_run.py::test_trailing_channel_trade_records_raw_entry_price_for_single_entry_slippage tests/application/test_backtest_run.py -q
→ 28 passed
```

Task checkboxes unchanged (bounded remediation only).

## Status

10/26 tasks complete (Unit 1 done). Ready for next batch (Unit 2) or partial verify of Unit 1.
