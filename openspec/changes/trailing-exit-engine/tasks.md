# Tasks: Trailing Exit Engine

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 650–1000 (authored) |
| 400-line budget risk | High |
| Session budget | 800 authored lines |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 (force-chained feature-branch-chain) |
| Delivery strategy | force-chained |
| Chain strategy | feature-branch-chain |
| Feature-chain bases | PR 1 base = tracker; PR 2 base = PR 1 branch; PR 3 base = PR 2 branch; only tracker merges to `main` |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Base | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|------|----------------------|-----------------|-------------------|
| 1 | Pure 10-day-low + replay wiring | PR 1 | tracker branch | `pytest tests/domain/test_indicators.py tests/domain/test_exit_policy.py tests/domain/test_backtest_metrics.py tests/application/test_backtest_run.py -q` | `N/A` — pure domain + in-memory `BacktestRun.replay` only | Revert `exit_policy.py`, `trailing_low`, metrics reasons, `backtest_run` wiring; restore fixed-TP tests; paper untouched |
| 2 | Conditional 20-session time stop | PR 2 | PR 1 branch | `pytest tests/domain/test_exit_policy.py tests/application/test_backtest_run.py -q -k "time_stop or progress or priority"` | `N/A` — pure + in-memory replay fixtures | Revert time-stop fields/eval/tests only; channel path stays |
| 3 | 3-ATR + CLI/report isolation | PR 3 | PR 2 branch | `pytest tests/domain/test_exit_policy.py tests/adapters/test_cli_backtest.py tests/test_boundaries.py tests/application/test_backtest_run.py -q -k "atr or exit_policy or boundary or determin"` | `invest-backtest --help` (flag present); execute/scan parsers reject policy flag | Revert ATR branch, `--exit-policy`, report metadata; default 10-day-low remains |

## Phase 1: Unit 1 — 10-day-low engine + replay (350–500 lines)

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

## Phase 2: Unit 2 — Conditional 20-session time stop (150–250 lines)

- [ ] 2.1 RED: `tests/domain/test_exit_policy.py` — 20 held sessions no +0.5R / no prior-20 high → pending `time-stop`; progress suppresses; stop > trail > time same-bar
- [ ] 2.2 GREEN: `exit_policy.py` + state — `sessions_held`, `reached_half_r`, `printed_new_prior20_high`; evaluate after 20th close
- [ ] 2.3 RED: `tests/application/test_backtest_run.py` — time-stop next-open+slippage; missing next → open-at-end+warning; forced-close/hard-stop still win
- [ ] 2.4 GREEN: wire time-stop pending fill in `backtest_run.py` priority after trail
- [ ] 2.5 REFACTOR: progress flags only on completed history ≤ t
- [ ] 2.6 Verify unit 2 focused command green

## Phase 3: Unit 3 — 3-ATR variant + CLI/report isolation (150–300 lines)

- [ ] 3.1 RED: `tests/domain/test_exit_policy.py` — ATR high-water floor never loosens; close `<` post-ratchet floor → pending `atr-trail`; next-open semantics
- [ ] 3.2 GREEN: `exit_policy.py` kind `atr-3-high-water`; `high_water`; candidate `high_water - 3×ATR`
- [ ] 3.3 RED: `tests/domain/test_backtest_metrics.py` — `ExitReason.atr-trail`
- [ ] 3.4 GREEN: metrics + `backtest_run` inject config by kind
- [ ] 3.5 RED: `tests/adapters/test_cli_backtest.py` — `--exit-policy`; report `"exit_policy": {kind, params}` sorted; twin metadata identity
- [ ] 3.6 GREEN: `src/invest/adapters/cli.py` + optional `BacktestResult` metadata in `models.py`
- [ ] 3.7 RED: `tests/test_boundaries.py` — execute/day-0 parsers lack exit-policy flag; paper `take_profit`/brackets byte-compatible
- [ ] 3.8 GREEN: boundary isolation only; no execute path selection
- [ ] 3.9 RED/GREEN: no-look-ahead + deterministic twin with both policies
- [ ] 3.10 REFACTOR + verify unit 3 focused command + `invest-backtest --help`

## Spec coverage checklist

| Spec scenario | Task |
|---------------|------|
| Pure domain evaluation | 1.3–1.4 |
| Paper contracts preserved | 1.9, 3.7–3.8 |
| Below prior low → next open | 1.7–1.8 |
| Equal close no signal | 1.3 |
| Missing next bar | 1.7, 2.3 |
| Floor only ratchets up | 1.3, 3.1 |
| Forced-close beats ordinary | 1.7, 2.3 |
| Hard stop beats trail/time | 1.3, 2.1 |
| Time stop without progress | 2.1–2.4 |
| Progress suppresses time stop | 2.1–2.2 |
| 3-ATR selected on backtest | 3.1–3.6 |
| CLI isolation | 3.7–3.8 |
| No look-ahead | 1.7, 3.9 |
| Deterministic twin runs | 1.7, 3.5, 3.9 |
