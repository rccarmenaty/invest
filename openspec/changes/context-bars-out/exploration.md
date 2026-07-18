# Exploration: `--bars-out` for `invest-generate-context` (context-bars-out)

## Intent
Extend `invest-generate-context` so a single Sharadar pull can also emit a replayable
bars fixture. Add a `--bars-out PATH` flag. When set, persist the SEP daily bars already
fetched during context generation to a `JsonFixtureReader`-compatible fixture, so backtests
can run `--source fixture` locally forever with zero duplicate API calls. Backtest-only,
deep-module, TDD.

## Current State
`invest-generate-context` (`src/invest/adapters/generate_context_cli.py`, console script in
`pyproject.toml:17`) runs:
`SharadarContextSource(client=client).load(start, end, config)` →
`GenerateMarketContext().run(inputs, config)` →
`BacktestContextJsonWriter().write(context, out)`.

`SharadarContextSource.load` (`src/invest/adapters/sharadar_context_source.py`) discovers
TICKERS candidates, fetches SEP bars per listing-window cohort (`_fetch_sep_cohorts`,
lines 119-140) via `self._sep.fetch_range(...)` (reusing `SharadarMarketDataReader`
unchanged), and fetches ACTIONS once. It returns
`GeneratorInputs(sessions, listings, bars, actions)`
(`src/invest/application/generate_market_context.py`) with `bars` already sorted by
`(symbol, date)`. Today `GenerateMarketContext.run` consumes `inputs.bars` and discards
the raw tuple after building `MarketContext`. `--bars-out` must persist `inputs.bars`
without a second API round trip.

## Key architectural fact
Every symbol in `inputs.listings` gets a `SymbolContext` entry in the output context —
none are ever dropped (verified in `market_context_builder.build_market_context`). And
`_fetch_sep_cohorts` guarantees every listing has ≥1 fetched bar (each cohort's
`fetch_range` call enforces full-calendar coverage per cohort window). So
`{listing symbols} == {bar symbols}` always holds at this point, which directly satisfies
`JsonFixtureReader`'s invariant.

## Ragged-coverage contrast (confirmed)
`SharadarMarketDataReader.fetch_range` (`src/invest/adapters/sharadar_market_data.py:82-125`)
enforces strict all-or-nothing full-calendar coverage per call — but `_fetch_sep_cohorts`
calls it once **per distinct listing-derived cohort window**, not once globally. That is
why ragged IPO/delisting coverage across the full requested range survives into
`GeneratorInputs.bars` untouched.

## Reusable precedent: `SnapshotWriter`
`src/invest/adapters/alpaca_market_data.py:168-242` already does almost exactly this for
the Alpaca path: writes an atomic directory `{out}/{version}/{universe.json,bars.json,
provenance.json}` (staging tempdir + `Path.replace`), with `fixture_version =
as_of.isoformat()`, `str(bar.open)`-style Decimal serialization, and int-collapse for
whole-number volume (consistent with fractional-volume commit `f5d928d`). Mirror this
pattern; do not import the class — `tests/test_boundaries.py:449-468` asserts
`generate_context_cli.py` only imports `sharadar_context_source`. A new small
Sharadar-context-specific writer adapter is the correct seam.

## Companion universe.json (resolved)
A bars fixture alone isn't replayable: `JsonFixtureReader.load`
(`src/invest/adapters/fixtures_json.py:54-94`) requires
`universe.fixture_version == bars.fixture_version` and (combining both checks)
`set(universe.symbols) == set(bar symbols)` exactly. Given the architectural fact above,
the universe to write is simply `sorted({listing.symbol for listing in inputs.listings})`.
**Recommendation: `--bars-out PATH` is a directory** (mirrors `SnapshotWriter` and the
existing hand-authored `fixtures/backtest/{universe.json,bars.json}` pair), writing
`PATH/universe.json` + `PATH/bars.json`, avoiding a second CLI flag.

## fixture_version
`fixture_version = args.end.isoformat()`, consistent with `SnapshotWriter`'s
`as_of.isoformat()` convention. `JsonFixtureReader` treats it as an opaque string equality
check only.

## Approaches
1. **New thin adapter (`BarsFixtureWriter`-style), CLI wires it as a second write step
   using `inputs.listings`/`inputs.bars` already in scope.** Deep-module, zero domain
   changes, testable via round-trip through `JsonFixtureReader` like
   `tests/adapters/test_fixtures_json.py`. Effort: Low. **Recommended.**
2. Thread bars persistence through `GenerateMarketContext`/`GeneratorInputs`. Couples the
   pure application use case to filesystem I/O, violates "domain untouched". Rejected.

## Recommendation
Approach 1. Add `--bars-out PATH` (directory) to the parser; after
`inputs = SharadarContextSource(...).load(...)`, if set, call a new adapter
(`src/invest/adapters/bars_fixture_json.py`) with `inputs.listings`/`inputs.bars` to
atomically write `PATH/universe.json` + `PATH/bars.json`, mirroring `SnapshotWriter`'s
serialization and atomicity pattern.

## Risks
- `tests/adapters/test_generate_context_cli.py:175-193`
  (`test_core_defaults_and_no_banned_flags`) needs an explicit new assertion for
  `--bars-out`'s dest during apply.
- The `universe ⊆ bars` invariant is currently emergent (a consequence of upstream
  cohort-fetch behavior), not independently enforced at the writer boundary — recommend a
  defensive check + test there.
- Directory-vs-single-file semantics for `--bars-out PATH` is a genuine open product
  decision; recommended default is directory, confirm at proposal time.
- Read `tests/adapters/test_alpaca_market_data.py` at design time to mirror
  `SnapshotWriter`'s exact atomicity test style.

## Ready for Proposal
Yes — data path, seam, companion-universe requirement, and fixture_version convention are
resolved with codebase evidence. Engram artifact: `sdd/context-bars-out/explore` (obs 3229).
