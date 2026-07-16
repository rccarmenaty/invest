```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:d8d1637f96b4a3a43d42308385cb1c4e7040dd33fc6a0b7cd8fd3c41f1d064c9
verdict: pass
blockers: 0
critical_findings: 0
requirements: 6/6
scenarios: 14/14
test_command: uv run pytest tests/domain/test_indicators.py tests/domain/test_exit_policy.py tests/domain/test_backtest_metrics.py tests/application/test_backtest_run.py tests/adapters/test_cli_backtest.py tests/test_boundaries.py -q
test_exit_code: 0
test_output_hash: sha256:74449b859f3b6f54831999d69076d932db35f5a1a8e6a2405ae59603e5363ba4
build_command: uv run python -m compileall -q src/invest/domain/exit_policy.py src/invest/domain/indicators.py src/invest/domain/backtest_metrics.py src/invest/domain/models.py src/invest/application/backtest_run.py src/invest/adapters/cli.py
build_exit_code: 0
build_output_hash: sha256:71fe9bcf24d15e72167453a11b7d7b2b587aa42a98c4b9a955a79248724aee08
```

## Verification Report

**Change**: trailing-exit-engine  
**Version**: N/A (delta on trading-system)  
**Mode**: Strict TDD  
**Artifact store**: hybrid  
**Review gate**: approved compact lineage `trailing-exit-engine-unit-3` (orchestrator-stated; not revalidated here)

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 26 |
| Tasks complete | 26 |
| Tasks incomplete | 0 |

### Build & Tests Execution
**Build**: ✅ Passed (bytecode compile of changed modules; no mypy/pyright configured)
```text
command: uv run python -m compileall -q src/invest/domain/exit_policy.py src/invest/domain/indicators.py src/invest/domain/backtest_metrics.py src/invest/domain/models.py src/invest/application/backtest_run.py src/invest/adapters/cli.py
exit_code: 0
output:
compileall: OK (no output)
output_hash: sha256:71fe9bcf24d15e72167453a11b7d7b2b587aa42a98c4b9a955a79248724aee08
```

**Tests**: ✅ 131 passed / ❌ 0 failed / ⚠️ 0 skipped
```text
command: uv run pytest tests/domain/test_indicators.py tests/domain/test_exit_policy.py tests/domain/test_backtest_metrics.py tests/application/test_backtest_run.py tests/adapters/test_cli_backtest.py tests/test_boundaries.py -q
exit_code: 0
output:
........................................................................ [ 54%]
...........................................................              [100%]
131 passed in 0.42s
output_hash: sha256:74449b859f3b6f54831999d69076d932db35f5a1a8e6a2405ae59603e5363ba4
```

**CLI runtime harness**: ✅ Passed
```text
command: uv run invest-backtest --help
exit_code: 0
output:
usage: invest-backtest [-h] --universe UNIVERSE [--bars BARS]
                       [--market-context MARKET_CONTEXT] [--start START]
                       [--end END] [--format {json}]
                       [--slippage-bps SLIPPAGE_BPS] [--tax-rate TAX_RATE]
                       [--split-date SPLIT_DATE] [--strategy STRATEGY]
                       [--source SOURCE]
                       [--exit-policy {ten-day-low,atr-3-high-water}]

options:
  -h, --help            show this help message and exit
  --universe UNIVERSE
  --bars BARS
  --market-context MARKET_CONTEXT
  --start START
  --end END
  --format {json}
  --slippage-bps SLIPPAGE_BPS
  --tax-rate TAX_RATE
  --split-date SPLIT_DATE
  --strategy STRATEGY
  --source SOURCE
  --exit-policy {ten-day-low,atr-3-high-water}
output_hash: sha256:61ce6934568f92b31601d803238b7b5c78fb950f83f92f18adaa06ca3082bae6
```

**Paper/execute baseline (supporting paper-contract scenario)**: ✅ 51 passed  
`uv run pytest tests/domain/test_sizing.py tests/application/test_execute_run.py tests/adapters/test_alpaca_broker.py -q` → exit 0

**Coverage**: ➖ Not available — no coverage tool in project capabilities (`pyproject.toml` dev deps: pytest, ruff only)

### Spec Compliance Matrix
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Replay-only pure exit engine | Pure domain evaluation | `tests/domain/test_exit_policy.py` > `test_on_bar_does_not_mutate_input_state` + pure unit suite; `tests/test_boundaries.py` > domain boundary / no-broker backtest path | ✅ COMPLIANT |
| Replay-only pure exit engine | Paper contracts preserved | `tests/application/test_backtest_run.py` > `test_intent_take_profit_is_ignored_for_replay_exits`; sizing/execute/alpaca baseline green; exit-policy flag absent from execute/scan | ✅ COMPLIANT |
| Default 10-day-low trailing exit | Below prior low fills next open | `test_exit_policy.py` > `test_channel_strict_below_prior_low_sets_pending_trailing_channel`, `test_pending_trailing_channel_fills_at_next_open_when_no_hard_stop`; `test_backtest_run.py` > `test_trailing_channel_close_below_prior_low_exits_at_next_open` | ✅ COMPLIANT |
| Default 10-day-low trailing exit | Equal close does not signal | `test_exit_policy.py` > `test_channel_equal_close_to_prior_low_does_not_signal` | ✅ COMPLIANT |
| Default 10-day-low trailing exit | Missing next bar | `test_backtest_run.py` > `test_trailing_signal_without_next_session_uses_open_at_end_and_warns` | ✅ COMPLIANT |
| Never-loosening floor and exit priority | Floor only ratchets up | `test_exit_policy.py` > `test_floor_only_ratchets_up_when_candidate_is_lower`, `test_floor_ratchets_up_to_prior_channel_low`; ATR: `test_atr_high_water_floor_never_loosens` | ✅ COMPLIANT |
| Never-loosening floor and exit priority | Forced-close beats ordinary exits | `test_backtest_run.py` > `test_forced_close_beats_pending_trailing_channel`, `test_forced_close_beats_pending_time_stop` | ✅ COMPLIANT |
| Never-loosening floor and exit priority | Hard stop beats trailing and time stop | `test_exit_policy.py` > `test_hard_stop_same_bar_beats_pending_trailing_channel`, `test_hard_stop_beats_pending_time_stop_on_same_bar`; `test_backtest_run.py` > `test_hard_stop_beats_pending_trailing_channel_on_same_bar`, `test_hard_stop_beats_pending_time_stop_on_fill_bar` | ✅ COMPLIANT |
| Conditional 20-session time stop | Time stop without progress | `test_exit_policy.py` > `test_time_stop_after_20_held_sessions_without_progress`, `test_pending_time_stop_fills_at_next_open`; `test_backtest_run.py` > `test_time_stop_exits_at_next_open_after_20_held_sessions_without_progress` | ✅ COMPLIANT |
| Conditional 20-session time stop | Progress suppresses time stop | `test_exit_policy.py` > `test_time_stop_suppressed_when_half_r_reached`, `test_time_stop_suppressed_when_new_prior20_closing_high_printed`; `test_backtest_run.py` > `test_half_r_progress_suppresses_time_stop_in_replay` | ✅ COMPLIANT |
| Selectable 3-ATR high-water variant | 3-ATR selected on backtest | `test_exit_policy.py` ATR cases; `test_backtest_run.py` > `test_atr_exit_policy_can_produce_atr_trail_next_open_fill`, `test_replay_records_exit_policy_provenance_for_both_kinds`; CLI report metadata tests | ✅ COMPLIANT |
| Selectable 3-ATR high-water variant | CLI isolation | `tests/test_boundaries.py` > `test_exit_policy_flag_is_backtest_only_and_absent_from_execute_and_scan_parsers`; runtime `invest-backtest --help` shows flag | ✅ COMPLIANT |
| No look-ahead and deterministic exit provenance | No look-ahead | `test_backtest_run.py` > `test_mutating_future_bars_does_not_change_day_n_exit`, `test_mutating_future_bars_does_not_change_day_n_exit_under_atr_policy` | ✅ COMPLIANT |
| No look-ahead and deterministic exit provenance | Deterministic twin runs | `test_backtest_run.py` > `test_replaying_same_range_twice_is_byte_identical`, `test_replaying_same_range_twice_is_byte_identical_for_atr_policy`; CLI twin default/explicit ten-day-low | ✅ COMPLIANT |

**Compliance summary**: 14/14 scenarios compliant

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| Replay-only pure exit engine | ✅ Implemented | `domain/exit_policy.py` pure; wired only via `BacktestRun`; no broker/I/O imports |
| Default 10-day-low trailing exit | ✅ Implemented | Strict `close < prior_low`; pending next-open; missing-next warning token |
| Never-loosening floor and exit priority | ✅ Implemented | `max(initial_stop, prior, candidate)`; hard-stop → pending trail → time-stop priority |
| Conditional 20-session time stop | ✅ Implemented | `sessions_held`, half-R + prior-20 high suppressors |
| Selectable 3-ATR high-water variant | ✅ Implemented | `atr-3-high-water` kind; CLI `--exit-policy`; `policy_provenance` on result/report |
| No look-ahead and deterministic exit provenance | ✅ Implemented | history ≤ bar; twin + mutate-future tests green |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Pure `domain/exit_policy.py` | ✅ Yes | Module present; `on_bar` pure API |
| Replay-only scope | ✅ Yes | No execute/paper selection |
| Strict prior-10 low break | ✅ Yes | Channel uses `trailing_low` on history_before |
| ATR close < post-update floor | ✅ Yes | `bar.close < new_floor` after ratchet |
| Hard stop same-bar; trail/time next-open | ✅ Yes | Matches design priority rule |
| Missing next → open-at-end + warning | ✅ Yes | `missing-next-session-after-exit-signal` |
| Delete `_simulate_trade` | ✅ Yes | Apply-progress + no dual path observed |
| `--exit-policy` backtest-only | ✅ Yes | Boundaries + help output |
| Documented deviations | ✅ Acceptable | Hyphen branch names; `time-stop` in `ExitReason` (design listed both) |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | ✅ | Full Unit 1/2/3 tables in apply-progress (filesystem + Engram) |
| All tasks have tests | ✅ | 26/26 tasks complete with RED/GREEN mapping |
| RED confirmed (tests exist) | ✅ | `test_indicators.py`, `test_exit_policy.py`, `test_backtest_metrics.py`, `test_backtest_run.py`, `test_cli_backtest.py`, `test_boundaries.py` present |
| GREEN confirmed (tests pass) | ✅ | 131/131 focused suite pass on independent execution |
| Triangulation adequate | ✅ | Multi-case channel/time/ATR/priority; single-case contract sets where appropriate |
| Safety Net for modified files | ✅ | Baselines recorded in apply-progress; paper suite re-run green |

**TDD Compliance**: 6/6 checks passed

### Test Layer Distribution
| Layer | Tests (approx) | Files | Tools |
|-------|----------------|-------|-------|
| Unit | 38 | `test_indicators.py`, `test_exit_policy.py`, `test_backtest_metrics.py` | pytest |
| Integration | 66+ | `test_backtest_run.py`, `test_cli_backtest.py` | pytest |
| Boundary | 17 | `test_boundaries.py` | pytest + AST guards |
| E2E | 0 | — | not installed / not required |
| **Total (focused)** | **131** | **6** | |

### Changed File Coverage
Coverage analysis skipped — no coverage tool detected

### Assertion Quality
**Assertion quality**: ✅ All assertions verify real behavior  
No tautologies, ghost loops, smoke-only renders, or production-free assertions found in change-related tests. Assertions exercise `on_bar`, replay fills, CLI report metadata, and parser dest sets with concrete expected values (floors, reasons, byte identity).

### Quality Metrics
**Linter (ruff on changed files)**: ✅ All checks passed  
**Type Checker**: ➖ Not available (no mypy/pyright); build substituted with `compileall` exit 0

### Issues Found
**CRITICAL**: None  
**WARNING**: None  
**SUGGESTION**:
1. `resolve_exit_policy` is covered via CLI integration/parser tests but has no dedicated pure unit cases for unknown-kind failure and kind mapping (optional hardening only; not required for scenario compliance).

### Canonical verification-evidence preimage
Exact bytes hashed for `evidence_revision` (1620 bytes). Reconstructable from the recorded commands/outputs below.

```text
test_command=uv run pytest tests/domain/test_indicators.py tests/domain/test_exit_policy.py tests/domain/test_backtest_metrics.py tests/application/test_backtest_run.py tests/adapters/test_cli_backtest.py tests/test_boundaries.py -q
test_exit_code=0
test_output=
........................................................................ [ 54%]
...........................................................              [100%]
131 passed in 0.42s

build_command=uv run python -m compileall -q src/invest/domain/exit_policy.py src/invest/domain/indicators.py src/invest/domain/backtest_metrics.py src/invest/domain/models.py src/invest/application/backtest_run.py src/invest/adapters/cli.py
build_exit_code=0
build_output=
compileall: OK (no output)
runtime_command=uv run invest-backtest --help
runtime_exit_code=0
runtime_output=
usage: invest-backtest [-h] --universe UNIVERSE [--bars BARS]
                       [--market-context MARKET_CONTEXT] [--start START]
                       [--end END] [--format {json}]
                       [--slippage-bps SLIPPAGE_BPS] [--tax-rate TAX_RATE]
                       [--split-date SPLIT_DATE] [--strategy STRATEGY]
                       [--source SOURCE]
                       [--exit-policy {ten-day-low,atr-3-high-water}]

options:
  -h, --help            show this help message and exit
  --universe UNIVERSE
  --bars BARS
  --market-context MARKET_CONTEXT
  --start START
  --end END
  --format {json}
  --slippage-bps SLIPPAGE_BPS
  --tax-rate TAX_RATE
  --split-date SPLIT_DATE
  --strategy STRATEGY
  --source SOURCE
  --exit-policy {ten-day-low,atr-3-high-water}
```

### Verdict
**PASS**  
All 26 tasks complete; 6/6 requirements and 14/14 scenarios have runtime-passing covering tests; Strict TDD evidence present and reconfirmed; build and CLI harness green; zero CRITICAL/WARNING findings.
