# Delta for Trading System

## MODIFIED Requirements

### Requirement: Backtest-only reference-data adapter boundary

`SharadarTickersReader` and `SharadarActionsReader` MUST remain backtest-only adapters. Exactly one deliberate caller, the standalone Sharadar market-context generator route, MAY import and invoke them solely to write `market-context-v1` context for later backtest use. They MUST NOT be imported, invoked, or selected by broker, execution, scanner, live-trading, paper-trading, `backtest_main`, `BacktestContextJsonReader`, `MarketContext`, or `BacktestRun` paths. The generator MUST NOT alter `SharadarMarketDataReader` or existing context/replay behavior.
(Previously: No CLI source or generator route could use the reference-data readers.)

#### Scenario: Only the generator may depend on reference readers

- GIVEN the source tree and reference-reader caller allowlist
- WHEN boundary checks inspect imports and reader-name references
- THEN exactly the standalone backtest-only generator route MAY reference either reader
- AND every other protected path MUST remain denied

#### Scenario: Protected paths have no reference-data reader dependency

- GIVEN the source tree's broker, execution, scanner, live/paper trading, CLI, and protected backtest/domain modules
- WHEN boundary checks inspect imports and reader-name references
- THEN none of those paths other than the dedicated generator MUST reference `SharadarTickersReader` or `SharadarActionsReader`
- AND no existing SEP, market-context, backtest-run, or backtest-context JSON behavior MUST be altered
