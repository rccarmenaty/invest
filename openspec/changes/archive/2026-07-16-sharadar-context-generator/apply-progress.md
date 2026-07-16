# Apply Progress: Sharadar Market Context Generator

**Slice**: 1 (complete) + 2 (complete) + 3 (complete) — tasks 1.1–1.4, 2.1–2.6, 3.1–3.4
**Mode**: Strict TDD
**Date**: 2026-07-16

## Native Review Correction Batch (Slice 1 — historical)

| Field | Value |
|---|---|
| Lineage | `review-2631b69c26c2de8f` (escalated — DO NOT reuse) |
| Review state | corrected, then superseded by later approved lineage |
| Note | Slice 1 is review-approved under `review-e75eb3a6896d05b5`. Domain modules were not modified in Slice 2 or Slice 3. |

## Completed Tasks

### Slice 1 — Pure domain

- [x] 1.1 RED `tests/domain/test_liquidity_screen.py`
- [x] 1.2 GREEN `src/invest/domain/liquidity_screen.py`
- [x] 1.3 RED `tests/domain/test_market_context_builder.py`
- [x] 1.4 GREEN `src/invest/domain/market_context_builder.py`

### Slice 2 — Source, application, writer

- [x] 2.1 RED `tests/application/test_generate_market_context.py` — 9 tests: immutable inputs, happy path, orphan bars/actions → `reference-data-incomplete`, empty sessions, raw Sharadar rejection, corporate-action blocker, valueless action.
- [x] 2.2 GREEN `src/invest/application/generate_market_context.py` — `GeneratorInputs`, `NormalizedListing`, `NormalizedAction`, `ReferenceDataIncompleteError`, `GenerateMarketContext.run`; REFACTOR preserves adapter → application → domain.
- [x] 2.3 RED `tests/adapters/test_sharadar_context_source.py` — 10 tests: primary/listing reuse, ticker conflict, identical coalesce, preceding XNYS, cohort batching, one ACTIONS fetch, blank/exhausted pagination, missing listed_date, delisting clip.
- [x] 2.4 GREEN `src/invest/adapters/sharadar_context_source.py` — sole TICKERS/ACTIONS importer; reuses SEP `fetch_range`; cohort normalization by clipped listing/history window.
- [x] 2.5 RED extend `tests/adapters/test_backtest_context_json.py` — 7 new writer tests: canonical newline, reader round-trip, existing-target refusal, temp cleanup, empty invalid, atomic no-replace race, determinism.
- [x] 2.6 GREEN `BacktestContextJsonWriter` in `src/invest/adapters/backtest_context_json.py` — temp+fsync+reader-validate+`os.link` exclusive create; reader behavior unchanged.

### Slice 3 — CLI and boundary

- [x] 3.1 RED `tests/adapters/test_generate_context_cli.py` — success silent 0; invalid dates/floors/NaN/seasoning; existing out / missing parent; incomplete + reader reason one-line JSON; no replay/broker/scanner imports; Core defaults; banned flags absent.
- [x] 3.2 GREEN `src/invest/adapters/generate_context_cli.py` + `invest-generate-context` console script; orchestration-only; REFACTOR merged validation helpers.
- [x] 3.3 RED extend `tests/test_boundaries.py` — allowlist exactly context source; protected CLI/domain/backtest deny; consumers unchanged.
- [x] 3.4 GREEN one-path allowlist; default-deny retained; README generation/replay separation.

## TDD Cycle Evidence

### Slice 1 (original + correction) — preserved from prior apply-progress

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1/1.2 | `tests/domain/test_liquidity_screen.py` | Unit | N/A (new) | ✅ Written | ✅ 17→23 passed | ✅ multi-path | ✅ helpers |
| 1.3/1.4 | `tests/domain/test_market_context_builder.py` | Unit | N/A (new) | ✅ Written | ✅ 12→17 passed | ✅ multi-path | ✅ helpers |
| Corr #1–#3 | domain tests | Unit | ✅ | ✅ | ✅ | ✅ | ✅ |

### Slice 2

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 2.1/2.2 | `tests/application/test_generate_market_context.py` | Unit | N/A (new) | ✅ 8–9 failed (ModuleNotFound) | ✅ 9 passed | ✅ orphan bars+actions, raw ticker+action, valueless action, blocker | ✅ orphan detection isolated in `_to_symbol_data` |
| 2.3/2.4 | `tests/adapters/test_sharadar_context_source.py` | Adapter | N/A (new) | ✅ 10 failed (ModuleNotFound) | ✅ 10 passed | ✅ conflict vs coalesce, blank vs exhausted pagination, delisting clip, multi-cohort | ✅ `_cohort_window` / `_normalize_candidates` / `_fetch_actions` extracted |
| 2.5/2.6 | `tests/adapters/test_backtest_context_json.py` | Adapter | ✅ 8/8 reader | ✅ 7 failed (ImportError) | ✅ 15 passed (8+7) | ✅ empty invalid, race no-replace, determinism, round-trip | ✅ `_to_payload` / `_write_temp`; reader untouched |

### Slice 3

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 3.1/3.2 | `tests/adapters/test_generate_context_cli.py` | CLI | ✅ S2 suite 36/36 | ✅ 12 failed (ModuleNotFound) | ✅ 11 passed (parametrized) | ✅ date/floor/NaN/seasoning, exists/missing parent, incomplete vs reader reason, banned flags | ✅ `_validate` merged; lean CLI |
| 3.3/3.4 | `tests/test_boundaries.py` | Architecture | ✅ isolation RED (source not allowlisted) | ✅ allowlist assertion + protected/deny | ✅ one-path allowlist + README | ✅ protect CLI/domain/backtest; consumers importable | ➖ None needed |

## Work Unit Evidence (Slice 2)

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `.venv/bin/python -m pytest tests/application/test_generate_market_context.py tests/adapters/test_sharadar_context_source.py tests/adapters/test_backtest_context_json.py` → **34 passed** in 0.81s |
| Runtime harness command/scenario and exact result | MockTransport TICKERS+SEP+ACTIONS → `SharadarContextSource.load` → `GenerateMarketContext.run` → `BacktestContextJsonWriter.write` → `BacktestContextJsonReader.load`; ACME eligible with corporate-action on 2024-01-09 → **OK** |
| Rollback boundary | Delete `src/invest/application/generate_market_context.py`, `src/invest/adapters/sharadar_context_source.py`, `tests/application/test_generate_market_context.py`, `tests/adapters/test_sharadar_context_source.py`; revert writer additions in `backtest_context_json.py` and writer tests in `test_backtest_context_json.py`. Domain Slice 1 files untouched. |

## Work Unit Evidence (Slice 3)

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `.venv/bin/python -m pytest tests/adapters/test_generate_context_cli.py tests/test_boundaries.py` → **30 passed** |
| Runtime harness command/scenario and exact result | Fake `SharadarContextSource` → `generate_context_cli.main(--start/--end/--out + screen flags)` → silent exit 0 + reader-valid `market-context-v1` file; failure paths emit one sorted JSON line, empty stderr, no partial file → **OK** |
| Rollback boundary | Delete `src/invest/adapters/generate_context_cli.py`, `tests/adapters/test_generate_context_cli.py`; revert `pyproject.toml` script entry, `tests/test_boundaries.py` allowlist/protected tests, and README market-context section. Slice 1–2 files untouched. |
| Lint | `.venv/bin/python -m ruff check src/invest/adapters/generate_context_cli.py tests/adapters/test_generate_context_cli.py tests/test_boundaries.py` → All checks passed |
| Changed lines (Slice 3 only) | **391** authored (CLI 118 + CLI tests 192 + boundaries +65 net + README 15 + pyproject 1); under 400 budget; no size:exception |

## Test Summary

- **Slice 2 tests written**: 26 (9 application + 10 source + 7 writer)
- **Slice 2 tests passing**: 26
- **Slice 3 tests written**: 11 CLI functions (parametrized) + boundary allowlist/protected extensions
- **Focused suite (S1+S2+S3)**: 106 passed
- **Layers used**: Unit, Adapter/Integration, CLI, Architecture
- **Approval tests**: None new
- **Pure functions / deep modules**: CLI `_validate`; allowlist remains default-deny with one explicit path

## Files Changed (Slice 3)

| File | Action | Lines | What Was Done |
|------|--------|-------|---------------|
| `src/invest/adapters/generate_context_cli.py` | Created | 118 | Standalone orchestration CLI |
| `tests/adapters/test_generate_context_cli.py` | Created | 192 | CLI TDD coverage |
| `tests/test_boundaries.py` | Modified | +55/−10 | One-path allowlist + protected deny |
| `pyproject.toml` | Modified | +1 | `invest-generate-context` script |
| `README.md` | Modified | +15 | Generation vs replay docs |
| `openspec/changes/sharadar-context-generator/tasks.md` | Modified | — | Tasks 3.1–3.4 marked `[x]` |

**Authored line estimate (Slice 3)**: 391 (under 400 review budget).

## Deviations from Design

None material — implementation matches design:
- Required `--start`/`--end`/`--out`; Core optional screen flags; no source/replay/universe/overwrite/AUM/ADV/impact flags.
- Success exit 0 silent; failure exit 2 one sorted JSON reason on stdout.
- Allowlist exactly `sharadar_context_source.py`; CLI imports source not readers.
- Pre-listing SEP clip from Slice 2 correction preserved (not modified in Slice 3).

## Issues Found

- **Argparse SystemExit**: invalid CLI type/parse errors are mapped to `invalid-arguments` via SystemExit catch; help (`code==0`) still returns 0.
- **Review budget**: Slice 3 kept to 391 authored lines by compressing CLI tests (parametrized invalid-arg matrix) after first draft exceeded 600.

## Remaining Tasks

None — all 14 tasks complete (1.1–3.4).

## Workload / PR Boundary

- Mode: chained PR slice (feature-branch-chain; PR3 → PR2)
- Current work unit: Slice 3 — CLI and boundary
- Boundary: Starts from Slice 2 source/app/writer; ends with `generate_context_cli`, console script, one-path allowlist, README. No domain/source/writer behavior changes.
- Estimated review budget impact: 391 authored lines (under 400)

## Native Review Correction Batch (Slice 2 — lineage review-e7c1191a58adead7)

| Field | Value |
|---|---|
| Lineage | `review-e7c1191a58adead7` |
| Generation | 1 |
| State at correction | `correction_required` (Slice 2 approved after correction; do not reuse for Slice 3) |
| Correction budget | 200 (accepted forecast 150) |
| Frozen criterion only | Pre-listing SEP absence for listing-inside-range must not abort as incomplete/malformed; yield insufficient-history / ineligible pre-seasoning outcome |
| Explicit exclusions | Residual broad-range quadratic prefix re-filtering (R2-002); no CLI/allowlist; no commit/PR/review start |

### Fix

- Clip SEP cohort `fetch_start` to `listing.listing_date` in `SharadarContextSource._cohort_window` so lookback never requests pre-listing sessions.
- Reused `SharadarMarketDataReader.fetch_range` left unchanged; domain/application untouched.
- Slice 3 did not modify this path.

### TDD Cycle Evidence (correction)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| Corr pre-listing SEP | `tests/adapters/test_sharadar_context_source.py` | Adapter | ✅ 10/10 | ✅ 2 failed (`incomplete date coverage`) | ✅ 12 passed | ✅ load-only + GenerateMarketContext ineligible→eligible | ➖ None needed (one-line clip + comment) |

### Work Unit Evidence (correction)

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `.venv/bin/python -m pytest tests/adapters/test_sharadar_context_source.py tests/application/test_generate_market_context.py` → **21 passed** |
| Runtime harness command/scenario and exact result | MockTransport TICKERS+SEP(no pre-listing rows)+ACTIONS → `SharadarContextSource.load` → `GenerateMarketContext.run`; NEW listed mid-range: first two post-listing sessions ineligible, third eligible → **OK** |
| Rollback boundary | Revert `_cohort_window` clip in `src/invest/adapters/sharadar_context_source.py` and the two new tests in `tests/adapters/test_sharadar_context_source.py` |
| Lint | `.venv/bin/python -m ruff check src/invest/adapters/sharadar_context_source.py tests/adapters/test_sharadar_context_source.py` → All checks passed |
| Changed lines | ~95 (prod +4, tests ~91); under accepted 150 forecast / 200 budget |
| Criterion scope | Only frozen pre-listing criterion corrected; R2-002 quadratic warning not addressed |

## Native Review Correction Batch (ordinary review — lineage review-481934bcc7e6c5a2)

| Field | Value |
|---|---|
| Lineage | `review-481934bcc7e6c5a2` |
| Generation | 1 |
| State at correction | `correction_required` |
| Correction budget | 200 (accepted forecast 120) |
| Fix finding | `R4-001` (corroborated deterministic) |
| Frozen criterion only | Preserve full-session coverage for a valid listing that is ineligible on every requested session so replay `require_complete` treats it as ineligible instead of `MarketContextIncompleteError` |
| Explicit exclusions | CLI stderr/invalid-Decimal warnings; quadratic prefix-filter warning; source/CLI/writer/README/boundaries/requirements |

### Fix

- Removed the all-false eligibility skip in `build_market_context` so every valid input listing receives full coverage + RLE eligibility windows (`eligible=False` when never eligible).
- Domain tests now assert inclusion, full ineligible coverage, `require_complete` success, and `SYMBOL_INELIGIBLE` status for all-ineligible listings.
- No source, CLI, writer, README, boundary, or requirements changes.

### TDD Cycle Evidence (correction)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| Corr R4-001 all-ineligible coverage | `tests/domain/test_market_context_builder.py` | Unit | ✅ 17/17 | ✅ 2 failed (`BETA`/`THIN` omitted) | ✅ 18 passed | ✅ mixed eligible+never + only-never listing | ➖ None needed (skip removal + docs) |

### Work Unit Evidence (correction)

| Evidence | Required value |
|---|---|
| Focused test command and exact result | `.venv/bin/python -m pytest tests/domain/test_market_context_builder.py tests/application/test_generate_market_context.py` → **27 passed** |
| Runtime harness command/scenario and exact result | Domain builder → `MarketContext.require_complete` / `status` for all-ineligible listing across sessions → ineligible with `SYMBOL_INELIGIBLE`, no incomplete abort → **OK** (N/A separate integration harness: unchanged replay contracts exercised via `require_complete`) |
| Rollback boundary | Revert `src/invest/domain/market_context_builder.py` skip-removal/docstrings and the two all-ineligible tests in `tests/domain/test_market_context_builder.py` |
| Lint | `.venv/bin/python -m ruff check src/invest/domain/market_context_builder.py tests/domain/test_market_context_builder.py` → All checks passed |
| Changed lines | ~80 authored add+del (prod ~16, tests ~64); under accepted 120 forecast / 200 budget |
| Criterion scope | Only frozen R4-001 all-ineligible coverage criterion corrected |
