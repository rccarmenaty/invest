# Adversarial Strategy Debate — Round 2 Shared Brief

**Date:** 2026-07-20  
**Repo:** invest (main @ `96ee859` + Phase 2 merge `a4021ce`)  
**Task:** Propose the strongest *next* research program after Round 1’s ordered plan was **fully executed** and the residual price-event portfolio claim **died**.  
**Role:** You are one of three adversarial judges. Argue hard for YOUR proposal. Attack weak reasoning. Prefer real edge and research economics over narrative beauty.

## Why Round 2 exists

Round 1 produced three proposals (Quiet Drift, DAMB, Filed Conviction / Form-4) and a meta-judge program:

1. **Gate 1a** — h60 excess-vs-universe on the existing cohort  
2. **Phase 2** — unranked fixed-horizon + slot lottery (if 1a passes; Gate 1b failed → no ranking)  
3. **Phase 3** — Form-4 or full stop *only after Phase 2 settles* (or if 1a failed)

That program is **complete**. Results are binding. This debate is an **event-only re-open** under the freeze rules: human-initiated, not auto-start from residual reports. You must account for settled outcomes — do **not** re-propose “run Gate 1a” or “try fixed-horizon naïve” as if unknown.

## System (what exists)

- Point-in-time market context from Sharadar (SEP + ACTIONS + TICKERS)
- Momentum-selection Core scanner vs naïve spike-detector benchmark (§2.5 control)
- Fixed-horizon exit policy (`fixed-horizon`, no price stop / TP path exits)
- Seeded slot-cap random admission (`max_concurrent_positions`, `admission_seed`)
- Event-study excess helpers (Gate 1a); Phase 2 report + concentration autopsy drivers
- Trailing channel / time-stop / ATR-trail exits still available
- Memory-bounded streaming fixtures; fail-closed if open position's last bar predates replay end
- **No** production Form-4 / SEC ownership PIT tape yet (Round 1 Codex track never started)

## Evidence window

- Continuous fixture: ~2019-01-02 → 2025-12-31, ~6.5k symbols, ~8.87M bars
- Historical IS/OOS split used: 2023-01-03 — **burned**; walk-forward + deflated testing only
- Costs: 5 bps/side primary; tax secondary where reported
- Sequential multi-GB runs only on 16GB host (no parallel fixture loads)

## Settled experiment results (must internalize)

### 0 — First continuous Core failure
- Capped $100k: 125 trades, net −7.7k; capital-gate dominated
- Uncapped: 4,683 trades; raw PF 0.97; after costs large loss
- Tight stops dominate loss count; short path ≈ noise

### 1 — Forced-close audit
- FC profit on old stop/trail books is **policy artifact**, not alpha

### 2 — Signal event study (n≈12,295 position-blind accepted signals)
| Horizon | Mean | clustered t | Hit>0 |
|---|---:|---:|---:|
| +1d | −0.08% | −1.01 | 48.8% |
| +5d | −0.04% | −0.31 | 50.9% |
| +10d | +0.43% | +2.44 | 52.3% |
| +20d | +0.98% | +3.31 | 53.6% |
| +60d | +3.49% | +7.49 | 52.0% |
| +120d | +7.11% | +13.6 | 56.5% (survivorship caveat) |

- h20 excess vs same-date universe: +0.36%, t=1.78 (thin CS)
- Race to ±1×ATR within 60d: P(+1R first)≈48.5%

### 3 — Spec-compliant baseline + §2.5 control
- **Core fails to beat naïve spike control OOS** — ranking adds no clear value
- Spec-compliant still no edge after costs

### 4 — Corrected 2022–2025 matrix
- Fail-closed on stale terminal opens; **no valid multi-year P&L** from that matrix

### 5 — Gate 1a (EXECUTED — PASS)
Source: `docs/research/gate1a-results.md`

| Horizon | n | Mean excess | Clustered t | Hit>0 | Median excess |
|---|---:|---:|---:|---:|---:|
| 20 | 11,977 | +0.36% | 1.78 | 49.1% | −0.19% |
| **60 (primary)** | **11,489** | **+1.89%** | **5.30** | 49.0% | **−0.42%** |
| 120 (flagged) | 10,681 | +2.26% | 4.98 | 49.0% | −0.64% |

- Mean residual at h60 is **not pure beta** (clears t≥2.5)
- **Median excess still negative** — right-tail driven
- Regime: 2021 h60 excess −6.74% (t −5.85); 2024 +5.16% (t 6.98)
- **Gate 1b NOT claimed:** ID q1−q5 spread only +0.55pp; not monotone enough for ranking

### 6 — Phase 2 structure test (EXECUTED — NO-GO)
Source: `docs/research/phase2-results.md`  
Config frozen: §2.5 naïve · `fixed-horizon` 60 · slots 20 · seed 42 · 5 bps · no ranking

| Gate | Result |
|---|---|
| Majority WF folds after-cost exp > 0 | **PASS** (6/7) |
| FC-segregated still meets majority > 0 | **PASS** |
| No year > ~25% of net profit | **FAIL** (2020 = **85.7%**) |
| Random-admission only | **PASS** |

Headline: full book n=200, mean exp +56.12, net +11,223; non-FC stronger than full (FC *subtracts* here).  
2022 only negative fold (−290.75 mean); 2020 dominates dollars.

**Interpretation already published:** structure not uniformly dead after costs, but **promotion blocked** by concentration. Do not add ranking to rescue.

### 7 — Phase 2b concentration autopsy (EXECUTED — residual_hope DIE)
Source: `docs/research/phase2-concentration-autopsy.md`

| K2/S2 leg | Result |
|---|---|
| Leave-2020 mean > 0 | PASS (~9.44) |
| Leave mean > ½ full-book mean | **FAIL** (9.44 ≤ 28.06) |
| Majority remaining folds > 0 | PASS (5/6) |
| S2 mean trade−SPY excess > 0 | **FAIL** (~**−102**) |

**Verdict:** residual_hope **DIE**. Leave-dominant-year hope is economically weak; trade-window matched SPY is not beaten after costs.

### Freeze (binding research law)

Language: **promotion block** of the residual claim — **not** program kill of all research.

| Rule | Decision |
|---|---|
| Budget | Pause-default on *this residual line* |
| Intensity | **Hard freeze** on the settled claim |
| Exit | **Event-only re-open** (this debate is that event) |
| Scope | **Narrow freeze** — naïve event → fixed-horizon → slot-lottery **portfolio residual** only |

**Out of bounds until a *new* named hypothesis with its own PRD:**  
structure tweaks / second residual autopsy on the same book; ranking or Quiet Drift / DAMB packaging *as continuation of this residual*; rewriting the ~25% year-share gate to green-light the same book; treating Gate 1a as go-live.

**In bounds:** non-claim engineering; **new signal families** (different line); honest full-stop / capital reallocation proposals; Form-4 *as a competing new line* (not Phase 2 continued).

## Round 1 prior art (do not rediscover blindly)

Read if useful (mandatory for attacks section):

- `docs/research/adversarial-debate/outputs/proposal-claude-fable.md` — Quiet Drift (ID + fixed hold)
- `docs/research/adversarial-debate/outputs/proposal-grok-45-high.md` — DAMB package
- `docs/research/adversarial-debate/outputs/proposal-codex-gpt56-sol-xhigh.md` — Form-4 opportunistic clusters
- `docs/research/adversarial-debate/outputs/meta-judge-verdict.md` — ordered program (now executed)

You may **refine, reject, or replace** Form-4. You may propose a different information source, an honest beta product, multi-strategy research ops, or **stop**. You may **not** pretend Phase 2 residual still has open “hope” under K2/S2.

## Research principles already agreed

1. Diagnose signal independent of exits before tuning  
2. One conceptual component at a time  
3. Constant risk when comparing stops  
4. Pre-tax after costs primary; tax secondary  
5. Date-clustered inference  
6. Prefer broad stable regions; deflated Sharpe / multiple-testing discipline  
7. 2023–2025 no longer untouched holdout  
8. **New (post Phase 2b):** residual DIE + pause-default; re-open is explicit and hypothesis-named  
9. **New:** year concentration is a hard promotion gate, not a soft narrative

## Hard constraints for proposals

- Implementable on this stack *or* with an explicit data-feasibility audit first (especially any new SEC/alt tape)
- Must include **falsifiable acceptance gates** and **rejection conditions**
- Must cite external research (arXiv / NBER / journal) for the economic mechanism
- Must explain survival of: costs, short-path noise, FC contamination, ranking failure, **year concentration**, **median-vs-mean excess**, **matched SPY trade-window loss**, multiple testing
- Forbidden: inventing numbers as if already measured; claiming edge without a measurement plan
- Forbidden: reopening the frozen residual claim with knob-turning
- Prefer ideas that treat Gate 1a PASS + Phase 2 NO-GO + residual DIE as **joint** evidence (mean residual exists; portfolio residual failed promotion *and* economic residual bar)

## Required output structure (strict)

# Proposal title
## Thesis (1 paragraph)
## Mechanism (why edge should exist economically)
## Literature anchors (3–8 citations with arXiv/DOI/URL + one-line relevance)
## Concrete strategy design (entries, ranking, exits, portfolio, costs assumptions)
## How it differs from settled Phase 2 residual and from Round 1 proposals
## Why settled results (Steps 0–7) predict this might work
## Why it might fail (steelman opposition)
## Measurement plan (ordered experiments, sample design, stats)
## Acceptance / rejection gates
## Implementation cost on this repo (files / new modules / data needs)
## Confidence (0–100) and single sharpest risk

Then:
## Attacks on the other two archetypes
Attack these alternative directions (even if you also like parts of them):

A) **Form-4 opportunistic clusters** — Round 1 Codex Phase 3 as written (PIT audit → event study → portfolio)  
B) **Rescue / rebrand residual price events** — ranking, gates, vol-scale, DAMB modules, “just drop 2020,” second autopsy  
C) **Honest beta / passive** — stop claiming CS alpha; productize SPY/IWM or simple TSMOM with costs  

Argue which archetype is most dangerous *now* (overfit / engineering sink / opportunity cost / false confidence).

## Final one-liner
What would you bet your own capital research budget on next, and what single experiment proves or kills it?

---

## Judge independence rules

1. Draft YOUR proposal from this brief + primary result docs **before** reading the other Round-2 judges’ files.  
2. You may read Round 1 archive and result docs freely.  
3. After drafting, if other Round-2 proposals exist in `round-2/outputs/`, revise only the **Attacks** section (optional).  
4. Write the full proposal to the path given in your seat prompt. Do not edit trading code.
