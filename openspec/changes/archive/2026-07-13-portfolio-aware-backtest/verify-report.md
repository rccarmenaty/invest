```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:92e0453b6c90384626be6b17b02986dfce895aa20fd7a059c222133518a54851
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 4/4
scenarios: 11/11
test_command: uv run --extra dev pytest
test_exit_code: 0
test_output_hash: sha256:561cf2c7045561b99c7c25933b57bd82cdc50461141a84912876dfbec5692d23
build_command: uv run --extra dev ruff check .
build_exit_code: 0
build_output_hash: sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18
```

## Verification Report

**Change**: `portfolio-aware-backtest`  
**Version**: N/A  
**Mode**: Strict TDD  
**Evidence revision / review target snapshot**: `sha256:92e0453b6c90384626be6b17b02986dfce895aa20fd7a059c222133518a54851`  
**Persistence mode**: hybrid (`openspec` file + Engram topic `sdd/portfolio-aware-backtest/verify-report`)  
**Final verdict**: PASS WITH WARNINGS

### Artifact Inputs Read

| Artifact | Path | Status |
|---|---|---|
| Proposal | `openspec/changes/portfolio-aware-backtest/proposal.md` | Read |
| Spec | `openspec/changes/portfolio-aware-backtest/specs/trading-system/spec.md` | Read |
| Design | `openspec/changes/portfolio-aware-backtest/design.md` | Read |
| Tasks | `openspec/changes/portfolio-aware-backtest/tasks.md` | Read; 4.1/4.2 checked after successful independent verification |
| Apply progress | `openspec/changes/portfolio-aware-backtest/apply-progress.md` | Read |
| Review ledger | `openspec/changes/portfolio-aware-backtest/reviews/ledger.json` | Read |
| Failure evidence | `openspec/changes/portfolio-aware-backtest/reviews/failure-evidence.json` | Read as historical failed snapshot |
| Scoped validation | `openspec/changes/portfolio-aware-backtest/reviews/scoped-validation.json` | Read |
| Review policies | `openspec/changes/portfolio-aware-backtest/reviews/policy.md`, `clean-policy.md` | Read |

### Completeness

| Metric | Value |
|--------|-------|
| Requirements total | 4 |
| Requirements compliant | 4 |
| Scenarios total | 11 |
| Scenarios compliant | 11 |
| Tasks total | 15 |
| Tasks complete | 15 |
| Tasks incomplete | 0 |
| Blockers | 0 |
| Critical findings | 0 |

### Command Evidence Bound to Target Snapshot

All runtime evidence below was independently generated during verification and is bound to review target snapshot `sha256:92e0453b6c90384626be6b17b02986dfce895aa20fd7a059c222133518a54851`. Development evidence from `apply-progress.md` was not used as final evidence.

| Check | Command | Exit code | Raw output hash | Result |
|---|---|---:|---|---|
| Focused touched tests | `uv run --extra dev pytest tests/domain/test_backtest_metrics.py tests/application/test_backtest_run.py tests/adapters/test_cli_backtest.py` | 0 | `sha256:78e71154204b4d6b80341b16c9f99feb9f558aa6e72a7189e6521c91c01a0d6f` | 41 passed |
| Full suite | `uv run --extra dev pytest` | 0 | `sha256:561cf2c7045561b99c7c25933b57bd82cdc50461141a84912876dfbec5692d23` | 179 passed, 3 skipped |
| Ruff/static quality | `uv run --extra dev ruff check .` | 0 | `sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` | All checks passed |
| CLI replay 1 | `uv run --extra dev invest-backtest --universe fixtures/backtest/universe.json --bars fixtures/backtest/bars.json --split-date 2024-01-23 --format json` | 0 | `sha256:260a294d92676f9be9e5681f2c4bd149d6f75ded2cc8413f5ac32e58f6860b05` | Stable JSON report produced |
| CLI replay 2 | Same command as CLI replay 1 | 0 | `sha256:260a294d92676f9be9e5681f2c4bd149d6f75ded2cc8413f5ac32e58f6860b05` | Byte-identical to replay 1 (`cmp` exit 0) |

### Build & Tests Execution

**Build/static quality**: Passed

```text
uv run --extra dev ruff check .
All checks passed!
```

**Tests**: Passed

```text
uv run --extra dev pytest
179 passed, 3 skipped in 3.95s
```

**Focused tests**: Passed

```text
uv run --extra dev pytest tests/domain/test_backtest_metrics.py tests/application/test_backtest_run.py tests/adapters/test_cli_backtest.py
41 passed in 0.38s
```

**Coverage**: Not available. `pyproject.toml` dev extras include `pytest` and `ruff`; no coverage tool is configured.

### Spec Compliance Matrix

| Requirement | Scenario | Runtime evidence | Result |
|-------------|----------|------------------|--------|
| Portfolio-aware backtest accounting | Overlapping entries consume finite capital | `tests/application/test_backtest_run.py::test_portfolio_replay_orders_same_day_entries_and_enforces_deployed_cap`; focused/full pytest passed | ✅ COMPLIANT |
| Portfolio-aware backtest accounting | Capital unavailable skips entry | `test_portfolio_replay_records_insufficient_buying_power_as_visible_skip`; `test_entry_gap_is_rejected_when_actual_next_open_cost_exceeds_cash`; focused/full pytest passed | ✅ COMPLIANT |
| Portfolio-aware backtest accounting | Exits release portfolio capacity | `test_portfolio_replay_releases_cash_on_exit_and_uses_prior_equity_for_kill_switch`; focused/full pytest passed | ✅ COMPLIANT |
| Deterministic simulated gate telemetry | Gate pressure is counted by reason | `test_portfolio_replay_orders_same_day_entries_and_enforces_deployed_cap`; `test_portfolio_replay_records_insufficient_buying_power_as_visible_skip`; CLI replay includes `gates.label=portfolio-gates-simulated`; focused/full pytest and CLI replay passed | ✅ COMPLIANT |
| Deterministic simulated gate telemetry | Kill-switch uses prior-session equity | `test_portfolio_replay_releases_cash_on_exit_and_uses_prior_equity_for_kill_switch`; focused/full pytest passed | ✅ COMPLIANT |
| Deterministic simulated gate telemetry | Same replay has same telemetry | `test_replaying_same_range_twice_is_byte_identical`; independent CLI replay hashes match and `cmp` exit 0 | ✅ COMPLIANT |
| Daily equity summary and split-date metrics | Daily summary is observable | `tests/domain/test_backtest_metrics.py::test_equity_summary_reports_drawdown_and_is_deterministic`; CLI replay includes `equity` fields; focused/full pytest and CLI replay passed | ✅ COMPLIANT |
| Daily equity summary and split-date metrics | Trades are split by entry date | `test_segment_metrics_classifies_split_date_entries_as_oos`; CLI replay includes `segments.is` and `segments.oos`; focused/full pytest and CLI replay passed | ✅ COMPLIANT |
| Daily equity summary and split-date metrics | Invalid split date fails closed | `tests/adapters/test_cli_backtest.py::test_backtest_requires_valid_in_range_split_date_as_one_json_error`; `test_backtest_rejects_malformed_or_out_of_range_split_date`; focused/full pytest passed | ✅ COMPLIANT |
| Mandatory portfolio-backtest limitations | Required limitation labels are present | `test_backtest_report_exposes_portfolio_contract_and_all_limitations`; CLI replay includes day-0, survivorship, cost-model, portfolio-gates, static-universe-OOS, and execution-realism disclaimers | ✅ COMPLIANT |
| Mandatory portfolio-backtest limitations | Broker and live trading remain isolated | `test_backtest_bars_run_prints_one_report_with_metrics_and_disclaimers_and_touches_no_broker`; `test_backtest_report_exposes_portfolio_contract_and_all_limitations`; source inspection confirms `backtest_main` uses `BacktestRun` and does not construct `AlpacaBroker` | ✅ COMPLIANT |

**Compliance summary**: 11/11 scenarios compliant.

### Corrected Behavior Verification

| Historical finding / risk | Current evidence | Status |
|---|---|---|
| Portfolio cash/equity/gates ignored configured costs | `src/invest/application/backtest_run.py` uses `entry_fill(...)` and `exit_proceeds(...)` in entry cost, cash release, marking, deployed capital; `test_portfolio_cash_and_equity_use_configured_entry_slippage` passed | ✅ Corrected |
| Missing daily bar silently dropped open-position value | `_mark_positions` carries prior marked value; `missing-bar-carried-forward` warning emitted; `test_open_position_without_daily_bar_carries_last_valuation_with_warning` passed | ✅ Corrected |
| Entry opening gap could exceed cash/capacity | Entry intent is adjusted to actual next open via `entry_fill(entry_bar.open, ...)` before `evaluate_gates`; `test_entry_gap_is_rejected_when_actual_next_open_cost_exceeds_cash` passed | ✅ Corrected |
| Repeated accepted signal overwrote an open symbol | `replay` checks `decision.symbol in positions` and records `already-submitted`; `test_repeated_accepted_signal_does_not_overwrite_open_position_or_cash` passed | ✅ Corrected |
| Invalid cost inputs accepted | `_valid_cost_model` rejects negative, infinite, NaN, and out-of-range costs; `test_backtest_rejects_invalid_cost_model_values_with_one_json_error` passed | ✅ Corrected |

### Correctness (Static Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| Portfolio-aware accounting | ✅ Implemented | `BacktestRun.replay(...)` tracks cash, marked equity, positions, deployed capital, exits, skipped entries, metrics, portfolio summary, and warnings. |
| Simulated gate telemetry | ✅ Implemented | Existing `compute_intent`, `evaluate_halt_gates`, and `evaluate_gates` are reused; `GateReason` values populate `GateTelemetry("portfolio-gates-simulated", ...)`. |
| Equity summary and split metrics | ✅ Implemented | `compute_equity_summary(...)` and `compute_segment_metrics(...)` are pure helpers; CLI requires in-range `--split-date`. |
| Mandatory limitations and isolation | ✅ Implemented | CLI emits machine-readable warnings/disclaimers; focused tests monkeypatch broker construction to fail if touched. |

### Coherence (Design)

| Design decision | Followed? | Notes |
|---|---|---|
| Keep seam at `BacktestRun.replay(...)` | ✅ Yes | No separate portfolio engine introduced. |
| Reuse existing pure gates unchanged | ✅ Yes | `compute_intent`, `evaluate_halt_gates`, and `evaluate_gates` are called from replay. |
| Report equity summaries, not full curve | ✅ Yes | CLI emits summary fields only. |
| Segment IS/OOS by entry date around explicit split | ✅ Yes | `compute_segment_metrics` uses `< split_date` for IS and `>= split_date` for OOS. |
| Preserve out-of-scope boundaries | ✅ Yes | No point-in-time universe, confirmation, richer execution, or broker control added. |

### TDD Compliance

| Check | Result | Details |
|-------|--------|---------|
| TDD evidence reported | ✅ | `apply-progress.md` includes a TDD Cycle Evidence table. |
| All tasks have tests | ✅ | 3/3 reported test files exist. |
| RED confirmed | ✅ | RED failure signatures are recorded per row in `apply-progress.md`; test files are present. |
| GREEN confirmed | ✅ | Focused touched tests passed now: 41/41. |
| Triangulation adequate | ✅ | Current focused files cover cost variance, missing-bar, entry-gap, repeat-signal, split-date, invalid-cost, and broker-isolation cases. |
| Safety net for modified files | ✅ | Full suite passed now: 179 passed, 3 skipped. |

**TDD Compliance**: 6/6 checks passed.

### Test Layer Distribution

| Layer | Tests | Files | Tools |
|-------|------:|------:|-------|
| Unit | 7 | 1 | pytest |
| Integration | 34 | 2 | pytest + fixture CLI harness |
| E2E | 0 | 0 | Not configured |
| **Total** | **41** | **3** | |

### Changed File Coverage

Coverage analysis skipped — no coverage tool is configured in `pyproject.toml` dev extras.

### Assertion Quality

| File | Result |
|------|--------|
| `tests/domain/test_backtest_metrics.py` | ✅ Behavioral value assertions over pure metrics/cost/summary/segment outputs |
| `tests/application/test_backtest_run.py` | ✅ Behavioral value assertions over replay results, gates, cash/equity, warnings, deterministic equality |
| `tests/adapters/test_cli_backtest.py` | ✅ Behavioral assertions over CLI exit codes, one-record JSON output, report contract, limitations, and broker isolation |

**Assertion quality**: ✅ All assertions verify real behavior. No tautologies, ghost loops, production-free assertions, or smoke-only tests found.

### Quality Metrics

**Linter**: ✅ No errors (`uv run --extra dev ruff check .`, exit 0)  
**Type Checker**: ➖ Not available/configured  
**Coverage**: ➖ Not available/configured

### Notes on Verification Method

- CodeGraph initialization was attempted before broad structural exploration, but `gentle-ai codegraph init --cwd /Users/rcty/invest` returned `Error: unsafe CodeGraph root "/Users/rcty/invest"`; verification fell back to the explicit artifact/source/test paths named by the SDD artifacts.
- Existing `.env` and `universe.json` are untracked and explicitly out of scope per review policy. They were not read.

### Issues Found

**CRITICAL**: None.

**WARNING**:
- `src/invest/application/backtest_run.py:10-13` has stale module documentation saying portfolio construction/gates are not simulated, while the current implementation and design require simulated gates. Runtime behavior is compliant, but the comment should be corrected in a follow-up cleanup.
- `src/invest/application/backtest_run.py:308-341` retains legacy `_simulate_trade(...)`, apparently unused by current replay. This does not break the spec but adds maintenance noise.

**SUGGESTION**:
- Add coverage tooling only if the project wants changed-file coverage gates; current dev toolchain does not include it.

### Verdict

PASS WITH WARNINGS

Independent Strict TDD verification passed: focused tests, full pytest suite, ruff, and deterministic CLI replay all exited 0; 4/4 requirements and 11/11 scenarios have passing runtime coverage. Warnings are cleanup/readability issues, not blockers or critical spec failures.
