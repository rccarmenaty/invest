# Proposal: Kill the cheapest path first, then hunt where the meta blinked

**Seat:** deepseek-v4-pro

## Thesis

The meta-synthesis optimizes for adapter-wiring cost, not expected alpha. Its ordered program puts PEAD F0 remeasure first because "helpers already exist" — but the cheapest path to a null is still a null. Martineau (2022) shows PEAD attenuation in liquid US equities is structural, not a data-quality artifact. The meta acknowledges this ("liquid PEAD may be dead — dual-exit ready") and then proceeds as if measurement cost dominates. It doesn't.

The correct ordering maximizes *probability of finding promotable edge per unit of research budget*, not *cheapest next adapter*. Given 2–3 honest line kills before Full-Stop re-seal, the program should sequence by **mechanism novelty × prior probability of edge — wiring cost**. On that metric, SF3/13F ownership changes rank first, SF2 Form-4 second, and SF1 PEAD third. The meta's ordering is inverted.

## Capability inventory (first)

### Already wired (non-claim, operational)

| Table | Adapter | Consumer |
|-------|---------|----------|
| SHARADAR/TICKERS | `SharadarTickersReader` (full: pagination, validation, exchange/category filter) | `SharadarContextSource` |
| SHARADAR/SEP | `SharadarMarketDataReader` (full: OHLCV, adj close, cohort batching, calendar alignment) | `SharadarContextSource` |
| SHARADAR/ACTIONS | `SharadarActionsReader` (full: splits, dividends, delistings, ticker changes; kind-blind consumer) | `SharadarContextSource` |
| `NASDAQ_DATA_LINK_API_KEY` | Env-var gating in all three readers | Auth layer |

### Not wired (gating)

| Table | Status | What it unlocks |
|-------|--------|-----------------|
| SHARADAR/SF1 | No adapter; PEAD F0 driver exists but fail-closed on `sf1_adapter_present=False` | Fundamentals: EPS, revenue, balance sheet, cash flow (ARQ/MRY) |
| SHARADAR/SF2 | No adapter; no consumer | Insider transactions (Form-4): ticker, filing date, transaction code, shares, price, insider role |
| SHARADAR/SF3 | No adapter; no consumer | Institutional ownership (13F): filer, quarter, ticker, shares held, market value |
| SHARADAR/DAILY | Not explored | Alternative price source (superseded by SEP) |
| SHARADAR/EVENTS | Not explored | Corporate event calendar (earnings dates, guidance) |

### PEAD F0 driver state

- Protocol frozen: `revenue_confirmed_gaap_earnings_surprise`, diluted GAAP EPS, GAAP revenue
- `nasdaq_api_key_present`: was `False` at probe time — **this is the only thing that changed**
- `sf1_adapter_present`: `False` — the real blocker
- Gates D1–D7 all `FAIL` (not measured), D0 `PASS` (protocol freeze exists)
- Returns **never measured** — this is data absence, not a null

### Adapter codebase pattern

All three existing Sharadar readers share a proven template: httpx client, pagination with cursor_id, retry with backoff, Pydantic validation, `MarketDataFetchError` taxonomy. An SF1/SF2/SF3 adapter following this pattern is ~150–250 lines each, not a multi-week engineering project. The meta overstates "engineering tax" as a reason to defer SF2/SF3.

## Ordered idea queue

### Line 0 — Inventory probe (Week 0, non-claim, mandatory)

**Mechanism:** Hit Nasdaq Data Link `/api/v3/datatables` metadata under the paid key. Confirm SF1, SF2, SF3, DAILY, EVENTS entitlements. For each live table, probe one page: column list, row count, date range, ARQ vs MRY policy for SF1, transaction code vocabulary for SF2, lag distribution for SF3.

**Tables:** `SHARADAR/SF1`, `SHARADAR/SF2`, `SHARADAR/SF3`, `SHARADAR/DAILY`, `SHARADAR/EVENTS`

**First falsifier:** `SF1` returns 401/403 or empty datatable → entitlement doesn't include fundamentals → SF1 and SF3 likely both gated (Nasdaq bundles). If only SEP+ACTIONS+TICKERS entitled, **Full-Stop re-seal immediately** — no inventing price alpha from the same information set that killed R2-1.

**Density gate:** For SF2, count non-derivative transactions with `transactionshares > 0` in last 5 years. If <500 distinct filer-ticker pairs per year after liquid-universe filter, Form-4 is density-dead before F0. For SF3, count distinct manager-ticker-quarter observations; if <10K/quarter, institutional data is too sparse.

**Dual-exit:** I0 fail → Full-Stop re-seal (success mode). I0 pass → gate to Lines 1–3.

**Artifact:** `fixtures/real-continuous/reports/inventory-probe.json` + `docs/research/sharadar-entitlement.md`

### Line 1 — SF3/13F ownership Δ (highest mechanism novelty)

**Mechanism:** Institutional ownership changes (13F filings) are the one genuinely novel information family versus everything tested so far. Residual (Phase 2) used price momentum; R2-1 used price reversal; PEAD uses earnings surprises. None used *who owns what* — this is an orthogonal signal dimension. Cohen–Malloy–Pomorski show insider purchases carry information; 13F institutional flows (especially concentrated managers, small-cap tilts) may carry a slower but diversifying signal. Gu–Kelly–Xiu (2020, 2022) show that even simple factor timing on institutional flows adds information beyond price-based factors.

**Tables:** SF3 (13F holdings), SF1 (for fundamentals overlap filter)

**F0 (data integrity, Week 2–3):**

- Build SF3 adapter (follow pattern: httpx + Pydantic + cursor pagination)
- Measure: filing lag distribution (calendar quarter end → filing date for each manager), amendment rate (original vs restated), survivorship/backfill honesty, consecutive-quarter coverage
- Document: which manager types appear (mutual funds, hedge funds, pension, banks), ticker coverage overlap with liquid universe
- Hard gates: known-time policy (can we trade on filing date or only publication date?), lookahead in backfill, filing-date vs as-of-date integrity
- **F0 falsifier:** If median filing lag > 45 days after quarter-end for >50% of AUM, or if amendment/restatement rate > 15%, the signal is too lagged to be implementable in a liquid universe — kill before E1

**E1 (event study, Week 4–5):**

- If F0 passes: build quarterly ownership-change signal (Δ shares held by top-N concentrated managers, normalized by ADV)
- Event: filing publication date + 1 day (conservative)
- Structure: h≈60 excess return vs same-date eligible universe mean, median, year ≤25%, costs, matched-SPY
- Predeclared kill: Martineau-style attenuation may not apply (ownership changes are slower to be arbitraged away than earnings surprises), but year concentration risk is real — 13F data spans 2013+, which is a concentrated macro regime
- **Dual-exit:** If year share >25% or clustered t < 2.0, kill_line. If E1 passes promotion gates, this is the first new-information-family promotion since Phase 2.

**Why first:** Highest mechanism novelty per unit of adapter cost. The SF3 adapter is one new file (~200 lines); the signal is orthogonal to everything tested. If it's dead, it dies from data lag, not from a literature prior — that's a cleaner kill than PEAD's "we knew it was probably dead."

### Line 2 — SF2 Form-4 insider clusters (medium novelty, medium cost)

**Mechanism:** Cohen–Malloy–Pomorski (2012) show opportunistic insider purchases (not sales, which are liquidity-driven) predict returns, especially clustered purchases by multiple insiders in the same firm-month. This is the same information family as 13F (ownership) but at higher frequency and with a cleaner causal story: insiders know more than institutions, and purchase clusters signal conviction.

**Tables:** SF2 (insider transactions), SF1 (for fundamentals filter), SEP (for ADV filter)

**F0 (data integrity, Week 2–3, parallel with SF3):**

- Build SF2 adapter: `transactioncode`, `transactionshares`, `transactionpricepershare`, `filingdate`, `ownertype`, `officertitle`
- Measure: filing lag (transaction date → filing date), amendment patterns, transaction code vocabulary mapping
- Density histogram: count purchases (transactioncode = P) after ADV filter, by month, by insider role, by cluster size (≥2 insiders same firm within 30 days)
- **Density gate:** If purchase clusters (≥2 insiders, same firm, 30-day window) average <20/year in liquid universe, kill before F0 portfolio build — signal too sparse for Phase 2 structure (20 slots, 60-session hold)
- **F0 falsifier:** Known-time policy — are filings timestamped? Can we trade on publication datetime or only next session? If unknown, fail closed

**E1 (if density passes, Week 5–6):**

- Event: cluster purchase filing publication date + 1 day
- Structure: fixed-horizon h≈60, seeded-random admission (same structure as Phase 2)
- Gates: identical family law (mean > 0, median > 0, year ≤25%, costs, matched-SPY, clustered t ≥ 2.0, deflated Sharpe > 0)
- **Dual-exit:** Same kill_line criteria as R2-1. Form-4 has the sharpest year-share risk of any line: insider clusters concentrate in drawdowns/crises, so 2008–2009 and 2020 may dominate.

**Why second:** SF2 adapter follows the same pattern as existing readers. Density can kill it in Week 3 without portfolio engineering. The mechanism is orthogonal to price signals but has a sparsity risk the meta underweights.

### Line 3 — SF1 PEAD F0 remeasure (lowest novelty, cheapest wiring)

**Mechanism:** This is *measurement completion*, not a new alpha thesis. The PEAD F0 driver exists; the only missing piece is an SF1 adapter that feeds `diluted_gaap_eps` and `gaap_revenue` into the frozen protocol. The meta treats this as Track A priority because "helpers already exist" — but the Martineau (2022) prior that liquid PEAD is structurally dead is strong. Bernard–Thomas (1989, 1990) show PEAD exists, but in a pre-HFT, pre-electronic-dissemination market. The meta's 25–35% confidence on promotable CS alpha *this quarter* is almost entirely PEAD's prior.

**Tables:** SF1 (fundamentals: ARQ for quarterly EPS/revenue)

**F0 (data integrity, Week 1–2, sequential after inventory if I0 passes):**

- Build SF1 adapter (ARQ reader: `ticker`, `datekey`, `reportperiod`, `revenue`, `eps`, `shareswa`, `fcf`, etc.)
- Re-run PEAD F0 gates D0–D7 as *measured* (not fail-closed)
- Measure: original EPS reconstructability (was the as-published number restated?), lookahead integrity (does datekey precede reportperiod in backfill?), silent unit changes, amendment rewrites, calendar alignment of ARQ `datekey` vs earnings announcement dates
- **D1–D7 falsifier:** Any hard D-gate fail → kill PEAD data path permanently (no analyst SUE swap, no guidance NLP rescue). This is NOT a returns null — it's a data-integrity null, which is cleaner.

**E1 (if all D-gates pass, Week 3–5):**

- Only if D-pass is clean. Run E1 with the exact frozen protocol: `revenue_confirmed_gaap_earnings_surprise`, h≈60 excess, median, year ≤25%, costs, matched-SPY
- Martineau prior: expect clustered t < 2.0 or year concentration failure
- **Dual-exit:** Kill PEAD line cleanly if E1 fails. Do not retune thresholds, do not add analyst SUE, do not layer guidance NLP.

**Why third:** Lowest mechanism novelty — it's the same earnings-surprise signal that's been arbitraged for 40 years, measured on the same US liquid universe where Martineau shows attenuation. Wiring cost is lowest (~150 lines for SF1 ARQ adapter + gate re-run), but expected alpha is also lowest. The program should chase mechanism novelty first, then clean up the unmeasured null.

### Line 4 — SF1 accruals / gross profitability (contingent on SF1 D-pass + PEAD E1 kill)

**Mechanism:** If SF1 fundamentals are clean (D-pass) but PEAD E1 kills, reuse the SF1 adapter for accruals anomaly (Sloan 1996) and/or gross profitability (Novy-Marx 2013). These are different signal families from earnings surprise — they use balance-sheet and cash-flow statement fields, not EPS surprises.

**Tables:** SF1 (ARQ: total assets, current assets, cash, total liabilities, current liabilities, depreciation, revenue, COGS)

**F0:** Accruals = (ΔCA − ΔCash) − (ΔCL − ΔSTD − ΔTP) − Depreciation, scaled by average total assets. Gross profitability = (Revenue − COGS) / Total Assets.

**E1:** Monthly rebalance on most recent ARQ filing, long high-accruals/low-accruals or high-GP/low-GP, same structure gates.

**Dual-exit:** Standard kill_line if gates fail. This is the last SF1-based line before Full-Stop re-seal.

### Line 5 — Full-Stop re-seal (dual-exit success mode)

If Lines 1–4 all produce clean kills: re-seal Full-Stop with prejudice. The program has tested:

- Price residual (Phase 2): DIE
- Price reversal (R2-1): kill_line
- Earnings surprise (PEAD): kill_line (data or returns)
- Ownership changes (13F): kill_line
- Insider clusters (Form-4): kill_line
- Accruals / GP: kill_line

That's 5–6 independent signal families across price, fundamentals, and ownership. Two honest kills after re-open → Full-Stop re-seal. Capital stays honest liquid beta.

## Explicit rejects

1. **Residual rescue / ranking / DAMB** — hard freeze, settled, no reopening
2. **R2-1 retune theater** — kill_line is final
3. **PEAD portfolio before D-pass** — forbidden by binding law and common sense
4. **Analyst SUE silent swap** — if GAAP SUE is data-dead, analyst estimates are a different (lower-quality) data product, not a rescue
5. **Factor-zoo ML on prices** — same information set as R2-1; if you can't beat clustered t=2.0 on a simple reversal, no amount of XGBoost rescues it
6. **"We paid" as accept path** — payment is an option on measurement, not a promotion
7. **SF3 → 13F factor timing as first dollar** — the 13F signal must clear F0 integrity before any portfolio; no "let's just run it"
8. **Parallel E1 on multiple lines** — one line at a time through E1; parallel F0 (data integrity) is fine, parallel portfolio builds invite p-hacking across signal families
9. **LLM fine-tune on prices / 8-K text / press releases** — not Sharadar core; only after all tabular lines settle

## LLM / open-weight fine-tunes (honest)

| Idea | Verdict | Why |
|------|---------|-----|
| Fine-tune Llama on price sequences | **Reject** | Same information set as R2-1. If linear reversal fails clustered t, a transformer on the same inputs is feature engineering, not new information. |
| FinBERT on 8-K / earnings call text | **Defer** | Needs EDGAR text ingestion infra (not Sharadar). Only after tabular lines (SF1/SF2/SF3) all settle. Wu et al. (ICAIF 2025) show press-release soft info has signal, but this is a separate data pipeline. |
| Fine-tune on SEC filings (10-K/10-Q) | **Defer** | Same EDGAR dependency. Sharadar SF1 gives you the *numbers* from those filings, not the text. Text is a different program. |
| Graph neural net on insider networks | **Reject for now** | Form-4 density may not even support basic clusters; graph ML is third-order after density and basic clusters both pass. |
| LLM-as-judge on SF1 footnotes | **Defer** | SF1 doesn't carry footnote text. Would need EDGAR XBRL parsing. Interesting but not a Sharadar play. |

**Honest summary:** The Sharadar entitlement is tabular fundamentals, insider transactions, and institutional holdings. None of these are text. LLM fine-tuning as "first dollar" is category error — the data product doesn't support it. If the human wants LLM-on-text alpha, they need a different data subscription (EDGAR full-text, RavenPack, etc.).

## Recommended first 2 weeks

### Week 0 — Inventory probe (I0)

**Day 1–2:** Write and run inventory probe script. Hit all five datatables endpoints (SF1, SF2, SF3, DAILY, EVENTS) with the paid key. Output `inventory-probe.json`.

**Decision gate (Day 2):** If SF1/SF2/SF3 are not entitled → **Full-Stop re-seal** (success mode). Paid for SEP+ACTIONS+TICKERS only = same capability as before payment = no new CS lines possible.

### Week 1–2 — Parallel F0: SF3 + SF2 adapters + density

**If I0 passes (SF1, SF2, SF3 all live):**

| Day | SF3 (13F) Track | SF2 (Form-4) Track |
|-----|-----------------|---------------------|
| 1–3 | Build `SharadarSF3Reader` (follow SEP/ACTIONS pattern) | Build `SharadarSF2Reader` (same pattern) |
| 4–5 | Probe: filing lag, amendment rate, coverage, as-of-date honesty | Probe: transaction code vocabulary, filing lag, amendment rate |
| 6–7 | Density: distinct manager-ticker-quarter ≥ 10K? | Density: purchase clusters ≥ 20/year in liquid universe? |
| 8–10 | Write F0 integrity memo; if density fails → kill 13F line | Write F0 density memo; if density fails → kill Form-4 line |

**Decision gate (end of Week 2):** Which lines survive density/integrity to E1?

### Week 3+ — Sequential E1 based on survival

If both SF3 and SF2 survive F0 → run SF3 E1 first (higher mechanism novelty), then SF2 E1. If only one survives → run that one. If both die in F0 → move to SF1 PEAD F0 remeasure (Line 3).

### Simultaneously (Week 1): Build SF1 adapter

Even if PEAD is Line 3 in priority, the SF1 adapter is a shared dependency (SF3 needs it for fundamentals overlap; SF2 may want it for firm characteristics; PEAD needs it; accruals/GP need it). Build `SharadarSF1Reader` (ARQ) in Week 1 regardless of line ordering. This is non-claim engineering — building the adapter doesn't commit to running PEAD first.

## Confidence 0–100 and sharpest risk

| Claim | Confidence |
|-------|-----------|
| Inventory-first ordering is correct | 95 |
| SF3/13F has highest mechanism novelty of any Sharadar table | 85 |
| Form-4 purchase clusters are density-dead in liquid US universe | 55 |
| At least one of SF3/SF2/SF1 yields promotable CS alpha | 20 |
| PEAD E1 produces clean kill (not promotion) if D-pass | 75 |
| Program economics (measure → kill or promote) beats Full-Stop-forever | 60 |
| SF1 entitlement exists under the current subscription tier | 70 |

**Sharpest risk:** The Nasdaq Data Link "Sharadar Core" bundle may not include SF2 and SF3. SF1 is the core product; SF2 and SF3 are often premium add-ons. If only SF1 is entitled, Lines 1–2 collapse immediately, and we're left with PEAD F0 remeasure + accruals/GP as the only play. That's two lines from one table, both with strong null priors (Martineau PEAD, Sloan accruals attenuated post-publication). In that scenario, the program likely hits Full-Stop re-seal after 2 honest kills — which is still a clean outcome but gives the human less exploration per dollar of subscription.

**Second risk:** Year concentration will be the dominant failure mode for any line that survives F0. The 2019–2025 window has 2020 (COVID crash/recovery) and 2022 (bear market) as extreme folds. Any event-driven strategy (insider clusters during crashes, 13F rebalancing during volatility) will concentrate P&L in those years. The ~25% year-share gate is the hardest gate in the family law, and it's the one most likely to kill a line that otherwise looks promising.

## Attacks on meta-synthesis order

### Attack 1: The meta optimizes for wiring cost, not expected alpha

The meta-synthesis orders the program as:

1. Inventory
2. PEAD F0 remeasure (Track A) ∥ Form-4 density (Track B)
3. Accruals/GP if both kill
4. SF3/13F "last"

The stated reason for PEAD-first: "PEAD F0 helpers already exist — cheapest path from unmeasured to scientific null or sealed tape." This is **process logic masquerading as alpha logic**. The question is not "which line costs the fewest lines of Python to measure?" — it's "which line has the highest probability of producing a promotable CS edge given the Martineau prior, the settled residual/R2-1 nulls, and the structure of the Nasdaq data product?"

On expected alpha:

- **PEAD** (SF1): 40 years of literature, Martineau (2022) shows attenuation in liquid US, electronic trading has shrunk the window. Prior probability of promotion: ~10–15%.
- **Form-4** (SF2): Cohen–Malloy–Pomorski (2012) show purchase clusters work, but after publication, after decimalization, after SEC EDGAR modernization. Prior probability: ~15–20%, but density risk is real.
- **13F** (SF3): Novel mechanism for this program; institutional flows less studied than PEAD or insider transactions; slower signal means less arbitrage pressure. Prior probability: ~20–25%. Highest uncertainty, highest upside.

If you have 2–3 honest kills before Full-Stop re-seal, starting with the lowest-probability line is backwards. Start with the highest-uncertainty, highest-upside line so that an early kill doesn't consume the budget on a measurement the literature already suggests is dead.

### Attack 2: PEAD F0 "integrity remeasure" conflates data quality with alpha existence

The meta treats PEAD F0 as "measurement completion" because the original kill_line was data absence. But clearing D1–D7 doesn't make PEAD more likely to produce an edge — it just means we can finally measure what Martineau already measured and found attenuated. The meta writes "Martineau prior: liquid PEAD may be dead — dual-exit ready" as a caveat, then proceeds to make PEAD the primary track.

The correct framing: PEAD F0 remeasure is a **debt cleanup**, not an alpha priority. Wire SF1, clear the D-gates, and then either (a) run E1 knowing the prior is hostile, or (b) shelve E1 and use SF1 for accruals/GP first, which have different (though also attenuated) priors. The meta's ordering would have us spend Weeks 2–5 on PEAD E1 only to produce a "we told you so" kill — that's a waste of the re-open budget.

### Attack 3: The meta underrates SF3 and the adapter cost symmetry

All three Sharadar datatables (SF1, SF2, SF3) use the same Nasdaq Data Link API v3 pattern: `datatables/SHARADAR/{TABLE}.json` with cursor-based pagination and column selection. The existing TICKERS, SEP, and ACTIONS readers share a proven 200-line template. Building SF1, SF2, and SF3 adapters is **symmetric work** — SF3 is not harder than SF1, SF2 is not harder than SF3. The meta treats SF3 as "later" and PEAD as "now" based on the accidental fact that PEAD F0 has a driver file, but the driver is just a gate evaluator — it calls an adapter that doesn't exist. The real work is the adapter, and that work is the same for all three tables.

If all three adapters cost ~200 lines each, the ordering should be determined by alpha priors, not by which driver file happens to exist. The existing PEAD F0 driver saves maybe 100 lines of gate-evaluation code — it doesn't justify putting PEAD first.

### Attack 4: Parallel F0 on SF2 + SF3 is correct; parallel PEAD F0 is redundant

The meta proposes PEAD F0 (Track A) ∥ Form-4 density (Track B). This is the wrong parallelization. Both SF2 and SF3 need F0 (density/integrity) before any portfolio work. Both are new adapter builds. Running SF2 F0 ∥ SF3 F0 in Week 2–3 is genuine parallelism — two independent adapters, two independent density probes, no shared state. PEAD F0, by contrast, depends on SF1 which is a shared dependency for both SF2 and SF3 (for fundamentals overlap filters). Building SF1 in Week 1 as shared infrastructure, then running SF2 F0 ∥ SF3 F0 in Week 2, then deciding which line enters E1 first, is the efficient schedule. PEAD E1 can happen after SF3 and SF2 both resolve — it's the fallback, not the vanguard.

---

**Verdict:** The meta-synthesis is a reasonable consensus but has the ordering inverted. It treats PEAD as the primary line because the measurement gap is most visible, not because the alpha thesis is strongest. The correct program chases mechanism novelty (ownership) before cleaning up old debts (earnings surprises), and parallelizes the adapter builds that are genuinely independent. If the human only gets 2–3 kills before re-seal, make them count.
