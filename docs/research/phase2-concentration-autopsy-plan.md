# Phase 2b — Concentration autopsy (frozen plan)

**Date frozen:** 2026-07-20  
**Status:** Shared understanding confirmed (grill-with-docs).  
**Parent:** Phase 2 NO-GO — `docs/research/phase2-results.md` · PRD #58 · artifact `fixtures/real-continuous/reports/phase2-structure.json`  
**Glossary:** `CONTEXT.md` (promotion block, concentration autopsy, K2, S2, pause-default)

## Why this exists

Phase 2 failed **year concentration** (2020 ≈ 85.7% of after-cost net profit) while passing majority walk-forward folds and FC-segregated expectancy. That is a **promotion block**, not a program kill.

This residual experiment is the **single** allowed follow-up. It asks whether residual structure after dropping 2020 is economically real, or a thin leftover / equity beta. It does **not** re-open ranking, Quiet Drift, DAMB-as-package, or Form-4 spend.

## Classification (locked)

| Term | Decision |
| --- | --- |
| Phase 2 NO-GO | **Promotion block** (B) |
| Residual experiment | **Concentration autopsy** only |
| Residual hope bar | **K2 — economic bar** |
| Equity comparator | **S2 — trade-window SPY** |
| After report | **P2 — pause-default** |
| Delivery | Plan doc (this file) + **one** implementation ticket |

## Frozen knobs (do not retune)

Reuse Phase 2 provenance as published:

| Knob | Value |
| --- | --- |
| Source book | `phase2-structure.json` trades (n=200) |
| Scanner | §2.5 naïve / `benchmark` |
| Exit | fixed-horizon, horizon_sessions=60 |
| Slots / admission | max_concurrent=20, seeded-random, **seed=42** |
| Primary costs | 5 bps/side, tax_rate=0 (pre-tax) |
| Leave-out year | **2020** (peak profit year from Phase 2 gate) |
| Equity proxy | **SPY** (not in continuous universe — **sidecar required**; research driver uses Yahoo chart opens, committed as `spy-opens-sidecar.json`) |
| Ranking | **off** the accept path |

## Measurement (implementation contract)

### Prefer post-process

1. **Leave-2020 book** — closed trades with `entry_date` year ≠ 2020. Drop `open-at-end` from expectancy books if Phase 2 helpers already exclude them; stay consistent with `phase2_report` / published full-book mean.
2. **Recompute with existing pure helpers** where possible (`summarize_book`, fold-by-entry-year, FC segregation) at **5 bps / tax 0**.
3. **Half-mean denominator** — published full-book mean expectancy from the **same** artifact (`after_cost_pre_tax.mean_expectancy`, currently ≈ +56.12). Do **not** re-estimate a new full book as the bar.
4. **S2 trade-window SPY** — for each leave-2020 **closed** trade (include FC exits; still report FC-segregated tables separately):
   - Window: **entry fill open → exit fill open** (match fixed-horizon next-open semantics).
   - Matched SPY P&L = SPY open-to-open return over that window × trade notional (`qty * entry_price` after the same cost convention used for trade nets, or document exact notional if helpers already define one).
   - Per-trade excess = trade after-cost P&L − matched SPY P&L.
   - S2 metric = **mean** per-trade excess on the leave-2020 closed set.
5. **No multi-GB continuous re-backtest** required for leave-2020 / folds / half-mean. Unit CI must stay free of full fixture loads. SPY sidecar may be a small series file under fixtures/reports, not a second 1.3GB bars pull in CI.

### Explicitly out of scope

- Core / ID / any ranking admission  
- New exit policies, stops, trails, TP  
- DAMB package (200DMA gate, trail grids, vol-target search)  
- Multi-seed lottery sweeps (unless a later explicit re-open)  
- Moving the Phase 2 year-share **promotion** gate (~25%)  
- Form-4 engineering  
- Treating residual survival as GO for promotion  

## K2 — residual hope verdict

Emit `residual_hope: die | survive` (never `go` / never promotion).

**Dies** if **any** of:

1. Leave-2020 mean after-cost expectancy **≤ 0**, or  
2. Leave-2020 mean after-cost expectancy **≤ ½ ×** published full-book mean, or  
3. Among remaining entry-year folds (2019, 2021–2025), **majority** do **not** have mean exp **> 0**, or  
4. S2 mean (trade after-cost P&L − matched SPY P&L) **≤ 0**.

**Survives** only if all four clear. Survival = still **promotion-blocked** under Phase 2 year concentration.

### Notes on metrics

- Do **not** re-apply the 25% net-profit year-share gate to the leave-2020 residual net (crash years make residual-net share pathological). Concentration for promotion remains the original Phase 2 gate on the full book.
- FC segregation is **reported**, not a second residual accept path. S2 primary set includes FC exits on leave-2020 closed trades.

## Pause-default (after report)

| Outcome | Default next budget |
| --- | --- |
| `residual_hope: die` | **Pause** price-event portfolio residual work. Form-4 PIT audit only if explicitly re-opened. |
| `residual_hope: survive` | Still promotion-blocked. Default **pause**. New concentration-policy PRD only if explicitly re-opened. No ranking / Quiet Drift / DAMB auto-start. |

## Deliverables

| Artifact | Path |
| --- | --- |
| This plan (science freeze) | `docs/research/phase2-concentration-autopsy-plan.md` |
| Results write-up | `docs/research/phase2-concentration-autopsy.md` |
| JSON report | `fixtures/real-continuous/reports/phase2-concentration-autopsy.json` |
| Pure helpers + unit tests | extend `src/invest/application/phase2_report.py` (or sibling module) + `tests/application/` |
| Driver (optional thin script) | `fixtures/real-continuous/reports/research_phase2_autopsy.py` |
| SPY sidecar | small series usable offline; document acquisition; not full continuous bars |

## Acceptance for the implementation ticket

1. Unit tests lock K2 evaluation on synthetic trades (half-mean, fold majority, S2 excess ≤ 0 kills; all clear → survive).  
2. Post-process of committed `phase2-structure.json` produces JSON + markdown with provenance, leave-2020 book stats, fold table, S2 summary, `residual_hope`.  
3. No ranking path; no full continuous re-run in CI.  
4. README / research index links the autopsy results next to Phase 2.

## Expected directional hint (non-binding)

Leave-2020 net ≈ full net − 2020 net ≈ +1.6k on ~170 trades → mean ~+9 vs half of ~+56 → **half-mean kill is likely**. That is a hypothesis for the implementer, **not** a substitute for running K2.
