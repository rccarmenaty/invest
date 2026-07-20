# First Backtest Failure — Post-Mortem & Research Plan

**Date:** 2026-07-18
**Inputs:** `fixtures/real-continuous/reports/backtest-baseline.json`, `backtest-uncapped.json`, `reports/README.md`
**Fixture:** continuous 2019-01-02 → 2025-12-31, market-context-v2, 6,477 symbols, split 2023-01-03
**Code under test:** main @ 0eeb903, `--strategy core`, defaults (slippage 5bps/side, tax 0.15, exit ten-day-low, equity 100k)
**Status:** research plan — no strategy code changed by this document

---

## 1. What the reports actually prove

### 1.1 The capped baseline is a measurement artifact, not a strategy result

- 11,721 of 12,030 skips are `max-equity-deployed` — the 25%-of-equity cap on a 100k
  account admits ~1 position at a time, so only ~2.7% of signals ever traded.
- The harness picks *which* signals fill **alphabetically by symbol**
  (`application/backtest_run.py`: `sorted(pending[current_date], key=lambda item: item.symbol)`),
  not by momentum rank / 52-week-high proximity / liquidity as SPEC §2.4 mandates.
- Consequence: the headline −7.7% net, and even the +9.6k gross-at-zero-cost
  (PF 1.10, t = 0.34), are noise from an arbitrary subsample. The top trade (ARRY1 +13.5k)
  exceeds total gross — concentration, not edge. **Discard this run as evidence either way.**

### 1.2 The uncapped run is the honest measurement

`uncap_backtest.py`: equity 1e9, RISK_PER_TRADE patched so risk capital stays 1,000/trade
(sizing comparable to baseline), portfolio gates effectively off → every context-safe
signal trades. n = 4,683.

| Finding | Number | Interpretation |
|---|---|---|
| Raw directional P&L | −106,030 (mean −22.6, sd 2,975, t = −0.52, PF 0.972) | No cross-sectional edge — but measured *through* a broken exit |
| IS / OOS expectancy | −281.57 (n=2,443) / −68.28 (n=2,240) | Both negative → not overfitting; the configuration simply loses |
| Hard-stop exits | 3,413 trades (73%), −3.59M | **The dominant leak** |
| Stop exit age | median 3 calendar days; **28.1% die on entry day**, 47% within 1 day | The stop sits inside normal daily noise |
| Winners | 711 trailing-channel +2.36M; avg win +12.2% vs avg loss −3.3% | Expectancy ≈ −0.05%/trade *before* costs |
| Right tail | 350 trades (7.5%) > +10% carry **all** gross profit (sum +9,775% vs −63% total) | Classic trend profile — the tail pays, the churn bleeds |
| Regime (gross by entry year) | 2022: −235k @ 16.4% hit; 2021: −151k; 2025: −111k; 2019: −74k; vs 2020/2023/2024 positive | No market-regime filter |
| Costs | −106k raw → −841k net (~−157/trade) | 15% tax haircut on gross gains (no loss netting) + 10bps round trip punishes churn |

Artifacts, not signal: 528 corporate-action forced closes (+1.03M) and 31 open-at-end
(+92k) are harness mechanics.

---

## 2. Root causes — mostly known spec gaps

The measured system is **not** the SPEC Core model. Failures map to documented gaps:

1. **Initial stop: 1×ATR(14)** (`domain/sizing.py`, explicitly flagged in SPEC §2.7 as the
   *interim benchmark-era* value, "superseded by the trailing model"). SPEC §2.7 target:
   **min(breakout-day low, entry − 2×ATR(20))**. A 1-ATR stop on a ~3%-daily-range momentum
   stock is a coin flip against noise — 28.1% of stops trigger intraday on the entry day
   itself; the 10-day-low trail never gets a chance to ratchet because trades die within
   ~72 hours.
2. **No market-regime filter.** SPEC §2.3: "benchmark close above its 200-day SMA, else no
   new entries." `MomentumSelectionScanner` has no such layer → the system bought breakouts
   straight through the 2022 bear market (−235k gross, 16.4% hit).
3. **No 10-session re-entry cooldown** (SPEC §2.7) → stopped names re-signal and churn;
   7,457 `already-submitted` skips in the uncapped run show how clustered re-signals are.
4. **Alphabetical instead of ranked candidate selection** (violates SPEC §2.4: rank by
   momentum rank, high proximity, liquidity).
5. **Risk 1% flat** instead of SPEC §2.8's 0.35% baseline with volatility scaling and
   ~4% aggregate open-risk cap. Flat 1% also makes position notional explode in high-ATR
   names, which is what starved the capped baseline (25% deployment cap → 1 position).
6. **The SPEC §2.5 control comparison never ran.** The Core model was never required to
   beat the plain spike-detector benchmark under identical replay assumptions, so the
   §2.9 acceptance gates are formally unmet.

---

## 3. Evidence base (external research)

| Claim | Source | Implication for this system |
|---|---|---|
| Scaling momentum exposure by realized vol roughly doubles Sharpe and nearly eliminates crashes | Barroso & Santa-Clara, *Momentum Has Its Moments*, JFE 2015 | Volatility scaling is core, not optional (§2.8) |
| Momentum crashes are predictable and concentrate in panic/rebound states | Daniel & Moskowitz, *Momentum Crashes*, JFE 2016 | The 2022 bleed is textbook; regime gating addresses it |
| Time-series trend filters (asset above its long-run MA) remove most left-tail exposure | Moskowitz, Ooi & Pedersen 2012; Faber, *A Quantitative Approach to Tactical Asset Allocation*, 2007 | §2.3's benchmark-200-DMA gate is the right, evidence-backed layer |
| Trend systems run ~35-45% hit rates with positive skew; the right tail pays | Hurst, Ooi & Pedersen, *A Century of Evidence on Trend-Following*, 2017 | Our 21% hit is below the viable band — indicts the stop, not necessarily the selection |
| Stop-loss overlays help momentum when wide/state-aware; stops inside the noise band convert drift into churn | Han, Zhou & Zhu, *Taming Momentum Crashes: A Simple Stop-Loss Strategy*; Kaminski & Lo, *When Do Stop-Loss Rules Stop Losses?* | Widen invalidation to 2×ATR(20) / structural; keep sizing risk-based |
| ~50-60% of breakouts throw back to the breakout level (practitioner statistics) | Bulkowski, Encyclopedia of Chart Patterns | Supports testing §2.6 follow-through confirmation — as a *separate* experiment, never bundled |
| Individual-stock momentum profitability has decayed post-publication (roughly halved post-2000s samples) | Recent long-sample momentum studies | Expect a thin edge; turnover and cost control decide whether it survives |

---

## 4. Research plan (ordered — each step is one experiment, judged by SPEC §2.9 gates)

### Phase 0 — Fix measurement first (no strategy change)

1. **Rank gated signals** by momentum rank → 52-week-high proximity → liquidity (fix §2.4;
   delete alphabetical ordering).
2. **Run the §2.5 control**: same fixture, `MomentumScanner` spike detector, identical
   costs. The Core model must beat it or the added layers are noise.
3. **Entry-edge isolation study**: for every accepted signal, log close→+5/+10/+21-day
   forward returns vs (a) universe mean, (b) top-momentum names *without* a breakout.
   This separates "entry has no edge" from "exit destroys edge" — the uncapped run
   conflates them, and no exit redesign should start before this is answered.

### Phase 1 — Repair exit mechanics (expect the largest delta)

1. **Initial stop** = min(breakout-day low, entry − 2×ATR(20)); qty sized from actual stop
   distance at **0.35% risk** (§2.8). Grid: 1.5/2/2.5/3 ATR and structural; also
   close-basis vs intraday trigger (28.1% entry-day deaths are wick-outs).
2. **10-session re-entry cooldown** per symbol (§2.7).
3. **Trail comparison**: `ten-day-low` vs the already-built `atr-3-high-water` vs 20-day
   channel; require neighboring-parameter robustness (§2.9: a result living in one grid
   cell is data mining).

### Phase 2 — Regime & volatility management (the evidence-backed core)

1. **Benchmark 200-DMA gate** on new entries (test none / 100 / 200 / dual-average per
   §2.3). From the year table, this alone removes most of 2021-2022's −386k gross.
2. **Volatility scaling**: per-trade risk ∝ target/realized 20-day vol; sleeve-level
   exposure scaled by momentum-vol (Barroso-Santa-Clara).

### Phase 3 — Selectivity (only if Phases 1-2 produce positive expectancy)

1. Apply the existing liquidity screen ($10 price / $10M ADV — already implemented in the
   context generator) to the backtest universe; stress slippage at 10/25bps.
2. One at a time: breakout buffer (close > 20-day high + 0.25-0.5×ATR), relative volume
    as ranking context (§2.3 — never a hard veto), the §2.6 follow-through confirmation
    (house hypothesis, tested standalone), 10/40/55-day breakout variants.

### Phase 4 — Portfolio construction

1. 6-10 concurrent positions at 0.35% risk, ~4% aggregate open-risk cap, sector caps
    (§2.8). This also fixes the capped-run starvation mechanically.

---

## 5. What *not* to do

- Don't add entry filters to fix a stop problem — 73% of trades never lived long enough
  to express the entry thesis.
- Don't optimize hit rate; optimize expectancy and payoff (§2.9).
- Don't re-tune on the same 2019-2025 window — add walk-forward splits; the single 2023
  split already shows IS and OOS both broken, so this is a design failure, not an
  overfit failure.
- Don't trust the capped baseline in either direction until candidate ranking is fixed.

---

## 6. Bottom line

The reports do not yet prove the strategy has no edge. They prove that the *interim exit*
(1×ATR stop) and the *missing regime filter* guarantee failure, and that costs finish the
job. Most of the fix path is already written in SPEC (§2.3, §2.4, §2.7, §2.8) and is
independently backed by the momentum-crash / volatility-management / trend-following
literature. Run Phases 0-2 as three separate experiments against the §2.5 control, and
let the §2.9 acceptance gates — not hope — decide whether the Core model ships.

**Acceptance gates (SPEC §2.9), restated as the go/no-go for every phase:**
positive expectancy after costs in aggregate *and* across subperiods; beats the §2.5
control; neighboring parameters behave similarly; no single stock/sector/year/regime
accounts for most profits; pre-tax and conservative post-tax results both reported.

---

## Appendix A — Baseline report headline numbers (for reference)

- net_pnl −7,743 (−7.74%), 125 trades, hit 20%, expectancy −61.9, maxDD(equity) 37,965
  (peak 118,724 → trough 80,759), 1,760 trading days.
- Gates: max-equity-deployed 11,721; already-submitted 234; kill-switch 60; sizing-invalid 15.
- Segments: IS −7,063 (82 trades, hit 19.5%); OOS −680 (43 trades, hit 20.9%).
- Exit mix (baseline): stop 89, trailing-channel 24, forced-close 11, open-at-end 1.

## Appendix B — Uncapped experiment configuration

- `fixtures/real-continuous/reports/uncap_backtest.py`: equity 1e9, RISK_PER_TRADE → 1e-6
  (risk capital stays 1,000/trade), MAX_CONCURRENT_POSITIONS → 1e9; same scanner
  (`MomentumSelectionScanner`), same exit (`ten-day-low`, channel 10, time-stop 20,
  half-R 0.5), same costs (5bps + 0.15 tax), same split (2023-01-03).
- Gates remaining: already-submitted 7,457; sizing-invalid 15.
