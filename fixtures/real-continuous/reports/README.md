# Backtest reports — fixtures/real-continuous

Fixture: continuous 2019-01-02 → 2025-12-31 pull (market-context-v2, generation_span
2019-01-02..2025-12-31, 6477 symbols; bars.json 1.3GB). Pulled 2026-07-18 on main @ 0eeb903.

## backtest-baseline.json

Produced 2026-07-18, code main @ 0eeb903 (via worktree src):

```
invest-backtest \
  --universe fixtures/real-continuous/bars/universe.json \
  --bars fixtures/real-continuous/bars/bars.json \
  --market-context fixtures/real-continuous/market-context.json \
  --strategy core --split-date 2023-01-03
```

Defaults: slippage 5bps, tax 0.15, exit ten-day-low, equity 100k.

Headline: net_pnl −7,743 (−7.74%), 125 trades, hit 20%, maxDD(equity) 37,965.
Gate-dominated: 11,721 of 12,030 skips = max-equity-deployed (25% × 100k cap →
~1-2 concurrent positions). Same 125 trades at zero cost: +9,597 (PF 1.10);
gross edge t-stat 0.34 — not significant; top trade (ARRY1 +13.5k) exceeds total.

## backtest-uncapped.json

Signal-edge experiment (scratchpad/uncap_backtest.py, same code + fixture):
equity 1e9, RISK_PER_TRADE patched 1e-6 (risk capital stays 1,000/trade,
sizing comparable to baseline), MAX_CONCURRENT_POSITIONS effectively off →
capital gates never bind, every context-safe signal trades. Measures raw
cross-sectional edge with large n. Same costs (5bps + 0.15 tax), same split.

Result (2026-07-18): 4,683 trades; RAW directional pnl −106,030 (mean −22.6,
sd 2,975, t = −0.52, PF 0.972); net after costs −840,828. IS exp −281.57
(n=2443), OOS exp −68.28 (n=2240) — both negative. Verdict: the signal as
configured has no demonstrable edge; the baseline's +9.6k gross was sampling
noise from the capital gate. 73% of trades die at the 1×ATR hard stop
(3,413 stops, −3.59M) vs 711 trailing-channel winners (+2.36M) and 528
corporate-action forced-closes (+1.03M).

Decomposition (2026-07-19): OOS raw +248,299 (PF 1.135, t 1.53) is entirely
forced-close carried — ex-FC OOS is −362,377 (PF 0.795, t −2.61).

## fc-audit.json (research plan Step 1)

Driver: research_steps12.py Phase A/B (2026-07-19, same code + fixture).
528 forced closes = 405 corporate-action (+1,023,274) + 123 symbol-ineligible
(+3,068). Only 4 terminal (coverage ends ≤7d after exit; delist/acquisition
proxy) — 524 transient. Valuation is already conservative: as-run same-day
low +1.026M vs same-day open +1.35M vs prior close +1.33M. Conclusion: FC
profit is a policy artifact — kind-blind corporate-action blockers (splits/
dividends that follow run-ups) act as accidental take-profit near local
highs — not a pricing artifact.

## event-study.json (research plan Step 2)

Driver: research_steps12.py Phase C. n = 12,295 position-blind accepted
signals (scan_decisions; no already-submitted suppression). Forward returns
from next-session open, date-clustered t:

| Horizon | Mean | t | Hit >0 |
| --- | ---: | ---: | ---: |
| +1d | −0.08% | −1.01 | 48.8% |
| +5d | −0.04% | −0.31 | 50.9% |
| +10d | +0.43% | +2.44 | 52.3% |
| +20d | +0.98% | +3.31 | 53.6% |
| +60d | +3.49% | +7.49 | 52.0% |
| +120d | +7.11% | +13.6 | 56.5% (survivorship caveat: full-window only) |

By year (h20): 2021 −1.76% (t −1.77), 2022 −2.54% (t −2.62); all other
years positive (2024 +3.22%, t 5.42) → regime gate indicated. Excess vs
same-date eligible-universe mean (h20): +0.36%, t 1.78, median negative —
cross-sectional alpha thin; much of the drift is beta. MFE/MAE over 20
sessions: +10.6% / −9.3% (means). Race to ±1×ATR(14) within 60 sessions:
down-first 6,208 vs up-first 5,848 — P(+1R first | resolved) = 48.5%.

Verdict: the plan's decision rule fires — drift positive (20–120 sessions),
short-horizon drift zero/negative, path hits −1 ATR before +1 ATR on a coin
flip → the 1×ATR stop, not the entry, destroys the edge. Proceed to Step 3
(structural stop min(breakout-day low, entry − 2×ATR(20)), cooldown, ranked
fill, §2.5 control) and Step 4 (200-DMA regime gate); benchmark hurdle stays
open (excess-vs-universe only marginally significant).
