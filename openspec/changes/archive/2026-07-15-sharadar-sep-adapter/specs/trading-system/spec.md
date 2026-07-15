# Delta for trading-system

## ADDED Requirements

### Requirement: Backtest data source selection

`invest-backtest` MUST accept `--source {fixture,alpaca,sharadar}` on `_backtest_parser`. Omitting `--source` MUST preserve today's implicit inference (fixture via `--bars`, Alpaca via `--start`/`--end`) byte-identically. Selecting `sharadar` MUST route the fetch to `SharadarMarketDataReader.fetch_range`. An unknown `--source` value MUST fail closed before any fetch or replay.

#### Scenario: Default inference is unchanged

- GIVEN the same fixtures/universe/date arguments as before this change
- WHEN `invest-backtest` runs without `--source`
- THEN it MUST select fixture or Alpaca exactly as it did before this change, byte-identically

#### Scenario: Explicit sharadar source routes to the new reader

- GIVEN `--source sharadar` with a universe and date range
- WHEN `invest-backtest` runs
- THEN it MUST fetch bars via `SharadarMarketDataReader.fetch_range`

#### Scenario: Unknown source value fails closed

- GIVEN `--source` set to a value other than `fixture`, `alpaca`, or `sharadar`
- WHEN `invest-backtest` starts
- THEN it MUST fail with a machine-readable error and exit non-zero before any fetch or replay begins

### Requirement: Source flag stays backtest-only

The `--source` flag MUST exist only on the `invest-backtest` CLI parser. `invest-execute` and the day-0 scan CLI MUST NOT define or accept a source-selection flag.

#### Scenario: Execute and scan parsers reject the flag

- GIVEN the `invest-execute` and scan CLI parsers
- WHEN their argument definitions are inspected
- THEN neither MUST define a `--source` argument
