# Exploration: backtest-spec-compliant-baseline (Step 3 measurement fixes)

**Change:** backtest-spec-compliant-baseline
**Date:** 2026-07-19
**Source plan:** docs/research/first-backtest-failure-research-plan-fable-5.md §5 Step 3
**Baseline code:** main @ 0eeb903, branch feat/backtest-spec-compliant-baseline

## Current State

**Ranked fill (item 1)** — `src/invest/application/backtest_run.py:194`: `for decision in sorted(pending[current_date], key=lambda item: item.symbol):` fills same-day candidates alphabetically before capital gates (`MAX_CONCURRENT_POSITIONS`, `MAX_EQUITY_DEPLOYED_RATIO`, buying power) are checked per-candidate in that order. Confirmed by `tests/application/test_backtest_run.py:692` (`test_portfolio_replay_orders_same_day_entries_and_enforces_deployed_cap`), which explicitly asserts ALPHA beats BRAVO purely by name.

**Initial stop (item 2)** — `src/invest/domain/sizing.py:8-10`: `RISK_PER_TRADE = 0.01`, `STOP_ATR_MULTIPLIER = 1`. `indicators.py:6-15` `average_true_range()` takes no period arg (hardcoded `ATR_DAYS = 14`, shared by `scanner.py`'s spike-detector and `exit_policy.py`'s ATR-trail variant). The breakout-day bar is `symbol_bars[signal_index]` in `backtest_run.py` — its `.low` is directly available at the fill site with no look-ahead issue, since entry executes on the next session's open (`entry_bar = todays_bars[decision.symbol]`, a later bar).

**Cooldown (item 3)** — no cooldown state exists anywhere in `backtest_run.py`. **Important finding**: the task brief framed this as "after a stop-out," but SPEC.md itself is broader — `SPEC.md:135` ("10 sessions per symbol after **close**") and `SPEC.md:240-248`'s state machine (`CLOSED (trailing exit / stop / time-stop / broker action) → COOLDOWN → NONE`) mandate cooldown after **any** position close, not just hard-stop-outs.

**Risk sizing (item 4)** — `RISK_PER_TRADE = Decimal("0.01")`, SPEC §2.8 wants `0.0035`.

**Control run (item 5)** — already fully wired: `cli.py:53,168,240` (`BACKTEST_STRATEGIES = ("benchmark", "core")`, defaults to `"benchmark"` = `MomentumScanner`, `"core"` = `MomentumSelectionScanner`), plus a complete capability-spec requirement (`openspec/specs/trading-system/spec.md:852-916`) and CLI test coverage (`tests/adapters/test_cli_backtest.py:801-850`). This item needs **no new production code** — it's an invocation/reporting task.

## Affected Areas

- `src/invest/application/backtest_run.py:194` — alphabetical fill sort (item 1), and the natural home for new cooldown-gate checks (near line 195's already-submitted check)
- `src/invest/domain/sizing.py:8-10,34-63` — `RISK_PER_TRADE`, `STOP_ATR_MULTIPLIER`, `compute_intent()` (items 2, 4)
- `src/invest/domain/indicators.py:6-15` — `average_true_range()` needs an optional `period` param (default 14, preserving `scanner.py`/`exit_policy.py` callers)
- `src/invest/domain/models.py:35-40` — `ScanDecision` intentionally NOT recommended for extension (see approaches)
- `openspec/specs/trading-system/spec.md:414-430` (position sizing requirement, needs delta) and `:432-465` (pre-trade risk gates, natural home for a cooldown gate requirement)
- `tests/domain/test_sizing.py`, `tests/domain/test_indicators.py`, `tests/application/test_backtest_run.py:692` — existing tests coupled to current behavior that will need rewriting

## Approaches

1. **Local ranking computation inside `backtest_run.py`** (recommended) — compute momentum-return/proximity/liquidity directly from existing `by_symbol` bar history using existing pure reducers (`momentum_return`, `trailing_high`), keeping `ScanDecision` and both scanners untouched.
   - Pros: no shared-contract changes, no blast radius into journal/contracts/both scanners; matches `momentum_selection_scanner.py`'s explicit "no changes to sibling scanner" convention.
   - Cons: duplicates rank math that `MomentumSelectionScanner` already computes internally then discards.
   - Effort: Medium

2. **Extend `ScanDecision` with rank/proximity/liquidity fields**, populated by both scanners.
   - Pros: single source of truth for ranking data.
   - Cons: touches a shared dataclass used by journal/contracts/CLI event plumbing across both scanners; higher blast radius; `MomentumSelectionScanner`'s own spec explicitly scopes out extra responsibilities.
   - Effort: High

## Recommendation

Approach 1 for ranked fill. Implement items 1-4 as narrowly-scoped, largely independent changes in `backtest_run.py`/`sizing.py`/`indicators.py`. Treat item 5 as verification only (flag already exists). Resolve the stop/qty proxy-entry-vs-real-fill-price question explicitly in proposal before implementation.

**Orchestrator decision (post-exploration):** cooldown scope follows SPEC literally — after **any** position close (SPEC.md:135, state machine SPEC.md:240-248). The whole point of this change is spec compliance; the stop-out-only framing in the research brief is superseded.

## Risks

- `sizing.py`'s `compute_intent`/`RISK_PER_TRADE`/`STOP_ATR_MULTIPLIER` are also consumed by the live/paper execution path per `openspec/specs/trading-system/spec.md`'s existing requirements — changing these constants affects live/paper sizing too, not just backtest; verify the live path can supply "breakout-day low" context.
- ATR(20) parameterization must not alter `scanner.py`'s ATR(14) spike-detector or `exit_policy.py`'s ATR-3-high-water variant (both depend on the current default-14 behavior); a byte-identical-benchmark spec scenario (`trading-system/spec.md:856-860`) would break otherwise.
- Wider structural stops (breakout-day low or 2×ATR20 vs. 1×ATR14) will shift the exit-reason mix toward the ten-day-low trailing mechanism — expected per the research plan, but downstream tests/metrics asserting specific exit-reason distributions will need updates.
- `scan_decisions()` (position-blind collector) must remain untouched — ranking and cooldown logic must live exclusively in `replay()`'s pending-fill loop, never in the scanners or `scan_decisions()`.
- Qty/stop-distance calc ambiguity between signal-day-close proxy entry vs. true next-session-open fill price — must be decided in proposal.

## Ready for Proposal

Yes.
