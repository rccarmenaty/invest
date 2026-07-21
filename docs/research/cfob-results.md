# CFOB Stage D + F0 results

**Date:** 2026-07-21  
**Driver:** `fixtures/real-continuous/reports/research_cfob.py`  
**Artifact:** `fixtures/real-continuous/reports/cfob-structure.json`  
**Parent PRD:** #76 (grilled 2026-07-21)  
**ADR:** `docs/adr/0002-cfob-gate-law-divergence.md`

## Verdict

### **kill_line**

- stage: `D+F0`
- capital_go: `False` (always false)
- implementability_eligible: `False`
- all hard gates passed: `False`

## Cohort

- raw clusters: `23,954`
- **de-overlapped clusters (gated object)**: `8,363`
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
- 2007: 0.0529
- 2008: 0.0780
- 2009: 0.0362
- 2010: 0.0314
- 2011: 0.0519
- 2012: 0.0347
- 2013: 0.0286
- 2014: 0.0366
- 2015: 0.0494
- 2016: 0.0452
- 2017: 0.0384
- 2018: 0.0611
- 2019: 0.0540
- 2020: 0.0835
- 2021: 0.0469
- 2022: 0.0647
- 2023: 0.0624
- 2024: 0.0472
- 2025: 0.0639

## Gates (D + F0 combined)

- **D1-volume** [hard] **PASS** — de-overlapped clusters=8363 vs floor 7500 (MDS=0.0116 vs bar 0.0125)
- **D2-spread** [hard] **PASS** — years contributing >=2%: 20 vs floor 12
- **D3-concentration** [hard] **PASS** — max year share=0.0835 (2020) vs cap 0.25
- **F0-protocol** [hard] **PASS** — protocol freeze and trial ledger present
- **F1-mapping** [hard] **FAIL** — mapping rate=0.6849 vs floor 0.9
- **F2-unmapped-composition** [hard] **PASS** — worst-year unmapped rate=0.4498 (2007) vs 3.0x global 0.3151 = 0.9454
- **F3-reconcile** [hard] **PASS** — parsed counts reconcile against SEC aggregates
- **F4-parse-coverage** [hard] **PASS** — archives parsed=81 vs expected 81
- **F5-derivative-exclusion** [hard] **PASS** — qualified stream is non-derivative only
- **F6-amendment-dedupe** [hard] **PASS** — amendment dedupe measured; original filing date kept as known-time
- **F7-late-filing-share** [hard] **PASS** — late_filed=8 of 376382 qualified (share=0.000021); reported, not capped
- **F8-off-market-price** [info] **PASS** — SEP panel exposes only adjusted open/close; no unadjusted high/low band for off-market-price diagnostic

## Stage F0 detail

- F0 sub-verdict (informational; top-level already combines): `kill_line`
- listing window source: `tickers-cache`
- mapped purchases: `257775`
- total purchases mapped against: `376382`
- ambiguous multi-match: `0`

## What this does and does not claim

### Claims

- Density, spread, and tape-integrity of insider purchase clusters on the free SEC tape (2006-), measured against floors frozen before any returns existed.
- The density floor is derived from Gate-1a's measured dispersion, not chosen for convenience.
- Purchase-level mapping uses listing windows (TICKERS first/lastpricedate when available; otherwise SEP first/last session) on filing-date.

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
