# Proposal: Paper Trading Execution (Alpaca Bracket Orders)

## Intent

Turn accepted scan candidates into real bracket orders on Alpaca's **paper** account, proving order-execution mechanics (sizing, brackets, idempotency, kill-switch, caps) end to end. Paper-first stays absolute: no live-trading code path exists, not even feature-flagged.

## Named Decision: day-0 execution (INTERIM SIMPLIFICATION)

**User-resolved.** This slice executes on day-0 `candidate.accepted.v1`, knowingly bypassing SPEC §2.3–2.4's "never enter on day 0" confirmation stage. It is an explicitly-labeled interim simplification to validate execution mechanics safely on paper — NOT a SPEC-compliant entry strategy. A confirmation service is a designated future slice that will re-point execution at confirmed signals. The strategy-fidelity gap is documented loudly, never inherited silently.

## Scope

### In Scope
- `BrokerPort` (submit bracket order, get account, get open positions/orders) + raw-`httpx` `alpaca_broker` adapter; paper base URL **hardcoded**, zero live-URL code path.
- Pure domain sizing/risk module: 1% equity risk per trade; stop = entry − 1×ATR14; TP = entry + 2×ATR14; price-increment quantization; max 5 concurrent positions; max 25% equity deployed; stateless 3% intraday-drawdown kill-switch from `equity`/`last_equity`; broker-rule guard (`trading_blocked`, `account_blocked`, buying power).
- Deterministic `order.intent.v1` events (pure, content-hashed; `client_order_id` = intent event id) vs separate non-deterministic broker-ack family (`order.submitted.v1`, `order.rejected.v1`, dry-run skipped).
- Idempotency: GET order by `client_order_id` before POST; never blind-retry the mutating POST; bounded retry on idempotent GETs only.
- `invest-execute` CLI: dry-run DEFAULT (prints intents, zero broker mutation); explicit `--execute` opt-in; distinct `paper_execute` pytest marker for paper-mutating tests.
- Bracket at entry: `order_class=bracket`, stop-market SL leg, entry `time_in_force=day`, `extended_hours` never.

### Out of Scope
- Live trading, confirmation service, position management beyond the entry bracket (no time-stop/cooldown/fill polling).
- Corporate actions, OCO race halts, PDT logic, NATS/Postgres, intraday data, Kubernetes.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `trading-system`: add paper order-execution requirements — broker port, sizing/risk rules, intent/ack event split, idempotency, dry-run default, kill-switch, caps, paper-only safety rails.

## Approach

Hexagonal, mirroring the market-data slice: pure domain computes intents from `candidate.accepted.v1` + an account snapshot; adapter owns HTTP, retry, error taxonomy, and the single mutating POST. Broker is source of truth for caps/kill-switch reads (SPEC §3.7).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/invest/application/ports.py` | Modified | Add `BrokerPort`. |
| `src/invest/domain/` | New | Pure sizing/risk/quantization module. |
| `src/invest/contracts/events.py` | Modified | `order.intent.v1` + broker-ack family. |
| `src/invest/adapters/alpaca_broker.py` | New | httpx paper-only broker adapter. |
| `src/invest/adapters/cli.py` | Modified | `invest-execute`, dry-run default. |
| `pyproject.toml` | Modified | `paper_execute` marker; no new deps. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Day-0 execution contradicts SPEC edge model | Certain (accepted) | Named interim decision; confirmation slice designated next. |
| Accidental paper-state mutation | Low | Dry-run default, `--execute` opt-in, distinct marker. |
| Duplicate order submission | Low | Deterministic `client_order_id`; GET-before-POST; no POST retry. |
| `last_equity`/bracket-TIF semantics unverified | Medium | Verify in design + empirical adapter tests. |

## Rollback Plan

Remove broker adapter, port, sizing module, order contracts, CLI entrypoint, and marker; scan/fetch pipeline is fully restored. No persisted state beyond paper-account orders (cancelable via Alpaca dashboard).

## Dependencies

- Alpaca paper Trading API + paper-scoped key pair via existing env vars; `httpx` (already present).
- Archived `implementation-foundation` and `market-data-adapter` slices.

## Success Criteria

- [ ] Dry-run prints deterministic intents with zero broker calls.
- [ ] `--execute` submits idempotent bracket orders to the hardcoded paper URL only.
- [ ] Caps, kill-switch, and broker-rule guard block submission as pure predicates.
- [ ] Repeat runs never duplicate an order (`client_order_id` idempotency).
- [ ] Codebase contains no live-URL string or live code path.
