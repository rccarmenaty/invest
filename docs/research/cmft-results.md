# CMFT Stage A results

**Date:** 2026-07-21
**Driver:** `fixtures/real-continuous/reports/research_cmft.py`
**Artifact:** `fixtures/real-continuous/reports/cmft-structure.json`
**Parent PRD:** #74

## Verdict

### **underpowered-stop**

- implementability_eligible: `False`
- capital_go: `False` (always false)
- residual freeze untouched: `True`
- R2-1 kill_line untouched: `True`
- SF* features included: `False`
- HMM included: `False`

## Gates

- **G0-data** [hard] FAIL — G0-data not measured — fail closed
- **K0-power** [hard] FAIL — K0 power inputs not measured — fail closed
- **G0-placebo** [hard] PASS — placebo |t|=0.0 < 2.0
- **G1** [hard] FAIL — insufficient or non-finite spread sample
- **G2** [hard] FAIL — median missing or non-finite
- **G3** [hard] FAIL — no annual folds
- **G4-costs** [hard] FAIL — mean_net_10bps=nan<=0
- **G5-beat-c1** [hard] FAIL — T1 mean nan vs C1 nan (ok=False); T1 median nan vs C1 nan (ok=False)
- **G6-VI** [hard] FAIL — VI not measured — fail closed
- **G7-reversal** [escalate] FAIL — short-horizon VI share not measured — fail closed escalate
- **G8-DSR** [hard] FAIL — deflated Sharpe not measured — fail closed

## Mode notes

- mode: `default-unmeasured`
- note: Continuous full-depth SEP panel measurement is not executed in this default path. Publish fail-closed until a sequential panel load is implemented against entitled SEP. Use --synthetic for harness smoke.

## How to re-run

```bash
# Fail-closed default (no invented continuous measurement)
uv run python fixtures/real-continuous/reports/research_cmft.py --write-docs

# Synthetic harness smoke (no LightGBM, no multi-GB)
uv run python fixtures/real-continuous/reports/research_cmft.py --synthetic --write-docs
```
