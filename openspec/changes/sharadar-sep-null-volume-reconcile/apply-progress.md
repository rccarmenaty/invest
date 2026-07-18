# Apply Progress: Reconcile Null SHARADAR/SEP Volume

## Status

- Mode: Strict TDD
- Tasks: 10/10 complete
- Delivery: Single PR work unit; no chain or size exception required
- Authored diff: `366` additions plus deletions, below the 400-line review budget

## Completed Work

- Added the public `fetch_range` BAYA 2024-12-31 null-volume regression before production edits.
- Added the smallest `_SepRow.volume` before-validator: exact `None` becomes `Decimal("0")`; every other value is unchanged.
- Added the missing public-seam guard proving `open=None` remains `malformed-response` with no partial bars.
- Kept `_rows_to_bars`, domain models, public interfaces, broad error masking, and unrelated behavior unchanged.

## Files Changed by Apply

| File | Action | Result |
|---|---|---|
| `tests/adapters/test_sharadar_market_data.py` | Modified | Two public-seam regression/guard tests. |
| `src/invest/adapters/sharadar_market_data.py` | Modified | Private exact-`None` volume reconciliation. |
| `openspec/changes/sharadar-sep-null-volume-reconcile/tasks.md` | Modified | All assigned tasks checked. |
| `openspec/changes/sharadar-sep-null-volume-reconcile/apply-progress.md` | Created | Cumulative implementation evidence. |

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1 | `tests/adapters/test_sharadar_market_data.py` | Provider integration | 34/34 pass | 1 expected failure | Pending at task boundary | Existing fractional/negative paths identified | N/A while RED |
| 1.2 | Same | Provider integration | 34/34 pass | `malformed-response`, exit 1 | Pending at task boundary | Existing guards retained | N/A while RED |
| 2.1 | Same | Provider integration | 34/34 pass | Confirmed before edit | 1/1 pass | Exact non-null paths unchanged | Minimal validator |
| 2.2 | Same | Provider integration | 34/34 pass | Confirmed before edit | 1/1 pass | Fractional and negative tests remain | No behavior refactor |
| 3.1 | Same | Provider integration | 34/34 pass | Primary RED retained | Guard 1/1 pass | Added `open=None` guard | Clean naming |
| 3.2 | Same | Provider integration | 34/34 pass | Primary RED retained | Focused pass | 36 adapter cases | No extra refactor |
| 3.3 | Same | Provider integration | 34/34 pass | Primary RED retained | 36/36 pass | All adapter paths | Final diff checked |
| 4.1 | Repository suite | Verification | N/A — evidence task | N/A | 573 pass, 4 skip | Full suite | N/A |
| 4.2 | `src`, `tests` | Static analysis | N/A — evidence task | N/A | Touched files pass | Full command exposed unrelated debt | N/A |
| 4.3 | SDD artifacts | Handoff | N/A — evidence task | N/A | Evidence recorded | Scope/budget checked | N/A |

## Command Evidence

| Stage | Command | Exact result | Output SHA-256 |
|---|---|---|---|
| Safety net | `SSL_CERT_FILE=/etc/ssl/cert.pem uv run pytest tests/adapters/test_sharadar_market_data.py` | exit 0; 34 passed | `29153123f83ba109388dde677f699e5bf273c712e8800374ff335b03df12ecdd` |
| RED | `SSL_CERT_FILE=/etc/ssl/cert.pem uv run pytest tests/adapters/test_sharadar_market_data.py -k null_volume` | exit 1; 1 failed with `malformed-response` | `07ae986402c4302bbedcc1a5d19493d8c86f6f2c27f08ef3bc2bb759d08940a3` |
| GREEN/refactor | Same focused command | exit 0; 1 passed, 35 deselected | `18b48f9f2c43c88e96088c0f9f2fc01a8d46f9555e67e585e31229a816f51aa3` |
| Guard | `... -k null_non_volume` | exit 0; 1 passed, 35 deselected | `18b48f9f2c43c88e96088c0f9f2fc01a8d46f9555e67e585e31229a816f51aa3` |
| Adapter | `SSL_CERT_FILE=/etc/ssl/cert.pem uv run pytest tests/adapters/test_sharadar_market_data.py` | exit 0; 36 passed | `6d92b3f461a8032f60968bdd17eb5bae7dd1ec3ecce8c2e729daf644133bacb0` |
| Full suite | `SSL_CERT_FILE=/etc/ssl/cert.pem uv run pytest` | exit 0; 573 passed, 4 skipped | `90e4f8514b82bc606c4734f482c3274ac8437f25df57ff315c7d9b7974b1eb1d` |
| Full lint | `uv run ruff check src tests` | exit 1; 17 pre-existing errors in unchanged CLI files | `b82221f50ffc7b2a816601107b57151aaeec5b401106082be8c514746fe7e516` |
| Touched lint | `uv run ruff check src/invest/adapters/sharadar_market_data.py tests/adapters/test_sharadar_market_data.py` | exit 0; all checks passed | `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` |

## Test Summary

- Total tests written: 2
- Total tests passing: 2 new tests within 36 passing adapter tests
- Layers used: provider integration (2)
- Approval tests: 1 fail-closed non-volume-null characterization guard
- Pure functions created: 0; reconciliation stays inside the private row model

## Work Unit Evidence

| Evidence | Result |
|---|---|
| Focused test | Null-volume public seam: exit 0, 1 passed after observed RED. |
| Runtime harness | N/A — deterministic `httpx.MockTransport` exercises the complete provider boundary without credentials or external network. |
| Rollback boundary | Revert the validator and its two regression/guard tests; prior null-volume fail-closed behavior returns without affecting other work. |

## Issues and Deviations

- No design deviation.
- Full lint remains red only in unchanged `src/invest/adapters/cli.py` and `src/invest/adapters/generate_context_cli.py`; fixing those 17 pre-existing findings is outside this change.
- The sandbox blocks the environment's bundled CA `.pem`; `/etc/ssl/cert.pem` was supplied for deterministic test execution. No repository configuration changed.
