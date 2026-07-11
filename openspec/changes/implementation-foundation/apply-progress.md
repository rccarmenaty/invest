# Apply Progress: Implementation Foundation

## Delivery Boundary

- Strategy: chained PRs, `stacked-to-main`
- Current work unit: PR 1 — contracts and validated fixtures
- Start: specification-only repository
- End: installable Python scaffold with versioned contracts and validated static JSON fixtures
- Prior dependencies: none
- Follow-up: PR 2 deterministic scanner; PR 3 journal, CLI, and container packaging
- Out of scope: scanner logic, journal, CLI, container, broker/infrastructure integrations, and Kubernetes assets

```text
main <- PR 1 contracts/fixtures 📍 <- PR 2 scanner <- PR 3 CLI/container
```

## Completed Tasks

- [x] 1.1 Contract tests written before contract implementation.
- [x] 1.2 Python scaffold and Pydantic contracts implemented and refactored around shared fields.
- [x] 1.3 Fixture adapter tests written before adapter implementation.
- [x] 1.4 Domain input models, stable rejection reasons, fixture-reader port, JSON adapter, and v1 fixtures implemented.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1–1.2 | `tests/contracts/test_events.py` | Unit | N/A (new) | Import failed: `invest` absent | 4 passed | accepted/rejected/failed variants plus missing version | Shared immutable `EventBase`; 4 passed |
| 1.3–1.4 | `tests/adapters/test_fixtures_json.py` | Integration | N/A (new) | Import failed: `invest.adapters` absent | 7 passed | valid, five stable failure reasons, malformed JSON | Validation kept behind `FixtureReader`; 7 passed |

## Work Unit Evidence

| Evidence | Result |
|---|---|
| Focused tests | `uv run --extra dev pytest tests/contracts tests/adapters/test_fixtures_json.py` — exit 0, 11 passed |
| Runtime harness | `uv run python -c ...JsonFixtureReader().load(...)` — exit 0, printed `v1 2`; planned CLI harness belongs to PR 3 |
| Quality | `uv run --extra dev ruff check .` — exit 0, all checks passed |
| Rollback boundary | Remove `pyproject.toml`, `uv.lock`, `src/invest/{contracts,domain/models.py,domain/rejection.py,application/ports.py,adapters/fixtures_json.py}`, `fixtures/v1`, and PR 1 tests |

## Deviations and Risks

- No design deviation. Pydantic 2.x is used to implement schema-version-v1 event contracts; "v1" identifies the event contract version rather than the Pydantic library major version.
- The planned `invest.adapters.cli --help` harness cannot exist within the PR 1 boundary; the fixture adapter was exercised directly instead.
- Engram persistence was unavailable to this executor, so the hybrid artifact is persisted on the OpenSpec side only and must be mirrored by the orchestrator.

## Frozen Review Correction

Correction scope was limited to the four corroborated PR 1 findings. No PR 2/PR 3 work or informational findings were addressed.

| Frozen ID | Regression and correction | RED | GREEN |
|---|---|---|---|
| `RESILIENCE-001` | Invalid UTF-8 is translated to stable `fixture-invalid`. | `UnicodeDecodeError` escaped the fixture boundary; 1 failed, 7 passed. | Focused regression passed after including decoding failures in adapter translation. |
| `RISK-001` | Empty symbols, non-positive OHLC values, negative volume, and impossible OHLC relationships are rejected as `fixture-invalid`. | 9 parameter cases failed. | 9 parameter cases passed with constrained payload fields and an OHLC relationship validator. |
| `RELIABILITY-001` | Duplicate `(symbol, date)` rows now use the delta-spec classification `fixture-invalid`. | Expected `fixture-invalid`, received `duplicate-bar`; 1 failed, 4 passed. | Duplicate classification suite passed; 5 passed. |
| `RELIABILITY-002` | Every universe symbol must have at least one bar, otherwise `fixture-symbol-missing`. | Missing-bar regression did not raise. | Focused regression passed after bidirectional symbol coverage validation. |

### Correction Verification

- Focused suite: `uv run --extra dev pytest tests/contracts tests/adapters/test_fixtures_json.py -q` — exit 0, 22 passed.
- Quality: `uv run --extra dev ruff check .` — exit 0, all checks passed.
- Rollback boundary: revert only the correction delta in `src/invest/adapters/fixtures_json.py`, `tests/adapters/test_fixtures_json.py`, and this correction section; the original PR 1 implementation remains intact.
