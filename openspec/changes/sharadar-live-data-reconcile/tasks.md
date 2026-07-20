# Tasks: sharadar-live-data-reconcile

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 380–590 total (production, tests, compact retained/synthetic rows, and the three delta specs); confirmed below the user-approved 600-line single-PR cap |
| 400-line budget risk | High |
| Chained PRs recommended | No |
| Suggested split | Single PR with Unit 1 → Unit 2 → Unit 3 as three independently revertable work-unit/commit boundaries |
| Delivery strategy | exception-ok |
| Chain strategy | size-exception |

```text
Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: High
```

The single-PR exception is explicitly approved up to 600 changed lines. Reuse existing helpers and keep captured payloads compact. Re-forecast after each RED slice and before its production edit. Stop apply and return for a reviewed split if the projected total reaches 600; do not overrun reactively.

## Execution Contract

- Strict TDD: each work unit runs RED → GREEN → TRIANGULATE → REFACTOR. An already-green assertion is not RED evidence; use the immediate pre-fix revision or temporarily remove premature implementation while testing, as directed by `design.md`.
- Runtime: Python 3.12 through `uv`; tests use pytest with monkeypatched HTTP or in-process CLI harnesses; lint uses Ruff.
- Delivery: one PR, three independently revertable behavioral boundaries. Apply performs no `git commit`, push, or PR operation; the parent owns lifecycle actions after apply.
- Apply progress: after each unit, update this file’s evidence block and upsert Engram topic `sdd/sharadar-live-data-reconcile/apply-progress` with commands, expected RED, GREEN result, touched paths, changed-line count, and rollback boundary. Never include credentials or raw live dumps.
- Live access is prohibited during apply. Exactly one credentialed pull may run later in verify, and only after explicit user authorization.

## Unit 1 — ACTIONS kind-specific exact zero

> **ABSORBED (do not apply as written)** — review correction REL-101/REL-102 of
> `sharadar-sep-null-volume-reconcile`: the exact-zero acceptance shipped there, kind-blind
> (`value < 0` guard), with spec coverage ("Exact zero valued actions are retained") and the
> `test_fetch_accepts_exact_zero_valued_actions` regression. Do NOT re-implement or revert it.
> The kind-specific narrowing below (reject zero splits) contradicts the merged spec and, if
> still desired, requires a fresh spec delta and its own RED evidence as a new change.

### RED

- [ ] Add a public `SharadarActionsReader.fetch()` regression in `tests/adapters/test_sharadar_actions.py` using the retained live-shaped cursor payload containing `RVPH | 2026-02-23 | dividend | 0`; assert the complete paginated event set returns, RVPH is a typed dividend with `Decimal("0")`, and valid-columns/empty-data remains malformed. Add parameterized guards proving `split`/`adrratiosplit` exact zero and negative, absent, `NaN`, and infinity values fail without partial events. Capture an intended RED (the current broad-zero implementation should fail zero-split cases). <!-- sdd-owner: implementation -->
  - Exact command: `uv run pytest tests/adapters/test_sharadar_actions.py -k "rvph or zero_dividend or zero_split or invalid_valued_action or empty_actions" -x`
  - Runtime harness: pytest; monkeypatched ACTIONS HTTP/cursor responses; no network.
  - Rollback boundary: revert only the new/modified tests in `tests/adapters/test_sharadar_actions.py`; production remains untouched.

- [ ] Record the post-RED cumulative line count and projected final total in the Unit 1 apply-progress evidence; continue only when the forecast remains below 600 changed lines. <!-- sdd-owner: implementation -->
  - Exact command: `git diff --numstat HEAD -- src/invest/adapters/sharadar_actions.py tests/adapters/test_sharadar_actions.py openspec/changes/sharadar-live-data-reconcile/specs/sharadar-actions-reference-data/spec.md | awk '{a+=$1; d+=$2} END {print a+d}'`
  - Runtime harness: local Git diff plus manual projection against the remaining Unit 2/3 task ranges.
  - Rollback boundary: evidence-only edit to `tasks.md`/Engram; no runtime behavior.

### GREEN

- [ ] Implement the minimum kind-specific valued-action validator in `src/invest/adapters/sharadar_actions.py::_rows_to_actions`: map kind first, preserve finite dividend values `>= 0`, require split values `> 0`, retain exact `Decimal("0")`, and leave empty-page, missing-column, short-row, pagination, skipped-kind, and valueless-kind behavior unchanged. <!-- sdd-owner: implementation -->
  - Exact command: `uv run pytest tests/adapters/test_sharadar_actions.py -k "rvph or zero_dividend or zero_split or invalid_valued_action or empty_actions" -x`
  - Runtime harness: pytest adapter harness; no network.
  - Rollback boundary: revert `src/invest/adapters/sharadar_actions.py` plus Unit 1 tests only; no SEP behavior is coupled.

### TRIANGULATE

- [ ] Run the complete ACTIONS and context-normalization suites to prove zero dividend retention, zero split rejection, all-or-nothing public fetch behavior, and unchanged downstream corporate-action normalization. <!-- sdd-owner: implementation -->
  - Exact command: `uv run pytest tests/adapters/test_sharadar_actions.py tests/adapters/test_sharadar_context_source.py tests/application/test_generate_market_context.py`
  - Runtime harness: pytest with synthetic/live-shaped fixtures; no network.
  - Rollback boundary: verification-only; any correction remains confined to Unit 1 paths.

### REFACTOR

- [ ] Remove duplicated test setup or validator branching introduced by Unit 1 while preserving the kind-specific contract; run focused Ruff and tests after cleanup. <!-- sdd-owner: implementation -->
  - Exact command: `uv run ruff check src/invest/adapters/sharadar_actions.py tests/adapters/test_sharadar_actions.py && uv run pytest tests/adapters/test_sharadar_actions.py`
  - Runtime harness: Ruff plus pytest.
  - Rollback boundary: revert only the Unit 1 refactor hunk; keep the preceding green implementation if cleanup regresses behavior.

- [ ] Persist Unit 1 apply-progress evidence in this file and Engram, including RED failure, GREEN/focused results, line count, touched paths, and the independent rollback boundary. <!-- sdd-owner: implementation -->
  - Exact command: `git diff --numstat HEAD -- src/invest/adapters/sharadar_actions.py tests/adapters/test_sharadar_actions.py openspec/changes/sharadar-live-data-reconcile/specs/sharadar-actions-reference-data/spec.md`
  - Runtime harness: OpenSpec edit plus `mem_save(title="SDD apply progress: sharadar-live-data-reconcile Unit 1", topic_key="sdd/sharadar-live-data-reconcile/apply-progress", type="architecture", project="invest", capture_prompt=false)`.
  - Rollback boundary: evidence records only; removing Unit 1 behavior does not require removing Unit 2/3 evidence.

**Independent work-unit/commit boundary 1:** ACTIONS source + ACTIONS tests only. Parent may form the lifecycle commit later; apply does not commit.

## Unit 2 — Context-only sparse SEP seam with strict replay preserved

### RED

- [ ] Add reader contract tests in `tests/adapters/test_sharadar_market_data.py` proving the identical real-shaped ragged payload succeeds through the named `fetch_context_observations(universe, start, end)` seam but still fails through unchanged strict `fetch_range`; assert deterministic `(symbol,date)` ordering and at least one observation per requested symbol. <!-- sdd-owner: implementation -->
  - Exact command: `uv run pytest tests/adapters/test_sharadar_market_data.py -k "context_observations or sparse or strict_range" -x`
  - Runtime harness: pytest with monkeypatched paginated SEP responses and XNYS calendar; no network.
  - Rollback boundary: revert this reader-test hunk only; strict production behavior is still unchanged.

- [ ] Add sparse-seam fail-closed tests in `tests/adapters/test_sharadar_market_data.py` for out-of-range and non-session dates, unknown symbols, duplicate `(symbol,date)` across pages/chunks, empty results, zero-row requested symbols, and representative missing/short/raw-invalid rows; require no partial `FixtureInputs`. <!-- sdd-owner: implementation -->
  - Exact command: `uv run pytest tests/adapters/test_sharadar_market_data.py -k "context_observations and (out_of_range or non_session or unknown_symbol or duplicate or empty or zero_row or malformed)" -x`
  - Runtime harness: pytest with monkeypatched HTTP pages/chunks; no network.
  - Rollback boundary: revert only these sparse-guard tests.

- [ ] Add context-source and routing tests in `tests/adapters/test_sharadar_context_source.py` and `tests/adapters/test_cli_backtest.py`: context must call `fetch_context_observations` and never strict `fetch_range`; ragged cohorts succeed when returned-date union equals expected global XNYS union; a globally absent session, duplicate merged key, or zero-row symbol fails before ACTIONS/output; direct Sharadar backtest must call strict `fetch_range` and never the context seam. <!-- sdd-owner: implementation -->
  - Exact command: `uv run pytest tests/adapters/test_sharadar_context_source.py tests/adapters/test_cli_backtest.py -k "aggregate_context or sparse or context_observations or explicit_sharadar_source" -x`
  - Runtime harness: pytest with fake SEP readers, XNYS sessions, and in-process CLI; no network.
  - Rollback boundary: revert only Unit 2 context/CLI test hunks; no source touched yet.

- [ ] Record the cumulative post-RED line count and projected total for all three units; stop before GREEN if the projection reaches 600 changed lines. <!-- sdd-owner: implementation -->
  - Exact command: `git diff --numstat HEAD -- src/invest/adapters/sharadar_market_data.py src/invest/adapters/sharadar_context_source.py tests/adapters/test_sharadar_market_data.py tests/adapters/test_sharadar_context_source.py tests/adapters/test_cli_backtest.py openspec/changes/sharadar-live-data-reconcile/specs | awk '{a+=$1; d+=$2} END {print a+d}'`
  - Runtime harness: local Git diff plus remaining Unit 3 projection.
  - Rollback boundary: evidence-only; no runtime behavior.

### GREEN

- [ ] Refactor `src/invest/adapters/sharadar_market_data.py` to expose `fetch_context_observations` over the same private transport/chunk/page/parser path as strict `fetch_range`; add common aggregate validation for requested symbols only, in-range XNYS dates, global key uniqueness, non-empty results, at least one row per requested symbol, and deterministic sorting, while retaining dense expected-date equality only in `fetch_range`. <!-- sdd-owner: implementation -->
  - Exact command: `uv run pytest tests/adapters/test_sharadar_market_data.py -k "context_observations or sparse or strict_range or coverage or duplicate or zero_row or out_of_range" -x`
  - Runtime harness: pytest adapter harness with fake HTTP/chunks and exchange calendar; no network.
  - Rollback boundary: revert Unit 2 changes in `sharadar_market_data.py` and its tests; Unit 1 remains valid.

- [ ] Change `src/invest/adapters/sharadar_context_source.py::_fetch_sep_cohorts` to call the named sparse seam, accumulate expected XNYS-session and actual returned-date unions across all cohorts, reject unequal unions and merged duplicate keys before returning bars, and preserve the no-candidate `()` path. <!-- sdd-owner: implementation -->
  - Exact command: `uv run pytest tests/adapters/test_sharadar_context_source.py -k "aggregate_context or sparse or context_observations or duplicate or zero_row" -x`
  - Runtime harness: pytest context-source harness with fake readers/calendar; no network.
  - Rollback boundary: revert only `sharadar_context_source.py` plus its Unit 2 tests; direct replay stays strict throughout.

### TRIANGULATE

- [ ] Run reader, context-source, direct-backtest routing, and observed-bar eligibility tests together, including 251 observations, 252 observations with a current bar, and missing-current-bar boundaries, to prove sparse data reaches the unchanged screen without leaking into replay. <!-- sdd-owner: implementation -->
  - Exact command: `uv run pytest tests/adapters/test_sharadar_market_data.py tests/adapters/test_sharadar_context_source.py tests/adapters/test_cli_backtest.py tests/application/test_generate_market_context.py -k "context_observations or sparse or aggregate_context or observed_bar or explicit_sharadar_source"`
  - Runtime harness: pytest; fake provider and in-process application/CLI; no network.
  - Rollback boundary: verification-only; corrections stay inside Unit 2 source/tests.

### REFACTOR

- [ ] Consolidate only duplicated SEP acquisition/finalization code introduced by Unit 2, keeping the named public seam and strict public signatures explicit; run the complete affected suites and focused Ruff after cleanup. <!-- sdd-owner: implementation -->
  - Exact command: `uv run ruff check src/invest/adapters/sharadar_market_data.py src/invest/adapters/sharadar_context_source.py tests/adapters/test_sharadar_market_data.py tests/adapters/test_sharadar_context_source.py tests/adapters/test_cli_backtest.py && uv run pytest tests/adapters/test_sharadar_market_data.py tests/adapters/test_sharadar_context_source.py tests/adapters/test_cli_backtest.py`
  - Runtime harness: Ruff plus pytest.
  - Rollback boundary: revert only Unit 2 refactor hunks; preserve the prior green seam and aggregate guard if cleanup fails.

- [ ] Persist Unit 2 apply-progress evidence in this file and the shared Engram apply-progress topic, including all RED reasons, GREEN/focused results, cumulative line count, and independent rollback paths. <!-- sdd-owner: implementation -->
  - Exact command: `git diff --numstat HEAD -- src/invest/adapters/sharadar_market_data.py src/invest/adapters/sharadar_context_source.py tests/adapters/test_sharadar_market_data.py tests/adapters/test_sharadar_context_source.py tests/adapters/test_cli_backtest.py openspec/changes/sharadar-live-data-reconcile/specs/sharadar-sep-market-data/spec.md openspec/changes/sharadar-live-data-reconcile/specs/sharadar-market-context-generator/spec.md`
  - Runtime harness: OpenSpec edit plus `mem_save(title="SDD apply progress: sharadar-live-data-reconcile Unit 2", topic_key="sdd/sharadar-live-data-reconcile/apply-progress", type="architecture", project="invest", capture_prompt=false)`.
  - Rollback boundary: evidence-only; Unit 2 can be reverted without Unit 1 or Unit 3.

**Independent work-unit/commit boundary 2:** named SEP seam, common/strict finalization, context aggregate validation, and their tests. Parent may form the lifecycle commit later; apply does not commit.

## Unit 3 — Adjusted-only OHLC envelope

> **ABSORBED (do not apply as written)** — review correction REL-101/REL-102 of
> `sharadar-sep-null-volume-reconcile`: the adjusted-only `max`/`min` re-envelope shipped there
> and is spec-bound (`sharadar-sep-market-data` requirement "Deterministic OHLC adjustment") and
> test-pinned (`test_fetch_range_keeps_adjusted_ohlc_envelope_when_high_equals_close`,
> `test_fetch_range_preserves_exact_adjusted_products_when_no_clamp_is_needed`). Do NOT
> re-implement, revert, or manufacture RED evidence for it. Only the writer/reader round-trip and
> offline integration regressions below remain candidate work under this change.

### RED

- [ ] Add compact retained/synthetic real-shaped rows to `tests/adapters/test_sharadar_market_data.py` where raw OHLC is valid but independent Decimal adjustment leaves adjusted containment off by exactly `1E-27`; assert adjusted open and exact `closeadj` are unchanged while final high/low equal `max`/`min` of all adjusted candidates. Retain explicit raw `low > high` and raw open/close-outside-envelope failures. <!-- sdd-owner: implementation -->
  - Exact command: `uv run pytest tests/adapters/test_sharadar_market_data.py -k "adjusted_envelope or decimal_drift or raw_ohlc" -x`
  - Runtime harness: pytest with compact retained/synthetic SEP payloads and Decimal arithmetic; no network.
  - Rollback boundary: revert only Unit 3 market-data tests/fixture rows; production remains untouched.

- [ ] Add a writer-reader round-trip regression in `tests/adapters/test_bars_fixture_json.py` or a focused market-data integration test that feeds the adjusted drift bars through `BarsFixtureWriter` and `JsonFixtureReader`; also add/reuse an offline in-process generate-context → bars fixture → fixture backtest regression in `tests/adapters/test_generate_context_cli.py` using sparse real-shaped data and no HTTP. <!-- sdd-owner: implementation -->
  - Exact command: `uv run pytest tests/adapters/test_bars_fixture_json.py tests/adapters/test_generate_context_cli.py tests/adapters/test_cli_backtest.py -k "adjusted_envelope or decimal_drift or real_shaped_sparse_context_export" -x`
  - Runtime harness: pytest `tmp_path`, monkeypatched context source, `BarsFixtureWriter`, `JsonFixtureReader`, and in-process CLI; no network.
  - Rollback boundary: revert only the Unit 3 round-trip/offline integration tests and compact fixture data.

- [ ] Record the final post-RED forecast before production editing; continue as one PR only if the total remains below 600 changed lines. <!-- sdd-owner: implementation -->
  - Exact command: `git diff --numstat HEAD -- src/invest/adapters tests/adapters openspec/changes/sharadar-live-data-reconcile/specs | awk '{a+=$1; d+=$2} END {print a+d}'`
  - Runtime harness: local Git diff and final implementation projection.
  - Rollback boundary: evidence-only; if at/over 600, stop and hand the preferred Unit 2 split to the parent.

### GREEN

- [ ] In `src/invest/adapters/sharadar_market_data.py::_rows_to_bars`, keep raw `_SepRow` validation first, compute adjusted open/high/low and exact close, then set output high to `max(all four)` and low to `min(all four)` without epsilon, quantization, float conversion, row dropping, or changes to open/close. <!-- sdd-owner: implementation -->
  - Exact command: `uv run pytest tests/adapters/test_sharadar_market_data.py tests/adapters/test_bars_fixture_json.py -k "adjusted_envelope or decimal_drift or raw_ohlc" -x`
  - Runtime harness: pytest with exact Decimal and filesystem round-trip harnesses; no network.
  - Rollback boundary: revert only the adjusted-envelope hunk and Unit 3 tests; discard/regenerate derived bars outputs.

### TRIANGULATE

- [ ] Run all market-data, fixture writer/reader, generate-context CLI, and fixture-backtest tests to confirm raw malformed OHLC still fails, valid unadjusted bars remain exact, sparse bars serialize, and exported bars replay offline. <!-- sdd-owner: implementation -->
  - Exact command: `uv run pytest tests/adapters/test_sharadar_market_data.py tests/adapters/test_bars_fixture_json.py tests/adapters/test_generate_context_cli.py tests/adapters/test_cli_backtest.py`
  - Runtime harness: pytest adapter/in-process CLI/filesystem harness; no network.
  - Rollback boundary: verification-only; corrections stay within Unit 3 paths unless a Unit 2 contract regression is exposed.

### REFACTOR

- [ ] Remove duplicate adjusted-candidate calculations or oversized captured rows while retaining exact assertions and the raw-validation-before-adjustment order; run focused Ruff and tests. <!-- sdd-owner: implementation -->
  - Exact command: `uv run ruff check src/invest/adapters/sharadar_market_data.py tests/adapters/test_sharadar_market_data.py tests/adapters/test_bars_fixture_json.py tests/adapters/test_generate_context_cli.py && uv run pytest tests/adapters/test_sharadar_market_data.py tests/adapters/test_bars_fixture_json.py -k "adjusted_envelope or decimal_drift or raw_ohlc"`
  - Runtime harness: Ruff plus pytest.
  - Rollback boundary: revert only Unit 3 refactor hunks; preserve the preceding green min/max implementation if cleanup fails.

- [ ] Persist Unit 3 apply-progress evidence in this file and Engram, including RED/GREEN/round-trip results, final changed-line count, affected files, and the derived-output rollback note. <!-- sdd-owner: implementation -->
  - Exact command: `git diff --numstat HEAD -- src/invest/adapters/sharadar_market_data.py tests/adapters/test_sharadar_market_data.py tests/adapters/test_bars_fixture_json.py tests/adapters/test_generate_context_cli.py openspec/changes/sharadar-live-data-reconcile/specs/sharadar-sep-market-data/spec.md`
  - Runtime harness: OpenSpec edit plus `mem_save(title="SDD apply progress: sharadar-live-data-reconcile Unit 3", topic_key="sdd/sharadar-live-data-reconcile/apply-progress", type="architecture", project="invest", capture_prompt=false)`.
  - Rollback boundary: evidence-only; Unit 3 can be reverted independently and generated bars regenerated.

**Independent work-unit/commit boundary 3:** adjusted-only envelope plus writer-reader/offline regression tests. Parent may form the lifecycle commit later; apply does not commit.

## Integration verification (apply-owned, offline only)

- [ ] Run the targeted cross-unit adapter/application suites as the first integration gate. <!-- sdd-owner: implementation -->
  - Exact command: `uv run pytest tests/adapters/test_sharadar_actions.py tests/adapters/test_sharadar_market_data.py tests/adapters/test_sharadar_context_source.py tests/adapters/test_cli_backtest.py tests/adapters/test_bars_fixture_json.py tests/adapters/test_generate_context_cli.py tests/application/test_generate_market_context.py`
  - Runtime harness: pytest; all provider access mocked or synthetic.
  - Rollback boundary: verification-only; route failures to the owning Unit 1/2/3 boundary.

- [ ] Run the complete repository test suite and record its exit status in OpenSpec/Engram apply-progress. <!-- sdd-owner: implementation -->
  - Exact command: `uv run pytest`
  - Runtime harness: full pytest suite; do not enable credentialed live/paper markers.
  - Rollback boundary: verification-only; no broad opportunistic fixes outside this change.

- [ ] Run repository-wide lint and record its exit status in OpenSpec/Engram apply-progress. <!-- sdd-owner: implementation -->
  - Exact command: `uv run ruff check .`
  - Runtime harness: Ruff from the repository root.
  - Rollback boundary: verification-only; lint fixes stay in their owning unit.

- [ ] Re-run the offline real-shaped generate-context → fixture write/read → fixture backtest regression and confirm no network client is called. <!-- sdd-owner: implementation -->
  - Exact command: `uv run pytest tests/adapters/test_generate_context_cli.py tests/adapters/test_bars_fixture_json.py tests/adapters/test_cli_backtest.py -k "real_shaped_sparse_context_export or adjusted_envelope or round_trip or backtest_bars_run"`
  - Runtime harness: pytest `tmp_path`, monkeypatched context source/HTTP, `BarsFixtureWriter`, `JsonFixtureReader`, and fixture-mode `backtest_main`; retained compact rows or equivalent synthetic real-shaped data.
  - Rollback boundary: verification-only; temporary files are pytest-owned and removed automatically.

## Post-apply lifecycle and verify (parent-owned)

- [ ] Start or reuse bounded review for the single PR, verify the three independent work-unit boundaries and final `<600` changed-line count, and keep commit/push/PR mechanics outside apply. <!-- sdd-owner: parent -->
  - Exact command: `git diff --numstat HEAD | awk '{a+=$1; d+=$2} END {print a+d}'`
  - Runtime harness: parent lifecycle/review harness after apply evidence is complete.
  - Rollback boundary: review-only; request corrections against the owning unit rather than coupling reversions.

- [ ] In `sdd-verify` only, after explicit user authorization, perform exactly one credentialed live context pull with bars export, then load the exported fixture offline; do not run any live pull during apply and do not repeat the pull without renewed authorization. <!-- sdd-owner: parent -->
  - Exact command: `test ! -e /tmp/sharadar-live-data-reconcile-context.json && test ! -e /tmp/sharadar-live-data-reconcile-bars && NASDAQ_DATA_LINK_API_KEY="$NASDAQ_DATA_LINK_API_KEY" uv run invest-generate-context --start 2025-07-17 --end 2026-07-16 --out /tmp/sharadar-live-data-reconcile-context.json --bars-out /tmp/sharadar-live-data-reconcile-bars && uv run python -c 'from pathlib import Path; from invest.adapters.fixtures_json import JsonFixtureReader; p=Path("/tmp/sharadar-live-data-reconcile-bars"); JsonFixtureReader().load(p / "universe.json", p / "bars.json")'`
  - Runtime harness: one user-authorized Nasdaq Data Link pull in verify, followed by an offline `JsonFixtureReader` check; never log the API key.
  - Rollback boundary: read-only provider interaction; delete `/tmp/sharadar-live-data-reconcile-context.json` and `/tmp/sharadar-live-data-reconcile-bars` after evidence capture, and record any newly surfaced blocker as a separate change.

## Apply Progress Evidence

Update during apply; do not pre-check tasks or claim runs not performed.

| Unit | RED evidence | GREEN / focused suite | Changed lines / forecast | Engram apply-progress |
|---|---|---|---|---|
| Unit 1 — ACTIONS | Pending | Pending | Pending; must remain `<600` projected | Pending |
| Unit 2 — sparse context seam | Pending | Pending | Pending; must remain `<600` projected | Pending |
| Unit 3 — adjusted OHLC | Pending | Pending | Pending; final total must be `<600` | Pending |
| Offline integration | N/A | Pending targeted/full/lint/offline results | Pending final total | Pending |
