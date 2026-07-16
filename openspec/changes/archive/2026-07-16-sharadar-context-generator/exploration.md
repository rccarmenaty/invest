# Exploration: Sharadar point-in-time MarketContext generator — liquidity-screen baseline research

**Change**: `sharadar-context-generator`
**Date**: 2026-07-15 (research refresh)
**Engram**: `sdd/sharadar-context-generator/explore` (obs #3034, merged/updated)
**Branch**: `feat/sharadar-context-generator`
**Scope contract**: A **standalone generator** that produces `market-context-v1` JSON from Sharadar TICKERS + SEP (+ ACTIONS) and a configurable liquidity screen. It **writes context only** and **must not invoke replay**. Replay (`BacktestRun.replay`) consumes the generated JSON unchanged through the existing `BacktestContextJsonReader`.

Prior decisions (settled, not re-litigated): Engram `architecture/backtest-data-layer` (SEP-only, liquidity-screen universe, SQLite snapshot), `reference/backtest-data-providers` (SEP schema confirmed). Change 1 (`sharadar-sep-adapter`) and the TICKERS/ACTIONS readers (`sharadar-reference-data-adapter`) are DONE + archived.

> This refresh merges the prior exploration (Engram #3034) and adds the requested **Liquidity-screen baseline research** section (§5) with external, citation-backed defaults. The earlier proposal ($10 price / 20-day median $10M / 252 observed bars) is retained as the **core momentum-research** profile but is now grounded and contextualized rather than asserted.

---

## Current State (seams that will carry thresholds)

- `src/invest/adapters/sharadar_market_data.py` (`SharadarMarketDataReader`): SEP-only, `fetch`/`fetch_range` → `FixtureInputs`. Cursor pagination via the Nasdaq datatables envelope (`datatable.columns`/`data`, `meta.next_cursor_id`), injected `httpx.Client`, bounded retry (401/403 no-retry; 429/5xx backoff). `.gitignore` covers `fixtures/snapshots/sharadar/` and `*.sqlite`.
- `src/invest/adapters/sharadar_tickers.py` (`SharadarTickersReader`): fetches `SHARADAR/TICKERS` columns `ticker, exchange, category, firstpricedate, lastpricedate, isdelisted` and translates provider vocabulary into plain facts. **Security-type/listing eligibility is already decided here**: `is_primary_common_stock` is `True` only when `category ∈ {"Domestic Common Stock", "Domestic Common Stock Primary Class"}` **and** `exchange ∈ {"AMEX", "ARCA", "NASDAQ", "NYSE"}`. `listed_date = firstpricedate`, `delisted_date = lastpricedate` (when `isdelisted`). Every other category (ETF, fund, preferred, warrant, ADR, unit, secondary common class) falls out as `is_primary_common_stock=False`. **This is the authoritative seam for "eligible security types/listings"; the liquidity screen must reuse it, not redefine it.**
- `src/invest/domain/market_context.py`: frozen value objects `CoverageWindow`, `EligibilityWindow(eligible: bool)`, `BlockerWindow(reason)`, `SymbolContext`, `MarketContext`. Hard invariants (construction-time, `MarketContextInvalidError`): (1) `BlockerWindow` REJECTS `SYMBOL_INELIGIBLE` — delisting/ineligibility must be an `EligibilityWindow(eligible=False)`, never a blocker; (2) blockers must not overlap an ineligible interval; (3) eligibility/blockers nest inside coverage; (4) no overlapping windows within a symbol. Only `CORPORATE_ACTION`/`EARNINGS_CONTEXT_MISSING` are valid blocker reasons; this change has no earnings source, so it emits zero `EARNINGS_CONTEXT_MISSING`.
- `src/invest/adapters/backtest_context_json.py` (`BacktestContextJsonReader`): strict Pydantic (`extra=forbid, strict=True`) parser of `market-context-v1` JSON → `MarketContext`. `fixtures/backtest/market-context.json` is the hand-authored fixture. The generator's output seam is a companion **writer** that targets this schema; reader/`MarketContext`/`BacktestRun` stay unchanged.
- `src/invest/application/backtest_run.py` (`BacktestRun.replay`): calls `market_context.require_complete(replay_dates, universe.symbols)` up front (fail-closed across the full roster), then narrows per-day via `market_context.eligible_symbols`. `Universe.symbols` is a flat, non-time-varying tuple — **point-in-time behavior lives entirely in `MarketContext`, not in a time-varying universe list.**
- `src/invest/domain/momentum` (scanner): hard floor `>= 253 daily bars per symbol` (252 momentum look-back + candidate day) or reject with `insufficient-history`. **This is a second hard seam**: any observed-bar / IPO-seasoning default below 253 does not actually let a symbol trade earlier — the scanner still rejects it. Seasoning defaults govern *coverage/eligibility*, not *tradability trigger eligibility*.
- `src/invest/adapters/cli.py`: `backtest_main` requires `--market-context <path>`; `--source {fixture,alpaca,sharadar}` is wired. New `invest-generate-context` is a sibling entrypoint. `tests/test_boundaries.py` AST-enforced hex purity is **hardcoded to `SharadarMarketDataReader`** — new reader/builder class names need their own explicit boundary checks.
- SPEC.md §2.1 documents two **distinct** universes (see §5.1): a LIVE/paper execution universe and a replay/backtest universe. Only the latter is this generator's concern.

## Affected Areas

- `src/invest/adapters/sharadar_market_data.py` — do **not** modify; new builders are siblings, not extensions (different cardinality, no OHLC adjustment, no calendar buffer).
- New `src/invest/domain/liquidity_screen.py` (pure, Decimal-only, no wall-clock) — price floor, rolling N-day dollar-volume floor (`close × Decimal(volume)`, SEP-adjusted), primary-common-stock check (reuses `SharadarTicker.is_primary_common_stock`), IPO seasoning as **observed-bar count** (calendar-free). **All thresholds explicit parameters with profile defaults — never a single hardcoded value.**
- New `src/invest/domain/market_context_builder.py` (pure) — run-length-encodes per-day eligibility/blocker decisions into windows, enforcing the invariants above (filter corporate-action blockers out of ineligible windows; merge same-day multi-event actions into one contiguous blocker).
- New `BacktestContextJsonWriter` (mirror of `SnapshotWriter`) — serializes generated context to `market-context-v1` JSON. Zero changes to reader/`MarketContext`/`BacktestRun`.
- `src/invest/adapters/cli.py` + `pyproject.toml` — `invest-generate-context` entrypoint.
- `tests/test_boundaries.py` — explicit AST checks for the new class names.
- `fixtures/backtest/market-context.json` — stays a test artifact; generated output is a separate path.

---

## 5. Liquidity-screen baseline research

### 5.1 Live vs backtest universe — do not conflate (SPEC §2.1)

| Universe | Source | Numeric rules | Who builds it | This generator? |
|---|---|---|---|---|
| **Live / paper execution** | SPEC §2.1 "Live universe" | S&P 500 + Nasdaq 100 (~600–800); avg daily dollar volume **> $10M**; price **> $5**; Alpaca `tradable` flag; rebuilt nightly; "no microcaps ever" | `ref-data` CronJob from **Alpaca** | **No** |
| **Replay / backtest** | SPEC §2.1 "Replay/backtest universe" | "point-in-time constituents **or a broader historical liquid-universe screen**"; never today's index retroactively; delisted/merged/renamed/split-adjusted represented or excluded with a logged reason | This generator from **Sharadar** | **Yes** |

The backtest universe has **no numeric thresholds in SPEC** — only the freedom to use a "broader historical liquid-universe screen." The research report §6.2 ("Core 52-Week-High Momentum Breakout" baseline) supplies the specific screen numbers and an explicit parameter grid (price 5/10/20; dollar volume 5/10/25M; IPO seasoning 126/252 days). SPEC's live $5/$10M pair is **one point on that same grid, not a contradiction**. The generator defaults to the report §6.2 baseline (see §5.6) but exposes every threshold.

### 5.2 What the data seams already decide (no research needed)

- **Eligible security types / listings**: decided by `SharadarTickersReader` (§Current State). Primary common stock = `Domestic Common Stock` / `Domestic Common Stock Primary Class` on `AMEX/ARCA/NASDAQ/NYSE`; everything else excluded. The screen reuses `is_primary_common_stock`; it does **not** re-derive security type.
- **Dollar-volume computability**: SEP gives split/dividend-adjusted `close` and `volume` (closeadj applied adapter-side). Dollar volume = `close × Decimal(volume)`, point-in-time consistent. No external data needed.
- **Observed-bar / IPO-seasoning floor**: the scanner's 253-bar hard floor is the binding minimum for *trading*; the screen's seasoning only governs *eligibility/coverage*. See §5.7 product-vs-technical.

### 5.3 External evidence and citations

Citations are labeled **[primary]** (regulator/statute or the academic paper itself) or **[secondary]** (encyclopedia/report citing primary). Claims I could **not** live-verify against the original publisher (publisher blocked automated access) are marked **[unverified-live]** with the authoritative substitute used.

**Share-price mechanics**
- **[primary]** SEC, *17 CFR §240.3a51-1 — Definition of "penny stock"*, paragraph (d): a non-exempt equity security is a "penny stock" when it does **not** "hav[e] a price of five dollars or more" → the regulatory line is **< $5**. Paragraph (a)(2)(i)(C) references a **$4 minimum bid price** as one criterion for the exchange/ATS listing-standard *exemption* from penny-stock designation. Verified via Cornell LII mirror (eCFR itself bot-blocked): https://www.law.cornell.edu/cfr/text/17/240.3a51-1
- **[primary]** Exchange continued-listing minimum bid price = **$1.00/share** (NYSE §802.01C average closing price; Nasdaq Rule 5810 minimum bid price), with a 30-consecutive-business-day deficiency trigger. **[unverified-live]** against the NYSE Listed Company Manual / Nasdaq Rulebook (both JS-gated/bot-blocked); corroborated by **[secondary]** Skadden, Arps, Slate, Meagher & Flom, "SEC Approves Nasdaq Rule Change on Reverse Stock Splits and Minimum Bid Price Compliance Periods; NYSE Proposes a Similar Rule Change" (Nov 14, 2024), https://www.skadden.com/insights/publications/2024/11/sec-approves-nasdaq-rule-change , as surfaced through Wikipedia "Penny stock" (https://en.wikipedia.org/wiki/Penny_stock, retrieved 2026-07-15).
- **Important nuance**: exchange-listed NMS stocks are **exempt** from the penny-stock designation *regardless of price* (17 CFR §240.3a51-1(a); Wikipedia "Penny stock", "Regulation"). A sub-$5 listed name is "low-priced," not legally a "penny stock." **So a price floor above $5 is a tradability/risk choice, not a regulatory requirement** for listed names. Do not frame $5 as "legally required."

**Tradability / liquidity proxies**
- **[primary]** Amihud, Y. (2002), "Illiquidity and stock returns: cross-section and time-series effects," *Journal of Financial Markets* 5(1), 31–56. The **Amihud illiquidity measure** `ILLIQ = |daily return| / daily dollar volume` is the standard price-impact-per-dollar-traded proxy. (Dedicated encyclopedia page bot-blocked/404; bibliographic citation is verifiable in any academic database. Formula is the canonical definition.)
- **[primary]** Kyle, A. S. (1985), "Continuous Auctions and Insider Trading," *Econometrica* 53(6), 1315–1335 — market depth/impact foundations (informed trading, "depth" parameter). Cited as the theoretical basis for why absolute turnover is only a proxy for executable depth.
- **[primary]** Lee, C. M. C., & Swaminathan, B. (2000), "Price Momentum and Trading Volume," *Journal of Finance* 55(5), 2017–2069 — already the project report's ref [4]; documents that **past turnover carries information about momentum persistence**, supporting "volume as a ranking/context feature, not an untested hard veto" (SPEC §2.3). SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=92589
- **[secondary]** Amihud, Mendelson & Pedersen (2013), *Market Liquidity*, Cambridge University Press (overview of liquidity pricing); Acharya & Pedersen (2005), "Asset pricing with liquidity risk," *JFE* 77 — both surfaced via Wikipedia "Market liquidity" (https://en.wikipedia.org/wiki/Market_liquidity), retrieved 2026-07-15. Used only to frame the spread/impact/liquidity-premium argument, not for any numeric threshold.

**Momentum formation / IPO seasoning**
- **[primary]** Jegadeesh, N., & Titman, S. (1993), "Returns to Buying Winners and Selling Losers," *Journal of Finance* 48(1), 65–91 — project report ref [1]; the J-months/K-months cross-sectional momentum formation. The 12-1 default (≈252 trading-day formation) is what makes **252 observed bars** the natural, research-aligned seasoning floor, and it coincides with the scanner's 253-bar hard requirement. Wiley: https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1993.tb04702.x

**Explicitly inconclusive / practitioner-only (not research-validated)**
- The **specific dollar-volume thresholds** ($5M / $10M / $25M) are **not** established by any cited paper. They are **practitioner capacity heuristics** that scale with assumed account AUM and participation rate. No academic source mandates them; they must be exposed as parameters and labeled as capacity choices (see §5.5, §5.7).

### 5.4 Candidate profiles (exact defaults)

All profiles compute dollar volume as SEP-adjusted `close × volume`; rolling statistic = **median** (robust to single event-day spikes; mean is a parameter); seasoning = **observed trading bars** (calendar-free). Eligible types/listings reuse `SharadarTickersReader.is_primary_common_stock` (see §5.2).

| Lever | A — Conservative / institutional / implementation-aware | B — Core momentum-research (recommended default) | C — Broad exploratory |
|---|---|---|---|
| **Share-price floor** | **$10** (2× SEC $5 penny line; comfortably above $1 delisting floor; narrows relative spreads) | **$10** (report §6.2 baseline; 2× SEC $5 line; removes sub-$5 microcap feed per SPEC "no microcaps ever") | **$5** (exactly the SEC penny-stock line 17 CFR §240.3a51-1(d); SPEC §2.1 live floor) |
| **Rolling dollar-volume threshold** | **median 20-day ≥ $25M** (report grid upper bound; at ~1% ADV ≈ $250k/day executable) | **median 20-day ≥ $10M** (report §6.2 baseline; equals SPEC live $10M) | **median 20-day ≥ $5M** (report grid lower bound) |
| **DV window / aggregation** | 20-day median (or 63-day median for steadier estimate) | 20-day median | 20-day median (or mean, to widen coverage) |
| **IPO seasoning / observed bars** | **252 trading days** (J-T 12-month formation; ≥ scanner's 253-bar floor) | **252 trading days** (same; calendar-free bar count) | **126 trading days** (≈6-month J-T 6-1 variant) — ⚠️ scanner still hard-rejects <253 bars, so this only widens *coverage*, not *earlier entry* |
| **Eligible types / listings** | Primary common stock on **NYSE/Nasdaq only** (drop AMEX/ARCA; smallest microcap tilt) | Primary common stock on **AMEX/ARCA/NASDAQ/NYSE** (adapter default) | Same primary common stock on AMEX/ARCA/NASDAQ/NYSE — **do not** relax to ETFs/funds (corrupts the equity momentum cross-section) |
| **Expected coverage** | ~300–500 names | ~600–800 names (SPEC Tier-0 target) | ~1000+ names |
| **Bias** | Large-cap tilt; may dilute momentum (momentum historically stronger in mid/smaller caps) | Balanced; matches project's evidence-reviewed baseline | Microcap/illiquid bias; recent-IPO noise; widest spreads |
| **Capacity / fill realism** | Highest; best for larger AUM | Moderate; fine for personal-sized account | Lowest; report §11 warns "microcaps and illiquid stocks can create spectacular historical results that cannot be executed" |
| **Overfitting risk** | Low | Low–Medium | High (use only for a one-time sensitivity sweep, never as the ship baseline) |

### 5.5 Why absolute dollar-volume is only a proxy — and ADV-fraction / impact restriction should be DEFERRED

Absolute rolling dollar volume is a **tradability proxy**, not a tradability measure. It correlates with spread, depth, and price impact but does not capture them: a name can post $10M DV concentrated on one earnings day (the **median** mitigates this), or carry wide spreads despite adequate turnover. Amihud's `|return|/DV` normalizes by price movement per dollar traded — a direct impact proxy (Amihud 2002); Kyle (1985) formalizes depth/impact. So the absolute DV floor is the right **coarse universe-eligibility** filter; it is the wrong instrument for **per-trade capacity**.

An **ADV-participation cap** (e.g., order size ≤ 1% of trailing ADV) or an **Amihud-style impact cap** is a capacity/execution control that depends on **order size and account equity** — inputs the context generator does **not** have (it writes eligibility windows only). SPEC §2.8 makes `risk-gate` the single money authority, and report §9.4 already states "Reject entries whose planned size is too large relative to average daily dollar volume." That control belongs in the **risk-gate / sizing layer**, not in the generator.

**Recommendation: defer the ADV-fraction / price-impact restriction to the risk-gate/sizing change.** Rationale: (1) keeps the generator single-responsibility (eligibility windows, not capacity); (2) avoids coupling eligibility to account size, which would make the backtest universe AUM-specific and non-reproducible; (3) the report §10.2 already requires modeling higher slippage for small stocks and high participation rates, partially compensating until the explicit cap exists. **Optional, design-phase scope decision (not a baseline threshold):** the generator may emit a per-symbol rolling ADV series as context *metadata* for the risk-gate to consume later — but that is additive, not a screen threshold.

### 5.6 Recommended default for this project — and when to pick another

**Default to Profile B (Core momentum-research): price ≥ $10, median 20-day dollar volume ≥ $10M, primary common stock on AMEX/ARCA/NASDAQ/NYSE, 252-trading-day observed-bar seasoning.** Expose every threshold (price floor, DV floor, DV window, DV aggregation, seasoning bars, listing-exchange set) as a parameter with these defaults.

Why B fits the stated strategy: it is the project's own evidence-reviewed baseline (report §6.2); it hits the SPEC Tier-0 ~600–800-name target; $10 is 2× the SEC $5 line (real tradability margin, not a legal minimum); 252 observed bars aligns with both the J-T 12-month formation and the scanner's 253-bar hard floor; and it equals the SPEC live $10M DV figure, so the backtest universe is *no more permissive than* the live universe on the liquidity axis (the backtest is intentionally *broader in name coverage* but *comparable in liquidity*, which is the SPEC intent).

**Pick Profile A instead if** the user is sizing for a materially larger AUM where $10M DV names cannot absorb the intended participation without impact — the $25M floor raises executable capacity at the cost of a smaller, large-cap-tilted universe (expect some momentum dilution).

**Pick Profile C only as a one-time sensitivity sweep** to measure how much of the backtest's edge is a microcap/illiquid artifact (report §11 failure mode). Do **not** ship C: it admits exactly the "spectacular historical results that cannot be executed" the report warns against, and its 126-day seasoning does **not** actually allow earlier entries because the scanner hard-rejects <253 bars.

### 5.7 Product decisions vs technical design decisions

**Product decisions (require user sign-off — not settleable in design):**
- **Target AUM / capacity assumption** — determines whether $10M or $25M DV is appropriate. Capacity is a function of AUM; this is the single most important product input.
- **Listing-exchange set** — NYSE/Nasdaq only (Profile A) vs include AMEX/ARCA (Profile B). Affects microcap tilt and ETF/ETP leakage on ARCA.
- **Dual-class / secondary common-stock classes** (e.g., non-voting classes, `Domestic Common Stock Secondary Class`) — currently **excluded** by the adapter's 2-category whitelist. Include them or not?
- **ADRs / foreign primary listings** — currently excluded by category. Include or not?
- **Whether Profile C is ever run** — and if so, only as a documented sensitivity sweep, never the ship baseline.
- **Optional universe-size cap** (e.g., top-N most liquid survivors) vs all survivors — a capacity/coverage tradeoff.

**Technical design decisions (settleable in design phase without user):**
- **Median vs mean** for the rolling DV statistic → recommend **median** (robust to event spikes).
- **Rolling window length** as a parameter (default 20; configurable 20/63/252).
- **Seasoning counted in trading bars** (calendar-free) vs calendar days → already decided: bars (keeps domain clock-free).
- **Dollar volume from adjusted close × adjusted volume** (SEP closeadj) for point-in-time consistency.
- **Eligibility recompute cadence** = daily rolling (SEP is already daily-bar).
- **Run-length encoding** of per-day eligibility into `EligibilityWindow` (per prior exploration invariants).
- **Optional rolling-ADV metadata emission** for the downstream risk-gate (additive, deferrable).

---

## Threshold conflict — resolved (see §5)

SPEC §2.1 "Live universe" ($5/$10M, Alpaca tradable flag) governs the **live/paper execution** universe — a different concept, not what this generator produces. SPEC §2.1 "Replay/backtest universe" gives **no numeric thresholds**, only "point-in-time constituents or a broader historical liquid-universe screen." Report §6.2 is the specific, research-aligned source for this screen, with an explicit test grid (price 5/10/20; DV 5/10/25M; seasoning 126/252). SPEC's $5/$10M is one point on that grid. **Default to report §6.2 baseline (Profile B in §5.6); expose every threshold as a parameter.** Numeric DV thresholds are practitioner capacity heuristics, not research-validated constants (§5.3).

## Two-pass universe architecture (non-obvious finding)

Today's `Universe.symbols` is small/pre-known and fed into `fetch_range`. This change inverts that: TICKERS discovery is broad (SPEC Tier-0: ~8,000 listings → ~600–800 survive), not scoped to a known list. Recommended pipeline: (1) fetch TICKERS broadly (optionally server-side filter by exchange/category to cut candidates before any SEP fetch), (2) fetch SEP bars across candidates for the full range, (3) run the liquidity screen over those same SEP bars to determine day-by-day eligibility, (4) the union of ever-eligible symbols becomes the final `Universe.symbols` roster, (5) reuse the **same** already-fetched SEP bars as backtest input — no second narrower fetch. Design phase must pin down server-side TICKERS pre-filtering (recommended, cheaper) and the daily rolling recompute cadence (natural since SEP is daily). This scalability concern affects real runs, not the mocked-httpx test suite.

## Recommendation

Sibling builders (not extensions of `SharadarMarketDataReader`); a pure-domain `liquidity_screen.py` + `market_context_builder.py` as two small modules; a JSON-output seam (writer + `invest-generate-context` CLI) that leaves `MarketContext`/`BacktestRun`/`BacktestContextJsonReader`/`backtest_main`'s `--market-context` flag untouched. **Default liquidity profile = B (§5.6)**; every threshold a parameter. **Defer ADV-fraction/impact restriction to the risk-gate/sizing change (§5.5).**

## Scope / Slicing (critical)

Estimated total ~2000–3000+ authored lines — well beyond one SDD change or the 400-line review budget. Split into two SDD changes, each internally chained into 2–3 PRs (mirrors change 1's PR1/PR2 split):

| Sub-change | Contents | Rough lines |
|---|---|---|
| 2a `sharadar-reference-data-adapter` (DONE/archived) | TICKERS + ACTIONS readers | shipped |
| 2b `market-context-generator` (this change) | `liquidity_screen.py` + `market_context_builder.py` + `BacktestContextJsonWriter` + CLI wiring + boundary tests + e2e | ~1100–1750 |

2b consumes 2a's outputs (ticker classification + corporate-action events). 2b itself likely needs 2–3 chained PRs (screen; builder+writer; CLI+boundary+e2e) to stay under the 400-line review budget per slice.

## Risks

- `tests/test_boundaries.py` Sharadar-isolation guard is hardcoded to `SharadarMarketDataReader` by name — new classes need explicit AST boundary tests or they silently escape the backtest-only guard.
- Real TICKERS/SEP response cardinality/pagination unverified against the live API (`MAX_PAGES` open question); confirm during design/apply.
- Broad ~8,000-ticker fetch is a materially larger data-volume operation than change 1's narrow per-symbol fetch; needs an explicit design-phase sizing/cadence decision.
- **Numeric DV thresholds ($5M/$10M/$25M) are capacity heuristics, not research-validated** (§5.3) — must be exposed as parameters and labeled as AUM-dependent.
- **$5 is not a legal floor for listed names** (NMS exemption) — frame the price floor as a tradability choice, not a regulatory requirement.
- **126-day seasoning (Profile C) does not relax the scanner's 253-bar hard floor** — coverage gain only, not earlier entry.
- Could not live-fetch SEC.gov/eCFR/NYSE/Nasdaq Data Link directly (bot-blocked/JS-only); verified via Cornell LII (authoritative CFR mirror) and Wikipedia (secondary, citation-checked). If any exchange-rule detail beyond the $1 minimum bid becomes load-bearing, re-verify against the live NYSE Listed Company Manual §802.01C and Nasdaq Rule 5810.
- **ADV-fraction/impact restriction deferred** — without it the backtest may overstate capacity for larger AUM; report §10.2 slippage modeling partially compensates.

## Ready for Proposal

Yes — for this change (`market-context-generator`): scope is well-bounded (liquidity screen + window builder + writer + CLI + boundary/e2e tests), the liquidity baseline is now evidence-grounded (§5), and it consumes only the already-archived 2a outputs. Open product decisions (§5.7: AUM/capacity, listing-exchange set, dual-class/ADR inclusion, Profile-C usage) should be surfaced to the user at proposal time but need not block the proposal — they are parameterized, not hardwired.
