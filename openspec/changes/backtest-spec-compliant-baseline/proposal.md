# Proposal: Backtest Spec-Compliant Baseline (Step 3 Measurement Fixes)

## Intent

The current backtest measures an interim configuration, not the SPEC.md strategy: alphabetical candidate fill (violates §2.4), 1×ATR(14) stop vs structural min(breakout-day low, entry − 2×ATR(20)) (§2.7), no 10-session re-entry cooldown (SPEC.md:135, state machine :240-248), and 1% risk vs 0.35% (§2.8). Evidence: 73% of 4,683 uncapped trades die at the 1×ATR stop while the event study (n=12,295) shows +0.98%/20d drift (t=3.31) with a 48.5% coin-flip race to ±1×ATR — the stop sits inside the noise band and destroys measured drift; 7,457 already-submitted skips show re-signal clustering. This is a measurement fix so Step 4+ experiments are interpretable, NOT a tuned result. No performance claims.

## Scope

### In Scope
1. Ranked candidate fill: momentum rank → 52-week-high proximity → liquidity, replacing alphabetical sort at `backtest_run.py:194`.
2. Structural initial stop min(breakout-day low, entry − 2×ATR(20)); qty from actual stop distance.
3. 10-session per-symbol cooldown after ANY position close (SPEC literal wording wins over the research brief's stop-out-only framing — orchestrator decision).
4. `RISK_PER_TRADE` 0.01 → 0.0035.
5. §2.5 control comparison as verification/reporting protocol only (`cli.py --strategy benchmark|core` already wired — zero new production code).

### Out of Scope
§2.3 regime gate, volatility scaling, trailing-exit changes, parameter grids/tuning, scanner changes, `scan_decisions()` collector changes, `ScanDecision` extension.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `trading-system`: "Position sizing and bracket price math" (spec.md:414-430) — 0.35% risk, structural stop, ATR(20); "Pre-trade risk gates" (:432-465) — new cooldown gate requirement; "Portfolio-aware backtest accounting" (:741-763) — ranked same-day fill ordering replaces alphabetical.

## Decisions (resolved)

1. **Stop/qty basis: actual fill-day open, computed at fill time.** SPEC §2.7 defines the stop from *entry*, and entry is the next-session open (§2.4). The backtest knows the fill-day open at fill time with no look-ahead (stop applies only after the fill). A signal-day-close proxy would systematically mis-size on gaps — the exact distortion this change removes.
2. **Ranked fill via Approach 1** (exploration): local ranking in `backtest_run.py` from `by_symbol` bar history using existing pure reducers; `ScanDecision` and both scanners untouched. Lower blast radius; duplication of rank math is acceptable and test-pinned.
3. **ATR(20) delivery: optional `period` param on `average_true_range()`, default 14.** Preserves `scanner.py`/`exit_policy.py` callers and the byte-identical benchmark scenario (trading-system/spec.md:856-860).
4. **Sizing changes flow to live/paper too.** `sizing.py` is shared and SPEC §§2.7/2.8 are system-wide. Implication: `compute_intent()` needs breakout-day-low context; the live/paper path sizes from its pre-submission reference price (fill-time recompute for live is future work, documented as such).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/invest/application/backtest_run.py` | Modified | Ranked fill; cooldown gate in `replay()` pending-fill loop |
| `src/invest/domain/sizing.py` | Modified | Risk 0.0035, structural stop, ATR(20) basis |
| `src/invest/domain/indicators.py` | Modified | Optional `period` param (default 14) |
| `openspec/specs/trading-system/spec.md` | Modified | Deltas for :414-430, :432-465, :741-763 |
| Tests (`test_sizing.py`, `test_indicators.py`, `test_backtest_run.py:692`) | Modified | Rewrite behavior-pinned tests incl. alphabetical-fill test |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Constant changes alter live/paper sizing | High (intended) | Spec deltas make it explicit; paper-first gates intact, no live path exists |
| ATR(20) param breaks ATR(14) callers / benchmark byte-identity | Low | Default 14 unchanged; benchmark scenario asserted in tests |
| Wider stops shift exit-reason mix; distribution-asserting tests break | Med | Expected per research plan; update tests, no metric assertions on mix |
| Ranking/cooldown leaks into scanners or `scan_decisions()` | Low | Logic confined to `replay()`; exploration convention pinned |

## Rollback Plan

Single branch revert; constants and sort are localized. No data migration, no contract/schema change, no external state.

## Dependencies

None. Item 5 depends only on existing `--strategy` flag.

## Success Criteria

- [ ] All tests green, including rewritten ranked-fill test (replaces alphabetical assertion at `test_backtest_run.py:692`).
- [ ] Benchmark strategy scenario byte-identical (ATR(14) callers unaffected).
- [ ] Cooldown blocks re-entry for 10 sessions after any close, with machine-readable skip reason.
- [ ] Post-verify experiment: rerun capped + uncapped backtest and §2.5 benchmark control under identical replay assumptions; report comparison (no performance claims).

## Proposal question round

Non-interactive execution; orchestrator pre-resolved the open questions. Assumptions needing user review if any feel wrong: (a) fill-day-open stop basis, (b) sizing constants flowing to live/paper now, (c) cooldown after ANY close.
