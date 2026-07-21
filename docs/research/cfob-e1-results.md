# CFOB Stage E1 results — insider purchase-cluster event study

**Date:** 2026-07-22  
**Git SHA:** `99861ca3658763de310668ee574b83a40152f686`  
**Driver:** `fixtures/real-continuous/reports/research_cfob.py --e1`  
**Artifact:** `fixtures/real-continuous/reports/cfob-e1.json`  
**Parent PRD:** #76 (grilled 2026-07-21; E1 separately authorised)  
**ADR:** `docs/adr/0002-cfob-gate-law-divergence.md`

## Verdict

### **kill_line**

- capital_go: `False` (always false)
- implementability_eligible: `False`
- all hard gates passed: `False`

## Cohort

- de-overlapped clusters (input): `10,394`
- measured events (realized n): `10,218`
- MDS at realized n: `0.0105` (bar 0.0125)
- exclusions: `{'incomplete_horizon': 169, 'no_entry_session': 7, 'no_placebo_candidates': 0, 'matched_spy_window_missing': 0}`

## Primary measurement (h60, placebo-differenced, net of cost)

| Rung | Mean | Clustered t | Median (diagnostic) |
|---|---|---|---|
| 10bps | +0.01821 | 6.536 | -0.00116 |
| 25bps **(primary)** | +0.01521 | 5.460 | -0.00416 |
| 50bps | +0.01021 | 3.665 | -0.00916 |

- raw gross excess: mean `+0.01093`, clustered t `3.816`, median `-0.00547`, hit rate `0.488`
- placebo null: draws `100`, seed `20260722`, placebo mean `-0.00928`, observed percentile `1.00`
- winsorized (1/99) primary: mean `+0.01073`, clustered t `4.519`
- matched SPY (net, primary rung): mean diff `+0.01133`, t `2.740`, n `10,218`, missing `0`
- contribution: max year share `0.3103`, max month share `0.1166` (month is diagnostic)

### Contribution by entry year (share of positive total, primary rung)

- 2009: `+51.76` (share `0.310`)
- 2020: `+42.25` (share `0.253`)
- 2018: `+17.92` (share `0.107`)
- 2016: `+8.72` (share `0.052`)
- 2008: `+8.22` (share `0.049`)
- 2007: `+7.62` (share `0.046`)

## Secondary diagnostics (never promotable to primary)

- h20 gross excess: mean `+0.00733`, t `4.725`, n `10,218` (incomplete `0`)
- h120 gross excess: mean `+0.01531`, t `3.458`, n `10,073` (incomplete `145`)
- $10M house band gross excess: mean `+0.00833`, t `2.236`, n `5,454`

## Gates

- **E1-power** [hard] **PASS** — MDS=0.010526 at realized n=10218 vs bar 0.0125
- **E1-placebo-t** [hard] **PASS** — placebo-differenced clustered t=5.4595 vs floor 3.0 (primary at 25.0 bps)
- **E1-trimmed-t** [hard] **PASS** — winsorized (1%/99%) clustered t=4.5193 vs floor 2.0
- **E1-year-concentration** [hard] **FAIL** — max year contribution share=0.3103 vs cap 0.25
- **E1-spy-beat** [hard] **PASS** — mean net return minus matched SPY window=0.011334 (must be > 0)
- **E1-month-concentration** [info] **PASS** — max month contribution share=0.1166 (diagnostic; no month-share bound frozen in PRD #76)

## What this does and does not claim

### Claims

- One pre-registered event study on the de-overlapped D+F0 cohort: h60 open-to-open excess vs the same-entry-date habitat-eligible-universe mean, measured against the within-ticker date-shuffled placebo null, net of the frozen cost ladder.
- The placebo isolates timing: firms are preserved, dates are shuffled, so cohort composition cannot manufacture the primary statistic.

### Non-claims

- Not capital permission; `capital_go` is false by construction.
- No secondary band, horizon, or diagnostic can promote itself to primary.
- Not a reopening of residual, R2-1, PEAD, or CMFT #74.
- A kill or underpowered-stop re-seals Full-Stop immediately (grill Q8; `docs/research/full-stop-seal.md`).

## Decisions the PRD did not settle (flagged, not silently chosen)

- **SPY source**: SEP has no ETFs and SFP is not entitled (re-probed at run time: zero rows). Matched-SPY uses real SPY opens via the Yahoo chart API per the Phase-2b precedent, dividend/split-adjusted like SEP `open_adj`, committed sidecar, provenance in the artifact.
- **Cost application**: the round-trip cost is charged to the traded (event) leg only; the placebo leg stays gross. A cost-symmetric placebo would cancel and make the frozen 10/25/50 ladder vacuous on the primary gate.
- **Month-share**: the PRD names 'a month-share bound' with no frozen number; it is reported as a diagnostic, never gated.
- **Delisting truncation**: events whose h60 window is not fully covered are excluded and counted (`incomplete_horizon`), the reused Gate-1a full-window convention; placebo candidates obey the same rule, so the differencing does not inherit a one-sided bias.

## How to re-run

```bash
CFOB_SEP_DIR=fixtures/full-depth-sep CFOB_TAPE_DIR=<tape-cache> \
  uv run python fixtures/real-continuous/reports/research_cfob.py --e1 --write-docs
```
