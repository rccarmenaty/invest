# Delta for Trading System

## ADDED Requirements

### Requirement: Preserve existing boundaries

Context filtering MUST NOT change `MomentumScanner`, Alpaca bars, portfolio accounting, costs, broker paths, or paper-first/live gates. Alpaca MUST remain bars-only; backtests MUST make zero broker calls.

#### Scenario: Preserve behavior

- GIVEN complete context marks every symbol eligible and unblocked
- WHEN the same replay runs with context filtering
- THEN scanner outputs, accounting, costs, and ordinary exits MUST remain unchanged

#### Scenario: Preserve boundaries

- GIVEN a context-backed replay
- WHEN calls are observed
- THEN Alpaca MUST NOT supply context and `BrokerPort` MUST receive zero calls

## MODIFIED Requirements

### Requirement: Survivorship-bias disclaimer

Reports MUST show the static-universe warning unless the entire run has validated PIT date/symbol coverage. Only then MUST a machine-readable PIT statement replace it.
(Previously: Every report always warned that its universe was a fixed historical screen.)

#### Scenario: Replace warning

- GIVEN complete validated PIT coverage
- WHEN reporting succeeds
- THEN the PIT statement MUST replace the static-universe warning

#### Scenario: Reject uncovered claim

- GIVEN missing, incomplete, or invalid context
- WHEN backtest starts
- THEN it MUST fail without a success report or PIT statement

### Requirement: `invest-backtest` CLI never touches BrokerPort

`invest-backtest` MUST require externally prepared context, validate complete date/symbol coverage, replay the bulk fixture, and print one machine-readable report with metrics and labels. It MUST NOT use `BrokerPort`.
(Previously: The CLI required only a bulk fixture/snapshot and always emitted both existing mandatory labels.)

#### Scenario: Successful report

- GIVEN valid bars, split date, and complete context
- WHEN `invest-backtest` runs
- THEN it MUST print one report with metrics, labels, context outcomes, and zero broker calls

#### Scenario: Context failure

- GIVEN context is absent, incomplete, unreadable, malformed, contradictory, or unsupported
- WHEN `invest-backtest` starts
- THEN it MUST print one machine-readable context error, exit non-zero, and output no partial replay
