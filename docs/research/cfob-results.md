# CFOB Stage D results

**Date:** 2026-07-21  
**Driver:** `fixtures/real-continuous/reports/research_cfob.py`  
**Artifact:** `fixtures/real-continuous/reports/cfob-structure.json`  
**Parent PRD:** #76 (grilled 2026-07-21)  
**ADR:** `docs/adr/0002-cfob-gate-law-divergence.md`

## Verdict

### **stage_pass**

- capital_go: `False` (always false)
- implementability_eligible: `False`
- all hard gates passed: `True`

## Cohort

- raw clusters: `35,615`
- **de-overlapped clusters (gated object)**: `8,369`
- required for MDS bar: `7,246`
- MDS at measured n: `0.0116`

## Qualification counts

- total_rows: `6,852,440`
- qualified: `376,382`
- wrong_code: `5,890,992`
- disposals: `3,714`
- below_size_floor: `407,840`
- stale: `30,152`
- amendment_superseded: `132,018`
- unparseable_value: `11,270`
- late_filed: `8`
- indirect_ownership: `157,142`

## Year shares

- 2006: 0.0331
- 2007: 0.0531
- 2008: 0.0780
- 2009: 0.0362
- 2010: 0.0314
- 2011: 0.0519
- 2012: 0.0347
- 2013: 0.0286
- 2014: 0.0366
- 2015: 0.0493
- 2016: 0.0453
- 2017: 0.0384
- 2018: 0.0611
- 2019: 0.0540
- 2020: 0.0834
- 2021: 0.0470
- 2022: 0.0646
- 2023: 0.0624
- 2024: 0.0472
- 2025: 0.0639

## Gates

- **D1-volume** [hard] **PASS** — de-overlapped clusters=8369 vs floor 7500 (MDS=0.0116 vs bar 0.0125)
- **D2-spread** [hard] **PASS** — years contributing >=2%: 20 vs floor 12
- **D3-concentration** [hard] **PASS** — max year share=0.0834 (2020) vs cap 0.25


## Stage F0 — integrity

**Status: `incomplete_f1_join_deviates_from_prd`** (raw gate report: `kill_line` — **not published as a kill**)

F1 resolved against the SEP price panel; PRD #76 specifies the TICKERS reference tape. Unmapped therefore includes out-of-universe issuers, not only mapping failures. F3 reconciles exactly, so ingestion is lossless. Not published as kill_line.

- **F0-protocol** [hard] **PASS** — protocol freeze and trial ledger present
- **F1-mapping** [hard] **FAIL** — mapping rate=0.6126 vs floor 0.9
- **F2-unmapped-composition** [hard] **PASS** — worst-year unmapped rate=0.5250 (2006) vs 3.0x global 0.3874 = 1.1621
- **F3-reconcile** [hard] **PASS** — parsed counts reconcile against SEC aggregates

### Reconciliation against EDGAR full-index

One row per *(filing, filer)* in `form.idx` (~2.10 rows per Form 4: issuer plus each
reporting owner), so counts are deduplicated by accession before comparison.

| Quarter | Dataset | EDGAR index | Delta |
| --- | ---: | ---: | ---: |
| 2006Q2 | 63,467 | 63,467 | 0.00% |
| 2009Q4 | 42,912 | 42,912 | 0.00% |
| 2012Q3 | 39,034 | 39,034 | 0.00% |
| 2015Q1 | 65,957 | 65,957 | 0.00% |
| 2018Q2 | 49,467 | 49,467 | 0.00% |
| 2021Q4 | 40,731 | 40,731 | 0.00% |
| 2024Q3 | 33,050 | 33,050 | 0.00% |

Ingestion is lossless across all sampled quarters, so the F1 shortfall is a universe
difference (OTC, pink-sheet, non-primary-common issuers absent from the SEP price
panel), not data loss.

**Open decision:** F1 must be re-measured against the TICKERS reference tape as PRD #76
specifies before F0 can return an honest verdict. Amending F1's definition instead would
be threshold retuning after seeing a failure, and is not taken unilaterally.

## What this does and does not claim

### Claims

- Density and spread of insider purchase clusters on the free SEC tape (2006-), measured against floors frozen before any returns existed.
- The floor is derived from Gate-1a's measured dispersion, not chosen for convenience.

### Non-claims

- **No returns were measured.** Stage D counts events; it says nothing about whether insider clusters predict anything.
- Not capital permission; `capital_go` is false by construction.
- Not a reopening of residual, R2-1, PEAD, or CMFT #74.

## How to re-run

```bash
uv run python fixtures/real-continuous/reports/research_cfob.py --pull-only
uv run python fixtures/real-continuous/reports/research_cfob.py --measure-only --write-docs
```
