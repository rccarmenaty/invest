# Delta for Trading System

## ADDED Requirements

### Requirement: Backtest-only reference-data adapter boundary

`SharadarTickersReader` and `SharadarActionsReader` MUST remain backtest-only adapters. They MUST NOT be imported, invoked, or selected by broker, execution, scanner, live-trading, or paper-trading paths. This change MUST NOT add or alter a CLI source or generator path, alter `SharadarMarketDataReader`, or alter domain market-context, backtest-run, or backtest-context JSON behavior.

#### Scenario: Protected paths have no reference-data reader dependency

- GIVEN the source tree's broker, execution, scanner, live/paper trading, CLI, and protected backtest/domain modules
- WHEN boundary checks inspect imports and reader-name references
- THEN none of those paths MUST reference `SharadarTickersReader` or `SharadarActionsReader`
- AND no new CLI route or altered existing SEP, market-context, backtest-run, or backtest-context JSON behavior MUST be present
