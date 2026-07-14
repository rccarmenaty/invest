# Delta for Trading System

## ADDED Requirements

### Requirement: Backtest strategy selection

`invest-backtest` MUST accept a `--strategy` flag with values `benchmark` and `core`, defaulting to `benchmark` when omitted. `BacktestRun` MUST depend on a `ScannerPort` abstraction rather than the concrete `MomentumScanner` class, so either strategy runs through the identical unmodified replay harness. Selecting `benchmark` (or omitting the flag) MUST reproduce today's scan decisions, trade logs, and metrics byte-for-byte.

#### Scenario: Default and explicit benchmark are identical

- GIVEN the same fixtures and universe
- WHEN `invest-backtest` runs once with no `--strategy` flag and once with `--strategy benchmark`
- THEN both runs MUST produce byte-identical scan decisions, trade logs, and metrics

#### Scenario: Core strategy replays through the same harness

- GIVEN the same fixtures and universe
- WHEN `invest-backtest --strategy core` runs
- THEN it MUST replay day-by-day through the unmodified `BacktestRun` harness
- AND its output MUST use the same report shape as the benchmark strategy

#### Scenario: Unknown strategy value is rejected

- GIVEN `--strategy` is set to a value other than `benchmark` or `core`
- WHEN `invest-backtest` starts
- THEN it MUST fail with a machine-readable error and exit non-zero before any replay begins

### Requirement: Strategy flag stays backtest-only

The `--strategy` flag MUST exist only on the `invest-backtest` CLI parser. `invest-execute` and the day-0 scan CLI MUST NOT expose or accept a strategy-selection flag.

#### Scenario: Execute and scan parsers reject the flag

- GIVEN the `invest-execute` and scan CLI parsers
- WHEN their argument definitions are inspected
- THEN neither MUST define a `--strategy` argument
