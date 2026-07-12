# Review Policy: backtest-replay

## Target

The merged backtest-replay implementation (PR #17, baseline 7d7179e,
candidate 95158fd): fetch_range/_paginate extraction, BacktestRun harness,
trade simulation, backtest_metrics.py, invest-backtest CLI, disclaimers,
out-of-scope guard.

## Deterministic Risk Classification

- Authored changed lines: ~1,000 (over 400) -> High tier
- Financial correctness surface (metrics feed real go/no-live decisions)
- Result: full 4R sweep set.

## Rules

- Findings freeze post-sweeps; deterministic severe corroborate directly;
  inferential severe merge into ONE refuter batch; WARNING/SUGGESTION info.
- Corrections land as PRs FIRST, then a fresh terminal lineage over the
  corrected tree (archive-gate reproducibility constraint).
- Final verification = enveloped SDD verify report.

## Terminal Lineage: backtest-replay-clean

Lineage backtest-replay (genesis at 95158fd) held the full 4R sweeps: 11
findings -- BRISK-001/BRES-001 CRITICAL, plus 9 info rows. Correction PR #18
(4fc94bd) fixed both severe findings via a Claude Sonnet subagent (first
fully Codex-free fix cycle). This terminal lineage reviews the corrected
tree: empty current-changes diff at 4fc94bd -> Low tier, zero lenses;
ledger records resolved findings and open follow-ups; final verification
is the enveloped SDD verify report.
