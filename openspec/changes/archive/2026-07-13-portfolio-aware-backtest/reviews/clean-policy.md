# Review Policy: portfolio-aware-backtest-clean

## Target

The current corrected `portfolio-aware-backtest` worktree target, based on
candidate commit `b6539f65a850d67e7c9311e53c8522db17674dfd` plus the current
uncommitted correction diff. `gentle-ai review-start` must capture this exact
state as the immutable snapshot; later worktree changes are out of scope.

## Scope

- Application changes: `src/invest/adapters/cli.py`,
  `src/invest/application/backtest_run.py`,
  `src/invest/domain/backtest_metrics.py`, and `src/invest/domain/models.py`.
- Regression coverage: `tests/adapters/test_cli_backtest.py`,
  `tests/application/test_backtest_run.py`, and
  `tests/domain/test_backtest_metrics.py`.
- Change intent and requirements: `openspec/changes/portfolio-aware-backtest/`.
- Excluded: unrelated untracked local files `.env` and `universe.json`.

## Mode

Ordinary post-correction review transaction for lineage
`portfolio-aware-backtest-clean`.

## Deterministic Risk Classification

- The corrected target is executable code with more than 400 authored changed
  lines -> High tier.
- Portfolio-aware backtest behavior and financial metrics affect simulation
  correctness and decision-quality outputs.
- Result: full ordinary 4R initial sweep -- one exhaustive sweep each of
  `review-risk`, `review-resilience`, `review-readability`, and
  `review-reliability`.

## Lineage Independence

`portfolio-aware-backtest-clean` is a new, independent ordinary review lineage
for the current corrected target. It does not continue, mutate, validate, or
replay the terminal escalated lineage `portfolio-aware-backtest`.

## Rules

- This policy applies only to the immutable snapshot captured when this review
  transaction starts.
- Findings freeze after the four initial lens sweeps; deterministic severe
  findings corroborate directly; inferential severe findings merge into one
  refuter batch; WARNING/SUGGESTION rows are informational.
- This start operation runs no reviewers, refuters, corrections, or final
  verification.
