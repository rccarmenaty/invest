# Tasks: Backtest Spec-Compliant Baseline

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~350-400 (authored) |
| Files touched | 4 prod (`sizing.py`, `indicators.py`, `backtest_run.py`, `execute_run.py`) + 4 test files |
| 400-line budget risk | Medium (borderline) |
| Chained PRs recommended | No (single cohesive slice; see optional split below) |
| Suggested split | Single PR (optional 2-unit split available if diff exceeds budget) |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium

### Suggested Work Units (optional fallback if diff exceeds 400 lines)

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | ATR period param + sizing rewrite (risk/stop/TP), self-contained domain logic | PR 1 | `.venv/bin/python -m pytest tests/domain/test_indicators.py tests/domain/test_sizing.py` | N/A — pure Decimal domain math, no external harness | Revert `sizing.py`/`indicators.py` + their tests |
| 2 | backtest_run.py fill-site wiring + ranked fill + cooldown + execute_run.py caller | PR 2 | `.venv/bin/python -m pytest tests/application/test_backtest_run.py tests/application/test_execute_run.py` | N/A — replay harness runs on fixture bars only | Revert `backtest_run.py`/`execute_run.py` + their tests (depends on Unit 1 merged first) |

## Phase 0: Baseline

- [x] 0.1 Run `.venv/bin/python -m pytest --collect-only -q` from repo root to confirm the runner and current suite collect cleanly before edits.

## Phase 1: indicators.py — ATR period param

- [x] 1.1 RED `tests/domain/test_indicators.py`: add `test_average_true_range_period_20_uses_wider_window` and `test_average_true_range_default_period_still_14` (scenario: benchmark byte-identical / ATR default-14 unchanged).
- [x] 1.2 GREEN `src/invest/domain/indicators.py`: add `period: int = ATR_DAYS` to `average_true_range()`; slice `ranges[-period:]`.

## Phase 2: sizing.py — risk/structural-stop/TP rewrite

- [x] 2.1 RED `tests/domain/test_sizing.py`: rewrite the 4 existing `compute_intent` tests for new signature `compute_intent(symbol, decision_date, equity, history, entry_price, breakout_low)`.
- [x] 2.2 RED `tests/domain/test_sizing.py`: add tests for scenarios "Structural stop picks the lower of the two candidates", "Gap-up entry re-sizes from the actual fill price", "Degenerate stop distance skips the intent", "Zero or negative quantity skips the intent", and TP assertion (`entry + 2×ATR20`, both stop-winner cases).
- [x] 2.3 GREEN `src/invest/domain/sizing.py`: `RISK_PER_TRADE = Decimal("0.0035")`, add `STOP_ATR_DAYS = 20`; new signature; `stop = min(quantize(breakout_low), entry - 2*ATR(period=20))`; `take_profit = entry + 2*ATR(period=20)` (same ATR value); unified `SIZING_INVALID` on `stop_distance <= 0` or `qty <= 0`.

## Phase 3: backtest_run.py — fill-site wiring

- [x] 3.1 RED `tests/application/test_backtest_run.py`: cover fill-day-open + breakout-day-low basis via Phase 4's rewritten/added tests (no standalone case needed — same call site).
- [x] 3.2 GREEN `src/invest/application/backtest_run.py:215-221`: call `compute_intent(decision.symbol, decision.decision_date, marked_equity, symbol_bars[:signal_index], entry_bar.open, symbol_bars[signal_index].low)`; leave slippage post-step at `:222-224` unchanged.

## Phase 4: backtest_run.py — ranked same-day fill

- [x] 4.1 RED `tests/application/test_backtest_run.py`: rewrite `test_portfolio_replay_orders_same_day_entries_and_enforces_deployed_cap` (:692) — give BRAVO higher 252/21-day momentum, assert `trades == ["BRAVO"]`, ALPHA skipped `max-equity-deployed` (scenario: "Higher-momentum symbol fills first when capital admits only one").
- [x] 4.2 RED `tests/application/test_backtest_run.py`: add short-history (~21 bar, benchmark-shaped) fallback case asserting liquidity-then-symbol order, NOT alphabetical (design: Benchmark-Strategy Interaction).
- [x] 4.3 GREEN `src/invest/application/backtest_run.py`: add `RANK_MOMENTUM_FAR=252`, `RANK_LIQUIDITY_WINDOW=20`, `_fill_rank_key()` per design; replace `sorted(pending[current_date], key=lambda item: item.symbol)` (:194) with `sorted(pending[current_date], key=self._fill_rank_key)`.

## Phase 5: backtest_run.py — re-entry cooldown

- [x] 5.1 RED `tests/application/test_backtest_run.py`: add `test_cooldown_blocks_reentry_for_ten_sessions_then_allows_at_eleven` (scenario: "Cooldown blocks re-entry within 10 sessions of any close").
- [x] 5.2 RED `tests/application/test_backtest_run.py`: add `test_forced_close_also_starts_cooldown`, closing via `_process_unsafe_positions` (scenario: "Forced close also starts the cooldown").
- [x] 5.3 RED `tests/application/test_backtest_run.py`: add `test_scan_decisions_ignores_cooldown_state` (scenario: "scan_decisions() remains unaffected by cooldown").
- [x] 5.4 GREEN `src/invest/application/backtest_run.py`: add `COOLDOWN_SESSIONS=10`, `COOLDOWN_SKIP_REASON="cooldown-active"`; enumerate `sorted(bars_by_date)` to `session_index`; `cooldown_release: dict[str,int]`; snapshot `day_start=len(trades)` per day, after settle set `cooldown_release[symbol]=session_index+COOLDOWN_SESSIONS+1` for `trades[day_start:]` where `exit_reason != "open-at-end"`; gate check in pending loop after the already-submitted check.

## Phase 6: execute_run.py — caller wiring

- [x] 6.1 RED `tests/application/test_execute_run.py`: adjust any assertions hardcoded to old 1%/ATR14 constants for new 0.35%/ATR20 values; confirm breakout-low context flows.
- [x] 6.2 GREEN `src/invest/application/execute_run.py:76-82`: call `compute_intent(decision.symbol, decision.decision_date, snapshot.equity, history, bars[-1].close, bars[-1].low)`.

## Phase 7: Full suite + lint

- [x] 7.1 `.venv/bin/python -m pytest` — full suite green (613 passed, 1 skipped [credentials-gated], 1 deselected [pre-existing Docker-build acceptance test, unrelated to this change, ~10+min build]).
- [x] 7.2 `.venv/bin/ruff check .` — lint clean for `src/` and `tests/` (repo-wide `ruff check .` flags only an untracked, out-of-scope scratch file at `fixtures/real-continuous/reports/uncap_backtest.py`, not part of this change or the source tree).

## Out of Scope

- Backtest reruns (capped, uncapped, §2.5 benchmark control) are post-verify and orchestrator-owned per proposal Success Criteria — NOT part of `sdd-apply`.
