# Review Policy: paper-trading-execution

## Target

The merged paper-trading-execution implementation (PRs #11-#14, baseline
6ca7374, candidate main c357350): domain sizing/indicators/gates, order
event contract families, BrokerPort/ExecuteRun orchestration, AlpacaBroker
paper adapter, invest-execute CLI.

## Deterministic Risk Classification

- Authored changed lines: ~1,900 (over 400) -> High tier
- First mutating broker adapter; credential handling; money-adjacent paths
- Result: full 4R sweep set.

## Rules

- Findings freeze post-sweeps; deterministic severe corroborate directly;
  inferential severe merge into ONE refuter batch; WARNING/SUGGESTION info.
- Corrections land as PRs FIRST, then a fresh terminal lineage over the
  corrected tree (archive-gate reproducibility constraint).
- Final verification = enveloped SDD verify report.

## Terminal Lineage: paper-trading-execution-clean

Lineage paper-trading-execution (genesis at c357350) held the full 4R
sweeps: 15 findings — PRES-001 BLOCKER, PRES-002/PREL-001/PREL-002 CRITICAL,
plus 11 info rows. Scope changed when correction PR #15 (8b8149a) landed
all severe fixes plus PREL-003/PREL-004/PRES-003. This terminal lineage
reviews the corrected tree: empty current-changes diff at 8b8149a -> Low
tier, zero lenses; ledger records resolved findings and open follow-ups;
final verification is the enveloped SDD verify report.
