# Tasks: Reconcile SharadarActionsReader with the Real SHARADAR/ACTIONS Schema

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~200-260 (mostly test-file rewrite) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|-----------------------|------------------|--------------------|
| 1 | Test-first rewrite + adapter fix for real ACTIONS vocabulary, skip-unknown, float coercion | PR 1 (single) | `pytest tests/adapters/test_sharadar_actions.py -v` | `invest-generate-context` broad-market pull 2025-07-16..2026-07-16 (manual, real API) | Revert the single adapter+test commit; no schema/domain/consumer changes |

## Phase 1: RED — Rewrite tests/adapters/test_sharadar_actions.py first

- [x] 1.1 Replace `test_fetch_maps_all_provider_literals_to_closed_frozen_events` with the 10 mapped literals (`split`, `adrratiosplit` → SPLIT; `dividend`, `spinoffdividend` → DIVIDEND; `delisted`, `regulatorydelisting`, `voluntarydelisting`, `bankruptcyliquidation` → DELISTING; `tickerchangeto`, `tickerchangefrom` → TICKER_CHANGE), asserting kind + value class.
- [x] 1.2 Add parametrized test: the 8 skipped literals (`listed`, `relation`, `acquisitionby`, `acquisitionof`, `mergerto`, `mergerfrom`, `spinoff`, `spunofffrom`) plus one arbitrary unknown literal each → `fetch()` returns `()`, no raise.
- [x] 1.3 Add multi-page test: unknown/skipped literal on page 1 does not abort the fetch; page 2's valid rows are still returned combined.
- [x] 1.4 Replace the `("dividend", 0.1)` rejection case with an acceptance test: floats `0.1`, `0.25`, `123.456789012345` → exact `Decimal(str(f))`, matching spec's "Float values coerce to exact Decimals" scenario.
- [x] 1.5 In `test_fetch_rejects_invalid_or_unsupported_action_rows`, remove now-valid/now-skipped cases (`("dividend", 0.1)`, `("tickerchange", "1")`, `("unsupported", "1")`, `("SPLIT", "2")`); keep split-ratio and dividend-finite cases; add `("tickerchangeto", "1")` for the valueless violation.
- [x] 1.6 In `test_rejected_rows_report_why_they_were_rejected`, replace `("delisting", "3", ...)` with `("delisted", "3", ...)`; delete the `("merger", "1", "unsupported ACTIONS action")` row.
- [x] 1.7 Add a boundary test asserting `_ACTION_KINDS.keys() & _SKIPPED_ACTIONS == set()`.
- [x] 1.8 Run `pytest tests/adapters/test_sharadar_actions.py -v` and confirm the rewritten/new tests FAIL against the current adapter (RED confirmed). — 25 failed / 39 passed against pre-fix adapter.

## Phase 2: GREEN — Fix src/invest/adapters/sharadar_actions.py

- [x] 2.1 Expand `_ACTION_KINDS` to the 10 mapped literals per the Mapping Table, folded onto the existing closed `SharadarActionKind` enum (no enum changes).
- [x] 2.2 Add module-level `_SKIPPED_ACTIONS` frozenset documenting the 8 explicit skip literals.
- [x] 2.3 In `_rows_to_actions`, resolve `kind = _ACTION_KINDS.get(raw_action)` from the raw literal BEFORE `_ActionRow.model_validate`; `continue` (no raise) when `kind is None`.
- [x] 2.4 Drop the `action` field from `_ActionRow`; pass only `ticker`, `date`, `value` to `model_validate`.
- [x] 2.5 Remove the `isinstance(raw_value, float)` guard; rely on pydantic v2 Decimal coercion (precedent: `_SepRow` in `sharadar_market_data.py`).
- [x] 2.6 Run `pytest tests/adapters/test_sharadar_actions.py -v` and confirm all tests pass (GREEN). — 64 passed.

## Phase 3: Verification

- [x] 3.1 Run `test_actions_source_has_no_sep_or_daily_bar_import` to confirm the boundary is unaffected. — passes.
- [x] 3.2 Run the full suite (`pytest tests/`) to confirm no regression in kind-blind consumers (`sharadar_context_source.py`, `generate_market_context.py`, `market_context_builder.py`). — 509 passed, 1 skipped (pre-existing, unrelated).
- [x] 3.3 Confirm the live-shaped float fixture (`9.00009000090001`, `0.04545`) produces exact `Decimal` values matching the spec scenario, no precision loss. — `test_live_shaped_float_fixture_has_no_precision_loss` passes.

## Phase 4: Cleanup

- [x] 4.1 Re-read the adapter diff for stray unused imports or dead code left from removing the `action` field / float guard. — confirmed clean; `ruff check` passes on both changed files.
- [ ] 4.2 Check off the proposal's Success Criteria in `proposal.md` once a real broad-market pull succeeds end-to-end. — Two of three criteria checked (skip-unknown policy, float precision) since they are proven by the test suite. The live end-to-end broad-market pull criterion remains open: it requires a real `NASDAQ_DATA_LINK_API_KEY` and network access not available in this apply sandbox; needs manual verification.
