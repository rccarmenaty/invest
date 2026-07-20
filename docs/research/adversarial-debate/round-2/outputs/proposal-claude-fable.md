# Proposal: Sell the Spike — cross-sectional short-horizon reversal as liquidity provision, dollar-neutral, on data already in the repo

**Judge:** Claude Fable (claude-fable)
**Round:** 2
**Date:** 2026-07-20
**Archetype:** new signal family on the *existing* tape — sign flip, horizon flip, and construction flip versus everything this program has tested. Not a continuation of the frozen residual.

---

## Thesis (1 paragraph)

Gate 1a PASS and Phase 2b DIE are not contradictory, and reading them jointly names the disease precisely: the event cohort has a **positive mean** universe-excess at h60 (+1.89%, t=5.30) with a **negative median** (−0.42%) and a **49.0% hit rate**, and the same book loses to its own trade-window SPY match by ~−102/trade after costs. That is the exact signature of a right-skewed, beta-and-lottery-loaded long-only payoff: the mean is bought with a thin right tail, the typical event *underperforms*, and a 20-slot lottery holding **n=200 trades over seven years** has no chance of sampling that tail reliably — which is why 85.7% of net profit landed in one calendar year. The concentration gate did not discover a risk problem; it discovered a **power problem**. My proposal refuses to keep buying right tails with 200 draws. It flips every axis of the failed object at once: **short horizon instead of 60 sessions, cross-sectional dollar-neutral instead of long-only, thousands of overlapping positions instead of 20 slots, negative-sign conditioning (buy the losers, sell the winners) instead of continuation, and central tendency (median) as a first-class gate instead of a mean.** The economic object is short-term reversal as compensation for **liquidity provision** (Nagel 2012), whose strongest documented conditioning state — high realized volatility / high selling pressure — is measurable from bars we already hold. And our own settled Step 2 numbers are the first weak corroboration: on the spike cohort, +1d mean is **−0.08%** and +5d is **−0.04%** *in a sample whose universe drifted strongly upward*, i.e. the short-horizon leg of our own event study was already leaning the way this proposal trades. The decisive property is not that I like the mechanism better; it is that this design produces roughly **350 weekly cross-sections × hundreds of names**, so for the first time in this program a negative result would be *statistically credible* rather than underpowered.

---

## Mechanism (why edge should exist economically)

Three stacked, separable mechanisms — each falsifiable on its own:

1. **Inventory risk and price pressure.** When uninformed liquidity demand (index flow, forced deleveraging, redemption-driven institutional selling) hits a name, market makers and opportunistic liquidity providers absorb the imbalance and must be compensated for inventory risk. That compensation shows up as a **transitory** price concession that reverts over days, not months (Hendershott–Menkveld estimate price-pressure half-lives on the order of days). Buying the extreme short-horizon losers and shorting the extreme winners is a mechanical way to sell that liquidity.

2. **The compensation is state-dependent and forecastable.** Nagel (2012) shows the return to reversal strategies is not a constant anomaly but rises sharply with the market's volatility state — liquidity providers withdraw when risk-bearing capacity is scarce, so the price of immediacy rises. This is the single most important design consequence: **the strategy should not always be on at the same gross.** A predeclared, single-variable exposure scaler on trailing realized vol is a mechanism implication, not a regime-gate rescue (and I hold myself to the same standard I used in Round 1 to condemn 200DMA gates — see the failure modes and Gate G5).

3. **Lottery demand explains the sign on the short leg specifically.** Bali–Cakici–Whitelaw show stocks with extreme maximum daily returns in the prior month earn **lower** subsequent returns: retail lottery preference bids up salient recent winners. Our scanner's accepted events *are* extreme positive daily moves — the MAX portfolio, essentially. That literature predicts precisely what we measured and never exploited: the typical spike name should *lag*, with a fat right tail that rescues the mean. Phase 2 bought the mean and got the concentration. This proposal takes the other side of the median.

A fourth, non-return mechanism drives the strategic choice: **the fundamental law of active management** (Grinold). Information ratio scales as IC × √breadth. Our settled program had a possibly-real but tiny IC applied at breadth ≈ 200 trades. No exit policy, ranker, or slot count can fix that arithmetic. Reversal is the highest-breadth object constructible from the tape we already own.

---

## Literature anchors

1. **Nagel, S. (2012), "Evaporating Liquidity," *RFS* 25(7):2005–2039** — [DOI:10.1093/rfs/hhs066](https://doi.org/10.1093/rfs/hhs066). Reversal-strategy returns are the return to liquidity provision and are strongly predictable by the market volatility state; the single anchor for both the mechanism and the exposure scaler.
2. **Lehmann, B. (1990), "Fads, Martingales, and Market Efficiency," *QJE* 105(1):1–28** — [DOI:10.2307/2937816](https://doi.org/10.2307/2937816). Original weekly contrarian result on the exact horizon and construction proposed here.
3. **Lo, A. & MacKinlay, A.C. (1990), "When Are Contrarian Profits Due to Stock Market Overreaction?," *RFS* 3(2):175–205** — [DOI:10.1093/rfs/3.2.175](https://doi.org/10.1093/rfs/3.2.175). Decomposes contrarian profit into own-autocovariance, cross-serial (lead-lag), and cross-sectional variance in means. Cited here as a **required kill test**, not as support: if our spread is lead-lag or mean-dispersion, it is not liquidity provision.
4. **Da, Z., Liu, Q., Schaumburg, E. (2014), "A Closer Look at the Short-Term Return Reversal," *Management Science* 60(3):658–674** — [DOI:10.1287/mnsc.2013.1766](https://doi.org/10.1287/mnsc.2013.1766). Reversal computed on **residual** (factor/industry-neutralized) returns is far stronger and far less contaminated by cross-sectional factor moves than raw reversal; defines the primary specification.
5. **Cheng, S., Hameed, A., Subrahmanyam, A., Titman, S. (2017), "Short-Term Reversals: The Effects of Past Returns and Institutional Exposure," *RFS* 30(2):658–693** — [DOI:10.1093/rfs/hhw057](https://doi.org/10.1093/rfs/hhw057). Reversals concentrate where the price move is attributable to non-informational institutional flow; supports conditioning on volume/flow proxies rather than on raw return magnitude alone.
6. **Novy-Marx, R. & Velikov, M. (2016), "A Taxonomy of Anomalies and Their Trading Costs," *RFS* 29(1):104–147** — [DOI:10.1093/rfs/hhv059](https://doi.org/10.1093/rfs/hhv059). The steelman kill: short-term reversal is among the **highest-turnover, highest-cost** anomalies and standard implementations have net alpha near zero. Cited as the primary rejection hypothesis, and the reason buffering/liquidity screens are in the primary spec rather than an afterthought.
7. **Bali, T., Cakici, N., Whitelaw, R. (2011), "Maxing Out: Stocks as Lotteries and the Cross-Section of Expected Returns," *JFE* 99(2):427–446** — [DOI:10.1016/j.jfineco.2010.08.014](https://doi.org/10.1016/j.jfineco.2010.08.014). Extreme-max-daily-return stocks subsequently underperform; the economics of the short leg and a direct explanation of Gate 1a's negative median.
8. **Grinold, R. (1989), "The Fundamental Law of Active Management," *JPM* 15(3):30–37** — [DOI:10.3905/jpm.1989.409211](https://doi.org/10.3905/jpm.1989.409211). IR = IC·√BR. The research-economics argument for abandoning a 200-trade book regardless of whether its IC is real.

Supporting method reference (not an edge claim): **Bailey, D. & López de Prado, M., "The Deflated Sharpe Ratio"** ([SSRN 2460551](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551)) — the multiple-testing correction owed on this fixture, counting every trial from Steps 0–7 forward.

---

## Concrete strategy design

**Name:** `xs-reversal-lp` (cross-sectional reversal / liquidity provision).

### Universe (deliberately narrow — the anti-mirage screen)
PIT-eligible US primary common stock from the existing TICKERS/ACTIONS context, plus a **hard liquidity floor applied on prior-session data only**: prior close ≥ $5 **and** 20-session median dollar volume ≥ $10M. Report the strategy on this liquid subset as **primary**. A second, more permissive tier (≥ $1M ADV) exists only as a diagnostic — if the edge lives only there, it is rejected, not celebrated (Novy-Marx–Velikov; Lakonishok–Lee's small-firm dependence is the standing lesson of every insider/anomaly study).

### Formation signal (one variable, predeclared, no grid)
At each weekly formation date *t* (last session of the ISO week):

- Raw formation return `r_i = close-to-close return over sessions t−4…t`, split/dividend adjusted from ACTIONS.
- **Residualization (primary spec, per Da–Liu–Schaumburg):** regress `r_i` cross-sectionally on (a) pre-formation 250-session beta to a universe-constructed market proxy, (b) log dollar-volume rank as a size proxy, (c) sector/industry dummies **only if** the context tape supplies PIT industry; otherwise omit and declare the omission. The signal is the cross-sectional residual `ε_i`.
- **Skip-day (mandatory, not optional):** formation ends at close of *t*; execution is at the open of *t+2*, skipping session *t+1* entirely. This is the standard defence against bid-ask bounce and one-day microstructure artifacts, which on daily close-to-close data are the single most likely source of a fake reversal edge — we have OHLC, not quotes, so we cannot correct bounce directly and must design it out.

### Portfolio construction
- Sort `ε_i` into deciles within the liquid subset on each formation date.
- **Long** bottom decile (largest negative residual), **short** top decile. Equal weight within leg, dollar-neutral across legs.
- **Hold 5 sessions**, exit at open. **Five overlapping books** (Jegadeesh–Titman overlapping design): each day one-fifth of gross is rolled. No stops, no take-profit, no trailing — the hold is fixed by construction, which is *why* the Kaminski–Lo / ±1R-coin-flip finding from Step 0/Step 2 cannot bite here.
- **No-trade buffer:** a name already held stays held if it remains within deciles 1–2 (long) / 9–10 (short). Buffering is in the **primary** spec, not a tuning knob, because turnover is the known kill vector.
- Caps: order notional ≤ 1% of prior-session median dollar volume; ≤ 2% of gross per name; gross ≤ 200% (100/100), no leverage beyond that.

### Exposure state scaler (exactly one, predeclared)
`gross_scale = clip(target_vol / realized_vol_20(market_proxy), 0.5, 1.5)` — inverse-vol *scaling*, not an on/off gate. Rationale: Nagel says compensation **rises** with vol, so a naive inverse-vol scaler *reduces* exposure exactly when payoff is highest. I therefore predeclare the **opposite-sign** variant as the primary — `gross_scale = clip(realized_vol_20 / target_vol, 0.5, 1.5)` — and report the inverse-vol variant as the single ablation. Two cells, declared in advance, both reported. If the result exists only under one of them, that is a **finding about the mechanism**, and if it exists only under a *tighter* state cut, it is a rejection (G5).

### Costs
5 bps/side primary; **10 and 25 bps/side stress mandatory**. The turnover arithmetic is deterministic from the design and must be stated up front rather than discovered later:

> Overlapping 5-day books roll ~1/5 of gross per session on each side. Absent buffering that is ~50× one-way gross turnover per year. At 5 bps/side on 200% gross, the design-implied cost hurdle is on the order of **several percent of capital per year**; at 25 bps/side it is multiples of any plausible gross spread.

This is the honest headline: **the hurdle is known before the first run, and it is large.** Buffering, the liquid-subset screen, and the ≤1%-ADV cap exist to cut it. If the gross spread cannot clear a 10 bps/side hurdle with buffering on, the line is dead and I will say so.

### Attribution (imported from every settled failure)
Every claim reported as: gross spread; net at 5/10/25 bps; **median** as well as mean; long-leg and short-leg separately (so a "reversal" edge that is really "short the MAX portfolio" is visible); correlation and regression alpha versus the market proxy; per-year and per-month decomposition; and the Lo–MacKinlay own-vs-cross-serial decomposition.

---

## How it differs from the settled Phase 2 residual and from Round 1 proposals

| Axis | Frozen Phase 2 residual | Round 1 Quiet Drift (mine) | Round 1 DAMB | Round 1 Form-4 | **xs-reversal-lp** |
|---|---|---|---|---|---|
| Sign of the bet | continuation | continuation | continuation | continuation | **reversal** |
| Horizon | 60 sessions | 60 sessions | 60–120 | 60 | **5 sessions** |
| Direction | long-only | long-only | long-only | long-only | **dollar-neutral L/S** |
| Breadth | 200 trades / 7 yrs | ~same | fewer (8 slots) | fewer (cluster scarcity) | **~350 weekly cross-sections × ~200 names/leg** |
| Benchmark risk | fails S2 vs SPY | unaddressed | market gate mints beta | unaddressed | **beta removed by construction; S2 is near-vacuous, replaced by G4** |
| Selection variable | none (lottery) | ID composite | 52wh + trend + breakout | insider cluster | **one residualized 5-day return** |
| New data required | none | none | none | **SEC ownership tape** | **none** |
| Dominant kill risk | concentration | beta | overfit knobs | filing-time decay | **transaction costs** |

**On the freeze.** The scope of the narrow freeze is the *naïve event → fixed-horizon → slot-lottery portfolio residual*. This proposal shares none of those three components: different event definition (no spike trigger at all — the primary sort is over the full liquid cross-section), different horizon, different admission, different sign, different exposure profile. The one place it *touches* the frozen cohort is a free corroboration probe (E1b below) — computing h1/h5 **excess** on the settled 12,295-signal cohort using the existing `event_study_excess.py`. I declare in advance that this probe is **non-decisive and off the accept path**: it cannot promote anything and it cannot revive the residual. If reviewers judge even that to be inside the freeze, drop E1b entirely; the program stands without it.

**Relationship to my own Round 1 seat.** Quiet Drift is dead and I am not smuggling it back. Its ranking feature (information discreteness) never cleared Gate 1b (q1−q5 spread +0.55pp, non-monotone), and Gate 1a's positive-mean/negative-median result retroactively explains why: on a spike-conditioned cohort, ID variation is truncated and the payoff is a tail, not a location shift. I am conceding my Round 1 thesis and taking the other side of it.

---

## Why settled results (Steps 0–7) predict this might work

- **Step 2 (+1d −0.08%, t=−1.01; +5d −0.04%, t=−0.31; hit 48.8%).** Raw, unhedged, in a sample where the eligible universe drifted strongly upward over 2019–2025. A raw ≈ 0 return against a rising universe implies a *negative* excess at h1/h5 on the spike cohort. That is not an alpha claim — it is unmeasured, and E1b measures it — but it is the first place in this entire program where the data leans the direction I want to trade.
- **Gate 1a (mean +1.89%, median −0.42%, hit 49.0%).** The mean/median gap is the diagnostic. It says the long-only object's *typical* member underperforms and a tail carries it. A dollar-neutral decile spread targets exactly the location parameter that is negative here, and my G2 makes **median > 0** a hard gate — a gate the settled program never had and would have failed at h20, h60 and h120.
- **Phase 2 concentration (2020 = 85.7%).** With n=200 and a tail-driven payoff, one-year dominance is the *expected* outcome, not an anomaly. Nothing about the structure was proven pathological; the sample was too small to be informative either way. High breadth is the only fix that is not a knob.
- **Phase 2b S2 (trade-window SPY excess ≈ −102).** This is the most important settled number in the whole program and it has one clean reading: **the long-only book was selling matched beta as alpha.** Dollar-neutral construction removes that failure mode by design rather than arguing with it. The corresponding test here is not S2 but G4 (|ρ| to market proxy and regression alpha) — a *harder* bar, since a market-neutral book has no beta to hide behind.
- **Step 3 (ranking loses to naïve control).** The lesson taken is "stop searching the momentum-composite family," and this proposal complies absolutely: one variable, one sign, opposite direction, defined ex ante, no composite, no grid.
- **Steps 0/1 (stops are a tax; FC profit is a policy artifact).** No stops exist here. And 5-session holds cut corporate-action and forced-close exposure by roughly an order of magnitude versus 60-session holds — FC contamination, which supplied 104 of Phase 2's 200 exits, becomes a rounding effect rather than the majority of the book.
- **Step 4 (fail-closed stale terminal opens).** Short holds sharply reduce the stale-terminal-open surface that invalidated the 2022–2025 matrix.

---

## Why it might fail (steelman opposition)

1. **Costs eat it. This is the modal outcome.** Novy-Marx–Velikov place short-term reversal at the top of the cost-mortality table; the design-implied hurdle above is several percent of capital per year at 5 bps and prohibitive at 25 bps. The most likely result is a real gross spread and a zero-to-negative net spread. My gates are built so that this outcome is a clean, fast rejection rather than a knob hunt.
2. **We cannot short, and borrow is unmodeled.** The engine is long-only. Worse, borrow cost and availability on the short leg are *not* in the tape at all, and the short leg is by construction the names that just spiked — historically the most expensive and most frequently hard-to-borrow. A dollar-neutral paper result that ignores borrow is a fiction. Mitigation is honesty plus the ≥$10M ADV floor; the long-only degenerate version (buy losers only) almost certainly dies to beta and is not the proposal.
3. **Bid-ask bounce manufactures reversal on daily closes.** With OHLC and no quotes, measured 5-day reversal on close-to-close returns is mechanically contaminated. The skip-day and open-to-open execution are the defence; if the edge disappears with the skip-day, it was microstructure, and that is a rejection.
4. **Lo–MacKinlay: it may be lead-lag, not own-reversal.** Contrarian profits decompose into own-autocovariance (what I claim), cross-serial covariance (large stocks leading small — a different, less tradeable phenomenon), and cross-sectional dispersion in mean returns (pure risk premia). If the decomposition attributes the spread to the second or third term, the liquidity-provision story is falsified even with a positive spread.
5. **Crowding and decay.** Weekly reversal is the most systematically farmed frequency in equity quant since the mid-2000s and sits adjacent to HFT inventory management. Our evidence window (2019–2025) is plausibly the *worst* era in the historical record for this trade. The published magnitudes are largely from earlier samples.
6. **Negative skew — the mirror of our current disease.** Liquidity provision is short volatility: many small wins, occasional violent losses. Being short the extreme recent winners is being short exactly the names that squeeze (Jan 2021 is in-sample and will punish the short leg hard). We would be trading a *symmetric-looking* strategy with a left tail, having just failed at one with a right tail. That is not obviously an improvement in capital terms and G6 exists to surface it.
7. **Year concentration can recur with a new face.** March 2020 was the largest liquidity-provision payday of the sample. If the entire net spread lives in Feb–Apr 2020, this is Phase 2's failure in a new costume and I have imported the ≤25% year gate plus a monthly gate to catch it (G3).
8. **The state scaler is a regime gate wearing a mechanism costume.** I attacked exactly this pattern in Round 1 (archetype C, "two effective independent regimes"). The scaler is continuous, single-variable, predeclared with its sign inverted-ablation, and cannot be tightened after seeing results — but if the edge exists **only** with the scaler on, G5 rejects it rather than shipping it.
9. **Sharadar SEP adjustment semantics.** If SEP prices are ex-post adjusted, then a mid-holding corporate action can leak information into a 5-day return in ways a 60-day study never noticed. E0 exists to fail closed on this before any economics.

---

## Measurement plan (ordered experiments, sample design, stats)

All inference date-clustered; overlapping holds require date-block / wild bootstrap, not iid t. All trials logged from Step 0 forward for the deflated-Sharpe correction. Sequential runs only (16 GB host).

**E0 — Data hygiene and adversarial placebo (blocking, ~1 day, no economics permitted before it passes).**
This is the experiment I would run first even if I were funding someone else's reversal idea, because unadjusted corporate actions are a **reversal-alpha factory**: an unadjusted 2:1 split reads as a −50% five-day return, lands in decile 1, and is "bought" the day before it mechanically recovers.
1. Rebuild the PIT liquid subset and the universe market proxy from SEP + ACTIONS + TICKERS; publish counts per year.
2. Inject synthetic splits/dividends into a fixture copy and verify the decile sort is unchanged.
3. Placebo: shuffle formation dates within each week and re-run E1; the spread must be indistinguishable from zero.
**Gate G0:** placebo spread |t| < 2 and synthetic-action injection produces no decile migration. Fail → fix the tape, no strategy runs.

**E1 — Pure cross-sectional decile study (no portfolio, no engine).**
Forward 5-session open-to-open return by formation-residual decile, weekly, liquid subset, 2019–2025. Report mean, **median**, hit rate, per-decile monotonicity, per-year, per-leg. Raw-return and residualized variants both reported (Da–Liu–Schaumburg predicts residualized is stronger; if raw is stronger, the "edge" is likely factor timing).
*E1b (optional, non-decisive, off the accept path):* h1/h5 excess-vs-universe on the settled Step-2 cohort via existing `event_study_excess.py`. Corroboration only. Cannot promote anything.

**E2 — Mechanism tests, not a kitchen sink.**
1. Lo–MacKinlay decomposition of the spread into own-autocovariance / cross-serial / mean-dispersion.
2. Nagel state test: spread by trailing-realized-vol tercile.
3. Cheng et al. flow test: spread conditioned on formation-window volume shock (predeclared: 5-day dollar volume vs 60-day median).
4. Skip-day ablation: 0-day vs 1-day skip. **A large gap is evidence of microstructure contamination, not of a better spec** — and the 1-day-skip version remains primary regardless of which is larger.

**E3 — Cost- and turnover-realistic portfolio replay (research-level accounting, still no engine change).**
Overlapping 5-book construction with buffering, ADV caps, weight caps, the two predeclared gross scalers. Net at 5/10/25 bps. Walk-forward: annual folds 2019…2025 **and** a weekly block bootstrap (the annual folds alone are 7 observations — the same low-power trap that produced the Phase 2 concentration verdict, so they are reported but are not the primary inference).

**E4 — Implementability audit (only if E3 clears).**
Short-side engine support scoping; borrow-cost sensitivity (flat 50/150/300 bps annualized on the short leg as declared stress); hard-to-borrow proxy; participation and no-fill assumptions. **A design that only works at zero borrow is rejected at E4, not renegotiated.**

**E5 — Full-family multiple-testing correction.**
Romano–Wolf / max-t stepdown across every cell reported in E1–E4 plus deflated Sharpe counting the entire fixture history from Step 0.

---

## Acceptance / rejection gates

Predeclared, frozen before E1 runs.

| ID | Gate | Threshold | Fail → |
|---|---|---|---|
| **G0** | Data placebo | shuffled-date spread \|t\| < 2; no decile migration under synthetic actions | fix tape; **no economics** |
| **G1** | Gross spread exists | bottom-minus-top decile 5-session spread > 0, date-clustered t ≥ **3.0**, residualized spec, liquid subset | **kill the line** |
| **G2** | Central tendency | **median** decile-spread > 0 (not just mean) | **kill the line** — this is the Gate-1a lesson made binding |
| **G3** | Distribution of profit | net-of-10-bps spread positive in ≥ 5/7 annual folds; **no single year > 25%** of net; **no single month > 20%** of net | **kill the line** — Phase 2's gate, imported unchanged |
| **G4** | Not beta | \|ρ\| to market proxy ≤ 0.3 **and** regression alpha vs (market, size proxy) > 0 with block-bootstrap CI excluding zero | **kill the line** (replaces S2, which is near-vacuous for a neutral book) |
| **G5** | Not a regime gate | spread survives **unscaled** (gross_scale ≡ 1) at t ≥ 2.0 | **kill the line** — edge that exists only under the state scaler is a two-regime fit |
| **G6** | Tail honesty | worst 5-session book loss and Jan-2021-window short-leg loss within predeclared limits; skew of the daily spread reported | escalate to explicit human sizing decision, not silent promotion |
| **G7** | Cost survival | positive net at **10 bps/side** with buffering; positive at 5 bps in the ≥$10M ADV tier | **kill the line** |
| **G8** | Multiple testing | deflated Sharpe > 0 across full trial family | **kill the line** |

**Standing rejection conditions (any one is terminal):**
- Edge exists only in the ≥$1M-ADV diagnostic tier and not the ≥$10M primary tier → small-cap mirage.
- Edge exists only without the skip-day → bid-ask bounce.
- Edge attributed by Lo–MacKinlay decomposition primarily to cross-serial or mean-dispersion terms → not liquidity provision.
- Edge exists only pre-cost or only at zero borrow.
- Edge concentrated in Feb–Apr 2020 → Phase 2's disease with a new face; **no leave-year rescue is permitted** (that move is exactly what K2 just killed).
- Any post-hoc change to decile cut, hold length, skip length, buffer width, liquidity floor, or scaler form after seeing E1 → the whole program reverts to archetype B and must be stopped.

**Note on what "pass" means.** Clearing G0–G8 promotes the line to an *implementability project*, not to capital. Gate 1a taught this program that a passed diagnostic is not a go-live.

---

## Implementation cost on this repo

**Low — and this is a first-order argument, not a footnote.** E0 through E3 require **no new data vendor, no engine change, and no shorting support**, because the portfolio is a research-level accounting object like `phase2_report.py`, not a `backtest_run` replay.

- **New:** `src/invest/application/cross_section_reversal.py` — pure functions: PIT liquid-subset selection, market/size proxy construction from the universe, cross-sectional residualization, decile assignment, overlapping-book accounting, turnover and cost ledger, buffer logic. Unit-testable with tiny synthetic frames; no multi-GB load in CI (same discipline as `tests/application/test_phase2_report.py`).
- **New:** `fixtures/real-continuous/reports/research_reversal.py` — driver emitting `reversal-decile.json` and `reversal-portfolio.json`, sequential single-fixture load, memory-bounded streaming reuse.
- **New:** `fixtures/real-continuous/reports/research_reversal_placebo.py` — E0 (shuffle + synthetic-action injection). Runs *first*.
- **Reused untouched:** streaming loader, PIT universe/ACTIONS handling, `event_study_excess.py` (E1b only), cost model, date-clustered inference helpers.
- **Engine work (E4 only, and only after E3 clears):** short-side position support in the domain/portfolio layer and a borrow-cost term. Scoped, not started.
- **Data needs: zero.** Compare to Form-4, whose entire critical path is a PIT tape that does not exist yet.

Rough shape: E0+E1 are days, not weeks. E2–E3 are the bulk. E4 is gated behind real evidence.

---

## Confidence (0–100) and single sharpest risk

**Confidence: 42.** Split deliberately: ~70 that a *gross* residualized 5-day reversal spread exists on the liquid subset at t ≥ 3 in 2019–2025 (the phenomenon is one of the most replicated in the literature and our own Step 2 h1/h5 numbers lean that way); ~35 that it survives G7 at 10 bps/side with buffering; ~25 that it survives G7 **and** realistic borrow at E4. The product is the number that matters.

**Sharpest risk:** **the cost/borrow scissors.** The spread is expected to be largest exactly where it is least tradeable — smaller, higher-spread, harder-to-borrow, higher-volatility names — and the liquid subset that makes it implementable is the subset where a decade of quant capital has already competed the compensation down. The honest modal outcome is "real gross, dead net," and I would rather buy that answer for a week of compute on data we already own than buy a maybe-answer for a month of SEC plumbing.

---

## Attacks on the other two archetypes

### A) Form-4 opportunistic clusters (Round 1 Codex Phase 3 as written)

I said in Round 1 that this was the best-designed proposal in the debate, and the design quality has not changed. What has changed is the **research budget context**, and that reverses my ranking of it.

1. **Its critical path is entirely non-informative.** Weeks of ingestion, bitemporal `known_time` modelling, Form 4/A amendment semantics, CIK-to-share-class linkage, delisting terminal economics — and at the end of all of it you have produced **zero** evidence about whether an edge exists. Every hour is spent before the first falsifiable number. That is the definition of an engineering sink, and on a single 16 GB sequential-compute host it is the entire budget.
2. **The data gate is likely to fail on its own terms.** The proposal itself requires ≥95% reconciliation to immutable source filings, zero retrospective amendment rewrites, and explicit terminal economics for every inactive security. Sharadar's insider table — if entitled at all, which is unproven in this repo — is a vendor product whose amendment and as-known-then semantics are exactly what such a gate is designed to reject. The most probable outcome is a month of work terminating at "reject the dataset."
3. **The mechanism's clock has moved.** The canonical evidence (Lakonishok–Lee 2001; Jeng–Metrick–Zeckhauser 2003; Cohen–Malloy–Pomorski 2012) is overwhelmingly pre-2010 and largely measures returns from *insider execution*. Post-SOX two-day filing plus a decade of commercial Form-4 feeds means the outsider's next-open clock is the crowded one. Codex named this risk honestly and still scored 63; that confidence was not earned by any measurement.
4. **Cluster scarcity recreates the exact failure we just published.** Two distinct opportunistic buyers, ≥3 years of classification history, a 10-session window, a $5M liquidity floor, one event per issuer per 60 sessions — this yields a **small** event count. Small n, 60-session holds, 20 slots, long-only, right-skewed payoffs: that is Phase 2's shape, feature for feature. We have a published, binding result about what happens to that shape, and Form-4 would rediscover it after paying for a data tape. If the strongest objection to my proposal is costs, the strongest objection to Form-4 is that **it cannot clear the year-concentration gate that just killed Phase 2**, and nobody has shown it can.
5. **It also owes S2.** A long-only 60-session insider book must beat trade-window-matched SPY after costs. Phase 2b established that bar empirically on this stack. Form-4 as written measures factor-adjusted alpha but never confronts the specific matched-clock benchmark that just produced −102/trade here.

Form-4 is not wrong. It is **expensive, slow, structurally identical to the thing that just failed, and unfalsifiable for weeks.** Fund it after a cheap high-breadth test has either produced signal or exhausted the free data.

### B) Rescue / rebrand the residual price events

This is intellectually the weakest and I will not spend much on it, because the freeze already names every move it can make: structure tweaks, a second autopsy, ranking, vol-scaling the same book, DAMB modules bolted on, "just drop 2020," or rewriting the ~25% gate. Three points:

1. **K2/S2 did not merely fail — they failed in the two ways that admit no repair.** Leave-2020 mean (9.44) is not merely below half the full-book mean (28.06); it is a book whose central economics collapse when one year is removed. And S2 (−102/trade) says the *realized* book lost to matched equity on its own clock. There is no knob whose adjustment makes a matched-beta loss into alpha; you would have to change the benchmark, which is fraud with extra steps.
2. **Ranking cannot rescue n=200.** Gate 1b already failed (q1−q5 = +0.55pp, non-monotone). Even a genuinely informative ranker applied to 200 draws from a tail-driven distribution produces a result dominated by which draws you got. Grinold's arithmetic is not negotiable by feature engineering.
3. **The specific rhetorical danger** is that Gate 1a PASS is a *very* quotable number (t=5.30) and will keep tempting people to say "but the residual is real." It is real **and** unbankable — mean-positive, median-negative, tail-borne, beta-matched-negative. Those are compatible facts and this program has now paid to learn all four. Anyone re-opening this line owes a *new named hypothesis with its own PRD*, and "the drift exists" is not a hypothesis, it is a settled measurement.

### C) Honest beta / passive

C is not dangerous — it is **correct as a terminal state and wrong as a research program**, and conflating those two is the error.

1. **Productizing SPY/IWM consumes no research budget.** It is a decision, executable in an afternoon, requiring no fixture, no gates, no debate. Presenting it as a "next research program" is a category error: there is nothing to measure. If the answer is "buy the index," the correct artifact is a one-page written stop, not a work plan.
2. **The TSMOM variant is a different and unfunded claim.** The trend-following evidence that survives costs (Moskowitz–Ooi–Pedersen; Hurst–Ooi–Pedersen) is overwhelmingly **liquid futures across asset classes**. Single-name US equity TSMOM after costs is precisely the debt DAMB never paid in Round 1, and running it on this fixture would be a fresh multiple-testing exercise on a burned holdout with ~2 effective regime episodes. That is archetype C's old disease, not honest beta.
3. **Its real hazard is emotional, not statistical:** after a NO-GO and a DIE, "let's just do honest beta" is the face-saving exit that *feels* like maturity while contributing zero new information — and it forecloses the one genuinely cheap, high-breadth, never-tested direction still available on data we already own.

### Which is most dangerous *now*

**A (Form-4) — on opportunity cost.**

Ranked by damage per unit of remaining budget:

1. **A — engineering sink + false confidence.** Highest expected spend, latest falsification, and a design whose portfolio shape (small n, long-only, 60-session, 20 slots, skewed) is the *same shape* the concentration gate just rejected. Worse, if the tape gets built, sunk cost will argue loudly for relaxing the cluster definition to get n up — the classic p-hacking route, pre-identified by Codex itself as failure mode 6.
2. **B — false confidence, currently well-contained.** It would be the most dangerous archetype if the freeze were soft. The freeze is hard and event-only, so its threat is latent rather than active. It becomes #1 the moment anyone quotes t=5.30 without the median.
3. **C — opportunity cost only.** Safe, honest, and the right terminal answer if my G1/G7 fail. Its only sin is arriving early.

Reordering versus my Round 1 danger ranking (C > A > B) is deliberate and evidence-driven: in Round 1, no measurement existed and the danger was overfitting; now the measurements exist, they were expensive, and the danger is **spending the remainder of the budget without generating another falsifiable number.**

---

## Final one-liner

I would bet the entire remaining research budget on **one week of compute against data we already own**: build the PIT liquid subset, residualize 5-day returns cross-sectionally, skip a day, and measure the decile spread over ~350 weekly cross-sections — and I would kill the whole line on the spot if the **median** spread is not positive with date-clustered t ≥ 3.0 gross, or if the net spread cannot clear **10 bps/side** with buffering on, because that single experiment costs less than the Form-4 data audit's first day and, unlike anything this program has run so far, it has the breadth to make a negative result actually mean something.
