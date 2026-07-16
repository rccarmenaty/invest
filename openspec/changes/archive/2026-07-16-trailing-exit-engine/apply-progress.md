# Apply Progress: trailing-exit-engine

**Change**: trailing-exit-engine  
**Mode**: Strict TDD  
**Branch (current)**: `feat/trailing-exit-engine-03-atr-cli` (from `feat/trailing-exit-engine-02-time-stop`)
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

### Unit 3 / PR 3 — 3-ATR variant + CLI/report isolation

- [x] 3.1 RED: ATR high-water floor never loosens; close `<` post-ratchet floor → pending `atr-trail`; next-open
- [x] 3.2 GREEN: `atr-3-high-water` kind; `high_water`; candidate `high_water - 3×ATR`
- [x] 3.3 RED: `ExitReason.atr-trail` (+ `time-stop` for contract completeness)
- [x] 3.4 GREEN: metrics + `BacktestResult.exit_policy` provenance from config
- [x] 3.5 RED: CLI `--exit-policy`; sorted report metadata; twin default/explicit identity
- [x] 3.6 GREEN: `cli.py` + `models.BacktestResult.exit_policy`
- [x] 3.7 RED: execute/scan parsers lack exit-policy flag
- [x] 3.8 GREEN: boundary isolation only
- [x] 3.9 RED/GREEN: no-look-ahead + deterministic twin under ATR policy
- [x] 3.10 REFACTOR + verify focused suite + `invest-backtest --help`

## Remaining Tasks

None — all 26 tasks complete.

## TDD Cycle Evidence

### Unit 1

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

### Unit 2

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 2.1 | `tests/domain/test_exit_policy.py` | Unit | ✅ 34 (exit_policy+backtest) | ✅ Written | ✅ time-stop state/eval | ✅ no-progress, half-R suppress, prior-20 suppress, stop>time, trail>time, channel>time, next-open fill | ✅ Pure flags from history ≤ t |
| 2.2 | (impl of 2.1) | Unit | — | — | ✅ 14/14 exit_policy | — | ✅ Config `time_stop_sessions`/`half_r` |
| 2.3 | `tests/application/test_backtest_run.py` | Integration | ✅ Unit 1 suite | ✅ Written | ✅ replay wiring | ✅ next-open, missing-next warn, hard-stop win, forced-close win, half-R suppress | ➖ pending reason path already generic |
| 2.4 | (impl of 2.3) | Integration | — | — | ✅ `initial_state(..., entry_price=raw_entry)` | — | ✅ No extra app logic |
| 2.5 | refactor | Unit | — | — | ✅ still green | — | ✅ progress only on completed history ≤ t |
| 2.6 | verify | — | — | — | ✅ focused unit2 + full 66 | — | — |

### Unit 3

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 3.1–3.2 | `test_exit_policy.py` | Unit | ✅ 53 U2 baseline | ✅ Written | ✅ ATR kind | ✅ never-loosen, signal, equal, next-open | ✅ Shared progress/time path |
| 3.3–3.4 | `test_backtest_metrics.py` + models/run | Unit/Integ | ✅ metrics | ✅ enum fail | ✅ atr-trail+time-stop | ➖ contract set | ✅ `policy_provenance` |
| 3.5–3.6 | `test_cli_backtest.py` + `cli.py` | Integration | ✅ CLI suite | ✅ Written | ✅ flag+report | ✅ default twin, atr kind | ✅ resolve_exit_policy |
| 3.7–3.8 | `test_boundaries.py` | Boundary | ✅ boundaries | ✅ Written | ✅ isolation | ➖ dest sets | ➖ none |
| 3.9 | `test_backtest_run.py` | Integration | ✅ backtest | ✅ Written | ✅ ATR no-look-ahead + twin | ✅ both policies provenance | ➖ none |
| 3.10 | verify | — | — | — | ✅ 118 focused + help | — | ✅ Clean |

### Test Summary (cumulative)

- **Unit 1 focused suite**: `uv run pytest tests/domain/test_indicators.py tests/domain/test_exit_policy.py tests/domain/test_backtest_metrics.py tests/application/test_backtest_run.py -q` → **53 passed**
- **Unit 2 filter**: `uv run pytest tests/domain/test_exit_policy.py tests/application/test_backtest_run.py -q -k "time_stop or progress or priority or half_r or forced_close_beats_pending_time"` → **12 passed**; full U1+U2 files → **66 passed**
- **Unit 3 focused suite**: `uv run pytest tests/domain/test_exit_policy.py tests/domain/test_backtest_metrics.py tests/application/test_backtest_run.py tests/adapters/test_cli_backtest.py tests/test_boundaries.py -q` → **118 passed**
- **Layers**: Unit + Integration + Boundary
- **Pure functions**: `trailing_low`, `initial_state`, `on_bar` (channel/time/ATR), `policy_provenance`, `resolve_exit_policy`

## Work Unit Evidence

### Unit 1

| Evidence | Value |
|---|---|
| Focused test command and exact result | `uv run pytest tests/domain/test_indicators.py tests/domain/test_exit_policy.py tests/domain/test_backtest_metrics.py tests/application/test_backtest_run.py -q` → **53 passed** |
| Runtime harness | `N/A` — pure domain + in-memory `BacktestRun.replay` only; no broker/CLI runtime boundary in Unit 1 |
| Rollback boundary | Revert `src/invest/domain/exit_policy.py`, `trailing_low` in `indicators.py`, `ExitReason` in `backtest_metrics.py`, `backtest_run.py` wiring; restore fixed-TP tests; paper/execute/sizing untouched |
| Paper/execute baseline (recorded) | `uv run pytest tests/domain/test_sizing.py tests/application/test_execute_run.py tests/adapters/test_alpaca_broker.py -q` → **pass**; `tests/test_boundaries.py` → **19 passed** |

### Unit 2

| Evidence | Value |
|---|---|
| Focused test command and exact result | `uv run pytest tests/domain/test_exit_policy.py tests/application/test_backtest_run.py -q -k "time_stop or progress or priority or half_r or forced_close_beats_pending_time"` → **12 passed**; full U1+U2 files → **66 passed** |
| Runtime harness | `N/A` — pure domain + in-memory `BacktestRun.replay` only; no broker/CLI boundary in Unit 2 |
| Rollback boundary | Revert time-stop fields/eval in `exit_policy.py`, `initial_state(entry_price=...)` wiring, and Unit 2 tests only; channel path remains |

### Unit 3

| Evidence | Value |
|---|---|
| Focused test command and exact result | `uv run pytest tests/domain/test_exit_policy.py tests/domain/test_backtest_metrics.py tests/application/test_backtest_run.py tests/adapters/test_cli_backtest.py tests/test_boundaries.py -q` → **118 passed** |
| Unit-3 filter | `-k "atr or exit_policy or boundary or determin or twin or byte_identical or no_look or mutating_future"` → **35 passed** |
| Runtime harness | `uv run invest-backtest --help` → shows `--exit-policy {ten-day-low,atr-3-high-water}` |
| Rollback boundary | Revert ATR branch in `exit_policy.py`, `--exit-policy` + report metadata, `ExitReason` atr/time, `BacktestResult.exit_policy`; default 10-day-low remains |

## Files Changed (cumulative)

### Unit 1
| File | Action | What Was Done |
|------|--------|---------------|
| `src/invest/domain/indicators.py` | Modified | `trailing_low` |
| `src/invest/domain/exit_policy.py` | Created | Pure 10-day-low policy |
| `src/invest/domain/backtest_metrics.py` | Modified | ExitReason set (trailing-channel) |
| `src/invest/application/backtest_run.py` | Modified | Policy wiring; delete `_simulate_trade` |
| tests (indicators/exit_policy/metrics/backtest_run) | Modified/Created | Unit 1 coverage |

### Unit 2
| File | Action | What Was Done |
|------|--------|---------------|
| `src/invest/domain/exit_policy.py` | Modified | `sessions_held`, progress flags, `time-stop`; `entry_price` on state |
| `src/invest/application/backtest_run.py` | Modified | `initial_state(initial_stop=..., entry_price=raw_entry)` |
| `tests/domain/test_exit_policy.py` | Modified | Time-stop pure cases |
| `tests/application/test_backtest_run.py` | Modified | Time-stop replay cases |

### Unit 3
| File | Action | What Was Done |
|------|--------|---------------|
| `src/invest/domain/exit_policy.py` | Modified | `atr-3-high-water`, `high_water`, `atr_mult`, `policy_provenance`, `resolve_exit_policy` |
| `src/invest/domain/backtest_metrics.py` | Modified | `ExitReason.time-stop`, `atr-trail` |
| `src/invest/domain/models.py` | Modified | `BacktestResult.exit_policy` provenance map |
| `src/invest/application/backtest_run.py` | Modified | Emit `exit_policy` provenance on result |
| `src/invest/adapters/cli.py` | Modified | `--exit-policy`; inject config; report field |
| `tests/domain/test_exit_policy.py` | Modified | ATR pure cases |
| `tests/domain/test_backtest_metrics.py` | Modified | ExitReason contract |
| `tests/application/test_backtest_run.py` | Modified | ATR fill, provenance, no-look-ahead, twin |
| `tests/adapters/test_cli_backtest.py` | Modified | Flag + report + twin metadata |
| `tests/test_boundaries.py` | Modified | exit-policy backtest-only |

## Workload / PR Boundary

- Mode: chained PR slice (`feature-branch-chain`)
- Tracker: `feat/trailing-exit-engine`
- PR1: `feat/trailing-exit-engine-01-channel` → tracker
- PR2: `feat/trailing-exit-engine-02-time-stop` → PR1
- PR3: `feat/trailing-exit-engine-03-atr-cli` → PR2
- Scope complete across three autonomous units; sizing/paper/execute untouched

## Deviations from Design

- Hyphen branch naming (Git constraint) — consistent across chain.
- `time-stop` added to `ExitReason` alongside `atr-trail` for contract completeness (design listed both).

## Issues Found

- None blocking.

## Bounded review correction (Unit 1 CRITICAL — preserved)

**Claim**: trailing exits record pre-slipped `entry_fill` as `SimulatedTrade.entry_price`.
**Verification**: defect not present (`entry_price` already raw open).
**Correction**: regression test + keyword-arg construction hardening.
**Evidence**: `uv run pytest tests/application/test_backtest_run.py::test_trailing_channel_trade_records_raw_entry_price_for_single_entry_slippage tests/application/test_backtest_run.py -q` → **28 passed**

## Status

**26/26** tasks complete. **Next recommended: `sdd-verify` only** (do not archive or open PR review until verify passes).
