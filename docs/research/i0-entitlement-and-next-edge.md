# I0 entitlement probe + next-edge decision brief

**Date:** 2026-07-21
**Status:** non-claim decision brief — no returns measured, no gates run, `capital_go` untouched (false)
**Authority:** human exploration ask ("which path to a new strategy/edge") after Full-Stop seal; this document is **input to an event-only re-open decision**, not a re-open itself
**Law respected:** `docs/research/full-stop-seal.md`, Round-4 meta-v2 (`docs/research/adversarial-debate/round-4/outputs/meta-synthesis-v2.md`), `CONTEXT.md`

## 1. I0 inventory probe — measured today

Round-4 meta-v2 Week-0 inventory, finally executed (read-only datatable calls under `NASDAQ_DATA_LINK_API_KEY`; per-table `qopts.per_page≤5`; no strategy code, no artifact driver built — that stays PRD-gated).

| Table | Live? | Evidence |
| --- | --- | --- |
| **SEP** | ✅ current | AAPL close 2026-07-20 returned |
| **EVENTS** | ✅ current, deep | rows 1998→2026-04-30; 8-K item codes (`22` = Results of Operations = Item 2.02 earnings) |
| **METRICS** | ⚠️ snapshot-only | 1 row (2026-07-20); no history — reference data, not a factor tape |
| **SP500** | ✅ current | constituents to 2026-07-20 |
| **SF1** | ❌ sample only | bare query returns 2 static MRY rows (2022–23); `dimension=ARQ` → 0 rows; any `datekey.gte` filter → 0 |
| **SF2** | ❌ sample only | 5 static rows, filingdate 2018 (AAPL and MSFT both) |
| **SF3** | ❌ sample only | static rows, calendardate 2015 |
| **DAILY** | ❌ sample only | static rows, date 2018 |
| **SFP** | ❌ empty | 0 rows (no ETF prices) |

**I0 verdict:** subscription = **Sharadar US Equities price/event tier** (SEP + EVENTS + METRICS + TICKERS + ACTIONS + SP500). **SF1 / SF2 / SF3 / DAILY are not entitled** — the "rows" are static demo samples that ignore recent-date filters. PEAD F0 and Form-4 remain **data-blocked under Sharadar**, exactly as when PEAD F0 published kill_line on `no_sf1_or_sec_original_tape`.

Under Round-4 law the strict branch is: *"I0 fail (only SEP entitled) → re-seal Full-Stop; do not invent price alpha."* One material amendment to that premise: **EVENTS is live with 1993/1998→present depth**, which R4 only parenthesized ("and DAILY/EVENTS if present"). Earnings-announcement filing dates for the whole universe are derivable from entitled data today.

## 2. The power lesson that constrains every next design

CMFT Stage A died **underpowered-stop**: monthly cross-sectional formations give n≈324 over 27 years → MDS ≈ 162 bps against a 50 bps bar. That is structural, not fixable by better features: any monthly-formation CS program on this tape is underpowered for realistic effect sizes.

**Event designs invert this.** Earnings announcements ≈ 6,000 tickers × 4/yr × 25 yr ≈ O(10⁵) events; Form-4 purchase clusters ≈ O(10⁴–10⁵). Date-clustered inference on event cohorts (the Gate-1a machinery, `src/invest/application/event_study_excess.py`) already demonstrated t=5.3 detection capability at h60 on an 11k-event cohort. The next research dollar should buy an **event-anchored design**, not another formation-calendar design.

## 3. External evidence (deep-research summary, 2026-07-21)

| Line | Evidence for | Evidence against | Net prior |
| --- | --- | --- | --- |
| **Form-4 opportunistic/cluster insider buys** | Cohen–Malloy–Pomorski (JF 2012): opportunistic trades ≈ 82 bps/mo VW abnormal; routine ≈ 0. AQR follow-up (insider opportunism). Small-cap insider buys show multi-month abnormal drift in recent practitioner replications | Post-publication crowding unquantified for 2020s; long-lived only in small/mid caps | **Strongest unmeasured family.** Never touched by this repo; legal-informed-trading mechanism, not a price artifact |
| **PEAD via as-filed SUE** | Earnings anomalies are the most persistent class in McLean–Pontiff; two 2025 papers argue PEAD alive when microcaps included | Martineau: dead for large caps since ~2006, fading even in microcaps; crowded | **Contested.** Dual-exit-ready; measurement debt (never measured here) but weaker prior than insiders |
| **Announcement-window return drift** (rank on announcement-day abnormal return, no fundamentals) | Chan–Jegadeesh–Lakonishok earnings momentum; announcement return is a strong surprise proxy when estimates are absent; implementable with **entitled data only** (EVENTS code 22 + SEP) | Same decay literature as PEAD applies; adjacent to the scarred price family; filing-date vs announcement-timestamp lag must be handled conservatively (+1 open entry) | **Cheapest falsifier** — zero new data cost |
| Quality/GP, accruals | Novy-Marx GP robust gross | Chen–Velikov: average anomaly ≈ 0 net; accruals decayed hard | Contingent (needs SF1) — unchanged L4 |
| 13F / SF3 | — | 45-day lag; copycat literature unkind | Last, unchanged |
| More price-only CS (trees, GKX-style) | — | Full-Stop; CMFT power wall; Avramov-class net-of-cost critiques of ML alphas | **Stay closed** absent fundamentals/event conditioning |

**Base-rate honesty (Chen–Velikov 2023):** after transaction costs + post-publication decay + decimalization, the *average* published anomaly nets ≈ 0 and the strongest ≈ 10 bps/mo in liquid names. Survival habitat is small/mid caps with high arbitrage costs — which suits small retail capital (no capacity problem) but demands an ADV floor and low turnover. Realistic promotable-line probability per funded line: **~15–30%** (R4 meta said 25–35; Kimi said 12).

**Implementability constraints (product reality, not research gates):** EU retail execution, long-only (no short leg — long-short spreads stay the science object; the product would be the long leg), multi-day/multi-month holds preferred ("not time constricted"), small capital. Event strategies with h60 holds and weekly-or-slower scans fit; capital default stays **honest liquid beta** until an implementability PRD passes.

## 4. The fork (human decision)

### Option A — $0 data: SEC EDGAR tape → Form-4 line (recommended)

SEC publishes for free: **Insider Transactions Data Sets** (structured Forms 3/4/5 derived from XML, 2006→present, quarterly TSV) and full Form 4 XML back to 1996 via EDGAR indexes; acceptance datetimes give an honest known-time (PIT) axis. Also free: **Financial Statement Data Sets** (as-filed XBRL numbers, 2009q2→present) — a future SF1 substitute for the PEAD/quality queue.

Sequence (mirrors R4 meta-v2, source swapped):

1. **CFOB-D density memo** — histogram of open-market purchase events (transaction code P) after ADV/liquidity filter; cluster definition (≥2 distinct insiders / 30d or officer-purchase); year-mass check (~25% law). **No returns.** Kill in memo if sparse or year-concentrated.
2. **CFOB-F0 integrity** — filing-vs-transaction lag audit, amendment handling, CIK→ticker mapping via entitled TICKERS, dedupe. Fail-closed gates in house D-gate style.
3. **CFOB-E1** — one event study: h60 open-to-open excess vs same-date eligible universe, date-clustered t, median as co-primary, year-share ≤25%, 10 bps costs, matched-SPY trade windows. Long-leg (purchases) primary. Dual-exit: kill_line or eligibility-only.

Cost: ~2–3 weeks engineering tax (XML/TSV ingestion, entity mapping). Buys the **highest-novelty, most-persistent unmeasured family** with power O(10⁴⁺) events and no subscription spend.

### Option B — paid accelerator: upgrade to Sharadar bundle (SF1+SF2)

Unlocks the R4 queue exactly as written (Form-4 density → PEAD D0–D7 *measured* → one E1) on a clean vendor tape; saves the EDGAR ingestion weeks and buys back the PEAD measurement debt in the same purchase. Pricing is login-gated on data.nasdaq.com — check the account's upgrade quote before deciding; if the annual cost exceeds a few months of Option-A engineering patience, A dominates.

### Option C — zero-new-data bridge: EVENTS-22 announcement-return drift

Rank on announcement-day abnormal return (EVENTS code 22 filing date, +1 open entry, h60 hold) on entitled SEP 1998→2025 (`fixtures/full-depth-sep/` already pulled). Reuses Gate-1a machinery nearly unchanged; the F0 (data feasibility) is already half-proven by today's probe. Weakest prior of the three (decay literature bites announcement drift hardest in liquid names) but the **cheapest possible falsifier** and the only one runnable this week. Fund only as the single active line if the human prefers spending zero on data and zero on EDGAR engineering first.

### Rejected (unchanged law)

Residual/R2-1/PEAD-null re-litigation without explicit PRD; ranking/DAMB rescue; CMFT T1 train on #74 artifact; LLM-on-prices; HMM as primary; SF3-first; factor-zoo ML before an event line survives; "we pay therefore edge."

## 5. Recommendation

1. **Commit this I0 memo** (closes R4 Week-0 honestly: fundamentals/ownership entitlement = FAIL, events entitlement = live).
2. **Human picks the fork** — recommended order: **A (CFOB via free EDGAR)** as the funded line; **B** only if the upgrade quote is cheap enough to be an obvious time-buy; **C** only as the single line if zero-cost-this-week matters most.
3. Whichever is picked: **new PRD + grill + named hypothesis** (event-only re-open), one line at a time, dual-exit precommitted, two sequential kills → re-seal Full-Stop without shame.
4. Capital stays **honest liquid beta** (VWCE) throughout; any surviving E1 buys only an implementability PRD, never `capital_go`.

## 6. Sources

- Cohen, Malloy, Pomorski — *Decoding Inside Information*, Journal of Finance 2012: https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2012.01740.x (SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1692517); AQR insight: https://www.aqr.com/-/media/AQR/Documents/AQR-Insight-Award/2018/Opportunism.pdf
- Martineau — *Rest in Peace Post-Earnings Announcement Drift*: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3111607; 2025 counter-evidence discussion: https://anderson-review.ucla.edu/is-post-earnings-announcement-drift-a-thing-again/
- McLean & Pontiff — *Does Academic Research Destroy Stock Return Predictability?*: https://www.hec.ca/finance/Fichier/McLean.pdf
- Chen & Velikov — anomaly nets after costs/decay/decimalization: https://www.sciencedirect.com/science/article/abs/pii/S1386418122000465 (and AFA viewpoint: https://afajof.org/management/viewp.php?n=46984)
- PEAD review: https://www.sciencedirect.com/science/article/pii/S2214635020303750; Quantpedia: https://quantpedia.com/strategies/post-earnings-announcement-effect
- SEC free tapes — Insider Transactions Data Sets & Financial Statement Data Sets: https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data, https://www.sec.gov/files/aqfs.pdf; Form 4 XML bulk (1996→present) index overview: https://sec-api.io/datasets/form-4-files; open-source reader: https://github.com/dgunning/edgartools
- Sharadar EVENTS eventcodes (22 = Results of Operations / Item 2.02): SHARADAR/INDICATORS `table=EVENTCODES` (probed 2026-07-21); help article: https://help.data.nasdaq.com/article/534-what-do-the-eventcodes-mean-in-the-sharadar-data
- Repo anchors: `docs/research/cmft-results.md` (power wall), `docs/research/gate1a-results.md` (event-study detection capability), `docs/research/pead-f0-results.md` (data-absence kill), `docs/research/full-stop-seal.md`
