# Momentum Breakout Trading System — Specification

**Status**: Proposed — revised for data, validation, and broker-rule safeguards; strategy layer re-aligned with the evidence review in `momentum_breakout_swing_trading_research_report.md`
**Date**: 2026-07-16 (data-authority + trailing-stop mitigation update; strategy revision 2026-07-13; original 2026-07-11)
**Broker**: Alpaca (paper first, live only after validation gates)
**Deployment target**: Local Kubernetes cluster
**Style**: Event-driven microservices, hexagonal architecture per service

---

## 0. Current Decision

Build a **paper-first swing-trading system** that selects established intermediate-term winners near their 52-week high, enters on objective trading-range breakouts, sizes positions mechanically, submits protected orders, and proves expectancy through replay/backtest plus paper trading before any live key is used.

The core architecture is accepted: **NATS JetStream + Postgres + small hexagonal services on local Kubernetes**. The hardening updates in this version are:

1. **Backtest/replay moves before paper execution** so obvious filter defects are found quickly.
2. **Authoritative decisions use consolidated daily data**, not IEX-only live volume.
3. **Broker/account-rule checks replace hard-coded PDT assumptions** because FINRA's intraday-margin framework is changing broker behavior during the 2026–2027 transition.
4. **Earnings, catalyst, corporate-action, and point-in-time universe data become explicit dependencies**.
5. **Bracket-order edge cases are handled explicitly** through reconciliation and safety halts.

**Strategy revision (2026-07-13)**: the evidence review in `momentum_breakout_swing_trading_research_report.md` re-ranks the strategy layers. The primary research model is the **Core 52-Week-High Momentum Breakout** (momentum-ranked candidate selection + 52-week-high proximity + trend/regime filters + trailing exits). The original day-0 spike detector is retained as the **benchmark control strategy** the Core model must beat in replay. Current implementation status and change sequence live in `ROADMAP.md`.

---

## 1. Purpose

Select liquid US stocks that are already proven intermediate-term winners trading near their 52-week high, enter swing trades automatically when an objective breakout confirms continuation, and exit via mechanical protective stops, trailing exits, and time stops.

This is **not forecasting**. The system reacts to confirmed movement. Its edge comes from:

1. **Candidate selection**: relative momentum ranking and 52-week-high proximity — the layers with the strongest academic evidence (report §3.1, §3.2).
2. Mechanical protective exits placed server-side at the broker, removing emotion.
3. A journal feedback loop that measures expectancy so filters can be tuned on evidence.
4. Point-in-time replay/backtesting that prevents survivorship-biased confidence.
5. Risk control designed in from the start: volatility-aware sizing and market-regime filters, because momentum returns are negatively skewed and crash-prone (report §3.5).

## 2. Trading Strategy

### 2.1 Universe

**Live universe**:

- S&P 500 + Nasdaq 100 constituents (~600–800 liquid names after dedupe).
- Filters: average daily dollar volume > $10M, price ≥ $10, tradable flag from Alpaca asset API. The $10 floor matches the backtest liquidity screen (`domain/liquidity_screen.py`) and the report §6.2 baseline; $5/$10/$20 remain in the test grid, but live and backtest universes must use the same value to keep Phase-3 paper results comparable to replay.
- Shortable flag may be recorded as a liquidity/marginability hint, but the strategy remains long-only.
- Rebuilt nightly.
- No microcaps ever — spike detection on illiquid names is a pump-and-dump feed.

**Replay/backtest universe**:

- Must use point-in-time constituents or a broader historical liquid-universe screen.
- Never backtest using today's index membership retroactively.
- Delisted, merged, renamed, split-adjusted, and corporate-action-affected symbols must be represented correctly or excluded with a logged reason.

### 2.2 Market-data authority

The system has two data tiers:

| Use | Acceptable data | Purpose |
|---|---|---|
| Intraday awareness | Alpaca IEX live feed or equivalent | Early warning only; no entry decisions |
| Daily decisions | Consolidated/SIP daily bars or delayed consolidated historical bars | Spike promotion, relative volume, breakout checks, ATR/MA calculations |
| Backtest/replay | Point-in-time adjusted historical bars + point-in-time universe/corporate actions — implemented via Sharadar SEP/TICKERS/ACTIONS (survivorship-bias-free, delisted names included) | Validation before paper/live |

Important rule: **relative volume and breakout decisions must not rely on IEX-only volume unless running an explicit degraded-data experiment**. IEX volume can diverge materially from full-market volume, so using it as the authoritative signal source can create false positives/negatives.

### 2.3 Candidate selection (Core 52-Week-High Momentum Breakout — primary model)

Momentum is a **selection effect before it is an entry signal** (report §3.1). A symbol becomes a `CANDIDATE` when all hold on the authoritative daily close:

| Layer | Baseline rule | Parameters to test |
|---|---|---|
| Relative momentum | Top 15% of universe by return from 252 to 21 trading days ago (12-1 month) | 6-1 / 9-1 / 12-1 lookbacks; top 10/15/20% |
| 52-week-high proximity | Close ≥ 95% of trailing 252-day high | 90/93/95/97%; new-high-only |
| Stock trend | Close > 50-day SMA > 200-day SMA; 200-day SMA rising over prior 20 days | EMA vs SMA; slope windows |
| Market regime | Benchmark close above its 200-day SMA, else no new entries | none / 100-day / dual-average |

Volume is **not** an entry veto. Past turnover carries information about momentum persistence (report §3.4), so volume features (turnover percentile, 5/20 volume ratio, breakout-day dollar volume) are tested as ranking/context features — never as an untested hard rule.

Hourly scans may pre-stage symbols that are trending toward a trigger, but **CANDIDATE promotion is a daily-close decision only**.

### 2.4 Entry trigger (objective and parsimonious)

- Entry signal: daily close above the prior 20-day high (current day excluded from the lookback).
- Execution: buy next session at the regular-hours open. Never fill at the signal close in replay unless a verifiable market-on-close process is modeled.
- Simultaneous signals are ranked by momentum rank, high proximity, and liquidity.
- The trigger stays simple by design: the edge is expected from selection and risk control; complex multi-condition triggers invite overfitting (report §5.2).

Parameters to test: 10/20/40/55-day breakout lookbacks.

### 2.5 Benchmark control strategy (day-0 spike detector — implemented)

The original spike detector is retained as the **control** the Core model must beat under identical replay assumptions (report ranks it "low as a stock-selection model"). Its rules, as implemented in `domain/scanner.py`:

| Rule | Threshold |
|---|---|
| Relative volume | today ≥ 2× 20-day average consolidated volume |
| Price move | ≥ 1.5× ATR(14) upward |
| Breakout | close above 20-day high |
| Not extended | price < 15% above 20-day MA |

Any Core-model result is reported **against this benchmark**: if momentum selection and high-proximity filters do not add value over the plain spike/breakout after costs and across subperiods, they do not ship.

### 2.6 Optional confirmation layer (house hypothesis — test separately)

The follow-through idea (price holds the breakout level for 1–2 sessions before entry) is a house hypothesis, **not** research-validated. Per the report's method (§7.2), it must be tested as one incremental feature against the frozen Core model — never silently bundled.

Safety checks that remain regardless:

- No earnings within the next 5 calendar days (binary event = coin flip, reject). Earnings-gap continuation is a **separate event strategy** (report §8), never merged into ordinary breakout entries.
- No overnight gap > 8% at entry (chase, reject).
- Catalyst presence is a soft journal flag, not a filter.

Data requirements:

- Earnings calendar comes from a configured `CorporateCalendarPort` provider before Phase 2 starts.
- Missing earnings data is fail-safe: reject or hold in `WATCHING`; never treat missing data as safe.
- Catalyst/news provider is optional for Phase 1, required before live trading if catalyst is used as a scored feature.
- Every rejection logs `stage`, `reason`, `data_source`, and `data_freshness`.

`CANDIDATE` that fails selection or safety checks → `REJECTED`, with reason logged. Rejections are journal gold — they tune the filters.

### 2.7 Trade management (mechanical)

Fixed profit targets truncate the right tail that pays for a momentum system (report §5.3). The target exit model is therefore **trailing**, not bracket-TP:

| Parameter | Target value (Core model) | Parameters to test |
|---|---|---|
| Entry | Next-session regular-hours order after signal close | close-entry vs stop-entry |
| Initial stop | Lower of breakout-day low or entry − 2× ATR(20), stop-market | 1.5/2/2.5/3 ATR; structural |
| Trailing exit | Close below prior 10-day low → exit next session; ratchet daily, **never loosen** | 5/10/20-day low; 20-day EMA; 3 ATR |
| Time stop | Exit after 20 sessions if trade has not reached +0.5R or a new 20-day high | 10/20/30 sessions; none |
| Re-entry cooldown | 10 sessions per symbol after close | — |

**Implemented interim model** (`domain/sizing.py`, backtest): stop = entry − 1 ATR(14), take-profit = entry + 2 ATR(14) bracket. This is the benchmark-era exit and is superseded by the trailing model for the Core system (roadmap change B).

**Open execution conflict — mitigations identified**: Alpaca server-side bracket orders carry a fixed take-profit leg, but Alpaca also offers native **server-side trailing-stop orders** (`trail_price`/`trail_percent`, high-water-mark based). Candidate resolutions: (a) native trailing stop as an always-on catastrophic layer plus EOD cancel/replace for the exact 10-day-low channel ratchet; (b) if the backtest grid shows the 3 ATR trailing variant performs comparably to the 10-day-low exit, use the native trailing stop alone — fully restoring the §3.7 uptime-independence property. The choice is made with roadmap change D data, before the Core model reaches paper execution (see `ROADMAP.md` §6).

Order rules (any exit model):

- `extended_hours` must be false/omitted.
- `time_in_force` must be `day` or `gtc` according to the final Alpaca adapter test.
- Take-profit and stop-loss prices must be rounded to Alpaca's valid increments before submission.
- `client_order_id` = signal event id for idempotency.
- Corporate actions are not ignored: bracket orders are DNR/DNC, so the position manager must reconcile splits/dividends and cancel/replace or halt when needed.
- Extreme volatility can cause rare OCO race conditions where both exit legs fill before cancellation. If detected, the executor/position manager must halt new entries and raise a critical alert until reconciled.

### 2.8 Risk rules (enforced in code, non-negotiable)

- Risk per trade: baseline **0.35%** of account equity for the Core model (test 0.20%–0.75%), sized from actual stop distance: qty = floor(equity × risk ÷ (entry − stop)). The implemented interim value is 1% and must come down with roadmap change C.
- **Volatility scaling**: risk per position falls when stock or portfolio volatility rises; never at maximum gross exposure immediately after severe market declines during violent rebounds — that is where momentum crashes live (report §3.5).
- Max concurrent positions: 5 implemented; Core model tests 6/10/15 with an aggregate open-risk cap (~4% of equity total initial risk) and sector-concentration caps.
- Max 25% of equity deployed.
- Stops do not guarantee the planned loss: overnight gaps, halts, and liquidity shocks produce larger losses. Position risk stays conservative enough to survive discontinuous moves.
- Daily kill-switch: account down 3% intraday → cancel all pending entries, no new orders until next session.
- Broker/account-rule guard: before any order, read Alpaca account state and reject if `trading_blocked`, account restrictions, buying-power checks, margin requirements, cash-account settlement, or house rules would be violated.
- Intraday-margin/PDT transition guard: do **not** hard-code the old “<$25k = max 3 day trades per 5 sessions” rule as the only control. FINRA's new intraday-margin framework became effective June 4, 2026, with broker phase-in through October 20, 2027. The adapter must support both legacy broker restrictions and new intraday-margin behavior during the transition.
- Swing-system guard: the strategy is designed for overnight holds; code must never intentionally same-day round-trip unless stop-loss, broker liquidation, or emergency risk controls force it.

### 2.9 Expectancy math

With trailing exits the win rate may sit **below 50%**; profitability must come from average win materially exceeding average loss (report §6.5). Judge expectancy (average R per trade) and payoff ratio — never optimize for hit rate, which hides tail losses (report §11).

Minimum gates:

- Positive expectancy after spread, slippage, regulatory fees, and tax sensitivity — in replay **and** across subperiods, not only in aggregate.
- The Core model must beat the benchmark spike/breakout control after costs; if it does not, the added layers are noise.
- Robustness: neighboring parameter values (e.g. 10 vs 20-day exits) must produce similar economic behavior; a result that lives in one grid cell is data mining.
- No single stock, sector, year, or regime may account for most profits.
- Paper results must roughly match replay/backtest assumptions before live keys exist in the cluster.
- Results must be reported both pre-tax and with a conservative short-term-tax sensitivity for the user's jurisdiction.

---

## 3. Architecture

### 3.1 Backbone decision: NATS JetStream

Kafka/Redpanda is ops overkill for this throughput on a local cluster. NATS JetStream provides streams with retention and replay, durable consumers, work-queue semantics, and at-least-once delivery in a single small StatefulSet. Every event is persisted → any trading day can be replayed against new filter logic. Replay is the backtesting substrate.

Operational note:

- Local paper can run a simple JetStream setup.
- Any live deployment must explicitly configure retention, backups, stream limits, and durability expectations. Do not assume “persisted” means lossless under every OS/storage failure.

### 3.2 System view

```
                         ┌──────────────────────────── k8s: ns trading ─┐
   Alpaca Market Data    │                                              │
   (IEX ws + REST) ──────┤► [ingestor] ──► md.bars.{symbol}             │
   Consolidated daily    │      ▲              │                        │
   / historical data ────┤──────┘              │                        │
                         │                     │                        │
   CronJob nightly ──────┤► [ref-data] ─► ref.universe / ref.calendar   │
                         │              (NATS KV + PG snapshots)        │
                         │                     │                        │
                         │              [scanner] ──► sig.spike         │
                         │                                │             │
                         │              [confirmator] ◄───┘             │
                         │              state machine per symbol        │
                         │                     │                        │
                         │                 sig.entry                    │
                         │                     │                        │
                         │                [risk-gate] ◄── account       │
                         │                     │          projection    │
                         │                orders.request                │
   Alpaca Trading API ◄──┤─── [executor] ◄─────┘                        │
   (bracket orders)  ────┤──► [executor] ──► orders.events              │
                         │        (fills/closes via trade-updates ws)   │
                         │                     │                        │
                         │   [position-mgr] ◄──┴──► [journal] ──► PG    │
                         │   time-stops,           append-only          │
                         │   cooldowns,            + read models        │
                         │   reconciliation                            │
                         │                     │                        │
                         │                [notifier] ──► Telegram       │
                         │                                              │
                         │  Postgres (StatefulSet) · NATS (StatefulSet) │
                         │  Prometheus/Grafana · k8s Secrets (API keys) │
                         └──────────────────────────────────────────────┘
```

### 3.3 Services

| Pod | Single responsibility | State |
|---|---|---|
| **ingestor** | Market-data adapter only. Normalizes intraday and daily bars → `md.bars.*`. Zero business logic | none |
| **ref-data** (CronJob) | Nightly universe build, point-in-time snapshots, earnings calendar, corporate actions → NATS KV + Postgres snapshots | Postgres snapshots |
| **scanner** | Indicators (ATR, MAs, 252-day momentum rank, 52-week high, rel-vol, 20d-high) + Core selection/trigger rules (§2.3–2.4), benchmark spike rules (§2.5) → `sig.spike` | rolling windows, rebuilt from stream/snapshots on boot |
| **confirmator** | Per-symbol state machine `CANDIDATE→WATCHING→CONFIRMED/REJECTED`; safety checks (earnings proximity, gap), market-regime filter, optional follow-through hypothesis (§2.6) → `sig.entry` | Postgres |
| **risk-gate** | **Single money authority.** Sizing, position/exposure caps, kill-switch, broker/account-rule guard → `orders.request` | account projection from `orders.events` |
| **executor** | Only pod holding trading keys. Places bracket orders; streams trade-updates → `orders.events`. Idempotent via `client_order_id` = signal event id | none (broker is source of truth) |
| **position-mgr** | Position lifecycle: time stops, cooldowns, corporate-action handling, EOD reconciliation vs broker | Postgres |
| **journal** | Consumes everything → append-only event table + read models (hit rate, expectancy, rejection reasons) | Postgres |
| **notifier** | Notable events → Telegram. Informational only, never actionable | none |

### 3.4 Symbol state machine (confirmator + position-mgr)

```
NONE → CANDIDATE (passes selection layers §2.3 + trigger §2.4, daily close)
     → WATCHING  (optional day +1/+2 follow-through, if the §2.6 hypothesis is enabled)
     → CONFIRMED (entry signal emitted)  |  REJECTED (reason logged)
     → ENTERED   (protective stop live at broker)
     → CLOSED    (trailing exit / stop / time-stop / broker action)
     → COOLDOWN  (10 sessions, no re-entry) → NONE
```

Without the follow-through hypothesis, `CANDIDATE → CONFIRMED` resolves at the same daily close and entry executes next session.

### 3.5 Event contracts

Monorepo shared `contracts/` package. Pydantic schemas, versioned (`SpikeDetected.v1`). Contract = the API between pods; a change is a new version, never a silent break.

```
md.bars.{symbol}      Bar{sym, o, h, l, c, v, ts, feed, adjusted, source}
ref.universe          UniverseSnapshot{as_of, symbols[], filters, source}
ref.calendar          EarningsWindow{sym, next_earnings_date, confidence, source}
ref.corp_actions      CorporateAction{sym, type, ex_date, ratio, source}
sig.spike             SpikeDetected{sym, rules_hit[], atr, rel_vol, ref_price, id}
sig.entry             EntryConfirmed{sym, entry_ref, stop, take_profit, spike_id}
sig.rejected          Rejected{sym, stage, reason, data_source, data_freshness}
orders.request        OrderRequest{sym, qty, bracket{tp, sl}, client_order_id}
orders.events         Filled | Closed | Canceled | Rejected {..., broker_payload}
risk.halt             RiskHalt{reason, scope, until, evidence}
```

Delivery is at-least-once → **every consumer idempotent** (dedupe on event id). Executor doubly protected: `client_order_id` makes duplicate submissions detectable by Alpaca/server-side order lookup.

### 3.6 Hexagonal layout — every service, same shape

```
service-x/
├── domain/          # PURE. No I/O, no SDK imports, no datetime.now()
│   ├── model.py     #   entities, value objects (Bar, Spike, Signal)
│   └── rules.py     #   detection/confirmation/risk logic — pure functions
├── ports/
│   ├── inbound.py   #   e.g. BarStream, ClockPort
│   └── outbound.py  #   e.g. SignalPublisher, StateRepository, BrokerPort
├── adapters/
│   ├── nats_in.py   #   JetStream consumer → drives inbound port
│   ├── nats_out.py  #   publisher implementation
│   ├── alpaca.py    #   BrokerPort implementation (executor only)
│   └── postgres.py  #   repository implementations
└── app/
    ├── usecases.py  #   orchestration: port-in → domain → port-out
    ├── wiring.py    #   DI composition root
    └── main.py      #   lifecycle, health endpoints, config from env
```

Hard rules:

- `domain/` imports nothing from `adapters/` or SDKs — enforced with import-linter in CI.
- Clock is a port → time-stop logic testable without waiting 15 days.
- Data providers are ports → vendor changes do not rewrite domain rules.
- Pure domain → same event always produces same decision → replay-safe.

### 3.7 Failure model

- Any pod dies → JetStream durable consumer resumes at last ack. No signal lost under the configured durability assumptions.
- **Executor dies mid-trade → protective stop already live server-side at Alpaca. Positions are usually protected without cluster uptime.** Most important property of the design. Note: under the Core model's trailing exits (§2.7) this property covers the **stop leg only** — there is no server-side take-profit leg, and the daily stop ratchet pauses if the cluster is down (stop protection persists at the last ratcheted level). If change D validates an ATR-style trail, Alpaca's native server-side trailing-stop order restores full uptime-independent protection (§2.7).
- Ingestor dies → no data → no signals → system fails SAFE (does nothing).
- Risk-gate is a deliberate chokepoint — exactly one place can authorize money movement; one audit point, one kill-switch.
- Paper vs live = same images, different k8s Secret + env. Promotion is configuration, not code.
- Bracket anomaly, duplicate fill, broker mismatch, or corporate-action uncertainty → publish `risk.halt`, cancel pending entries, alert, and require reconciliation before new orders.

### 3.8 Infrastructure

- NATS JetStream StatefulSet (streams + KV).
- Postgres StatefulSet (journal, state machines, point-in-time snapshots, read models).
- Prometheus + Grafana (signal counts, latencies, rejection rates, P&L, data freshness, broker mismatches).
- k8s Secrets for Alpaca keys (trading keys mounted ONLY into executor).
- k8s Secrets for data-provider keys (mounted only into adapters that need them).
- CronJobs: universe/calendar/corporate-action refresh, EOD reconciliation + summary.
- Kustomize overlays: `local-paper` / `local-live`.
- Scheduler awareness: market hours US/Eastern; scan cadence hourly 09:35–15:35 ET; daily decisions after official close data is available.

### 3.9 Supervision model — how every stock is watched, and at what frequency

Supervision is **tiered**: monitoring cost scales with how close a symbol is to real money. Not all symbols are watched equally.

| Tier | Population | What is supervised | Frequency |
|---|---|---|---|
| **0 — Universe** | ~8,000 US listings → ~600–800 survive | Liquidity screen, tradability, point-in-time index/universe snapshot, earnings/corporate-action refresh | Nightly CronJob |
| **1 — Scan** | All ~600–800 in universe | Bar ingestion; rolling indicators (ATR, 20/50/200-day MA, 252-day momentum rank, 52-week high, relative volume, 20-day high); Core selection + trigger rules and benchmark spike rules | Hourly awareness scans 09:35–15:35 ET + end-of-day authoritative daily-bar sweep |
| **2 — Watching** | ~5–20 candidates | Safety checks (earnings proximity, gap), regime filter, optional follow-through hypothesis | Same hourly awareness, but promotion/rejection at session close |
| **3 — Entered** | Max open positions per §2.8 | Protective stop-loss | **Not polled intraday** — stop order lives server-side at Alpaca, fires at broker/market-data resolution |
| | | Trailing-exit ratchet (10-day low, never loosened) | position-mgr at end of day: cancel/replace stop upward when the trailing level rises |
| | | Fill/close notifications | Real-time: Alpaca trade-updates websocket pushes to executor instantly |
| | | Time stop (§2.7), cooldown registry, broker/corporate-action reconciliation | position-mgr at end of day and on broker events |

**Data-flow cadence and load.** The ingestor may hold a single market-data websocket for intraday awareness and publish hourly bars per symbol to `md.bars.*`. Roughly 800 symbols × 7 bars/day ≈ 5–6k intraday events/day — trivial load, one pod. The authoritative daily sweep adds one daily bar per symbol and is the source for actual candidate promotion and confirmation decisions. The scanner consumes every bar, maintains rolling windows per symbol in memory (rebuilt from streams/snapshots on boot), and evaluates spike rules on bar close. All ~800 symbols are evaluated every hour for awareness; only daily close bars make trading decisions.

**Intraday awareness vs daily decision.** Breakout and spike rules are only meaningful on *session-close* data. Hourly scans provide early awareness (a symbol trending toward a trigger can be pre-staged), but `CANDIDATE` promotion is decided on the **daily close**, and confirmation is decided on the daily close of day +1/+2. Hourly = awareness; daily = decisions.

**Exit protection is broker-side by design.** Open positions should not depend on cluster uptime for ordinary TP/SL handling. TP/SL are attached to the bracket order at Alpaca and trigger through the broker. The cluster's position-time duties are the 15-session time stop, EOD reconciliation, corporate-action handling, and anomaly detection.

**Why not tick/minute streaming on everything.** Tick-level supervision of ~800 names means 10–100× the infrastructure for little edge: the strategy's horizon is days (swing), entries require day +1/+2 confirmation, and exits are already handled by the broker. Faster monitoring would only enable day-0 chasing — precisely what the confirmation layer exists to prevent. If the system later moves to intraday entries, only the ingestor subscription and scanner cadence change; the hexagonal seams keep every other service untouched.

---

## 4. Testing Strategy (strict TDD)

1. **Domain unit tests** — rule tables, property tests on state-machine transitions. Bulk of tests, zero infra.
2. **Contract tests** — each adapter against Pydantic schemas; testcontainers for NATS and Postgres.
3. **Data-quality tests** — adjusted bars, splits/dividends, missing earnings data, stale provider payloads, point-in-time universe snapshots.
4. **Replay/backtest tests** — recorded JetStream trading day and 2–3 years of point-in-time daily bars → full pipeline in kind → assert exact expected orders and metrics.
5. **Broker adapter tests** — Alpaca paper API for bracket order shape, price rounding, idempotent `client_order_id`, trade-updates handling, rejected-order paths.
6. **Paper soak** — 4–6 weeks on Alpaca paper only after replay/backtest acceptance criteria are pre-registered.

Strict TDD rule: implementation starts with failing tests for the domain rule or adapter behavior being added. Infra can be added with smoke tests, but trading logic must be red → green → refactor.

---

## 5. Delivery Phases (hard gates)

| Phase | Scope | Gate to next |
|---|---|---|
| **1. Signals only** | contracts → ref-data → ingestor → scanner → journal (+ notifier). Zero orders. | 2 weeks of logged signals; data freshness and rejection logging reviewed |
| **2. Replay/backtest** | Core 52-week-high momentum model **vs** benchmark spike/breakout control over 2–3 years of point-in-time daily bars; includes fees, slippage, tax sensitivity, survivorship-bias guard; change sequence in `ROADMAP.md` §5 | Positive expectancy after costs, robust across subperiods and neighboring parameters; Core beats benchmark or is dropped; drawdown and trade frequency acceptable; assumptions pre-registered for paper |
| **3. Paper loop** | confirmator → risk-gate → executor → position-mgr on Alpaca paper | 4–6 weeks; positive expectancy after spread/slippage; paper behavior roughly matches replay |
| **4. Live readiness rehearsal** | Live-like config without live trading: secrets isolation, kill-switch drill, reconciliation drill, broker-rule guard, alerting | No unresolved critical alerts; manual runbook tested |
| **5. Live small** | Live keys, minimum sizing, capped capital | Continuous: expectancy holds, kill-switch never breached, no unreconciled broker mismatches |

No positive replay and paper expectancy → no live. A system that skips phases 1–3 is a donation to the market.

---

## 6. Known Constraints & Honest Notes

- Alpaca free real-time stock data is IEX-only. It is acceptable for hourly awareness, but authoritative daily decisions should use consolidated/SIP or delayed consolidated historical bars when available.
- A paid SIP/consolidated-data plan or separate historical data provider may be required before serious validation.
- Earnings calendar, corporate actions, and catalyst/news are real data dependencies, not implementation details. Missing data must fail safe.
- Alpaca bracket orders materially improve safety, but they are not magic: extreme volatility can produce OCO race conditions, and bracket order prices are not automatically adjusted for corporate actions.
- FINRA's legacy PDT rule is being replaced by new intraday-margin standards effective June 4, 2026, with broker phase-in through October 20, 2027. The system must adapt to actual broker/account restrictions instead of assuming one static rule.
- Long-only, no options/leverage.
- EU tax: short-term gains are likely punitive compared with long-term investing — expectancy must be shown with tax sensitivity before live trading.
- A modular monolith with identical hexagonal internals would ship ~3× faster; the k8s decomposition buys independent restarts, replay infra, executor blast-radius isolation, and learning value. Chosen deliberately, eyes open: ~9 deployables + 2 StatefulSets.
- Build order if scope must shrink: `contracts → ref-data → ingestor → scanner → journal` first; everything else after filters prove out.

---

## 7. Acceptance Checklist Before Live

- [ ] Replay/backtest uses point-in-time universe and adjusted bars.
- [ ] Relative volume is computed from consolidated daily volume or explicitly marked as degraded-data mode.
- [ ] Earnings calendar provider is configured; missing data rejects or pauses signals.
- [ ] Corporate-action handling is tested against split/dividend fixtures.
- [ ] Alpaca bracket order adapter is tested in paper for rounding, idempotency, child-leg events, and rejection paths.
- [ ] Broker/account-rule guard reads live account restrictions instead of relying on static PDT assumptions.
- [ ] Kill-switch drill cancels pending entries and blocks new orders.
- [ ] Position reconciliation can detect duplicate fills, orphaned orders, and broker/state mismatches.
- [ ] Paper results match replay assumptions closely enough to justify live-small.
- [ ] Live keys have never been mounted into any pod except executor.
