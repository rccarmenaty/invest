# Dual Absolute-Momentum Breakouts: Harvest Time-Series Drift, Kill Ranking Theater

## Thesis (1 paragraph)

The event study and §2.5 control jointly falsify Core as a *stock-picking* system: accepted signals show multi-month positive drift, but excess versus the same-date eligible universe is thin (h20 +0.36%, clustered t≈1.78), the path to ±1R is a coin flip, and multi-factor momentum ranking **loses** to the naïve spike detector out of sample. That pattern is not “tighten the ranker”; it is the classic signature that most of the measured drift is **time-series / beta continuation**, not cross-sectional skill. The next capital-research bet should therefore **pivot** from ranking theater to a dual absolute-momentum breakout: simple 52-week-high proximity + objective breakout trigger, **absolute** trend filters at stock *and* market level, **no fixed +2×ATR take-profit**, horizon-matched trailing exits (20–40 session channels; 60–120 session time stop), and **volatility-scaled gross exposure**. Literature (TSMOM, 52-week high, momentum crashes, risk-managed momentum, stop-loss theory, after-cost anomaly taxonomy) predicts this combination can convert long-horizon path-dependent drift into after-cost expectancy while Core’s CS ranking cannot invent alpha that Step 2 already measured as marginal.

## Mechanism (why edge should exist economically)

1. **Continuation is serial, not primarily relative.** Price paths with intermediate-term strength and proximity to highs exhibit positive expected multi-month returns because underreaction / limited attention and institutional trend-chasing create persistence in the *level* of risk appetite for winners (Moskowitz–Ooi–Pedersen time-series momentum; George–Hwang 52-week-high anchoring). When CS excess is thin, ranking winners against winners mostly reorders noise; participating in the common continuation when absolute trend is positive is the economic object.

2. **Horizon mismatch destroys measured edge.** Short-horizon returns ~0 and P(+1R first)≈48.5% imply that tight stops and short holding periods sample a near-zero-mean path noise process. Under random-walk-like short paths, stop-loss rules *subtract* expected return (Kaminski–Lo). Under intermediate-horizon momentum, wider path protection and longer holds can *add* value—but only if the entry is not already negative-expectancy after costs.

3. **Crash states are forecastable and expensive.** Momentum and breakout books bleed in panic / rebound windows (Daniel–Moskowitz). Years 2021–2022 were negative at h20 in *this* event study; absolute market filters and volatility scaling reduce exposure precisely when path risk and crash risk spike (Barroso–Santa-Clara; Daniel–Moskowitz dynamic momentum).

4. **Costs kill high-turnover micro-edges.** Novy-Marx–Velikov show most high-turnover anomalies die after costs; buy/hold hysteresis and lower re-entry frequency are the durable mitigations. Core’s many short-lived stop-outs are exactly the wrong cost profile for thin CS alpha. Longer holds + fewer re-entries + no forced “take profit at +2ATR” reduce turnover while letting the documented h20–h120 drift compound.

5. **Why ranking failed.** Goyal–Jegadeesh-type comparisons emphasize that TS and CS strategies differ mainly by net market exposure timing. Core forced a CS ranking problem onto a dataset whose residual CS alpha is weak; the §2.5 control’s better OOS expectancy is consistent with “simpler participation + different fill path,” not with “12-1 rank encodes skill.” Treating ranking as the research frontier is therefore the highest overfit risk.

## Literature anchors (3–8 citations with arXiv/DOI/URL + one-line relevance)

1. **Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012).** Time series momentum. *Journal of Financial Economics*, 104(2), 228–250. https://doi.org/10.1016/j.jfineco.2011.11.003 — Documents robust TSMOM across assets: past 12-month *own* return predicts future returns; motivates absolute-momentum participation over pure CS ranking when CS residual is thin.

2. **George, T. J., & Hwang, C.-Y. (2004).** The 52-week high and momentum investing. *Journal of Finance*, 59(5), 2145–2176. https://doi.org/10.1111/j.1540-6261.2004.00695.x — Nearness to the 52-week high dominates past-return ranking for forecasting; future returns do not reverse long-run like pure momentum — justifies **promoting 52w proximity to primary selection** and demoting multi-score rank.

3. **Daniel, K., & Moskowitz, T. J. (2016).** Momentum crashes. *Journal of Financial Economics*, 122(2), 221–247. (NBER w20439: https://doi.org/10.3386/w20439) — Crashes cluster after market declines with high volatility and rebounds; dynamic strategies that forecast mean/variance roughly double Sharpe — motivates market absolute filter + vol scaling, not static always-on Core.

4. **Barroso, P., & Santa-Clara, P. (2015).** Momentum has its moments. *Journal of Financial Economics*, 116(1), 111–120. https://doi.org/10.1016/j.jfineco.2014.11.010 — Momentum risk is highly variable and predictable; scaling exposure by recent realized variance nearly eliminates crashes and roughly doubles Sharpe — concrete blueprint for portfolio-level vol targeting on this stack.

5. **Kaminski, K. M., & Lo, A. W. (2014).** When do stop-loss rules stop losses? *Journal of Financial Markets*, 18, 234–254. https://doi.org/10.1016/j.finmar.2013.07.001 — Under random walk, 0/1 stops reduce expected return; under momentum they can add value — maps directly to event-study path coin-flip + long-horizon drift: **path-aware stops only when serial dependence is the object**.

6. **Novy-Marx, R., & Velikov, M. (2016).** A taxonomy of anomalies and their trading costs. *Review of Financial Studies*, 29(1), 104–147. https://doi.org/10.1093/rfs/hhv059 — After costs, high-turnover strategies die; buy/hold spreads / hysteresis are the best simple mitigation — requires lower re-entry rate and longer holds than current stop-churn Core.

7. **Goyal, A., & Jegadeesh, N. (2018).** Cross-sectional and time-series tests of return predictability: Considering the impact of model averaging. (SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2610288) — Fair TS vs CS comparisons show much of TS “outperformance” is time-varying net long exposure; when CS residual is thin, engineering more CS ranks is the wrong margin.

8. **Bailey, D. H., & López de Prado, M. (2014).** The deflated Sharpe ratio: Correcting for selection bias, backtest overfitting, and non-normality. *Journal of Portfolio Management*, 40(5), 94–107. (SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551) — Any multi-variant path must be judged with deflated Sharpe / multiple-testing discipline; forbids “winner of the grid” as acceptance.

*(Supporting industry synthesis, not primary edge claim: Hurst, Ooi & Pedersen, “A Century of Evidence on Trend-Following Investing,” *Financial Analysts Journal* — multi-decade TS trend following survives costs in liquid futures; equity single-name implementation still needs the after-cost gates below.)*

## Concrete strategy design (entries, ranking, exits, portfolio, costs assumptions)

### Name / family
**DAMB** — Dual Absolute-Momentum Breakout (long-only US equities, daily bars, PIT context).

### Universe & data (existing stack)
- Same Sharadar PIT market context + continuous fixture universe (~6.5k symbols capability; liquidity screen as today).
- No new alternative data. Optional: SPY / equal-weight breadth series already constructible from bars + context.

### Entry (signal) — deliberately *simpler* than Core
A symbol generates a candidate on session *t* (decision on close *t*, enter next open *t+1*) iff **all** hold:

1. **Liquidity / eligibility** (existing screens; fail-closed on missing context).
2. **52-week-high proximity (primary):** close ≥ **95%** of trailing 252-session high (George–Hwang layer; small predeclared grid 93/95/97% only after baseline freezes).
3. **Stock absolute momentum:** close > **200-session SMA** *or* 12-1 own return > 0 (pick **one** primary definition for the first experiment; do not OR-stack without a predeclared ablation).
4. **Breakout trigger (simple):** close breaks prior **20-session high** (naïve §2.5-like trigger — the control already earned OOS respect).
5. **Market absolute momentum (hard gate):** SPY (or broad liquid proxy) close > **200-session SMA**. No new entries when market absolute trend is off. Existing open positions may trail/exit normally (do not force flatten on gate flip in v1; test flatten as separate ablation).
6. **Cooldown:** 10 sessions after any exit on that symbol (keep).

**Explicitly removed from selection:** multi-factor composite ranks (12-1 percentile + breakout magnitude + RVOL + slope composites). No ML ranker. No alphabetical capital allocation.

**Optional weak tie-break only when capital is scarce:** higher 52w proximity, then higher dollar volume — *not* a research claim of CS alpha.

### Ranking / portfolio selection
- When multiple candidates on the same day: fill by **52w proximity ↓, then liquidity ↓** until risk budget / max positions bind.
- This is **capital rationing**, not a claim that rank order predicts residual alpha. Acceptance does **not** require monotonic deciles of 12-1.

### Exits (horizon-matched; path-aware)
| Leg | Rule | Rationale |
| --- | --- | --- |
| Initial structural stop | `min(breakout-day low, entry − 2×ATR(20))` | Keep Step-3 structural idea; path needs width |
| **Take-profit** | **None (disable fixed +2×ATR TP)** | Fixed TP truncates the h20–h120 drift object |
| Trail | 20-session low channel (predeclared alt: 40-session) | Harvest intermediate drift; fewer noise exits |
| Time stop | 90 sessions (alts 60/120 predeclared) | Bound capital occupancy; match event-study horizon |
| Forced close | Existing corporate-action / eligibility policy **unchanged** | Do **not** treat FC P&L as alpha (Step 1) |

Constant dollar risk when comparing stop/trail variants (research plan principle 4).

### Portfolio / risk
- RISK_PER_TRADE baseline **0.35%** of equity at *normal* vol (SPEC Core baseline).
- **Vol scaling (Barroso–Santa-Clara style):** scale risk_per_trade and/or max aggregate open risk by `target_vol / realized_vol`, where realized_vol is trailing ~20-session annualized vol of SPY (v1) or of the strategy’s own daily P&L once n is large enough (v2). Cap scale ∈ [0.25, 1.5].
- Max concurrent positions: start **8** (alts 5/10); aggregate initial open risk cap ~**3–4%** equity.
- No short leg in v1 (long-only; absolute gate already cuts risk-on when market TS is negative).

### Costs assumptions (measurement)
- Primary alpha metric: **pre-tax after 5 bps/side** (both entry and exit).
- Tax 15% on winners reported **separately** (never used as the accept gate).
- Do not invent liquidity-dependent impact in v1; add as stress (10–20 bps/side) once raw after-5bps edge exists.
- Idle cash earns 0 in v1 (conservative).

### What is *not* in v1
- Sector-neutral residual momentum.
- Intraday confirmation / pullback entry grids (SPEC follow-through remains a later house hypothesis).
- Harvesting forced closes.
- Any claim from the invalid 2022–2025 fail-closed matrix.

## How it differs from current Core / §2.5 control

| Dimension | Current Core (spec-compliant) | §2.5 naïve control | **DAMB (this proposal)** |
| --- | --- | --- | --- |
| Selection | Momentum rank + 52w + trend stack | Spike / simple breakout | **52w proximity + absolute stock trend + simple breakout** |
| Market gate | Not the primary research object yet | None | **Hard SPY 200DMA absolute filter** |
| Ranking claim | Rank should beat naïve | No rank | **No CS skill claim; rank is capital ration only** |
| TP | entry + 2×ATR(20) | Same family in recent runs | **No fixed TP** |
| Trail / hold | Structural stop + existing exit mix; still short-path sensitive | Same exit family | **20/40d trail + 60–120d time stop** |
| Risk | Fixed 0.35% | Higher historical risk variants | **Vol-scaled risk** |
| Success criterion | Must beat §2.5 | Baseline hurdle | **Beat both zero and §2.5 after costs on walk-forward; Core rank ablation must not be required** |

DAMB is closer to “naïve trigger + George–Hwang filter + TSMOM market timing + trend-following exits” than to “smarter Core ranker.”

## Why prior experiments predict this might work (map to Steps 0–3)

| Step | Measured fact | Implication for DAMB |
| --- | --- | --- |
| **0** Uncapped first Core | After costs deeply negative; 1×ATR stop dominated losses | Path too tight; churn destroys any slow drift |
| **1** FC audit | FC P&L is policy artifact | Do not design to harvest FC; keep FC accounting segregated |
| **2** Event study | h1–h5 ~0; h10–h120 positive; race ±1R coin-flip; excess vs universe thin (t≈1.78); 2021–22 weak | Edge is **long-horizon + largely common**; need longer holds, wider path, **absolute/regime filter**, not finer CS sort |
| **3** Spec + §2.5 | Structural stop + ranked fill improved bleed but still negative; **Core loses to naïve OOS** | Ranking layer failed the ship gate; simplify selection; fix horizon/TP/vol; use naïve-like trigger as base |
| Matrix 2022–25 | Fail-closed on stale terminals | No P&L claims; keep fail-closed integrity |

Decision-rule consistency with research plan: “Positive forward drift but negative trades → research confirmation/stops” **and** “edge limited / ranking fails → redesign signal.” DAMB does both without pretending CS residual is large.

## Why it might fail (steelman opposition)

1. **Drift is beta you already own.** If h20 excess t=1.78 is the whole story, long-only breakouts with a 200DMA gate may underperform buy-and-hold SPY after costs and tracking error. A strategy that is “market with worse path” is not an edge.

2. **Absolute filters are in-sample regime luck.** 2023–24 strength and 2021–22 weakness invite a 200DMA story that fails in sideways chop (whipsaw entries/exits) or in slow bear rallies inside a still-broken primary trend.

3. **Removing TP + widening trail increases left-tail occupancy.** Without vol scaling, a few 2022-style sequences can dominate drawdown even if mean drift is positive. Kaminski–Lo “stops help under momentum” is not a free lunch if serial dependence is weaker in the live decade.

4. **52w proximity may already be saturated / capacity-limited** in liquid names; George–Hwang was published 2004. After costs and in post-2019 data, the premium may be gone even if the academic mechanism once existed.

5. **Implementation drag on single-name equities.** TSMOM evidence is strongest in liquid futures. Daily equity breakouts pay spread, gap risk, and corporate-action noise; Novy-Marx–Velikov warn high turnover dies — DAMB must prove *low enough* turnover.

6. **Multiple testing.** Trail window × time stop × proximity × vol target × max positions is a combinatorial minefield. Without pre-registration and deflated Sharpe, DAMB becomes another overfit narrative.

7. **Control contamination.** If DAMB wins only because it copies the naïve trigger while Core’s extra filters were pure cost, the win is “delete Core,” not “new dual-momentum science.” That is still useful — but then ship the simplest variant.

## Measurement plan (ordered experiments, sample design, stats)

**Sample:** continuous fixture 2019-01-02 → 2025-12-31; **walk-forward** (e.g., 24m train / 12m test rolling, or expanding) because 2023–2025 is burned as untouched OOS. Freeze parameters before any *new* future holdout. Date-cluster inference for all t-stats. Primary metric: **after 5 bps/side expectancy and PF**; tax secondary. Segregate FC P&L in every table.

### Experiment order (one conceptual change at a time)

**E0 — Provenance lock (ops, not alpha)**  
Commit streaming loader / replay integrity so reports are re-runnable. Sequential runs only on 16GB hosts.

**E1 — Horizon-matched exits on the §2.5 control (no new selection)**  
Fix scanner = naïve benchmark. Disable fixed +2×ATR TP. Compare exits on constant risk:
- A: current structural stop + TP (control)
- B: structural stop + 20d trail + 90d time (no TP)
- C: structural stop + 40d trail + 90d time (no TP)  
**Question:** Does path/horizon alone flip after-cost expectancy for the only scanner that already showed OOS dignity?

**E2 — Market absolute gate on the E1 winner**  
Add SPY > 200DMA as entry gate only. Report trade count drop, fold-level consistency, 2021–22 vs 2023–24 behavior. **No other changes.**

**E3 — Selection ablation (still no multi-factor rank)**  
On E2 chassis, compare:
- S0: naïve breakout only  
- S1: naïve + 52w ≥95%  
- S2: S1 + stock > 200DMA  
Reject any variant that needs a composite rank to “work.”

**E4 — Vol scaling**  
On E3 winner, apply SPY realized-vol scaling of risk_per_trade (target predeclared, e.g. 10–12% ann. portfolio vol proxy). Compare maxDD and crash windows vs unscaled.

**E5 — Cost stress & capacity**  
Re-run winner at 10 and 20 bps/side; report turnover, average hold, ADV participation. If edge dies at 10 bps, capacity claim is weak.

**E6 — Deflated / multiple-testing wrap**  
Count **all** trials from E1–E5 (including losers). Compute Deflated Sharpe (Bailey–López de Prado) on daily strategy returns. Publish full trial ledger.

**E7 — Head-to-heads (only after E3)**  
DAMB-winner vs: (i) buy-and-hold SPY on same capital timeline, (ii) Core spec-compliant, (iii) §2.5 with E1 exits. Excess vs same-date universe mean at h20 for *accepted* signals must be reported but is not the sole gate.

### Stats
- Trade-level expectancy with **entry-date clustered** SE.
- Fold-level hit rate of positive after-cost months/quarters.
- No single year > ~25% of total profit (research plan gate).
- Do **not** invent numbers; do not use fail-closed matrix P&L.

## Acceptance / rejection gates

### Accept DAMB for paper-trading consideration only if **all** hold
1. After-cost (5 bps/side) expectancy **> 0** in a majority of walk-forward folds; full-sample after-cost PF **≥ 1.10** in a **broad** region of trail ∈ {20,40} and time-stop ∈ {60,90,120}, not a single spike.
2. Beats §2.5 control **and** Core on after-cost expectancy under identical costs, risk scaling rules, and walk-forward scheme.
3. Beats or is not clearly dominated by **SPY buy-and-hold** on risk-adjusted terms (Sharpe or Calmar) over the same evaluation windows — otherwise it is levered/noisy beta.
4. FC-segregated books still meet (1)–(2); edge must not depend on corporate-action policy.
5. Deflated Sharpe (or equivalent) remains persuasive after counting all E1–E5 trials.
6. Cost stress: after-cost expectancy still ≥ 0 at **10 bps/side** *or* explicit capacity note that only top-liquidity names are tradable (with that restricted universe re-tested).
7. Crash behavior: 2021–2022 fold drawdown materially better than unfiltered always-on breakout (Daniel–Moskowitz / Barroso mechanism check).

### Reject / stop conditions
- **R1:** E1 fails (horizon fix on naïve still after-cost negative across the predeclared exit grid) → long-horizon path is **not** sufficient; do **not** add ranking complexity; consider full strategy abandonment or non-breakout research.
- **R2:** E2 helps only by deleting almost all trades so confidence intervals explode → regime gate is a sample-size destroyer, not an edge.
- **R3:** E3 shows 52w / stock absolute layers **hurt** vs naïve under same exits → ship simplest naïve+horizon+market-gate or kill.
- **R4:** Any “win” requires composite CS ranking or large discrete parameter hunt → reject as overfit (Bailey–López de Prado).
- **R5:** Edge vanishes when FC removed or when tax-agnostic costs applied → reject.
- **R6:** Invalid / fail-closed replays → no promotion; fix data integrity first.

## Implementation cost on this repo (files / new modules / data needs)

**Low–medium.** No new vendors. Mostly configuration + small domain policy + research harness.

| Area | Touch points | Notes |
| --- | --- | --- |
| Scanner | `src/invest/domain/scanner.py`, `momentum_selection_scanner.py` | New `DualAbsoluteMomentumScanner` (or flags): 52w + stock absolute + breakout; **no** multi-score rank requirement |
| Market gate | `application/backtest_run.py` / scan pipeline + indicators | SPY (or proxy) 200DMA series; gate entries |
| Exits | `domain/exit_policy.py`, `domain/sizing.py` | Disable fixed TP path; 20/40d trail + time stop configs |
| Sizing / vol scale | `domain/sizing.py`, backtest portfolio loop | Scale risk_per_trade by realized vol |
| CLI | `adapters/cli.py` | `--strategy damb` (name TBD) alongside `core` / `benchmark` |
| Research | `fixtures/real-continuous/reports/` harnesses | Ordered E1–E5 scripts; trial ledger JSON; FC segregation columns |
| Spec / docs | `SPEC.md`, research plan | Record predeclared grids before runs |
| Data | Existing bars + market-context | Ensure SPY (or chosen proxy) present in universe/bars for gate |
| Tests | domain exit/scanner unit tests | Strict TDD for gate, no-TP, trail, vol scale |

**Out of scope for this proposal:** broker trailing-order production wiring (paper path can EOD ratchet as today); ML rankers; matrix P&L resurrection.

## Confidence (0–100) and single sharpest risk

**Confidence: 58 / 100**

Honest band: better than continuing Core ranking (~20) or regime-gating Core without horizon fix (~35); far from “edge found.” The event study *directionally* supports horizon + absolute participation; Step 3 *falsifies* ranking; nothing yet proves after-cost TS participation beats SPY or survives 10 bps.

**Sharpest risk:** the long-horizon drift is **non-tradeable beta** — DAMB becomes a noisier, gap-prone, fee-paying way to hold risk-on equities, and E1/E7 will show SPY dominance once path is allowed to run.

## Attacks on the other two archetypes

### A) Hold longer / widen path — keep breakout signal, fix horizon & stops only

**What is right:** Step 2’s decision rule *requires* this. Short-horizon ~0 and coin-flip ±1R make 1×ATR / short holds scientifically doomed (Kaminski–Lo under near-RW short paths). Spec structural stops already proved “path matters” by cutting uncapped bleed (Step 3).

**What is weak / dangerous:**
- Uncapped **after** structural stops is **still negative** after costs. Horizon fix is necessary, **not sufficient**.
- Keeping Core’s ranking while only widening path doubles down on a layer that **failed §2.5 OOS**.
- Fixed +2×ATR TP, if retained, actively fights the long-horizon object.
- Without absolute/vol crash control, longer holds **increase** occupancy through Daniel–Moskowitz panic windows (2021–22 already red in the event study).

**Verdict:** Mandatory module inside DAMB (E1), fatal as a *standalone* research program if it pretends ranking and regime are optional afterthoughts.

### B) Ranking overhaul — continuous scores, deciles, composite; kill binary accept

**What is right:** Binary accept + alphabetical capital rationing was dumb engineering. Feature persistence for research is fine. If a *single* feature (52w proximity) shows monotonicity, promote it — George–Hwang says that can dominate past returns.

**What is weak / dangerous (most overfit-prone archetype):**
- Step 2 already measured **thin CS residual** (excess t≈1.78, median negative). You cannot rank your way into a residual that barely exists.
- Step 3: Core’s multi-layer selection **lost to naïve OOS**. That is a direct empirical rebuttal to “more sophisticated ranking.”
- Decile theater + composite weights + ML are classic Bailey–López de Prado multiple-testing machines. With n_days clustered and regime-dependent years, monotonicity in-sample is cheap.
- Novy-Marx–Velikov: complexity that increases turnover is the opposite of what after-cost economics wants.

**Verdict:** **Most dangerous archetype** for this project *right now*. It flatters the original Core story, burns research budget, and fights the measurement. Allowed only as **single-feature ablation** (52w yes/no), not as a composite quest.

### C) Regime / risk-on gate — 200DMA / breadth / vol filter before any signal

**What is right:** Event-study years and momentum-crash literature say exposure timing matters. Breadth/vol are economically motivated. Barroso–Santa-Clara vol scaling is one of the few interventions with both theory and strong empirical crash reduction.

**What is weak / dangerous:**
- Gating a **negative-expectancy** entry (current Core after costs) mostly **reduces sample size** and can create illusory improvement by deleting losing regimes without creating trade-level edge.
- Step 3 write-up already warned: regime gate is **conditional** on signal drift / control diagnosis — and the control comparison points at ranking failure first.
- Breadth definitions are easy to p-hack (threshold, universe, equal vs cap weight).
- A pure regime overlay on Core keeps the wrong exit horizon and the wrong selection stack.

**Verdict:** Powerful as **E2/E4 modules on a horizon-fixed simple entry**, illegitimate as the first or only lever on Core-as-is.

### Which archetype is most dangerous?
**B — Ranking overhaul.** It has the highest chance of producing a beautiful backtest with no economic residual, the weakest support from Steps 2–3, and the strongest psychological pull (“we just need better features”). A is incomplete but scientifically mandatory; C is literature-backed but parasitic on a fixed entry/exit chassis. **B is the implementation trap.**

## Final one-liner

**Bet the research budget on DAMB: simple 52w+breakout entries, hard market absolute gate, no fixed TP, 20–40d trails, vol-scaled risk — and let E1 (horizon-matched exits on the §2.5 control alone) be the single kill-or-continue experiment.**
