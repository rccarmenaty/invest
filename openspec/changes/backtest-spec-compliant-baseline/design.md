# Design: Backtest Spec-Compliant Baseline (Step 3 Measurement Fixes)

## Technical Approach

Four narrowly-scoped edits across two domain modules and one application module, plus a
verification-only item. All logic stays inside `replay()` and `sizing.py`/`indicators.py`;
`ScanDecision`, both scanners, and `scan_decisions()` are untouched (proposal decision 2).
Domain stays SDK/clock-free — cooldown uses replay session indices, not wall time.

## Architecture Decisions

### Decision: `compute_intent()` gains explicit entry + breakout-low, structural stop
**Choice**: Signature `compute_intent(symbol, decision_date, equity, history, entry_price, breakout_low)`.
Stop = `min(quantize(breakout_low), entry - 2×ATR(20))`; qty from that actual stop distance.
Callers supply the entry basis: backtest passes the fill-day open (decision 1, no look-ahead —
stop applies only after fill); live/paper passes its pre-submission reference close (decision 4;
fill-time recompute for live is documented future work).
**Alternatives**: keep internal `last_close→entry` derivation (rejected — hides the gap the change
fixes); add a new function (rejected — two call sites, shared math, one signature is simpler).
**Rationale**: entry/breakout-low are the only per-fill inputs; ATR and risk stay module constants.
Gap-down (fill opens below breakout low → `breakout_low ≥ entry`): `min()` then selects the
ATR leg (`entry − 2×ATR`, always `< entry` for `ATR>0`), so `stop_distance>0` holds and
`SIZING_INVALID` stays reserved for degenerate ATR / `qty<=0`. All-`Decimal`, existing `quantize_price`.

### Decision: Ranked fill computed locally from `by_symbol` history (Approach 1)
**Choice**: Replace alphabetical sort at `backtest_run.py:194` with a point-in-time rank key:
`(−momentum_return(252,21), −proximity, −median_dollar_volume(20), symbol)`. Windows mirror
`MomentumSelectionScanner` (`MOMENTUM_FAR=252/NEAR=21`, `PROXIMITY=252`) and `liquidity_screen`
(`dollar_volume_window=20`, median of `close×volume`). Symbol ascending is the deterministic
final tie-break, matching the scanner's `item[0]`.
**Alternatives**: extend `ScanDecision` with rank fields (rejected — shared-contract blast radius).
**Rationale**: SPEC §2.4 orders simultaneous signals by momentum → high-proximity → liquidity;
reusing the pure reducers duplicates cheap math but keeps zero contract change. Duplication is
test-pinned.

### Decision: ATR period via optional param, default 14
**Choice**: `average_true_range(history, period: int = ATR_DAYS)`; sizing passes `period=20`.
**Rationale**: `scanner.py:45` and `exit_policy.py:128` call with no period → default 14 preserved,
keeping the byte-identical benchmark scenario intact (proposal decision 3).

### Decision: Cooldown as replay session-index state, skip reason as replay-local constant
**Choice**: `cooldown_release: dict[str, int]` in `replay()`. Enumerate `sorted(bars_by_date)` to a
`session_index`. Snapshot `day_start = len(trades)` at the top of each day; after the day settles,
for each `trades[day_start:]` with `exit_reason != "open-at-end"` set
`cooldown_release[symbol] = session_index + COOLDOWN_SESSIONS + 1`. Skip reason `"cooldown-active"`
is a `backtest_run.py` constant, NOT a `GateReason` (cooldown is a replay concern, absent from the
live sizing/`evaluate_gates` chain).
**Alternatives**: instrument every exit path (forced/exit/same-day) individually (rejected —
scattered, error-prone); add `GateReason.COOLDOWN_ACTIVE` (rejected — leaks replay concept into
shared domain sizing). Deriving from the day's new trades captures ALL close paths
(`_process_unsafe_positions`, `_process_exits`, same-day post-entry close) in one place.
**Rationale**: SPEC §state-machine `CLOSED→COOLDOWN→NONE`, "10 sessions per symbol after close" —
after ANY close (proposal item 3). Session count, not calendar. Boundary: release at
`i+COOLDOWN_SESSIONS+1` blocks sessions `i+1..i+10` inclusive; the exact boundary is test-pinned.

## Data Flow

    signal day (breakout)            fill day (next session)
    symbol_bars[si]  ──low──┐        entry_bar.open ──┐
    symbol_bars[:si] ─ATR20─┼─► compute_intent ◄──────┘
    by_symbol history ─rank─┘        │ stop=min(low, entry−2·ATR20), qty=risk/dist
                                     ▼
    pending[date] ─rank-sort─► gate chain (cooldown ▸ already-submitted ▸ context ▸ gates)
                                     │ close (any path) ─► cooldown_release[symbol]=i+11

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/invest/domain/sizing.py` | Modify | `RISK_PER_TRADE=0.0035`, `STOP_ATR_MULTIPLIER=2`, `STOP_ATR_DAYS=20`; new `compute_intent` signature + structural `min()` stop |
| `src/invest/domain/indicators.py` | Modify | `average_true_range(history, period=ATR_DAYS)` |
| `src/invest/application/backtest_run.py` | Modify | Rank key replaces alphabetical sort; cooldown state + gate; new `compute_intent` call (fill-day open + breakout-day low) |
| `src/invest/application/execute_run.py:76` | Modify | Pass `bars[-1].close` (entry) + `bars[-1].low` (breakout low) to `compute_intent` |
| `openspec/specs/trading-system/spec.md` | Modify | Deltas at :414-430, :432-465, :741-763 |
| `tests/domain/test_sizing.py`, `test_indicators.py`, `tests/application/test_backtest_run.py:692` | Modify | Rewrite behavior-pinned tests |

## Interfaces / Contracts

```python
# sizing.py
def compute_intent(symbol, decision_date, equity, history, entry_price, breakout_low)
        -> tuple[OrderIntent | None, GateReason | None]:
    atr  = average_true_range(history, period=STOP_ATR_DAYS)          # 20
    entry = quantize_price(entry_price)
    stop  = quantize_price(min(quantize_price(breakout_low), entry - STOP_ATR_MULTIPLIER * atr))
    take_profit = quantize_price(entry + TAKE_PROFIT_ATR_MULTIPLIER * atr)   # SAME period-20 atr as stop
    if entry - stop <= 0 or int((equity*RISK_PER_TRADE)//(entry-stop)) <= 0:
        return None, GateReason.SIZING_INVALID
    ...
    # take_profit is independent of which stop candidate wins; paper bracket
    # live-consumes it (alpaca_broker.py:100 → take_profit.limit_price), backtest ignores it.

# backtest_run.py — fill site (~line 215)
intent, sizing_reason = compute_intent(
    decision.symbol, decision.decision_date, marked_equity,
    symbol_bars[:signal_index], entry_bar.open, symbol_bars[signal_index].low)

# backtest_run.py — rank key replacing sorted(..., key=item.symbol)
def _fill_rank_key(decision):
    sb = by_symbol[decision.symbol]; si = _signal_index(sb, decision); w = sb[:si+1]
    if len(w) > RANK_MOMENTUM_FAR:                # benchmark short-history fallback → sort last
        mom  = momentum_return(w, far=252, near=21)
        prox = w[-1].close / trailing_high(w[:-1], 252)
    else: mom = prox = Decimal(0)
    liq = median(b.close * b.volume for b in w[-RANK_LIQUIDITY_WINDOW:])
    return (-mom, -prox, -liq, decision.symbol)

# cooldown gate — pending loop, after the already-submitted check
if session_index < cooldown_release.get(decision.symbol, -1):
    gate_counts[COOLDOWN_SKIP_REASON] += 1
    skipped_entries.append(SkippedEntry(decision.symbol, decision.decision_date,
                                        current_date, COOLDOWN_SKIP_REASON)); continue
```

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit `test_indicators.py` | `average_true_range` default-14 unchanged; `period=20` path | Fixed bars; assert both windows |
| Unit `test_sizing.py` | 0.35% risk; structural stop = `min(breakout_low, entry−2·ATR20)`; ATR-leg wins vs low-leg wins; gap-down stays valid; `SIZING_INVALID` on degenerate ATR/qty | New signature fixtures pinning stop & qty |
| Unit `test_sizing.py` (TP) | Take-profit = `entry + 2×ATR(20)`, using the SAME period-20 ATR as the stop path, independent of which stop candidate (breakout-low vs ATR-leg) wins | Assert `intent.take_profit` for both stop-winner cases |
| Integration `test_backtest_run.py:692` | Rewrite: give BRAVO higher 21/252-day momentum so it fills first and ALPHA hits `max-equity-deployed`; assert `trades==["BRAVO"]` (ranking beats name) | Two breakout symbols, differing momentum shape |
| Integration (new) | Cooldown: close a position, re-signal within 10 sessions → skip `cooldown-active`; re-entry allowed at session 11 | Scheduled-signal scanner; assert `gates.counts` + `skipped_entries.reason` |
| Integration | Benchmark scenario byte-identical (ATR-14 callers) | Existing spec scenario asserted |

Deterministic fixtures express ranking by holding breakout geometry constant while varying the
252→21-day momentum path, so the rank order is unambiguous; a symbol-name tie-break case is pinned
separately.

## Benchmark-Strategy Interaction

`compute_intent` is strategy-agnostic, so benchmark-strategy trades resize under the new constants
too — intended: the corrected spec delta states sizing, cooldown, and ranked-fill apply to BOTH
strategies. The "byte-identical benchmark" guarantee is now scoped to default-vs-explicit
same-code equivalence only (ATR default-14 path), NOT preservation of old sizing or fill order.
The rank-key short-history fallback (`mom=prox=Decimal(0)` for benchmark's ~21-bar candidates)
means benchmark same-day fill order becomes liquidity-then-symbol, not pure alphabetical — this is
acceptable under the corrected spec; tests MUST NOT pin alphabetical fill order for the benchmark
strategy.

## Slippage Post-Step (unchanged)

The existing post-step at `backtest_run.py:222-224` replaces `intent.entry` with the
slippage-adjusted fill `entry_fill(entry_bar.open, slippage_bps)` AFTER `compute_intent`, WITHOUT
recomputing stop/qty. Preserve this unchanged: sizing uses the raw fill-day open and slippage
applies afterward (current semantics, ~5bps noise, out of scope to change).

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or
process-integration boundary. Pure Decimal domain math.

## Migration / Rollout

No migration. `BacktestResult`/`GateTelemetry` schema unchanged — `"cooldown-active"` surfaces
automatically through the existing `gates.counts` map and `skipped_entries`; `cli.py:341` renders
it with no code change. Single-branch revert (proposal rollback plan).

## Open Questions

- [ ] Cooldown boundary exact session count (block `i+1..i+10` vs `i+1..i+9`) — pinned by test; design assumes inclusive 10-session block.
- [ ] Liquidity reducer reuses `liquidity_screen`'s median(20) — confirm SPEC §2.4 intends median (not mean) dollar volume; adjust window/statistic if the spec delta says otherwise.
