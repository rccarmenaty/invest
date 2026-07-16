# Apply Progress: trailing-exit-engine

**Change**: trailing-exit-engine  
**Mode**: Strict TDD  
**Branch (current)**: `feat/trailing-exit-engine-02-time-stop` (from `feat/trailing-exit-engine-01-channel`)
**Note**: Git cannot host both `feat/X` and `feat/X/01-slice`; children use hyphen form per chained-pr skill.

## Completed Tasks

### Unit 1 / PR 1 — pure 10-day-low engine + replay wiring

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

### Unit 2 / PR 2 — Conditional 20-session time stop

- [x] 2.1 RED: `tests/domain/test_exit_policy.py` — 20 held sessions no +0.5R / no prior-20 high → pending `time-stop`; progress suppresses; stop > trail > time same-bar
- [x] 2.2 GREEN: `exit_policy.py` + state — `sessions_held`, `reached_half_r`, `printed_new_prior20_high`; evaluate after 20th close
- [x] 2.3 RED: `tests/application/test_backtest_run.py` — time-stop next-open+slippage; missing next → open-at-end+warning; forced-close/hard-stop still win
- [x] 2.4 GREEN: wire time-stop pending fill in `backtest_run.py` priority after trail
- [x] 2.5 REFACTOR: progress flags only on completed history ≤ t
- [x] 2.6 Verify unit 2 focused command green

## Remaining Tasks

- [ ] 3.1–3.10 Unit 3 — 3-ATR variant + CLI/report isolation

## TDD Cycle Evidence

### Unit 1 (preserved)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `tests/domain/test_indicators.py` | Unit | ✅ 17 domain baseline | ✅ Written (ImportError) | ✅ `trailing_low` | ✅ 3 cases | ➖ Mirror of `trailing_high` |
| 1.2 | (impl of 1.1) | Unit | — | — | ✅ 13/13 indicators | — | ✅ Clean |
| 1.3 | `tests/domain/test_exit_policy.py` | Unit | N/A (new) | ✅ Written | ✅ `exit_policy.py` | ✅ 7 cases | ✅ Pure frozen state |
| 1.4 | (impl of 1.3) | Unit | — | — | ✅ 7/7 exit_policy | — | ✅ Clean |
| 1.5 | `tests/domain/test_backtest_metrics.py` | Unit | ✅ metrics baseline | ✅ Written (enum set fail) | ✅ ExitReason update | ➖ Single contract set | ➖ None needed |
| 1.6 | (impl of 1.5) | Unit | — | — | ✅ 7/7 metrics | — | ➖ None needed |
| 1.7 | `tests/application/test_backtest_run.py` | Integration | ✅ 39 backtest baseline | ✅ Written (TP path fail) | ✅ BacktestRun wiring | ✅ multi-scenario | ✅ Policy on position |
| 1.8 | (impl of 1.7) | Integration | — | — | ✅ 53 focused green | — | ✅ Deleted `_simulate_trade` |
| 1.9 | seams | — | — | — | ✅ sizing/execute/broker green | — | ✅ Paper/intent TP untouched |
| 1.10 | verify | — | — | — | ✅ Focused 53 + boundaries 19 | — | — |

### Unit 2

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 2.1 | `tests/domain/test_exit_policy.py` | Unit | ✅ 34 (exit_policy+backtest) | ✅ Written | ✅ time-stop state/eval | ✅ no-progress, half-R suppress, prior-20 suppress, stop>time, trail>time, channel>time, next-open fill | ✅ Pure flags from history ≤ t |
| 2.2 | (impl of 2.1) | Unit | — | — | ✅ 14/14 exit_policy | — | ✅ Config `time_stop_sessions`/`half_r` |
| 2.3 | `tests/application/test_backtest_run.py` | Integration | ✅ Unit 1 suite | ✅ Written | ✅ replay wiring | ✅ next-open, missing-next warn, hard-stop win, forced-close win, half-R suppress | ➖ pending reason path already generic |
| 2.4 | (impl of 2.3) | Integration | — | — | ✅ `initial_state(..., entry_price=raw_entry)` | — | ✅ No extra app logic |
| 2.5 | refactor | Unit | — | — | ✅ still green | — | ✅ progress only on completed history ≤ t |
| 2.6 | verify | — | — | — | ✅ focused unit2 + full 66 | — | — |

### Test Summary (cumulative)

- **Unit 1 focused suite**: 53 passed (at Unit 1 close)
- **Unit 2 pure + integration additions**: time-stop / progress / priority cases
- **Current focused (U1+U2 files)**: `uv run pytest tests/domain/test_indicators.py tests/domain/test_exit_policy.py tests/domain/test_backtest_metrics.py tests/application/test_backtest_run.py -q` → **66 passed**
- **Unit 2 focused filter**: `uv run pytest tests/domain/test_exit_policy.py tests/application/test_backtest_run.py -q -k "time_stop or progress or priority or half_r or forced_close_beats_pending_time"` → **12 passed**
- **Layers**: Unit + Integration
- **Pure functions extended**: `on_bar` (sessions/progress/time-stop), `initial_state(entry_price=...)`

## Work Unit Evidence

### Unit 1 (preserved)

| Evidence | Value |
|---|---|
| Focused test | U1 command → **53 passed** |
| Runtime harness | `N/A` — pure domain + in-memory replay |
| Rollback boundary | Revert exit_policy/trailing_low/ExitReason/backtest_run; restore fixed-TP tests; paper untouched |

### Unit 2

| Evidence | Value |
|---|---|
| Focused test command and exact result | `uv run pytest tests/domain/test_exit_policy.py tests/application/test_backtest_run.py -q -k "time_stop or progress or priority or half_r or forced_close_beats_pending_time"` → **12 passed**; full U1+U2 files → **66 passed** |
| Runtime harness | `N/A` — pure domain + in-memory `BacktestRun.replay` only; no broker/CLI boundary in Unit 2 |
| Rollback boundary | Revert time-stop fields/eval in `exit_policy.py`, `initial_state(entry_price=...)` wiring, and Unit 2 tests only; channel path remains |

## Files Changed

### Unit 1
| File | Action | What Was Done |
|------|--------|---------------|
| `src/invest/domain/indicators.py` | Modified | `trailing_low` |
| `src/invest/domain/exit_policy.py` | Created | Pure 10-day-low policy |
| `src/invest/domain/backtest_metrics.py` | Modified | ExitReason set |
| `src/invest/application/backtest_run.py` | Modified | Policy wiring; delete `_simulate_trade` |
| tests (indicators/exit_policy/metrics/backtest_run) | Modified/Created | Unit 1 coverage |

### Unit 2
| File | Action | What Was Done |
|------|--------|---------------|
| `src/invest/domain/exit_policy.py` | Modified | `sessions_held`, progress flags, `time-stop` pending; `entry_price` on state; config `time_stop_sessions`/`half_r` |
| `src/invest/application/backtest_run.py` | Modified | `initial_state(initial_stop=..., entry_price=raw_entry)` |
| `tests/domain/test_exit_policy.py` | Modified | Time-stop pure RED/GREEN cases |
| `tests/application/test_backtest_run.py` | Modified | Time-stop replay integration cases |

## Workload / PR Boundary

- Mode: chained PR slice (`feature-branch-chain`)
- Unit 1 child: `feat/trailing-exit-engine-01-channel` → tracker
- Unit 2 child: `feat/trailing-exit-engine-02-time-stop` → PR1 branch
- Unit 2 scope: conditional 20-session time stop only; no ATR/CLI/paper
- Authored Unit 2 delta: ~377 lines (under session budget 800)

## Deviations from Design

- Branch hyphen naming (Git ref constraint) — same as Unit 1.
- `ExitReason` enum not extended with `time-stop` in Unit 2 (tasks do not require it; free-string reason matches forced-close pattern). Unit 3 may formalize additional reasons.

## Issues Found

- None blocking.

## Bounded review correction (Unit 1 CRITICAL — preserved)

**Claim**: trailing exits record pre-slipped `entry_fill` as `SimulatedTrade.entry_price`.
**Result**: defect not present; regression + keyword-arg hardening applied. See prior section in history / Engram.

## Status

16/26 tasks complete (Units 1–2 done). Ready for Unit 3 apply or PR 2 review.
