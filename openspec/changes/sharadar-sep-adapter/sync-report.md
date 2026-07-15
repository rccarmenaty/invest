# Sync Report: Sharadar SEP Adapter

**Status:** blocked

## Executive Summary

Canonical specifications were not synced. The approved ordinary-review receipt for `review-0a0e79d70c1fe394` was exported verbatim from the native compact review store to the native status path `openspec/changes/sharadar-sep-adapter/reviews/receipt.json`. Its SHA-256 matches the source exactly. The authoritative `gentle-ai sdd-status` parser rejects that authentic compact-v2 receipt because it expects `gentle-ai.review-receipt/v1`, reporting `json: unknown field "body"`. No receipt was synthesized or transformed, so the review gate remains invalidated and sync is blocked.

## Structured Status and Action Context

```yaml
changeName: sharadar-sep-adapter
artifactStore: openspec
applyState: all_done
taskProgress: 13/13 complete
actionContext:
  mode: repo-local
  workspaceRoot: /Users/rcty/invest
  allowedEditRoots:
    - /Users/rcty/invest
reviewGate:
  result: invalidated
  reason: 'review receipt is invalid or non-terminal: json: unknown field "body"'
nextRecommended: resolve-review
```

The authoritative workspace and every touched path are within `/Users/rcty/invest`. This is not a non-authoritative Engram-status case.

## Review Artifact Export

| Source | Destination | Result |
|---|---|---|
| `.git/gentle-ai/reviews/compact-v2/review-0a0e79d70c1fe394/review-receipt.json` | `openspec/changes/sharadar-sep-adapter/reviews/receipt.json` | Byte-identical authentic export; SHA-256 `a05fa861ea981459aac4d1a2a5227295f0e3bff0f813d45f4adb6274a0b5b570` |

The exported source declares terminal state `approved`, but its envelope is `gentle-ai.review-receipt-body/v2` under `{body, receipt_hash}`. The currently installed native status parser requires a `gentle-ai.review-receipt/v1` artifact. Creating such a conversion would synthesize a new receipt and was not performed.

## Planned Sync

| Domain | Canonical target | Delta operations | Result |
|---|---|---|---|
| `sharadar-sep-market-data` | `openspec/specs/sharadar-sep-market-data/spec.md` | New canonical spec (six requirements) | Not created |
| `trading-system` | `openspec/specs/trading-system/spec.md` | ADDED: `Backtest data source selection`; `Source flag stays backtest-only` | Not appended |

No MODIFIED, REMOVED, or RENAMED requirement blocks are present. No destructive approval is needed. There are no other active changes, so there are no same-domain collisions. `openspec/config.yaml` contains no `rules.sync`.

## Checks Performed

- Read proposal, both domain specs, design, tasks, verify report, and config.
- Confirmed verification report is PASS with 13/13 tasks complete.
- Validated the native receipt lineage and terminal state before export.
- Verified source and destination receipt bytes and SHA-256 match.
- Reran `gentle-ai sdd-status sharadar-sep-adapter --cwd /Users/rcty/invest --json --instructions` after export.
- Confirmed canonical targets are inside the allowed edit root and left canonical specs unchanged.

## Blocker and Next Step

A compatible, authentic `gentle-ai.review-receipt/v1` (and any required native review chain artifacts) must be exported by a native helper/version that supports the compact-v2 review store, or the status parser must gain compact-v2 receipt support. Do not hand-convert the receipt. Once native status returns a non-invalidated review gate and sync readiness, rerun `sdd-sync`; the next phase after a clean sync is `sdd-archive`.
