```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:44f1c46e017aa2b3874f9db9afabf1fa23feaff8dc0319578ab5936ce6678b58
verdict: pass
blockers: 0
critical_findings: 0
requirements: 2/2
scenarios: 9/9
test_command: SSL_CERT_FILE=/etc/ssl/cert.pem uv run pytest
test_exit_code: 0
test_output_hash: sha256:457d3e03423116768a21aa80c6f690d4addd880e791da303e599bd3571506006
build_command: uv run ruff check src/invest/adapters/sharadar_market_data.py tests/adapters/test_sharadar_market_data.py
build_exit_code: 0
build_output_hash: sha256:5b196eb3a6acb50d3fa398d04ca284985cc1ffec870e940264b00780bfd2c971
```

## Verification Report

**Change**: `sharadar-sep-null-volume-reconcile`  
**Version**: N/A  
**Artifact store**: Hybrid (OpenSpec + Engram)  
**Mode**: Strict TDD  
**Terminal verdict**: **PASS**  
**Finding counts**: **0 CRITICAL, 0 WARNING, 1 SUGGESTION**

Independent re-verification after the absent-volume remediation. All 6 normative scenarios for the modified requirement now have public-seam runtime coverage; focused, adapter, and full-suite evidence is green; design coherence holds.

### Completeness

| Metric | Value |
|---|---:|
| Requirements total | 1 |
| Requirements fully compliant | 1 |
| Requirements partial | 0 |
| Scenarios total | 6 |
| Scenarios compliant | 6 |
| Scenarios untested | 0 |
| Task checkboxes declared complete | 10/10 |
| Tasks independently substantiated | 10/10 |
| Tasks effectively incomplete | 0 |

Task `3.1` is now substantiated: the suite covers integer/fractional exactness, negative rejection, absent volume column, short rows, ordering, adjustment, pagination, chunking, coverage, and the `open=None` non-volume null guard.

### Command Evidence

All hashes are SHA-256 over exact combined stdout/stderr captured from the listed command.

| Purpose | Exact command | Exit | Exact result | Output hash |
|---|---|---:|---|---|
| Volume-scenario focus | `SSL_CERT_FILE=/etc/ssl/cert.pem uv run pytest tests/adapters/test_sharadar_market_data.py -k 'absent_volume or null_volume or null_non_volume or negative_volume or shorter_than'` | 0 | 5 passed, 32 deselected | `sha256:d7ffd05d3a582387fb9ade645a183128ecf9100ae2fa87b398b728d59ad99dd5` |
| Adapter suite | `SSL_CERT_FILE=/etc/ssl/cert.pem uv run pytest tests/adapters/test_sharadar_market_data.py` | 0 | 37 passed | `sha256:6941d2f1d485bbfb56bfda2f8b9922ebe756805bb066a375d83bcf1090b93223` |
| Full suite | `SSL_CERT_FILE=/etc/ssl/cert.pem uv run pytest` | 0 | 577 passed, 1 skipped | `sha256:457d3e03423116768a21aa80c6f690d4addd880e791da303e599bd3571506006` |
| Touched-file Ruff | `uv run ruff check src/invest/adapters/sharadar_market_data.py tests/adapters/test_sharadar_market_data.py` | 0 | All checks passed | `sha256:5b196eb3a6acb50d3fa398d04ca284985cc1ffec870e940264b00780bfd2c971` |
| Repository Ruff baseline | `uv run ruff check src tests` | 1 | 17 errors, all in unchanged CLI files | `sha256:a9e81f0936d4b1a13c04c845aa7fb7ae61d1282de5dcc888f86418d18a6c601b` |
| Snapshot identity | `(git rev-parse HEAD; git rev-parse origin/main; git hash-object src/invest/adapters/sharadar_market_data.py; git hash-object tests/adapters/test_sharadar_market_data.py)` | 0 | Four identities in order | `sha256:bb6ad04a1f980abfaf5b88baf3d22134c7bbc4451b1c4f49549bbc6171275420` |

`evidence_revision` is the SHA-256 of the ordered concatenation of full-suite, touched Ruff, snapshot, adapter, and focused command outputs.

The repository-wide Ruff failure is unchanged non-change evidence in `src/invest/adapters/cli.py` and `src/invest/adapters/generate_context_cli.py`. Touched implementation and test files pass Ruff.

### Spec Compliance Matrix

| Requirement | Scenario | Covering runtime evidence | Result |
|---|---|---|---|
| Fractional SEP volume preservation | Reconcile a volume-only null as a retained zero-volume bar | `tests/adapters/test_sharadar_market_data.py::test_fetch_range_reconciles_null_volume_as_a_retained_zero_volume_bar` — retained BAYA bar with `volume == Decimal("0")` in focused, adapter, and full-suite runs | ✅ COMPLIANT |
| Fractional SEP volume preservation | Preserve valid integer and fractional volume | `test_fetch_range_maps_adjusted_sep_bars_in_deterministic_symbol_date_order` (`100` and `250.125`) and `test_fetch_range_preserves_exact_fractional_sep_volume` (`48037.936`) in the 37-test adapter run | ✅ COMPLIANT |
| Fractional SEP volume preservation | Reject negative volume | `test_fetch_range_rejects_negative_volume_without_partial_bars` — `malformed-response`, no partial bars | ✅ COMPLIANT |
| Fractional SEP volume preservation | Reject an absent volume field | `test_fetch_range_rejects_absent_volume_field_without_partial_bars` — SEP columns omit `volume`; expects `malformed-response` and no partial bars | ✅ COMPLIANT |
| Fractional SEP volume preservation | Reject a null or invalid non-volume field | `test_fetch_range_rejects_null_non_volume_field_without_partial_bars` — `open=None` fails closed with no partial bars | ✅ COMPLIANT |
| Fractional SEP volume preservation | Preserve public behavior outside null-volume reconciliation | Adapter suite covers `fetch`/`fetch_range`, adjusted OHLC, ordering, cursor pagination, chunk merging, and coverage; full suite also passes `tests/test_boundaries.py` Sharadar backtest-isolation checks | ✅ COMPLIANT |

**Compliance summary**: 6/6 scenarios compliant; 1/1 modified requirements complete.

### Correctness (Static Evidence)

| Requirement element | Status | Evidence |
|---|---|---|
| Exact explicit null reconciliation | ✅ Implemented | `_SepRow.reconcile_null_volume` returns `Decimal("0")` only when `value is None` (`src/invest/adapters/sharadar_market_data.py:49-52`). |
| Preserve non-null values | ✅ Implemented | Validator returns every non-`None` value unchanged into existing `Decimal = Field(ge=0)` validation. |
| Reject negative values | ✅ Implemented and tested | Existing `ge=0` constraint and public-seam negative-volume test remain green. |
| Reject missing volume | ✅ Implemented and tested | `_rows_to_bars` rejects missing required columns (`set(self.COLUMNS) - columns.keys()`); public-seam test omits the `volume` column. |
| Reject invalid non-volume values without partial bars | ✅ Implemented and tested | Broad validation-to-`malformed-response` mapping unchanged; `open=None` guard passes. |
| Preserve public behavior and boundaries | ✅ Implemented and tested | Production change is limited to the import and private volume before-validator; 577 tests pass. |

### Coherence (Design)

| Decision | Followed? | Notes |
|---|---|---|
| Normalize at private `_SepRow.volume` seam | ✅ Yes | No domain/public-interface nullability was introduced. |
| Match exact `None` only | ✅ Yes | Empty, malformed, negative, and missing values continue through existing validation. |
| Retain bar with exact Decimal zero | ✅ Yes | Public `fetch_range` regression proves the retained BAYA bar and complete one-session coverage. |
| Preserve `_rows_to_bars`, error masking, pagination, chunking, and public methods | ✅ Yes | Production diff remains the Pydantic import plus five-line validator; missing-column path still fails before reconciliation. |

### TDD Compliance

| Check | Result | Details |
|---|---|---|
| TDD evidence reported | ✅ | Apply-progress contains the TDD Cycle Evidence and command-evidence tables. |
| Historical RED recorded | ✅ | Focused pre-fix run recorded exit 1 with `malformed-response` and hash `07ae9864…`. |
| RED test file exists | ✅ | `tests/adapters/test_sharadar_market_data.py` contains the public-seam regressions and guards. |
| Current GREEN confirmed | ✅ | Focused 5/5 selected, adapter 37/37, repository 577/577 non-skipped tests pass. |
| Safety net | ✅ | Apply-progress records 34/34 before the change; independent current adapter run is 37/37. |
| Scenario triangulation | ✅ | All six normative scenarios have distinct public-seam runtime coverage. |

**TDD compliance**: 6/6 checks passed.

### Test Layer Distribution

| Layer | Changed tests | Files | Tools |
|---|---:|---:|---|
| Unit | 0 | 0 | pytest available |
| Provider integration | 3 | 1 | pytest + `httpx.MockTransport` |
| E2E | 0 | 0 | not configured |
| **Total** | **3** | **1** | |

New/changed public-seam tests for this change: null-volume reconcile, null non-volume guard, and absent-volume-column rejection.

### Changed File Coverage

Coverage analysis skipped — no coverage tool is configured in `pyproject.toml` or the cached SDD capabilities.

### Assertion Quality

**Assertion quality**: ✅ All changed assertions exercise production behavior through `SharadarMarketDataReader.fetch_range`; no tautologies, ghost loops, type-only-only checks, smoke-only checks, or mock-heavy call-count coupling were found.

- Null-volume: asserts retained bar identity, exact `Decimal("0")`, and Decimal type.
- Absent volume: asserts `MarketDataFetchError.reason == "malformed-response"` and no partial `bars` attribute.
- Non-volume null / negative: same fail-closed assertions.

### Quality Metrics

**Linter**: ✅ Touched files pass. Repository-wide run retains 17 unchanged baseline findings.  
**Type checker**: ➖ Not configured.  
**Coverage**: ➖ Not configured.

### Snapshot and Review Consistency

| Identity | Observed | Notes |
|---|---|---|
| `HEAD` | `425c5f194dc449da5d8ba0405999362f19720126` | Matches `origin/main` base |
| `origin/main` | `425c5f194dc449da5d8ba0405999362f19720126` | Unchanged |
| Source blob | `a8f896ecfe8fdefb4ca482debf98237e962618c1` | Unchanged since prior verify |
| Test blob | `09ef54cf3b46c40ccb499ecb01fd0683c532e111` | Changed by absent-volume remediation (prior verify had `0f1b2ede…`) |
| Working tree | Dirty | Uncommitted adapter + test changes and untracked OpenSpec change dir |
| Native review receipt | Missing | No `openspec/changes/.../reviews/` artifacts; Engram review topics not materialised |

No reusable content-bound review receipt exists for the current test blob. This verifier did not start or mutate review state. Post-verify review remains an orchestrator concern before archive/commit.

### Issues Found

#### CRITICAL (0)

None.

#### WARNING (0)

None.

#### SUGGESTION (1)

1. **Stale apply-progress counts after remediation** (`openspec/changes/sharadar-sep-null-volume-reconcile/apply-progress.md`): still describes two public-seam tests and a 36-test adapter suite. The working tree now has three change-related public-seam tests and 37 adapter tests. Optional documentation refresh only; independent verification did not rely on those stale counts.

### Verdict

**PASS**

All 6/6 normative scenarios are runtime-compliant, 10/10 tasks are substantiated, design decisions match the implementation, focused/adapter/full tests pass, and touched-file Ruff is clean. Next lifecycle step is archive only after any required post-apply review receipt is obtained for the current candidate; this verify phase does not create that receipt.

## Review Addendum (correction for REL-101 / REL-102)

The shipped diff contains two behavior changes beyond the null-volume requirement verified above: the adjusted-OHLC minimal re-envelope (`src/invest/adapters/sharadar_market_data.py:181-185`) and the ACTIONS exact-zero value acceptance (`src/invest/adapters/sharadar_actions.py:179-185`). Both are KEPT and formalized into this change per the review decision; this addendum extends compliance coverage to them. The front-matter counts above now include the review-absorbed "Deterministic OHLC adjustment" delta requirement (2 requirements, 9 scenarios); the original sections of this report predate the amendment and cover only the null-volume requirement.

### Extended Compliance Coverage

| Behavior | Contract | Covering tests | Evidence class | Result |
|---|---|---|---|---|
| Adjusted-OHLC minimal re-envelope | Delta + main spec `sharadar-sep-market-data` requirement "Deterministic OHLC adjustment" (MODIFIED during review) | `tests/adapters/test_sharadar_market_data.py::test_fetch_range_keeps_adjusted_ohlc_envelope_when_high_equals_close` (existing GSBD regression, tightened during correction to pin `high == max(exact candidates)` exactly, so a widening clamp fails) and `::test_fetch_range_preserves_exact_adjusted_products_when_no_clamp_is_needed` (new exact-product invariant with a fractional `closeadj/close` ratio) | deterministic | ✅ COMPLIANT |
| ACTIONS exact-zero valued rows | Main spec `sharadar-actions-reference-data` requirement "Typed corporate-action events" (amended in this diff with a Previously note; scenario "Exact zero valued actions are retained") | `tests/adapters/test_sharadar_actions.py::test_fetch_accepts_exact_zero_valued_actions` (parameterized over `dividend`/`split`/`spinoffdividend` zero forms, RVPH 2026-02-23 shape) and `::test_rejected_rows_report_why_they_were_rejected` (negative/absent values remain fail-closed) | deterministic | ✅ COMPLIANT |

### Correction Command Evidence

| Purpose | Exact command | Exit | Result |
|---|---|---:|---|
| Envelope pins (focused) | `.venv/bin/python -m pytest tests/adapters/test_sharadar_market_data.py -q -k "envelope or exact_adjusted"` | 0 | 2 passed |
| SEP adapter suite | `.venv/bin/python -m pytest tests/adapters/test_sharadar_market_data.py -q` | 0 | 39 passed |
| ACTIONS adapter suite | `.venv/bin/python -m pytest tests/adapters/test_sharadar_actions.py -q` | 0 | 97 passed |

### TDD Deviation (documented, not remediated)

Both review-absorbed behaviors pre-dated formal SDD tracking on this branch, so RED-phase TDD evidence is historically unavailable for them and is not fabricated here. The two envelope tests added/tightened during this correction are regression pins: they were written and confirmed to PASS against the current implementation (not observed RED). The behaviors are formalized via review correction of findings REL-101 (BLOCKER, spec/test contract) and REL-102 (CRITICAL, scope/verification coverage); the frozen findings ledger at `openspec/changes/sharadar-sep-null-volume-reconcile/reviews/ledger.json` is unchanged by this addendum.

The related untracked draft `openspec/changes/sharadar-live-data-reconcile/` has been annotated so its Unit 1 (ACTIONS zero-value) and Unit 3 (OHLC envelope) are marked as absorbed by this change; future appliers must not re-implement or revert them.
