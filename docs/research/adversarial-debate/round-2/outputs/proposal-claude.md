# Negative Screen First (NS) — trade the median, not the tail

**Seat:** Adversarial Judge Claude · Round 2
**Date:** 2026-07-20
**Line status:** NEW named line. Not a continuation of the naïve-event → fixed-horizon → slot-lottery portfolio residual. That residual stays frozen and dead.

---

## Thesis

Gate 1a and Phase 2/2b are not in conflict, and the record has been reading them as if they were. Gate 1a measured a **mean** on ~11.5k events against an **equal-weight eligible-universe** benchmark. Phase 2 measured a **200-trade realization** against **nothing**, and S2 then measured it against **SPY** and found −102/trade. Three wedges separate those objects — breadth (200 draws from a tail-driven distribution), benchmark (equal-weight microcap universe ≠ SPY), and skew (median excess negative at h20/h60/h120, hit-rate 49%, 104/200 trades terminated by corporate action). Every one of those wedges points at the same characteristic: **the accepted event cohort is a lottery-stock basket**. The literature is unambiguous about the sign of lottery exposure — high-MAX / high-idiosyncratic-skew stocks earn *low* average returns because gambling preferences and attention overprice them. So the program should stop trying to harvest a rare right tail with 20 slots and instead test the only direction the evidence and the literature agree on: a **long-only, high-breadth, low-turnover underweight of lottery characteristics on the liquid US universe, benchmarked to SPY from the first measurement**. Breadth goes from ~29 positions/year to ~10³ names/month; the benchmark stops being a microcap average; and the claim becomes a *replication of a published effect in our window and our cost structure* rather than a discovery. The terminal deliverable is honest either way: a small implementable tilt, or a published "no retail-implementable lottery tilt survives 5bps — own the index."

---

## Mechanism

Two mechanisms, both with the correct sign for a **negative screen**, both already visible in our own settled numbers.

1. **Probability weighting / gambling preference.** Cumulative-prospect-theory investors overweight small probabilities of large gains, so positively-skewed securities are held in undiversified positions and bear a *negative* premium (Barberis–Huang). Empirically the characteristic that prices this is MAX — the maximum daily return in the prior month — and the decile spread is ~1%/month with the low-MAX decile winning (Bali–Cakici–Whitelaw).

2. **Attention-driven buying pressure and its reversal.** Retail investors are net buyers of attention-grabbing stocks (extreme returns, volume spikes — i.e. *exactly our scanner's admission criterion*), producing temporary price pressure that reverses (Barber–Odean).

Our Step-2 event study is a textbook realization of mechanism 2: h+1 mean −0.08%, h+5 −0.04%. The cohort is built from momentum/volume spikes, so it is *constructed* to sit in the right tail of MAX. Mechanism 1 then says the typical member of that cohort should underperform — which is exactly Gate 1a's **negative median at every horizon** and Phase 2b's **−102/trade vs SPY**.

The positive Gate 1a mean is the residual right tail, and Phase 2 tells us when it paid: **2020 = 85.7% of net profit**. 2020–21 is the single largest documented episode of social-interaction-amplified lottery demand in market history (Bali–Hirshleifer–Peng–Tang–Wang). The one year our long-lottery book worked is the year the lottery-demand literature says the bubble inflated. That is not an anomaly in the record; it is the mechanism confirming itself with the sign we did not want.

The trade, therefore, is the other side. Long-only investors cannot short microcap lottery names at 5bps, but they can *decline to own them*, which is where the lottery-demand literature has real capacity (Bali–Brown–Murray–Tang show lottery demand also drives the beta anomaly; Frazzini–Pedersen's long-only leverage-constraint variant is the same family).

---

## Literature anchors

1. **Barberis & Huang (2008), "Stocks as Lotteries: The Implications of Probability Weighting for Security Prices," *AER* 98(5):2066–2100.** [doi:10.1257/aer.98.5.2066](https://doi.org/10.1257/aer.98.5.2066) — Theoretical basis for a *negative* premium on positively skewed securities; predicts our negative median with a positive tail-driven mean.
2. **Bali, Cakici & Whitelaw (2011), "Maxing out: Stocks as lotteries and the cross-section of expected returns," *JFE* 99(2):427–446.** [doi:10.1016/j.jfineco.2010.08.014](https://doi.org/10.1016/j.jfineco.2010.08.014) · [NBER w14804](https://www.nber.org/system/files/working_papers/w14804/w14804.pdf) — The exact predictor (MAX, prior-month max daily return), ~1%/mo decile spread, robust to size/BM/momentum/reversal/liquidity/skewness. This is the signal NS-2 replicates.
3. **Barber & Odean (2008), "All That Glitters: The Effect of Attention and News on the Buying Behavior of Individual and Institutional Investors," *RFS* 21(2):785–818.** [doi:10.1093/rfs/hhm079](https://doi.org/10.1093/rfs/hhm079) — Attention/volume/extreme-return spikes attract retail buying then reverse; describes our scanner's admission rule and our h+1/h+5 negatives.
4. **Kumar (2009), "Who Gambles in the Stock Market?," *JF* 64(4):1889–1933.** [doi:10.1111/j.1540-6261.2009.01483.x](https://doi.org/10.1111/j.1540-6261.2009.01483.x) — Identifies which investors buy lottery stocks and confirms underperformance; supports the retail-crowding channel being persistent rather than arbitraged.
5. **Bali, Hirshleifer, Peng, Tang & Wang (2021, rev. 2025), "Social Interactions and Lottery Stock Mania," NBER w29543.** [nber.org/papers/w29543](https://www.nber.org/papers/w29543) · [doi:10.2139/ssrn.3343769](https://doi.org/10.2139/ssrn.3343769) — Social-interaction amplification of lottery demand; the direct explanation for why 2020 is 85.7% of Phase 2's net profit.
6. **Bali, Brown, Murray & Tang (2017), "A Lottery-Demand-Based Explanation of the Beta Anomaly," *JFQA* 52(6):2369–2397.** [doi:10.1017/S0022109017000928](https://doi.org/10.1017/S0022109017000928) — Lottery demand subsumes the beta anomaly; a long-only lottery underweight is the capacity-bearing implementation of both.
7. **Chen & Zimmermann (2022), "Publication Bias in Asset Pricing Research," arXiv:2209.13623.** [arxiv.org/abs/2209.13623](https://arxiv.org/abs/2209.13623) — Empirical-Bayes shrinkage for published predictors is only 10–15% of in-sample means; the correct prior for a *replication* claim, and the counterweight to McLean–Pontiff's 58% decay ([doi:10.1111/jofi.12365](https://doi.org/10.1111/jofi.12365)).
8. **Novy-Marx & Velikov (2016), "A Taxonomy of Anomalies and Their Trading Costs," *RFS* 29(1):104–147.** [doi:10.1093/rfs/hhv063](https://doi.org/10.1093/rfs/hhv063) — Turnover-adjusted survival of anomalies; MAX-family signals are monthly and cost-sensitive, which sets NS-3's binding gate.

Method anchors used but not part of the economic claim: Grinold (1989) fundamental law, `IR = IC·√BR` ([doi:10.3905/jpm.1989.409211](https://doi.org/10.3905/jpm.1989.409211)); Bailey & López de Prado (2014) deflated Sharpe ([doi:10.3905/jpm.2014.40.5.094](https://doi.org/10.3905/jpm.2014.40.5.094)); Harvey, Liu & Zhu (2016) multiple-testing thresholds ([doi:10.1093/rfs/hhv059](https://doi.org/10.1093/rfs/hhv059)); Hou, Xue & Zhang (2020) replication/microcap critique ([doi:10.1093/rfs/hhy131](https://doi.org/10.1093/rfs/hhy131)); Shumway (1997) delisting-return convention ([doi:10.1111/j.1540-6261.1997.tb03818.x](https://doi.org/10.1111/j.1540-6261.1997.tb03818.x)).

---

## Concrete strategy design

**Universe (monthly, point-in-time).** Sharadar TICKERS primary common stock on AMEX/ARCA/NASDAQ/NYSE, listed as of formation date. Liquidity floor via the existing `liquidity_screen.py` (trailing-inclusive median dollar volume) with a predeclared floor and a price floor ($5) — both frozen before any sort is run. Delisted names carry a Shumway delisting return, not a silent drop.

**Signal (one feature, frozen).** `MAX5` = mean of the 5 largest daily returns over the prior 21 sessions. Chosen over Bali et al.'s MAX1 because MAX5 is their own stated robustness variant and is less contaminated by single-print/split artifacts on illiquid names. **One predeclared alternative** (`IVOL` = residual σ vs SPY over 21 sessions) is registered up front as a robustness arm, not a search axis. No composites. No lookback grid.

**Ranking.** Cross-sectional quintiles of MAX5 within the liquid universe, formed on month-end, applied at next-month open. That is the *entire* ranker. There is no scanner, no momentum gate, no event.

**Entries / exits.** Monthly rebalance. No stops, no take-profits, no trailing exits, no time-stop, no path dependence whatsoever. A name is held while it stays out of the top MAX5 quintile and inside the liquid universe. This deliberately removes every mechanism that Steps 0–1 identified as a P&L artifact (tight stops taxing noise; forced-close profit as policy artifact).

**Portfolio.**
- *Primary book:* long-only, hold the bottom four MAX5 quintiles, weighted by trailing dollar volume (a liquidity-weighted proxy for cap weight, because we have **no PIT market cap** — see data audit). Target ~500–1500 names. Breadth ≈ 10³/month vs Phase 2's ~29/year.
- *Diagnostic book:* the academic Q1−Q5 equal-weight long/short spread, reported for mechanism verification only. **Never** on the accept path — it is not implementable for this operator.
- *Benchmark:* SPY on the identical clock, matched notional, from the first measurement. Not an equal-weight universe average. This is the direct lesson of S2.

**Costs.** 5 bps/side primary on turnover only (rebalance trades), pre-tax primary, 15% tax on gains secondary. Turnover is reported as a first-class gate quantity, not a footnote, because a monthly MAX sort is a high-turnover object (Novy-Marx–Velikov).

---

## How it differs from the settled Phase 2 residual and from Round 1

| Axis | Phase 2 residual (dead) | Round 1 Quiet Drift | Round 1 DAMB | Round 1 Form-4 | **NS** |
|---|---|---|---|---|---|
| Selection object | price-spike event | price-spike event | price-spike event | SEC filing event | **whole liquid universe, always on** |
| Breadth | ~29 positions/yr | ~29/yr | ~29/yr | rarer still | **~10³/month** |
| Signal direction | long the spike | long the spike | long the spike | long the buy | **underweight the spike-type name** |
| Ranker | none (lottery) | ID composite | gate + proximity + vol | cluster/opportunistic | **one published characteristic** |
| Benchmark at t₀ | none | universe EW | SPY (late) | universe | **SPY from experiment 1** |
| Exit | fixed T+60 | fixed hold | trail + time stop | fixed hold | **rebalance only** |
| New data | none | none | none | **new SEC tape** | none for NS-0..NS-2 |

NS is **not** the residual with more slots. I want that stated flatly because the breadth argument (W1) is the most seductive rescue available and I refuse it: even at infinite slots, the harvested object converges to Gate 1a's cohort mean, which is measured against an equal-weight universe — and S2 says that object loses to SPY. **Breadth would fix the variance and not the benchmark.** That is why the residual is genuinely dead rather than merely concentrated, and it is why NS changes the *sign and the population*, not the slot count.

NS is also not archetype C. It makes a real cross-sectional claim with a predeclared feature and a kill gate; it just makes it about a population where the effect is documented, dense, and capacity-bearing.

---

## Why settled results (Steps 0–7) predict this might work

Every settled number is a prediction of the lottery hypothesis, and none of them was designed to test it:

| Settled observation | Lottery/attention reading |
|---|---|
| Step 2: h+1 −0.08%, h+5 −0.04% | Attention-driven buying pressure reverses (Barber–Odean) |
| Gate 1a: median excess −0.19 / −0.42 / −0.64% at h20/60/120, hit ≈49% | Typical member underperforms; positive skew |
| Gate 1a: mean +1.89% (t 5.30) but median negative | Textbook right-tailed lottery payoff |
| Phase 2: 2020 = **85.7%** of net profit | 2020–21 lottery mania (NBER w29543) |
| Phase 2: 2022 the only negative fold (−290.75) | Lottery demand collapses in the de-risking year |
| Gate 1a regime: 2021 h60 excess −6.74% (t −5.85) | Post-mania unwind of the same cohort |
| Phase 2: **104/200 trades forced-closed** by corporate action | The cohort is >50% corporate-action-terminated — a distress/lottery signature, not a normal equity population |
| Phase 2b S2: −102/trade vs matched SPY | Long-lottery loses to the index, as predicted |
| Step 3: Core ranking loses to naïve control OOS | An internally-fitted momentum composite carries no CS information; an external published characteristic is a different class of ranker |

The strongest version of this: **we have already run the long leg of the lottery trade for seven years and lost to SPY on a matched clock.** That is an unusually expensive and unusually clean confirmation of the mechanism's sign. NS proposes to stop paying for it.

---

## Why it might fail (steelman)

1. **The mega-cap MAX inversion, 2023–2025.** This is the sharpest risk and I will not soften it. In our window the highest-MAX *large* caps were the market leaders — a mechanical MAX5 screen would have excluded exactly the names that produced index returns in 2023–2025. The lottery premium is documented predominantly in small/illiquid names; strip those out for tradability and the surviving effect may be zero or negative in this window. **NS-2 can fail on this alone, and the failure would be honest and informative.**
2. **No PIT market cap in the stack.** `sharadar_tickers.py` requests only `ticker/exchange/category/firstpricedate/lastpricedate/isdelisted`. There is no size variable, so no NYSE breakpoints, no value-weighting, no size control. Hou–Xue–Zhang's critique lands directly: the effect may live entirely in sub-$50m names that 5bps does not describe. Dollar-volume weighting is a proxy, not a fix.
3. **Turnover.** A monthly max-return sort is reversal-adjacent and churns. Long-only reduces but does not remove the cost drag; NS-3 may die on turnover even if NS-2 passes cleanly.
4. **Seven years is a short time series.** ~84 monthly cross-sections and roughly 2–3 independent macro regimes. Deflated Sharpe on 84 observations is punishing, and 2023–2025 is no longer an untouched holdout (principle 7). We cannot produce a 20-year replication on this fixture; we can only ask whether a published effect survives *here, at our costs*.
5. **Crowding / decay.** Low-vol, quality and min-vol ETFs have absorbed hundreds of billions since 2011 and they are correlated with a lottery underweight. McLean–Pontiff's 58% post-publication decay is the bear case; Chen–Zimmermann's 10–15% shrinkage is the bull case; the honest position is that we do not know which applies to a screen this widely implemented.
6. **It is a tilt, not alpha.** Realistic long-only IR is ~0.2–0.4 before costs. Against a VWCE core position, that is a rounding error for a retail EU portfolio, and the research time may cost more than the tilt's lifetime value. **This is the argument that should govern the go/no-go, and NS-3's gate is written to force it.**

---

## Measurement plan

Ordered, cheapest-kill-first. Each stage is fully specified before the previous one runs.

### NS-0 — Re-benchmark Gate 1a to SPY (free, ~0.5 day, **no accept branch**)

Recompute the existing h20/h60/h120 event cohort's excess against SPY over the identical entry→exit windows, using `spy-opens-sidecar.json` (already committed for the autopsy) instead of the same-date eligible-universe mean.

*Freeze compliance:* this touches the Gate-1a diagnostic, not the portfolio residual, and it is **declared with no accept branch** — its only possible outcomes are "the residual is even deader than recorded" or "no change." A measurement that cannot green-light anything cannot re-open a frozen claim. If the record disagrees, drop NS-0; the rest of the program does not depend on it. Nothing downstream is conditioned on this result.

*Value:* it converts the apparent Gate 1a ↔ S2 contradiction into a benchmark statement, which is the piece of the record currently missing.

### NS-1 — Cohort characteristic census (~2 days, existing fixture, **the real kill gate**)

For each of the ~11.5k accepted events, and for the same-date eligible universe, compute at decision date: `MAX1`, `MAX5`, `IVOL` (residual σ vs SPY, 21d), realized skewness (21d), price level, trailing median dollar volume. Then:

- (a) cohort's cross-sectional percentile in MAX5 vs same-date universe;
- (b) Gate 1a h60 excess re-tabulated by *universe* MAX5 quintile, cohort-only and universe-wide;
- (c) tail decomposition — share of the +1.89% mean contributed by the top 1% of events;
- (d) share of the cohort in the top universe MAX5 quintile that was forced-closed (links the 104/200 fact to the characteristic).

Inference: date-clustered t (existing `clustered_t`), yearly folds reported.

### NS-2 — Universe-wide replication (~4 days, needs new CS simulator)

Monthly MAX5 quintile sorts on the liquid universe, 2019-01 → 2025-12, with Shumway delisting returns. Report EW and dollar-volume-weighted Q1−Q5 spreads, Fama–MacBeth with Newey–West lags, per-year fold signs, and the same statistics for the preregistered `IVOL` arm. **A power calculation is computed from NS-1's measured dispersion and published *before* NS-2 is funded** — if 84 months cannot detect the published effect size at α=0.05 with power ≥0.5, NS-2 is not run and the line is parked as untestable on this fixture. No number is assumed here.

### NS-3 — Long-only implementable book (~3 days)

Primary book vs matched SPY, 5 bps/side on turnover, monthly, pre-tax primary. Report turnover, after-cost annualized excess vs SPY, deflated Sharpe with trial count = 2 (MAX5 + IVOL) × 1 horizon × 1 weighting = 2 registered trials, per-entry-year share of net excess, and max drawdown vs SPY's.

### NS-4 — Capacity, tax and EU implementability (~1 day, only if NS-3 passes)

Number of names, minimum viable account size, EU/UCITS access to the required tickers, Revolut-tier commission reality, and the honest comparison against simply holding VWCE.

---

## Acceptance / rejection gates

All thresholds predeclared here; none may be moved after data is seen. The ~25% year-concentration rule is carried forward as research law (principle 9).

| Gate | Test | Pass | Fail action |
|---|---|---|---|
| **NS-0** | Gate 1a cohort h60 excess vs matched SPY | *informational only — no accept branch* | none; record and continue |
| **NS-1a** | Cohort median MAX5 percentile vs same-date universe | ≥ 80th | **Line dead.** Lottery is not the operative characteristic; publish and stop |
| **NS-1b** | Gate 1a h60 excess by universe MAX5 quintile | monotone-decreasing in MAX5 across ≥4 of 5 quintiles, clustered t ≥ 2.0 on Q1−Q5 | **Line dead.** Mechanism not identified in our data |
| **NS-1c** | Tail share | top 1% of events contribute ≥ 50% of the +1.89% mean | if < 50%, the "tail-driven" reading is wrong → re-derive before proceeding |
| **NS-1d** | Power calculation from NS-1 dispersion | power ≥ 0.5 at published effect size, α = 0.05, 84 months | **Park line as untestable on this fixture.** Do not build the simulator |
| **NS-2a** | Q1−Q5 MAX5 monthly spread, liquid universe | mean > 0, NW/clustered t ≥ 2.5 | **Line dead.** Publish replication failure |
| **NS-2b** | Sign stability | spread > 0 in ≥ 5 of 7 entry-years | **Line dead** |
| **NS-2c** | `IVOL` robustness arm | same sign as MAX5 arm | flag as fragile; NS-3 requires both to pass |
| **NS-3a** | Long-only book vs matched SPY, after 5 bps/side | annualized after-cost excess > 0 | **Stop. Publish "no implementable lottery tilt", recommend index-only** |
| **NS-3b** | Deflated Sharpe, 2 registered trials | > 0 | **Stop** |
| **NS-3c** | Year concentration of net excess vs SPY | no entry-year > 25% | **NO-GO on year concentration** — and unlike Phase 2, no autopsy: this line has a pre-agreed single-shot rule |
| **NS-3d** | Turnover | ≤ 25%/month one-way | **Stop** — cost-dominated |
| **NS-4** | Retail implementability vs VWCE | tilt's expected excess exceeds implementation friction | **Publish paper result; do not deploy capital** |

**Rejection is the modal outcome and is a success.** NS-1a/1b kills the line in ~2 days on data already in the repo, before the expensive simulator exists. That is the whole point of the ordering.

---

## Implementation cost on this repo

| Stage | Work | New data |
|---|---|---|
| NS-0 | New driver `fixtures/real-continuous/reports/research_ns0_spy_benchmark.py`; reuse `application/event_study_excess.py` + committed `spy-opens-sidecar.json` | none |
| NS-1 | New `domain/lottery_characteristics.py` (MAX1/MAX5/IVOL/realized skew vs SPY); new `application/characteristic_census.py`; driver + unit tests. Reuse the streaming bar loader and `clustered_t` | none |
| NS-2 | **New capability:** `application/cross_sectional_sort.py` — monthly formation calendar, quintile sorts, Fama–MacBeth + Newey–West, Shumway delisting returns from the ACTIONS adapter. This is the largest single cost and does not exist today (the engine is event-driven scanner + exit policy, not a rebalancing CS simulator) | none |
| NS-3 | Extend the CS simulator with the turnover cost model, matched-SPY benchmark, year-share and deflated-Sharpe reporting | none |
| Data audit | Sharadar **DAILY** table for PIT market cap (one new adapter, ~0.5 day + subscription check); add `sicsector`/`famaindustry` to `sharadar_tickers.py`'s `COLUMNS` tuple if the table exposes them — **verify, do not assume** | 1 table |
| Ops | Sequential multi-GB runs only, 16GB host; unit CI must stay free of fixture loads (same discipline as Phase 2) | — |

Total ≈ 2 weeks of engineering plus one bounded data-feasibility audit, with a hard kill available at day 2. Comparable engineering to Form-4 — but on data already in the repo, with a power calculation computable *before* the expensive stage, and without a new bitemporal tape as a prerequisite.

---

## Confidence and sharpest risk

**Confidence: 38 / 100** that NS reaches NS-3a with an after-cost positive excess vs SPY. Higher — call it **70** — that NS-1 produces a *decisive* verdict on whether lottery characteristics explain the entire Gate 1a / Phase 2 / S2 record, which is worth funding on its own regardless of the strategy outcome.

**Single sharpest risk:** the **mega-cap MAX inversion of 2023–2025**. In our seven-year window the highest-MAX large caps were the market leaders, so a tradable (liquidity-floored) MAX5 underweight may have the wrong sign in exactly the period we can test — and with 84 monthly observations we will not be able to distinguish "the effect decayed" from "our window is the exception."

---

## Attacks on the other two archetypes

### A) Form-4 opportunistic clusters — *highest opportunity cost, and it repeats the failure we just published*

The Round-1 meta-judge already ranked this an "engineering sinkhole" before a data audit. That verdict is now **stronger**, not weaker, because the cheap diagnostics have been spent and the next dollar is scarcer.

1. **It has the identical breadth pathology that just killed us.** Opportunistic insider *clusters* are rare events. A cluster-conditioned cohort in a 7-year window produces a few hundred events at best — the same order as Phase 2's n=200. Low breadth + heavy-tailed single-name returns → the realized book will be dominated by one or two years → **it will fail the same 25% year-concentration gate**, and we will have paid weeks of SEC plumbing to arrive at the NO-GO we already have. Anyone proposing Form-4 must publish an *expected-n and expected-year-share calculation first*. Nobody has.
2. **The identification variable is only reliably observable in a window too short to test.** The clean separation of routine from opportunistic is the 10b5-1 status. The SEC's amended Rule 10b5-1 and the accompanying Form-4 checkbox make that reliably machine-readable only from **2023**. That leaves ~2.5 years of clean sample inside our fixture span. Before that you must reconstruct "routine" from filing-date regularity heuristics — which is precisely the fragile, researcher-degrees-of-freedom-laden part of the design. The proposal's sharpest mechanism prediction is the one our data can least support.
3. **Post-SOX filing lag is 2 business days and EDGAR is the most-mined public feed in existence.** Cohen–Malloy–Pomorski's opportunistic-vs-routine spread was estimated on a pre-2008 sample. Whatever remains after two decades of commercial insider-data products is the entire empirical question, and Form-4 is exactly the famous, trivially-computable signal that post-publication decay hits hardest.
4. **Sequencing.** The audit is correct and mandatory, but the audit itself costs real time, and it can only *permit* the expensive work — it cannot make it powerful. NS-1 costs two days and can kill an entire hypothesis class.

**Verdict:** do not fund before (i) a PIT bitemporal feasibility audit *and* (ii) a published power calculation showing expected n and expected year-share. If either is missing, this is Phase 2 with a more expensive data bill.

### B) Rescue / rebrand the residual — *most dangerous archetype right now*

The freeze forbids it. That is not the interesting argument; here is the technical one.

1. **Every available knob selects on the tail.** More slots, drop-2020, vol-scaling, DAMB gating, ranking — each is evaluated against a sample whose median is negative and whose mean lives in a handful of names. Any structure change that improves the in-sample mean is, by construction, fitting the 2020 realization. With 200 trades and 7 folds, the effective sample size for *structure selection* is ~7. Choosing among even five structures on seven observations is not inference.
2. **A regime gate has ~2 degrees of freedom in this window.** DAMB-style SPY-200DMA gating is fitted to roughly two drawdown episodes (2020, 2022). A rule with two effective observations is a coin flip wearing risk-management clothing, and it will backtest beautifully because it was chosen after seeing both episodes.
3. **"The gate was too strict" is fitting a threshold to one observation.** The 25% year-share rule was predeclared. Rewriting it because 2020 came in at 85.7% is the single most common way research programs die of self-deception.
4. **I refuse the best rescue argument available to me, and it is mine.** W1 says the concentration failure is the *predicted* symptom of drawing 200 samples from a tail-driven distribution — which sounds like "run it with more slots." It is not, because W2 says the object breadth converges to (Gate 1a's cohort mean vs an equal-weight microcap universe) is not the object we would trade (excess vs SPY), and S2 already measured that at −102/trade. **Fixing the variance does not fix the benchmark.** If my own strongest rescue doesn't survive, nobody else's knob does.

**Why it is the most dangerous *now*:** Phase 2 produced a *green-looking headline* — n=200, mean +56.12, net +11,223, 6/7 folds > 0 — and failed only a governance gate. That is the perfect substrate for motivated reasoning, it costs zero marginal engineering to "just try one more thing," and the pull is strong enough that a formal freeze had to be written. Highest probability × highest overfit damage.

### C) Honest beta / passive — *correct as a decision, not a research program; dangerous in its TSMOM disguise*

1. **"Just own the index" is not a program.** It requires zero further research, and per the standing conclusion it is already the operating position. Spending a research budget to arrive at a conclusion you already hold is a way of feeling productive. If this is the answer, the correct action is to *stop the research program*, not to fund one that terminates there.
2. **The TSMOM version is archetype B in disguise.** Moskowitz–Ooi–Pedersen's evidence is futures-heavy and multi-decade; a single-market SPY trend overlay on 2019–2025 has ~2 independent trend episodes. It will show a gorgeous 2020 and 2022 drawdown dodge and a whipsawed 2023 re-entry, and someone will promote it on two events. Same degrees-of-freedom poverty as DAMB's regime gate, with better literature cover — which makes it *more* persuasive and therefore more dangerous.
3. **The one thing worth taking from C is its discipline, and NS takes it:** SPY on a matched clock is the benchmark in experiment one, not the afterthought it was until S2.

### Ranking the danger

| Rank | Archetype | Failure mode | Probability it actually happens |
|---:|---|---|---|
| 1 | **B — rescue the residual** | **overfit**; threshold-fitting to one year; ~7 effective observations | **High** — zero marginal cost, green headline, governance-only fail |
| 2 | **C — TSMOM overlay dressed as beta** | **false confidence via low effort**; 2 regime events | Medium — cheap and seductive |
| 3 | **A — Form-4** | **opportunity cost / engineering sink**; repeats the breadth pathology; identification variable clean only from 2023 | Medium — the Round-1 momentum points here |

C-as-pure-passive is not dangerous at all; it is the honest floor, and NS-4 is written so that "own VWCE" is a legitimate terminal state rather than an admission of failure.

---

## Final one-liner

I would bet the next research budget on **NS-1: the cohort characteristic census** — two days on data already in the repo, no new tape, no new engine — because it is the only experiment that can explain Gate 1a's PASS, Phase 2's 85.7% 2020 share, the negative median at every horizon, the 104/200 forced closes, and S2's −102/trade **under a single published mechanism**, and because it has a hard kill: **if the accepted-event cohort does not sit at or above the 80th percentile of same-date universe MAX5, or if Gate 1a's h60 excess is not monotone-decreasing in MAX5 quintile, the lottery line is dead before a single line of strategy code is written — and the correct next move is to stop, not to pivot.**
