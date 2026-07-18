# Delta for Sharadar Market Context Generator

## ADDED Requirements

### Requirement: Optional bars fixture export

The standalone generator entrypoint MAY accept an optional `--bars-out DIR` flag. When omitted, generator behavior MUST be unchanged — only the `--out` context file is written. When present, the generator MUST atomically write a `JsonFixtureReader`-compatible fixture pair (`DIR/universe.json` + `DIR/bars.json`) from the SEP bars already fetched during context generation, MUST make no additional Sharadar API call to produce it, and MUST still write the `--out` context file. The write MUST use staging + atomic replace so an interrupted write leaves no partial fixture at the destination.

#### Scenario: Flag omitted preserves existing behavior

- GIVEN a valid `invest-generate-context` invocation without `--bars-out`
- WHEN generation completes
- THEN only the `--out` context file MUST be written
- AND no fixture files MUST be created

#### Scenario: Flag present emits both context and fixture outputs

- GIVEN a valid `invest-generate-context` invocation with `--bars-out DIR`
- WHEN generation completes
- THEN `DIR/universe.json` and `DIR/bars.json` MUST both be written
- AND the `--out` context file MUST also be written
- AND no additional SEP API call MUST be made to produce the fixture

#### Scenario: Interrupted fixture write leaves no partial output

- GIVEN `--bars-out DIR` is set and the write process is interrupted mid-write
- WHEN the destination is inspected afterward
- THEN `DIR` MUST NOT contain a partially written `universe.json` or `bars.json`

### Requirement: Fixture pair schema and round-trip compatibility

The emitted fixture pair MUST conform to the `JsonFixtureReader` contract. `bars.json` MUST match `{fixture_version, bars: [{symbol, date, open, high, low, close, volume}]}`; `universe.json` MUST match `{fixture_version, symbols: [...]}`. Both files MUST share `fixture_version == end.isoformat()`. OHLC values MUST serialize as decimal strings; whole-number volume MUST collapse to an integer. The pair MUST load without error via `JsonFixtureReader.load`, with no duplicate `(symbol, date)` pairs, strictly increasing dates per symbol, and `set(universe.symbols) == set(bar symbols)`.

#### Scenario: Emitted pair matches the fixture schema

- GIVEN a completed `--bars-out DIR` write
- WHEN `universe.json` and `bars.json` are inspected
- THEN their shapes MUST match the `_BarsPayload`/universe schema
- AND both `fixture_version` fields MUST equal `end.isoformat()`

#### Scenario: Emitted pair round-trips through JsonFixtureReader

- GIVEN a completed `--bars-out DIR` write
- WHEN `JsonFixtureReader().load(DIR/universe.json, DIR/bars.json)` runs
- THEN it MUST load without error
- AND per-symbol dates MUST be strictly increasing with no duplicate `(symbol, date)` entries

#### Scenario: Decimal and fractional-volume serialization is preserved

- GIVEN fetched bars containing fractional volume and non-integer OHLC values
- WHEN the fixture pair is written
- THEN OHLC values MUST serialize as decimal strings
- AND whole-number volumes MUST collapse to integers while fractional volumes MUST be preserved

### Requirement: Ragged coverage and fail-closed symbol-set invariant

The writer MUST preserve ragged per-symbol coverage (partial windows from IPO or delisting) by emitting only each symbol's available bars, and the resulting pair MUST still load cleanly. The writer MUST enforce `set(universe.symbols) == set(bar symbols)`; on violation, or on empty bars, it MUST raise and MUST NOT write a fixture to the destination.

#### Scenario: Partial-window symbols are preserved and loadable

- GIVEN a symbol with a mid-range IPO or delisting during the requested window
- WHEN the fixture pair is written
- THEN only that symbol's available bars MUST be emitted
- AND the pair MUST still load via `JsonFixtureReader.load` without error

#### Scenario: Symbol-set mismatch fails closed

- GIVEN a universe/bars symbol-set mismatch or empty bars at write time
- WHEN the writer runs
- THEN it MUST raise
- AND it MUST NOT write any fixture file to the destination
