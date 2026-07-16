# Proposal: `--bars-out` fixture export for invest-generate-context

## Intent

Generating a market context and then running an `invest-backtest --source sharadar` backtest pulls the same SEP daily bars twice: context generation fetches and discards them; the backtest re-fetches. This wastes Nasdaq Data Link quota and forces network pulls for every backtest run. Add `--bars-out PATH` to `invest-generate-context` so the bars already fetched during context generation are persisted once as a `JsonFixtureReader`-compatible fixture pair, making all subsequent backtests runnable offline via `--source fixture`.

## Scope

### In Scope
- New optional CLI flag `--bars-out PATH` (dest `bars_out`) on `invest-generate-context`; PATH is a **directory** receiving `universe.json` + `bars.json` (a bars file alone is not replayable — `JsonFixtureReader` requires a matching universe).
- New thin adapter `src/invest/adapters/bars_fixture_json.py` (`BarsFixtureWriter`-style), wired at CLI level from `inputs.listings` + `inputs.bars` — no second API call.
- `fixture_version = args.end.isoformat()` (matches `SnapshotWriter`'s `as_of.isoformat()` convention).
- Serialization/atomicity mirroring `SnapshotWriter` (`src/invest/adapters/alpaca_market_data.py:168-242`): staging tempdir + `Path.replace`, refuse-if-exists, `str(Decimal)` OHLC, int-collapse for whole-number volume.
- Defensive writer-boundary check: `set(universe symbols) == set(bar symbols)`; fail closed on violation or empty bars.
- TDD tests: writer round-trip through `JsonFixtureReader().load(...)`, CLI flag wiring, guard-test update in `tests/adapters/test_generate_context_cli.py`.

### Out of Scope
- No change to the live backtest `--source sharadar` path.
- No domain/application-layer changes (`GenerateMarketContext`, `GeneratorInputs` untouched).
- Not a general market-data cache — strictly emits already-fetched bars.
- Data-scope choices (which universe/date range to pull) are runtime usage, not this change.

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `sharadar-market-context-generator`: the standalone generator interface gains an optional `--bars-out` directory flag that atomically emits a replayable fixture pair from the already-fetched SEP bars, with fail-closed universe/bars symbol-set validation.

## Approach

CLI-level wiring only: `main()` already holds `inputs` from `SharadarContextSource.load` before running `GenerateMarketContext`. When `bars_out` is set, invoke the new adapter after the `--out` context write (isolated failure modes). Exploration confirmed `listings` symbol-set == `bars` symbol-set always holds upstream, so the universe file is `sorted({listing.symbol})` with a defensive re-check at the writer. Adapter stays a pure JSON-serialization module to satisfy `tests/test_boundaries.py` import rules (no `SnapshotWriter` import across the Alpaca/Sharadar boundary).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/invest/adapters/bars_fixture_json.py` | New | Atomic universe+bars fixture writer |
| `src/invest/adapters/generate_context_cli.py` | Modified | `--bars-out` flag + wiring |
| `tests/adapters/test_bars_fixture_json.py` | New | Round-trip + atomicity + invariant tests |
| `tests/adapters/test_generate_context_cli.py` | Modified | Flag presence/behavior; banned-dest guard note (`bars` banned vs `bars_out` allowed) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Guard test `test_core_defaults_and_no_banned_flags` silently unupdated | Med | Explicit task to add `bars_out` assertion |
| Emergent universe==bars invariant breaks upstream later | Low | Defensive fail-closed check in writer |
| Boundary-test violation via adapter imports | Low | Pure serialization adapter; run `tests/test_boundaries.py` |

## Rollback Plan

Revert the change commit(s): delete `bars_fixture_json.py`, remove the flag and its tests. No data migration; flag is optional and additive, so no consumer breaks.

## Dependencies

- None (uses existing `JsonFixtureReader` contract as the acceptance gate).

## Success Criteria

- [ ] `invest-generate-context ... --bars-out DIR` writes `DIR/universe.json` + `DIR/bars.json` with no additional API calls.
- [ ] `invest-backtest --source fixture --universe DIR/universe.json --bars DIR/bars.json` loads the pair via `JsonFixtureReader` without error.
- [ ] Writer refuses existing paths, writes atomically, preserves Decimal OHLC and fractional volume.
- [ ] All existing tests (incl. boundary and CLI guard tests) pass; strict TDD order observed.

## Resolved defaults (automatic mode)

- Directory semantics for `--bars-out` (vs single file): adopted — mirrors `SnapshotWriter` and existing `fixtures/backtest/` layout; avoids a second flag.
- `fixture_version = end.isoformat()`: adopted for convention consistency; `JsonFixtureReader` treats it as opaque.
- No `provenance.json`: the `--out` context artifact already anchors run provenance.
