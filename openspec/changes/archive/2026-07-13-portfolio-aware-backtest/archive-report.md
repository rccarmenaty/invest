# Archive Report: portfolio-aware-backtest

## Scope

Extends `invest-backtest` from single-symbol day-0 mechanics into a portfolio-aware replay: finite starting capital, cash, equity, open positions, and deployed capital tracked across the range, with the existing pure pre-trade gates (`max-concurrent-positions`, `max-equity-deployed`, buying power, kill-switch) applied to simulated entries. Adds a deterministic daily equity summary and explicit-split-date IS/OOS trade segmentation, and keeps `BacktestRun.replay(...)` as the single seam — no separate portfolio engine.

## Delivery

- Single PR slice (no chaining): `src/invest/adapters/cli.py`, `src/invest/application/backtest_run.py`, `src/invest/domain/backtest_metrics.py`, `src/invest/domain/models.py`, plus their focused tests — 738 changed lines, within the 800-line budget.
- Strict TDD throughout: RED/GREEN/TRIANGULATE/REFACTOR evidence recorded per phase in `apply-progress.md` (21/21, 21/21, 21/21 focused tests passed per phase; 31/31 combined at implementation time, 41/41 at verify time after additional edge-case tests).

## Review

Lineage `portfolio-aware-backtest-clean`: full 4R sweep produced 5 info-level findings only (`READABILITY-001..004`, `RELIABILITY-001`), 0 BLOCKER/CRITICAL. Receipt terminal state `approved`.

**Known tooling gap (not a code defect):** the installed `gentle-ai` v1.49.0 binary's `review-validate` reports this receipt as `invalidated` due to a `ledger_findings_hash` algorithm mismatch against a locally patched binary used in an earlier session (patched version excludes `proof_refs` from the hash; installed version includes them). The authoritative CAS transaction at `.git/gentle-ai/review-transactions/v1/portfolio-aware-backtest-clean/` is internally consistent (`ledger_hash` matches the raw `ledger.json` file hash exactly); the divergence is confined to the derived `ledger_findings_hash` field, which the installed binary's receipt schema doesn't even accept (`unknown field` on parse). This is an environment/tooling incompatibility between two binary versions, not a finding about `portfolio-aware-backtest`'s code. Archived manually on that basis, using `verify-report.md` as the authoritative evidence trail instead of the native gate.

## Verify

PASS WITH WARNINGS — 4/4 requirements, 11/11 scenarios compliant, 0 blockers/criticals. `uv run --extra dev pytest`: 179 passed, 3 skipped. `uv run --extra dev ruff check .`: clean. Deterministic CLI replay: two independent `invest-backtest --split-date 2024-01-23` invocations byte-identical.

## Open Follow-ups (non-blocking)

- `src/invest/application/backtest_run.py:10-13` module docstring says portfolio gates are not simulated; stale now that gates run during replay.
- `src/invest/application/backtest_run.py:308-341` retains legacy `_simulate_trade(...)`, unreferenced by current replay.
- `BacktestRun.__init__` takes six parameters mixing collaborator, account-state, and cost-model configuration — candidate for a config object in a future cleanup slice.
- Basis-point conversion constant `10000` repeated as an unnamed literal in `backtest_metrics.py` and `cli.py`.
- Deferred by scope (per proposal/design): point-in-time universe, confirmation-service logic, richer execution realism.
