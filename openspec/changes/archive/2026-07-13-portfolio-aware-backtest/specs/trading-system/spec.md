# Delta for Trading System

## ADDED Requirements

### Requirement: Portfolio-aware backtest accounting

The backtest harness MUST simulate finite starting capital, cash, equity, open positions, deployed capital, and closed trades across the replay range. Entries MUST size from current equity using the existing 1%-risk sizing rules and current fixed cost model. This change MUST NOT alter `MomentumScanner`, static universe semantics, cost assumptions, broker isolation, or paper-first/no-live validation gates.

#### Scenario: Overlapping entries consume finite capital

- GIVEN a replay day with multiple accepted candidates and limited cash
- WHEN entries are evaluated in deterministic order
- THEN accepted simulated positions MUST reduce available cash/deployed capacity
- AND later candidates MUST respect the updated portfolio state

#### Scenario: Capital unavailable skips entry

- GIVEN a candidate whose sized entry exceeds available buying power
- WHEN the harness evaluates the simulated entry
- THEN no position MUST open
- AND the trade log MUST record reason `insufficient-buying-power`

#### Scenario: Exits release portfolio capacity

- GIVEN an open simulated position reaches its modeled exit
- WHEN the exit is recorded
- THEN cash, equity, open positions, and deployed capital MUST update deterministically

### Requirement: Deterministic simulated gate telemetry

The harness MUST apply the existing pure pre-trade gates before simulated entry: max concurrent positions, max deployed equity, buying power, and kill-switch. Every blocked candidate MUST increment stable per-reason telemetry. Gate telemetry MUST be labeled `portfolio-gates-simulated` and MUST NOT be presented as broker/account enforcement.

#### Scenario: Gate pressure is counted by reason

- GIVEN candidates blocked by different simulated gates
- WHEN the backtest report is produced
- THEN the report MUST include deterministic counts by gate reason
- AND skipped entries MUST remain visible in the trade log

#### Scenario: Kill-switch uses prior-session equity

- GIVEN current equity breaches the 3% drawdown threshold versus prior-session equity
- WHEN later candidates are evaluated that day
- THEN simulated entries MUST be blocked with reason `kill-switch`

#### Scenario: Same replay has same telemetry

- GIVEN identical fixtures, universe, starting capital, and split date
- WHEN the replay runs twice
- THEN gate counts, trade logs, and metrics MUST be byte-identical

### Requirement: Daily equity summary and split-date metrics

The report MUST include a deterministic daily equity summary without requiring full equity-curve serialization. Summary fields MUST include starting equity, ending equity, min/max equity, max drawdown, total return, and covered trading-day count. The report MUST require an explicit split date for IS/OOS reporting and MUST classify trades by entry date: entries before the split are IS; entries on or after the split are OOS.

#### Scenario: Daily summary is observable

- GIVEN a completed replay with open and closed positions
- WHEN the report is produced
- THEN it MUST include the required daily equity summary fields
- AND repeated runs over the same inputs MUST produce identical values

#### Scenario: Trades are split by entry date

- GIVEN trades before, on, and after the split date
- WHEN IS/OOS metrics are computed
- THEN pre-split entries MUST contribute only to IS metrics
- AND split-date-or-later entries MUST contribute only to OOS metrics

#### Scenario: Invalid split date fails closed

- GIVEN a missing, malformed, or out-of-range split date for IS/OOS reporting
- WHEN `invest-backtest` runs
- THEN it MUST print one machine-readable error record and exit non-zero

### Requirement: Mandatory portfolio-backtest limitations

Every backtest report MUST preserve existing limitation labels for day-0 candidate mechanics, static universe survivorship bias, and approximate costs. It MUST additionally warn that OOS results still use the static universe, portfolio gates are simulated, and broker execution realism is out of scope. Missing market, earnings, or corporate-action data MUST fail safe rather than imply confirmed-entry or execution realism.

#### Scenario: Required limitation labels are present

- GIVEN a successful portfolio-aware backtest
- WHEN the report is rendered in any supported format
- THEN all mandatory limitation labels MUST be present and machine-readable

#### Scenario: Broker and live trading remain isolated

- GIVEN the portfolio-aware backtest executes
- WHEN the harness evaluates entries and exits
- THEN it MUST NOT construct or call `BrokerPort`
- AND it MUST NOT introduce any live-trading code path or broker-enforced backtest control
