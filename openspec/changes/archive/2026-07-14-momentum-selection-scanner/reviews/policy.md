# Review Policy: momentum-selection-scanner

**Operation**: `review/start(momentum-selection-scanner)` — explicit post-apply ordinary review (no prior receipt existed).
**Date**: 2026-07-14
**Snapshot**: working tree of branch `feat/momentum-selection-scanner` (post-verify, post-warning-closure), base content identical to main `143bb9f`.

## Risk classification (deterministic)

- Authored churn: ~603 lines (apply) + ~55 (verify-warning test + RES-001 correction) → **> 400 authored changed lines → High tier → full 4R** (generated `fixtures/backtest-252/*.json` excluded from the authored threshold).
- No auth/update/security/payments paths touched; the trigger is line count alone.

## Lens sweeps (one each, detached, read-only)

| Lens | Result |
|---|---|
| review-risk | No findings (explicit empty) |
| review-readability | 2 WARNING + 1 SUGGESTION (all info) |
| review-reliability | 1 WARNING + 1 SUGGESTION (all info) — first attempt crashed on a spend limit before any findings; the completed relaunch constitutes the single sweep |
| review-resilience | 1 CRITICAL + 2 WARNING |

## Evidence routing

- RES-001 (CRITICAL, deterministic) → corroborated directly; **no refuter** required.
- No inferential severe findings → refuter batch not launched (budget unconsumed).
- All WARNING/SUGGESTION rows → `info`, non-blocking follow-ups.

## Correction transaction (1 of 1)

- One atomic work unit mapped exactly to RES-001: stage-0 `MISSING_DATA` / `DOMAIN_INVARIANT_VIOLATION` guards + mirrored `_valid_bar`, strict TDD (RED: 2 failing tests → GREEN).
- Focused tests: `uv run --extra dev pytest tests/domain/test_momentum_selection_scanner.py` → 14 passed.
- Full suite: 241 passed, 3 skipped; `ruff check .` clean.
- Rollback boundary: revert the two guard blocks + `_valid_bar` + the two new tests.

## Scoped fix-delta validation

Detached read-only validator → **approve** (fix matches RES-001 exactly, RED evidence sound, acceptance criteria re-verified, no scope creep, purity preserved).

## Terminal state

**approved** — see `receipt.json`.

## Tooling note

The native gentle-ai review-transaction CAS store is incompatible with this flow (same limitation the `point-in-time-market-context` archive recorded); artifacts are persisted session-natively here with real command evidence, and no fabricated chain hashes are claimed.
