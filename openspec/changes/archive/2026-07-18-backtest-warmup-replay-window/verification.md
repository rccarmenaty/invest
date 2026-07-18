# Verification Report: backtest-warmup-replay-window

- Change: `backtest-warmup-replay-window`
- Worktree: `/Users/rcty/invest/.worktrees/backtest-warmup-replay-window`
- Branch: `feat/backtest-warmup-replay-window` (7 commits ahead of `main`: `e00f040`, `d0db49b`, `e5d062e`, `f15f875`, `5cf1023`, `91c09c9`, `4e7aeda`)
- Verified: 2026-07-17 (refreshed 2026-07-18 after review correction — see Review Correction Addendum)
- **Executor note**: this verify pass ran on the Claude native agent because Codex quota was exhausted (chain routing deviation from the standard Codex-executed verify phase).

## Verdict: PASS

No CRITICAL or WARNING findings. One SUGGESTION (minor, non-blocking) noted below.

---

## 1. Scenario → Test Matrix

### `point-in-time-market-context` spec

| Requirement / Scenario | Test | Result |
|---|---|---|
| Authoritative generation span — valid span retained | `tests/domain/test_market_context.py::test_status_resolves_complete_matrix_and_exact_outcome_values` | PASS |
| Authoritative generation span — invalid span rejected (empty/inverted) | `tests/domain/test_market_context.py::test_generation_span_is_immutable_and_rejects_inversion` (line 33) | PASS |
| Context authority — complete matrix | `tests/domain/test_market_context.py::test_require_complete_accepts_a_complete_multi_symbol_matrix` | PASS |
| Context authority — invalid matrix fails before replay | `tests/domain/test_market_context.py::test_contradictory_symbol_state_raises_market_context_invalid`, `test_require_complete_checks_later_symbols_for_missing_dates` | PASS |
| Outside-span authority rejected | `tests/domain/test_market_context.py::test_context_queries_fail_closed_outside_generation_span` (line 47, parametrized `status`/`require_complete`/`eligible_symbols`) | PASS |

### `sharadar-market-context-generator` spec

| Requirement / Scenario | Test | Result |
|---|---|---|
| Scanner-sufficient warmup fetch — full-history symbol gets ≥253 sessions | `tests/adapters/test_sharadar_context_source.py::test_load_fetches_scanner_sufficient_preceding_xnys_sessions` (line 217; asserts `len(expected_sessions) == 253`) | PASS |
| Listing date bounds warmup | `tests/adapters/test_sharadar_context_source.py::test_load_clips_delisted_candidate_history`, `test_load_accepts_new_listing_without_prelisting_sep`, `test_new_listing_without_prelisting_sep_is_ineligible_until_seasoned` | PASS |
| Deterministic schema output — reproduce byte-identical JSON | `tests/adapters/test_backtest_context_json.py::test_writer_is_deterministic_for_identical_context`; `tests/adapters/test_generate_context_cli.py::test_bars_out_writes_deterministic_pair_with_pre_span_warmup` (asserts byte-identical context + universe + bars across two runs) | PASS |
| Reject absent/malformed/inverted span | `tests/adapters/test_backtest_context_json.py::test_rejects_missing_malformed_empty_or_inverted_generation_span` (line 81-97, parametrized `None`/`{}`/`[]`/inverted); `test_rejects_unsupported_schema_version` (rejects literal `market-context-v1`) | PASS |
| Pair bars output with declared span | `tests/adapters/test_generate_context_cli.py::test_bars_out_writes_deterministic_pair_with_pre_span_warmup` (line 85-110; asserts `min(bar.date for bar in inputs.bars) == 2023-12-31` while `generation_span.start == 2024-01-02`, i.e. bars fixture carries pre-span warmup) | PASS |

### `trading-system` spec

| Requirement / Scenario | Test | Result |
|---|---|---|
| Partition warmup/replay bars | `tests/application/test_backtest_run.py::test_warmup_bars_are_scanner_visible_but_never_replay_events` (line 195) | PASS |
| Reject post-span bars | `tests/application/test_backtest_run.py::test_replay_rejects_post_span_bars_with_stable_reason` (line 243); `tests/adapters/test_cli_backtest.py::test_backtest_rejects_post_span_bar_with_one_replay_window_record` (line 503) | PASS |
| Require an in-window session | `tests/application/test_backtest_run.py::test_replay_rejects_empty_in_span_partition_with_stable_reason` (line 258) | PASS |
| Warmup bars history-only, first replay date sees warmup history | `tests/application/test_backtest_run.py::test_warmup_bars_are_scanner_visible_but_never_replay_events` (asserts `len(recorder.windows[0]) == 21`, i.e. warmup bars are in the scanner window) | PASS |
| No pre-span events | `tests/application/test_backtest_run.py::test_warmup_bars_are_scanner_visible_but_never_replay_events` (asserts `min(event_dates) >= replay_start`); `tests/fixtures/test_backtest_252_fixtures.py::test_backtest_252_replay_emits_no_pre_span_events` (line 60; real-shape fixture, asserts `all(span.start <= day <= span.end for day in event_dates)`) | PASS |
| Full-window fixture context completeness — in-window gap fails closed | `tests/application/test_backtest_run.py::test_replay_checks_each_observed_in_span_date_for_every_fixture_symbol` (line 222); `test_replay_rejects_incomplete_context_before_scanning` (line 163, asserts scanner never called: `scanner.calls == 0`) | PASS |
| Daily summary observable / deterministic | `tests/application/test_backtest_run.py::test_replaying_same_range_twice_is_byte_identical` | PASS |
| Trades split by entry date | `tests/domain` backtest_metrics segment tests (unchanged, pre-existing) + CLI `test_backtest_report_exposes_portfolio_contract_and_all_limitations` | PASS |
| Invalid split date fails closed | `tests/adapters/test_cli_backtest.py::test_backtest_requires_valid_in_range_split_date_as_one_json_error`, `test_backtest_rejects_malformed_or_out_of_range_split_date` | PASS |
| Warmup date cannot validate split | `tests/adapters/test_cli_backtest.py::test_backtest_rejects_warmup_split_date_with_replay_window_record` (line 457); `test_backtest_rejects_unobserved_in_span_split_date` (line 479, unobserved-but-in-range date also rejected — exact-membership policy) | PASS |
| Exact observed in-span split accepted | `tests/adapters/test_cli_backtest.py::test_backtest_accepts_exact_observed_in_span_split_date` (line 437) | PASS |
| Live `--start/--end` exact span equality | `tests/adapters/test_cli_backtest.py::test_backtest_live_range_must_exactly_match_declared_span` (line 525) | PASS |

No scenario gaps found — all 8 delta requirements have at least one asserting test; all are exercised in the current run (see §3).

---

## 2. Design Conformance in Code

All design decisions from `design.md`'s Architecture Decisions table are implemented as specified. No divergence found. (Full evidence in working-tree verification.md §2.)

---

## 3. Test Suite and Lint

Full suite: `uv run pytest -q`: 507 passed, 1 skipped in 15.25s. Lint: `uv run ruff check` clean. All 172 focused tests from strict TDD strategy pass in isolation. The single skip is pre-existing and unrelated to this change.

---

## 4. Runtime Proof

Fixture context span: `{"start": "2020-09-09", "end": "2020-09-16"}` with v2 schema. Bars span 2020-01-01 to 2020-09-16 (260 observed dates), confirming pre-span warmup bars present.

Positive case: `invest-backtest` with split-date 2020-09-14 (in-span) exits 0 with valid report.
Negative case: same with split-date 2020-08-14 (warmup-only) exits 2 with `{"reason": "replay-window-invalid"}`.

---

## 5. Proposal Success Criteria

All 5 criteria met: warmup/replay fixture separation, fail-closed span validation, in-window completeness, no pre-span events, ≥253-session warmup fetch.

---

## 6. Scope Audit

27 files changed, 1477 insertions(+), 86 deletions(-). All files map to change contract. Known deviation: `bars_fixture_json.py` restoration is byte-identical to origin and required by contract (Pair bars with span scenario).

---

## Findings

**CRITICAL**: none.
**WARNING**: none.
**SUGGESTION** (non-blocking): (Addressed) Success criteria checkboxes — resolved by commit `5cf1023`.

---

## Review Correction Addendum (2026-07-18)

Two CRITICAL findings corrected in-branch:
- `91c09c9`: orphan-context cleanup on bars-write failure
- `4e7aeda`: XNYS calendar start pinned to 1990-01-01

Post-correction: 510 passed, 1 skipped; ruff clean; runtime smoke pass.
