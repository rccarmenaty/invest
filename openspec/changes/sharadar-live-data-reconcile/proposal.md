# Proposal: sharadar-live-data-reconcile

## Intent

Realistic live Sharadar context generation still fails after the earlier ACTIONS-schema,
fractional-volume, and SEP request-chunking reconciles. The current exploration confirms three
remaining compatibility blockers. Two prior descriptions are explicitly superseded: blocker 1 is
not an empty ACTIONS page, and blocker 3 is not malformed raw OHLC data.

1. **A mapped, exact-zero valued action aborts the complete ACTIONS pull.** On the diagnosed
   revision, `SharadarActionsReader._rows_to_actions` rejects valued mapped actions when
   `value <= 0`. The live row `RVPH | 2026-02-23 | dividend | 0` is structurally valid and maps
   to a typed dividend, but exact zero follows the same `malformed-response` path as negative,
   absent, or non-finite values. Because the failure occurs inside the cursor-paginated full-table
   fetch, no partial event set is returned. Changing only the exact-zero condition allowed the
   complete **612,437-action** live fetch to finish.
2. **Strict direct-replay coverage and sparse context observations are conflated.**
   `SharadarMarketDataReader._validate_and_finalize` enforces a dense rectangle: every requested
   symbol must appear, every symbol must have the same dates, and the union must equal every XNYS
   session in the range. That is an intentional fail-closed contract for direct
   `invest-backtest --source sharadar` replay. It is not the correct contract for
   `SharadarContextSource`, where live observations are legitimately ragged and the existing
   screen evaluates observed-bar count, current-date presence, price, and liquidity. A live probe
   returned **4,196 symbols** and **1,024,219 bars**, collectively covering all **256 XNYS
   sessions**, but per-symbol/cohort gaps still aborted context generation before the screen could
   classify affected symbols or dates as ineligible.
3. **Adjusted-price Decimal arithmetic creates microscopic envelope drift.** Raw `_SepRow` OHLC
   relationships are valid. `_rows_to_bars` independently adjusts open, high, and low with
   `raw * (closeadj / close)` while assigning close directly from `closeadj`. Decimal rounding
   created exactly **six** adjusted bars outside the OHLC envelope by **`1E-27`**. The bars could
   be written by `BarsFixtureWriter`, but `JsonFixtureReader` later rejected the exported fixture
   as `fixture-invalid`. Deterministically re-enveloping adjusted low/high removed all six
   discrepancies.

This change introduces the smallest explicit seams needed to absorb those confirmed live-data
shapes while preserving unrelated fail-closed guards. Context generation gains sparse-observation
semantics without silently weakening strict direct replay; raw OHLC validation remains strict;
and empty ACTIONS response semantics remain unchanged.

Exploration: `openspec/changes/sharadar-live-data-reconcile/exploration.md` and Engram topic
`sdd/sharadar-live-data-reconcile/explore`.

## Scope

> **Scope note (review correction REL-101/REL-102 of `sharadar-sep-null-volume-reconcile`):**
> In-scope items 1 (ACTIONS exact-zero acceptance) and 3 (adjusted-OHLC re-envelope) have been
> absorbed into and formalized by `sharadar-sep-null-volume-reconcile` — spec deltas, pinned
> regressions, and verify addendum live there. Future appliers MUST NOT re-implement or revert
> those shipped behaviors under this change. Note the absorbed ACTIONS behavior is kind-blind
> (zero accepted for all mapped valued kinds); any kind-specific narrowing (e.g. rejecting zero
> splits) is a new behavioral change against the merged spec and needs its own delta. Item 2
> (sparse context seam) remains this change's active scope.

### In Scope

1. **Accept exact-zero mapped valued actions** in
   `src/invest/adapters/sharadar_actions.py` by separating exact zero from invalid negative,
   absent, or non-finite values. Preserve the mapped typed event so the kind-blind context builder
   can create its same-day corporate-action blocker. Add a regression case for
   `RVPH | 2026-02-23 | dividend | 0` and retain full-fetch/pagination behavior.
2. **Add an explicit sparse-observation seam for context generation.** Keep
   `SharadarMarketDataReader.fetch_range` strict by default for direct replay. Give
   `SharadarContextSource._fetch_sep_cohorts` an explicit way to request structurally validated
   observed SEP bars without requiring the dense full-symbol/full-session rectangle. The seam may
   be an explicit validation policy or a dedicated context-facing method, but it MUST be visible
   at the call boundary and MUST NOT silently change the default `fetch_range` contract.
3. **Re-envelope only adjusted prices** in
   `src/invest/adapters/sharadar_market_data.py::_rows_to_bars`. After independently adjusting
   open/high/low and assigning close from `closeadj`, set adjusted high/low deterministically so
   they contain adjusted open and close. Keep `_SepRow` raw structural OHLC validation unchanged,
   so provider rows with `low > high` or open/close outside `[low, high]` still fail closed.
4. Add focused adapter/context regression tests for all three blockers, including strict direct
   replay coverage tests and exported-fixture readability through `JsonFixtureReader`.

### Preserved Fail-Closed Behavior

- **ACTIONS:** empty `datatable.data`, missing required columns, short rows, absent/non-finite
  valued actions, and negative valued actions remain malformed. Empty ACTIONS page semantics are
  explicitly unchanged and out of scope.
- **SEP structure:** missing required columns, short rows, duplicate `(symbol,date)` rows, blank
  cursors, non-positive prices, raw OHLC relationship violations, authentication failures, retry
  bounds, pagination caps, and empty SEP responses remain fail-closed.
- **Direct replay:** `invest-backtest --source sharadar` continues to require strict
  full-universe/full-range dense coverage through the default `fetch_range` path.

### Out of Scope / Non-Goals

- No global weakening of `SharadarMarketDataReader.fetch_range` coverage validation.
- No acceptance or repair of malformed raw OHLC rows.
- No change to empty ACTIONS response handling, ACTIONS request filtering, pagination, or
  retry/backoff behavior.
- No new corporate-action kinds or changes to blocker semantics.
- No change to price-adjustment formula or precision; only deterministic adjusted-envelope
  restoration after the existing arithmetic.
- No domain model, liquidity-screen, context schema, or fixture schema change.
- Further provider/data-shape reconciles remain separate changes.

## Affected Areas

| Area | Expected change |
|------|-----------------|
| `src/invest/adapters/sharadar_actions.py` | Accept exact zero for mapped valued actions while preserving all other value guards |
| `src/invest/adapters/sharadar_market_data.py` | Expose explicit strict-vs-sparse observation validation seam; re-envelope adjusted low/high only |
| `src/invest/adapters/sharadar_context_source.py` | Select sparse-observation semantics explicitly for context cohorts |
| `tests/adapters/test_sharadar_actions.py` | RVPH exact-zero regression and preserved invalid-value cases |
| `tests/adapters/test_sharadar_market_data.py` | Strict replay coverage regression, sparse seam behavior, and `1E-27` adjusted-envelope cases |
| Context/fixture integration tests | Context cohort uses sparse seam; written bars remain readable by `JsonFixtureReader` |

Affected capabilities: `sharadar-actions-reference-data`, `sharadar-sep-market-data`, and
`sharadar-market-context-generator`. The strict replay requirements of the Sharadar SEP capability
remain authoritative for the default/direct path.

## Success Criteria

- The live `RVPH | 2026-02-23 | dividend | 0` row is returned as a mapped dividend rather than
  aborting the ACTIONS pull; the complete **612,437-action** probe succeeds.
- Negative, absent, and non-finite mapped valued actions still fail closed. Empty ACTIONS data
  remains fail-closed exactly as before.
- Broad `invest-generate-context` can consume legitimate per-symbol/per-cohort SEP gaps through an
  explicit context-only sparse-observation seam and reaches the existing observed-bar liquidity
  screen instead of aborting on dense-rectangle validation.
- Direct `invest-backtest --source sharadar` continues to use strict `fetch_range`: missing
  symbols, unequal per-symbol date sets, or incomplete XNYS range coverage still fail closed.
- Raw valid OHLC rows that produce independent-adjustment drift are re-enveloped after adjustment;
  all six retained **`1E-27`** cases pass `JsonFixtureReader` after export.
- Raw structural OHLC violations remain rejected before adjustment.
- Existing structural, pagination, authentication, and retry guards remain green.
- New tests bind the explicit call-site seam so future refactors cannot accidentally route direct
  replay through sparse semantics or context generation through strict dense validation.
- A realistic live context generation plus bars export completes, and the exported bars fixture is
  readable through `JsonFixtureReader`.

## Delivery Constraints

User preflight is authoritative:

- **Mode:** automatic; the resolved defaults below proceed without a blocking question round.
- **Artifact store:** both OpenSpec and Engram.
- **PR shape:** one PR by default, with three independently revertable commits (ACTIONS zero,
  sparse context seam, adjusted OHLC envelope).
- **Changed-line budget:** 600 lines. Initial proposal forecast is approximately **300-500 changed
  lines** across production code, tests, and delta specs. If design/task forecasting exceeds 600,
  stop and re-forecast the split before apply rather than silently overrun the budget.

## Rollback Plan

- Keep the work in one PR but use independently revertable commits:
  1. exact-zero ACTIONS acceptance and tests;
  2. explicit context sparse-observation seam plus strict replay regressions;
  3. post-adjustment envelope restoration plus fixture-read regression.
- Revert commit 1 to restore the previous `value <= 0` behavior without affecting SEP handling.
  This knowingly reintroduces failure on the RVPH live row; empty-page semantics are unaffected in
  either direction.
- Revert commit 2 to route context cohorts back through strict dense validation while leaving the
  direct replay contract unchanged throughout.
- Revert commit 3 to restore the previous independent adjusted values; discard and regenerate any
  bars fixtures produced by the reverted implementation.
- No domain/schema migration or persisted-state rollback is required. Context and bars artifacts
  are derived outputs and can be regenerated.
- If the forecast exceeds 600 changed lines, revise the delivery plan before implementation; do
  not split reactively after exceeding the budget.

## Dependencies

- Source diagnosis and retained evidence in
  `openspec/changes/sharadar-live-data-reconcile/exploration.md`, including:
  - RVPH zero-dividend regression and successful 612,437-action probe;
  - 4,196-symbol / 1,024,219-bar / 256-session sparse SEP probe;
  - unreconciled and reconciled six-row `1E-27` adjusted-envelope fixtures.
- Landed predecessors: archived `2026-07-16-sharadar-actions-reconcile` (live ACTIONS vocabulary
  and value normalization), archived `2026-07-16-sharadar-sep-volume-reconcile` (fractional SEP
  volume), and `sharadar-sep-batch-fetch` (large-universe request chunking).
- Existing context screening behavior (`min_observed_bars`, current-date presence, price, and
  liquidity) remains the authority for classifying sparse observed histories.
- Existing direct Sharadar replay capability remains the authority for strict dense coverage.
- `BarsFixtureWriter` and `JsonFixtureReader` form the export/read compatibility boundary for the
  adjusted-envelope fix.
- Live verification requires `NASDAQ_DATA_LINK_API_KEY`, network access, and access to the retained
  probe artifacts where available.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Exact-zero acceptance also permits a provider zero for another mapped valued kind, such as split, without equivalent live evidence | Medium | Medium | Specify the exact accepted kinds in design; preserve typed mapping and reject absent, non-finite, and negative values; bind RVPH dividend behavior explicitly |
| Sparse context policy accidentally becomes the default and weakens direct replay safety | Medium | High | Keep strict `fetch_range` as the default; require an explicit context-only policy/method at the call site; add negative boundary tests for direct replay |
| Sparse mode treats a provider outage as legitimate missing observations | Medium | High | Preserve response-structure, empty-response, pagination, and transport guards; distinguish structurally valid non-empty sparse observations from malformed/empty provider responses; make zero-row symbol behavior explicit in design tests |
| Context still aborts because only per-symbol equality is relaxed while another dense check remains on the sparse path | Medium | Medium | Define the sparse seam as an end-to-end validation contract, then test real-shaped ragged cohorts rather than changing one conditional in isolation |
| Adjusted re-enveloping masks malformed raw OHLC data | Low | High | Run unchanged `_SepRow` raw OHLC validation first; re-envelope only the validated adjusted values in `_rows_to_bars`; retain raw-violation tests |
| Decimal drift outside the retained six rows has a different magnitude | Medium | Low | Use deterministic containment (`max`/`min`) rather than a hard-coded `1E-27` tolerance; test both retained examples and generalized Decimal cases |
| Three fixes plus integration tests exceed the 600-line budget | Low | Medium | Forecast again in design/tasks; keep one PR only while at or below 600 lines, otherwise propose a reviewed split before apply |
| Generic public error reasons make future live-data diagnoses expensive | Medium | Low | Preserve useful internal test assertions and captured rows; broader diagnostic redesign remains out of scope |

## Proposal Question Round — Automatic-Mode Resolutions

The first proposal's assumptions are superseded. Under the user's automatic-mode preflight, the
proposal proceeds with these resolved defaults for design; no blocking response is required:

1. **Coverage boundary:** strict dense validation remains the default/direct `fetch_range`
   contract. Context cohorts opt into an explicit sparse-observation seam. There is no global
   relaxation.
2. **Sparse evidence boundary:** context mode accepts structurally valid ragged observations and
   delegates eligibility to the existing observed-bar screen. Empty SEP responses and structural
   payload failures remain fail-closed. Design must make absent-symbol behavior explicit rather
   than inherit it accidentally.
3. **Exact-zero values:** exact zero is separated from negative/absent/non-finite values for mapped
   valued actions. The RVPH zero dividend is the required regression; design must document whether
   the implementation guard applies uniformly to all mapped valued kinds or narrowly by kind.
4. **OHLC boundary:** raw OHLC validation is unchanged. Only adjusted low/high are deterministically
   re-enveloped after Decimal adjustment; no tolerance threshold and no raw bad-tick repair.
5. **Delivery:** one PR with three independently revertable commits is the default. Re-plan only if
   the design/task forecast exceeds the 600 changed-line budget.
