# Paid Tape Unlocks New Information Families — Inventory First, Kill Fast, No Residual Rescue

**Seat:** ADVERSARIAL JUDGE GROK 4.5 HIGH  
**Round:** 4 — IDEA GENERATION (event-only re-open of CS research budget)  
**Date:** 2026-07-21  
**Binding prior:** residual DIE · R2-1 kill_line · PEAD F0 kill_line (data-object absence) · Full-Stop seal · R3 consensus hold Full-Stop + beta  
**Re-open premise:** Human rejects “give up / only beta.” Paid Sharadar Nasdaq entitlement exists under prior advice to buy fundamentals/ownership for edge research. This is **CS budget re-open for named information families only**, not residual packaging and not “finish PEAD F0 because we almost measured.”

---

## Thesis (why paid data changes the decision)

Price-only residual, short-horizon reverse, and PEAD-without-tape already answered their questions honestly: structure product dies on year concentration and SPY-matched excess; reverse dies on weak clustered *t* and cost honesty; PEAD F0 dies on **missing original tape**, not on a measured returns null. What the paid stack changes is **which experiments become measurable** — SF1 (as-reported ARQ/ART + `datekey` public-time), SF2 (Form 3/4/5 insiders), SF3 (13F institutions), DAILY (market cap/EV/metrics), EVENTS (8-K item taxonomy), joined to existing SEP/ACTIONS/TICKERS. That is a **new information budget**, not a license to re-litigate residual_hope. The correct re-open is: **inventory capability probe → density/feasibility memo per hypothesis → F0 integrity fail-closed → position-blind E1 with Phase-2 family law → portfolio only after signal gates; `capital_go` always false until separate implementability PRD.** Dual-exit remains: kill_line or return-to-Full-Stop are success modes. Spending weeks wiring SF1 “so we can hope” is the same engineering-tax trap that produced PEAD F0’s unmeasured kill.

---

## Inventory first (API capability probe design — no strategy code)

**Goal:** Prove entitlement, schema, PIT fields, bulk economics, and join keys **before** any return series. Fail-closed if key absent, schema incomplete, or AR/`datekey` policy unprovable.

### I0 — Secrets and transport (hard)
| Check | Pass | Fail |
|---|---|---|
| `NASDAQ_DATA_LINK_API_KEY` present in env (no log of value) | key non-empty | kill all downstream |
| Authenticated call to one known table (existing SEP pattern) | HTTP 200 + columns | fail-closed; do not invent cache |
| Rate/cursor behavior documented | page + `next_cursor_id` works like SEP | redesign fetch; no silent trunc |

### I1 — Table presence matrix (hard per product claimed)
Probe each product with **minimal** filters (one ticker, one date window, export=false for row sample):

| Product | Table | Minimum fields to assert | Join key to SEP |
|---|---|---|---|
| Prices (have) | `SHARADAR/SEP` | ticker, date, OHLCV, closeadj | ticker+date |
| Actions (have) | `SHARADAR/ACTIONS` | ticker, date, action, value | ticker+date |
| Tickers (have) | `SHARADAR/TICKERS` | ticker, table, isdelisted, category | ticker |
| Fundamentals | `SHARADAR/SF1` | ticker, dimension, datekey, reportperiod, calendardate, lastupdated, epsdil, revenue, gp, ncfo, assets, equity | ticker; **public time = datekey** |
| Daily metrics | `SHARADAR/DAILY` | ticker, date, marketcap, ev, pe, pb (assert what exists) | ticker+date |
| Insiders | `SHARADAR/SF2` | filingdate, transactiondate, ticker, owner, transactioncode, shares, price, sharesownedfollowing | ticker; **entry clock = filingdate (+1 session)** |
| Institutions | `SHARADAR/SF3` | calendar date / filing lag fields as provided, ticker, investor, shares, value, % outstanding if any | ticker; **entry clock = public filing availability, not period end** |
| Events | `SHARADAR/EVENTS` | ticker, date, event codes / 8-K item strings | ticker+date |

**Artifact:** `inventory-probe.json` with `{table, reachable, n_rows_sample, columns_present, missing_critical, cursor_ok, notes}`. No strategy module imports this until I2 passes.

### I2 — PIT / integrity sample audit (hard; 50–200 random rows)
1. **SF1 dimension policy:** only `ARQ`/`ART`/`ARY` allowed for any research claim; `MR*` dimensions are **forbidden** for signals (restatement lookahead).  
2. **`datekey` vs `reportperiod`:** assert `datekey >= reportperiod` and document lag distribution; unknown policy → KnownTimePolicy = fail.  
3. **SF2:** open-market purchase codes only; exclude awards/exercises/gifts if codes allow; assert filingdate ≥ transactiondate; entry uses **filingdate**, never transactiondate.  
4. **SF3:** document 13F quarter-end vs SEC file date lag; if file date missing → **SMRL ineligible** (fail product for that hypothesis).  
5. **Ticker mapping / delists:** join SF* to TICKERS primary common stock; count orphans.  
6. **Amendment / lastupdated:** sample restatements; if “as reported” rows rewrite in place without version → fail integrity for that table.

### I3 — Density memo method (per hypothesis; no returns)
For each named hypothesis H:
- Define event predicate on inventory columns only.  
- Count events by calendar year and by liquid ADV bucket (join SEP volume×close).  
- Report: `n_events`, `n_names`, `years_with_≥N`, `max_year_share_of_events` (event density, not P&L).  
- **Kill density early** if: <10 annual folds with ≥ floor events, or max year-share of events > ~0.35 (sparsity theater), or liquid-name share too low for costs.

### I4 — Engineering budget for inventory
- **≤1 eng week** total for I0–I3 (read-only probe driver + pure validators + JSON artifact + docs).  
- Reuse SEP client patterns (`SharadarMarketDataReader` cursor/backoff); **do not** build portfolio or event-study code in this week.  
- 16GB sequential rule: one table bulk at a time; no parallel multi-GB loads.

### Explicit non-goals of inventory
- No SUE series, no Form-4 alpha, no SF1 factor zoo, no LLM, no residual re-open, no `capital_go`.

---

## Top 5 named hypotheses

Ranked by **mechanism novelty vs price residual + falsifiability + sample feasibility on Sharadar**, not by narrative coolness.

### 1. CFOB — Cluster Form-4 Open-Market Buys
| | |
|---|---|
| **Mechanism** | Multiple distinct insiders open-market **purchase** the same ticker within a short window; signal is **clustered informed demand**. Public entry only after Form-4 **filing** (≤2 business days post-trade under modern rules). Residual scanners never saw ownership events. Buys >> sales for signal quality (sales are diversifying/tax). |
| **Tables** | **SF2** (primary) + **SEP** + **TICKERS** + optional **DAILY** (size filter). |
| **Sample density method** | Count clusters: ≥*k* distinct reporting owners, open-market buy codes, window *W* calendar days, min notional or % shares; group by filingdate year; require liquid ADV floor on entry session. Density kill if <Y years with ≥N clusters or liquid share &lt; threshold. |
| **Kill criteria** | (D) density fail; (F0) filingdate unusable / code taxonomy unclean; (E1) median excess ≤0 at predeclared h; clustered *t* &lt; bar; year P&L share &gt;~25%; mean trade−SPY matched excess ≤0; net after 5–10 bps ≤0; awards/exercises contamination. Dual-exit Full-Stop if kill. |
| **Rough eng weeks** | Density+F0: **1–2**; E1 event study: **1–2**; portfolio structure only if E1 pass: **+2**. Total to honest null: **~3–4**. |
| **Lit anchors** | Lakonishok & Lee (2001) insider trades predict returns (purchases); Cohen, Malloy, Pomorski (2012) “decoding inside information” — routine vs opportunistic trades; cluster folklore consistent with multi-insider concurrence. |

### 2. RC-SUE — Revenue-Confirmed As-Reported Seasonal SUE
| | |
|---|---|
| **Mechanism** | Standardized unexpected **diluted GAAP EPS** vs seasonal random-walk, **confirmed** by same-quarter revenue surprise direction, using **ARQ only** and public time = **`datekey`**. This is the **correct re-open of PEAD F0** (prior kill was data absence, not returns). **Not** residual rescue; **not** analyst SUE fallback. Martineau’s “RIP PEAD” is the prior: large-cap classic PEAD may be dead — so RC-SUE carries a **high prior of kill** and must beat modern decay, not 1990s textbooks. |
| **Tables** | **SF1** (ARQ: epsdil, revenue, datekey, reportperiod) + **SEP** + **EVENTS** optional for 8-K earnings timestamp cross-check + **DAILY** size. |
| **Sample density method** | Firm-quarters with ≥8 prior same-fiscal-quarter ARQ EPS; revenue co-move filter; count by announcement year (`datekey` year); liquid ADV on next open. |
| **Kill criteria** | F0: AR reconstructability / datekey policy / no MR leakage (PEAD D1–D7 spirit); E1: median h60 excess ≤0; year share &gt;~25%; SPY-matched ≤0; costs; **post-2006 / large-cap subsample must not be the only place it “works” via microcap theater**; no analyst SUE rescue. |
| **Rough eng weeks** | Inventory+AR F0: **2–3** (heavier integrity); E1: **2**. Honest null path: **~4–5**. |
| **Lit anchors** | Bernard & Thomas (1989) PEAD; Martineau (2021/2022) *Rest in Peace PEAD* — announcement-day full incorporation for many stocks; Meursault et al. *PEAD.txt* (JFQA 2023) — text SUE survives where numeric PEAD dies (**we do not have call text in Sharadar** → RC-SUE is numeric only; do not claim PEAD.txt). Fink (2021) survey: PEAD magnitude declined. |

### 3. GPQC — Gross Profitability Quality Core
| | |
|---|---|
| **Mechanism** | Novy-Marx **gross profitability** (GP/Assets or GP/AT from SF1) as a slow characteristic: high quality earns relative to junk after size control. Mechanism is **earnings productivity**, not event underreaction and not price residual momentum. Uses DAILY for market equity ranking/liquidity. This is the cleanest **non-event** CS factor the paid SF1 tape enables. |
| **Tables** | **SF1** (ARQ/ART: gp, assets/equity) + **DAILY** (marketcap) + **SEP** + **TICKERS**. |
| **Sample density method** | Monthly/quarterly rebalance universe: count names with non-null GP and assets by year after ADV/price floors; not event-sparse. Density usually **passes** — risk is **edge**, not sample size. |
| **Kill criteria** | Value-weight and equal-weight OOS: mean-median conflict; after costs/turnover at rebalance frequency; year concentration of active P&L; failure vs SPY (or market) on matched exposure; microcap-only alpha; dependence on 1–2 years; cannot beat simple size-neutral random long-short placebo. |
| **Rough eng weeks** | Characteristic panel F0: **1–2**; CS formation study: **2–3**. Total: **~3–5**. |
| **Lit anchors** | Novy-Marx (2013) gross profitability premium (JFE); Asness, Frazzini, Pedersen *Quality Minus Junk* (RoAS 2019); Gu, Kelly, Xiu (RFS 2020) — nonlinear ML helps risk premia measurement, but **interpretable quality characteristics remain first-order** (do not jump to NN before GPQC dies). |

### 4. SMRL — Smart-Money 13F Revision Lag
| | |
|---|---|
| **Mechanism** | Large institutions disclose holdings with **statutory lag** (~45 days after quarter-end). Δ% ownership or new high-conviction stakes, measured only at **public 13F availability**, may still predict if markets under-react to smart money. Residual price tape never had this state variable. **High risk of weak after-cost edge** in liquid names and short SF3 history (~2013+ per Sharadar product notes). |
| **Tables** | **SF3** + **SEP** + **TICKERS** + optional **DAILY**. |
| **Sample density method** | Count quarterly revision events with usable **file/public date**; years available; % of SEP liquid universe covered. Kill if history &lt; ~10 annual folds or file date missing. |
| **Kill criteria** | File-date PIT fail; n folds &lt; floor; median excess ≤0; year share; costs high (turnover at quarterly bursts); concentration in mega-cap noise; “famous fund” storytelling without predeclared skill score. |
| **Rough eng weeks** | Inventory+PIT: **1–2**; E1: **2**. Total: **~3–4**. Skip if I1 shows SF3 lag fields inadequate. |
| **Lit anchors** | 13F literature mixed; institutional anomaly papers use Thomson/13F with careful lag; treat **lag integrity as first-class**. Do not cite “13F always works.” |

### 5. I2CD — Item 2.02 Continuity Drift (8-K earnings event clock)
| | |
|---|---|
| **Mechanism** | EVENTS taxonomy provides a **public 8-K earnings-results clock** (Item 2.02 and kin). Join to SF1 ARQ surprise **only when both exist**; trade the **joint** event. Improves known-time vs ambiguous `datekey` alone; still numeric fundamentals (not PEAD.txt). Distinct from residual price breakouts: entry is **filing event**, not scanner pattern. |
| **Tables** | **EVENTS** + **SF1** + **SEP**. |
| **Sample density method** | Count Item-2.02-class events with successful SF1 join within ±*d* days; year histogram; liquid share. |
| **Kill criteria** | Event code coverage incomplete; join rate too low; pure EVENTS without SF1 surprise = noise; same PEAD kill family (median, year, SPY, costs); cannot use EVENTS as excuse to skip AR integrity. |
| **Rough eng weeks** | Density join: **1**; depends on RC-SUE SF1 work — incremental **+1–2** if SF1 already clean. |
| **Lit anchors** | Complements RC-SUE; Martineau still applies to hard-number drift; PEAD.txt needs **call text we do not have**. |

### Explicit non-ranked / deprioritized (for clarity)
| Idea | Why not Top 5 |
|---|---|
| Sloan pure accruals long-short | Green, Hand, Soliman (2011) *Going, Going, Gone* — anomaly largely arbitraged; may appear as **diagnostic filter** after GPQC, not a funded primary line |
| Gu et al full ML factor zoo / NN3 | Needs huge characteristic panel, compute, multiple-testing discipline; **after** single-factor GPQC, not instead of inventory |
| PEAD.txt / open-weight LLM on filings | Requires earnings-call or 10-Q text corpus; **Sharadar EVENTS ≠ transcripts**; rank low until tabular lines dead and text pipeline cost justified |
| Residual / Quiet Drift / DAMB | **Banned** — settled DIE |
| R2-1 retune / cost-knob reverse | **Banned** — kill_line |

---

## Anti-patterns (subscription sunk-cost traps)

1. **“We paid for SF1, so PEAD must exist.”** Subscription is an **option on measurement**, not a put on efficiency. Martineau is the base rate for classic PEAD.  
2. **“Finish F0 because last time was unmeasured.”** Unmeasured kill was correct fail-closed. Re-open needs **inventory pass**, not sunk-cost completionism.  
3. **Wire all adapters then choose a story.** Adapters without a named hypothesis = readiness theater (R3 danger #2).  
4. **MR dimensions “because more complete.”** Most-recent restated series = lookahead poison for claims.  
5. **Entry on transactiondate (SF2) or quarter-end (SF3).** Public-time discipline or the backtest is fiction.  
6. **Microcap-only “works” with 10 bps costs.** Phase-2 SPY lesson: matched liquid exposure must be beaten.  
7. **Year-share soft rewrite.** ~25% family law stays; 2020 residual talisman does not.  
8. **Ranking theater on residual events.** Different information family only.  
9. **Factor zoo fishing across 50 SF1 fields.** One predeclared primary metric per line; secondary is pre-registered interaction only.  
10. **“capital_go true if mean &gt; 0.”** Always false until implementability PRD; median, SPY match, year, costs all hard.  
11. **Using inventory week to scaffold portfolio code.** Probe only.  
12. **Converting beta productization into CS cosplay** or vice versa — capital honesty remains parallel, not a research substitute **or** a blocker for this explicit re-open.

---

## LLM open-weight path (when justified; default rank low for tabular)

| Path | Rank | When justified |
|---|---|---|
| Fine-tune Llama/Mistral **on prices alone** | **Reject** | Prices already fully used in residual/R2-1; no new information; overfitting theater |
| LLM embeddings on **earnings call / 10-Q MD&A** (PEAD.txt style) | Low–medium **after** tabular kills | Literature: Meursault et al. PEAD.txt survives when numeric PEAD dies; needs EDGAR/transcript pipeline **outside** Sharadar SF1/SF2/SF3 |
| LLM to **classify 8-K item free text** if EVENTS codes incomplete | Low | Only if I1 shows EVENTS taxonomy insufficient |
| LLM for **insider footnote / 10b5-1 plan detection** | Speculative | Only after CFOB density pass and code-based F0 |

**Default:** spend **zero** LLM weeks in Round-4 sequence until CFOB + RC-SUE + GPQC inventory and at least one E1 complete. Tabular paid tape is the reason for re-open; text is a **later option**, not a bypass.

---

## Recommended sequence with dual-exit

```
R4-0  Human re-open recorded (this debate + named menu) — dual-exit law affirmed
R4-1  Inventory probe I0–I3 (≤1 week) — FAIL → Full-Stop retained (success: honesty)
R4-2  CFOB density + SF2 F0 (≤2 weeks) — FAIL density/F0 → kill CFOB, do not pivot knobs
R4-3  If CFOB F0 pass → E1 event study (median, SPY match, year≤~25%, costs) — FAIL → kill_line
R4-4  Parallel/next: SF1 AR integrity for RC-SUE + GPQC panel hygiene (≤2–3 weeks)
R4-5  Choose ONE SF1 primary by pre-registered rule:
        - If inventory shows clean datekey + dense firm-quarters → RC-SUE E1
        - Else if AR panel clean but SUE sparse → GPQC CS study first
      FAIL → kill that line
R4-6  SMRL only if SF3 file-date PIT proven and earlier lines need a third family
R4-7  I2CD only as RC-SUE known-time upgrade, not standalone zoo
R4-8  Portfolio structure PRD only after E1 pass; capital_go false
R4-9  Terminal: all funded lines kill_line → Full-Stop + honest beta (process success)
```

**Dual-exit definition (binding):**
- **Kill_line** = published null for that named hypothesis; no threshold retune.  
- **Full-Stop return** = CS budget ends again if inventory fails or two sequential funded lines die without a surviving E1.  
- **Neither exit is shame**; residual rescue is.

**Parallel capital:** Honest liquid beta productization (R3-1) may continue as **non-claim** ops. It does **not** gate inventory; it also does **not** mint alpha.

---

## Confidence + risks

| Claim | Confidence |
|---|---|
| Inventory-first is the only honest use of the new subscription | **90** |
| CFOB is the best *first* alpha line (mechanism + filing clock + not residual) | **62** |
| RC-SUE produces investable after-cost edge in liquid names post-2010 | **28** (Martineau prior) |
| GPQC produces *new* edge beyond cheap quality ETFs after costs | **40** |
| SMRL survives lag + costs | **22** |
| Any LLM-on-prices path is research malpractice here | **95** |
| This re-open avoids residual laundering if dual-exit enforced | **70** (process risk is human) |

**Sharpest risks**
1. **Sunk-cost adapter sprawl** — three SF* readers without a density number.  
2. **RC-SUE emotional favorite** because PEAD F0 “felt unfinished.”  
3. **SF2 code pollution** (awards as “buys”).  
4. **Year concentration** repeating 2020-style product disasters under a new name.  
5. **16GB thrash** loading SF1+SEP+SF2 together.  
6. **False dual-exit** (“kill then immediately retune k and W”).

---

## Attacks on "just wire SF1 and hope" and "fine-tune Llama on prices"

### Attack A — “Just wire SF1 and hope”
PEAD F0 already proved the failure mode: protocol freeze without a live original tape yields **kill_line on D1–D7 unmeasured**, not a trading insight. Wiring SF1 without I0–I3 repeats that with more code. SF1 is a **multidimensional** object (AR vs MR, datekey vs reportperiod, amendments). Hope is not a known-time policy. Martineau implies even a *perfect* SF1 SUE series may return a **measured** null in modern liquid markets — that null is valuable, but only if measured under AR/`datekey` discipline. “Wire everything” also violates research economics: eng weeks before a density histogram are how Full-Stop got sealed last time. **Correct:** inventory JSON → density memo → one hypothesis F0 → E1. Adapters are **scoped to the funded line**, not a platform fantasy.

### Attack B — “Fine-tune Llama on prices”
1. **No new information set.** Residual and R2-1 already exhausted daily OHLCV structure tests; an LLM is a nonlinear function of the same bits.  
2. **Gu, Kelly, Xiu (2020)** use **rich characteristic panels** + careful OOS design — not raw price tokens. Citing “ML works in asset pricing” to justify price-LLM is a category error.  
3. **Multiple testing / capacity:** sequence models on noisy daily returns overfit regime and microstructure without economic mechanism.  
4. **PEAD.txt justification fails here:** that paper uses **earnings-call text**, not price charts. If you want text edge, budget EDGAR/transcripts **after** tabular paid data is honestly tried.  
5. **Compute vs 16GB sequential research rule:** fine-tunes are the opposite of fail-closed pure helpers.  
6. **capital_go culture:** LLM narratives mint false confidence faster than Form-4 density memos.

**Most dangerous archetype now:** not “only beta” (the human already re-opened) but **subscription completionism** — adapters, factor zoos, and PEAD hope without density — which launders Full-Stop failure into “we’re building infrastructure.”

---

## Final one-liner

**Next quarter of CS research dollars:** inventory probe week, then **CFOB (SF2 clusters)** as first falsifiable line; SF1 **AR integrity** in parallel for **one** of RC-SUE or GPQC by density — dual-exit kill/Full-Stop as success; **never** residual, **never** Llama-on-prices, **never** “wire SF1 and hope.”

---

## Literature quick list (URLs / citations)

1. Martineau, C. — *Rest in Peace Post-Earnings Announcement Drift* (Critical Finance Review / SSRN 3111607) — classic PEAD decay.  
2. Meursault, V. et al. — *PEAD.txt* (JFQA 2023; Philadelphia Fed WP 21-07) — text SUE vs numeric PEAD.  
3. Gu, S., Kelly, B., Xiu, D. (2020) — *Empirical Asset Pricing via Machine Learning*, RFS 33(5) — ML needs characteristics, careful OOS.  
4. Novy-Marx, R. (2013) — gross profitability premium, JFE.  
5. Asness, Frazzini, Pedersen — *Quality Minus Junk*, Review of Accounting Studies 2019.  
6. Sloan, R. (1996) — accruals; Green, Hand, Soliman (2011) — demise of accruals anomaly.  
7. Lakonishok & Lee (2001); Cohen, Malloy, Pomorski (2012) — insider purchases / decoding inside information.  
8. Bernard & Thomas (1989) — PEAD foundation (historical, not modern base rate).

---

## Repo mapping (implementation later; not this proposal’s code)

| Need | Existing | Gap |
|---|---|---|
| SEP/ACTIONS/TICKERS | `sharadar_*` adapters | — |
| SF1/SF2/SF3/DAILY/EVENTS | **none** | inventory probe + scoped readers |
| PEAD F0 gates | `pead_f0.py` | reuse spirit for AR integrity; do not auto-start E1 |
| Event study excess | `event_study_excess.py` | join new event clocks |
| capital_go | always false pattern | keep |

**End of Round 4 Grok 4.5 High proposal.**
