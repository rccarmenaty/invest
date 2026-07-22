# CMP opportunistic Form-4 baseline — Stage C+D results

**Date:** 2026-07-22  
**Git SHA:** `d2c0ea7107ec811774d4cc4e08abecb5c0bbfe36-dirty`  
**Driver:** `fixtures/real-continuous/reports/research_cmp.py`  
**Artifact:** `fixtures/real-continuous/reports/cmp-structure.json`  
**Parent PRD:** #79 (grilled 2026-07-22)  
**ADR:** `docs/adr/0003-cmp-opportunistic-baseline-path.md`

## Verdict

### **underpowered_stop**

- stage: `C+D`
- capital_go: `False` (always false)
- implementability_eligible: `False`
- all hard gates passed: `False`

## Cohort (opportunistic primary)

- raw opportunistic events: `26,328`
- universe-eligible opportunistic: `10,307`
- **de-overlapped opportunistic (gated object)**: `5,842`
- required for MDS bar: `7,246`
- MDS at measured n: `0.0139`

## Classification counts

- total_purchases: `338,518`
- opportunistic: `42,934`
- routine: `83,343`
- unclassified: `212,241`
- opportunistic_events: `26,328`
- routine_events: `52,443`

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

## Year shares (de-overlapped opportunistic)

- 2007: 0.0017
- 2008: 0.0366
- 2009: 0.0630
- 2010: 0.0512
- 2011: 0.0642
- 2012: 0.0481
- 2013: 0.0466
- 2014: 0.0483
- 2015: 0.0664
- 2016: 0.0512
- 2017: 0.0551
- 2018: 0.0657
- 2019: 0.0539
- 2020: 0.0729
- 2021: 0.0507
- 2022: 0.0661
- 2023: 0.0570
- 2024: 0.0484
- 2025: 0.0529

## Gates (C + D combined)

- **C1-parse** [hard] **PASS** — archives parsed=81/81; reconcile ok
- **C2-map** [hard] **PASS** — mapping rate=0.9019 (338518/375332) vs floor 0.9
- **C3-class** [hard] **PASS** — opportunistic=42934 (events=26328); routine=83343 (events=52443); unclassified=212241; primary=opportunistic only
- **C4-protocol** [hard] **PASS** — protocol freeze and trial ledger present; primary=CMP opportunistic
- **D1-volume** [hard] **FAIL** — de-overlapped opportunistic events=5842 vs floor 7500 (MDS=0.0139 vs bar 0.0125)
- **D2-spread** [hard] **PASS** — years contributing >=2%: 18 vs floor 12
- **D3-year-mass** [hard] **PASS** — max year event share=0.0729 (2020) vs cap 0.25
- **D4-mds** [hard] **FAIL** — MDS=0.0139 at n=5842 vs bar 0.0125

## Dual-exit interpretation

**Stage C stage_pass** — tape parse/reconcile, CIK mapping (≥90%), PIT classification (full non-derivative trade history), and protocol freeze all clear. CMP object is measurable on free SEC tape without SF1/SF2.

**Stage D underpowered_stop** — after habitat filter and first-wins h60 de-overlap, **5,842** opportunistic events remain vs the **7,500** floor (MDS **1.39%** > **1.25%** bar). Year spread and year-mass pass. Per PRD #79: **no E1**, **no floor retune**, **no GP on this object**, Full-Stop default resumes.

Unclassified purchases remain the majority under the three-year prior-activity rule; that thins opportunistic density relative to raw code-P volume and is expected, not a bug.

## What this does and does not claim

### Claims

- Point-in-time CMP opportunistic vs routine classification on free SEC Form-4 tape.
- Density/power of de-overlapped opportunistic purchase events against floors frozen before any returns.

### Non-claims

- **No returns were measured** at Stage C+D (E1 needs human go + `--e1` after C+D pass).
- Not purchase-cluster rescue (#76 kill_line stands).
- Not capital permission; `capital_go` is false by construction.
- Not genetic/symbolic search.
- Not a licence to loosen density floors post-hoc after underpowered_stop.

## How to re-run

```bash
uv run python fixtures/real-continuous/reports/research_cmp.py --pull-only
CFOB_SEP_DIR=fixtures/full-depth-sep \
  uv run python fixtures/real-continuous/reports/research_cmp.py --measure-only --write-docs
```
