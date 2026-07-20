# Proposal: Quiet Drift — post-event long-horizon portfolio ranked by information discreteness, with no price stops and beta-separated measurement

**Judge:** Claude Fable (claude-fable-5)
**Date:** 2026-07-20
**Verdict archetype:** pivot — keep the event trigger, replace the ranking dimension with an orthogonal one (path smoothness), replace stop-bracketed trades with a fixed-horizon vol-scaled portfolio, and measure cross-sectional alpha beta-hedged from day one.

## Thesis (1 paragraph)

Every experiment so far converges on one shape: the accepted events have real forward drift at 20–120 sessions (h60 +3.49%, clustered t=7.49; h120 +7.11%, t=13.6), but (a) any tight price stop pays a coin-flip toll because the path hits −1×ATR before +1×ATR 51.5% of the time, and (b) the momentum/52w-high ranking layer *subtracts* value versus a naïve spike control OOS (−17.9 vs +30.0 expectancy). The system is a trade-structure machine bolted onto what the data says is a slow, portfolio-horizon phenomenon, and it ranks candidates by exactly the features that the strongest post-2004 momentum literature says are the *wrong* conditioning variables on a spike-selected sample. I propose to stop fighting both findings: hold the event cohort for a fixed 60-session horizon with no price stop, size positions by inverse volatility, cap concurrency, and rank admission by **information discreteness** (Da–Gurun–Warachka "frog in the pan") — preferring names whose formation-period gain arrived as many small same-sign moves rather than one jump — because that is the best-documented cross-sectional discriminator of *which* momentum continues versus reverses, and it is nearly orthogonal to the momentum-magnitude/52w-high composite that just failed. Crucially, the go/no-go is decided by a cheap event-study extension (no backtest) before any engine work: does excess-vs-universe drift at h60 survive, and is it monotone in the discreteness decile?

## Mechanism (why edge should exist economically)

Two stacked mechanisms, both with published economic stories:

1. **Gradual-information underreaction.** Limited investor attention means information arriving continuously in small increments is underpriced relative to the same cumulative information arriving as a discrete jump (which attracts attention and gets priced — or overpriced — immediately). Da–Gurun–Warachka show six-month momentum of 8.86% for continuous-information stocks versus 2.91% for discrete-information stocks, and the continuous-information continuation *does not reverse* long-run. Our scanner conditions on spike events — the discrete end of that spectrum — and then ranks by momentum magnitude, which on a spike-conditioned sample loads further onto discreteness. That is a coherent economic explanation for why the ranking layer underperformed a naïve control: it is ranking by a feature whose conditional expectation is *lower* continuation. Flipping the ranking to prefer smooth formation paths targets the documented underreaction channel instead.
2. **Anchoring near highs without reversal.** George–Hwang show nearness to the 52-week high forecasts returns that do not reverse long-run — an anchoring/underreaction channel consistent with the +60/+120-session drift we measured. This is the one existing feature worth keeping, but as a *portfolio admission* criterion at a 60-session horizon, not as a tiebreak for a 2×ATR-bracketed trade whose median stop-out was 3 days.

The trade-structure change is not cosmetic. Kaminski–Lo show stop-loss rules only add value when the underlying process has momentum at the *stop-decision* horizon; our measured short-horizon drift is zero/negative (+1d −0.08%, +5d −0.04%) with near-random ±1R race, which is precisely the regime where stops convert noise into realized losses. The 1×ATR stop alone destroyed $3.59M of the uncapped ledger. Removing price stops and controlling risk through sizing and diversification (inverse-vol weights, position cap) is the standard portfolio answer (Barroso–Santa-Clara for the vol-management channel).

## Literature anchors (3–8 citations)

1. Da, Z., Gurun, U., Warachka, M. (2014), "Frog in the Pan: Continuous Information and Momentum," *RFS* 27(7):2171–2218, DOI [10.1093/rfs/hhu003](https://academic.oup.com/rfs/article-abstract/27/7/2171/1578455) — information discreteness is a first-order cross-sectional discriminator of momentum continuation; directly explains why spike-conditioned momentum ranking failed.
2. George, T., Hwang, C-Y. (2004), "The 52-Week High and Momentum Investing," *JF* 59(5):2145–2176, DOI [10.1111/j.1540-6261.2004.00695.x](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2004.00695.x) — 52w-high proximity forecasts non-reversing returns; keep it, but at portfolio horizon.
3. Blitz, D., Huij, J., Martens, M. (2011), "Residual Momentum," *Journal of Empirical Finance* 18(3):506–521 ([SSRN 2319861](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2319861)) — ranking on residual (beta-stripped) returns roughly doubles risk-adjusted momentum profit and stabilizes it; motivates the beta-hedged measurement design, since our h20 excess-vs-universe was only +0.36% (t=1.78).
4. Kaminski, K., Lo, A., "When Do Stop-Loss Rules Stop Losses?" ([SSRN 968338](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=968338)) — stops add value only under return momentum at the stop horizon; our short-horizon drift is ≤0, so stops are predicted (and measured) to destroy value.
5. Barroso, P., Santa-Clara, P. (2015), "Momentum Has Its Moments," *JFE* 116(1):111–120 ([SSRN 2041429](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2041429)) — momentum's crash risk is forecastable from its own realized vol; volatility-scaled sizing, not price stops, is the risk-control mechanism for a stop-free book.
6. Daniel, K., Moskowitz, T., "Momentum Crashes" ([NBER w20439](https://www.nber.org/papers/w20439)) — momentum crashes cluster in rebound/high-vol states; the steelman against removing stops, addressed via vol-scaling and exposure cap rather than per-name stops.
7. Novy-Marx, R., Velikov, M. (2016), "A Taxonomy of Anomalies and Their Trading Costs," *RFS* 29(1):104–147 ([link](https://academic.oup.com/rfs/article-abstract/29/1/104/1844518)) — cost discipline: a 60-session hold cuts turnover ~6× versus the median-3-day stop-out regime, which is the single largest after-cost improvement available for free.
8. Bailey, D., López de Prado, M., "The Deflated Sharpe Ratio" ([SSRN 2460551](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)) — the multiple-testing control this proposal's gates commit to, given that 2023–2025 is a burned holdout.

## Concrete strategy design (entries, ranking, exits, portfolio, costs assumptions)

**Event trigger (unchanged):** the existing scanner event stream — use the §2.5 naïve spike trigger as the event source, since Step 3 showed it is the stronger event definition. The event is *admission candidacy*, not a trade with a bracket.

**Ranking (replaced):** at each scan date, score candidates by:

- **ID (information discreteness), primary:** over the trailing 60 sessions ending the day before the event, `ID = sign(cumulative return) × (%negative days − %positive days)` (the DGW measure). Lower ID = more continuous information = higher rank. Computable from bars already in the fixture; no new data.
- **52w-high proximity, secondary tiebreak** (existing feature, kept per George–Hwang).
- **Event-day gap penalty:** demote candidates whose event-day return exceeds, say, the 95th percentile of their own trailing daily-return distribution — the most discrete of the discrete. (Exact percentile is a *predeclared* single value, not a grid.)

**Entry:** next-session open (control-identical), only if a portfolio slot is free.

**Exits — no price stop:**

- Fixed horizon: close at the open of session T+60 (matches the strongest measured drift with t=7.49 and no full-window survivorship problem, unlike h120).
- Corporate-action / context forced exits: keep the existing fail-closed machinery as a *safety* exit, but per Step 1's finding, FC-exited trades are excluded from alpha attribution (reported separately, never harvested).
- No ATR stop, no trailing channel, no TP. Nothing touches price paths intra-hold.

**Portfolio:**

- Max **20 concurrent positions** (predeclared; not a grid).
- Inverse-volatility weights: per-name risk budget ∝ 1/ATR%(20), normalized so gross exposure ≤ 100%, no leverage, no shorts.
- 10-session per-symbol cooldown retained (already spec).
- Slot contention resolved by ID rank (best = smoothest formation path).

**Costs:** 5 bps/side as configured; 15% tax on winners reported secondary per agreed principles. Turnover assumption: ~4 round-trips/slot/year → ~80 round-trips/year at 20 slots, versus 3,451 trades in the uncapped spec run. Cost drag falls roughly an order of magnitude by construction, before any alpha claim.

**Benchmark & hedged measurement:** every performance claim is reported (a) raw, (b) versus SPY/IWM buy-and-hold at matched average exposure, and (c) as excess versus the same-date eligible-universe mean (the Step 2 methodology) — because the thin h20 excess (+0.36%, t=1.78) says most raw drift is beta, and this proposal refuses to sell beta as alpha.

## How it differs from current Core / §2.5 control

| Dimension | Core (spec-compliant) | §2.5 control | Quiet Drift |
|---|---|---|---|
| Event | momentum-selection scanner | naïve spike | naïve spike (same as control) |
| Ranking | momentum → 52wh → liquidity | none | **ID (path smoothness)** → 52wh |
| Stop | min(breakout low, entry−2×ATR) | same family | **none** |
| TP | entry+2×ATR | same family | none |
| Horizon | path-dependent, median days | path-dependent | **fixed 60 sessions** |
| Risk control | per-trade stop distance | per-trade | **inverse-vol weights + 20-slot cap** |
| Alpha metric | net P&L | net P&L | **excess vs universe, beta-separated** |

It is *not* archetype A (it replaces the ranking, not just the horizon), *not* archetype B (it does not search a composite over the failed feature family; it introduces one orthogonal, literature-anchored feature with a single predeclared definition), and *not* archetype C (no regime gate anywhere).

## Why prior experiments predict this might work (map to Steps 0–3)

- **Step 0:** the 1×ATR stop bucket was −$3.59M across 3,413 trades with median 3-day stop-outs; the only structurally profitable *legitimate* bucket (trailing channel, +$2.36M) was the one that let winners breathe. Quiet Drift removes the loss engine entirely rather than widening it.
- **Step 1:** FC profit is a policy artifact. Quiet Drift keeps FC as safety-only and excludes it from attribution, so the design cannot silently re-harvest it — the contamination that inflated every prior "positive" slice is walled off by construction.
- **Step 2:** the drift the strategy needs *was directly measured* on this event stream: +3.49% at h60 (t=7.49). The fixed 60-session horizon is not a hope; it is the horizon where the existing signal's own event study is strongest without the h120 survivorship caveat. The ±1R race result (48.5% up-first) predicts that *any* bracket structure taxes this signal; only a bracket-free structure can collect the measured drift.
- **Step 3:** the ranking failed against no-ranking. That licenses exactly two moves: drop ranking, or change the ranking *dimension*. Quiet Drift does the second with a feature (ID) that the literature says separates continuation from reversal on precisely this kind of sample — and the go/no-go experiment tests that claim on our own data before any engine work.
- **Step 4 (aborted matrix):** the fail-closed stale-terminal-open events (VG2, ISEE, CONE) show multi-year replays *will* carry positions across coverage gaps; a fixed-horizon design with a hard T+60 close sharply reduces terminal-open exposure versus indefinite trailing holds.

## Why it might fail (steelman opposition)

1. **The drift is all beta.** h20 excess vs universe was only +0.36% (t=1.78, median negative). If h60/h120 excess is similarly thin, Quiet Drift is a levered small-cap beta portfolio with extra steps, and the honest verdict is "buy IWM." This is the sharpest risk and it is *the first thing measured* (Experiment Q1) — the proposal dies in a week if true, at near-zero cost.
2. **ID doesn't discriminate on a spike-conditioned sample.** DGW's result is on the full CRSP cross-section with 6-month formation. Conditioning on a spike event truncates the ID distribution (every candidate just had a discrete day); the residual variation may be too narrow to spread deciles. Q1's decile monotonicity gate covers this.
3. **No stops = crash exposure.** 2021–2022 were −1.76%/−2.54% at h20 (t≈−2). A stop-free, always-invested 20-slot book eats those years fully; Daniel–Moskowitz says momentum crash states are exactly when high-beta recent winners die together. Vol-scaled weights mitigate but do not eliminate; walk-forward folds spanning 2021–2022 must survive the drawdown gate.
4. **Capacity/selection interaction.** With 20 slots and ~12k signals over 7 years, admission is highly selective; the realized portfolio may not inherit the event-study cohort's mean (selection into slots ≠ random sampling of the cohort). The measurement plan tests the *ranked* cohort event-study first, so the slot-selection gap is visible before backtesting.
5. **h120 survivorship.** The strongest drift number (t=13.6) is the most contaminated one. The design deliberately anchors on h60, but if h60 excess fails and only h120 "works," that is a rejection, not a pivot to h120.

## Measurement plan (ordered experiments, sample design, stats)

All inference date-clustered; all trials logged; deflated Sharpe over the *total* set of variants ever tried on this fixture (including Steps 0–3's).

**Q1 — Event-study extension (no backtest, ~1 day of compute):** on the existing 12,295-signal Step 2 cohort:
1. Compute excess-vs-same-date-eligible-universe forward returns at h60 (and h120 with survivorship flagged), not just h20. Clustered t.
2. Compute ID for every signal; split cohort into ID quintiles; report h20/h60 raw and excess drift per quintile.
3. Same split for 52w-high proximity as a check that the kept feature still earns its seat.
Sample: full 2019–2025 cohort, per-year breakdown, FC-fate cohort excluded/reported separately.

**Q2 — Ranked-cohort study:** restrict to the top-2-quintile-ID subset; re-run the Step 2 horizon table. This is the cohort the portfolio would actually hold. Walk-forward folds: expanding-origin yearly folds 2019→2025 (2023–2025 is burned as holdout; treated as walk-forward only, per agreed principle 7).

**Q3 — Portfolio backtest (only if Q1+Q2 gates pass):** implement fixed-horizon/no-stop/inverse-vol replay; run Quiet Drift vs two controls under identical replay: (a) §2.5 control as-is, (b) *random-admission* variant (same trigger, same portfolio mechanics, random slot fill) to isolate the ranking's marginal value — the lesson of Step 3 institutionalized. Sequential runs only (16 GB machine rule).

**Q4 — Sensitivity, predeclared and small:** horizon {40, 60, 80}; slots {10, 20}; nothing else. Every cell reported; broad-region criterion, not max-picking.

## Acceptance / rejection gates

**Gate 1 (after Q1):** excess-vs-universe h60 drift > 0 with clustered t ≥ 2.5, **and** ID quintile spread monotone-ish (top-minus-bottom quintile h60 excess > 0, t ≥ 2.0). *Fail → reject the proposal entirely; publish the negative; the signal is beta.*
**Gate 2 (after Q2):** ranked cohort h60 excess ≥ full-cohort h60 excess (ranking must not subtract value — the Step 3 lesson as a hard gate), positive in ≥ 4 of 6 yearly folds.
**Gate 3 (after Q3):** after-cost pre-tax expectancy > 0 in a majority of walk-forward folds; beats random-admission control on OOS folds; PF ≥ 1.10 across the Q4 broad region; no single year > 25% of profit; max drawdown ≤ 1.25× matched-exposure IWM drawdown over 2021–2022 folds; deflated Sharpe > 0 counting all historical trials.
**Standing rejection conditions:** any dependence of the edge on FC-exited trades; any result that only appears at h120; any gate passed only by the 2023–2024 fold pair.

## Implementation cost on this repo (files / new modules / data needs)

- **Q1/Q2: near-zero new surface.** Extends `research_steps12.py` Phase C (fixtures/real-continuous/reports/): add h60/h120 excess-vs-universe columns and an ID computation per signal (pure function over trailing 60 bars, already streamed). No engine change, no new data — bars.json has everything ID needs.
- **Q3: one new exit policy + one sizing policy.** A `FixedHorizonExit` (close at T+60 open) alongside existing exits; an inverse-vol allocator + 20-slot admission ranked by ID in the portfolio layer; a `--strategy quiet-drift` wiring in `cli.py`. FC machinery, streaming loader, cooldown, cost model all reused untouched. Prerequisite: **commit the WIP streaming loader first** (already flagged as blocking provenance for every future report).
- No new data vendors, no intraday data, no shorting, no options.

## Confidence (0–100) and single sharpest risk

**Confidence: 40.** High confidence the measurement plan resolves the question cheaply and honestly; moderate-low confidence the cross-sectional alpha survives beta separation, because the only excess number we have (h20: +0.36%, t=1.78) is thin. **Sharpest risk:** Gate 1 fails — the 60-session drift is beta plus selection into high-beta small caps, and no admission ranking can fix a cohort whose excess return is zero. That outcome costs ~a day of compute and kills the idea cleanly, which is exactly what a gate is for.

## Attacks on the other two archetypes

**A) Hold longer / widen path (keep breakout signal, fix horizon & stops only).**
A is half-right and that makes it dangerous: the event study *does* endorse longer horizons, so A will backtest green on 2023–2024 and its author will declare victory. But A keeps the ranking that Step 3 proved subtracts value versus no-ranking, and it makes no attempt to separate beta from alpha — so its "edge" is the +3.49% h60 raw drift, of which the only measured excess component is +0.36% at t=1.78. A is a levered beta bet wearing the event study as a costume. Worse, "widen the path" variants (2×, 3×ATR stops) still pay Kaminski–Lo's toll: with zero short-horizon drift, *every* stop width is a noise-triggered loss realizer — Step 3 already ran this experiment (structural stop = widened stop) and the uncapped book still bled −$50/trade OOS. If A ships without a beta-separated gate, it is the most likely archetype to produce a confident, well-documented, *wrong* deployment.

**B) Ranking overhaul (continuous scores, deciles, composite; kill binary accept).**
B correctly reads Step 3's "ranking is the missing-value locus" but draws the wrong conclusion: it plans to search *harder* in the same feature family (momentum percentile, 52wh distance, breakout magnitude, RVOL, trend slope — six features, deciles, composites) that just lost to a no-ranking control. That is a multiple-testing factory: six features × decile cuts × composite weights on a burned 2023–2025 sample, with correlated features whose range is already truncated by spike conditioning. The deflated Sharpe correction B owes will be enormous, and B has no *economic* argument for why any of those features should have conditional alpha on this sample — the literature actually argues the opposite for momentum magnitude on discrete-information names (DGW). B's honest version collapses into my Q1/Q2: test *one* orthogonal, theory-motivated feature with predeclared gates. B's likely version is a decile-grid fishing expedition that reports its best composite.

**C) Regime / risk-on gate (200DMA / breadth / vol filter before any signal).**
C is the most dangerous archetype, and I say that having proposed nothing that competes with it directly. The entire evidentiary basis for a regime gate is that 2021–2022 were negative and 2023–2024 positive — **two** bad regime episodes in the whole fixture. Any of the proposed filters (200DMA, breadth, realized vol, dispersion) has roughly *two effective independent observations* of the "off" state to fit against; a gate tuned on that will pass in-sample by construction and carry near-zero out-of-sample information. It is curve-fitting with a macro vocabulary. Worse, C is logically downstream of an unproven premise: gating decides *when* to take a signal that has not yet demonstrated cross-sectional alpha *ever*. Gating beta exposure is market timing — a different claim needing its own (much longer) evidence base. Step 3's own conclusion already said this: "if the selection adds nothing over a spike-buying control, gating by market regime does not rescue it." C should not be allowed to run until some archetype passes a Gate-1-style alpha test; if it runs first, it will overfit two years and burn what is left of the walk-forward sample.

**Ranking of danger: C > A > B.** C overfits with the least data, A deploys beta as alpha with the most confidence, B wastes the most compute but its own deflated-Sharpe discipline (if enforced) at least kills it visibly.

## Final one-liner

I would bet the research budget on one day of compute: extend the existing event study to **excess-vs-universe h60 returns split by information-discreteness quintile** — if the smooth-formation-path quintile shows monotone positive beta-separated drift (clustered t ≥ 2.5), Quiet Drift is real and everything else is engineering; if it doesn't, the signal is beta and every archetype including mine should be shelved.
