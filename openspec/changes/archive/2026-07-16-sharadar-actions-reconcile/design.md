# Design: Reconcile SharadarActionsReader with the Real SHARADAR/ACTIONS Schema

## Technical Approach

Schema-parity fix confined to `src/invest/adapters/sharadar_actions.py` and its test file. Expand `_ACTION_KINDS` to the 10 real mapped literals, fold them onto the existing closed 4-kind `SharadarActionKind` enum, make unmapped literals drop-and-continue (skip-unknown) instead of aborting the fetch, and remove the float guard so pydantic v2 coerces JSON floats to `Decimal`. No domain, application, or consumer change: the builder is kind-blind (`_build_blockers` keys on `effective_date` only) and the source treats `kind` as an opaque dedup string.

## Architecture Decisions

| Decision | Choice | Alternatives rejected | Rationale |
|---|---|---|---|
| Kind representation | (A) Keep the closed 4-kind enum; map many raw literals onto it | (B) Extend enum for directional ticker-change / per-literal fidelity | YAGNI-correct: no consumer branches on kind; directionality is never read. Fewer states, no downstream churn. Revisit only if the builder becomes kind-aware. |
| Unknown literals | Drop the row and `continue`; never raise | Raise (current reject-on-unknown) | Forward-compatible against provider vocabulary drift; a single new literal must not kill a broad-market pull. |
| Skip mechanism | Single runtime branch `kind is None -> continue`; explicit `_SKIPPED_ACTIONS` frozenset for documentation + a set-disjointness test | Two separate runtime paths for skipped vs unknown | Identical behavior; one branch avoids drift. The doc set makes deliberate skips testable and intentional. |
| Float values | Remove `isinstance(raw_value, float)` guard; rely on pydantic `Decimal` coercion | Keep guard | Real API sends every `value` as JSON float; `_SepRow` in `sharadar_market_data.py` is the exact precedent (str-based, precision-preserving). |
| Skip placement | Resolve/skip kind BEFORE `_ActionRow.model_validate` | Skip after full row validation | Skipped/unknown rows with odd fields must not abort the fetch; early-skip maximizes resilience. |

## Mapping Table (raw literal -> SharadarActionKind)

| Raw literal | Kind | Value class |
|---|---|---|
| `split`, `adrratiosplit` | `SPLIT` | valued, ratio > 0 |
| `dividend`, `spinoffdividend` | `DIVIDEND` | valued, finite |
| `delisted`, `regulatorydelisting`, `voluntarydelisting`, `bankruptcyliquidation` | `DELISTING` | valueless |
| `tickerchangeto`, `tickerchangefrom` | `TICKER_CHANGE` | valueless |

Explicit `_SKIPPED_ACTIONS` (documented, dropped): `listed`, `relation`, `acquisitionby`, `acquisitionof`, `mergerto`, `mergerfrom`, `spinoff`, `spunofffrom`. Any literal outside mapped ∪ skipped is also dropped (unknown drift). Legacy synthetic literals `delisting` and `tickerchange` no longer exist -> now dropped as unknown.

## Data Flow

    _rows_to_actions(page)
      per row:  len(values) < ncols ? -> raise (structural)      # unchanged, FIRST
                kind = _ACTION_KINDS.get(values[action_idx])
                kind is None ? -> continue                        # skip-unknown, no raise
                _ActionRow.model_validate(ticker,date,value)      # value: JSON float -> Decimal
                ticker.strip() empty ? -> raise
                DELISTING|TICKER_CHANGE -> value must be None
                else (SPLIT|DIVIDEND)  -> value present & finite
                  SPLIT -> value > 0
                append SharadarAction

The valueless/valued branch keys on the ENUM kind, so all 10 literals fold into the correct bucket with the existing checks unchanged. Skip drops rows without aborting the multi-page loop in `fetch()`.

## Per-row invariant ordering (preserved)

1. Short-row structural check stays FIRST (before kind peek).
2. Kind resolve/skip SECOND (raw literal peek), so only mapped rows reach validation.
3. `_ActionRow.model_validate` THIRD — drop the `action` field from `_ActionRow`; pass only `ticker`, `date`, `value`.
4. Whitespace-only ticker check FOURTH — unchanged.
5. valueless-vs-valued FIFTH; within the valued branch every mapped kind (split and dividend) requires a finite, strictly-positive value — a zero/negative value fails closed as `malformed-response`, per spec scenario "Non-finite or non-positive values still fail closed".

## File Changes

| File | Action | Description |
|---|---|---|
| `src/invest/adapters/sharadar_actions.py` | Modify | Expand `_ACTION_KINDS`; add `_SKIPPED_ACTIONS`; remove float guard; unknown-raise -> `continue`; drop `action` from `_ActionRow`; keep valueless/valued branch. |
| `tests/adapters/test_sharadar_actions.py` | Modify | Flip legacy-literal assertions; add mapped/skipped/unknown/float coverage. |

## Testing Strategy (strict TDD — RED first)

| Layer | What to test | Approach |
|---|---|---|
| Unit | 10 mapped literals -> correct enum + value class | Parametrized single-row pages; assert `kind` and value. |
| Unit | 8 skipped + arbitrary unknown literals -> zero actions, no raise | Assert `fetch()` returns `()`; mixed page keeps only mapped rows. |
| Unit | Multi-page resilience | Unknown literal on page 1 does not abort; page 2 combined. |
| Unit | Float values incl. high precision | JSON floats `0.1`, `0.25`, `123.456789012345` -> `Decimal(str(f))`. |
| Unit | Valueless violation via real literals | `tickerchangeto`/`delisted` with a value -> reject "valueless ... has a value". |
| Boundary | `_ACTION_KINDS.keys() & _SKIPPED_ACTIONS == set()`; no SEP/DailyBar import (existing) | Set assertion + existing AST test. |

### Existing assertions that flip

- `test_fetch_maps_all_provider_literals_to_closed_frozen_events`: `delisting`/`tickerchange` are now unknown -> rewrite with real literals.
- `test_fetch_rejects_invalid_or_unsupported_action_rows`: remove `("dividend", 0.1)` (now accepted), `("tickerchange","1")`, `("unsupported","1")`, `("SPLIT","2")` (now skipped, not rejected); keep split ratio and dividend finite cases; add `("tickerchangeto","1")` for the valueless violation.
- `test_rejected_rows_report_why_they_were_rejected`: replace `("delisting","3",...)` with `("delisted","3",...)`; remove `("merger","1","unsupported ACTIONS action")` — the unsupported-action `ValueError` is deleted.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. Pure data parsing.

## Migration / Rollout

No migration. Single small PR (well under the 400-line budget); rollback = revert the adapter + test commit. No schema, domain, or consumer changes to unwind.

## Open Questions

None. The kind-fold decision is resolved as Option A.

## Post-archive correction (live-data finding)

The "valueless" rows above (23-24, 41, 49, 66) assumed delisted/ticker-change rows never
carry a value — an assumption inherited from synthetic fixtures. The first live
`invest-generate-context` pull disproved it: real SHARADAR/ACTIONS attaches a contra/last
price to delisting and ticker-change rows (e.g. `BLD delisted value=9977.2`), and the
fail-closed guard aborted every pull. Corrected to **accept and drop**: those kinds accept
any source value and normalize it to absent, since the kind-blind context builder never
uses it. Split/dividend positivity checks are unchanged. See the updated main spec scenario
"Valueless kinds accept and drop any source value".
