# R2-1 results — xs-reversal-lp (short-horizon CS reverse)

**Date:** 2026-07-21
**Driver:** `fixtures/real-continuous/reports/research_xs_reversal.py`
**Artifact:** `fixtures/real-continuous/reports/xs-reversal-structure.json`
**Parent PRD:** #65

## Verdict

### **kill_line**

- implementability_eligible: `False`
- capital_go: `False` (always false for this line)
- residual claim: **hard frozen** (not reopened)

## Headline spread (residualized B−T, primary liquid)

| n formations | mean | median | hit>0 | clustered t |
| ---: | ---: | ---: | ---: | ---: |
| 404 | 0.001857 | 0.0012041148641387636 | 0.5222772277227723 | 1.4349857424874444 |

## Costs (mean-spread diagnostic — buffering not modeled)

- mean-spread 5 bps: 0.0008567897043592362
- mean-spread 10 bps: -0.00014321029564076377
- mean-spread 25 bps: -0.003143210295640764
- buffering_modeled: `False`

## Concentration

- max year share: 0.44016983740223325
- max month share: 0.1045493766968305

## Gates

- **G0-placebo** [hard] **PASS** — placebo |t|=0.04942577307514359 < 2.0
- **G0-synthetic** [hard] **FAIL** — synthetic-action migration not measured — fail closed
- **G1** [hard] **FAIL** — gross B-T clustered_t<3.0 (t=1.4349857424874444)
- **G2** [hard] **PASS** — median spread>0 (median=0.0012041148641387636)
- **G3** [hard] **FAIL** — folds=7/8 majority=True; year_share=0.44016983740223325 (max 0.25); month_share=0.1045493766968305 (max 0.2)
- **G4** [hard] **FAIL** — |rho|=0.07240965620649024 ok=True; alpha=0.0016728995253907195 ci_excludes_0=False
- **G5** [hard] **FAIL** — unscaled t=1.4349857424874444<2.0
- **G6** [escalate] **FAIL** — tail / Jan-2021 short-leg not measured — fail closed (no silent GO)
- **G7** [hard] **FAIL** — buffering/turnover not modeled — mean-spread net only (mean_net_10bps=-0.00014321029564076377; mean_net_5bps_primary=0.0008567897043592362)
- **G8** [hard] **FAIL** — deflated Sharpe=-0.03006744862493975 not >0

## Measurement gaps (fail closed)

- `g0_synthetic`: not_measured_fail_closed
- `g6_tail`: not_measured_fail_closed
- `g7_buffering`: not_modeled_fail_closed

## Pass meaning

Clearing hard gates ⇒ **implementability PRD eligibility only** — not capital, not residual unfreeze, not PEAD/Form-4 auto-start.

## How to re-run

```bash
# Alone on a 16GB host — no parallel multi-GB loads
uv run python fixtures/real-continuous/reports/research_xs_reversal.py --write-docs
```

