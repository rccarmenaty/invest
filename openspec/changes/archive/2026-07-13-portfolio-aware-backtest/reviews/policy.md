# Review Policy: portfolio-aware-backtest

## Target

The post-apply `portfolio-aware-backtest` implementation in the current
worktree, based on candidate commit `b6539f65a850d67e7c9311e53c8522db17674dfd`
plus its uncommitted implementation diff. `gentle-ai review-start` must capture
this exact state as the immutable review snapshot; no later worktree changes are
in scope.

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

Ordinary post-apply review transaction for lineage `portfolio-aware-backtest`.

## Deterministic Risk Classification

- Authored changed lines: 500-700 (over 400) -> High tier.
- Portfolio-aware backtest behavior and financial metrics affect simulation
  correctness and decision-quality outputs.
- Result: full 4R initial lens set -- one exhaustive sweep each of
  `review-risk`, `review-resilience`, `review-readability`, and
  `review-reliability`.

## Rules

- This policy applies only to the immutable snapshot captured when the review
  transaction starts.
- Findings freeze after the four initial lens sweeps; deterministic severe
  findings corroborate directly; inferential severe findings merge into one
  refuter batch; WARNING/SUGGESTION rows are informational.
- No reviewers, refuters, corrections, or validation are run by this start
  operation.
