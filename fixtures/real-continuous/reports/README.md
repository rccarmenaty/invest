# Backtest reports — fixtures/real-continuous

Fixture: continuous 2019-01-02 → 2025-12-31 pull (market-context-v2, generation_span
2019-01-02..2025-12-31, 6477 symbols; bars.json 1.3GB). Pulled 2026-07-18 on main @ 0eeb903.

## EVENTS-22 F0 sealed feasibility driver

`research_events22_f0.py` consumes a strict JSON manifest containing only
EVENTS rows, point-in-time listing and eligibility facts, session dates,
integrity evidence, input hashes, and an optional pre-existing power basis. It
emits a deterministic self-hashed F0 artifact. The manifest rejects unknown
fields; reaction values and forward returns are outside this implementation.

```sh
uv run python fixtures/real-continuous/reports/research_events22_f0.py \
  --input /path/to/events22-f0-input.json \
  --out fixtures/real-continuous/reports/events22-f0.json
```

D+2/h60 is recorded as the future primary design and D+1/h60 as the future
secondary design. Neither is measured in F0. Even `f0_pass` stops at human E1
approval and always records `capital_go=false`.

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

## gate1a-excess.json (Gate 1a — h60 excess kill test)

Driver: `research_gate1a.py`. Same position-blind Core accepted-signal cohort as
Step 2, but measures **excess vs same-date eligible-universe mean** at h20
(regression check), **h60 (primary gate)**, and h120 (survivorship-flagged).
Also splits by entry year, FC-symbol cohort, and frozen ID / 52w-proximity
quintiles.

**Gate 1a (predeclared):** h60 excess mean > 0 and date-clustered t ≥ 2.5 →
PASS; else FAIL (kills Quiet Drift / pure long-hold-as-alpha claims).

**Result (2026-07-20):** **PASS** — h60 excess mean **+1.89%**, clustered **t=5.30**,
n=11,489. h20 regression matches Step 2 (+0.36%, t=1.78). h120 excess +2.26%
(t=4.98; full-window only). Medians remain slightly negative (right-tail driven).
Year split: 2021 −6.74% (t−5.85); 2023–2025 strongly positive. ID q1−q5 mean
spread only +0.55pp (smooth_better, weak) — Gate 1b not declared passed.

```
uv run python fixtures/real-continuous/reports/research_gate1a.py
```

Sequential only on 16GB hosts. Runtime dominated by `scan_decisions` + universe
baselines. Output: `gate1a-excess.json`. Pure helpers live in
`src/invest/application/event_study_excess.py` (unit-tested).

## Step 3 spec-compliant runs (2026-07-19)

Produced 2026-07-19 on main @ 74d6ac7 + uncommitted WIP streaming loader (see
incident note below). Three runs, sequential (the 2026-07-19 ~12:19 parallel
launch exhausted the 16GB machine and left zero-byte reports).

    # §2.5 spike-detector control (naïve MomentumScanner, identical replay)
    invest-backtest --universe .../bars/universe.json --bars .../bars/bars.json \
      --market-context .../market-context.json --strategy benchmark --split-date 2023-01-03
    # core spec-compliant
    invest-backtest ... --strategy core --split-date 2023-01-03
    # uncapped spec-compliant
    python fixtures/real-continuous/reports/uncap_backtest.py  # risk capital 1,000/trade

| Run | Scanner | Trades | Net P&L | Hit | Exp/trade | IS exp | OOS exp |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline (interim, pre-PR#57) | core | 125 | −7,743 | 20.0% | −61.9 | −86.1 | −15.8 |
| **benchmark-control** (§2.5) | naïve | 396 | −7,099 | 38.1% | −17.9 | −48.7 | **+30.0** |
| core-speccompliant | core | 502 | −29,198 | 28.9% | −58.2 | −85.7 | −17.9 |
| uncapped (interim) | core | 4,683 | −840,828 | 20.9% | −179.5 | −281.6 | −68.3 |
| uncapped-speccompliant | core | 3,451 | −313,323 | 32.8% | −90.8 | −129.0 | −49.9 |

Note: core-speccompliant dollar P&L is NOT comparable to the interim baseline —
PR #57 dropped risk from 1% to 0.35%, so ~2.85x less capital per trade. Compare
per-trade expectancy and trade count, not net P&L.

### Findings

1. **Spec-compliant changes improved the signal-edge measurement.** Uncapped
   hit rate 20.9%→32.8%, per-trade expectancy −179.5→−90.8, OOS −68.3→−49.9.
   The structural stop + entry+2×ATR(20) TP + 10-session cooldown + ranked fill
   are materially better than the interim config. Still negative, but bleeding
   far less per trade.

2. **The §2.5 control beats the core strategy out-of-sample.** The naïve
   spike-detector scanner (MomentumScanner, `--strategy benchmark`) under
   identical replay assumptions: OOS expectancy **+30.0**, hit 38.1%, *positive*
   OOS. The core momentum-selection scanner: OOS −17.9. The core does NOT beat
   its control — fails the plan's §2.5 acceptance gate ("beats the §2.5
   control").

3. **The edge problem is the signal/ranking, not the exits.** Consistent with
   the Step 2 event study (drift positive but path hits −1R before +1R on a coin
   flip): the spec-compliant structural stop helped materially, but the
   momentum *selection* adds nothing over a naïve scanner OOS. Step 4's regime
   gate is conditional on the signal having drift; the control comparison points
   at the ranking as the missing-value locus.

### Incident note (2026-07-19 ~12:19)

The first attempt launched all three runs in parallel against bars.json (1.3GB,
8.87M bars). The old `JsonFixtureReader` read the whole file + `json.loads`
(~9GB dict phase) + pydantic validate → ~10–12GB peak per process; three
concurrent ≈ 30GB on a 16GB machine → collapse, zero-byte reports. A WIP
streaming loader (`fixtures_json.py`, uncommitted at 74d6ac7+dirty) replaced
this with incremental JSON decode + a compact forward-only bitmap for duplicate
detection: smoke test 8,869,021 bars / 6,477 symbols in 59.3s, peak RSS
**4.87GB** (was ~10–12GB). Runs must stay sequential on this machine.

## phase2-structure.json (Phase 2 — fixed-horizon portfolio structure)

Driver: `research_phase2.py`. Composed Phase 2 config (#61):

- Scanner: §2.5 naïve (`MomentumScanner` / `--strategy benchmark`) — **not** Core/ID ranking
- Exit: fixed-horizon 60 sessions → next open; no price stop / no take-profit
- Admission: max concurrent 20, seeded random (`seed=42`)
- Costs primary: **pre-tax after 5 bps/side**; tax 0.15 secondary only

**Sequential only on 16GB hosts** — do not parallel with other multi-GB bar loads
(same discipline as Gate 1a / Step 3). Unit CI never runs this command.

```
uv run python fixtures/real-continuous/reports/research_phase2.py
```

Output: `phase2-structure.json` (+ `phase2-run.log`). Pure helpers:
`src/invest/application/phase2_report.py` (unit-tested).

### Go / no-go vs PRD #58 gates (2026-07-20)

| Gate | Result |
| --- | --- |
| After-cost exp > 0 on majority of WF folds (entry-year 2019–2025) | **PASS** — 6/7 folds (only 2022 negative) |
| FC-segregated (ex-forced-close) still majority-positive | **PASS** |
| No single calendar year > ~25% of total after-cost profit | **FAIL** — 2020 = **85.7%** of profit |
| Ranking not the accept path | **PASS** (seeded random admission only) |

**Verdict: NO-GO** — structure shows positive after-cost mean/median expectancy on
the full continuous sample, but profit concentration violates the year-share gate.
Do **not** promote ranking / Quiet Drift / Form-4 as a rescue of this structure
claim; publish the negative concentration result.

| Book | n | Mean exp | Median exp | Net P&L (pre-tax, 5 bps) |
| --- | ---: | ---: | ---: | ---: |
| Full | 200 | +56.12 | +18.76 | +11,223 |
| Non-FC | 96 | +204.09 | +184.40 | +19,593 |
| FC only | 104 | −80.47 | −24.16 | −8,369 |

Exit mix: fixed-horizon 91, context-position-forced-closed 104, open-at-end 5.

Note: continuous measurement requires market-context **forced closes** for unsafe
days (restored for Phase 2 / PRD #58 FC segregation). Without FC, long-hold
positions on delisted names fail-closed at replay end (R4) with no P&L claim.

## phase2-concentration-autopsy.json (Phase 2b — residual K2)

Driver: `research_phase2_autopsy.py`. **Post-process only** of
`phase2-structure.json` + SPY open sidecar (no multi-GB re-backtest).

Plan: `docs/research/phase2-concentration-autopsy-plan.md` · issue #64.

```
uv run python fixtures/real-continuous/reports/research_phase2_autopsy.py
```

Uses committed `spy-opens-sidecar.json` when complete; otherwise refreshes SPY
daily opens via Yahoo chart API. Pure helpers in `phase2_report.py` (unit-tested).

### K2 residual hope (2026-07-20)

| Leg | Result |
| --- | --- |
| Leave-2020 mean after-cost exp > 0 | **PASS** (~+9.44 on n=170) |
| Leave mean > ½ published full-book mean (~+28.06) | **FAIL** |
| Majority remaining folds mean > 0 | **PASS** (5/6) |
| S2 mean (trade − trade-window SPY) > 0 | **FAIL** (~−102) |

**residual_hope: die** — still promotion-blocked; pause-default. Do not auto-start
Form-4 / ranking / DAMB. Results: `docs/research/phase2-concentration-autopsy.md`.
