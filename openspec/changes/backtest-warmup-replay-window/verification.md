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

| Design decision | Evidence |
|---|---|
| `market-context-v2` schema label | `src/invest/adapters/backtest_context_json.py:69` — `schema_version: Literal["market-context-v2"]` |
| Required top-level `generation_span` | `src/invest/adapters/backtest_context_json.py:70` — `generation_span: _DateRangePayload` (no `Optional`, no default) |
| Fail-closed v1/malformed/inverted rejection | `test_rejects_unsupported_schema_version` (v1 literal rejected by Pydantic `Literal` type before any inference); `test_rejects_missing_malformed_empty_or_inverted_generation_span`; `_DateRangePayload.validate_dates` (`backtest_context_json.py:42-46`) raises on `end < start` |
| Immutable `GenerationSpan` on `MarketContext` | `src/invest/domain/market_context.py:35-45` — `@dataclass(frozen=True) class GenerationSpan`, `__post_init__` raises `MarketContextInvalidError` on inversion (line 41-42); `MarketContext.generation_span: GenerationSpan` required field (`market_context.py:146`) |
| Exact `{"reason":"replay-window-invalid"}` error record | `src/invest/adapters/cli.py:276-278` — `_backtest_replay_window_error()` prints exactly `{"reason": "replay-window-invalid"}`; verified against runtime output below (§4) |
| `HISTORY_DAYS` imported from domain `momentum_selection_scanner`, no duplicate 253 | `src/invest/adapters/sharadar_context_source.py:28` — `from invest.domain.momentum_selection_scanner import HISTORY_DAYS`; used at `:130-134` as `max(config.min_observed_bars, config.dollar_volume_window, HISTORY_DAYS)`; `rg -n "HISTORY_DAYS" src/invest/domain/momentum_selection_scanner.py` shows the sole definition at line 20 (`HISTORY_DAYS = 253`) — no second literal `253` constant in the adapter |
| `--split-date` exact in-span observed-date membership | `src/invest/application/backtest_run.py:143-146` — `if split_date is not None and split_date not in partition.replay_dates: raise ReplayWindowInvalidError(...)`; confirmed both warmup-date and unobserved-but-in-range dates rejected (`test_backtest_rejects_warmup_split_date_with_replay_window_record`, `test_backtest_rejects_unobserved_in_span_split_date`) |
| Live `--start/--end` exact span equality | `src/invest/adapters/cli.py:204-208` — `if args.start != span.start or args.end != span.end: raise ReplayWindowInvalidError(...)` |

All design decisions from `design.md`'s Architecture Decisions table are implemented as specified. No divergence found.

---

## 3. Test Suite and Lint

Run from worktree root (`/Users/rcty/invest/.worktrees/backtest-warmup-replay-window`):

```
$ uv run pytest -q
.................s...................................................... [ 14%]
........................................................................ [ 28%]
........................................................................ [ 42%]
........................................................................ [ 56%]
........................................................................ [ 70%]
........................................................................ [ 85%]
....                                                                     [100%]
507 passed, 1 skipped in 15.25s
```

```
$ uv run ruff check
All checks passed!
```

Targeted re-run of the 9 files named in `design.md`'s Strict TDD Strategy + `tasks.md`'s Suggested Work Units also pass in isolation:

```
$ uv run pytest -q tests/domain/test_market_context.py tests/domain/test_market_context_builder.py \
  tests/adapters/test_backtest_context_json.py tests/application/test_backtest_run.py \
  tests/adapters/test_cli_backtest.py tests/adapters/test_sharadar_context_source.py \
  tests/adapters/test_generate_context_cli.py tests/domain/test_momentum_selection_scanner.py \
  tests/fixtures/test_backtest_252_fixtures.py
........................................................................ [ 41%]
........................................................................ [ 83%]
............................                                             [100%]
172 passed in 0.88s
```

The single skip in the full run is pre-existing and unrelated to this change (not investigated further — outside change scope).

---

## 4. Runtime Proof (`fixtures/backtest-252`)

Fixture context span: `{"start": "2020-09-09", "end": "2020-09-16"}` (`fixtures/backtest-252/market-context.json`, `schema_version: market-context-v2`). Bars span `2020-01-01` .. `2020-09-16` (260 observed dates), confirming pre-span warmup bars are present in the fixture.

**Positive case** — valid in-span `--split-date` (`2020-09-14`, inside `2020-09-09..2020-09-16`), `--strategy core`:

```
$ uv run invest-backtest \
  --universe fixtures/backtest-252/universe.json \
  --bars fixtures/backtest-252/bars.json \
  --market-context fixtures/backtest-252/market-context.json \
  --strategy core \
  --split-date 2020-09-14
Exit code: 0
```
Output is a valid JSON report (keys include `trade_count`, `context_outcomes`, `equity`, `exit_policy`, ...). No `market-context-incomplete` or `replay-window-invalid` error.

**Negative case** — `--split-date` set to a warmup-only date (`2020-08-14`, before span start `2020-09-09`), same fixture/strategy:

```
$ uv run invest-backtest \
  --universe fixtures/backtest-252/universe.json \
  --bars fixtures/backtest-252/bars.json \
  --market-context fixtures/backtest-252/market-context.json \
  --strategy core \
  --split-date 2020-08-14
Exit code: 2
{"reason": "replay-window-invalid"}
```

Both outcomes match the design contract exactly (positive: exit 0, complete report; negative: exit 2, exactly one `{"reason":"replay-window-invalid"}` record).

---

## 5. Proposal Success Criteria

| # | Criterion | Met | Evidence |
|---|---|---|---|
| 1 | Real generated fixtures with warmup bars replay without `market-context-incomplete` | Yes (via checked-in deterministic fixture, per design.md's explicit fallback: real Sharadar-credentialed regeneration of `fixtures/real-years/**` is called out as a "post-merge operational note", not part of this code change) | §4 positive run against `fixtures/backtest-252` (260 observed bar-dates, 8 in-span replay dates, 252 pre-span warmup dates) exits 0 with a complete report and no `market-context-incomplete`/`market-context-invalid` |
| 2 | Artifacts without a valid span are rejected fail-closed | Yes | `test_rejects_missing_malformed_empty_or_inverted_generation_span`, `test_rejects_unsupported_schema_version` (§1) |
| 3 | In-window coverage gaps still raise `MarketContextIncompleteError` | Yes | `test_replay_checks_each_observed_in_span_date_for_every_fixture_symbol`, `test_replay_rejects_incomplete_context_before_scanning` (asserts scanner never invoked) |
| 4 | No portfolio/decision events dated before the declared span start | Yes | `test_warmup_bars_are_scanner_visible_but_never_replay_events`, `test_backtest_252_replay_emits_no_pre_span_events` (§1, §7) — both assert `min(event_date) >= span.start` over trades, skipped entries, and context outcomes |
| 5 | Core generation requests >= 253 sessions of history | Yes | `test_load_fetches_scanner_sufficient_preceding_xnys_sessions` asserts `len(expected_sessions) == 253`; `test_backtest_252_every_symbol_has_at_least_253_bars` on the checked-in fixture |

All 5 success criteria are met with test or runtime evidence. (The `proposal.md` Success Criteria checkboxes at lines 70-74 are rendered `- [x]` — the earlier SUGGESTION about unchecked boxes has been addressed by commit `5cf1023`.)

---

## 6. Scope Audit

```
$ git diff --stat main...HEAD
 fixtures/backtest-252/market-context.json          |  18 +-
 fixtures/backtest/market-context.json              |   6 +-
 .../backtest-warmup-replay-window/design.md        |  41 ++++
 .../backtest-warmup-replay-window/exploration.md   |  88 ++++++++
 .../backtest-warmup-replay-window/proposal.md      |  74 +++++++
 .../specs/point-in-time-market-context/spec.md     |  44 ++++
 .../sharadar-market-context-generator/spec.md      |  46 ++++
 .../specs/trading-system/spec.md                   |  84 +++++++
 .../changes/backtest-warmup-replay-window/tasks.md |  72 ++++++
 .../backtest-warmup-replay-window/verification.md  | 242 +++++++++++++++++++++
 src/invest/adapters/backtest_context_json.py       |  23 +-
 src/invest/adapters/bars_fixture_json.py           | 112 ++++++++++
 src/invest/adapters/cli.py                         |  25 ++-
 src/invest/adapters/generate_context_cli.py        |  35 +++
 src/invest/adapters/sharadar_context_source.py     |  20 +-
 src/invest/application/backtest_run.py             |  71 +++++-
 src/invest/domain/market_context.py                |  19 ++
 src/invest/domain/market_context_builder.py        |   9 +-
 tests/adapters/test_backtest_context_json.py       |  52 ++++-
 tests/adapters/test_cli_backtest.py                | 166 ++++++++++++--
 tests/adapters/test_generate_context_cli.py        |  78 ++++++-
 tests/adapters/test_sharadar_context_source.py     |  30 ++-
 tests/application/test_backtest_run.py             |  93 +++++++-
 tests/domain/test_market_context.py                |  48 +++-
 tests/domain/test_market_context_builder.py        |  11 +-
 tests/domain/test_momentum_selection_scanner.py    |   3 +-
 tests/fixtures/test_backtest_252_fixtures.py       |  53 ++++-
 27 files changed, 1477 insertions(+), 86 deletions(-)
```

All 27 changed files map to the contract's Affected Areas (`design.md`), its tests/fixtures, or this change's own OpenSpec artifacts. No unrelated files touched.

**Known deviation: `src/invest/adapters/bars_fixture_json.py` restoration.**

- `main` does not contain this file (`git show main:src/invest/adapters/bars_fixture_json.py` → `fatal: path ... exists on disk, but not in 'main'`).
- The file was originally authored on commit `f0dd0de` ("feat(market-data): add --bars-out fixture export to generate-context"), which lives on the unmerged branches `feat/sharadar-actions-reconcile` and `fix/sharadar-sep-null-volume-reconcile` — **not** on `main` and **not** an ancestor of this branch's `HEAD` (`git merge-base --is-ancestor f0dd0de HEAD` → `no`).
- `feat/backtest-warmup-replay-window` branched from `main` at `8860fa6`, and commit `e5d062e` ("feat: pair generated context with warmup bars") reintroduces the file's content directly (not via merge/cherry-pick ancestry).
- **Faithfulness check**: `git diff f0dd0de..HEAD -- src/invest/adapters/bars_fixture_json.py` → empty diff (byte-identical, 112 lines). `git diff f0dd0de..HEAD -- src/invest/adapters/generate_context_cli.py` shows only a cosmetic multi-line reformatting of the same `BarsFixtureWriter().write(...)` call — functionally identical (no logic change).
- **In-scope justification**: this restoration is not incidental — it is the concrete implementation target of the `sharadar-market-context-generator` delta spec's "Pair bars output with the declared span" scenario (spec.md:41-46: "the bars fixture MAY include pre-span warmup bars governed by that span") and `tasks.md` work unit 6 ("Paired generation outputs": 6.1 RED extends `test_generate_context_cli.py` for "paired bars containing permitted pre-span warmup"; 6.2 GREEN wires "span-bearing context and paired bars in `generate_context_cli.py`"). `test_bars_out_writes_deterministic_pair_with_pre_span_warmup` (§1) directly exercises this restored code path and asserts the pre-span warmup bar is present in the paired output (`min(bar.date) == 2023-12-31` vs. `generation_span.start == 2024-01-02`).

Verdict on deviation: **faithful and in-scope**. The restoration is content-identical to its origin commit and is required by the contract itself, not an unrelated import.

---

## 7. No Pre-Span Events

Confirmed structurally and via test/runtime assertions:

- **Structural guard**: `BacktestRun._partition_bars` (`backtest_run.py:325-346`) classifies every bar as `warmup` (date `< span.start`), `replay` (`span.start <= date <= span.end`), or raises `ReplayWindowInvalidError` (date `> span.end`). `bars_by_date` (the portfolio day-loop driver, `backtest_run.py:153-155`) is built **only** from `partition.replay_bars`, and `scan_decisions` iterates only `partition.replay_dates` (`backtest_run.py:128`) — pre-span dates never enter the day-loop or the decision-collection loop, only the scanner's window construction (`window = tuple(bar for bar in partition.all_bars if bar.date <= d ...)`, line 131-135), which is the intended warmup-as-history behavior.
- **Test assertions**: `test_warmup_bars_are_scanner_visible_but_never_replay_events` — `assert min(event_dates) >= replay_start` over trade entry/exit dates, skipped-entry decision/entry dates, and context-outcome dates.
- **Fixture-scale test**: `test_backtest_252_replay_emits_no_pre_span_events` — same assertion pattern (`assert all(span.start <= day <= span.end for day in event_dates)`) against the real-shaped 252-bar fixture with actual `MomentumSelectionScanner`.
- **Runtime**: the §4 positive run (span `2020-09-09..2020-09-16`) produced a report with `context_outcomes` (potentially empty) and `trade_count`; no assertion failure or `market-context-incomplete`, consistent with all emitted events being in-span (report does not itself dump all trade dates here since `trade_count` was 0 in that run's window — the exhaustive in-span guarantee is proven by the fixture-scale test above, which does exercise non-empty events).

---

## Findings

**CRITICAL**: none.

**WARNING**: none.

**SUGGESTION** (non-blocking):
- (Addressed) `openspec/changes/backtest-warmup-replay-window/proposal.md` Success Criteria checkboxes (lines 70-74) were rendered `- [ ]` at initial verification; they are now `- [x]` (commit `5cf1023`).

## Tasks vs. Code State

All 19 items in `tasks.md` are marked `[x]`. Spot-checked against code:
- Group 1 (domain span): `market_context.py` `GenerationSpan` — present, matches 1.1-1.4.
- Group 2 (v2 JSON): `backtest_context_json.py` required `generation_span` — present, matches 2.1-2.2.
- Group 3 (replay partition): `backtest_run.py::_partition_bars` — present, matches 3.1-3.2.
- Group 4 (CLI coherence): `cli.py` split/range checks + `replay-window-invalid` — present, matches 4.1-4.2.
- Group 5 (warmup depth): `sharadar_context_source.py` `HISTORY_DAYS` import — present, matches 5.1-5.2.
- Group 6 (paired outputs): `generate_context_cli.py` + `bars_fixture_json.py` — present (see §6 deviation note), matches 6.1-6.2.
- Group 7 (scanner contract guard): `momentum_selection_scanner.HISTORY_DAYS == 253` unchanged — confirmed via `rg`.
- Group 8 (fixture regression): `fixtures/backtest-252/{bars,market-context,universe}.json` regenerated as v2, `test_backtest_252_fixtures.py` updated — present.
- Group 9 (final verification): `uv run pytest` / `uv run ruff check` — re-run independently in §3, both green.

No task is marked complete without matching code/tests.

---

## Review Correction Addendum (2026-07-18)

Bounded review of this change produced two CRITICAL findings, corrected in two commits:

- `91c09c9` `fix(market-data): keep context and bars outputs paired on bars-write failure` (REL-001) — `generate_context_cli.py` no longer leaves an unpaired context artifact on disk when the `--bars-out` write fails; a retry with the same context path now succeeds. Tests: `test_bars_write_failure_leaves_no_orphan_context`, `test_bars_storage_failure_leaves_no_orphan_context`.
- `4e7aeda` `fix(market-data): pin XNYS calendar start to remove floating warmup boundary` (RES-001) — `sharadar_context_source.py` builds the XNYS calendar with `start="1990-01-01"` so the >=253-session warmup lookback can never underflow the calendar's floating default first session (now minus 20 years). Test: `test_xnys_calendar_start_pinned_before_sharadar_history`.

Report figures above (commit list, 27-file scope, 8 in-span replay dates / 252 pre-span warmup dates, checked proposal boxes) were refreshed to the post-correction branch state in the same pass.
