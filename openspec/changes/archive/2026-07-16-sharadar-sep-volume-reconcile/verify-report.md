```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:d538911d067399a1917af7d54167bb725e2ed7d017e464ec54347a2ea58b4b4a
verdict: pass_with_warnings
blockers: 0
critical_findings: 0
requirements: 4/4
scenarios: 11/11
test_command: uv run pytest -q
test_exit_code: 0
test_output_hash: sha256:4163a8ff66b3bdf63f9d74c16fcf751850ad2277a389b1f08f8771b48a6c6537
build_command: uv run ruff check src/invest/domain/models.py src/invest/adapters/sharadar_market_data.py src/invest/adapters/alpaca_market_data.py src/invest/adapters/fixtures_json.py src/invest/domain/liquidity_screen.py tests/adapters/test_sharadar_market_data.py tests/adapters/test_alpaca_market_data.py tests/adapters/test_fixtures_json.py tests/domain/test_liquidity_screen.py
build_exit_code: 0
build_output_hash: sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18
```

## Verification Report

**Change**: 2026-07-16-sharadar-sep-volume-reconcile
**Version**: N/A (delta change)
**Mode**: Strict TDD
**Artifact store**: hybrid (OpenSpec + Engram)
**Review authority**: lineage `review-fcb57c0b9c700142` (post-apply validation passed; not authority-only denied)
**Strict envelope**: schema-validated for native dispatch (`gentle-ai.verify-result/v1` canonical fields only; focused/SEP evidence kept in narrative)

### Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 13 |
| Tasks complete | 13 |
| Tasks incomplete | 0 |
| Verification handoff (non-checkbox) | owned by sdd-verify — executed this phase |

All apply checkboxes 1.1–5.1 are marked complete in `tasks.md` and `apply-progress.md`. Full-suite and representative SEP pull are correctly **not** apply checkboxes.

### Build & Tests Execution

**Build / static check (ruff on changed files)**: ✅ Passed (exit 0)
```text
uv run ruff check src/invest/domain/models.py src/invest/adapters/sharadar_market_data.py src/invest/adapters/alpaca_market_data.py src/invest/adapters/fixtures_json.py src/invest/domain/liquidity_screen.py tests/adapters/test_sharadar_market_data.py tests/adapters/test_alpaca_market_data.py tests/adapters/test_fixtures_json.py tests/domain/test_liquidity_screen.py
All checks passed!
```
`build_output_hash`: `sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`

**Focused tests** (narrative evidence only; not an envelope field): ✅ 92 passed, 1 skipped (exit 0)
```text
uv run pytest tests/adapters/test_sharadar_market_data.py tests/adapters/test_alpaca_market_data.py tests/adapters/test_fixtures_json.py tests/domain/test_liquidity_screen.py -q
.........................s.............................................. [ 77%]
.....................                                                    [100%]
92 passed, 1 skipped in 0.76s
```
Focused test command: `uv run pytest tests/adapters/test_sharadar_market_data.py tests/adapters/test_alpaca_market_data.py tests/adapters/test_fixtures_json.py tests/domain/test_liquidity_screen.py -q`
Focused test exit code: `0`
Focused test output hash: `sha256:8c196392b8e78fd24cedc1f6e6d82101deb843cecc0d7123a2b1f492cbc42bab`

**Full suite**: ✅ 548 passed, 1 skipped (exit 0)
```text
uv run pytest -q
.................s...................................................... [ 13%]
........................................................................ [ 26%]
........................................................................ [ 39%]
........................................................................ [ 52%]
........................................................................ [ 65%]
........................................................................ [ 78%]
........................................................................ [ 91%]
.............................................                            [100%]
548 passed, 1 skipped in 9.94s
```
`test_output_hash`: `sha256:4163a8ff66b3bdf63f9d74c16fcf751850ad2277a389b1f08f8771b48a6c6537`

**Coverage**: ➖ Not available — `pytest-cov` / `coverage` not installed in the environment. Coverage analysis skipped (not a failure).

**Type checker**: ➖ Not available — no mypy (or equivalent) in project dependencies.

### Representative SEP Pull (external boundary)

Credentials available via normal application loading (`NASDAQ_DATA_LINK_API_KEY` present; value not revealed). Read-only pull only; no live trading.

**Primary representative pull** (AAPL, 2024-01-02 → 2024-01-05):
```text
status=ok
bar_count= 4
all_volume_decimal= True
any_negative= False
ordered= True
ohlc_decimal= True
AAPL 2024-01-02 volume 79824000.0 Decimal
AAPL 2024-01-03 volume 56442000.0 Decimal
AAPL 2024-01-04 volume 70652000.0 Decimal
AAPL 2024-01-05 volume 61866000.0 Decimal
```
SEP pull status (narrative): `available_and_ok`
SEP pull output hash (narrative): `sha256:c83c6761d84c8933a0ece23bfcc102443ef291db35d620c5647f410305d9c63c`

**Additional candidate windows** (NVDA/TSLA/AAPL split-adjacent ranges; META/AMZN/GOOGL/IBM/GE/F/BAC/XOM/CVX): all succeeded with `volume` as `Decimal`, non-negative, ordered; **no live fractional volume sample observed** in those windows.

**Interpretation**: Live path confirms provider-neutral Decimal volume end-to-end through `SharadarMarketDataReader.fetch_range`. Exact fractional preservation (`Decimal("48037.936")`) is proven by unit tests against real-shaped SEP payloads, not by a live fractional sample in the windows tried.

### Spec Compliance Matrix

| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Fractional SEP volume preservation | Preserve valid fractional volume | `tests/adapters/test_sharadar_market_data.py` > `test_fetch_range_preserves_exact_fractional_sep_volume` (+ `test_fetch_range_maps_adjusted_sep_bars` for `250.125`) | ✅ COMPLIANT |
| Fractional SEP volume preservation | Reject negative volume | `tests/adapters/test_sharadar_market_data.py` > `test_fetch_range_rejects_negative_volume_without_partial_bars` | ✅ COMPLIANT |
| Fractional SEP volume preservation | Preserve unrelated SEP behavior | `tests/adapters/test_sharadar_market_data.py` > `test_fetch_range_maps_adjusted_sep_bars_in_deterministic_symbol_date_order` (OHLC adjust + order) + live pull OHLC/order checks | ✅ COMPLIANT |
| Canonical daily-bar volume | Preserve Alpaca fractional volume | `tests/adapters/test_alpaca_market_data.py` > `test_reader_preserves_fractional_alpaca_volume_as_exact_decimal` | ✅ COMPLIANT |
| Canonical daily-bar volume | Reject negative fixture volume | `tests/adapters/test_fixtures_json.py` > `test_rejects_negative_volume_before_producing_daily_bars` (+ param case `volume: -1`) | ✅ COMPLIANT |
| Fetch-to-fixture snapshot semantics | Snapshot feeds the unchanged scan pipeline | `tests/adapters/test_alpaca_market_data.py` > `test_snapshot_writes_schema_provenance_and_round_trips` (`MomentumScanner` on loaded snapshot) | ✅ COMPLIANT |
| Fetch-to-fixture snapshot semantics | Fractional volume round-trips exactly | `tests/adapters/test_alpaca_market_data.py` > `test_snapshot_round_trips_fractional_canonical_volume` | ✅ COMPLIANT |
| Fetch-to-fixture snapshot semantics | Integral snapshot compatibility | `tests/adapters/test_alpaca_market_data.py` > `test_snapshot_writes_schema_provenance_and_round_trips` (`volume == 100` JSON number) | ✅ COMPLIANT |
| Configurable point-in-time liquidity screen | Apply Core defaults | `tests/domain/test_liquidity_screen.py` > core defaults + eligible history cases | ✅ COMPLIANT |
| Configurable point-in-time liquidity screen | Reject insufficient or failing history | `tests/domain/test_liquidity_screen.py` > insufficient bars / price / rolling volume ineligible cases | ✅ COMPLIANT |
| Configurable point-in-time liquidity screen | Retain fractional liquidity at the threshold | `tests/domain/test_liquidity_screen.py` > `test_eligibility_uses_fractional_volume_in_decimal_dollar_volume` | ✅ COMPLIANT |

**Compliance summary**: 11/11 scenarios compliant (covering tests exist and passed at runtime)

### Correctness (Static Evidence)

| Requirement | Status | Notes |
|------------|--------|-------|
| Canonical `DailyBar.volume: Decimal` | ✅ Implemented | `src/invest/domain/models.py` |
| Sharadar SEP `_SepRow.volume: Decimal = Field(ge=0)` pass-through | ✅ Implemented | `sharadar_market_data.py` maps `volume=row.volume` |
| Alpaca `_BarPayload.volume: Decimal = Field(ge=0, alias="v")` pass-through | ✅ Implemented | no quantization on map |
| Fixtures `_BarPayload.volume: Decimal = Field(ge=0)` | ✅ Implemented | rejects negative before domain |
| Dual-form snapshot write | ✅ Implemented | integral → `int`; fractional → exact decimal string |
| Liquidity pure Decimal product | ✅ Implemented | `bar.close * bar.volume` (no redundant cast / float path) |
| Negative volume fail-closed | ✅ Implemented | ValidationError → `malformed-response` / `FixtureValidationError` |

### Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| Canonical volume type = `Decimal` | ✅ Yes | domain model |
| Validation seam = adapter Pydantic `Field(ge=0)` | ✅ Yes | all three adapters |
| Snapshot dual form (int number / fractional string) | ✅ Yes | `SnapshotWriter` |
| Liquidity direct `close * volume` | ✅ Yes | `liquidity_screen.py` |
| Scope = domain + 3 adapters + screen + tests | ✅ Yes | matches file list |
| No new live-provider harness in apply | ✅ Yes | verify-owned SEP pull only |

### TDD Compliance

| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | ✅ | Found in `apply-progress.md` “TDD Cycle Evidence” table |
| All tasks have tests | ✅ | 12/12 code tasks map to adapter/domain tests; 5.1 process-only |
| RED confirmed (tests exist) | ✅ | Fractional + negative + round-trip + liquidity tests present on disk |
| GREEN confirmed (tests pass) | ✅ | Focused 92 passed; full 548 passed |
| Triangulation adequate | ✅ | SEP: `250.125` + `48037.936` + negative; Alpaca integral + fractional + negative; snapshot integral + fractional RT; liquidity exact vs truncated product |
| Safety Net for modified files | ✅ | Apply-progress reports prior focused 87/87 safety net; current full suite green |

**TDD Compliance**: 6/6 checks passed

### Test Layer Distribution

| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 92 passed (+1 skipped) focused; 548 passed (+1 skipped) full | 4 focused files under `tests/adapters/` + `tests/domain/` | pytest via `uv run` |
| Integration | 0 new | — | not required by design |
| E2E | 0 new | — | design: no new live-provider harness |
| **Total (focused)** | **93 collected** | **4** | |

Representative live SEP pull is verification evidence, not an automated E2E test case.

### Changed File Coverage

Coverage analysis skipped — no coverage tool detected (`pytest-cov` / `coverage` absent).

Changed implementation files inspected statically:
- `src/invest/domain/models.py`
- `src/invest/adapters/sharadar_market_data.py`
- `src/invest/adapters/alpaca_market_data.py`
- `src/invest/adapters/fixtures_json.py`
- `src/invest/domain/liquidity_screen.py`

### Assertion Quality

| File | Line | Assertion | Issue | Severity |
|------|------|-----------|-------|----------|
| — | — | — | — | — |

**Assertion quality**: ✅ All assertions verify real behavior

Notes (non-violations):
- Fractional tests assert exact `Decimal("48037.936")` / `Decimal("250.125")` values, not type-only checks.
- Negative paths call production readers/loaders and assert failure reason + no partial bars / no DailyBar.
- Round-trip tests assert JSON form (`"48037.936"` string vs integral number) **and** reloaded equality.
- Liquidity test asserts exact product `480379.36`, truncated product strictly less, and eligibility True under exact floor.
- No tautologies, ghost loops, or smoke-only assertions found in change-related tests.

### Quality Metrics

**Linter (ruff)**: ✅ No errors  
**Type Checker**: ➖ Not available  
**Coverage tool**: ➖ Not available

### Issues Found

**CRITICAL**: None

**WARNING**:
1. Live representative SEP pulls across multiple symbols/windows returned only integral volumes. Fractional preservation is proven by unit tests with real-shaped payloads (`48037.936`), not by a live fractional sample. External boundary was available and the Decimal path succeeded.
2. Coverage analysis unavailable (no coverage package) — cannot quantify changed-file line/branch coverage.

**SUGGESTION**:
1. `tests/domain/test_liquidity_screen.py` helper `_bar(..., volume: int)` still annotates volume as `int` while the domain type is `Decimal`. Runtime works (dataclass accepts the value; `Decimal * int` yields `Decimal`), but aligning the helper annotation to `Decimal` would reduce confusion for future edits.
2. Consider recording one known live ticker/date that currently emits fractional adjusted SEP volume for future verify-phase smoke (without hard-coding secrets).

### Verdict

**PASS WITH WARNINGS**

All 13 apply tasks complete; all 4 requirements / 11 scenarios have passing runtime coverage; Strict TDD evidence is present and re-confirmed by execution; design decisions match code; full suite green (548 passed); ruff clean; representative SEP pull succeeded with Decimal volume and unchanged OHLC/order. Warnings are limited to missing live fractional sample in sampled windows and unavailable coverage tooling — not behavioral failures.

Strict envelope revalidated: removed non-schema fields (`focused_test_*`, `sep_pull_*`, `mode`, non-denial authority flags) so native `gentle-ai sdd-status` can parse `gentle-ai.verify-result/v1`. No commands re-executed; prior evidence preserved.

---

### Canonical verification-evidence bytes (preserve for parent)

Primary test command output (exact):
```
.................s...................................................... [ 13%]
........................................................................ [ 26%]
........................................................................ [ 39%]
........................................................................ [ 52%]
........................................................................ [ 65%]
........................................................................ [ 78%]
........................................................................ [ 91%]
.............................................                            [100%]
548 passed, 1 skipped in 9.94s
```

Primary build/static command output (exact):
```
All checks passed!
```

Focused test command output (exact):
```
.........................s.............................................. [ 77%]
.....................                                                    [100%]
92 passed, 1 skipped in 0.76s
```

Representative SEP pull summary output (exact; no credentials):
```
status=ok
bar_count= 4
all_volume_decimal= True
any_negative= False
ordered= True
ohlc_decimal= True
AAPL 2024-01-02 volume 79824000.0 Decimal
AAPL 2024-01-03 volume 56442000.0 Decimal
AAPL 2024-01-04 volume 70652000.0 Decimal
AAPL 2024-01-05 volume 61866000.0 Decimal
```
