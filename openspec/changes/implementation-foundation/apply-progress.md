# Apply Progress: Implementation Foundation

## Delivery Boundary

- Strategy: chained PRs, `stacked-to-main`
- Current work unit: PR 2 — deterministic scanner
- Start: PR 1 contracts and validated fixtures on `main`
- End: pure deterministic momentum scanner with stable rejection decisions and enforced domain boundaries
- Prior dependencies: PR 1 contracts and validated fixtures
- Follow-up: PR 3 journal, CLI, and container packaging
- Out of scope: journal, application orchestration, CLI, container, broker/infrastructure integrations, and Kubernetes assets

```text
main <- PR 1 contracts/fixtures <- PR 2 scanner 📍 <- PR 3 CLI/container
```

## Completed Tasks

- [x] 1.1 Contract tests written before contract implementation.
- [x] 1.2 Python scaffold and Pydantic contracts implemented and refactored around shared fields.
- [x] 1.3 Fixture adapter tests written before adapter implementation.
- [x] 1.4 Domain input models, stable rejection reasons, fixture-reader port, JSON adapter, and v1 fixtures implemented.
- [x] 2.1 Deterministic acceptance and ordering tests written before scanner implementation.
- [x] 2.2 Pure 20-day momentum rule and ATR(14) scanner implemented.
- [x] 2.3 Stable rejection tests added for all five assigned domain reasons.
- [x] 2.4 Scanner emits exactly one deterministically ordered decision per universe symbol; calculations refactored behind named constants and pure helpers.
- [x] 2.5 AST boundary test enforces forbidden imports, I/O, network, randomness, SDK, and wall-clock calls.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1–1.2 | `tests/contracts/test_events.py` | Unit | N/A (new) | Import failed: `invest` absent | 4 passed | accepted/rejected/failed variants plus missing version | Shared immutable `EventBase`; 4 passed |
| 1.3–1.4 | `tests/adapters/test_fixtures_json.py` | Integration | N/A (new) | Import failed: `invest.adapters` absent | 7 passed | valid, five stable failure reasons, malformed JSON | Validation kept behind `FixtureReader`; 7 passed |
| 2.1–2.2 | `tests/domain/test_scanner.py` | Unit | 22 passed | Import failed: `invest.domain.scanner` absent | 1 passed | Two accepted symbols, reversed inputs, repeat execution | Named rule constants and pure ATR helper; 6 passed |
| 2.3–2.4 | `tests/domain/test_scanner.py` | Unit | 1 scanner test passed | Four rejection assertions failed before validation branches | 6 passed | Five distinct stable rejection paths plus accepted path | One decision path per symbol; 6 passed |
| 2.5 | `tests/test_boundaries.py` | Architecture | 6 scanner tests passed | No forbidden dependency was present when the boundary guard was introduced | 1 passed | All domain modules traversed via AST | Helper functions isolate import and call-name analysis; 1 passed |

## Work Unit Evidence

| Evidence | Result |
|---|---|
| Focused tests | `uv run --extra dev pytest tests/contracts tests/adapters/test_fixtures_json.py` — exit 0, 11 passed |
| Runtime harness | `uv run python -c ...JsonFixtureReader().load(...)` — exit 0, printed `v1 2`; planned CLI harness belongs to PR 3 |
| Quality | `uv run --extra dev ruff check .` — exit 0, all checks passed |
| Rollback boundary | Remove `pyproject.toml`, `uv.lock`, `src/invest/{contracts,domain/models.py,domain/rejection.py,application/ports.py,adapters/fixtures_json.py}`, `fixtures/v1`, and PR 1 tests |
| PR 2 focused tests | `uv run --extra dev pytest tests/domain tests/test_boundaries.py -q` — exit 0, 7 passed |
| PR 2 runtime harness | `N/A` — the scanner is a pure domain module and is exercised directly through its public `MomentumScanner.scan` interface |
| PR 2 full suite | `uv run --extra dev pytest -q` — exit 0, 29 passed |
| PR 2 quality | `uv run --extra dev ruff check .` — exit 0, all checks passed |
| PR 2 rollback boundary | Remove `src/invest/domain/scanner.py`, `tests/domain/test_scanner.py`, `tests/test_boundaries.py`, and the `ScanDecision` addition in `src/invest/domain/models.py` |

## Deviations and Risks

- No design deviation. Pydantic 2.x is used to implement schema-version-v1 event contracts; "v1" identifies the event contract version rather than the Pydantic library major version.
- The planned `invest.adapters.cli --help` harness cannot exist within the PR 1 boundary; the fixture adapter was exercised directly instead.
- Engram persistence was unavailable to this executor, so the hybrid artifact is persisted on the OpenSpec side only and must be mirrored by the orchestrator.
- Task 2.5's boundary test passed on first execution because the new scanner was already free of forbidden dependencies; no production cleanup was required. This is recorded explicitly rather than claiming a fabricated RED failure.

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
