# Archive Report: trailing-exit-engine

**Change**: trailing-exit-engine  
**Artifact store**: hybrid  
**Archived at**: 2026-07-16  
**Archive path**: `openspec/changes/archive/2026-07-16-trailing-exit-engine/`  
**Status**: success  

## Gates

| Gate | Result | Evidence |
|------|--------|----------|
| Review gate | allow | `gentle-ai sdd-status` → `reviewGate.result: allow` ("explicit bound compact authority exactly matches the current repository"); `gentle-ai review validate --gate post-apply --lineage trailing-exit-engine-unit-3-postcommit-recovery` → `result: allow` |
| Bound authority | match | lineage `trailing-exit-engine-unit-3-postcommit-recovery`; binding revision `sha256:85840d63c7a045d109418e1ef32c0b366ac4bb172bdac4e38f4e5abcc7eb7e2a`; authority revision `sha256:f08ed6db7af7eb238c8f6b33ed055221bb7059302fedcfe5d0b9222ea142ea28` |
| Terminal receipt | approved | `terminal_state: approved`; final_candidate_tree `50050c23b5e6c2473e5fca9d6bbb4054638016f7`; paths_digest `sha256:2286a180488f90f2e97062d500a629bc747716d55a34c2861a8309e1b02589a1`; empty fix delta; policy/ledger hashes match gate context |
| Task completion | 26/26 | Archived `tasks.md` has 26 `[x]` implementation tasks and zero unchecked implementation tasks |
| Verification | PASS | verify-report verdict `pass`; 6/6 requirements; 14/14 scenarios; 0 CRITICAL; 0 WARNING; evidence_revision `sha256:d8d1637f96b4a3a43d42308385cb1c4e7040dd33fc6a0b7cd8fd3c41f1d064c9` |
| Action context | repo-local | allowed root `/Users/rcty/invest` |

## Bound review authority consumed

| Artifact | Location | Key facts |
|----------|----------|-----------|
| Transaction / state | `.git/gentle-ai/review-transactions/v2/trailing-exit-engine-unit-3-postcommit-recovery/review-state.json` | state `approved`; generation 2; store revision `sha256:f08ed6db7af7eb238c8f6b33ed055221bb7059302fedcfe5d0b9222ea142ea28` |
| Receipt | `.git/gentle-ai/review-transactions/v2/trailing-exit-engine-unit-3-postcommit-recovery/review-receipt.json` | `terminal_state: approved`; trees equal (clean post-commit recovery) |
| Ledger | empty (no findings) | `ledger_hash` / `fix_delta_hash` = empty SHA-256 `sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| Gate context | binding `gate_context` + live post-apply validate | gate `post-apply`; `allowed: true`; base relationship valid |
| SDD binding | `.git/gentle-ai/sdd-review-bindings/v1/trailing-exit-engine/binding.json` | change `trailing-exit-engine` bound to recovery lineage |

Recovery note: successor of `trailing-exit-engine-unit-3-committed-scope` after post-commit scope-changed disposition; user-authorized compact recovery for clean tree SDD binding.

## Specs synced

| Domain | Action | Details |
|--------|--------|---------|
| trading-system | Updated | 6 ADDED requirements, 0 MODIFIED, 0 REMOVED, 0 RENAMED; appended before `## Source` in `openspec/specs/trading-system/spec.md` |

### Added requirements

1. Replay-only pure exit engine (2 scenarios)
2. Default 10-day-low trailing exit (3 scenarios)
3. Never-loosening floor and exit priority (3 scenarios)
4. Conditional 20-session time stop (2 scenarios)
5. Selectable 3-ATR high-water variant (2 scenarios)
6. No look-ahead and deterministic exit provenance (2 scenarios)

All pre-existing main-spec requirements preserved.

## Archive contents

- proposal.md ✅
- exploration.md ✅
- design.md ✅
- tasks.md ✅ (26/26 complete)
- specs/trading-system/spec.md ✅
- apply-progress.md ✅
- verify-report.md ✅
- archive-report.md ✅ (this file)

## Active change cleanup

- `openspec/changes/trailing-exit-engine/` removed (moved to archive)
- No active change folder remains for this name

## Engram observation IDs (traceability)

| Artifact | Observation ID | Topic key |
|----------|----------------|-----------|
| proposal | #3134 | `sdd/trailing-exit-engine/proposal` |
| spec | #3135 | `sdd/trailing-exit-engine/spec` |
| design | #3136 | `sdd/trailing-exit-engine/design` |
| tasks | #3139 | `sdd/trailing-exit-engine/tasks` |
| apply-progress | #3141 | `sdd/trailing-exit-engine/apply-progress` |
| verify-report | #3159 | `sdd/trailing-exit-engine/verify-report` |
| archive-report | #3162 | `sdd/trailing-exit-engine/archive-report` |

## Intentional overrides

None. Full archive with complete tasks, passing verification, and allow review gate.

## SDD cycle

The change has been planned, implemented (3 chained units), reviewed (bound Unit 3 post-commit recovery authority), verified, and archived. Source of truth updated at `openspec/specs/trading-system/spec.md`.
