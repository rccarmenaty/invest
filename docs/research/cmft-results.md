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

## C1 diagnostics

- n_formations: `83`
- c1_mean_gross: `0.012146385344112609`
- c1_mean_net_10bps: `0.010146385344112609`
- c1_median_gross: `0.022305956378001136`
- k0_mds_bps: `225.30969066079206`
- g0_years_monotone/total: `0/7`
- placebo |t|: `1.0814244611011348`

## Annual fold table (C1 gross spreads)

- 2019: n=12 mean=0.02086723671781213
- 2020: n=12 mean=0.009728976747540575
- 2021: n=12 mean=-0.01986216961145229
- 2022: n=12 mean=0.020438359313304368
- 2023: n=12 mean=0.023095394783817867
- 2024: n=12 mean=0.0277837546587912
- 2025: n=11 mean=0.002139213840325486

## Gates

- **G0-data** [hard] FAIL — monotone years 0/7 < 4
- **K0-power** [hard] FAIL — underpowered: MDS=225.31bps > 50.0bps (n=83)
- **G0-placebo** [hard] PASS — placebo |t|=1.0814244611011348 < 2.0
- **G1** [hard] FAIL — gross D10-D1 clustered_t<3.0 (t=1.5186487430724112)
- **G2** [hard] PASS — median spread>0 (median=0.022305956378001136)
- **G3** [hard] FAIL — folds=6/7 majority=True; year_share=0.26747382330193364 (max 0.25); month_share=0.04909316588624629 (max 0.2)
- **G4-costs** [hard] PASS — mean_net_10bps=0.010146385344112609>0 (mean_net_5bps=0.011146385344112608 diagnostic)
- **G5-beat-c1** [hard] FAIL — T1 mean nan vs C1 0.010146385344112609 (ok=False); T1 median nan vs C1 0.020305956378001137 (ok=False)
- **G6-VI** [hard] FAIL — VI not measured — fail closed
- **G7-reversal** [escalate] FAIL — short-horizon VI share not measured — fail closed escalate
- **G8-DSR** [hard] FAIL — deflated Sharpe not measured — fail closed

## Mode notes

- mode: `continuous-fixture`
- note: Continuous 2019–2025 fixture panel: C1 + G0-data + K0 + placebo measured. Not full-depth SEP (~1998+). T1/C2 only if K0 passes and research-ml present. K0 failed → T1/C2 not trained (cheap kill / underpowered-stop path).
- t1_status: `skipped_k0`

## How to re-run

```bash
# Continuous fixture panel (sequential multi-GB; alone on 16GB host)
uv run python fixtures/real-continuous/reports/research_cmft.py --write-docs

# Synthetic harness smoke (no LightGBM, no multi-GB)
uv run python fixtures/real-continuous/reports/research_cmft.py --synthetic --write-docs
```
