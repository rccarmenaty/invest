# Meta-Judge Verdict — Adversarial Strategy Debate

**Judge:** Grok (meta, not a competing proposal author)  
**Date:** 2026-07-20  
**Inputs:**
- `proposal-claude-fable.md` — Quiet Drift (Claude Fable)
- `proposal-grok-45-high.md` — DAMB (Grok 4.5)
- `proposal-codex-gpt56-sol-xhigh.md` — Opportunistic Insider Clusters (Codex GPT-5.6 Sol)

**Ground rules for this verdict:** No invented backtest numbers. Prefer falsification order and research economics over narrative beauty. Steps 0–3 evidence is binding.

---

## One-paragraph decision

Spend the next research dollar on Claude’s **Q1 kill test** (h60 excess-vs-universe on the existing 12,295-signal cohort; optional ID quintile split in the same pass). Do **not** start DAMB’s multi-knob chassis or Form-4 engineering until that measurement exists. If Q1 fails (no excess drift), kill Quiet Drift and any pure “hold longer” Core rescue; treat DAMB as unproven beta dressing unless it can beat SPY after costs with a frozen, minimal parameter set; **then** open Codex’s Form-4 track only after a data feasibility audit. If Q1 passes and ID is monotone, implement Quiet Drift’s ranked fixed-horizon portfolio next. If Q1 passes but ID is not monotone, ship the **unranked** fixed-horizon / no-price-stop control (honest archetype A), not a new composite.

---

## Scorecard

| Criterion | Quiet Drift (Claude) | DAMB (Grok) | Insider Clusters (Codex) |
|---|---|---|---|
| Fits Steps 0–3 evidence | Strong | Strong on path; weaker on selection stack | Strong on “ranking dead”; leaves price path |
| Economic mechanism | Good (DGW underreaction) | Good (TSMOM/crash lit) but equity transfer weak | Best of three (informed costly action) |
| Falsifiability / kill speed | **Best** (~1 day, no engine) | Medium (ordered E1–E5, many cells) | Slow until PIT tape exists |
| Overfit surface | Low if gates frozen | **High** (gate + trails + proximity + vol + slots) | Low on signal; high on data plumbing |
| Implementation cost | Lowest | Medium (config + exits + gate) | Highest (new SEC tape) |
| Stated confidence | 40 | 58 | 63 |
| My adjusted confidence | **45** on process; **30** on edge | **35** as package; **50** on modules | **40** on edge after filing lag; **70** on design quality |
| Main failure mode | Drift is beta | Green beta + market gate theater | Filing-time alpha already gone |

---

## What each got right

### Claude — Quiet Drift
1. Correctly reads Step 2 + Step 3: long drift, thin CS residual, ranking subtracts value, tight stops tax noise.
2. Best research discipline: **measure h60 excess before writing a strategy class**.
3. Correct trade-structure move: no price stop, fixed horizon, inverse-vol / concurrency for risk.
4. Correct attribution rule: beta-separate, FC out of alpha books.
5. Right danger ranking for *generic* regime gates (few independent regimes in 2019–2025).

### Grok — DAMB
1. Correct diagnosis that Core is not a stock-picking system when residual CS alpha is thin.
2. Correct mandatory modules: kill fixed +2×ATR TP; lengthen hold; vol scale for crash windows; do not invent ranking theater.
3. Correct that E1-style “fix path on the naïve control alone” must happen before new selection science.
4. Correct that SPY buy-and-hold is a required competitor, not an afterthought.

### Codex — Insider clusters
1. Correct strategic fork: if price residual is thin, **change the information source**, not the ranker.
2. Best protocol hygiene: bitemporal known_time, code-P honesty, delisting/Shumway, capacity-weighted reject, family-wise testing, next-open only.
3. Best attack on Quiet Drift’s ID adaptation (DGW is not “60d ID on spike cohort + gap penalty + 52w”).
4. Best attack on DAMB’s package (E1 confounded; many knobs; market gate can mint green beta).
5. Mechanism predictions are sharp (opportunistic > routine, cluster > single) — science-grade.

---

## What each got wrong (or overclaimed)

### Quiet Drift
- **ID on a spike-conditioned sample is not DGW.** Codex is right: formation window, double-sort design, and residual ID variation after a discrete event day are unresolved. Gate must treat “ID fails, unranked fixed-hold still has excess” as a *success for A*, not a license to retune ID lookbacks.
- Gap penalty + 52w tiebreak + quintile cut + {40,60,80} horizon is already a small search family; keep Q4 tiny or it becomes archetype B.
- Confidence 40 is honest; do not treat thesis as preferred because process is clean.

### DAMB
- **E1 is not a clean horizon experiment.** Retaining structural price stop while removing TP and adding trail + time stop confounds the Step-2 object (stop-free collection of slow drift). A clean A test is: no price stop, no TP, fixed T+60 (or predeclared time stop only).
- Hard SPY 200DMA as a *primary* selection layer with ~two bad regimes in sample is the highest false-confidence path among the three packages. Vol scaling can stay; hard entry gate must be demoted until a no-gate book already has trade-level after-cost expectancy.
- “Capital rationing by 52w proximity” is ranking when slots bind — say so, and require a random-admission control (Claude’s Q3 idea is better science).
- TSMOM literature is futures-heavy; equity single-name after costs is the unpaid debt of the thesis.

### Insider clusters
- **Highest opportunity cost.** Weeks of SEC/vendor work can starve the one-day measurement that still decides whether *any* price-event path lives.
- Filing-time decay is not a footnote; it may be the entire story post-SOX / alt-data era.
- “Stop optimizing Core” is right as strategy, wrong as sequencing if it delays free diagnostics on data already in-repo.
- Capacity and liquid-subset gates are necessary; without them this becomes classic small-cap mirage.

---

## Cross-proposal synthesis (what the evidence actually demands)

Binding facts from Steps 0–3:

1. Short path ≈ noise; ±1R race ≈ coin flip → tight stops are tax.
2. Raw multi-month drift exists on the accepted event stream.
3. Measured CS excess is thin (h20 +0.36%, t≈1.78).
4. Core ranking loses to naïve spike OOS.
5. FC profit is policy artifact.
6. 2023–2025 is burned; walk-forward + deflated testing only.
7. 2022–2025 matrix produced **no** valid multi-year P&L (fail-closed).

Implications:

- **Mandatory diagnostic (all camps):** measure **h60 (and h120 flagged) excess vs same-date universe** on the existing cohort. Everyone is arguing without this number.
- **Mandatory structure fix if any price event survives:** no fixed TP; stop path that samples short noise; longer capital occupancy with portfolio-level risk, not 1×ATR micro-trades.
- **Forbidden near-term research:** composite ranking overhaul (archetype B); regime gate as first lever on a negative-expectancy Core (archetype C alone).
- **Strategic fork after Q1:**  
  - excess fails → abandon price-breakout edge research; only then prioritize new information source (Form 4) or full stop.  
  - excess passes → fixed-horizon portfolio; ranking only if a *single* predeclared feature is monotone (ID or 52w alone), else unranked.

---

## Ordered research program (what I would fund)

### Phase 0 — Ops (blocks provenance)
Commit streaming loader / replay integrity if still WIP. Sequential fixture runs only.

### Phase 1 — Free kill (1–2 days) — **Claude Q1 core**
On existing Step-2 cohort:
1. h60 / h120 excess vs same-date eligible universe (clustered t; yearly folds; FC fate separate).
2. Optional same pass: ID quintiles + 52w quintiles (frozen definitions; no grid).

**Gate 1a:** h60 excess > 0 with clustered t ≥ 2.5 (or predeclared equivalent).  
**Fail →** kill Quiet Drift as strategy; kill pure A as alpha claim; open Phase 3 (Form 4) *or* declare no price-event program.  
**Pass →** Phase 2.

**Gate 1b (only if 1a passes):** ID top−bottom h60 excess monotone-ish, t ≥ 2.0.  
**Fail 1b / pass 1a →** unranked fixed-horizon only (no Quiet Drift ranker).  
**Pass both →** Quiet Drift Q2/Q3 path.

### Phase 2 — Clean structure test (only if Gate 1a passes)
**Not DAMB E1 as written.** Use:

| Arm | Selection | Exit | Ranking |
|---|---|---|---|
| C0 | §2.5 naïve | current structural + TP | none |
| C1 | §2.5 naïve | **no price stop, no TP, exit open T+60** | none |
| C2 | §2.5 naïve | C1 mechanics | random admission under 20-slot cap |
| C3 | only if Gate 1b | C1 mechanics | frozen ID (or frozen 52w alone) |

Accept only if after-cost expectancy > 0 on majority of walk-forward folds **and** beats matched-exposure SPY/IWM on risk-adjusted terms **and** FC-segregated.  
**Do not** add SPY 200DMA until C1 already clears trade-level expectancy. Then add gate as **one** ablation.

### Phase 3 — New information source (Codex) — **parallel only after Gate 1a fails, or sequential after Phase 2 settles**
1. Data feasibility audit (Sharadar insider vs SEC raw): timestamps, amendments, code-P venue, delistings.
2. If audit fails → stop; do not code a scanner on fantasy PIT.
3. If audit passes → freeze protocol, build tape, **position-blind next-open +60 event study** before any portfolio optimizer.
4. Mechanism orderings must hold (opportunistic cluster > routine; multi-buyer > single).

---

## Ranking of the three proposals as *research programs*

| Rank | Proposal | Role |
|---:|---|---|
| 1 | **Quiet Drift process (not full thesis)** | Immediate funded path: Q1 + unranked/ranked fixed-horizon |
| 2 | **Insider clusters** | Best true pivot if price residual dies or after Phase 2; highest data bar |
| 3 | **DAMB as package** | Reject as primary program; **harvest modules** (no TP, vol scale, SPY benchmark, trial ledger) into Phase 2 |

### Danger ranking (this project, now)
1. **DAMB-as-shipped package** — green beta + regime gate + confounded exits (Codex’s “most dangerous” is correct for this instantiation of C).  
2. **Composite ranking overhaul** — still the classic overfit factory if anyone reopens it.  
3. **Quiet Drift without Gate 1a** — honest process risk if people skip to engine work.  
4. **Form 4 before data audit** — engineering sinkhole.

---

## Final capital-research bet

**I would not bet production capital on any of the three.**  

**I would bet the next research budget on:**

> Extend the existing event study to **h60 excess-vs-universe** (and ID/52w quintiles in one frozen pass).  
> If excess is real, implement **stop-free fixed 60-session** portfolio on the naïve event with random-admission control; add ranking only if one feature is monotone.  
> If excess is dead, stop patching Core and open **Form-4 opportunistic cluster** only after a PIT data audit.

**Single experiment that decides the next month of work:**  
**Phase 1 Gate 1a — h60 excess vs same-date universe on the Step-2 cohort.**

---

## Status of debate seats

| Seat | Artifact | Status |
|---|---|---|
| Claude Fable | `proposal-claude-fable.md` | Complete |
| Grok 4.5 | `proposal-grok-45-high.md` | Complete |
| Codex GPT-5.6 Sol | `proposal-codex-gpt56-sol-xhigh.md` | Complete |
| Meta-judge | this file | Complete |
