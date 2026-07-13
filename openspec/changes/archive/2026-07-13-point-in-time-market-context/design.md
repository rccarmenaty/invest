# Design: Point-in-Time Market Context

## Technical Approach

Add a deep, clock-free `MarketContext` domain module. A strict Pydantic JSON adapter constructs it; eligibility, blockers, complete date/symbol coverage, and invariants remain behind its small interface. Before replay, `BacktestRun` validates every replay-date/universe-symbol pair, where replay dates are the sorted distinct input-bar dates. Each date then processes unsafe open positions before ordinary exits or entries, filters the `Universe` passed to the unchanged `MomentumScanner`, and records context outcomes separately from `GateReason`. Provider adapters and earnings-vendor selection remain deferred.

## Architecture Decisions

| Option | Tradeoff | Decision |
|---|---|---|
| Immutable `MarketContext` with `status()` and `require_complete()` | Adds domain code but localizes all PIT semantics | Chosen; file/Pydantic concerns remain in the adapter. |
| Complete replay-date × symbol matrix | Curated files must be explicit | Chosen; missing, malformed, unsupported, or contradictory pairs fail before replay. No static fallback exists. |
| Force close on first unsafe replay date | Requires same-day price certainty | Chosen; before any ordinary exit or entry, an unsafe long closes at that day’s `bar.low`, the least favorable admissible OHLC price. Existing cost formulas consume that raw exit unchanged. |
| Defer when an unsafe position lacks its same-day bar | Could hide risk across missing bars | Rejected; abort immediately as `market-context-incomplete`, return no result, emit no partial report, and never inspect a later bar. |
| Extend context into execution/provider paths | Risks weakening paper-first isolation | Rejected; context remains backtest-only. `--execute`, paper endpoint, readiness expectations, and zero-live-default behavior stay unchanged. |

## Data Flow

    context JSON -> BacktestContextJsonReader -> MarketContext
    universe + replay dates -----------------> require_complete
                                                     |
    date D -> unsafe positions -> D bar present? -> forced close at bar.low
                              \-> absent -> fail closed; no later-date deferral
           -> ordinary exits/accounting -> filtered Universe -> MomentumScanner
           -> candidate context check -> enter | context-entry-blocked
    BacktestResult -> unchanged metrics/costs + context outcomes -> CLI JSON

An unsafe close emits `context-position-forced-closed` before any D entry. Context reasons never enter portfolio gate counts.

## File Changes

| File | Action | Description |
|---|---|---|
| `src/invest/domain/market_context.py` | Create | Context model, exact outcome/reason taxonomy, coverage queries. |
| `src/invest/adapters/backtest_context_json.py` | Create | Strict versioned decoder and stable errors. |
| `src/invest/application/backtest_run.py` | Modify | Validate coverage; filter scans; order forced closes before exits/entries; fail on missing required D bar. |
| `src/invest/domain/models.py` | Modify | Add context outcomes to `BacktestResult`. |
| `src/invest/adapters/cli.py` | Modify | Require `--market-context`; emit one failure or one PIT report. |
| `fixtures/backtest/market-context.json` | Create | Fully covered deterministic fixture. |
| `tests/domain/test_market_context.py` | Create | Matrix, intervals, exact values, future-mutation tests. |
| `tests/adapters/test_backtest_context_json.py` | Create | Schema and semantic failures. |
| `tests/application/test_backtest_run.py` | Modify | Ordering, forced-close, parity, accounting, and cost tests. |
| `tests/adapters/test_cli_backtest.py` | Modify | Required context, labels, Alpaca-bars-only, zero-broker tests. |
| `tests/test_boundaries.py` | Modify | Backtest isolation and paper/live endpoint guards. |
| `tests/application/test_execute_run.py`, `tests/adapters/test_cli_execute.py`, `tests/adapters/test_alpaca_broker.py` | Modify | Prove `--execute`, paper-only broker, and live-safety gates are unchanged. |

No production changes are permitted in `MomentumScanner`, Alpaca market data, portfolio/accounting, cost, broker, or execution modules.

## Interfaces / Contracts

```python
class ContextOutcomeType(StrEnum):
    ENTRY_BLOCKED = "context-entry-blocked"
    POSITION_FORCED_CLOSED = "context-position-forced-closed"

class ContextReason(StrEnum):
    SYMBOL_INELIGIBLE = "symbol-ineligible"
    CORPORATE_ACTION = "corporate-action"
    EARNINGS_CONTEXT_MISSING = "earnings-context-missing"
```

JSON v1 contains `schema_version`, explicit coverage, eligibility intervals, and blocker intervals. All interval endpoints are inclusive. Every outcome includes type, reason, symbol, and date. CLI context failures remain one exit-2 JSON record: `market-context-missing`, `market-context-invalid`, or `market-context-incomplete`.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Domain/adapter | Complete matrix, inclusive windows, exact outcome values, strict JSON | RED table and malformed-file tests. |
| Application | First-unsafe-date close precedes exits/entries; `bar.low`; absent D bar aborts without deferral; deterministic replay | Recording scanner and crafted multi-symbol bars. |
| Regression | Scanner outputs, Alpaca bars, accounting, costs, ordinary exits | All-eligible/unblocked parity against current results. |
| CLI/boundary | One-record failures, PIT labels, zero broker calls, unchanged `--execute`, paper URL, and no live URL/readiness bypass | CLI spies, AST guards, broker/execute suites, existing paper smoke. |

Strict TDD requires these RED tests before implementation; full `pytest` is the integration gate.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout

No state migration. Preflight remains `auto/hybrid/auto-forecast/800`. Rollback restores static-universe reporting. Live provider/context adapters and earnings-vendor selection remain deferred.

## Open Questions

None.

Next Recommended Phase: sdd-tasks
