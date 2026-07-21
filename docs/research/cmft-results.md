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

- n_formations: `323`
- c1_mean_gross: `0.017104286933022555`
- c1_mean_net_10bps: `0.015104286933022555`
- c1_median_gross: `0.01853244336051284`
- k0_mds_bps: `162.3408998435467`
- g0_years_monotone/total: `0/27`
- placebo |t|: `0.47311700271845897`

## Annual fold table (C1 gross spreads)

- 1999: n=12 mean=0.05275074340634978
- 2000: n=12 mean=-0.031857652441842
- 2001: n=12 mean=0.04657935069641156
- 2002: n=12 mean=0.061040545250981286
- 2003: n=12 mean=0.01924933745320947
- 2004: n=12 mean=0.01908422806982304
- 2005: n=12 mean=0.010922215248516274
- 2006: n=12 mean=-0.010796770495303176
- 2007: n=12 mean=0.014597439604178837
- 2008: n=12 mean=0.055084602002725865
- 2009: n=12 mean=-0.047023008817108414
- 2010: n=12 mean=-0.002505540680011411
- 2011: n=12 mean=0.015533612172933982
- 2012: n=12 mean=0.007028615112217703
- 2013: n=12 mean=0.02449211143285937
- 2014: n=12 mean=0.03616341340449302
- 2015: n=12 mean=0.02783127151964632
- 2016: n=12 mean=-0.028804911352871002
- 2017: n=12 mean=0.002226738453433184
- 2018: n=12 mean=-0.017669403648703563
- 2019: n=12 mean=0.01818127372132883
- 2020: n=12 mean=0.03348544153200252
- 2021: n=12 mean=-0.0019999198657765014
- 2022: n=12 mean=0.014763288071254863
- 2023: n=12 mean=0.07651214028482389
- 2024: n=12 mean=0.06356028452748409
- 2025: n=11 mean=0.0021392130372355606

## Gates

- **G0-data** [hard] FAIL — monotone years 0/27 < 4
- **K0-power** [hard] FAIL — underpowered: MDS=162.34bps > 50.0bps (n=323)
- **G0-placebo** [hard] PASS — placebo |t|=0.47311700271845897 < 2.0
- **G1** [hard] FAIL — gross D10-D1 clustered_t<3.0 (t=2.954665908292919)
- **G2** [hard] PASS — median spread>0 (median=0.01853244336051284)
- **G3** [hard] PASS — folds 20/27 majority; year_share=0.1272979721323989; month_share=0.02828517997616566
- **G4-costs** [hard] PASS — mean_net_10bps=0.015104286933022555>0 (mean_net_5bps=0.016104286933022554 diagnostic)
- **G5-beat-c1** [hard] FAIL — T1 mean nan vs C1 0.015104286933022555 (ok=False); T1 median nan vs C1 0.016532443360512843 (ok=False)
- **G6-VI** [hard] FAIL — VI not measured — fail closed
- **G7-reversal** [escalate] FAIL — short-horizon VI share not measured — fail closed escalate
- **G8-DSR** [hard] FAIL — deflated Sharpe not measured — fail closed

## Mode notes

- mode: `full-depth-sep-parquet`
- note: Full-depth Sharadar SEP 1998-01-02..2025-12-31 via year parquet shards under /Users/rcty/invest/fixtures/full-depth-sep (primary common, snappy). T1/C2 only if K0 passes and research-ml feature panel is available. K0 failed → T1/C2 not trained (underpowered-stop / cheap path).
- t1_status: `skipped_k0`

## How to re-run

```bash
# Continuous fixture panel (sequential multi-GB; alone on 16GB host)
uv run python fixtures/real-continuous/reports/research_cmft.py --write-docs

# Full-depth SEP → year parquet + measure (needs NASDAQ_DATA_LINK_API_KEY)
uv sync --extra research-ml
uv run python fixtures/real-continuous/reports/research_cmft.py --full-depth --write-docs

# Resume pull only / measure only
uv run python fixtures/real-continuous/reports/research_cmft.py --full-depth --pull-only
uv run python fixtures/real-continuous/reports/research_cmft.py --full-depth --measure-only --write-docs

# Synthetic harness smoke (no LightGBM, no multi-GB)
uv run python fixtures/real-continuous/reports/research_cmft.py --synthetic --write-docs
```
