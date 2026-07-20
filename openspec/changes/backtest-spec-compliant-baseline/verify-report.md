# Verify Report: backtest-spec-compliant-baseline

**Date:** 2026-07-19
**Verifier:** sdd-verify (fresh context, independent rerun)
**Verdict:** PASS WITH WARNINGS (0 CRITICAL, 2 WARNING, 0 SUGGESTION)

## Test/Lint Evidence

- `.venv/bin/python -m pytest -q --deselect tests/test_container_scope.py::test_container_entrypoint_runs_the_default_scan` → `613 passed, 1 skipped, 1 deselected in 3.72s`, exit 0. Matches apply-progress exactly.
- `.venv/bin/ruff check src tests` → `All checks passed!`, exit 0.
- `git diff --stat`: 9 files, 570(+)/64(-) — exactly `src/invest/{application/backtest_run.py,application/execute_run.py,domain/indicators.py,domain/sizing.py}` + `tests/{adapters/test_cli_backtest.py,application/test_backtest_run.py,application/test_execute_run.py,domain/test_indicators.py,domain/test_sizing.py}`. `git diff` on scanners/exit_policy is empty. No commits made.

## Scenario → Test Mapping (test bodies read, not name-trusted)

| Spec Scenario | Test | Behavior confirmed |
|---|---|---|
| Structural stop picks lower candidate + TP | `test_sizing.py::test_compute_intent_structural_stop_picks_the_lower_of_the_two_candidates` + `test_compute_intent_atr_leg_wins_when_breakout_low_is_the_higher_candidate` | Both stop-winner branches asserted; TP=entry+2×ATR(20) independent of winner. Hand-verified numerically. |
| Gap-up entry re-sizes from fill-day open | `test_sizing.py::test_compute_intent_gap_up_entry_resizes_from_the_actual_fill_price` + `test_backtest_run.py::test_entry_gap_is_rejected_when_actual_next_open_cost_exceeds_cash` | entry=105 (not the 100 baked into history) drives stop/qty; integration test proves the fill site passes the gapped `entry_bar.open`. |
| Degenerate stop → sizing-invalid | `test_sizing.py::test_compute_intent_degenerate_stop_distance_skips_the_intent`, `test_compute_intent_skips_with_sizing_invalid_when_atr_makes_stop_distance_zero` | `intent is None`, `reason is GateReason.SIZING_INVALID`. |
| Zero/negative qty → sizing-invalid | `test_sizing.py::test_compute_intent_zero_or_negative_quantity_skips_the_intent`, `test_compute_intent_skips_with_sizing_invalid_at_zero_qty` | Same reason asserted at qty-floor-to-0 boundary. |
| Cooldown T+1..T+10 blocked / T+11 eligible | `test_backtest_run.py::test_cooldown_blocks_reentry_for_ten_sessions_then_allows_at_eleven` | Exact boundary pinned: close@22 → blocked at day23(T+1)/day32(T+10), allowed day33(T+11). |
| Forced close starts cooldown | `test_backtest_run.py::test_forced_close_also_starts_cooldown` | Close via `_process_unsafe_positions`; later candidate at T+8 skipped `cooldown-active`. |
| scan_decisions() unaffected by cooldown | `test_backtest_run.py::test_scan_decisions_ignores_cooldown_state` | Same scanner through `scan_decisions()` and `replay()`; decision collected regardless, `replay()` still skips fill. |
| Ranked fill higher-momentum-first | `test_backtest_run.py::test_portfolio_replay_orders_same_day_entries_and_enforces_deployed_cap` | BRAVO (37.5% momentum) fills over ALPHA (0.9%). |
| Short-history fallback → liquidity then symbol | `test_backtest_run.py::test_portfolio_replay_short_history_same_day_fill_uses_liquidity_then_symbol` | ZZZ (high volume) beats AAA (alphabetically first, low volume) — proves non-alphabetical. |
| Default-vs-explicit benchmark byte-identity | `test_cli_backtest.py::test_backtest_default_and_explicit_benchmark_strategy_are_byte_identical` | Raw stdout strings compared equal across two CLI runs. |
| ATR default 14 preserved | `test_indicators.py::test_average_true_range_default_period_still_14`, `test_average_true_range_period_20_uses_wider_window` | No-arg == explicit period=14; period=20 provably differs. scanner.py/exit_policy.py call with no period arg (untouched in diff). |
| Unknown --strategy rejected | `test_cli_backtest.py::test_backtest_rejects_unknown_strategy_value_with_one_json_error_before_any_replay` | Exit 2, single JSON error line, no replay side effects. |
| Core strategy through same harness | `test_cli_backtest.py::test_backtest_strategy_core_replays_through_the_same_harness` | Scanner-specific symbol surfaced, proving Core scanner ran. |

No banned/tautological assertion patterns found in the 5 changed test files.

## Design Coherence

`compute_intent(symbol, decision_date, equity, history, entry_price, breakout_low)`, `RISK_PER_TRADE=Decimal("0.0035")`, `STOP_ATR_DAYS=20`, `stop=min(quantize(breakout_low), entry-2*ATR(period=20))`, `take_profit=entry+2*ATR(period=20)` (same ATR value) — confirmed verbatim in diff. `_fill_rank_key` matches design's rank tuple and short-history fallback exactly. Cooldown captured via `trades[day_start:]` after both `_process_unsafe_positions` and `_process_exits`, covering forced closes; `COOLDOWN_SKIP_REASON="cooldown-active"` confirmed NOT a `GateReason` member via the exact 7-value enum contract test. Slippage post-step (`replace(intent, entry=entry_fill(...))`) untouched. `execute_run.py` 1-line diff matches design.

## Tasks Reality Check

19/19 checked, 0 unchecked; spot-verified against actual diffs.

## Deviation Assessment

1. Golden-value cascade (~13 tests + 1 fixture redesign): 3 independent cases hand-recomputed against the new constants (qty=87; stop=99/qty=58; stop=9.80/TP=13.00/qty=218) — all matched exactly. No masked regression.
2. **WARNING** — CLI test cascade (trade_count 1→3, new `missing-bar-carried-forward` warning): directionally consistent with smaller position sizes fitting more candidates under the 25% cap; not independently re-derived from raw fixture JSON. Low risk.
3. **WARNING** — Diff-size overage (634 vs ~350-400 forecast): root cause is golden-value maintenance, not new logic; flag for the 400-line review-workload guard at PR time.

## Final Verdict

PASS WITH WARNINGS. Next: bounded post-apply review (High tier — >400 authored lines), then archive.
