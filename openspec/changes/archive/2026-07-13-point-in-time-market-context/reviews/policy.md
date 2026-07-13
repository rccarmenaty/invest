# Review Policy: Point-In-Time Market Context Integrated Clean

## Transaction

- Mode: `ordinary_4r`
- Lineage: `point-in-time-market-context-integrated-clean`
- Working directory: `/var/folders/k_/jgmzsf8d6qd42sp29q1vwn7r0000gn/T/opencode/pit-integrated-review-worktree`
- Target kind: `current-changes`
- Detached HEAD commit: `70f4be02b167e4187c764aeaa6bb25fb1798d2d8`
- Base tree: `8bf837998eb2ef5c51535dd142c815a99ddb27a6`
- Candidate tree: `9bdcfb0c0e0df464017c9a432e57ebede91bc73c`
- Delivered candidate commit: `f7ee101af6d1474c2af2d7f3c66d905d8702c30c`
- Source revision: `70f4be02b167e4187c764aeaa6bb25fb1798d2d8..f7ee101af6d1474c2af2d7f3c66d905d8702c30c`
- Materialization: the exact binary/full-index source revision is applied to the detached base as staged, uncommitted tracked changes.
- Previous lineage: `point-in-time-market-context-integrated` captured an empty snapshot and is invalid for content review; do not resume, reuse, mutate, or treat it as review evidence.

## Preconditions

- The detached HEAD tree must equal the declared base tree.
- The current index tree must equal the declared candidate tree and the delivered candidate commit tree.
- The worktree must contain no unstaged changes and no untracked files.
- The status path set must contain exactly the 22 paths below and no others.
- Stop before transaction creation if any precondition differs.

## Scope

The exact current-changes target contains only these paths:

- `fixtures/backtest/market-context.json`
- `openspec/changes/point-in-time-market-context/apply-progress.md`
- `openspec/changes/point-in-time-market-context/design.md`
- `openspec/changes/point-in-time-market-context/exploration.md`
- `openspec/changes/point-in-time-market-context/proposal.md`
- `openspec/changes/point-in-time-market-context/specs/point-in-time-market-context/spec.md`
- `openspec/changes/point-in-time-market-context/specs/trading-system/spec.md`
- `openspec/changes/point-in-time-market-context/tasks.md`
- `openspec/changes/point-in-time-market-context/verify-report.md`
- `src/invest/adapters/backtest_context_json.py`
- `src/invest/adapters/cli.py`
- `src/invest/application/backtest_run.py`
- `src/invest/domain/market_context.py`
- `src/invest/domain/models.py`
- `tests/adapters/test_alpaca_broker.py`
- `tests/adapters/test_backtest_context_json.py`
- `tests/adapters/test_cli_backtest.py`
- `tests/adapters/test_cli_execute.py`
- `tests/application/test_backtest_run.py`
- `tests/application/test_execute_run.py`
- `tests/domain/test_market_context.py`
- `tests/test_boundaries.py`

The intended-untracked manifest is explicitly empty. Stop if the derived snapshot has empty paths, a different base or candidate tree, any untracked path, or any out-of-scope path.

## Risk And Lenses

- Risk tier: high because the delivered delta contains 2,179 additions plus deletions across 22 paths.
- Initial review: full 4R.
- Selected lenses, each exactly once: `risk`, `readability`, `reliability`, `resilience`.
- Create exactly one review-start transaction for this lineage.
- Do not launch reviewers, refuters, fixes, rejudgments, or verification as part of transaction creation.
