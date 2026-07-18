# Tasks: Reconcile Null SHARADAR/SEP Volume

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~300–360 total authored lines: ~35–55 implementation/tests plus existing SDD and expected evidence artifacts |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR; monitor final authored diff before review |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending (not needed unless scope grows) |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Reconcile exact SEP null volume while preserving strict validation | Single PR | `uv run pytest tests/adapters/test_sharadar_market_data.py -k null_volume` | N/A — deterministic MockTransport exercises the complete provider boundary without credentials | Revert the validator and its regression/guard tests; prior fail-closed behavior returns |

## Phase 1: RED — Public-Semantics Tracer Bullet

- [x] 1.1 In `tests/adapters/test_sharadar_market_data.py`, add a `fetch_range` regression using BAYA on 2024-12-31 with valid flat OHLC/closeadj and `volume=None`; assert the retained symbol/date/prices, exact `Decimal("0")`, Decimal type, and successful one-session coverage.
- [x] 1.2 Run `uv run pytest tests/adapters/test_sharadar_market_data.py -k null_volume`; record the expected pre-fix `malformed-response` failure before editing production code.

## Phase 2: GREEN — Minimal Provider Reconciliation

- [x] 2.1 In `src/invest/adapters/sharadar_market_data.py`, import `field_validator` and add a private `_SepRow.volume` before-validator that maps only `value is None` to `Decimal("0")` and returns every other value unchanged.
- [x] 2.2 Re-run the focused null-volume command; record GREEN evidence proving bar retention and exact zero without interface changes.

## Phase 3: REFACTOR — Preserve Fail-Closed Guards

- [x] 3.1 Confirm existing public-seam tests cover fractional/integer exactness, negative rejection, absent/short volume, ordering, adjustment, pagination, chunking, and coverage; add an `open=None` malformed-response/no-partial-bars guard only if current coverage lacks it.
- [x] 3.2 Keep `_rows_to_bars`, domain models, public methods, and broad error masking unchanged; refactor naming only while GREEN.
- [x] 3.3 Run `uv run pytest tests/adapters/test_sharadar_market_data.py` and record focused adapter evidence.

## Phase 4: Verification and Handoff

- [x] 4.1 Run `uv run pytest`; record exit code and output hash for the complete suite.
- [x] 4.2 Run `uv run ruff check src tests`; record exit code and output hash.
- [x] 4.3 Confirm the authored diff remains below 400 lines, update these checkboxes/apply progress with RED→GREEN evidence, and hand proposal/spec/design/tasks plus test/lint evidence to `sdd-verify`.
