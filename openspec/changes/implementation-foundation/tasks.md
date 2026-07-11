# Tasks: Implementation Foundation

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 850-1,200 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 contracts -> PR 2 scanner -> PR 3 CLI/container |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Scaffold contracts and validated fixtures | PR 1 | `uv run pytest tests/contracts tests/adapters/test_fixtures_json.py` | `uv run python -m invest.adapters.cli --help` | Remove scaffold, contracts, fixture adapter/data |
| 2 | Deliver deterministic scanner | PR 2 | `uv run pytest tests/domain tests/test_boundaries.py` | `N/A: pure module tested directly` | Remove domain scanner/models and tests |
| 3 | Orchestrate, journal, expose CLI/container | PR 3 | `uv run pytest tests/application tests/adapters/test_cli.py` | `uv run invest-scan --universe fixtures/v1/universe.json --bars fixtures/v1/bars.json --format json` | Remove application, journal, CLI, Dockerfile |

## Phase 1: Contracts and Validated Inputs (PR 1)

- [x] 1.1 RED: Add `tests/contracts/test_events.py` proving missing `schema_version` fails and accepted/rejected/failed payloads preserve required versioned fields.
- [x] 1.2 GREEN: Create `pyproject.toml`, package skeleton, and `src/invest/contracts/events.py` with Pydantic v1 contracts; REFACTOR shared fields without reinterpretation.
- [x] 1.3 RED: Add `tests/adapters/test_fixtures_json.py` for valid loading plus `fixture-invalid`, duplicate-bar, non-monotonic-bars, fixture-symbol-missing, and fixture-version-mismatch failures before scanning.
- [x] 1.4 GREEN: Create `src/invest/domain/models.py`, `src/invest/domain/rejection.py`, `src/invest/application/ports.py`, `src/invest/adapters/fixtures_json.py`, and `fixtures/v1/*.json`; REFACTOR behind `FixtureReader`.

## Phase 2: Deterministic Scanner (PR 2)

- [x] 2.1 RED: Add `tests/domain/test_scanner.py` proving the momentum rule accepts a fixture candidate and produces identical ordered results twice.
- [x] 2.2 GREEN: Implement `src/invest/domain/scanner.py` with the 20-day volume/high/MA and ATR(14) rule; sort inputs and decisions deterministically.
- [x] 2.3 RED: Extend scanner tests for `insufficient-history`, `missing-data`, `unsupported-input`, `domain-invariant-violation`, and `no-signal`, each with its exact stable reason.
- [x] 2.4 GREEN: Emit one decision per valid symbol; REFACTOR calculations while preserving the scanner interface.
- [x] 2.5 RED then GREEN: Add `tests/test_boundaries.py` and remove any forbidden domain imports, I/O, network, randomness, SDK, or wall-clock calls.

## Phase 3: Journal, CLI, and Packaging (PR 3)

- [x] 3.1 RED then GREEN: Add `tests/adapters/test_journal_memory.py`; implement `src/invest/adapters/journal_memory.py` to store accepted/rejected events exactly once in deterministic order.
- [x] 3.2 RED then GREEN: Add `tests/application/test_scan_run.py`; implement `src/invest/application/scan_run.py` mapping decisions to deterministic IDs/contracts and journaling every rejection.
- [x] 3.3 RED: Add `tests/adapters/test_cli.py` proving success prints only the event list and malformed fixtures print exactly one `scan.failed.v1` record with non-zero exit and no partial output.
- [x] 3.4 GREEN: Implement `src/invest/adapters/cli.py` and `invest-scan` entrypoint; REFACTOR I/O to remain outside domain.
- [x] 3.5 RED then GREEN: Add container-scope test and `Dockerfile` exposing `invest-scan`; prove build metadata needs no cluster access and repository adds no Kubernetes/Helm/provisioning assets.
- [x] 3.6 Run `uv run pytest` and `uv run ruff check .`; document local/container commands while keeping Kubernetes infrastructure out of scope.
