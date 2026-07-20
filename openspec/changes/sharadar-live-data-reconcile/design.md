# Design: sharadar-live-data-reconcile

## Summary

This change fixes only three confirmed Sharadar compatibility blockers while retaining strict direct-replay and structural validation contracts:

1. Accept exact zero only for normalized `DIVIDEND` actions. Normalized `SPLIT` ratios remain strictly positive. Empty ACTIONS pages remain malformed.
2. Keep public `SharadarMarketDataReader.fetch_range` strict for direct replay and add a named context-only observation method that shares transport/parsing but allows per-symbol session gaps. `SharadarContextSource` then validates aggregate session coverage across all cohorts.
3. Keep raw OHLC validation strict and re-envelope only adjusted prices after Decimal adjustment.

No domain model, screen, fixture schema, context schema, request shape, retry, pagination, or adjustment-formula change is introduced.

## Current-State Note

SUPERSEDED IN PART — review correction REL-101/REL-102 of `sharadar-sep-null-volume-reconcile`: the ACTIONS broad `value < 0` guard (kind-blind zero acceptance) and the `_rows_to_bars` adjusted-OHLC minimal re-envelope have been ABSORBED into and formalized by `sharadar-sep-null-volume-reconcile` (spec deltas, pinned regression tests, and verify addendum live there). Future appliers of this change MUST NOT re-implement, revert, or "re-RED" those two shipped behaviors; their contracts are now owned by the merged specs (`sharadar-sep-market-data` requirement "Deterministic OHLC adjustment" and `sharadar-actions-reference-data` requirement "Typed corporate-action events").

Consequences for this draft:
- Unit 3 (adjusted envelope) is fully absorbed: the shipped `max`/`min` containment matches this design's decision and is already spec-bound and test-pinned. Only the fixture round-trip/offline integration regressions remain optionally valuable here.
- Unit 1 is absorbed as shipped (zero accepted for ALL mapped valued kinds). This design's further narrowing — rejecting zero splits while keeping zero dividends — would now be a NEW behavioral change against the merged spec's "Exact zero valued actions are retained" scenario and requires its own spec delta if still desired; it is not a reconciliation of untracked code anymore.
- Unit 2 (sparse context seam) is unaffected and remains this change's core.

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| ACTIONS zero scope | Permit `value == 0` only when the normalized kind is `SharadarActionKind.DIVIDEND`; reject zero for `SPLIT` | The live evidence is RVPH dividend zero. A zero split ratio is nonsensical and unsupported by evidence. Mapping first also covers raw `spinoffdividend` as a dividend and `adrratiosplit` as a split. |
| Empty ACTIONS page | Unchanged: required columns plus empty `data` still raises `malformed-response` | This change is row-value reconciliation, not outage/empty-table handling. |
| Sparse API | Add `fetch_context_observations(universe, start, end) -> FixtureInputs` | The name makes weaker coverage semantics visible. A defaulted `strict=False`/policy boolean would be easy to misuse. |
| Direct replay API | `fetch()` and `fetch_range()` remain strict and keep their existing signatures | `invest-backtest --source sharadar` continues to require a dense symbol/session rectangle. |
| Sparse symbol handling | Tolerate gaps; never drop a requested symbol. A requested symbol with zero returned rows fails `symbol-missing-at-fetch` | Listings must remain visible to the screen, while total symbol omission remains indistinguishable from a bad request/provider failure. |
| Sparse date handling | Returned dates must be XNYS sessions inside that call's inclusive range; missing sessions are allowed | Sparse means absent observations, not acceptance of unknown, holiday, weekend, or out-of-range records. |
| Cross-cohort coverage | Before returning bars, context source requires `union(expected XNYS sessions for every cohort range) == union(returned bar dates across all cohorts)` | Legitimate symbol/cohort gaps survive, but a globally absent session still fails closed. |
| OHLC repair | Compute all four adjusted candidates, then set `high=max(candidates)` and `low=min(candidates)` | Deterministic containment handles any Decimal drift magnitude without an epsilon. Open and close are not modified. |
| Raw OHLC | Keep `_SepRow` positivity, finiteness, and envelope validation before adjustment | The adapter must not repair provider corruption or economically meaningful raw bad ticks. |

## Technical Approach

### 1. ACTIONS: kind-specific exact-zero validation

`SharadarActionsReader._rows_to_actions` continues to map the raw action literal before validating its value.

Validation order and contract:

1. Unknown/skipped action literals continue to drop before row-value validation.
2. Delisting and ticker-change events continue to normalize any source value to `None`.
3. For mapped valued events, absent or non-finite values remain malformed.
4. For `DIVIDEND`, require `value >= 0`.
5. For `SPLIT`, require `value > 0`.
6. Preserve the accepted exact value as `Decimal`; do not rewrite zero to `None`.

Thus `dividend` and `spinoffdividend` may carry `Decimal("0")`, while `split` and `adrratiosplit` may not. Negative values remain invalid for both normalized kinds. `_rows_to_actions` retains its existing `not columns or not data` guard, required-column check, short-row check, pagination behavior, and all-or-nothing fetch result.

The accepted zero dividend remains a typed event. `SharadarContextSource._fetch_actions` normalizes it unchanged, and the kind-blind context builder can produce the existing same-day corporate-action blocker when that date is otherwise eligible.

### 2. SEP: explicit strict and sparse observation contracts

#### API shape

```python
class SharadarMarketDataReader:
    def fetch(self, universe: Universe, as_of: date) -> FixtureInputs: ...

    def fetch_range(
        self, universe: Universe, start: date, end: date
    ) -> FixtureInputs:
        """Strict dense range for direct replay."""

    def fetch_context_observations(
        self, universe: Universe, start: date, end: date
    ) -> FixtureInputs:
        """Structurally valid, non-empty-per-symbol observations for context screening."""
```

`fetch()` continues to delegate to strict `fetch_range()`. `adapters/cli.py::backtest_main` remains unchanged and therefore also uses strict `fetch_range()`. Only `SharadarContextSource._fetch_sep_cohorts` calls `fetch_context_observations()`.

#### Shared transport and parse layer

Refactor the current chunk loop into one private shared acquisition path, conceptually:

```text
_fetch_observed_bars(universe, start, end)
  -> chunk symbols
  -> fetch every cursor page
  -> validate response schema and rows
  -> reject duplicate (symbol, date)
  -> merge chunks
  -> run common observation-set validation
  -> return deterministically sorted DailyBars
```

Both public methods use this exact path, so sparse context does not gain a separate HTTP implementation. Existing request projection, ticker chunking, retries, authentication, page cap, empty-page rejection, short-row rejection, required columns, raw row validation, and cursor handling remain shared.

Common observation-set invariants for both methods:

- Every bar symbol is in the requested universe; unknown symbols are malformed.
- Every bar date is an XNYS session in `[start, end]`; holiday/weekend and out-of-range dates are malformed.
- Every `(symbol, date)` is unique across all pages and chunks.
- Every requested symbol has at least one row; otherwise fail `symbol-missing-at-fetch` and return no partial `FixtureInputs`.
- Bars are returned sorted by `(symbol, date)`.

The range-wide duplicate check is retained after merge even if page/chunk checks catch the usual cases. It prevents a future chunking refactor or an unexpected cross-request provider row from weakening uniqueness.

#### Strict finalization

`fetch_range` applies the existing replay contract after common validation:

```text
expected_dates = all XNYS sessions in [start, end]
for every requested symbol:
    dates_by_symbol[symbol] == expected_dates
```

Any unequal symbol date set or globally missing expected session remains `MarketDataFetchError("malformed-response", "incomplete date coverage")`. Missing symbols retain `symbol-missing-at-fetch`. No existing strict coverage test flips.

#### Context observation finalization

`fetch_context_observations` applies no per-symbol dense-date equality after common validation. It returns all observed bars and drops none. In particular:

- a symbol with at least one valid row and internal gaps is retained;
- a symbol with zero rows fails;
- a missing session for all symbols in one call is not decided at the reader level because cohorts have different active windows and are aggregated by the context source;
- no bars are synthesized, forward-filled, interpolated, or rejected merely for a gap.

#### Aggregate context coverage

`SharadarContextSource._fetch_sep_cohorts` explicitly calls `fetch_context_observations`. While building cohorts it accumulates:

```text
expected_global = union(
    XNYS sessions in each cohort's inclusive [fetch_start, fetch_end]
)
actual_global = union(bar.date for every returned cohort bar)
```

After every cohort has returned and before bars leave `_fetch_sep_cohorts`, require `actual_global == expected_global`. Common reader validation already proves `actual_global` cannot contain unknown dates, so inequality means at least one globally absent expected session. Raise `MarketDataFetchError("malformed-response", "incomplete aggregate context date coverage")` and return no inputs.

The context merge also asserts global `(symbol, date)` uniqueness. Cohort construction currently assigns each deduplicated listing to exactly one cohort; the assertion protects that invariant from later refactors.

If there are no candidates, `_fetch_sep_cohorts` still returns `()` and does not invent an expected SEP range. Existing `load` session validation remains authoritative for the requested context range.

#### Eligibility semantics

Sparse symbols remain in `GeneratorInputs.listings` and their observed bars remain in `GeneratorInputs.bars`. `GenerateMarketContext._to_symbol_data` groups those bars without requiring a dense date set. The unchanged liquidity screen decides each output date:

- no bar on `as_of` -> `eligible=False`;
- fewer than `config.min_observed_bars` observations on or before `as_of` -> `eligible=False`;
- with Core defaults, that threshold is 252 observed bars, not 252 calendar sessions;
- once 252 observations exist and the current bar exists, a symbol with earlier gaps may still be eligible if price and trailing observed-bar dollar-volume checks pass.

Therefore sparse does not mean unconditional rejection. Gaps reduce the observed count and missing-current-date observations fail that date; otherwise the existing screen remains the sole eligibility authority.

### 3. OHLC: adjusted-only deterministic re-envelope

`_SepRow` remains unchanged in role and order: Pydantic first validates finite positive raw `open`, `high`, `low`, `close`, and `closeadj`, then the model validator requires raw `low <= open, close <= high`. Invalid raw rows fail before adjustment and no row is returned.

For a validated row, `_rows_to_bars` computes:

```python
adjusted_open = _adjust(row.open, row.close, row.closeadj)
adjusted_high = _adjust(row.high, row.close, row.closeadj)
adjusted_low = _adjust(row.low, row.close, row.closeadj)
adjusted_close = row.closeadj
adjusted_prices = (adjusted_open, adjusted_high, adjusted_low, adjusted_close)
high = max(adjusted_prices)
low = min(adjusted_prices)
```

`DailyBar.open` remains `adjusted_open`, `DailyBar.close` remains exact `closeadj`, and only the output high/low envelope can move outward. There is no tolerance, quantization, float conversion, row drop, raw repair, or change to `_adjust`.

Because raw prices and the adjustment factor remain finite and positive, re-enveloping cannot legitimize a non-positive or non-finite input. Existing validation/arithmetic failures remain all-or-nothing `malformed-response`; the max/min operation is only reached for validated adjusted candidates.

## Data Flow

### Context generation

```text
invest-generate-context
  -> SharadarContextSource.load(start, end, config)
     -> TICKERS discovery and listing normalization (unchanged)
     -> cohort windows, including seasoning lookback (unchanged)
     -> SharadarMarketDataReader.fetch_context_observations per cohort
        -> shared SEP HTTP/chunk/page/parser
        -> strict structure + non-empty-per-symbol validation
        -> adjusted-only OHLC envelope
        -> sparse bars returned without per-symbol gap rejection
     -> aggregate expected-session union == returned-date union
     -> ACTIONS full-table fetch
        -> zero normalized dividend retained; zero split rejected
     -> GeneratorInputs
  -> GenerateMarketContext
     -> bars grouped per listing, no gap fill
     -> screen_eligible per requested session
        -> current-bar and 252-observed-bar gates
     -> existing action blockers and context schema
```

### Direct Sharadar backtest

```text
invest-backtest --source sharadar
  -> SharadarMarketDataReader.fetch_range
     -> same SEP HTTP/chunk/page/parser and adjusted envelope
     -> same structural/non-empty validation
     -> strict full symbol x XNYS-session coverage validation
  -> existing replay
```

The direct CLI never calls the context observation method.

### Bars fixture export/read

`invest-generate-context --bars-out` serializes the already fetched sparse `GeneratorInputs.bars` through `BarsFixtureWriter`. The zero-row-symbol guard keeps writer universe/bar symbol sets aligned. Ragged date coverage is already supported by the writer and `JsonFixtureReader`. The adjusted envelope ensures every exported row satisfies `JsonFixtureReader._BarPayload` OHLC validation; the reader remains unchanged and acts as the compatibility backstop.

## Contracts and Invariants

| Boundary | Accepted | Rejected |
|---|---|---|
| ACTIONS valued row | finite dividend `>= 0`; finite split `> 0` | absent/non-finite/negative valued actions; zero split |
| ACTIONS response | non-empty structurally valid pages | empty data, missing columns, short rows, bad cursor/page bound |
| Shared SEP parse | requested symbols, unique keys, valid raw row, valid in-range XNYS date | unknown symbol/date, duplicate, empty page, missing/short fields, non-positive/non-finite raw price, invalid raw OHLC |
| `fetch_range` | complete dense requested rectangle | missing symbol, any symbol/session gap, globally missing session |
| `fetch_context_observations` | every symbol observed at least once; per-symbol gaps allowed | zero-row symbol or any shared structural violation |
| Context cohort aggregate | global returned-date union equals expected cohort-session union | session absent from all returned cohort observations |
| Adjusted OHLC | exact adjusted open/close enclosed by outward adjusted high/low | no raw invalidity is repaired |

## File Changes

| File | Change |
|---|---|
| `src/invest/adapters/sharadar_actions.py` | Make valued-action zero validation kind-specific. |
| `src/invest/adapters/sharadar_market_data.py` | Add named context observation API; share acquisition/parsing; split common, strict, and sparse finalization; retain adjusted-only min/max envelope. |
| `src/invest/adapters/sharadar_context_source.py` | Call context observation API and enforce aggregate session-union plus merged-key invariants. |
| `tests/adapters/test_sharadar_actions.py` | Narrow existing broad zero test; add RVPH dividend and zero split boundaries; preserve empty/invalid tests. |
| `tests/adapters/test_sharadar_market_data.py` | Bind strict-vs-sparse APIs, shared structural guards, retained adjusted drift rows, and raw OHLC rejection. |
| `tests/adapters/test_sharadar_context_source.py` | Bind explicit method routing, cross-cohort union validation, and observed-bar eligibility flow. |
| `tests/adapters/test_cli_backtest.py` | Assert explicit Sharadar replay calls `fetch_range` and never the context method. |
| `tests/adapters/test_bars_fixture_json.py` or focused market-data integration test | Export adjusted retained rows and reload through `JsonFixtureReader`. No writer/reader production change. |
| `openspec/changes/sharadar-live-data-reconcile/specs/sharadar-actions-reference-data/spec.md` | Modify the existing broad zero requirement: dividend zero accepted, split zero rejected. |
| `openspec/changes/sharadar-live-data-reconcile/specs/sharadar-sep-market-data/spec.md` | Specify strict public range, named context observations, common structural invariants, and adjusted-only envelope. |
| `openspec/changes/sharadar-live-data-reconcile/specs/sharadar-market-context-generator/spec.md` | Specify sparse cohort use, global session-union guard, and unchanged observed-bar screening. |

No changes are planned for `DailyBar`, `liquidity_screen.py`, `generate_market_context.py`, `market_context_builder.py`, `BarsFixtureWriter`, `JsonFixtureReader`, context JSON, or CLI request arguments.

## Testing Strategy: Strict TDD

Tests are written and observed failing before each production slice. Each RED must fail for the intended contract reason, not from a typo or missing fixture. Then implement the minimum GREEN change, triangulate boundaries, refactor while green, and run the full gate.

### Baseline

```bash
uv run pytest tests/adapters/test_sharadar_actions.py tests/adapters/test_sharadar_market_data.py tests/adapters/test_sharadar_context_source.py tests/adapters/test_cli_backtest.py tests/adapters/test_bars_fixture_json.py
uv run ruff check .
```

### Slice 1: dividend zero only

RED tests:

- RVPH `dividend=0` and `spinoffdividend=0.0` return typed zero dividends.
- `split=0` and `adrratiosplit=0.0` fail `malformed-response`.
- negative, absent, NaN, and Infinity remain rejected.
- valid-columns/empty-data ACTIONS remains rejected.
- a cursor sequence containing RVPH returns the complete valid event set rather than partial data.

```bash
uv run pytest tests/adapters/test_sharadar_actions.py -k "zero_dividend or zero_split or empty_actions or rvph"
```

The current broad zero implementation should make the zero-split test RED. GREEN changes only the kind-specific value guard.

### Slice 2: sparse context seam with strict replay preserved

RED tests:

- `fetch_context_observations` accepts two non-empty symbols with unequal session sets.
- the identical payload still fails through `fetch_range`.
- sparse mode rejects a zero-row requested symbol, unknown symbol, unknown/non-session/out-of-range date, duplicate key, empty page, and structural row corruption.
- context source calls `fetch_context_observations`; a fake `fetch_range` raises if touched.
- two ragged cohorts whose combined dates cover the expected global union succeed.
- if every cohort lacks one expected session, context loading fails before ACTIONS/output.
- screen flow demonstrates 251 observed bars are ineligible, 252 current observations can be eligible, and no current-date bar is ineligible.
- direct backtest fake exposes both methods and fails the test if the context method is called.

```bash
uv run pytest tests/adapters/test_sharadar_market_data.py tests/adapters/test_sharadar_context_source.py tests/adapters/test_cli_backtest.py -k "context_observations or sparse or aggregate_context or observed_bar or explicit_sharadar_source"
```

### Slice 3: adjusted envelope only

RED tests use the retained six `1E-27` drift rows (or a compact checked-in fixture derived from them):

- raw rows satisfy the original envelope;
- adjusted open and close remain exact;
- adjusted low/high equal min/max of all adjusted candidates;
- exported rows round-trip through `BarsFixtureWriter` and `JsonFixtureReader`;
- raw `low > high`, raw open/close outside the envelope, zero/negative prices, NaN, and Infinity remain rejected.

```bash
uv run pytest tests/adapters/test_sharadar_market_data.py tests/adapters/test_bars_fixture_json.py -k "adjusted_envelope or decimal_drift or raw_ohlc"
```

If the current min/max implementation makes these tests green, obtain honest RED evidence by running the new tests against the immediate pre-envelope revision (or first reverting the premature implementation in the working branch), then restore the minimal implementation. Do not weaken the test merely to manufacture RED.

### Final gates

```bash
uv run pytest
uv run ruff check .
```

Manual live verification, after automated gates and only with credentials/network available:

1. ACTIONS probe completes and retains RVPH as a zero dividend; record total count without logging credentials.
2. Broad context probe reaches generation with the known 4,196-symbol/1,024,219-bar shape and aggregate 256-session coverage.
3. `--bars-out` output reloads through `JsonFixtureReader`.
4. A direct Sharadar replay fixture with a deliberate symbol/session gap still fails strict coverage.

Live probes supplement but never replace deterministic tests.

## Security / Threat Matrix

| Threat / failure mode | Risk from relaxation | Control | Residual risk |
|---|---|---|---|
| Zero split accepted as valid | Invalid ratio could create a misleading action/blocker | Zero permission is checked after normalization and only for `DIVIDEND`; split remains `> 0` | Provider may encode another legitimate zero-valued mapped kind; handle only with new evidence/change |
| Empty ACTIONS outage interpreted as no events | Corporate-action blockers disappear | Empty page behavior is unchanged and fail-closed | None added by this change |
| Sparse context method used by direct replay | Replay silently runs on incomplete symbol/date data | Separate named method; `fetch_range` signature/default unchanged; CLI routing test | Future call-site changes require tests/review |
| Provider-wide missing SEP session treated as ordinary gaps | Eligibility may be computed from an outage | Context aggregate expected-session union must equal returned-date union | A cohort-local outage can be masked if another cohort has that date; accepted because per-cohort density would recreate the live blocker |
| Entire requested symbol silently disappears | Listing vanishes or writer later fails | Both modes require at least one row per requested symbol and raise `symbol-missing-at-fetch` | A single bad row can prove presence; quality is then governed by structure and screening |
| Unknown ticker/date contaminates observations | Cross-request data or look-ahead could alter eligibility | Common validation requires requested symbol and in-range XNYS session | Calendar correctness remains dependent on existing `exchange_calendars` data |
| Duplicate rows double-count observed history | Could prematurely satisfy 252 bars or distort trailing liquidity | Range-wide `(symbol,date)` uniqueness before return and merged-cohort assertion | None added |
| Sparse history still becomes eligible | Earlier gaps may be overlooked | This is intentional observed-bar semantics: current bar, 252 observed bars, price, and trailing liquidity all remain required | Screen does not require 252 consecutive sessions; changing that is out of scope |
| Adjusted clamp hides raw bad ticks | Corrupt provider prices could be normalized | Raw positivity/finiteness/envelope validation runs first; only adjusted high/low move outward | Valid raw values with questionable economics remain provider data, as before |
| NaN/Infinity or non-positive values exploit min/max | Invalid bars could pass fixture validation unpredictably | Raw Decimal fields and positive constraints remain fail-closed before adjustment; invalid arithmetic returns no partial fetch | Decimal-context failures remain adapter failures; no fallback is introduced |
| Exported sparse bars mismatch universe | Fixture becomes unwritable/unreadable | Zero-row-symbol rejection preserves exact symbol set; writer and reader guards remain active | Storage failures remain handled by existing atomic writer |
| Large cohort aggregation increases resource use | Memory pressure/DoS during broad generation | Only bounded date/key sets are added to bars already materialized; existing chunk/page caps remain | Live universe size still determines existing bar memory cost |

## Migration, Rollout, and Rollback

There is no schema or persisted-state migration. Existing generated context/bars are derived artifacts; regenerate them after rollout or rollback.

Land one PR with three independently revertable commits, in this order:

1. **ACTIONS kind-specific zero**: tests/spec delta first, then the narrow guard. This corrects the current over-broad zero acceptance while retaining RVPH.
2. **Context observation seam**: tests/spec deltas first, then shared acquisition refactor, named method, context call-site, and aggregate guard. Direct `fetch_range` tests must remain green throughout.
3. **Adjusted envelope**: retained-row and fixture-read tests/spec delta first, then the minimal adjusted min/max implementation (or preserve the already-correct implementation with honest pre-change RED evidence).

Rollout gates for every commit:

- focused RED recorded;
- focused GREEN;
- relevant adapter suite;
- `uv run ruff check .`;
- no credential-bearing fixtures or logs committed.

Final merge requires `uv run pytest` and `uv run ruff check .`. Perform live smoke verification after CI, not as a merge substitute.

Rollback is commit-scoped:

- Revert commit 1 to restore prior zero handling; this may reintroduce RVPH failure or broad zero acceptance depending on the selected base, but does not affect SEP.
- Revert commit 2 to route context back through strict `fetch_range`; direct replay stays strict before, during, and after rollback.
- Revert commit 3 to restore pre-envelope adjusted values; discard and regenerate unreadable bars artifacts.

No compatibility shim, feature flag, dual schema, or data migration is needed.

## Changed-Line Forecast

Forecast counts additions plus modified/deleted lines for implementation, tests, retained compact fixture data, and delta specs; the design artifact itself is not part of the apply diff budget.

| Area | Forecast changed lines |
|---|---:|
| Production: ACTIONS | 5-12 |
| Production: SEP reader refactor/seam/validation | 45-75 |
| Production: context aggregate validation | 20-35 |
| ACTIONS tests | 25-45 |
| SEP reader tests | 90-135 |
| Context source and direct-CLI routing tests | 85-125 |
| Adjusted-envelope fixture/read tests and compact captured rows | 45-75 |
| Three delta specs | 65-95 |
| **Total** | **380-597** |

The high estimate remains under the 600-line single-PR budget by only three lines. Apply must target the middle of the range by reusing existing test helpers and keeping captured fixtures compact. Re-forecast after RED tests and before production implementation. If the actual forecast reaches or exceeds 600, stop and obtain approval for a reviewed split; do not exceed the budget reactively. The preferred split boundary is commit 2 (sparse context seam) versus commits 1 and 3, while preserving the same contracts.

## Resolved Questions

All design questions are resolved by the automatic-mode decisions above. No new feature or domain behavior is left open for implementation-time choice.
