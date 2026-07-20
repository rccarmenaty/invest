# Exploration: Backtest Warmup Replay Window

## Problem

Every real fixture emitted by `invest-generate-context --bars-out` fails replay with `market-context-incomplete`. The generator intentionally fetches pre-`--start` bars so liquidity screening and momentum scanning have historical observations, but the generated market context only declares coverage for the requested generation dates. The replay harness currently treats every bar date—including those earlier warmup dates—as a decision and validation date.

The system therefore conflates two different time ranges:

- **Warmup history**: bars before the requested generation start, available only as inputs to indicators and screens.
- **Replay window**: dates on which context must be complete and the backtest may make decisions, enter or exit positions, validate state, and produce portfolio observations.

## Current Architecture

- `src/invest/adapters/generate_context_cli.py:52-68` accepts `--start`, `--end`, context output, optional bars output, and liquidity-screen settings. `src/invest/adapters/generate_context_cli.py:99-116` loads one `GeneratorInputs`, builds the context from it, and optionally writes all fetched bars as a replay fixture.
- `src/invest/adapters/sharadar_context_source.py:54-74` constructs `GeneratorInputs.sessions` from XNYS sessions in `[start, end]`, while separately fetching bars. `src/invest/adapters/sharadar_context_source.py:119-169` moves each cohort's SEP fetch start backward by `needed_bars - 1` sessions, bounded by listing date, so the bar set can predate `start`.
- `src/invest/domain/liquidity_screen.py:42-49` sets the Core screen default to 252 observed bars. `src/invest/adapters/sharadar_context_source.py:129-133` consequently requests only the maximum of the screen's observed-bar and dollar-volume requirements.
- `src/invest/application/generate_market_context.py:50-70` keeps requested sessions and fetched bars in the same input object, then passes the requested sessions to the context builder. `src/invest/domain/market_context_builder.py:50-83` creates per-symbol coverage and eligibility only from the first through last requested session; earlier bars participate in screening history but do not extend coverage.
- `src/invest/adapters/backtest_context_json.py:65-100` defines and reads `market-context-v1` with only `schema_version` and per-symbol state. `src/invest/adapters/backtest_context_json.py:147-177` writes the same structure. The artifact has no authoritative top-level generation span that replay can use as its temporal boundary.
- `src/invest/application/backtest_run.py:98-120` derives scan and completeness dates from every bar date. It calls `MarketContext.require_complete` before scanning, then `scan_decisions` asks for an eligible universe on every one of those dates. `src/invest/application/backtest_run.py:146-178` also runs portfolio/context processing over every date in `bars_by_date`.
- `src/invest/domain/market_context.py:148-179` is intentionally fail-closed: `status` raises when either coverage or eligibility is missing, `require_complete` checks the full date-symbol product supplied by replay, and `eligible_symbols` delegates to `status`.
- `src/invest/domain/momentum_selection_scanner.py:20-40` requires `HISTORY_DAYS = 253` bars before a symbol can participate. That exceeds the generator's 252-bar Core screen default by one bar.
- `src/invest/adapters/cli.py:225-242` validates `--split-date` against the minimum and maximum dates of all input bars, so a split inside warmup history is currently accepted, then invokes replay without an explicit replay boundary.

## Root Cause

The generator and replay use different implicit meanings for the same bar set:

1. The source declares context sessions only for `[start, end]` (`sharadar_context_source.py:58-60`).
2. The source fetches up to roughly one trading year of earlier bars (`sharadar_context_source.py:129-169`).
3. The builder correctly limits coverage to the declared sessions (`market_context_builder.py:62-75`).
4. The bars fixture preserves both warmup and in-window bars (`generate_context_cli.py:109-116`).
5. Replay derives `replay_dates` from all preserved bars and requires context for every symbol on every such date (`backtest_run.py:117-120`).

The first pre-window bar therefore reaches `MarketContext.status`, which cannot find coverage for that date and raises `MarketContextIncompleteError` (`market_context.py:148-155`). This is deterministic for any generated fixture containing warmup bars; it is not a missing-data condition in the provider payload.

A second mismatch is latent: the generator's default 252-bar fetch depth satisfies the liquidity screen but not the Core scanner's 253-bar history gate. Even after separating warmup from replay, the first declared replay session would otherwise have insufficient scanner history when the symbol has a full prehistory.

## Proposed Direction A'

1. **Declare an authoritative generation span in `market-context-v1`.** Add a required top-level date range populated from the requested generation sessions and expose it through the loaded domain object. Missing or malformed span metadata must make the artifact invalid; replay must not infer a boundary from whatever coverage happens to be present.
2. **Define the replay window from that declared span.** Partition input bars into pre-window warmup bars and in-window replay bars. Dates after the declared end should be rejected rather than silently ignored. Require at least one in-window replay session and verify that CLI range/split inputs are coherent with the declared span.
3. **Keep completeness fail-closed.** Call `require_complete` for every replay date and every fixture symbol across the declared replay window. Do not shrink the replay window to the intersection of observed context coverage: an accidentally late or incomplete coverage window must still fail.
4. **Use pre-window bars only as history.** `scan_decisions` should iterate only replay dates, while each scanner call receives eligible symbols' bars through the current replay date, including their pre-window history. Portfolio processing, unsafe-position checks, entries, exits, context outcomes, equity observations, and segment validation must begin no earlier than the declared span.
5. **Guard warmup depth against the selected scanner.** Core generation must request at least 253 bars where listing history permits, matching `MomentumSelectionScanner.HISTORY_DAYS`. Newly listed symbols may legitimately have fewer bars and should remain scanner-level `INSUFFICIENT_HISTORY`; the guard is on requested lookback depth, not a fabricated guarantee that every symbol has 253 observations.
6. **Preserve temporal authority.** Context status remains authoritative only inside the declared generation span. Warmup bars never require eligibility or blockers because they cannot produce decisions, entries, exits, or validation events.

This direction repairs the harness without weakening `MarketContext` invariants or pretending that the generator produced historical point-in-time screening outside its requested range.

## Alternatives Considered

### Naive A: Validate only dates that happen to be covered — rejected

Intersecting bar dates with existing per-symbol coverage would avoid the immediate exception, but it is fail-open. If an artifact accidentally omits the first week, ends early, or has a symbol-specific gap, replay would silently shorten or reshape the test period instead of reporting incomplete context. Coverage cannot safely define its own validation boundary.

### B: Extend/fill eligibility across all warmup dates — rejected

Adding eligibility and blocker state for pre-`start` bars would fabricate unscreened point-in-time authority. The generator's declared session set, candidate interval, and action/blocker evaluation are scoped to `[start, end]`; warmup SEP rows were fetched only to supply trailing history. Treating them as screened dates would also permit pre-window decisions and entries, changing the semantic meaning of `--start`.

## Open Questions

1. **Schema compatibility:** adding a required span to `market-context-v1` will intentionally reject older v1 files. The fail-closed choice is to require regeneration rather than make the field optional or infer it; confirm whether the schema label should remain v1 or be version-bumped despite the chosen direction's wording.
2. **Domain representation:** decide whether the declared span is a first-class field on `MarketContext` or whether reader/replay use a small document wrapper containing `{generation_span, context}`. A first-class field gives replay one domain-owned authority; a wrapper reduces changes to context-query code.
3. **Post-window bars:** the recommended behavior is a deterministic input error when a fixture contains dates after the declared end. Confirm the error reason and whether live-source requests must exactly equal, rather than merely fall within, the declared span.
4. **Warmup configuration:** decide whether the 253-bar requirement is imported from the Core scanner, passed explicitly as a generation requirement, or represented by a shared strategy capability. Avoid an unexplained duplicated constant in the Sharadar adapter.
5. **Split semantics:** `--split-date` should be validated against in-window replay dates, not all bar dates. Confirm whether it must equal an observed replay session or may remain any date within the declared span.

## Impacted Files

### Production

- `src/invest/domain/market_context.py` — carry or expose the authoritative generation span while preserving fail-closed status and completeness behavior.
- `src/invest/adapters/backtest_context_json.py` — add required span serialization, strict validation, and reader/writer round-trip support.
- `src/invest/application/generate_market_context.py` — retain the requested span when constructing the context artifact.
- `src/invest/domain/market_context_builder.py` — attach the requested session bounds to the built context if the span is domain-owned.
- `src/invest/adapters/sharadar_context_source.py` — request scanner-sufficient warmup depth while keeping `sessions` limited to the generation span.
- `src/invest/application/backtest_run.py` — partition warmup and replay dates; limit decisions and portfolio processing to the declared span while retaining warmup bars in scanner history.
- `src/invest/adapters/cli.py` — validate fixture/live range and split date against the declared replay window.
- `src/invest/adapters/generate_context_cli.py` — pass span/warmup requirements explicitly through generation and bars-output orchestration.

### Tests

- `tests/adapters/test_backtest_context_json.py` — required span schema, malformed/missing span rejection, and round-trip tests.
- `tests/application/test_backtest_run.py` — warmup-only history, first in-window decision timing, fail-closed in-window gaps, and no pre-window portfolio events.
- `tests/adapters/test_sharadar_context_source.py` — 253-session requested lookback and listing-date truncation.
- `tests/adapters/test_generate_context_cli.py` — paired context/bars outputs with a declared replay span.
- `tests/domain/test_market_context.py` and `tests/domain/test_market_context_builder.py` — span invariants and builder propagation if domain-owned.
- `tests/domain/test_momentum_selection_scanner.py` — preserve the 253-bar history contract.
- `tests/fixtures/test_backtest_252_fixtures.py` — regression coverage for fixtures containing pre-window history.
