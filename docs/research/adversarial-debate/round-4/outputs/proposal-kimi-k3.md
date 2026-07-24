# Round 4 — kimi-k3: Density-First Serialized Re-open (Form-4 memo kills before SF1 engineering)

**Seat:** kimi-k3 · **Date:** 2026-07-21 · **Mandate:** event-only re-open, paid Sharadar, dual-exit culture.

## Thesis

The re-open is legitimate, but the binding constraint is not ideas — it is the sequencing of *cheap kills before expensive builds*. Every prior line in this repo died or froze at the point where engineering ran ahead of a measurable falsifier. Round 4 must invert that: run the cheapest falsifier of each new information family first, in strict sequence, and let two sequential honest kills re-seal Full-Stop without shame. Concretely: **inventory → Form-4 density memo (days, no returns) → SF1 PEAD F0 integrity remeasure (weeks, no returns) → exactly one E1** for whichever family survives with the better density/integrity posture. The meta-synthesis runs PEAD-integrity ∥ Form-4-density in parallel; I attack that below. Parallel is how this repo burns a quarter. Serialize, cheapest falsifier first.

## Capability inventory (first)

What exists and is directly reusable — this determines marginal cost per line:

| Asset | State | Reuse for |
| --- | --- | --- |
| `sharadar_market_data.py` / `sharadar_actions.py` / `sharadar_tickers.py` | Wired (SEP, ACTIONS, TICKERS) | Adapter pattern is uniform: httpx + pydantic datatable + cursor pagination (`next_cursor_id`, MAX_PAGES 512) + retry/backoff + strict row validation. SF1/SF2/SF3 readers are mechanical clones of this shape, not new architecture. |
| SEP closeadj + TICKERS listed/delisted + ACTIONS splits/delisting | Wired | Liquid-universe ADV filter, delisting-honest membership, matched-SPY windows (S2) — the density and E1 gates for *both* SF1 and SF2 lines. |
| `research_pead_f0.py` + D0–D7 pure gates + protocol freeze (revenue-confirmed GAAP surprise, no analyst SUE) | Exists, fail-closed | Only the *tape source* is missing. Gate logic, ledger, `--write-docs` artifact pattern already built. Marginal cost of PEAD F0 remeasure = SF1 AR-dimension reader + known-time audit only. |
| R2-1 gate stack (clustered t, deflated Sharpe, year-share ≤25%, month-share ≤20%, costs 5/10/25bps, placebo) | Built, published | Any E1 inherits frozen gates verbatim. No new gate science allowed — that is the anti-rescue mechanism. |
| Phase-2 structure harness (fixed-horizon h60, seeded-random admission, FC-segregated book) | Built, published negative | E1s run as *event studies* (Gate-1a style: h60 excess vs same-date eligible-universe mean, clustered inference), **not** portfolio promotion. The portfolio harness stays off the accept path. |
| 16GB host, sequential-run law ("no parallel multi-GB loads") | Operational | Empirical argument against the meta's parallel A/B tracks — the machine itself enforces serialization. |
| Env `NASDAQ_DATA_LINK_API_KEY`; probe showed `nasdaq_api_key_present=false` at PEAD F0 time | Key now paid/present per human mandate | Week 0 probe. |
| SF1/SF2/SF3 adapters | **Absent** | The only new code this round. SF2 is one flat table (cheap). SF1 AR dimension + `datekey`/`reportperiod` PIT discipline is the expensive one. |

Net: the *expensive* unknown is SF1 PIT integrity; the *cheap* unknown is SF2 event density. Cheap falsifiers run first. That is the whole thesis.

## Ordered idea queue

Gates inherit the frozen family law unless stated: clustered inference, median reported beside mean, after-cost at 5/10/25 bps, year-share ≤ ~25%, matched-SPY (S2) on identical windows, deflated Sharpe > 0, `capital_go` always false. Every line names its kill_line condition *before* code.

### L0 — INVENTORY (non-claim engineering, mandatory, no alpha content)

- **Mechanism:** prove entitlement before any adapter. Probe script (clone of actions-reader shape): key present; live non-empty pull of SF1, SF2, SF3 (+ EVENTS/DAILY if entitled); SF1 dimensions (ARQ/ARY/ART/MRQ…), `datekey` vs `reportperiod` semantics, AR vs MR availability; SF2 transaction codes + `filingdate` presence; SF3 filing-lag fields.
- **Tables:** SHARADAR metadata/INDICATORS + one-page sample per table.
- **First falsifier (I0):** only SEP/ACTIONS/TICKERS entitled → **Full-Stop re-seal**, do not invent price alpha.
- **Density gate:** n/a. **Dual-exit:** re-seal is the published success mode on I0 fail.
- **Cost:** 1–2 days. Artifact: `inventory-probe.json` + one-page memo.

### L1 — FORM4-DENSITY (memo-grade kill; no returns, no F0)

- **Mechanism:** Cohen–Malloy–Pomorski (2012): stripping *routine* trades leaves *opportunistic* insiders whose purchases earned ~82 bp/month value-weighted abnormal; routine ≈ 0. This is the highest mechanism-novelty family available — a genuinely new information set (insider behavior) vs the settled price residual.
- **Tables:** SF2 (transactions), SEP (ADV filter), TICKERS (listed, primary common).
- **Work:** SF2 flat reader (adapter clone) → event histogram **only**: open-market purchases (P-codes) by officers/directors, liquid filter (e.g. 60-day median dollar-volume ≥ $5M from SEP), per-year counts 2010–2025, plus CMP-decode feasibility check (per-insider trade history sufficient to classify routine vs opportunistic — needs ≥3 years of per-insider rows; measure coverage, don't assume).
- **First falsifier:** qualifying purchase events < 30/year in ≥3 of the last 10 folds, **or** top calendar year holds > 40% of all qualifying events (event concentration pre-commits a year-concentration fail), **or** per-insider history too thin to run the CMP routine/opportunistic split → **kill_line in a memo**. No F0, no E1, no portfolio code written.
- **Density gate:** the falsifier *is* the gate. This line exists to kill Form-4 for the price of a histogram.
- **Dual-exit:** kill memo is a success. Pass ⇒ fund L3 F0.
- **Cost:** 3–5 days.

### L2 — PEAD-F0-REMEASURE (integrity only; still no returns)

- **Mechanism:** Bernard–Thomas classic PEAD via revenue-confirmed GAAP earnings surprise — but Martineau (2022, *Rest in Peace PEAD*, Critical Finance Review): prices fully reflect surprises at announcement for large caps since ~2006; drift survived longest only in microcaps, i.e. exactly the names our liquid ADV filter excludes. This line's *returns* prior is the most negative in the queue. It is run second, not because it is promising, but because its F0 verdict was **data absence** (`sf1_adapter_present=false`, returns never measured) — completing that measurement under a new PRD is honest science, not re-arguing a null.
- **Tables:** SF1 (AR dimensions), SEP, TICKERS, ACTIONS.
- **Work:** minimal SF1 AR reader (adapter clone, the expensive build of this round) → re-run frozen D0–D7 as *measured* pass/fail: reconstructability of as-first-reported diluted GAAP EPS and revenue (D1/D2), known-time policy audit (D3), amendment-rewrite / silent-unit-change / lookahead integrity (D4), mapping/terminals (D5), fold floors (D6), stratified reconcile (D7).
- **First falsifier:** any hard D fail → **kill PEAD data path**, publish measured null.
- **Density gate:** D6 fold floors (≥10 annual test folds, ≥8 prior seasonal changes per the frozen protocol) — measured, not assumed.
- **Dual-exit:** measured D-fail kill is a success; it converts "fail-closed absence" into a scientific null.
- **Cost:** 1–2 weeks (the SF1 reader + known-time audit is the real spend).

### L3 — FORM4-F0 → E1 (only if L1 density passes)

- **Mechanism:** CMP decode on SF2: classify per-insider routine vs opportunistic from own trade history; signal = opportunistic open-market **purchases**, with multi-insider cluster buys as the strong cell.
- **Tables:** SF2, SEP, TICKERS, ACTIONS; SPY sidecar for S2.
- **F0 (integrity, predeclared):** filing-timestamp honesty (`filingdate` as known-time, not `transactiondate`); amendment handling; code mapping audit; dedup of family/10b5-1 disclosures where identifiable. Any hard fail → kill_line.
- **E1 (event study, Gate-1a shape):** h60 excess vs same-date eligible-universe mean, clustered t; primary test is **opportunistic minus routine** spread — if the decode carries no information (spread t < 2, or routine ≈ opportunistic), the mechanism itself is falsified cleanly.
- **First falsifier:** opportunistic−routine spread clustered t < 2.0 gross, or opportunistic mean ≤ 0 after 10 bps, or year-share > 25%.
- **Density gate:** inherited from L1 (already passed) + per-fold ≥ 20 opportunistic events for clustered inference; fold below floor counts as fail, not as missing data.
- **Dual-exit:** E1 kill = settled line; pass ⇒ implementability PRD eligibility **only**.

### L4 — PEAD-E1 (only if L2 D-pass; lowest prior in the queue)

- **Mechanism:** revenue-confirmed GAAP surprise, h≈60 excess drift.
- **Tables:** sealed SF1 tape from L2, SEP, TICKERS.
- **Work:** E1 event study under frozen protocol (no analyst SUE swap, no guidance NLP, no ranking).
- **First falsifier:** gross B−T clustered t < 3.0 (R2-1's bar), or mean ≤ 0 after 10 bps, or median ≤ 0, or year-share > 25%. Given Martineau, treat a *pass* as the surprising branch requiring placebo re-check, not as vindication.
- **Density gate:** L2 D6 already enforced; E1 additionally requires ≥ 10 entry-year folds with majority > 0.
- **Dual-exit:** kill = second measured null; the two-kill rule (L3/L4 both dead) triggers **Full-Stop re-seal**.

### L5 — QUALITY-SLOW (contingent third; only if exactly one of L3/L4 killed and the other was never entitled)

- **Mechanism:** Novy-Marx gross profitability (GP/A) + Sloan accruals, monthly-rebalanced slow cross-section — reuses the L2 SF1 reader at near-zero marginal adapter cost. This is the *only* ranking-adjacent line allowed, and it is a new information family (fundamentals levels), not residual rescue.
- **First falsifier:** quintile spread Q5−Q1 after 10 bps with deflated Sharpe ≤ 0 (Gu–Kelly–Xiu lesson: published factor zoo does not survive deflation; predeclare the deflation, don't discover it).
- **Density gate:** SF1 coverage ≥ 60% of liquid universe per quarter in ≥ 8 of 10 years.
- **Dual-exit:** kill → re-seal; this is the last line. There is no L6.

## Explicit rejects

- **Residual rescue / ranking / DAMB / Quiet Drift** — settled DIE, hard freeze; out of scope by law.
- **R2-1 retune** (buffering modeling, Jan-2021 tail work as alpha rescue) — settled kill_line.
- **PEAD portfolio before D-pass** — forbidden in the mandate, repeated here because it is the historically tempting violation.
- **Analyst SUE silent swap** — frozen protocol says `analyst_sue_fallback: false`; changing it is a new PRD, not an adapter detail.
- **13F/SF3 copycat alpha** — 45-day filing lag destroys the information; only admissible as lag-honest Δ-ownership *context*, never as a first-dollar signal. If SF3 is the only interesting table after L0, that is an I0-flavored re-seal, not a research line.
- **Factor-zoo ML (Gu–Kelly–Xiu-style) on Sharadar tabulars** — the universe is ~liquid US equities with ~15 years; the method needs scale and OOS discipline this program cannot fund, and its honest expected contribution over L5's two-factor sort is negative after deflated-Sharpe gates.
- **"We paid" as accept path** — entitlement is an option on measurement, not evidence.
- **Parallel A/B tracks** — see attack section; the host, the budget, and the repo's own history all say serialize.

## LLM / open-weight fine-tunes (honest)

| Idea | Verdict | Why |
| --- | --- | --- |
| Fine-tune on prices / SEP features | **Reject** | Identical information set to the settled residual and R2-1. An LLM does not create new information; it re-mines a killed mine. |
| Fine-tune on SF1 fundamentals | **Reject as first dollar; revisit never** | Tabular cross-section of this size is gradient-boosting territory at best, and GKX-style ML is already rejected above on deflation grounds. |
| Earnings-call / press-release text (PEAD.txt, Meursault et al.; 8-K soft info, Wu et al. ICAIF 2025) | **Not this round** | Text is **not in the Sharadar entitlement** (SF1/SF2/SF3 are tabular). Requires EDGAR crawling + PIT timestamp infra = a second data-integrity program on top of L2. Admissible only after tabular lines settle *and* a new human re-open names it. Announcement-day/open-entry inefficiency findings cut against naive text-PEAD anyway. |
| LLM as research clerk (reading SF1 dimension docs, drafting adapter field maps) | **Allow** | Engineering assistance, zero alpha claim. Non-claim engineering. |

Honest bottom line: there is no LLM line in this queue because the paid data is tabular. Anyone proposing otherwise is proposing a *different* data purchase, which is a human decision, not a seat proposal.

## Recommended first 2 weeks

**Week 1**

1. Day 1: L0 probe script (clone `sharadar_actions.py` skeleton → `inventory_probe.py`); run; write `inventory-probe.json` + one-page memo. **Decision gate: I0.**
2. Days 2–4: SF2 flat reader (adapter clone; strict pydantic row model; cursor pagination; cache to fixture JSON like existing pattern). Pull 2010–2025 transactions.
3. Days 4–5: L1 histogram + CMP-decode feasibility memo: qualifying P-code purchases under liquid ADV filter, per-year counts, top-year share, per-insider history depth. **Decision gate: density falsifier → kill memo or fund L3 F0.**

**Week 2** (runs regardless of L1 outcome, *after* L1 memo is published — not parallel)
4. Days 6–9: SF1 AR-dimension reader (the round's one expensive build): dimension policy (ARQ primary), `datekey` as known-time candidate, pagination + cache, strict rows.
5. Days 8–10: wire reader into existing `research_pead_f0.py` D-gates; measure D1–D5 first (reconstructability, known-time, integrity). **Decision gate: any hard D-fail → measured kill_line, published.**
6. End of week 2: status memo to human with both gate outcomes and the explicit statement: *E1 code has not been written; no returns measured; capital remains honest liquid beta.*

Stop conditions are predeclared per line above; a kill at any gate ends that line the same day, in writing.

## Confidence and sharpest risk

| Claim | Confidence |
| --- | ---: |
| Inventory-first, serialize-cheapest-falsifier order is correct | 90 |
| SF2 density memo is the best value-per-day in the program | 70 |
| Any line reaches implementability-PRD eligibility this quarter | **12** (meta says 25–35; I say that is optimism — see attacks) |
| Two-kill re-seal is reached within ~6 weeks | 55 |
| Program economics beat Full-Stop-forever *given the subscription is sunk* | 70 |

**Sharpest risk:** the L2 SF1 build is where this program repeats its original sin — "build before honest stop." SF1 PIT integrity (AR dimension discipline, `datekey` vs `reportperiod`, amendment rewrites) is a 1–2 week engineering spend in service of a line (PEAD) whose *returns* prior is the most negative in the literature we cited (Martineau: dead in liquid names since ~2006). The mitigation is structural, not rhetorical: L1's density memo runs **first** so that if Form-4 density passes, L2's PEAD work can be *descoped to integrity-only with a precommitted E1-skip decision*; and if both L1 and L2 kill, the program re-seals having spent ≤ 2 weeks, which is the correct price for converting an entitlement question into published nulls.

## Attacks on meta-synthesis order (inventory → PEAD F0 integrity ∥ Form-4 density)

1. **The parallel A/B track is the meta's central error.** Three independent reasons: (a) the 16GB sequential-run law is written into every published results doc in this repo — the hardware forbids the meta's own plan; (b) the repo's entire scar tissue is from engineering running ahead of falsifiers — a 3–5-day density memo that can kill Form-4 *before* the 1–2-week SF1 build is strictly dominant sequencing, and running them in parallel forfeits the option value of the cheap kill; (c) dual-exit cadence — kills are supposed to be published, human-visible events; two simultaneous tracks produce one ambiguous combined status. Correct order: **L0 → L1 (density) → L2 (SF1 integrity) → one E1.** Grok's Form-4-first instinct was right on mechanism novelty but still wrong to reach for F0 before a density memo; Codex/Fable were right that PEAD F0 is cheap *gate-wise* but wrong that it is cheap *program-wise* — the gates exist, the tape reader does not, and that reader is the round's only real build.
2. **"PEAD F0 helpers exist ⇒ cheapest path" confuses sunk cost with marginal value.** The helpers are pure fail-closed gates; they cost nothing to re-run and prove nothing until an SF1 AR reader + known-time audit exists. The marginal cost of the PEAD line is the most expensive artifact in Round 4, spent on the line with the worst literature prior. It still belongs in the queue — the F0 kill was data absence, and completing that measurement is honest — but it belongs **second**, after the cheap falsifier, not first and not parallel.
3. **Meta's 25–35% promote probability is miscalibrated upward.** Inputs: two sequential funded kills on this exact stack; Martineau's liquid-PEAD null; CMP's 82 bp/month is a 2003-sample, pre-decimalization, value-weighted result whose liquid-name remnant after an ADV filter is the weakest cell; GKX deflation on anything factor-shaped. Honest number is 10–15%. This matters because the human's decision to fund Round 4 should be priced at the real rate, not the consensus-flattering one.
4. **What the meta got right (not rubber-stamping, verifying):** inventory-first with I0 re-seal — correct, adopted verbatim. Dual-exit framing — correct. LLM reject — correct, and I extend it: the text-based PEAD variants (PEAD.txt, 8-K soft info) are out-of-entitlement and require a *second* PIT infrastructure program; any seat proposing them as near-term is proposing a new purchase. SF3 demoted to last — correct; I go further and reject 13F copycat outright absent lag-honest framing.
5. **Missing from the meta: a precommitted re-seal trigger.** The meta says "both E-lines kill cleanly → accruals or re-seal" — that is an open door to a fourth line. My queue hard-codes it: **two sequential honest kills anywhere in L1–L4 ⇒ Full-Stop re-seal, and L5 exists only under a narrow contingency, never as momentum.** A re-open without a precommitted exit is how Full-Stop erodes into pause-default by drift.
