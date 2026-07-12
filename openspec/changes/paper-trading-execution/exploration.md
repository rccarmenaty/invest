# Exploration: paper-trading-execution

Execute accepted scan candidates as bracket orders against Alpaca's paper-trading API. Paper only, dry-run-first, no NATS/Postgres, no confirmation service, no live-trading path whatsoever.

## Current State

Two archived changes exist. `implementation-foundation` gives a pure `MomentumScanner` (day-0 spike rules only — rel-vol >= 2x, move >= 1.5x ATR14, breakout above 20d high, not > 15% extended) driving `ScanRun` -> `MemoryJournal` -> deterministic content-hashed events (`candidate.accepted.v1` / `candidate.rejected.v1` / `scan.failed.v1`), exposed via `invest-scan` CLI. `market-data-adapter` adds `MarketDataReader` port + raw-`httpx` `AlpacaMarketDataReader` (bounded retry: 3 attempts, backoff 0.5s -> cap 4s, honors `Retry-After`) + `SnapshotWriter` (atomic temp-dir-then-rename write, provenance with sha256 + degraded-feed flag), `invest-fetch` CLI, env-only creds `ALPACA_API_KEY_ID`/`ALPACA_API_SECRET_KEY`.

No order/broker port exists yet. `src/invest/application/ports.py` only has `FixtureReader`, `MarketDataReader`, `Journal`. `src/invest/contracts/events.py` only has scan events — no order contracts. `tests/test_boundaries.py` forbids `alpaca`, `httpx`, `invest.adapters`, `invest.application`, wall-clock calls, and `random` inside `src/invest/domain/*.py` via AST walk — any new `invest.adapters.alpaca_broker` module is automatically covered by the existing `invest.adapters` root ban, no boundary-test changes needed structurally. Event IDs are `sha256("|".join(("1", fixture_version, rule_version, symbol, decision_date.isoformat(), decision, reason)))` — fully deterministic and reproducible from inputs alone.

**Critical scope/strategy mismatch to surface**: SPEC.md §2.3–2.4 defines a two-stage pipeline — day-0 `CANDIDATE` (spike, cheap filters) then day+1/+2 `CONFIRMED` (follow-through, trend filter, no earnings within 5 days, no >8% gap) — and explicitly states "Never enter on day 0." The current `MomentumScanner`'s `candidate.accepted.v1` output is exactly the day-0 `CANDIDATE` stage, **not** the SPEC's confirmed entry signal. Executing directly on `candidate.accepted.v1` as-is is a deliberate simplification that contradicts SPEC's stated anti-chase edge model. This must be a loud, explicit, written decision in the proposal — not something quietly inherited. See Recommendation.

## SPEC.md mapping — this slice vs later

| SPEC section | Belongs here? | Notes |
|---|---|---|
| §2.5 entry via bracket order | IN | mechanical, matches broker-side exit-protection philosophy (§3.9) |
| §2.5 stop-loss = entry − 1×ATR14, take-profit = entry + 2×ATR14 | IN | pure Decimal domain math, testable without I/O |
| §2.5 time stop (15 sessions), re-entry cooldown (10 sessions) | OUT | requires day-by-day polling + persisted position state; bracket TP/SL is broker-side and self-contained without this |
| §2.6 risk per trade 1% equity, sizing formula | IN | pure domain function; equity value is an external input |
| §2.6 max 5 concurrent positions, max 25% equity deployed | IN | requires reading open positions/orders from broker (`GET /v2/positions`, `GET /v2/orders?status=open`) — broker is source of truth (SPEC §3.7) |
| §2.6 daily kill-switch (3% intraday drawdown) | IN, simplified | stateless `(equity - last_equity)/last_equity <= -3%` from `GET /v2/account`; verify `last_equity` field during design |
| §2.6 broker/account-rule guard (`trading_blocked`, `account_blocked`, buying power) | IN | `GET /v2/account` fields |
| §2.6 intraday-margin/PDT transition guard | OUT | note as config surface/future work only |
| §2.4 confirmation state machine (follow-through, trend, earnings, gap) | OUT (per scope) | see Critical mismatch above — must be an explicit written decision |
| §2.5 corporate-action reconciliation, OCO race-condition halt | OUT | needs ongoing polling/position-mgr; future risk, not built now |
| §3.1–3.9 NATS/Postgres/K8s architecture | OUT | continue the single-process in-memory CLI slice pattern |

## Affected Areas

- `src/invest/application/ports.py` — new `BrokerPort` (submit bracket order, get account, get open positions)
- `src/invest/domain/` — new pure sizing/risk module (position size from equity/ATR/stop-distance; concurrent-position and exposure caps as pure predicates; price-increment rounding as pure Decimal quantization)
- `src/invest/contracts/events.py` — new versioned contracts: deterministic `order.intent.v1` (derived from `candidate.accepted.v1` + sizing) and broker-acknowledgement events (`order.submitted.v1` / `order.rejected.v1` / dry-run equivalent) as a **separate** non-deterministic event family
- `src/invest/adapters/alpaca_broker.py` (new) — `BrokerPort` implementation: `POST /v2/orders` (bracket), `GET /v2/account`, `GET /v2/positions`, `GET /v2/orders?status=open`, idempotency via GET by `client_order_id` before POST
- `src/invest/adapters/cli.py` — new `invest-execute` entrypoint with dry-run default and explicit `--execute` opt-in
- `pyproject.toml` — no new dependency (reuses `httpx`); distinct pytest marker (e.g. `paper_execute`) separate from the read-only `live` marker
- `tests/test_boundaries.py` — no structural change required

## Alpaca paper trading API research

- Paper base URL: `https://paper-api.alpaca.markets/v2/orders`. Given "no live path whatsoever", the strongest safety rail is to **hardcode** the paper base URL with no live-URL config branch at all.
- Paper API keys are a distinct key pair scoped to paper mode; same env var **names** reused, values must be the paper-scoped pair.
- `POST /v2/orders` bracket shape: `order_class="bracket"`, `take_profit={"limit_price": ...}`, `stop_loss={"stop_price": ...}` (omitting stop_loss.limit_price yields stop-market SL, matching SPEC). `time_in_force`: recommend `day` for the entry leg; exit-leg persistence verified empirically in adapter tests. `extended_hours` stays false. `client_order_id` <= 128 chars — our deterministic 64-char sha256 event_id fits directly.
- Idempotency: duplicate-submission semantics not explicitly documented — safe pattern is **always GET by client_order_id before POST**; if found, treat as already-submitted. Never blind-retry the mutating POST; bounded retry only on the idempotent GET.
- Order status lifecycle: `new/accepted -> filled/partially_filled/canceled/rejected/expired/...`. This slice ends at initial submission acknowledgment; fill tracking is position-mgr territory, out of scope.
- Rate limits: per-minute RPM, 429 on excess. Reuse the market-data bounded-retry pattern for GETs only.
- Price rounding: > $1 rounds to whole cents; < $1 up to 4 decimals; sub-penny violations rejected. Pure Decimal quantization in the domain sizing module.
- `GET /v2/account`: `buying_power`, `cash`, `equity`, `last_equity`, `pattern_day_trader`, `trading_blocked`, `account_blocked` — feeds the pre-trade guard and stateless kill-switch.

## Determinism / replay strategy

Order **intents** (symbol, qty, entry/stop/TP prices, client_order_id) remain pure, deterministic domain decisions computed from `candidate.accepted.v1` + an account snapshot (equity, open-position count/value) — replay-safe, zero I/O. Broker **acknowledgements** are external, non-reproducible events journaled in a separate event family, never merged into the deterministic-hash scheme. Mirrors SPEC §3.5's `orders.request` vs `orders.events` split, scaled to the in-memory/CLI shape.

**Dry-run as default safety posture**: the execution CLI computes and prints order intents without calling the broker by default; explicit `--execute` opts into the real (paper) POST.

## Safety rails for this slice

- Paper base URL **hardcoded**; no live-URL config path introduced at all.
- No live-trading code path whatsoever — not even feature-flagged.
- Dry-run default; `--execute` explicit opt-in.
- Max 5 concurrent positions / 25% equity deployed / broker-rule guard enforced as pre-submission domain predicates fed by a broker read.
- Kill-switch check reads account state fresh each run; stateless approximation.
- `client_order_id` = deterministic event_id; GET-before-POST idempotency.
- Distinct pytest marker (`paper_execute`) — order submission mutates broker state even in paper mode.

## Testing without network

Reuse the `httpx.MockTransport` pattern from `tests/adapters/test_alpaca_market_data.py` for the broker adapter unit tests (bracket shape, price rounding, GET-before-POST, error taxonomy). Env-gated real-paper smoke test with the distinct marker.

## Approaches

1. **Bracket order at entry (single POST, order_class=bracket)** — matches SPEC's broker-side exit protection; zero polling for TP/SL; one call per entry. Entry-leg TIF interaction needs empirical verification. Effort: Medium. **Recommended.**
2. **Separate stop management** — reintroduces cluster-uptime dependency SPEC designed against; more surface, no upside. Effort: High. Rejected.
3. **Dry-run default vs execute default** — dry-run default recommended: a paper account is still real infrastructure state that shouldn't change on every run by accident.
4. **Execute on day-0 `candidate.accepted.v1` vs defer until confirmation exists** — proceeding on the accepted event keeps the excluded-confirmation-service boundary but knowingly bypasses SPEC's "never enter on day 0" rule. **Recommend proceeding as an explicitly-labeled interim simplification** (slice proves order-execution mechanics safely on paper, not yet a SPEC-compliant confirmed-entry strategy), carried loudly into sdd-propose.

## Recommendation

Build `BrokerPort` + `alpaca_broker` adapter (raw httpx, mirroring the market-data adapter's retry/error-taxonomy style) submitting bracket orders to the hardcoded paper base URL, driven by a new pure domain sizing/risk module computing qty, stop, take-profit, and price rounding from `candidate.accepted.v1` + an account-state snapshot. Intents pure/deterministic; broker acks journaled as a separate event family. Dry-run default; `--execute` opt-in. `client_order_id` = deterministic event_id with GET-before-POST idempotency. No NATS/Postgres/confirmation/live-path/position-management-beyond-entry-bracket.

## Risks

- **Day-0 execution vs SPEC "never enter on day 0"** — must be an explicit, named decision in the proposal.
- `last_equity` field not re-confirmed against current Alpaca docs this session — verify during design.
- Entry-leg `time_in_force` interaction with bracket exit-leg persistence needs empirical adapter-test verification.
- Broker reads for concurrency/exposure caps introduce the first live-dependent adapter calls — same mock discipline as market data.
- Paper-mode order submission is the codebase's first mutating adapter call — dry-run-first, GET-before-POST, distinct marker are load-bearing.
- Corporate-action handling, OCO race halts, time-stop/cooldown remain unbuilt — executor stops at bracket submission acknowledgment.

## Ready for Proposal

Yes, with one required carry-forward: sdd-propose must explicitly resolve the day-0-vs-confirmed execution decision (Approach 4) as a named decision.
