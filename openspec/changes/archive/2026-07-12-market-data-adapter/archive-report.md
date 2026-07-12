# Archive Report: market-data-adapter

**Date**: 2026-07-12  
**Change**: market-data-adapter (Alpaca Daily Bars)  
**Status**: ARCHIVED  
**Artifact Store Mode**: Hybrid (openspec + Engram)

## Executive Summary

The `market-data-adapter` change—a read-only Alpaca daily-bars adapter with fetch-to-fixture snapshot semantics, fail-closed symbol validation, feed authority, credential handling, deterministic as-of date processing, fetch error taxonomy, and snapshot/scan-time rejection boundaries—has been fully implemented, verified (PASS: 8/8 requirements, 20/20 scenarios, 66 tests + 1 expected skip, ruff clean), reviewed, and archived.

## Change Scope

**Objective**: Replace hand-authored fixture bars with real Alpaca daily-bar data while preserving the deterministic, replayable, fail-closed pipeline. Adapter fetches split-adjusted daily bars, snapshots them into the existing fixture JSON schema, and hands off to the unchanged `JsonFixtureReader -> ScanRun -> MomentumScanner` pipeline.

**Delivery**:
- PR #7: Port + Alpaca client + error taxonomy (raw `httpx`, Pydantic validation, bounded retry, error mapping)
- PR #8: Snapshot writer + provenance + `invest-fetch` CLI (atomic snapshot publication, `--as-of` required, `--feed sip|iex` opt-in)
- PR #9: Review corrections (universe file edge validation, snapshot-exists/storage-failure handling, pagination cap)

**Implementation Executor**: Codex (gpt-5.6-sol) under orchestrator gates.

## Specs Synced

| Domain | Action | Details |
|--------|--------|---------|
| trading-system | Updated | Appended 8 ADDED requirements from delta spec to main spec |

**Delta Spec Requirements** (all ADDED):
1. Market data fetch port and adapter boundary
2. Fetch-to-fixture snapshot semantics
3. Fail-closed snapshot on missing universe symbols
4. Feed authority and degraded-data opt-in
5. Alpaca credential handling
6. Deterministic as-of date handling
7. Fetch error taxonomy (8 scenarios covering auth, network, rate-limit, malformed, pagination, snapshot-exists, storage, fixture-invalid)
8. Snapshot-time and scan-time rejection boundary

**Merged Into**: `openspec/specs/trading-system/spec.md` (main spec now contains all 8 requirements + 20 scenarios)

## Archive Contents

**Archived to**: `openspec/changes/archive/2026-07-12-market-data-adapter/`

### Artifacts Present

- ✅ `proposal.md` — Intent, scope, design positions, capabilities, approach, risks, rollback plan
- ✅ `exploration.md` — Current state, affected areas, approaches evaluated, recommendation
- ✅ `design.md` — Technical approach, architecture decisions (separate CLI, one module two classes, required `--as-of`, split-adjusted, fail-closed symbol gaps), data flow, interfaces, error taxonomy
- ✅ `tasks.md` — 21/21 tasks checked; review workload forecast; 5 work units across 2 PRs
- ✅ `verify-report.md` — PASS verdict; 8/8 requirements, 20/20 scenarios passing; 66 passed, 1 skipped; ruff clean; task completion verified; harness probes confirmed
- ✅ `specs/trading-system/spec.md` — Delta spec (8 ADDED requirements, 20 scenarios, no MODIFIED/REMOVED)
- ✅ `reviews/policy.md` — Review policy; high-tier risk classification (> 400 lines); full 4R review scope
- ✅ `reviews/ledger.json` — 7 findings (all `status: info`); 3 RESOLVED in PR #9 (MREL-001 BLOCKER, MREL-002/MRES-001/MRES-002 CRITICAL); 4 open follow-ups (TMDA-005 staging-dir cleanup, TMDA-006 OHLC validator duplication, TMDA-007 inline imports)
- ✅ `reviews/receipt.json` — Terminal receipt; `lineage_id: market-data-adapter-clean`; `mode: ordinary_4r`; `terminal_state: approved`; counters: 1 full review, 1 final verification, 0 fix rounds/refuter batches
- ✅ `reviews/transaction.json` — Transaction record; 7 findings with outcomes (all `info`); paths digest and identity hashes
- ✅ `reviews/gate-context.json` — Post-apply gate context; policy/ledger/evidence artifact paths

### Task Completion

All 21 implementation tasks marked `[x]`:
- Phase 1 (Port + Client Happy Path): 4/4 tasks
- Phase 2 (Error Taxonomy + Retry): 5/5 tasks
- Phase 3 (Snapshot Writer + Provenance): 7/7 tasks
- Phase 4 (CLI + Packaging): 2/2 tasks
- Phase 5 (Boundary + Live/Calendar Coverage): 3/3 tasks

No unchecked implementation tasks. Spot-checked against code and tests: MarketDataReader port present, SPEC reason strings used correctly (not design's draft names), snapshot path at `fixtures/snapshots/{as-of}/` confirmed, `invest-fetch` CLI + `httpx` dependency in place, boundary tests extended, live/calendar tests present.

## Review Lineages

### Primary Lineage: market-data-adapter

**State**: Completed with scope change (terminal lineage: market-data-adapter-clean)

**Full 4R Sweeps** (genesis at commit 0d3b2b8):
- 12 findings discovered during review
- 1 BLOCKER (MREL-001: universe file failures)
- 3 CRITICAL (MREL-002: snapshot dir collision, MREL-003: argparse contract scope—reclassified info, MRES-001: OSError during write)
- 5 readability + reliability findings

**Correction** (PR #9, commit e78c933):
- Resolved MREL-001 BLOCKER via edge validation before network
- Resolved MREL-002 CRITICAL via snapshot-exists mapping + staged cleanup
- Resolved MRES-001 CRITICAL via storage-failure mapping + OSError handling
- Reclassified MREL-003 info (argparse contract out of spec scope)
- Pagination cap (MAX_PAGES=64) → malformed-response mapping resolves MRISK-001/MRISK-002

### Terminal Lineage: market-data-adapter-clean

**State**: approved (post-apply scope-change lineage)

**Ledger** (7 entries, all `status: info`):
- TMDA-001 (RESOLVED): fixture-invalid classification (formerly MREL-001 BLOCKER)
- TMDA-002 (RESOLVED): snapshot-exists / storage-failure handling (formerly MREL-002/MRES-001 CRITICAL)
- TMDA-003 (RESOLVED): pagination cap (formerly MRISK-001/MRISK-002)
- TMDA-004 (info): argparse stance documented and accepted
- TMDA-005 (OPEN WARNING): orphaned staging directories on SIGKILL/power-loss (no startup sweep)
- TMDA-006 (OPEN WARNING): OHLC validator duplication across adapters (code quality, no spec impact)
- TMDA-007 (OPEN SUGGESTION): inline `__import__` idiom in test file (cosmetic)

**Terminal Receipt**: `mode: ordinary_4r`, `generation: 1`, `terminal_state: approved`; counters show 1 full review, 1 final verification, zero fix/refuter batches

## Verification Summary

**Verdict**: PASS (per `openspec/changes/market-data-adapter/verify-report.md`)

**Evidence**:
- 8/8 requirements covered by passing tests
- 20/20 scenarios covered by passing tests
- All 21 tasks match code inspection
- 66 tests passed, 1 skipped (env-gated live smoke test—expected)
- Ruff lint clean (exit 0)
- No BLOCKER/CRITICAL findings in terminal ledger
- Three harness probes confirm spec compliance
- TDD compliance: 4/6 checks verified, 2 N/A due to missing apply-progress (accepted per orchestrator instruction)

**Test Suite**: `uv run --extra dev pytest` → 66 passed, 1 skipped, exit 0  
**Lint Check**: `uv run --extra dev ruff check .` → All checks passed, exit 0

## Deviations Documented

| Deviation | Level | Resolution |
|-----------|-------|-----------|
| Snapshot path `fixtures/snapshots/{as-of}/` vs proposal's `fixtures/{as_of_date}/` | WARNING | Does not violate spec; spec does not mandate path, only that JsonFixtureReader loads unchanged. Documented in tasks.md 3.4. |
| SPEC reason strings (`auth-failure`, etc.) vs design draft shorter names (`auth`, etc.) | INFO | Correct choice—implementation followed SPEC over design draft. Task 2.2 explicitly documents this deviation. |
| Argparse usage error behavior (MREL-003/TMDA-004) | INFO | Documented and accepted—spec contract scopes machine-readable records to fetch-taxonomy failures, not argparse internal errors. |
| Missing apply-progress.md artifact | INFO | Accepted per orchestrator instruction; evidence substituted by tasks.md checkboxes + PR history + live verification. |

## Open Follow-Ups (Non-Blocking)

Logged in ledger as follow-up items, not required for this slice:

- **TMDA-005** (WARNING): Orphaned staging directories after SIGKILL/power-loss between mkdtemp and rename have no startup sweep. Does not affect any spec scenario (no crash-recovery requirement). Correctly deferred.
- **TMDA-006** (WARNING): OHLC price-relationship validator duplicated across `alpaca_market_data.py` and `fixtures_json.py`. Code quality only, no spec impact. Tracked for later shared-rule consolidation.
- **TMDA-007** (SUGGESTION): Inline `__import__("datetime")` in test module instead of top-level import. Cosmetic; recommend test module import style cleanup.

## Source of Truth Updated

All 8 ADDED requirements and 20 scenarios from delta spec now merged into:
- `openspec/specs/trading-system/spec.md` (main spec, source of truth)

The main spec now contains the complete, integrated trading-system specification including all market-data-adapter requirements. Future changes targeting the trading-system domain will build on this merged specification.

## SDD Cycle Complete

The `market-data-adapter` change has been:
1. ✅ Proposed (proposal.md)
2. ✅ Explored (exploration.md)
3. ✅ Designed (design.md)
4. ✅ Tasked (tasks.md, 21/21 checked)
5. ✅ Implemented and Delivered (3 PRs: #7, #8, #9)
6. ✅ Reviewed (full 4R, terminal approved receipt)
7. ✅ Verified (PASS: 8/8 requirements, 20/20 scenarios, 66 tests + 1 skip, ruff clean)
8. ✅ Archived (this report)

The change is ready for release; no pending blockers or critical findings. Two non-blocking warning-level follow-ups and one cosmetic suggestion remain open as documented in the ledger.

## Observation IDs (Engram Traceability)

Archived to Engram topic: `sdd/market-data-adapter/archive-report`

No prior Engram observations found for proposal/spec/design/tasks/verify-report in this hybrid-mode session (filesystem artifacts remain source of truth). All review artifacts stored in openspec/changes/archive/2026-07-12-market-data-adapter/reviews/ for full traceability.

---

**Archived**: 2026-07-12 by sdd-archive executor  
**Mode**: Hybrid (openspec filesystem + Engram persistence)  
**Artifact Integrity**: Files copied to archive location; original `openspec/changes/market-data-adapter/` retained pending manual deletion verification
