# Archive Report: paper-trading-execution

## Scope

Execute day-0 accepted scan candidates as bracket orders against Alpaca's paper-trading API. Explicitly interim: SPEC.md defines a two-stage day-0 candidate / day+1-+2 confirmed entry model ("never enter on day 0"); this slice executes directly on `candidate.accepted.v1` as a named, documented simplification to prove order-execution mechanics safely on paper. Confirmation service is a designated future slice.

Paper only — the base URL is hardcoded to `paper-api.alpaca.markets` with zero live-trading code path, not even feature-flagged. Dry-run is the CLI default; `--execute` is explicit opt-in.

## Delivery

Four chained PRs plus one correction:

| PR | Scope | Writer |
|---|---|---|
| #11 | Pure domain: ATR extraction, sizing math (1% risk, ATR-based bracket, tick quantization), pre-trade gates, `GateReason` contract | Claude Sonnet 5 |
| #12 | Event contracts (deterministic `order.intent.v1` vs non-deterministic ack family), `BrokerPort`, `ExecuteRun` dry-run/halt orchestration | Codex gpt-5.6-sol |
| #13 | `AlpacaBroker` adapter: idempotent bracket submission, GET-only retry, credential redaction | Codex gpt-5.6-sol (orchestrator aligned `BrokerPort`/`BrokerAck` signatures to the settled design after a contract-drift catch) |
| #14 | `invest-execute` CLI, dry-run default, `paper_execute` marker | Claude Sonnet 5 |
| #15 | Correction: 4R review findings | Codex gpt-5.6-sol |

Mid-session decision: Codex retired as implementation executor going forward; all future SDD apply work uses Claude Agent subagents only.

## Review

Two lineages:

- **paper-trading-execution** (full 4R over the merged implementation): 15 findings — `PRES-001` BLOCKER (mid-run infra failure vaporized the journal, already-submitted orders vanished from output), `PRES-002`/`PREL-001`/`PREL-002` CRITICAL (ambiguous POST timeout indistinguishable from clean failure; caps projection counted rejected orders as open; kill-switch silently disabled at `last_equity <= 0`), plus 11 info rows. All four severe findings corrected via PR #15, along with three folded-in adjacents (ack-id formula, buying-power depletion, zero-ATR characterization test).
- **paper-trading-execution-clean** (terminal lineage over the corrected tree): 7 info rows (5 resolved-in-PR-#15 records, 2 open follow-ups), receipt **approved**.

## Verify

PASS — 8/8 requirements, 22/22 scenarios, 131 tests passed (3 expected credential-gated skips), ruff clean. Harness confirmed: `invest-execute` without credentials emits a single `{"reason": "auth-failure"}` record, exit 2; `invest-scan` regression unaffected. Paper-only rail confirmed — no non-paper Alpaca URL anywhere in `src/`.

## Open Follow-ups (non-blocking)

- **`client_order_id` includes `rule_version`** — dedup is per-rule-version, not per-symbol/day; a `RULE_VERSION` bump could re-submit an already-executed day. Explicit decision required before any live-trading slice (Engram topic `trading-system/order-idempotency-scope`).
- Duplicated `EventBase`/`ExecutionEventBase` definitions in `contracts/events.py`.
- Three divergent CLI failure-output shapes across `main`/`fetch_main`/`execute_main` in `cli.py`.
- `BrokerFetchError` uses free-form reason strings instead of a `StrEnum`, unlike the domain's `GateReason`/`RejectionReason` convention.
- Minor: parameter naming, duplicated parser boilerplate, repeated skip-event construction sites, `fetch_main`'s use of a module-private Pydantic model.

## Known Gap Identified During This Cycle

The system has no backtest/replay validation. SPEC.md mandates replay/backtest expectancy proof *before* paper execution ("a system that skips phases 1-3 is a donation to the market"); this was built out of order. Scoped as the next SDD change: `backtest-replay`.
