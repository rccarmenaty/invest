# CFOB E1/E2 returns gates — results

**Verdict:** `promotion_block` (failing: E1, E2) · `capital_go` = false

- Mode: `measured` · git `03c2f72f305e84a0206b1aaa8be459243ba87e71`
- Common frozen cohort: **10,663** clusters over 243 known-time months
- E1 p = `0.33046` · E2 p = `0.97055` · α = `0.005` · cost = 25.0 bps round-trip

## Conjunctive gate

`stage_pass` iff E1 `p ≤ 0.005` **and** E2 `p ≤ 0.005` on the *same* common frozen cohort; else `promotion_block` naming the failing gate; `underpowered_stop` below the 2,000-cluster floor. `capital_go` stays a separate human decision even on a green E2.

## Drop-reason ledger

Every cluster excluded from the common cohort is counted (resolved before inference, no post-hoc exclusion):

- `focal_window_incomplete`: 23
- `insufficient_placebo`: 19
- `no_entry_session`: 7

## Non-gating diagnostics

The block bootstrap is the gate; the diagnostics below are reported, never gated. Parametric iid / month-clustered / ticker-clustered t **under-state** the calendar-overlap dependence. The round-trip cost **cancels** in the placebo-differenced `d_i`, so the 10/25/50 bps ladder does not move the gate statistic. Estimator/data variants outside this build (non-circular blocks, Politis–White selector, intercept-inclusive / log-return / unit-beta / SPY benchmarks, universe-excess) are recorded as `deferred_non_gating`.

## Reproducibility

- NumPy `2.5.1` · generator `PCG64`
- Master seed `3473662434` · spec `cfob-e1-e2-1`
- Data fingerprint `66151240cc16fe7aee26783d7ea018cfd53a1e0de6640642f7b73dba4bb36608`
- Seeds, bootstrap-index hashes, and the SHA-256 length-prefixed serialization contract are in `cfob-returns.json` — a second same-seed / same-data run reproduces every p-value bit-for-bit.

## Line-close archive

**Status:** `line-closed` — Line archived at this record. Do NOT retune any frozen constant against the same data — a changed config_fingerprint is a new trial under the deflated-Sharpe standard, not an edit to this result.

### Bootstrap confidence intervals (post-hoc, non-gating)

Percentile CIs for θ̂ = T(d) from the **un-recentered** block resample (the gate itself is the one-sided null-imposed p-value; these only show the point estimate's sampling spread):

- E1: point `0.00862`, 95% CI [`-0.02959`, `0.05584`]
- E2: point `-0.00843`, 95% CI [`-0.01702`, `0.00119`]

### Paired contrast dᵢ^E1 − dᵢ^E2 — **EXPLORATORY / POST-HOC**

Not a pre-registered gate; decides nothing, recorded for the archive only:

- winsorized mean `0.01737`, point `0.01737`, 95% CI [`-0.02201`, `0.06780`], excludes zero: `False`

### Beta and habitat-breadth distributions (kept cohort)

- Observed pre-event OLS beta: n=10,663 · median `0.988` · p5..p95 [`0.4088`, `1.893`]
- Habitat breadth (non-focal names, count−1): n=10,663 · median `1705` · p5..p95 [`1370`, `1844`]

### Cost invariance

A **fixed symmetric 25 bps round-trip cost cancels exactly** from the observed-minus-placebo `dᵢ` (both legs are net of the same cost). It affects **absolute profitability** reporting, but **not** these E1/E2 inferential statistics — the 10/25/50 bps ladder moves neither p-value.

### Content hashes

- `config_fingerprint`: `4304e6d00faae1fe0055ef6eb7fc96c41d6f7906f4a9879c320c34c9898ed6b5`
- `artifact_sha256`: `119546a0551ed058169d793e99e3fb79c74d82a48b64cd9c83ca034fd908e8ae`
- `data_fingerprint`: `66151240cc16fe7aee26783d7ea018cfd53a1e0de6640642f7b73dba4bb36608`
- `cohort_fingerprint`: `70d061b87a22c3ee46d9c1c41d06c8f213acf2d8aec21851e0a259f6fcd6d972`

**Archived — do not retune against the same data.** A changed `config_fingerprint` is a new trial under the deflated-Sharpe standard, not an edit to this result.

## Claims

- E1 is provisional timing evidence; a green E1 is not alpha.
- stage_pass requires BOTH E1 and E2 p<=0.005 on the same common frozen cohort at 25 bps round-trip.
- E2 is a habitat-factor-adjusted timing test, not asset-pricing alpha and not an investable return.

### Non-claims

- Not capital permission; capital_go is false by construction.
- Not comparable gate-by-gate to R2-1 / CMFT / Phase 2 or CFOB Stage D.
- Does not reopen residual, R2-1, PEAD, or CMFT.
- The habitat factor is gross; cost applies only to the focal traded leg.

## How to re-run

```bash
CFOB_SEP_DIR=fixtures/full-depth-sep \
  uv run python fixtures/real-continuous/reports/research_cfob.py --measure-returns --write-docs
```

Frozen design: `docs/adr/0003-cfob-e1-e2-returns-gate.md`.
