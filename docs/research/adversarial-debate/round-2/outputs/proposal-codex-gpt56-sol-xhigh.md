# Corroborated Fundamental Surprise: Test Revenue-Confirmed Earnings Drift, Then Stop If the Modern Liquid Null Wins

## Thesis (1 paragraph)

The next research dollar should leave the frozen price-event residual completely and test one narrower, higher-information claim: **after both GAAP earnings and revenue arrive materially above their own point-in-time seasonal histories, liquid US common stocks continue to earn positive abnormal returns from the first unquestionably tradable open through session 60**. This is not generic post-earnings-announcement drift (PEAD), not an analyst-consensus fantasy built from revised data, and not a price-momentum rescue. It is a preregistered **corroboration** hypothesis: an earnings innovation is more persistent when top-line news points the same way, so investors who react mainly to the headline earnings number may still underweight the joint implication. The proposal begins with a data-feasibility and modern-null gate, uses original-as-published revenue and diluted GAAP EPS with a bitemporal `known_time`, admits every qualifying event in a position-blind study, enters only at the next certainly available open, and requires positive median abnormal return, liquid-sample economics, matched-SPY outperformance, fold breadth, and the existing year-concentration limit. If the first event study reproduces the published finding that modern liquid-stock PEAD has disappeared, the line ends; no Friday filter, guidance NLP, analyst-revision add-on, or threshold retuning follows.

## Mechanism (why edge should exist economically)

The economic object is a **new fundamental innovation**, not continuation inferred from an old price path.

1. **Earnings news is persistent but cognitively compressed.** Investors must map a quarterly innovation into a multi-period earnings process. Bernard and Thomas' mechanism is delayed recognition of the serial implications of earnings, not a claim that every positive-return stock keeps rising.
2. **Revenue corroborates persistence.** Equal earnings surprises need not have equal quality. Earnings growth accompanied by revenue growth is harder to manufacture through expense timing alone and has stronger implications for future operating performance. Jegadeesh and Livnat predict a strict ordering: concordant revenue-and-earnings surprises should drift more than earnings surprises without revenue confirmation.
3. **Attention is finite.** Complex, joint information can be incorporated more slowly than a salient headline. DellaVigna and Pollet supply a behavioral mechanism for delayed response, but announcement weekday is an attribution variable only; it is forbidden as a selection filter in this program.
4. **The counter-mechanism is strong and must be allowed to win.** Modern price discovery may already absorb both signals immediately. Martineau reports that PEAD disappeared in large stocks, while Chordia et al. show that historical paper profits were concentrated in illiquid names and largely consumed by trading costs. Therefore liquidity and next-open timing are kill gates, not post hoc robustness checks.
5. **Why this is preferable to another price feature.** Novy-Marx argues that earnings momentum can subsume price momentum. The settled project evidence says price ranking adds no clear value and the residual price-event portfolio loses to matched SPY. Moving upstream to the fundamental innovation is therefore a coherent change of information source, whereas ID, 52-week-high, breakout, regime, and volatility overlays remain transformations of the failed object.

The hypothesis makes falsifiable mechanism predictions: double-positive events must beat EPS-only positive events; the negative mirror must have the opposite sign; the effect must be monotone across frozen joint-surprise bins; and all of this must survive public-time execution, liquid names, abnormal-return controls, and modern years. A green raw long-only mean without those orderings is beta or luck, not corroborated fundamental drift.

## Literature anchors (3–8 citations with arXiv/DOI/URL + one-line relevance)

1. Bernard, V. L., and Thomas, J. K. (1989), “Post-Earnings-Announcement Drift: Delayed Price Response or Risk Premium?”, *Journal of Accounting Research* 27, 1–36, [DOI 10.2307/2491062](https://doi.org/10.2307/2491062) — establishes the delayed-response mechanism and the canonical 60-session research horizon.
2. Livnat, J., and Mendenhall, R. R. (2006), “Comparing the Post–Earnings Announcement Drift for Surprises Calculated from Analyst and Time Series Forecasts,” *Journal of Accounting Research* 44, 177–205, [DOI 10.1111/j.1475-679X.2006.00196.x](https://doi.org/10.1111/j.1475-679X.2006.00196.x) — shows time-series surprises are weaker than analyst-based surprises, an explicit warning against overstating a vendor-free design.
3. Jegadeesh, N., and Livnat, J. (2006), “Revenue Surprises and Stock Returns,” *Journal of Accounting and Economics* 41, 147–171, [DOI 10.1016/j.jacceco.2005.10.003](https://doi.org/10.1016/j.jacceco.2005.10.003) — revenue surprises contain incremental information and identify more persistent earnings growth.
4. Jegadeesh, N., and Livnat, J. (2006), “Post-Earnings-Announcement Drift: The Role of Revenue Surprises,” *Financial Analysts Journal* 62(2), 22–34, [DOI 10.2469/faj.v62.n2.4081](https://doi.org/10.2469/faj.v62.n2.4081) — directly motivates the concordant revenue-plus-earnings contrast rather than generic PEAD.
5. DellaVigna, S., and Pollet, J. M. (2009), “Investor Inattention and Friday Earnings Announcements,” *Journal of Finance* 64, 709–749, [DOI 10.1111/j.1540-6261.2009.01447.x](https://doi.org/10.1111/j.1540-6261.2009.01447.x) — supplies a limited-attention mechanism; weekday remains diagnostic, not a tradable filter.
6. Chordia, T., Goyal, A., Sadka, G., Sadka, R., and Shivakumar, L. (2009), “Liquidity and the Post-Earnings-Announcement Drift,” *Financial Analysts Journal* 65(4), 18–32, [DOI 10.2469/faj.v65.n4.3](https://doi.org/10.2469/faj.v65.n4.3) — finds the anomaly concentrated in illiquid stocks and estimates that costs consume most paper profits, making the liquid subset a primary gate.
7. Martineau, C. (2022), “Rest in Peace Post-Earnings Announcement Drift,” *Critical Finance Review* 11, 613–646, [DOI 10.1561/104.00000122](https://doi.org/10.1561/104.00000122) — the strongest hostile prior: modern large-stock PEAD may already be zero, so a failure is the expected clean stopping outcome.
8. Novy-Marx, R. (2015), “Fundamentally, Momentum is Fundamental Momentum,” NBER Working Paper 20984, [DOI 10.3386/w20984](https://doi.org/10.3386/w20984) — earnings innovations can subsume price momentum, supporting a move upstream from the failed price-ranking family.

## Concrete strategy design (entries, ranking, exits, portfolio, costs assumptions)

This is the deployable specification **only if** the position-blind signal gates pass. No portfolio code is justified before then.

**Data-time contract.** For each issuer-quarter, preserve every original filing/release version. `valid_time` is the fiscal period; `known_time` is the earliest verified public timestamp at which both the reported revenue and diluted GAAP EPS values were observable. A later 10-Q, 10-Q/A, restatement, taxonomy correction, or vendor refresh is a prospective version, never a rewrite of the original observation. If the source has only a calendar date and no reliable intraday timestamp, entry waits until the second regular-session open after that date. Ambiguous units, unstable XBRL tag lineage, duplicate fiscal periods, current-ticker mappings, or inconsistent splits quarantine the event.

**Fundamental innovations.** Using only values known before the event:

- `E_SUE = (EPS_q - EPS_{q-4}) / sd(EPS_j - EPS_{j-4})` over the previous eight eligible quarterly changes.
- `R_SUE = (REV_q - REV_{q-4}) / sd(REV_j - REV_{j-4})` over the previous eight eligible quarterly changes.
- Zero denominators, fewer than eight prior comparable changes, unit discontinuities, or non-comparable fiscal-period transitions produce no event; they are not imputed.

The **primary positive event** is `E_SUE >= +1` and `R_SUE >= +1`. The **negative mirror** is `E_SUE <= -1` and `R_SUE <= -1`; it is a mechanism diagnostic, not a live short strategy. EPS-only controls have `|E_SUE| >= 1` while revenue is neutral or opposite. Thresholds and definitions are frozen once, not searched.

**Universe.** Period-valid US primary common stocks; prior-session close at least $5; prior-20-session median dollar volume at least $10 million; complete PIT market context and terminal economics. An order may not exceed 1% of that prior median dollar volume. Depositary receipts, funds, OTC securities, ambiguous share classes, and events without stable quarterly comparability are excluded.

**Entry.** Buy at the first regular-session open strictly after `known_time` when exact availability is proven. Apply the conservative second-open rule for date-only sources. No filing-close, transaction-date, prior-close, or synthetic fill is admissible. If the open is absent or halted, follow a deterministic no-fill rule.

**Ranking.** None. Every primary event enters the position-blind event study. If portfolio slots bind, use the existing seeded random-admission control; do not rank by surprise magnitude, announcement gap, weekday, momentum, liquidity beyond the fixed floor, analyst coverage, or sentiment.

**Exit.** Open of the 60th completed trading session after entry. No price stop, take-profit, ATR trail, channel, or regime-triggered liquidation. Horizons 20 and 120 are preregistered diagnostics in the same multiple-testing family and can never replace h60 as the accept path. A subsequent quarterly announcement does not reset or pyramid the position.

**Portfolio.** Long-only; at most 20 concurrent issuers; equal 5% notional per admitted position; 100% gross cap; no leverage; one active position per issuer. Slot contention is seeded random. Report the uncapped equal-event book first, then the capacity-constrained book. Inverse-volatility sizing is deliberately absent from the primary test because it would add another transformation before signal proof.

**Costs and benchmarks.** Primary results are pre-tax after 5 bps per side; stress 10 and 25 bps. Tax is secondary. Each trade is compared with raw SPY open-to-open P&L on identical notional and identical dates, matching the settled S2 clock. Primary abnormal return is also measured against a same-date eligible-universe industry-and-size match formed without future information. Report the realized opening gap separately; never subtract it from the signal merely because it is inconvenient.

**Corporate actions.** Use actual merger, cash-out, delisting, or liquidation economics. Policy/context forced closes are excluded from the alpha claim and reported separately. Missing terminal economics invalidates the affected run; it cannot be patched with the last observed close.

## How it differs from settled Phase 2 residual and from Round 1 proposals

| Dimension | Settled Phase 2 residual | Quiet Drift / DAMB | Round 1 Form-4 | This proposal |
| --- | --- | --- | --- | --- |
| Information source | Naïve price spike | Price path, ID, 52w high, trend/regime | Insider ownership filing | **Original revenue + GAAP EPS innovation** |
| Frozen claim reused? | The frozen claim itself | Would repackage the frozen family if continued now | New line | **New line** |
| Selection/ranking | No rank, slot lottery | ID or absolute-momentum layers | Opportunistic cluster and buyer-count mechanics | **Fixed joint surprise; no portfolio rank** |
| Primary proof | Portfolio residual | Price-event cohort/portfolio | Filing-time cluster event study | **Public-time fundamental event study** |
| Timing hazard | Next-open price event | Same | Transaction vs Form-4 acceptance | **Release/filing known-time vs restatement** |
| Data burden | Already built | Low | High: insider identity, code P, history classifier | **Medium-high, but higher-frequency and structured** |

Reusing fixed-horizon execution, seeded random admission, market context, costs, and report helpers does **not** continue Phase 2. The event cohort, economic mechanism, data contract, and acceptance evidence are different. The narrow freeze remains intact: no naïve-spike event, ID, 52-week-high, breakout, volatility, or market-gate result can rescue or count toward this proposal.

Compared with Quiet Drift, this does not pretend DGW information discreteness survived Gate 1b; Gate 1a's ID spread was weak and Phase 2b later killed portfolio residual hope. Compared with DAMB, it refuses to turn beta management into signal discovery. Compared with Form-4, it sacrifices the stronger “costly insider action” story for a denser event sample, simpler issuer mapping, no three-year insider classifier, and a faster signal kill. Form-4 remains a possible later new line, not a Phase 3 entitlement.

## Why settled results (Steps 0–7) predict this might work

**Step 0 — first continuous Core failure.** Core's uncapped PF below one and cost-sensitive stop churn say that a better chassis cannot create information. This proposal changes the information input and avoids short-path exits.

**Step 1 — forced-close audit.** FC profit was a policy artifact. Fundamental events are especially exposed to distress and inactive names, so actual terminal economics and FC-segregated attribution are admission conditions, not cleanup.

**Step 2 — signal event study.** The old cohort had negligible +1/+5-day behavior, later raw drift, thin h20 cross-sectional excess, and a coin-flip ATR race. That predicts no price stop here, but it does **not** prove earnings drift. The useful inference is narrower: if delayed response exists, diagnose it position-blind at a slow horizon before portfolio work.

**Step 3 — Core versus naïve.** Sophisticated price ranking lost to the no-rank control. This proposal has no price rank and uses random admission when capacity binds. Joint surprise is the event definition demanded by the mechanism, not a capital-allocation score optimized on returns.

**Step 4 — corrected matrix.** Stale terminal opens invalidated multi-year P&L. The new tape must carry explicit availability and terminal outcomes and must fail closed on absent price coverage.

**Step 5 — Gate 1a PASS.** The old event cohort's h60 mean excess was positive, but hit rate was below 50% and median excess was negative. That is evidence against accepting another right-tail mean. This program requires a positive median abnormal return and mechanism ordering in addition to a positive mean.

**Step 6 — Phase 2 NO-GO.** Six of seven positive annual folds did not excuse 2020 supplying 85.7% of net profit. The same approximately 25% maximum-year share remains a hard promotion gate here; no “pandemic was special” waiver exists.

**Step 7 — residual_hope DIE.** Leaving 2020 reduced expectancy below half the full book, and matched-window SPY excess was negative. Therefore any new long-only event line must beat matched SPY on the same clock and remain economically material without its best year. A green raw book is insufficient.

The joint evidence does not say “hold longer.” It says a mean residual existed, but the tradable residual was right-tail, concentrated, and not superior to matched beta. A more defensible next hypothesis must introduce information with a predicted cross-sectional sign and must clear harder breadth and benchmark gates. Corroborated fundamental surprise does exactly that; it may still die quickly.

## Why it might fail (steelman opposition)

1. **Modern PEAD may be dead.** Martineau's result is devastating: large-stock surprises may be incorporated on announcement day. The proposed next-open h60 return can be exactly zero even if old papers were correct.
2. **Tradability and statistical significance may be mutually exclusive.** Chordia et al. imply the residual may live only in names excluded by the liquidity floor or consumed by spread and impact. Relaxing the floor after failure would be p-hacking.
3. **Time-series SUE is an inferior expectation model.** Livnat and Mendenhall show analyst-based surprise is stronger. Historical seasonal changes may misclassify expected growth, structural breaks, and pandemic base effects. The absence of PIT consensus data is a real information disadvantage, not a reason to smuggle in current consensus history.
4. **Revenue confirmation may be stale or redundant.** Modern investors and machines ingest revenue simultaneously with EPS. The EPS-only versus double-positive spread may be zero even if both groups have positive beta.
5. **GAAP taxonomy is not economically uniform.** Acquisitions, divestitures, fiscal-year changes, split-adjusted EPS, restatements, and issuer-specific XBRL tags can create synthetic “surprises.” A loose normalizer would manufacture alpha.
6. **Publication time can be unknowable from vendor rows.** A `datekey` is not necessarily the earliest public earnings timestamp. Using revised vendor fundamentals or a day-level field can leak the result by one or more sessions.
7. **The 2019–2025 market window is still regime-poor.** Thousands of events do not create thousands of independent macro regimes. If older event-time price/context coverage cannot produce at least ten annual test folds after warmup, the program should stop rather than pretend event count cures year dependence.
8. **No price stop admits gap and bankruptcy risk.** Equal notional and a 5% issuer cap bound but do not remove single-name loss. That tail must appear in the result; excluding it would repeat FC contamination.
9. **The positive side may not be symmetric.** Negative surprise drift can be stronger because of short-sale constraints, while the long positive side is efficiently priced. The mirror can validate the academic mechanism while leaving no deployable long strategy.
10. **Corroboration can become a feature factory.** Guidance, analyst revisions, cash flow, accruals, weekday, call tone, and announcement gap are obvious follow-ons. They are explicitly forbidden after a failed primary gate; otherwise this becomes ranking overhaul in accounting clothing.

## Measurement plan (ordered experiments, sample design, stats)

**F0 — Freeze the claim and trial ledger before return extraction.** Record the exact original-value semantics, tag mapping, seasonal standardization, ±1 thresholds, liquidity floor, next-open rule, h60 primary horizon, controls, costs, annual folds, and all gates. Every diagnostic and failed attempt enters one trial ledger.

**F1 — Data-feasibility kill, no alpha code.** Audit whether the available Sharadar entitlement or raw SEC filings can provide original-as-published quarterly revenue, diluted GAAP EPS, exact public availability, filing versions, stable issuer/share-class mapping, and inactive-security outcomes. Reconcile a stratified sample against immutable source filings, including after-hours releases, 8-K/10-Q ordering, amendments, split adjustments, fiscal-year changes, and tag changes. Require enough history for eight prior seasonal changes and at least ten completed annual test folds. If exact known-time and original values cannot be reconstructed, stop.

**F2 — Build an immutable research tape.** One row per issuer-quarter version with `valid_time`, `known_time`, source accession/vendor key, original values, units, taxonomy lineage, security mapping, eligibility, and quarantine reason. Later versions append; they never mutate an earlier row. Publish coverage and rejection counts before looking at returns.

**F3 — Position-blind event study.** On all qualifying positive, negative, EPS-only, and neutral-control events, measure next-open-to-open returns at +1, +5, +20, +60, and +120 sessions. h60 double-positive is the sole primary hypothesis. Report raw after-cost return, same-date eligible-universe excess, industry-size matched abnormal return, matched-SPY trade-window excess, mean, median, hit rate, and opening gap. Cluster by issuer and availability date; use availability-week blocks/wild cluster bootstrap for overlapping horizons.

**F4 — Mechanism contrasts.** Predeclare and test: double-positive > EPS-only positive; double-negative < EPS-only negative; ordered joint-surprise bins; and positive versus shuffled-within-issuer-quarter placebo dates. Announcement weekday, price momentum, analyst coverage, and gap size are attribution tables only. They cannot select events.

**F5 — Walk-forward and concentration.** Compute each event's standardization using prior published quarters only. Use expanding-origin annual folds; treat 2023–2025 as burned walk-forward data, never a fresh holdout. Report every year, leave-each-year-out mean/median, maximum year profit share, issuer jackknife, liquid-subset results, and the worst fold. Preserve a genuinely future period after protocol freeze.

**F6 — Multiple-testing correction.** Apply Romano–Wolf/max-t or an equivalent dependence-aware family-wise procedure to all surprise signs, controls, and horizons. The historical project trial ledger remains disclosed; portfolio variants later feed the Deflated Sharpe Ratio. A single nominal t-stat cannot promote the line.

**F7 — Portfolio replay only after F1–F6 pass.** Run the exact long-only design under uncapped equal-event and 20-slot seeded-random books. Compare with SPY on the identical capital clock and with a random sample of all eligible quarterly announcers under the same hold/cost mechanics. Run full fixtures sequentially on the 16 GB host.

**F8 — One bounded robustness pass.** Stress only costs {5, 10, 25 bps} and liquidity floors {$10 million, $25 million prior median dollar volume}. These are deployability cells, all reported, not an optimizer. No alternate surprise threshold, horizon, sizing rule, ranking, regime gate, or NLP layer is permitted.

## Acceptance / rejection gates

**Data gate — all required before returns count:**

- Original-as-published revenue and diluted GAAP EPS are reconstructable without retrospective overwrite.
- Exact `known_time` is proven, or the conservative second-open date-only rule is used.
- Zero detected lookahead, current-identifier leakage, silent unit changes, or amendment rewrites in the audited sample.
- Every included event has a unique period-valid listed security and complete terminal economics.
- At least ten annual test folds exist after the eight-change warmup. If not, reject the program as underidentified by regimes.

**Signal gate — all required on the frozen h60 double-positive event:**

- Next-open, 5-bps-per-side industry-size matched abnormal **mean > 0**, with family-wise-adjusted 95% confidence interval excluding zero.
- **Median abnormal return > 0** and hit rate above 50%; a Gate-1a-style positive mean with negative median fails.
- Double-positive abnormal return exceeds EPS-only positive abnormal return under the same timing, liquidity, and matching rules; the negative mirror points oppositely.
- Matched-SPY trade-window excess is positive after strategy costs.
- A majority of annual walk-forward folds are positive; no calendar year supplies more than approximately 25% of equal-notional after-cost net profit; leave-best-year mean remains economically material rather than merely above zero.
- The result survives the $25 million liquidity subset and remains non-negative at 10 bps per side.

**Portfolio gate — all required before paper trading:**

- Positive pre-tax after-cost expectancy in a majority of annual folds for both uncapped equal-event and 20-slot random-admission books.
- Full-sample PF at least 1.10 at both 5 and 10 bps per side, with no single-year concentration breach.
- Capacity-constrained P&L beats matched-clock SPY and the all-announcer random control on risk-adjusted and dollar terms.
- FC-segregated results still satisfy the signal and portfolio gates; no policy forced-close profit enters the claim.
- Deflated Sharpe is positive after counting every fundamental-surprise portfolio variant actually tried.

**Immediate rejection conditions:** alpha only at filing close or transaction date; only in microcaps/illiquid names; only before costs; only in the mean; only in 2020; only at h20 or h120; only after using revised fundamentals/current identifiers; no revenue-confirmation spread; matched SPY not beaten; or dependence on FC exits. On rejection, publish the null and terminate the line. Do **not** add analyst consensus, guidance, call text, Friday, gap, quality, accrual, momentum, regime, or volatility filters as rescue.

## Implementation cost on this repo (files / new modules / data needs)

**Overall: medium-high, but staged so the cheap audit can prevent the expensive build.** The repo currently proves Sharadar `SEP + ACTIONS + TICKERS`, not a PIT fundamental-release tape. That missing contract is the work.

**F0–F1: low cost, research-only.** Add a protocol/audit report under `docs/research/` and a disposable probe under `fixtures/real-continuous/reports/`. Verify Sharadar SF1 entitlement/semantics against SEC 8-K/10-Q acceptance metadata before touching domain or trading code.

**F2–F6: medium-high cost if the audit passes.** Likely additions:

- `src/invest/adapters/sharadar_fundamentals.py` or `src/invest/adapters/sec_fundamentals.py` — immutable original-version ingestion with filing acceptance metadata; one adapter, chosen after the audit.
- `src/invest/domain/fundamental_surprise.py` — pure versioned facts, seasonal surprise calculation, and quarantine reasons.
- `src/invest/application/fundamental_event_study.py` — public-time cohort construction, controls, and event returns; reuse `src/invest/application/event_study_excess.py` where its same-date summaries are sufficient.
- `src/invest/application/research_inference.py` — issuer/date clustered or block-bootstrap inference and family-wise correction, isolated from trading logic.
- `fixtures/real-continuous/reports/research_fundamental_surprise.py` plus a versioned JSON artifact — sequential, memory-bounded driver and provenance.
- Focused tests under `tests/adapters/`, `tests/domain/`, and `tests/application/` for original-versus-amended values, timestamp ordering, split-adjusted EPS, fiscal-year changes, XBRL tag lineage, ticker changes, duplicates, missing history, and stale terminal opens.

The existing `MarketContext`, Sharadar TICKERS/ACTIONS mapping, event-study excess helpers, fixed-horizon exit, cost model, and seeded random admission can be reused after their boundaries are verified. The initial position-blind study needs no scanner or broker path. Only if F1–F6 pass should a fundamental event source be wired into replay; that later change is smaller than the trustworthy data tape.

**New data required:** original quarterly revenue and diluted GAAP EPS; exact public release/filing timestamps; filing/amendment identities; period-valid issuer/security mappings; at least eight prior comparable quarterly changes; event-window SEP opens; PIT eligibility; corporate actions; and actual inactive-security terminal outcomes. Analyst consensus is deliberately not required and is forbidden as a fallback after a null.

## Confidence (0–100) and single sharpest risk

**Confidence: 44/100.** Confidence is higher in the research economics than in the edge: a high-frequency, structured corporate-information event can be killed before portfolio work, and the mechanism has a direct revenue-confirmation contrast. Confidence in deployable alpha is below even odds because modern liquid-stock PEAD may already be zero. **Single sharpest risk:** the market fully incorporates both earnings and revenue by the first tradable open, so every post-open abnormal-return ordering collapses and only illiquid, cost-eaten remnants remain.

## Attacks on the other two archetypes

### A) Form-4 opportunistic clusters — Round 1 Codex Phase 3 as written

Form-4 clusters have the best narrative mechanism of the three alternatives: discretionary cash purchases by already-exposed officers/directors can reveal conviction, and two distinct buyers are a sensible corroboration. That does not make the proposed research economics good **now**.

The Round 1 design owes a three-year insider-history classifier before its first eligible event, exact owner identity, joint-report deduplication, Form 4/A partial corrections, security-title mapping, code-P venue ambiguity, 10b5-1 interpretation, and inactive-name outcomes. Its highest-conviction subset is deliberately sparse and most likely strongest in illiquid small firms. It can consume weeks building a pristine tape only to discover that transaction-time information was incorporated during the statutory filing lag or by specialist feeds before the next open. The routine/opportunistic classifier also creates a dangerous temptation: when clusters are scarce, someone will relax “two distinct,” shorten the ten-session window, admit unclassified insiders, or call private code-P purchases open-market. That is p-hacking through ontology.

The fundamental-surprise audit is not easy, but it produces many issuer-quarters, needs no cross-person identity graph, and tests a structured numeric mechanism before portfolio integration. Form-4 should remain behind a written new-line decision after this faster program settles, not inherit priority because Round 1 once called it Phase 3. If Form-4 is opened later, the Round 1 bitemporal, next-open, liquid-subset, actual-terminal-economics, and mechanism-ordering rules are non-negotiable.

### B) Rescue / rebrand residual price events — ranking, gates, vol-scale, DAMB modules, “just drop 2020,” second autopsy

This is not research; it is refusal to accept a settled loss of optionality.

- Gate 1a already answered the scientific diagnostic: h60 mean excess exists, but median excess is negative and ID provides no credible ranking ladder.
- Phase 2 already answered the structure question: the frozen no-rank, fixed-horizon, random-admission book failed the hard year-concentration gate.
- Phase 2b already answered the residual economics: leaving 2020 cut expectancy below half the full book, and the same-clock SPY match beat the strategy after costs.

Every proposed rescue either violates the narrow hard freeze or changes the claim after seeing the failure. ID/Quiet Drift searches for a selector after Gate 1b did not earn one. DAMB's 200DMA, volatility scaling, trails, and breakout proximity can reduce or time beta; they cannot retroactively make the settled event beat matched SPY. “Drop 2020” deletes the best year while ignoring that the residual then became economically trivial. A second autopsy is repeated sampling from the same corpse. Rewriting the 25% gate is governance fraud, not robustness.

**This is the most dangerous archetype now.** It is cheap because all the code exists, emotionally attractive because 6/7 folds were positive, and almost guaranteed to generate another green slice if enough gates, ranks, or risk scalers are tried. That combination—low marginal engineering cost, high analyst degrees of freedom, and a published matched-beta failure—is a faster route to false confidence than Form-4's obvious engineering sink.

### C) Honest beta / passive — stop claiming CS alpha; productize SPY/IWM or simple TSMOM with costs

Honest passive is the correct **capital default** and an important benchmark, but it is not automatically the strongest research program. If the objective is exposure to the equity premium, a low-cost diversified vehicle dominates a 20-name event book on simplicity, tax, capacity, and governance. The settled S2 result makes that default stronger, not weaker.

The danger begins when “honest beta” mutates into a backtested alpha story. SPY/IWM choice is an allocation decision, not a discovered signal. A single 200DMA or 12-month TSMOM overlay evaluated over 2019–2025 has only a handful of independent regime transitions; it can look brilliant by side-stepping one drawdown and then bleed through whipsaw, taxes, and missed rebounds. The strongest TSMOM evidence is multi-asset and futures-heavy, not proof for this repo's single-equity event machinery. Productizing a timing rule without a long external sample and a cash/T-bill benchmark merely replaces cross-sectional overfit with regime overfit.

So: hold passive exposure if capital must be deployed, but do not spend alpha-research budget cosmetically recreating it. Passive is the hurdle and the fallback. The proposed fundamental event earns research budget only because one bounded experiment can prove a distinct abnormal-return mechanism; if it fails, the intellectually honest outcome is pause or passive—not another technical overlay.

## Final one-liner

I would bet the next research budget on one public-time, liquid-sample event study of **revenue-confirmed positive earnings surprises**, and the killing proof is simple: if next-open-to-open h60 abnormal mean **and median** do not beat EPS-only events and matched-window SPY after costs without a year-concentration breach, terminate the line and allocate capital passively.
