# First Backtest Failure — Verification, Assessment & Revised Research Plan

**Model:** Claude Fable 5
**Date:** 2026-07-18
**Inputs:** `fixtures/real-continuous/reports/{backtest-baseline.json, backtest-uncapped.json, README.md}`,
`docs/research/first-backtest-failure-research-plan.md` ("doc 1"),
`docs/research/first-backtest-failure-research-plan-kimi-k3.md` ("doc 2"),
`SPEC.md`, `application/backtest_run.py`
**Status:** supersedes the ordering in docs 1 and 2; incorporates a decomposition both missed

---

## 1. Verification of the prior research docs

Every quantitative claim in docs 1 and 2 was recomputed from the uncapped trade
ledger (n = 4,683) or checked against source before this assessment was written.

**Confirmed:**

- 960 stops on the entry day (28.1% of 3,413 stops); median stop duration 3
  calendar days.
- By-year raw P&L table exact: 2019 −74,212; 2020 +105,660; 2021 −151,083;
  2022 −234,693; 2023 +146,930; 2024 +212,430; 2025 −111,061.
- OOS aggregate raw +248,299, PF 1.135, t = 1.53 (see §2 — this number is
  real but misleading).
- Tail concentration: 350 trades (7.5%) with >+10% return sum to +2,727,853
  raw against a −106,030 total; avg win +12.2%, avg loss −3.4%.
- Alphabetical candidate fill confirmed at `application/backtest_run.py:194`
  (`sorted(pending[current_date], key=lambda item: item.symbol)`), violating
  SPEC §2.4 ranked selection.
- All six spec-gap claims in doc 2 §2 verified against `SPEC.md`: interim
  1×ATR stop vs spec'd `min(breakout-day low, entry − 2×ATR(20))` (§2.7);
  missing benchmark-200-DMA regime gate (§2.3); missing 10-session re-entry
  cooldown (§2.7); implemented 1% risk vs spec'd 0.35% baseline (§2.8,
  "must come down with roadmap change C"); §2.5 control never run.

**Minor discrepancy:** doc 2 states 47% of stops die within 1 day; recomputed
as 41.1% within 1 *calendar* day (1,404 of 3,413). Likely trading-day vs
calendar-day counting. Not material.

## 2. The finding both docs missed: OOS positivity is a forced-close artifact

Both docs quote the OOS segment (entries ≥ 2023-01-03) as tentative
improvement — raw +248,299, PF 1.135, t = 1.53. Decomposed by exit reason:

| OOS cohort | n | Raw P&L | PF | Naive t |
| --- | ---: | ---: | ---: | ---: |
| All trades | 2,240 | +248,299 | 1.135 | +1.53 |
| `context-position-forced-closed` only | 249 | **+610,676** | — | — |
| Ex-forced-close | 1,991 | **−362,377** | 0.795 | **−2.61** |
| Ex-forced-close, ex-open-at-end | 1,960 | −454,088 | 0.743 | −3.34 |

The entire OOS improvement — and more — is carried by 249 corporate-action
forced closes averaging +2,452 per trade (acquisition run-ups valuated at the
forced-close timestamp). The strategy's own exits (hard stop + trailing
channel) lose money OOS at conventional significance. In-sample forced closes
add another +415,666 (279 trades).

Consequences:

- Doc 1's rejection condition for its context-exit audit ("if apparent signal
  edge depends on … a single event category, do not attribute that edge to the
  scanner") **fires on the existing data**. The audit was ranked second; the
  data says it is a precondition for interpreting anything else.
- Doc 2's regime narrative (2023/2024 positive years motivating the 200-DMA
  gate) is contaminated: the positive years must be re-verified ex-forced-close
  before they can justify a regime layer.
- Every "positive cohort" cited anywhere in the current evidence base rides on
  forced-close proceeds until proven otherwise.

Caveat on the label: the ledger's exit reason is
`context-position-forced-closed`, not `forced-closed`. A string-match against
the short form silently selects zero rows — the first verification script here
made exactly that mistake and briefly "proved" the opposite.

## 3. Assessment of the prior docs

**Doc 1** — strongest *methodology*. Clustered-by-entry-date inference,
deflated Sharpe / multiple-testing correction, predeclared grids with all
trials recorded, constant-risk stop comparisons, and the point nobody else
made: the 2023-2025 window is a burned holdout, so research must move to
rolling walk-forward with a fresh future holdout. Weaknesses: it treats the
implemented configuration as "the strategy" without noting most fixes are
already written in SPEC, and it quoted the OOS aggregate without exit-reason
decomposition — which its own item 2 was designed to catch.

**Doc 2 (kimi-k3)** — strongest *diagnosis*. Maps every observed failure to a
verified, documented spec gap, and its external-literature table is accurate
and on-point (Barroso & Santa-Clara 2015 volatility scaling; Daniel &
Moskowitz momentum crashes; Kaminski & Lo on stops inside the noise band).
Weaknesses: (a) the motivating regime/year evidence is forced-close
contaminated per §2; (b) the bottom line — "the reports do not yet prove the
strategy has no edge" — is literally true but reads as optimism the data does
not yet support; (c) it correctly labels forced closes "artifacts, not
signal" and then uses artifact-contaminated aggregates as motivation anyway.

## 4. Prior, stated plainly

Individual-stock momentum breakout, post-publication edge decay in the
literature, ~10 bps round-trip execution plus taxes, on a small account,
against a benchmark (SPY) that returned roughly +130% over the same window.
The realistic ceiling is modest and the burden of proof is on the strategy.
Ex-forced-close, no segment of the current system — IS or OOS, any year — is
demonstrably positive.

## 5. Revised ordered program

Reorders docs 1 and 2; keeps doc 1's methodology rules and doc 2's spec-gap
targets.

### Step 1 — Forced-close audit (promoted to first; blocking)

Partition all 528 forced closes by cause (acquisition, delisting, eligibility
change, invalid/missing context). Re-valuate under conservative,
knowable-at-time prices (prior close / same-day open / same-day low
sensitivity, per doc 1). Publish the corrected ex-artifact segment and year
tables. No regime, OOS, or year-level claim is admissible until this exists.
Cheap: ledger partition plus revaluation; no backtest rerun.

### Step 2 — Signal event study (exit-blind, portfolio-blind)

Doc 1's design, adopted: for every accepted signal — independent of gates and
exits — forward returns at 1/5/10/20/60/120 sessions, MFE/MAE, P(+1R before
−1R), by entry year and ex-ante regime, raw and after execution costs,
date-clustered confidence intervals, forced-close-affected symbols as a
separate cohort (per Step 1). This answers the only question that matters:
does the accepted entry have forward drift at all.

Decision rule (doc 1's, kept): drift positive but trades negative → repair
exits; no drift → redesign signal/ranking; drift only in top-score cohorts →
replace binary acceptance with ranking.

### Step 3 — Measurement fixes, one batch (no strategy claims from it)

- Ranked candidate fill (momentum rank → 52-week-high proximity → liquidity),
  deleting alphabetical order (`backtest_run.py:194`; SPEC §2.4).
- Run the §2.5 spike-detector control under identical replay assumptions.
- Spec'd initial stop `min(breakout-day low, entry − 2×ATR(20))` and the
  10-session cooldown (§2.7), 0.35% risk (§2.8) — as the *spec-compliant
  baseline*, not as a tuned result.

Explicitly deferred: no stop-width grid search until Step 2 shows drift. If
the entry has no drift, wider stops lose more slowly and prove nothing
(doc 1, principle 1).

### Step 4 — Regime gate (conditional on Step 2)

Benchmark-above-200-DMA gate (§2.3 grid: none/100/200/dual). Motivation is
the 2021-2022 −386k raw bleed, but only after that number is re-verified
ex-forced-close (Step 1). Then volatility scaling per Barroso & Santa-Clara.

### Step 5 — Walk-forward evaluation and fresh holdout

Doc 1, principle 8, adopted verbatim: 2019-2025 is burned for selection.
Rolling walk-forward folds for research; the true holdout is future data
(post-2025 accrual or paper trading) after the strategy is frozen.

### Step 6 — Cost model

Pre-tax after-execution-cost is the primary alpha metric (doc 1, principle 5).
Separately, fix the no-loss-offset 15% tax model in
`domain/backtest_metrics.py` (`exit_proceeds` taxes each winner's gross gain
with zero loss netting) — real flaw, but irrelevant until something is
positive pre-tax.

## 6. Acceptance gates

Docs 1/2 gates (positive after-cost expectancy across folds, PF ≥ ~1.10 in a
broad parameter region, no single trade/year/sector > ~25% of profit,
clustered-CI evidence, multiple-testing correction, beats the §2.5 control),
plus one addition:

- **Benchmark hurdle:** the after-cost strategy must beat SPY/VWCE
  buy-and-hold on a risk-adjusted basis across rolling folds. If it cannot,
  the correct product decision is indexing, and the research program should
  say so. This belongs at §2.9 gate level, not as a late-stage comparison.

## 7. Bottom line

Doc 1's methodology + doc 2's spec-gap map are both kept. The ordering is
not: the forced-close audit is a blocking precondition, because as of today it
accounts for every positive cohort in the evidence. The system ex-artifact is
negative everywhere it has been measured. Optimism must be earned by the
event study, not assumed from contaminated aggregates.
