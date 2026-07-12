# Design: Paper Trading Execution (Alpaca Bracket Orders)

## Technical Approach

Mirror the market-data slice hexagonally. A new pure `sizing` domain module turns each accepted `ScanDecision` + an `AccountSnapshot` + bar history into an `OrderIntent` (qty, entry, stop, take-profit) and evaluates halt/skip gates as pure predicates. A new `ExecuteRun` application service (mirroring `ScanRun`) reads the broker snapshot, runs halt gates once, **rescans from the fixture snapshot** to regenerate accepted decisions (single source of truth), sizes each, journals a deterministic `order.intent.v1`, and — only under `--execute` — performs GET-by-`client_order_id`-then-POST bracket submission. `alpaca_broker` (raw `httpx`) owns HTTP, the fetch error taxonomy, bounded retry on GETs only, and the single mutating POST against a **hardcoded paper URL**. Dry-run is the default and never POSTs.

## Architecture Decisions

### Decision: ATR sourced by extracting the scanner's ATR into a shared pure helper
**Choice**: Move `MomentumScanner._average_true_range` (scanner.py:60-66, byte-mechanical, scanner-regression test first) to `domain/indicators.py::average_true_range`; scanner and `sizing` both import it. The helper receives the 20-bar `history` window and slices to `ATR_DAYS` internally (no misleading `14` suffix). `sizing` recomputes ATR from the same `history = bars[-(HISTORY_DAYS+1):-1]` window; entry ref = last bar close.
**Alternatives**: (a) extend `ScanDecision`/events to carry ATR — touches scanner, `ScanDecision`, event scheme; (b) duplicate the ATR algorithm in `sizing` — drift risk.
**Rationale**: Rescan-from-snapshot means bars are already in hand; a shared function keeps ONE ATR implementation with zero behavior change and no event-schema churn. Minimal disruption.

### Decision: `ExecuteRun` rescans from the fixture snapshot (not journaled accepted events)
**Choice**: Feed `ExecuteRun` the same `FixtureInputs` as `invest-scan`; regenerate accepted decisions via `MomentumScanner`.
**Rationale**: One deterministic source of truth (bars) for both scan and execute; avoids parsing/trusting prior event JSON and keeps intents reproducible.

### Decision: Two event families — deterministic intent vs content-addressed ack
**Choice**: `order.intent.v1` extends the deterministic `EventBase`. The ack family (`order.submitted.v1`, `order.rejected.v1`, `execution.skipped.v1`, `execution.halted.v1`) uses a separate `ExecutionEventBase`. `Journal.append` widens to `pydantic.BaseModel` (superclass of both).
**Rationale**: Broker acks are external/non-reproducible; keeping them out of the deterministic hash scheme mirrors SPEC §3.5 `orders.request` vs `orders.events`.

### Decision: Halt continues fail-closed (never aborts); caps/qty skip per symbol
**Choice**: `kill-switch` and `broker-account-restricted` are evaluated once from the snapshot BEFORE any sizing. On halt the run emits ONE `execution.halted.v1` carrying the halt reason, then still iterates every remaining accepted candidate emitting a per-candidate `execution.skipped.v1` carrying that SAME halt reason, submits nothing, and completes normally (exit 0, full event list). Cap/qty failures skip only that candidate and continue.
**Rationale**: Fail-closed with a complete, auditable per-candidate record beats an early abort that hides which candidates were suppressed; matches the settled spec.

## Data Flow

    invest-execute --universe --bars [--snapshot DIR] [--execute]
        │  JsonFixtureReader → FixtureInputs (bars)
        ▼
    AlpacaBroker.snapshot()  ── GET /v2/account + /v2/positions ──▶ AccountSnapshot
        │
        ▼
    ExecuteRun: halt gates(snapshot) ──halt──▶ execution.halted.v1 (halt reason)
        │                                        then per remaining candidate:
        │                                        execution.skipped.v1 (same halt reason),
        │                                        no POST, run completes (exit 0)
        │  (no halt) MomentumScanner.scan(bars) → accepted decisions
        │  per candidate: sizing.compute_intent → skip gates (running projection)
        │     skip ──▶ execution.skipped.v1        pass ──▶ order.intent.v1 (deterministic)
        ▼  (only if --execute)
    GET /v2/orders:by_client_order_id ──exists──▶ execution.skipped.v1 (reason=already-submitted, no POST)
        │  else POST /v2/orders (bracket, no retry)
        ▼  201 → order.submitted.v1   |   422 → order.rejected.v1

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/invest/application/ports.py` | Modify | Add `BrokerPort` Protocol; widen `Journal.append` to `BaseModel`. |
| `src/invest/domain/models.py` | Modify | Add `AccountSnapshot`, `OrderIntent` frozen dataclasses (Decimal fields). |
| `src/invest/domain/indicators.py` | Create | Shared pure `average_true_range`. |
| `src/invest/domain/sizing.py` | Create | `compute_intent`, `quantize_price`, `GateReason`, `evaluate_gates`. |
| `src/invest/domain/scanner.py` | Modify | Import shared ATR (mechanical, no behavior change). |
| `src/invest/application/execute_run.py` | Create | `ExecuteRun` orchestration + event id hashing. |
| `src/invest/contracts/events.py` | Modify | `OrderIntentEvent` + `ExecutionEventBase` ack family. |
| `src/invest/adapters/alpaca_broker.py` | Create | httpx broker adapter, hardcoded paper URL, GET retry, POST once. |
| `src/invest/adapters/cli.py` | Modify | `execute_main` (`invest-execute`), dry-run default. |
| `pyproject.toml` | Modify | `invest-execute` script + `paper_execute` marker. |

## Interfaces / Contracts

```python
# ports.py
@runtime_checkable
class BrokerPort(Protocol):
    def snapshot(self) -> AccountSnapshot: ...
    def find_order(self, client_order_id: str) -> str | None: ...      # broker order id or None
    def submit_bracket(self, intent: OrderIntent, client_order_id: str) -> BrokerAck: ...

# models.py
@dataclass(frozen=True)
class AccountSnapshot:
    equity: Decimal; last_equity: Decimal; buying_power: Decimal
    open_position_count: int; deployed_value: Decimal
    trading_blocked: bool; account_blocked: bool

@dataclass(frozen=True)
class OrderIntent:
    symbol: str; decision_date: date; qty: int
    entry: Decimal; stop: Decimal; take_profit: Decimal
```

**Sizing** (pure, Decimal): `risk_capital = equity*0.01`; `atr = average_true_range(history)`; `entry = quantize(last_close)`; `stop = quantize(entry-atr)`; `take_profit = quantize(entry+2*atr)`; `qty = floor(risk_capital / (entry-stop))`. `quantize(p)`: tick `0.01` if `p>=1` else `0.0001`, `ROUND_HALF_EVEN` (deterministic; sub-penny-safe). `ExecuteRun` seeds a running `(count, deployed)` projection from the snapshot and increments it on each submission so intra-run caps hold.

**Gate order** — halt (once, continues fail-closed): `kill-switch` (`(equity-last_equity)/last_equity <= -0.03`) → `broker-account-restricted` (`trading_blocked or account_blocked`). Per candidate: `max-concurrent-positions` (`count >= 5`) → `sizing-invalid` (`qty == 0`) → `max-equity-deployed` (`deployed + qty*entry >= 0.25*equity`) → `insufficient-buying-power` (`qty*entry > buying_power`). First failure wins. Idempotency outcome `already-submitted` is emitted when the pre-POST GET finds an existing order (own outcome record, never folded into `order.submitted.v1`). Full reason set (kebab-case `GateReason` StrEnum): `kill-switch`, `broker-account-restricted`, `max-concurrent-positions`, `sizing-invalid`, `max-equity-deployed`, `insufficient-buying-power`, `already-submitted`. A contract test MUST assert this enum equals the spec reason set exactly (no additions, no omissions).

**`OrderIntentEvent(EventBase)`** (deterministic; `EventBase` is `frozen`, `extra="forbid"` — carries `schema_version`, `event_type`, `event_id`, `symbol`, `decision_date`, `fixture_version`, `rule_version`, `decision`). The intent event sets `event_type="order.intent.v1"`, `decision="intent"`, and ADDS `qty: int`, `entry_price: str`, `stop_price: str`, `take_profit_price: str`, `client_order_id: str`. Prices are Decimal-serialized as the exact quantized strings sent to the broker (`str(quantized)`), so intent id ↔ submitted `limit_price`/`stop_price` stay byte-identical.

**Contracts** — `order.intent.v1.event_id = sha256("|".join(("1","order.intent.v1", fixture_version, rule_version, symbol, decision_date.isoformat(), str(qty), str(stop), str(take_profit))))`; `client_order_id = event_id` (64 chars ≤ 128 limit). Ack family ids are content-addressed, no wall-clock: submitted `sha256(intent_id|broker_order_id)`; rejected `sha256(intent_id|reason|broker_order_id)`; skipped `sha256(intent_id_or_symbol|reason)`; already-submitted `sha256(intent_id|already-submitted|broker_order_id)`; halted `sha256("execution.halted.v1"|fixture_version|reason)`. All `schema_version="1"`.

**Bracket POST body** (`https://paper-api.alpaca.markets/v2/orders`): `{symbol, qty, side:"buy", type:"market", time_in_force:"day", order_class:"bracket", client_order_id, take_profit:{limit_price}, stop_loss:{stop_price}}` — **verified** against Alpaca docs: `order_class="bracket"` with `take_profit.limit_price` and `stop_loss.stop_price` mandatory and `stop_loss.limit_price` optional (omitted → stop-market SL leg); `extended_hours` never sent. Auth headers/env identical to market-data adapter; secrets never logged; errors `raise ... from None`.

**Broker error taxonomy** — GETs (bounded retry, `MAX_ATTEMPTS=3`, backoff `0.5→4s`, honor `Retry-After`): 401/403 `auth-failure` (no retry); 429 `rate-limited`; 5xx/timeout `network-failure`; bad JSON `malformed-response`. POST (**no retry**): 201 → ack; **422 → `order.rejected.v1`** (business outcome, run completes); 401/403 `auth-failure`, 429 `rate-limited`, 5xx `network-failure` → raise (infrastructure failure). Exit mapping is the single authoritative table below.

**CLI** — `invest-execute --universe --bars [--snapshot DIR] --format json [--execute]`; `execute_main` mirrors `fetch_main`. Dry-run is the default (prints the intent list, read-only account/position GETs, zero POST); `--execute` opts into submission.

**Exit codes (authoritative — supersedes every other exit mention in this doc):**

| Exit | Meaning | Includes | Output |
|---|---|---|---|
| 0 | Run completed | all-skipped, halted (+ per-candidate skips), `already-submitted`, and broker `422 → order.rejected.v1` business outcomes | full event list printed |
| 2 | Infrastructure failure | `auth-failure`, `network-failure`, `rate-limited`, `malformed-response`, `fixture-invalid` (input files) | exactly one machine-readable `{"reason": ...}` record |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit (domain) | Sizing math + **boundary values** (qty floor, qty==0, tick <$1/≥$1, kill-switch exactly −3%, cap exactly at 5/25%) | Pure Decimal, no I/O |
| Unit (domain) | Each `GateReason`; halt-vs-skip; running projection caps 2nd candidate | Pure predicates |
| Unit (adapter) | Bracket JSON exact shape, GET-before-POST, no-POST-retry, GET retry/backoff, error→reason map, secret redaction | `httpx.MockTransport` |
| Unit (contracts) | Deterministic intent id reproducible; ack id content-addressed | Fixed inputs |
| Unit (CLI) | Dry-run prints intents + zero POST; `--execute` order; exit 0/2 contract | MockTransport broker |
| Boundary | New `alpaca_broker` covered by existing `invest.adapters` ban; domain stays pure | Existing AST test (no change) |
| Smoke | Real paper submit + cancel | `@pytest.mark.paper_execute`, skipped unless creds set |

Strict TDD sequence (RED first):

| Step | First failing behavior |
|---|---|
| 1 | `average_true_range` extracted; scanner still green. |
| 2 | `compute_intent` sizing + quantization from snapshot+bars. |
| 3 | Boundary values: floor, `sizing-invalid`, tick thresholds. |
| 4 | `evaluate_gates` halt + each skip reason, in order. |
| 5 | Running projection blocks the 2nd candidate at caps. |
| 6 | `BrokerPort` shape; `AlpacaBroker.snapshot()` maps account+positions. |
| 7 | Bracket POST JSON shape; GET-before-POST; POST not retried. |
| 8 | GET retry/backoff + error taxonomy; redaction. |
| 9 | Deterministic `order.intent.v1` id; content-addressed ack ids. |
| 10 | Halt continues: emits `execution.halted.v1` + per-candidate `execution.skipped.v1` (same reason), zero POST; `already-submitted` on GET-hit. |
| 11 | `GateReason` enum equals the spec reason set exactly (contract test). |
| 12 | `execute_main`: dry-run zero-POST, `--execute` submits, exit codes per authoritative table. |
| 13 | `paper_execute` marker registered; env-gated smoke. |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. This adds an outbound HTTPS client whose only mutation is `POST /v2/orders`. Mutation-safety rails: hardcoded paper URL (no live branch), dry-run default, `--execute` opt-in, deterministic `client_order_id` + GET-before-POST idempotency, no POST retry, distinct `paper_execute` marker, env-only redacted secrets.

## Migration / Rollout

No data migration. Rollback removes the broker adapter, `BrokerPort`, `sizing`/`indicators`, order contracts, `ExecuteRun`, `invest-execute`, and the marker; the ATR extraction is behavior-preserving, so scan/fetch is fully restored.

## Decisions and Tradeoffs

| Decision | Rejected alternative | Rationale |
|---|---|---|
| **Day-0 interim execution** on `candidate.accepted.v1` | Wait for confirmation service | Named, loud interim simplification to prove paper mechanics; bypasses SPEC §2.3–2.4 "never enter on day 0"; confirmation is the next slice. |
| Hardcoded paper URL | Configurable base URL | Strongest safety rail — no live code path exists. |
| ATR via shared extracted helper | Extend `ScanDecision` / duplicate | One implementation, no event-schema churn. |
| Ack id = hash(intent id + broker order id) | UUID / wall-clock | Content-addressed, replay-stable, no clock. |
| `time_in_force=day`, market entry, stop-market SL | GTC / limit entry | Matches SPEC broker-side exit protection; exit-leg persistence confirmed by adapter test. |
| `httpx.MockTransport` | `respx` | No new dependency; deterministic. |
| GET retry only, POST never retried | Retry POST | Avoids duplicate submission; idempotency via GET-before-POST. |

## Verified Facts (formerly open)

- **`account.last_equity` EXISTS** — Alpaca account object field, "Equity as of previous trading day at 16:00:00 ET"; feeds the stateless `kill-switch` gate directly.
- **Bracket JSON confirmed** — `order_class="bracket"`, `take_profit.limit_price` and `stop_loss.stop_price` mandatory, `stop_loss.limit_price` optional (omitted → stop-market SL leg).
- The MockTransport bracket-shape test and env-gated `paper_execute` smoke remain the regression guard, but neither field is an unresolved risk.

## Open Questions

None.
