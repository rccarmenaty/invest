# Archive Report: backtest-warmup-replay-window

## Scope

Adds an authoritative generation span to the backtest context, partitions bars into warmup/replay cohorts by that span, and validates that all in-window symbols are complete before replay. Extends the warmup fetch to >=253 trading sessions matching the scanner's required history depth, partitions the replay loop to emit no pre-span events, and enforces split-date validation against in-window replay dates only (never warmup or post-span bars).

Three core OpenSpec specs merged:
- `point-in-time-market-context`: added `GenerationSpan` as an authoritative immutable property of `MarketContext`
- `sharadar-market-context-generator`: added 253-session warmup fetch sharing `MomentumSelectionScanner.HISTORY_DAYS`, versioned context schema to `market-context-v2` with required top-level span
- `trading-system`: added bar partitioning (warmup/replay), context completeness gates, and split-date validation scoped to in-window dates

## Delivery

- Single PR slice (no chaining): PR #55 merged 2026-07-18, 7 commits (e00f040, d0db49b, e5d062e, f15f875, 5cf1023, 91c09c9, 4e7aeda)
- 27 files changed, 1477 insertions(+), 86 deletions(-), high review-budget risk (forecast 500–700 lines; user elected single-pr delivery)
- Strict TDD throughout: 9 focused work units covering domain span, v2 JSON, replay partition, CLI coherence, warmup depth, paired outputs, scanner contract guard, fixture regression, and final verification. All 19 tasks marked complete. Deterministic fixtures (backtest-252) regenerated with v2 span and byte-identical verification runs.

## Review

Lineage `backtest-warmup-replay-window-main-merge`: full 4R sweep (high tier due to 1477 changed lines + security/architecture implications) produced 2 CRITICAL findings, both corrected in-branch before merge:
- `91c09c9` (`fix(market-data): keep context and bars outputs paired on bars-write failure`): orphan-context cleanup on paired-output write failure; `test_bars_write_failure_leaves_no_orphan_context`, `test_bars_storage_failure_leaves_no_orphan_context` verify recovery.
- `4e7aeda` (`fix(market-data): pin XNYS calendar start to remove floating warmup boundary`): calendar start fixed to 1990-01-01 to prevent 253-session warmup lookback from underflowing; `test_xnys_calendar_start_pinned_before_sharadar_history` verifies.

Post-correction review receipt terminal state: `approved`.

## Verify

PASS — Full suite: `uv run pytest -q`: 507 passed, 1 skipped in 15.25s (pre-merge branch state); refreshed post-merge on main. Lint: `uv run ruff check` clean. Deterministic replay confirmed: two independent backtest runs (span 2020-09-09..2020-09-16, split 2020-09-14) byte-identical. All 8 delta requirements covered by scenario tests (see verification.md §1). Design conformance audit: all 10 architecture decisions from design.md implemented as specified (verification.md §2). Proposal success criteria: all 5 criteria met (verification.md §5).

## Specs Merged

| Domain | Changes |
|--------|---------|
| `point-in-time-market-context` | ADDED 1 requirement (Authoritative generation span), MODIFIED 1 requirement (Context authority and coverage: added outside-span authority rejection scenario) |
| `sharadar-market-context-generator` | ADDED 1 requirement (Scanner-sufficient warmup fetch), MODIFIED 1 requirement (Deterministic schema output: clarified v2 versioning, span requirement, added pair-bars scenario) |
| `trading-system` | ADDED 3 requirements (Authoritative replay window/bar partition, Warmup bars history-only, Full-window context completeness), MODIFIED 1 requirement (Daily equity summary/split-date: scoped split validation to in-window dates, added warmup-date rejection scenario) |

## Known Deferred Items (non-blocking)

- Post-merge operational note (not part of code change): regenerate `fixtures/real-years/**` for real Sharadar-credentialed runs; this change provides the context/bars schema and validation, not live fetches.
- `src/invest/adapters/bars_fixture_json.py` restoration: file originated on unmerged branch `feat/sharadar-actions-reconcile`, faithfully restored here as required implementation target for "Pair bars output with the declared span" scenario; no logic divergence, verified byte-identical to origin (see verification.md §6 deviation note).

## Archive Record

- Change folder: archived as `openspec/changes/archive/2026-07-18-backtest-warmup-replay-window/`
- Artifacts preserved: proposal.md, design.md, exploration.md, specs/ (3 merged main specs), tasks.md (19/19 tasks), verification.md (PASS verdict + design audit), reviews/ (ledger.json, receipt.json)
- Main specs updated: `openspec/specs/point-in-time-market-context/spec.md`, `openspec/specs/sharadar-market-context-generator/spec.md`, `openspec/specs/trading-system/spec.md`
