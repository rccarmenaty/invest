# CFOB gate law diverges from prior CS lines

CFOB is an **event-cohort** study on insider purchase clusters. R2-1, CMFT, and Phase 2 were **cross-sectional spread** studies on a formation calendar. Three of CFOB's gates deliberately differ from those precedents, decided in the PRD #76 grill. Recording them together because they share one rationale: an event cohort is a different statistical object, and copying spread-study gate law onto it would fail for reasons unrelated to whether the signal exists.

## Considered options

### 1. Median gate: hard `median > 0` (precedent) vs diagnostic (chosen)

- **Hard median > 0** — used by R2-1 and CMFT. Rejected: Gate-1a measured h60 mean **+1.89%** against median **−0.42%** on this repo's own event cohort. Sixty-session single-stock excess returns are right-skewed by nature, so the gate would kill on distributional shape rather than absence of effect. A long-only basket earns exactly this shape legitimately.
- **Median demoted to diagnostic, breadth guarded by a winsorized (1/99) trimmed mean with trimmed t ≥ 2** (chosen) — targets the real worry, "a few moonshots carry the result", with a test that distinguishes it from ordinary skew.
- Both mean and median hard — compounds the first problem.

### 2. Null model: raw excess vs universe (precedent) vs placebo null (chosen)

- **Raw h60 excess vs same-date eligible-universe mean** — Gate-1a's object. Rejected as *primary*: that same measurement returned +1.89% at t=5.3 on a spike-event cohort, so "excess vs universe" is not reliably zero for event cohorts. A positive CFOB reading could be cohort artifact rather than insider information.
- **Placebo null** (chosen) — primary statistic is observed excess minus the within-ticker date-shuffled placebo mean. Shuffling preserves the firms and destroys only timing, so it isolates the information claim. Raw excess still reported.
- **Characteristic-matched control portfolio** — the rigorous alternative. Rejected on cost and honesty: it needs a daily cross-sectional characteristic panel, a per-event peer selector, a contamination policy, and a paired-inference estimator, none of which exist — and market-cap history is not entitled (METRICS is snapshot-only, DAILY is samples), so "size" would be a proxy. Named as a follow-up if E1 survives.

### 3. Universe floor: house $10M screen (precedent) vs $2M (chosen)

- **House eligible-universe screen** (price ≥ $10, 20-bar median dollar volume ≥ $10M) — maximum comparability with the Gate-1a cohort. Rejected as primary: the surviving-anomaly habitat in the literature is small/mid caps with high arbitrage costs, mostly *below* that floor. Testing where the edge is not claimed to live designs the line to fail, then invites post-hoc promotion of a secondary band.
- **Price ≥ $5, 20-bar median dollar volume ≥ $2M** (chosen) with a 10/25/50 bps cost ladder and the **primary verdict taken at 25 bps**. Capital here is retail-small, so capacity is not binding; spread and slippage are, and the 25 bps primary prices them in. The $10M band is reported as a secondary comparability diagnostic.
- **Sub-$2M microcap primary** — closest to the literature, rejected on execution honesty for a real account.

## Consequences

- CFOB verdicts are **not** directly comparable to R2-1 / CMFT verdicts on gate-by-gate grounds; the artifact's frozen protocol block records each divergence explicitly.
- The divergences are **not** a loosening: the placebo null is strictly harder than raw excess, the 25 bps primary cost bar is stricter than the 10 bps used elsewhere, and the power precheck (MDS ≤ 1.25%) is calibrated to a decayed effect size rather than a convenient one.
- Prior lines stay settled. Nothing here reopens residual, R2-1, PEAD, or CMFT #74, and none of these bars may be back-ported to rescue them.
- Changing any of the three later is a **new trial** and must be recorded as such against the deflated-Sharpe standard.
