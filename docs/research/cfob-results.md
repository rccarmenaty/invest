# CFOB Stage D + F0 results

**Date:** 2026-07-21  
**Git SHA:** `86d1f595269ed30b3f30c1a0ac2397c0c6688da0`  
**Driver:** `fixtures/real-continuous/reports/research_cfob.py`  
**Artifact:** `fixtures/real-continuous/reports/cfob-structure.json`  
**Parent PRD:** #76 (grilled 2026-07-21)  
**ADR:** `docs/adr/0002-cfob-gate-law-divergence.md`

## Verdict

### **stage_pass**

- stage: `D+F0`
- capital_go: `False` (always false)
- implementability_eligible: `False`
- all hard gates passed: `True`

## Cohort

- raw clusters: `31,294`
- **de-overlapped clusters (gated object)**: `10,394`
- required for MDS bar: `7,246`
- MDS at measured n: `0.0104`

## Qualification counts

- total_rows: `6,852,440`
- qualified: `375,332`
- wrong_code: `6,001,837`
- disposals: `3,625`
- below_size_floor: `404,819`
- stale: `28,228`
- amendment_superseded: `27,487`
- unparseable_value: `11,112`
- late_filed: `9`
- indirect_ownership: `156,768`

## Year shares

- 2006: 0.0397
- 2007: 0.0659
- 2008: 0.0855
- 2009: 0.0390
- 2010: 0.0342
- 2011: 0.0555
- 2012: 0.0380
- 2013: 0.0329
- 2014: 0.0409
- 2015: 0.0523
- 2016: 0.0455
- 2017: 0.0389
- 2018: 0.0579
- 2019: 0.0520
- 2020: 0.0751
- 2021: 0.0431
- 2022: 0.0575
- 2023: 0.0538
- 2024: 0.0397
- 2025: 0.0525

## Gates (D + F0 combined)

- **D1-volume** [hard] **PASS** — de-overlapped clusters=10394 vs floor 7500 (MDS=0.0104 vs bar 0.0125)
- **D2-spread** [hard] **PASS** — years contributing >=2%: 20 vs floor 12
- **D3-concentration** [hard] **PASS** — max year share=0.0855 (2008) vs cap 0.25
- **F0-protocol** [hard] **PASS** — protocol freeze and trial ledger present
- **F1-mapping** [hard] **PASS** — mapping rate=0.9019 vs floor 0.9
- **F2-unmapped-composition** [hard] **PASS** — worst-year unmapped rate=0.1417 (2006) vs 3.0x global 0.0981 = 0.2943
- **F3-reconcile** [hard] **PASS** — parsed counts reconcile against SEC aggregates
- **F4-parse-coverage** [hard] **PASS** — archives parsed=81 vs expected 81
- **F5-derivative-exclusion** [hard] **PASS** — qualified stream is non-derivative only
- **F6-amendment-dedupe** [hard] **PASS** — amendment dedupe measured; original filing date kept as known-time
- **F7-late-filing-share** [hard] **PASS** — late_filed=9 of 375332 qualified (share=0.000024); reported, not capped
- **F8-off-market-price** [info] **PASS** — SEP panel exposes only adjusted open/close; no unadjusted high/low band for off-market-price diagnostic

## Stage F0 detail

- F0 sub-verdict (informational; top-level already combines): `stage_pass`
- reference source: `tickers-reference-cache`
- mapped purchases: `338518`
- total purchases mapped against: `375332`
- ambiguous multi-match: `4950`

## What this does and does not claim

### Claims

- Density, spread, and tape-integrity of insider purchase clusters on the free SEC tape (2006-), measured against floors frozen before any returns existed.
- The density floor is derived from Gate-1a's measured dispersion, not chosen for convenience.
- Purchase-level mapping is a CIK-primary identity join against the Sharadar TICKERS reference, with the frozen tiebreak ladder: exact as-filed symbol → related symbols → sole covering row → ambiguous-excluded, counted (grill 2026-07-21). The as-filed symbol never establishes identity on its own.

### Non-claims

- **No returns were measured.** Stages D/F0 count and integrity-check events; they say nothing about whether insider clusters predict anything.
- Not capital permission; `capital_go` is false by construction.
- Not a reopening of residual, R2-1, PEAD, or CMFT #74.
- The $5 price floor is diagnostic on adjusted closes only (ADR 0002); dollar volume is the binding habitat gate.

## How to re-run

```bash
uv run python fixtures/real-continuous/reports/research_cfob.py --pull-only
CFOB_SEP_DIR=fixtures/full-depth-sep \
  uv run python fixtures/real-continuous/reports/research_cfob.py --measure-only --write-docs
```
