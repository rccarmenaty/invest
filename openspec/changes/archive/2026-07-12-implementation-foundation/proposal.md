# Proposal: Implementation Foundation

## Intent

Create the first locally runnable, signals-only vertical slice so scanner behavior, event contracts, rejection reasons, and journaled outputs can be specified and tested before broker, replay, or infrastructure work.

## Scope

### In Scope
- Versioned Pydantic event contracts for accepted candidates, rejected candidates, and scanner/journal events.
- Pure momentum scanner rule over fixture daily bars, with explicit rejection reasons.
- Static, versioned universe and fixture bar inputs.
- In-memory journal and thin CLI that reads fixture bars and prints emitted events.
- Python 3.12+ project scaffold using uv, pytest, ruff, and hexagonal seams.
- Container packaging for services intended to run on user-owned Kubernetes later.

### Out of Scope
- Alpaca execution, broker access, NATS/Postgres wiring, replay engine, live trading, corporate-action providers.
- Kubernetes manifests, Helm charts, operators, provisioning, or cluster infrastructure.
- Dynamic universe construction, earnings/news ingestion, and order/risk execution loops.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `trading-system`: refine the first implementation slice for signals-only scanning, versioned events, fixture data, CLI output, and explicit rejection observability.

## Approach

Use hexagonal modules: pure domain scanner and event models behind small interfaces, with fixture/CLI/journal adapters outside domain code. Domain code must not import external SDKs, infrastructure, wall-clock calls, or adapters. Start strict TDD with contract and scanner tests.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `pyproject.toml` | New | Python toolchain and quality commands. |
| `src/` | New | Domain, contracts, CLI, and adapter scaffold. |
| `tests/` | New | Contract, scanner, CLI, and journal tests. |
| `fixtures/` | New | Versioned universe and daily bar examples. |
| `Dockerfile` | New | Container packaging only; no Kubernetes resources. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Overbuilding toward broker/infrastructure too early | Medium | Keep first slice fixture-only and signals-only. |
| Scanner ambiguity from incomplete market context | Medium | Emit explicit rejection reasons and defer unsafe dependencies. |
| Domain purity erosion | Low | Tests enforce no SDK/adapter/wall-clock imports in domain modules. |

## Rollback Plan

Remove the new scaffold, fixtures, tests, container file, and delta specs; no production data, broker state, or infrastructure is affected.

## Dependencies

- Python 3.12+, uv, pytest, ruff, Pydantic.
- Alpaca consolidated/SIP daily bars.

## Success Criteria

- [ ] A local CLI can read fixture bars and print accepted and rejected events.
- [ ] Tests prove event contract versioning, scanner decisions, rejection reasons, and in-memory journaling.
- [ ] Domain modules remain free of external adapters, SDKs, infrastructure, and wall-clock calls.
