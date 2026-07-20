# Phase 2 results — fixed-horizon portfolio structure

**Date:** 2026-07-20  
**Driver:** `fixtures/real-continuous/reports/research_phase2.py`  
**Artifact:** `fixtures/real-continuous/reports/phase2-structure.json`  
**Helpers:** `src/invest/application/phase2_report.py`  
**Parent PRD:** #58 · Issue: #62

## Config (frozen provenance)

| Knob | Value |
| --- | --- |
| Scanner | §2.5 naïve (`momentum-naive-§2.5`) |
| Strategy flag | `benchmark` |
| Exit | `fixed-horizon`, horizon_sessions=60 |
| Slots | max_concurrent_positions=20 |
| Admission | seeded-random, seed=42 |
| Primary costs | 5 bps/side, tax_rate=0 (pre-tax) |
| Secondary tax | 0.15 on gains only |
| Fixture span | 2019-01-02 → 2025-12-31 |
| Walk-forward folds | entry-year 2019…2025 (not an untouched 2023–2025 holdout) |

Ranking (Core / ID) is **not** on the accept path.

## Verdict

### **NO-GO**

Predeclared PRD #58 gates:

1. After-cost expectancy **> 0** on a **majority** of walk-forward folds → **PASS** (6/7)
2. FC-segregated (ex-forced-close) book still meets (1) → **PASS**
3. No single calendar year **> ~25%** of total after-cost net profit → **FAIL** (2020 = 85.7%)
4. Random-admission primary path only → **PASS**

Fail reason published: year concentration. Do not treat positive mean expectancy alone as promotion.

## Headline books (pre-tax, 5 bps/side)

| Book | n | Mean exp | Median exp | Hit | Net P&L |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full | 200 | +56.12 | +18.76 | 52.0% | +11,223 |
| Non-FC | 96 | +204.09 | +184.40 | 59.4% | +19,593 |
| FC only | 104 | −80.47 | −24.16 | 45.2% | −8,369 |
| Tax secondary (full) | 200 | +9.72 | +15.94 | 52.0% | +1,943 |

Exit reasons: fixed-horizon 91 · context-position-forced-closed 104 · open-at-end 5.

## Walk-forward folds (entry year)

| Year | n | Mean exp | Median exp | Net P&L |
| ---: | ---: | ---: | ---: | ---: |
| 2019 | 34 | +137.53 | +104.57 | +4,676 |
| 2020 | 30 | +320.63 | +340.10 | +9,619 |
| 2021 | 25 | +62.67 | +34.55 | +1,567 |
| 2022 | 33 | **−290.75** | −103.93 | −9,595 |
| 2023 | 22 | +62.74 | −14.91 | +1,380 |
| 2024 | 28 | +110.72 | +273.46 | +3,100 |
| 2025 | 28 | +17.00 | +9.21 | +476 |

Crash / concentration notes: 2022 is the only negative fold; 2020 dominates total profit.

## Interpretation

1. **Structure is not uniformly dead after costs** under naïve event + fixed 60-session hold + slot lottery — mean and median full-book expectancy are positive, and 6/7 annual folds clear zero.
2. **Edge is not FC-dependent** — the non-FC book is *stronger* than the full book; forced closes *subtract* expectancy here (opposite of Step 1's FC-as-false-edge pattern on the old stop/trail book).
3. **Promotion still blocked** by the year-share gate: ~86% of after-cost profit sits in 2020. That fails the predeclared concentration rule and keeps 2021-style regime risk front and center.
4. **Do not add ranking to rescue** this result (PRD R1/R5). Next research budget should treat Phase 2 as a published negative on *accept-for-promotion*, not as a green light for Quiet Drift / Form-4 spend.
5. **Residual follow-up (Phase 2b):** concentration autopsy under K2/S2 — see `docs/research/phase2-concentration-autopsy.md`. Verdict: **residual_hope die**; pause-default.
6. **Freeze:** hard, event-only, narrow — full rules in the autopsy doc. No ranking / Quiet Drift / DAMB / Form-4 auto-start; re-open only via new PRD.

## How to re-run (sequential)

```bash
# Alone on a 16GB host — no parallel invest-backtest / Gate 1a / Step 3 loads
uv run python fixtures/real-continuous/reports/research_phase2.py
```

Equivalent CLI composition (#61):

```bash
invest-backtest \
  --universe fixtures/real-continuous/bars/universe.json \
  --bars fixtures/real-continuous/bars/bars.json \
  --market-context fixtures/real-continuous/market-context.json \
  --split-date 2023-01-03 \
  --strategy benchmark \
  --exit-policy fixed-horizon \
  --max-concurrent-positions 20 \
  --admission-seed 42 \
  --slippage-bps 5
```

Unit CI must remain free of this multi-GB run; helpers are covered in
`tests/application/test_phase2_report.py`.
