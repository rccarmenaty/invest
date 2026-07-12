# Review Policy: market-data-adapter

## Target

The merged market-data-adapter implementation (PRs #7, #8): MarketDataReader
port, AlpacaMarketDataReader (httpx, pagination, retry, error taxonomy),
SnapshotWriter with atomic publication and provenance sidecar, invest-fetch
CLI, boundary/live/calendar tests. Content at main 0d3b2b8 relative to
c379eae (pre-change baseline).

## Deterministic Risk Classification

- Authored changed lines: ~900 (> 400) -> High tier
- Secrets handling (Alpaca credentials), shell/process integration (new CLI)
- Result: full 4R - one exhaustive sweep each of review-risk,
  review-readability, review-reliability, review-resilience.

## Rules

- Findings freeze after the four sweeps; deterministic severe findings
  corroborate directly; inferential severe findings merge into ONE refuter
  batch; WARNING/SUGGESTION are info and never block.
- If correction is needed it lands as a PR FIRST, then a fresh terminal
  lineage reviews the corrected state (remediation-envelope constraint on
  tracked apply-progress.md makes in-lineage fix batches unusable at the
  archive gate).
- Independent final verification is the SDD verify phase; verify-report.md
  MUST begin with a gentle-ai.verify-result/v1 YAML envelope.

## Terminal Lineage: market-data-adapter-clean

Lineage market-data-adapter (genesis at 0d3b2b8) held the full 4R sweeps:
12 findings — MREL-001 BLOCKER, MREL-002/MREL-003/MRES-001 CRITICAL,
MRISK-001/MRISK-002/MRES-002 + 5 readability info rows. Scope changed when
correction PR #9 (e78c933) landed the fixes (MREL-003 was reclassified info:
its claimed contract text came from an orchestrator paraphrase, not the
spec). Per lifecycle rules, scope change creates this new terminal lineage
over the corrected tree: empty current-changes diff at e78c933 -> Low tier,
zero lenses; ledger records resolved findings and open follow-ups; final
verification is the enveloped SDD verify report.
