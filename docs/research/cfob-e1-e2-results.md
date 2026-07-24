# CFOB E1/E2 returns gates — results

**Verdict:** `promotion_block` (failing: E1, E2) · `capital_go` = false

- Mode: `measured` · git `a03a8917d9ea675a079ba03d3cb01e3b61f68bba-dirty`
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
