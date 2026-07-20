# Adversarial Strategy Debate — Round 3 Shared Brief

**Date:** 2026-07-21  
**Repo:** invest (main @ `6354ef5`)  
**Task:** Stress-test **Full-Stop** and propose the strongest *next program path* after Round 2’s ordered research was **fully executed** and both funded lines **killed**.  
**Role:** You are one of three adversarial judges (seats: **Codex**, **Claude Fable**, **Grok 4.5 High**). Argue hard for YOUR proposal. Attack weak reasoning. Prefer research economics and capital honesty over narrative beauty.

## Why Round 3 exists

Round 2 meta-judge ordered:

1. **R2-0** — residual hard freeze + honest liquid beta capital default  
2. **R2-1** — short-horizon residualized CS reverse kill (Claude) — **EXECUTED → kill_line**  
3. **R2-2** — PEAD F0 only (Codex) — **EXECUTED → kill_line** (no original SF1/SEC tape; fail-closed)  
4. **R2-3** — Form-4 (Grok) — **NOT STARTED** (sequenced after PEAD; dual-exit Full-Stop co-equal)  
5. **R2-4** — Terminal if CS lines die: stop alpha budget; keep honest beta  

After R2-1 and R2-2 kills, a human grill sealed **Full-Stop** on the CS alpha research budget (ADR-0001 + `docs/research/full-stop-seal.md`).  

This debate is an **event-only re-open of the decision process** (allowed). It is **not** automatic permission to spend on Form-4, PEAD tape, or residual rescue. Your job is to argue what should happen **now**: hold Full-Stop, productize beta, explicitly re-open a named line with density/feasibility first, or another path that does not launder residual theater.

## Binding law (must internalize)

### Residual (unchanged)
- **Hard freeze / narrow freeze** on naïve event → fixed-horizon → slot-lottery portfolio residual  
- residual_hope **DIE** (K2/S2); year concentration NO-GO (2020 ≈ 85.7%)  
- Gate 1a PASS is **not** go-live  

### Round 2 funded outcomes
| Line | Verdict | Source |
|---|---|---|
| R2-1 xs-reversal-lp | **kill_line** | `docs/research/xs-reversal-results.md` |
| R2-2 PEAD F0 | **kill_line** | `docs/research/pead-f0-results.md` |

**R2-1 headline:** n=404 formations; residualized B−T mean ~0.19%, median > 0, clustered t ≈ **1.43** (G1 need ≥ 3.0 **FAIL**); year share ≈ **44%** (G3 **FAIL**); mean-spread net at 10 bps ≤ 0; buffering not modeled (G7 fail-closed); capital_go always false.

**PEAD F0 headline:** D0 pass (protocol+ledger); D1–D7 **fail-closed unmeasured** — no SF1/SEC original-as-published tape wired (`live_audit_capable=false`). Not a returns null; a **data-object absence** null. Returns never measured. E1 not started.

### Full-Stop seal (current default until this debate + human accept a change)
Source: `docs/research/full-stop-seal.md`, `docs/adr/0001-full-stop-cs-alpha.md`, `CONTEXT.md`

| Axis | Call |
|---|---|
| Strength | CS alpha **budget** kill (broader than a single line program kill) |
| Capital | **Honest liquid beta** only |
| Allowed | **Non-claim engineering** only |
| Forbidden without event-only re-open | New CS lines; PEAD tape-for-alpha; Form-4 F0; residual rescue/ranking/DAMB; curiosity re-runs |
| End | Event-only re-open (new PRD + grill + named hypothesis) |

**Glossary distinctions:**  
- **Program kill** = end of *one* line  
- **Full-Stop** = end of CS alpha *budget*  
- Do not conflate them  

## System (what exists)

- Same stack as Round 2: PIT Sharadar SEP+ACTIONS+TICKERS, fixed-horizon, random admission, event-study excess, Phase 2 / 2b / R2-1 / PEAD F0 pure helpers + drivers  
- R2-1 pure CS reverse helpers + continuous measurement artifact  
- PEAD F0 pure data gates + fail-closed probe (no SF1 adapter)  
- **No** production Form-4 / SEC ownership PIT tape  
- **No** original-as-published SF1/SEC fundamentals tape  

## Settled history (do not re-argue as open)

You must treat as **binding**, not re-runnable without a new PRD:

0–7 from Round 2 brief still hold (Core failure, FC audit, event study, Gate 1a PASS, Phase 2 NO-GO, residual DIE).  

**Plus R2 execution:**
8. R2-1 kill_line (gross t fail, concentration fail, net/buffering honesty fail-closed gaps)  
9. PEAD F0 kill_line (data object not proven; fail-closed)  
10. Human Full-Stop seal on CS alpha budget  

Forbidden: inventing numbers; claiming R2-1 “almost passed”; treating PEAD F0 unmeasured as “data pending so keep spending”; reopening residual with knobs; ranking/Quiet Drift/DAMB packaging; auto-starting Form-4 because it was third in the meta order.

## Research principles (updated)

1–9 from Round 2 still apply where relevant.  

**New for Round 3:**
10. Full-Stop is a **valid success** for research process, not a failure of courage  
11. Capital allocation ≠ alpha research; do not dress beta productization as a discovered edge  
12. If you re-open any CS line, you must pay **density/feasibility first** and name **dual-exit** (kill/Full-Stop as success)  
13. Opportunity cost of engineering weeks before a falsifiable number is first-class evidence  

## Hard constraints for proposals

- Implementable on this stack **or** explicit feasibility/density gate before tape build  
- Falsifiable acceptance/rejection gates  
- Cite external research (arXiv/NBER/journal) for economic mechanism when proposing alpha; cite portfolio/allocation literature when proposing capital product  
- Must survive: costs, year concentration family law (~25%), median-vs-mean lessons, matched-SPY lesson, multiple testing, R2-1 kill, PEAD F0 kill, Full-Stop law  
- Forbidden: inventing measurements; residual rescue; silent Full-Stop override  
- Prefer proposals that treat **R2-1 kill + PEAD F0 kill + residual DIE + Full-Stop** as **joint** evidence  

## Required output structure (strict)

# Proposal title

## Thesis (1 paragraph)
## Mechanism (why this path is correct economically / process-wise)
## Literature anchors (3–8 citations with arXiv/DOI/URL + one-line relevance)
## Concrete program design (capital, research, engineering — what happens in what order)
## How it differs from Round 2 meta-order and from the current Full-Stop seal
## Why settled results (Steps 0–10) predict this is right
## Why it might fail (steelman opposition)
## Measurement / decision plan (ordered steps; what is *not* measured)
## Acceptance / rejection gates (including how Full-Stop is held or re-opened)
## Implementation cost on this repo (files / modules / data / product work)
## Confidence (0–100) and single sharpest risk

Then:

## Attacks on the other two archetypes

Attack these alternative directions (even if you like parts of them):

A) **Hold Full-Stop + productize honest liquid beta** — stop CS alpha; capital is allocation  
B) **Explicit re-open PEAD** — fund SF1/SEC original-as-published tape + measured F0 → E1 only if pass  
C) **Explicit re-open Form-4** — density math → ownership F0 → filing-time study; dual-exit Full-Stop  
D) **Residual rescue** — always attack as most dangerous false-confidence path  

Argue which archetype is most dangerous *now*.

## Final one-liner
What would you bet the next *calendar quarter* of budget on, and what single decision or experiment proves or kills that bet?

---

## Judge independence rules

1. Draft YOUR proposal from **this brief** + mandatory result/seal docs **before** reading other Round-3 judges’ files.  
2. **Mandatory reads** (use tools):  
   - this file  
   - `docs/research/xs-reversal-results.md`  
   - `docs/research/pead-f0-results.md`  
   - `docs/research/full-stop-seal.md`  
   - `docs/adr/0001-full-stop-cs-alpha.md`  
   - `CONTEXT.md` (glossary)  
   - Optional for depth: `docs/research/gate1a-results.md`, `phase2-results.md`, `phase2-concentration-autopsy.md`  
   - Optional: Round 2 meta-judge only (not other seats until Attacks): `docs/research/adversarial-debate/round-2/outputs/meta-judge-verdict.md`  
3. Do **not** read `round-3/outputs/proposal-*.md` written by other seats while drafting.  
4. After drafting, optional: revise only **Attacks** if other R3 proposals exist.  
5. Write the full proposal to the path given in your seat prompt. Do **not** edit trading code or reverse Full-Stop in repo files — argue in the proposal only.  
6. No invented backtest numbers.

## Seats (user-specified lineup)

| Seat | Output path |
|---|---|
| Claude Fable | `docs/research/adversarial-debate/round-3/outputs/proposal-claude-fable.md` |
| Codex GPT-5.6 Sol | `docs/research/adversarial-debate/round-3/outputs/proposal-codex-gpt56-sol-xhigh.md` |
| Grok 4.5 High | `docs/research/adversarial-debate/round-3/outputs/proposal-grok-45-high.md` |

Meta-judge is a **separate** later step; seats do not write the meta verdict.
