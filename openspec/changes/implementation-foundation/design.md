# Design: Implementation Foundation

## Technical Approach

Create a local, signals-only Python 3.12 vertical slice around one deep application module: `ScanRun`. It loads versioned static fixtures through adapters, validates them before domain evaluation, runs a pure deterministic scanner, journals accepted/rejected decisions in memory, and prints machine-readable events. The repository is currently specification-only, so implementation will add the first `uv` Python scaffold.

## Module Layout and Dependency Direction

```
src/invest/
  domain/              # dataclasses/enums, scanner rule, no I/O/time/random/SDKs
    models.py          # Symbol, DailyBar, Universe, ScanDecision
    rejection.py       # stable RejectionReason enum
    scanner.py         # MomentumScanner.scan(universe, bars) -> list[ScanDecision]
  contracts/
    events.py          # Pydantic v1 event payloads and validation errors
  application/
    ports.py           # FixtureReader, Journal, EventSink protocols
    scan_run.py        # orchestration; maps decisions to contracts
  adapters/
    fixtures_json.py   # static fixture loader/validator
    journal_memory.py  # deterministic in-memory journal
    cli.py             # thin non-interactive CLI
fixtures/v1/
tests/
Dockerfile
pyproject.toml
```

Dependencies point inward: `adapters -> application -> domain`; `application -> contracts`; `domain` imports only stdlib/project domain modules.

## Event and Rejection Contracts

All emitted records are Pydantic contracts with `schema_version`, `event_type`, deterministic `event_id`, `symbol`, `decision_date`, `fixture_version`, `rule_version`, and `decision`.

| Event | Purpose |
|---|---|
| `candidate.accepted.v1` | Scanner rule accepted a symbol/date. |
| `candidate.rejected.v1` | Scanner evaluated a valid symbol and rejected it. |
| `scan.failed.v1` | Pre-scan validation or CLI failure; no partial scan output. |

Stable `RejectionReason`: `fixture-invalid`, `fixture-version-mismatch`, `fixture-symbol-missing`, `duplicate-bar`, `non-monotonic-bars`, `insufficient-history`, `missing-data`, `unsupported-input`, `no-signal`, `domain-invariant-violation`. Fixture-level failures stop before domain decisions; symbol-level rule failures become rejected candidate events.

## Data Flow, Ordering, and Error Semantics

```
CLI args -> fixture adapter -> validated in-memory inputs
        -> ScanRun -> MomentumScanner -> in-memory Journal -> JSON output
```

Fixture validation rejects invalid schema, duplicate `(symbol,date)`, non-monotonic dates, unknown symbols, and fixture-version mismatches before scanning. Scanner inputs are sorted by `(symbol, date)`; outputs are sorted by `(decision_date, symbol, event_type, reason)`. Event IDs are deterministic hashes of version, fixture version, rule version, symbol, date, decision, and reason. No wall-clock timestamps are emitted in this slice.

CLI failures exit non-zero and print exactly one `scan.failed.v1` JSON record with a stable reason. Successful runs exit `0` and print the journaled event list only.

## Scanner Rule

`MomentumScanner` starts with the day-0 spike rule from the seed spec over fixture daily bars: relative volume >= `2x` 20-day average, upward move >= `1.5x` ATR(14), close above prior 20-day high, and close < `115%` of 20-day moving average. Missing history or prerequisites reject deterministically. Confirmation, earnings, risk, and orders remain out of scope.

## CLI and Container Entrypoints

`invest-scan --universe fixtures/v1/universe.json --bars fixtures/v1/bars.json --format json` is the supported local entrypoint. `Dockerfile` packages the same console script with `uv`; the container default command runs `invest-scan`. No Kubernetes manifests, Helm charts, operators, or provisioning files are created.

## Testing Strategy and TDD Sequence

Use strict vertical RED -> GREEN -> REFACTOR cycles:

| Step | First failing behavior |
|---|---|
| 1 | Contract validation rejects missing `schema_version`. |
| 2 | Fixture loader rejects duplicate rows and version mismatch. |
| 3 | Scanner accepts one deterministic fixture candidate twice identically. |
| 4 | Scanner rejects `insufficient-history` and `no-signal`. |
| 5 | In-memory journal stores each event exactly once in order. |
| 6 | CLI prints success JSON and failure JSON with correct exit codes. |
| 7 | Boundary test fails on forbidden imports/calls under `src/invest/domain`. |
| 8 | Container metadata exposes the CLI entrypoint without Kubernetes assets. |

Boundary tests parse domain imports and ban adapters, SDKs, filesystem/network modules, randomness, and wall-clock calls such as `datetime.now()`/`date.today()`.

## Migration, Rollback, and Non-Goals

No data migration is required. Rollback deletes the new scaffold, fixtures, tests, and Dockerfile. Explicit non-goals: Alpaca access, broker execution, NATS/Postgres, replay engine, live trading, external data providers, confirmation service, Kubernetes infrastructure, and money-moving safety-halt implementation. Deterministic event IDs preserve future replay/idempotency compatibility without adding infrastructure now.

## Decisions and Tradeoffs

| Decision | Rejected alternative | Rationale |
|---|---|---|
| Domain dataclasses plus edge Pydantic contracts | Pydantic everywhere | Keeps scanner pure while preserving machine-validated contracts. |
| One `ScanRun` application module | Many shallow services | Maximizes locality for the first slice. |
| Static JSON fixtures | Provider adapters now | Prevents infrastructure creep and makes tests deterministic. |
| In-memory journal port adapter | Postgres/NATS journal | Proves event semantics before persistence. |
| Deterministic hashes for event IDs | UUID/time-based IDs | Enables reproducible scans and future idempotency. |
| Duplicate `(symbol,date)` rows classified as `duplicate-bar` | Generic `fixture-invalid` | Rejection taxonomy requires the exact failure class; `fixture-invalid` is reserved for schema/parse/value failures. |
| Universe symbol without bars fails the whole run (`fixture-symbol-missing`) | Per-symbol rejection | Versioned static fixtures must be complete; an incomplete fixture is an authoring error, not a market condition. Revisit when the universe becomes dynamic. |
| Scanner rejects every symbol with `unsupported-input` when bars contain non-universe symbols | Silently dropping alien bars | Defense in depth behind the loader (which already blocks this); silent drops would violate rejection observability. Revisit if the scanner gains a second caller. |
| Any zero-volume bar in the window rejects the symbol as `missing-data` | Treating zero volume as a valid halted session | Fixture-slice data-quality rule; halted-session semantics deferred until real market data arrives. |

## Open Questions

None.
