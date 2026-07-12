# Review Policy: implementation-foundation

## Target

The full implementation of the `implementation-foundation` change: the entire
authored source tree at the final candidate (src/, tests/, fixtures/,
Dockerfile, pyproject.toml, openspec artifacts) relative to the empty
pre-change repository.

## Deterministic Risk Classification

- Authored changed lines: ~1,900 (> 400) → **High tier**
- Shell/process integration present (CLI entrypoint, container packaging)
- Result: **full 4R** — one exhaustive sweep each of `review-risk`,
  `review-readability`, `review-reliability`, `review-resilience`.

## Rules

- Findings freeze after the four initial lens sweeps; ledger is append-frozen.
- Deterministic severe findings corroborate directly with proof references.
- Inferential severe findings from all lenses merge into exactly ONE detached
  refuter batch.
- WARNING/SUGGESTION rows are `info` and never block or drive correction.
- At most one correction transaction; scoped fix-delta validation if any
  correction occurs.
- Independent final verification is the SDD verify phase (requirements,
  tasks, tests, build evidence) and can only approve or escalate.

## Evidence Commands

- `uv run --extra dev pytest` (36 tests)
- `uv run --extra dev ruff check .`
- `uv run invest-scan --universe fixtures/v1/universe.json --bars fixtures/v1/bars.json --format json`
- `docker build` + container run (accept + failure paths)


## Correction Lineage: implementation-foundation-final

The full-implementation 4R review completed in lineage
`implementation-foundation-code` (terminal receipt: approved; frozen ledger of
9 findings; REL-001 corroborated and corrected; RES-001 refuted by refuter
batch; scoped fix-delta validation approved; independent final verification
PASS). Its chain bundle and receipt are preserved as
`chain-bundle-code-lineage.json` / `receipt-code-lineage.json`.

This lineage covers the uncommitted REL-001 correction delta as a
current-changes target so the archive gate can reproduce the snapshot:

- Target: 6 modified files (scanner, rejection, cli, two test files, design.md)
- Deterministic classification: ~71 changed lines, no security/auth surface,
  behavior/tests dominant → **Medium tier — exactly one lens:
  `review-reliability`**
- Independent final verification evidence: `verify-report.md` (sdd-verify PASS
  over this exact worktree)


## Terminal Lineage: implementation-foundation-clean

Lineages `implementation-foundation-code` (full 4R, REL-001 corrected,
RES-001 refuted) and `implementation-foundation-final` (FREL-001/FREL-002
corrected: real-fixture CLI contract test plus truthful design row) are
preserved as audit chains. This terminal lineage reviews the final
current-changes state (all corrections applied): Medium tier, exactly one
`review-reliability` lens, independent verification evidence in the
enveloped `verify-report.md`.
