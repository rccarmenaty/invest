# Exploration: trailing-exit-engine

**Change**: `trailing-exit-engine` (roadmap change B)
**Date**: 2026-07-16
**Engram**: `sdd/trailing-exit-engine/explore`

## Current State

### Product intent (SPEC / ROADMAP)

- `ROADMAP.md` §5 change **B** is next and unblocks **C** (`regime-and-vol-sizing`).
- Target exit model is `SPEC.md` §2.7:
  - Trailing exit: close below prior **10-day low** → exit **next session**; ratchet daily, **never loosen**.
  - Time stop: exit after **20 sessions** if trade has not reached **+0.5R** or a **new 20-day high**.
  - Test-grid siblings include **3 ATR trailing** (feeds conflict #1: native Alpaca trailing-stop vs 10-day-low channel).
- Scope is **backtest-only**. Phase-3 / paper Alpaca execution model is explicitly deferred to change **D**.

### Implemented interim exit model

| Layer | Behavior today |
|---|---|
| `domain/sizing.py` | `compute_intent`: stop = entry − 1×ATR(14); take-profit = entry + 2×ATR(14); 1% risk. Constants `STOP_ATR_MULTIPLIER=1`, `TAKE_PROFIT_ATR_MULTIPLIER=2`. |
| `OrderIntent` | Frozen fields include required `take_profit`. Used by paper path and backtest entry. |
| `BacktestRun._OpenPosition` | Stores fixed `stop` + `take_profit` at entry; no trailing state, no session counter, no high-water mark. |
| `BacktestRun._exit_for_bar` | Intrabar: `low <= stop` → fill `min(open, stop)`, reason `"stop"`; else `high >= take_profit` → fill `take_profit`, reason `"take-profit"`; same-bar **stop wins**. |
| `BacktestRun._simulate_trade` | Dead/duplicate path with the same stop/TP rules (PIT review already flagged divergence risk). Active path is `_process_exits` / `_exit_for_bar`. |
| `ExitReason` | Contract set is exactly `{"stop", "take-profit", "open-at-end"}` (`tests/domain/test_backtest_metrics.py`). Forced closes use string `"context-position-forced-closed"`. |
| Paper path | `ExecuteRun` + `alpaca_broker.submit_bracket` still submit full brackets with `take_profit.limit_price`. **Must stay untouched in this change.** |

### Existing pure building blocks (reusable)

- `domain/indicators.py`: `average_true_range`, `trailing_high`, SMA helpers. **No `trailing_low`.**
- Day-by-day replay already has chronological symbol bars, pending next-open entries, unsafe forced closes before ordinary exits, cash settlement, and gate telemetry.
- CLI already has backtest-only flags (`--strategy`, `--split-date`, `--market-context`) with boundary tests forbidding execute-path leakage — same pattern for an exit-policy flag.

### Gap vs §2.7

1. Fixed 2-ATR take-profit truncates winners (exactly what research rejects).
2. No never-loosening trailing level (channel or ATR).
3. No close-signal → next-session exit semantics (current TP is same-bar high-touch).
4. No time stop / R-progress / 20-day-high progress checks.
5. No exit-policy grid seam for 10-day-low vs 3-ATR-trail comparison.

## Affected Areas

| Path | Why |
|---|---|
| `src/invest/domain/indicators.py` | Add `trailing_low(bars, window)` (mirror of `trailing_high`). |
| **New** `src/invest/domain/exit_policy.py` (name TBD) | Pure exit engine: initial stop retention, never-loosen ratchet, 10-day-low channel signal, 3-ATR trail level, time-stop predicate, deterministic priority / fill rules. |
| `src/invest/domain/backtest_metrics.py` | Extend `ExitReason` (`trailing-exit`, `time-stop`, optionally `atr-trail`; retire or retain `take-profit` for benchmark-compat mode). |
| `src/invest/application/backtest_run.py` | Replace fixed-TP exit path; hold trailing state on open positions; optional exit-policy config; stop writing exits from `intent.take_profit`. Prefer delete or quarantine `_simulate_trade`. |
| `src/invest/domain/models.py` | Possibly small position/exit DTOs if pure functions need structured state; **do not remove** `OrderIntent.take_profit` (paper contracts). |
| `src/invest/adapters/cli.py` | Optional backtest-only `--exit-policy` (or equivalent) for grid cells; report already serializes `exit_reason`. |
| `tests/domain/test_indicators.py` | TDD for `trailing_low`. |
| **New** `tests/domain/test_exit_policy.py` | Strict unit seams for ratchet, never-loosen, time stop, priority, fill prices. |
| `tests/application/test_backtest_run.py` | Replace take-profit scenarios; add trailing / time-stop / next-session fill / grid-variant integration tests. |
| `tests/domain/test_backtest_metrics.py` | Update `ExitReason` contract set. |
| `tests/test_boundaries.py` | Ensure any new CLI flag is backtest-only; domain purity auto-covered by glob. |

**Explicit non-goals (this change):**

- `ExecuteRun`, `alpaca_broker`, `OrderIntentEvent`, paper brackets, native Alpaca trailing-stop orders.
- Changing interim **initial stop** (1×ATR14) or risk % (1%) — those belong to change C / later SPEC alignment to 2×ATR(20).
- Full research grid (5/20-day low, EMA, 10/30-day time stops) beyond the mandated **10-day-low primary + 3-ATR variant + time stop**.
- Regime filter, vol sizing, Phase D gate runs.

## Approaches

1. **Pure domain exit policy + inject into `BacktestRun` (recommended)**
   - New pure module owns: level update (never loosen), exit signal evaluation, time-stop, priority, fill price.
   - `BacktestRun` supplies bars/history/position state and records `SimulatedTrade`.
   - Paper sizing/`OrderIntent.take_profit` unchanged.
   - Pros: domain purity, strict TDD, reproducible, clean seam for 10-day-low vs 3-ATR grid, no paper blast radius.
   - Cons: application wiring + state on `_OpenPosition`; must carefully define close-signal vs fill-day split.
   - Effort: Medium.

2. **Inline trailing logic only inside `BacktestRun._exit_for_bar`**
   - Pros: fewer files.
   - Cons: hard to unit-test pure rules; mixes portfolio loop with policy; grid variants become conditionals; `_simulate_trade` drift risk grows.
   - Effort: Medium short-term, High long-term.

3. **Remove `take_profit` from `OrderIntent` / sizing now**
   - Pros: forces model purity end-to-end.
   - Cons: breaks paper contracts, event IDs, broker adapter tests — out of scope and violates “backtest-only / decide at D”.
   - Effort: High, wrong boundary.

## Recommendation

**Approach 1.** Implement a pure, clock-free exit engine and wire it only into the backtest harness.

### Smallest safe first slice

| Slice | Deliverable | Why first |
|---|---|---|
| **1 (first PR)** | `trailing_low` + pure exit-policy functions for **10-day-low never-loosen channel** + unit tests; expand `ExitReason`; wire `BacktestRun` so Core/default backtest exits via channel (no fixed TP); rewrite take-profit application tests. | Replaces the interim TP with the primary research exit; smallest end-to-end behavioral change. |
| **2** | Time stop (20 sessions, +0.5R / new 20-day high progress gates) + integration tests. | Depends on session/R state from slice 1 position model. |
| **3** | **3-ATR trailing** policy variant + backtest-only CLI/config grid seam (default = 10-day-low). | Feeds conflict #1 data for D; keep as separate policy object, not if/else soup. |

Delivery strategy is **force-chained** (session preflight). Do not land all three in one PR if authored churn exceeds budget.

### Domain / application seams

```
domain/exit_policy.py  (pure)
  evaluate_exit(position_state, bar, history, config) -> ExitDecision | None
  update_trailing_level(state, history, config) -> state   # never-loosen

application/backtest_run.py
  open position holds: entry_date, entry_price, qty, initial_stop,
                       trailing_level, sessions_held, high_water / progress flags
  day loop:
    unsafe forced closes (unchanged)
    update trailing levels from completed history (no look-ahead)
    evaluate exits (priority: protective stop / trail / time-stop)
    settle cash
    entries (unchanged sizing for qty/stop; ignore take_profit for exits)
```

### Exit semantics to pin in proposal/design (not re-litigate product scope)

These are the main correctness forks; propose defaults aligned with SPEC §2.7 / research:

1. **10-day-low signal**: on session *t*, if `close_t < prior_10_day_low` (prior window = lows of the previous 10 sessions, excluding *t*), mark exit; **fill next session open** (with existing exit slippage model). Missing next bar → fail-closed or `open-at-end` policy must be explicit.
2. **Never-loosen**: effective protective floor only ratchets up: `trailing_level = max(trailing_level, channel_or_atr_level)`; never decreases after entry. Initial stop remains a hard floor until trail surpasses it.
3. **3-ATR trail**: high-water-based level (entry-or-since-entry high − 3×ATR); prefer bar-touch/stop-style fill consistent with protective stop, **or** same next-open-after-close-break rule — design must pick one and test it; do not mix silently.
4. **Time stop**: count **sessions held** from entry date (trading bars present, not calendar days). After 20 sessions, exit if neither (a) mark ≥ entry + 0.5×R with R = entry − initial_stop, nor (b) close printed a new 20-day high during the hold. Fill rule: next open vs same-day close — pin in design.
5. **Priority** (deterministic): unsafe context forced-close > hard stop gap/touch > trailing exit > time stop > open-at-end. Same-bar ambiguity must remain worst-case / stop-favoring where applicable.
6. **Benchmark vs Core**: either (a) both strategies share the new exit engine (recommended for “same harness”), or (b) retain fixed-TP only behind an explicit legacy policy. Prefer one engine + policy config so D comparisons stay honest.

### Data requirements

- No new external feeds. Reuse daily OHLC already in fixtures / Sharadar / Alpaca range fetch.
- Unit tests need hand-built multi-week series (10+ bars post-entry for channel; 20+ for time stop; ATR history for trail).
- Existing short breakout fixtures that only exercise same-bar TP must be rewritten, not deleted without replacement.
- Fail-closed: missing bar for an open position already carries forward mark; exit-on-missing-next-session after a close-signal needs an explicit rule (prefer fail-closed or forced open-at-end with warning — decide in design).
- Reproducibility: exit policy id/parameters must appear in backtest report warnings or config fields so runs are git-SHA + policy traceable (ROADMAP §7).

### Strict-TDD test seams

| Seam | File | Assert |
|---|---|---|
| Indicator | `test_indicators.py` | `trailing_low` hand-computed max/min window, no look-ahead past slice end. |
| Never-loosen | `test_exit_policy.py` | Level rises with higher lows/highs; never falls when window softens. |
| Channel signal | `test_exit_policy.py` | Close below prior 10-day low signals; close equal does not; window excludes signal day. |
| Next-session fill | `test_backtest_run.py` | Signal day does not close trade; next open is exit price/date. |
| Time stop | `test_exit_policy.py` + integration | Fires at 20 sessions without progress; suppressed by +0.5R or new 20-day high. |
| 3-ATR variant | domain + integration | Trail level math; never-loosen; distinct `exit_reason`. |
| Contract | `test_backtest_metrics.py` | Updated `ExitReason` set. |
| Isolation | `test_boundaries.py` / existing execute tests | Paper path still requires take_profit; no execute CLI exit-policy flag. |
| Determinism | existing twin-run pattern | Same inputs → byte-identical trades/metrics. |

RED → GREEN per pure function before `BacktestRun` wiring. Do not “fix” exit policy only through multi-hundred-line integration fixtures.

### Compatibility / rollback

- **Rollback**: revert exit-policy module + `BacktestRun` wiring; restore fixed-TP tests. Paper path remains valid throughout.
- **Compat risk**: any consumer assuming `exit_reason == "take-profit"` (metrics enum test, hand-built trade fixtures) must update.
- **Do not** change `OrderIntent` event_id inputs (includes take_profit) in this change.
- Dead `_simulate_trade`: either delete in a tiny cleanup within a slice or leave unused — do **not** dual-implement trailing there.

### Changed-line forecast (authored)

| Slice | Est. authored +/- | Budget vs 800 session / 400 default |
|---|---|---|
| 1 Domain engine + 10-day-low wire + test rewrites | **350–500** | Near/over default 400; under 800 if tightly scoped |
| 2 Time stop | **150–250** | Low–Medium |
| 3 3-ATR + CLI/grid seam | **150–300** | Low–Medium |
| **Total change B** | **650–1000** | **Chained PRs required** |

```
Decision needed before apply: No (force-chained already selected)
Chained PRs recommended: Yes
400-line budget risk: High (total); Medium per slice if split as above
800-line session budget risk: Medium-High if slice 1 is not ruthlessly scoped
```

Generated goldens (if any long fixture JSON) excluded from authored risk count per SDD review guard; prefer synthetic short unit series over large goldens.

## Risks

- **Close-signal vs bar-touch ambiguity** if design copies current TP touch model for the 10-day-low exit — would mis-implement SPEC §2.7.
- **Look-ahead** if “prior 10-day low” accidentally includes the signal bar or future bars.
- **Session counting** with missing bars / holidays — must use observed trading sessions in the series, not calendar days.
- **Paper/backtest divergence** is intentional now; document loudly so D does not “discover” it late.
- **`_simulate_trade` divergence** if someone extends the dead path.
- **Test churn** in `test_backtest_run.py` (take-profit / stop+TP tie cases) — expected, not optional.
- **Scope creep** into initial-stop ATR(20), risk 0.35%, cooldowns, or Alpaca trailing orders — reject; belongs to C/D/paper later.

## Ready for Proposal

**Yes.** Scope, seams, first slice, data needs, TDD surfaces, rollback, and line forecast are clear enough for `sdd-propose`.

Tell the user:

1. Proceed to proposal for `trailing-exit-engine` with Approach 1 and three force-chained slices.
2. Explicitly keep paper/Alpaca out of scope.
3. Pin exit fill/priority semantics in design before apply.
4. Slice 1 is the only safe first implementation cut: pure policy + 10-day-low never-loosen in backtest, no fixed TP.
