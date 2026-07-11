# Momentum Breakout Trading System — Specification

**Status**: Proposed — revised for data, validation, and broker-rule safeguards
**Date**: 2026-07-11
**Broker**: Alpaca (paper first, live only after validation gates)
**Deployment target**: Local Kubernetes cluster
**Style**: Event-driven microservices, hexagonal architecture per service

---

## 0. Current Decision

Build a **paper-first swing-trading system** that detects confirmed momentum breakouts, sizes positions mechanically, submits protected bracket orders, and proves expectancy through replay/backtest plus paper trading before any live key is used.

The core architecture is accepted: **NATS JetStream + Postgres + small hexagonal services on local Kubernetes**. The hardening updates in this version are:

1. **Backtest/replay moves before paper execution** so obvious filter defects are found quickly.
2. **Authoritative decisions use consolidated daily data**, not IEX-only live volume.
3. **Broker/account-rule checks replace hard-coded PDT assumptions** because FINRA's intraday-margin framework is changing broker behavior during the 2026–2027 transition.
4. **Earnings, catalyst, corporate-action, and point-in-time universe data become explicit dependencies**.
5. **Bracket-order edge cases are handled explicitly** through reconciliation and safety halts.

---

## 1. Purpose

Detect early positive momentum (spikes) across a wide universe of liquid US stocks, verify the movement is real (not noise or a chase), enter swing trades automatically via bracket orders, and exit at a realistic take-profit, stop-loss, or time stop.

This is **not forecasting**. The system reacts to confirmed movement. Its edge comes from:

1. A verification layer that rejects day-0 chases and pump-and-dumps.
2. Mechanical exits (server-side bracket orders) that remove emotion.
3. A journal feedback loop that measures hit rate and expectancy so filters can be tuned on evidence.
4. Point-in-time replay/backtesting that prevents survivorship-biased confidence.

## 2. Trading Strategy

### 2.1 Universe

**Live universe**:

- S&P 500 + Nasdaq 100 constituents (~600–800 liquid names after dedupe).
- Filters: average daily dollar volume > $10M, price > $5, tradable flag from Alpaca asset API.
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
| Backtest/replay | Point-in-time adjusted historical bars + point-in-time universe/corporate actions | Validation before paper/live |

Important rule: **relative volume and breakout decisions must not rely on IEX-only volume unless running an explicit degraded-data experiment**. IEX volume can diverge materially from full-market volume, so using it as the authoritative signal source can create false positives/negatives.

### 2.3 Spike detection (day 0 — cheap filters, run on everything)

A symbol becomes a `CANDIDATE` when all hold on the authoritative daily close:

| Rule | Threshold |
|---|---|
| Relative volume | today ≥ 2× 20-day average consolidated volume |
| Price move | ≥ 1.5× ATR(14) upward |
| Breakout | close above 20-day high |
| Not extended | price < 15% above 20-day MA (else too late) |

Hourly scans may pre-stage symbols that are trending toward a trigger, but **CANDIDATE promotion is a daily-close decision only**.

### 2.4 Confirmation (day +1 / +2 — the actual edge)

`CANDIDATE → CONFIRMED` only if all hold:

- Follow-through: price holds above the breakout level for the next 1–2 sessions. Never enter on day 0.
- Trend filter: price > 50-day MA and 50-day MA > 200-day MA (trade with the tide only).
- No earnings within the next 5 calendar days (binary event = coin flip, reject).
- No overnight gap > 8% (chase, reject).
- Catalyst presence (earnings beat, guidance raise, material news) strengthens the signal; absence is a soft flag recorded in the journal.

Data requirements:

- Earnings calendar comes from a configured `CorporateCalendarPort` provider before Phase 2 starts.
- Missing earnings data is fail-safe: reject or hold in `WATCHING`; never treat missing data as safe.
- Catalyst/news provider is optional for Phase 1, required before live trading if catalyst is used as a scored feature.
- Every rejection logs `stage`, `reason`, `data_source`, and `data_freshness`.

`CANDIDATE` that fails confirmation → `REJECTED`, with reason logged. Rejections are journal gold — they tune the filters.

### 2.5 Trade management (mechanical)

| Parameter | Value |
|---|---|
| Entry | On confirmation, regular-hours bracket order |
| Stop-loss | entry − 1× ATR(14) (~5–8%); stop-market by default to prioritize exit |
| Take-profit | entry + 2× ATR(14) (2:1 reward/risk, ~8–15%) |
| Time stop | No TP after 15 sessions → close at market during regular hours |
| Re-entry cooldown | 10 sessions per symbol after close |

Bracket-order rules:

- `extended_hours` must be false/omitted.
- `time_in_force` must be `day` or `gtc` according to the final Alpaca adapter test.
- Take-profit and stop-loss prices must be rounded to Alpaca's valid increments before submission.
- `client_order_id` = signal event id for idempotency.
- Corporate actions are not ignored: bracket orders are DNR/DNC, so the position manager must reconcile splits/dividends and cancel/replace or halt when needed.
- Extreme volatility can cause rare OCO race conditions where both exit legs fill before cancellation. If detected, the executor/position manager must halt new entries and raise a critical alert until reconciled.

### 2.6 Risk rules (enforced in code, non-negotiable)

- Risk per trade: 1% of account equity. Position size = equity × 0.01 / stop-distance-fraction.
- Max 5 concurrent positions.
- Max 25% of equity deployed.
- Daily kill-switch: account down 3% intraday → cancel all pending entries, no new orders until next session.
- Broker/account-rule guard: before any order, read Alpaca account state and reject if `trading_blocked`, account restrictions, buying-power checks, margin requirements, cash-account settlement, or house rules would be violated.
- Intraday-margin/PDT transition guard: do **not** hard-code the old “<$25k = max 3 day trades per 5 sessions” rule as the only control. FINRA's new intraday-margin framework became effective June 4, 2026, with broker phase-in through October 20, 2027. The adapter must support both legacy broker restrictions and new intraday-margin behavior during the transition.
- Swing-system guard: the strategy is designed for overnight holds; code must never intentionally same-day round-trip unless stop-loss, broker liquidation, or emergency risk controls force it.

### 2.7 Expectancy math

Target: ~40–45% hit rate × 2:1 payoff = positive expectancy after spread, slippage, regulatory fees, borrow/margin costs if applicable, and tax sensitivity.

Minimum gates:

- Below 35% hit rate in replay or paper → filters are broken, do not go live.
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
| **scanner** | Indicators (ATR, MAs, rel-vol, 20d-high) + spike rules → `sig.spike` | rolling windows, rebuilt from stream/snapshots on boot |
| **confirmator** | Per-symbol state machine `CANDIDATE→WATCHING→CONFIRMED/REJECTED`; follow-through, trend, earnings-proximity checks → `sig.entry` | Postgres |
| **risk-gate** | **Single money authority.** Sizing, position/exposure caps, kill-switch, broker/account-rule guard → `orders.request` | account projection from `orders.events` |
| **executor** | Only pod holding trading keys. Places bracket orders; streams trade-updates → `orders.events`. Idempotent via `client_order_id` = signal event id | none (broker is source of truth) |
| **position-mgr** | Position lifecycle: time stops, cooldowns, corporate-action handling, EOD reconciliation vs broker | Postgres |
| **journal** | Consumes everything → append-only event table + read models (hit rate, expectancy, rejection reasons) | Postgres |
| **notifier** | Notable events → Telegram. Informational only, never actionable | none |

### 3.4 Symbol state machine (confirmator + position-mgr)

```
NONE → CANDIDATE (spike day 0)
     → WATCHING  (awaiting day +1/+2 follow-through)
     → CONFIRMED (entry signal emitted)  |  REJECTED (reason logged)
     → ENTERED   (bracket live at broker)
     → CLOSED    (TP / SL / time-stop / broker action)
     → COOLDOWN  (10 sessions, no re-entry) → NONE
```

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
- **Executor dies mid-trade → bracket TP/SL already live server-side at Alpaca. Positions are usually protected without cluster uptime.** Most important property of the design.
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
| **1 — Scan** | All ~600–800 in universe | Bar ingestion; rolling indicators (ATR-14, 20/50/200-day MA, relative volume, 20-day high); spike rules | Hourly awareness scans 09:35–15:35 ET + end-of-day authoritative daily-bar sweep |
| **2 — Watching** | ~5–20 spiked candidates | Follow-through: does price hold the breakout level? Trend + earnings-proximity checks | Same hourly awareness, but promotion/rejection at session close of day +1/+2 |
| **3 — Entered** | Max 5 open positions | Take-profit / stop-loss | **Not polled by the cluster at all** — bracket order lives server-side at Alpaca, fires at broker/market-data resolution |
| | | Fill/close notifications | Real-time: Alpaca trade-updates websocket pushes to executor instantly |
| | | Time stop (15 sessions), cooldown registry, broker/corporate-action reconciliation | position-mgr at end of day and on broker events |

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
| **2. Replay/backtest** | Same signal and confirmation logic over 2–3 years of point-in-time daily bars; includes fees, slippage, tax sensitivity, survivorship-bias guard | Positive expectancy; hit rate ≥ ~40%; drawdown and trade frequency acceptable; assumptions pre-registered for paper |
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
