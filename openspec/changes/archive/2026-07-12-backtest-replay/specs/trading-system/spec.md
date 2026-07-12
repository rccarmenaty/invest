# Delta for trading-system

## ADDED Requirements

### Requirement: Bulk historical range fetch

`AlpacaMarketDataReader` MUST add `fetch_range(universe, start, end)` returning validated bars for `[start, end]` in the existing schema. Additive only: `fetch(universe, as_of)` MUST NOT change. Failures MUST use the existing fetch error taxonomy.

#### Scenario: Range fetch returns validated multi-day bars

- GIVEN a universe and a date range
- WHEN `fetch_range` runs successfully
- THEN it MUST return validated bars for every trading day in range, in the existing schema

#### Scenario: Existing fetch is unchanged

- GIVEN the existing `fetch(universe, as_of)` call
- WHEN `fetch_range` is added
- THEN `fetch`'s inputs, outputs, and errors MUST stay identical to before this change

#### Scenario: Range fetch failure uses the existing taxonomy

- GIVEN an auth, network, rate-limit, or malformed-response failure during a range fetch
- WHEN it occurs
- THEN it MUST fail with the matching existing reason code and write no partial output

### Requirement: Deterministic day-by-day replay without look-ahead

The harness MUST evaluate the pure `MomentumScanner`/sizing functions once per historical day, using only bars dated on or before that day. The same range replayed twice MUST yield identical trade logs and metrics.

#### Scenario: Replaying the same range twice is identical

- GIVEN the same historical bar range and universe
- WHEN the harness replays it twice
- THEN both runs MUST produce byte-identical trade logs and metrics

#### Scenario: Each day sees only its own history

- GIVEN a replay in progress on day N
- WHEN the harness evaluates day N
- THEN it MUST pass only bars dated on or before day N to the scanner/sizing functions

### Requirement: Look-ahead prevention is a testable property

A fixture-based test MUST prove that day N's recorded decision is unaffected by bars dated after day N.

#### Scenario: Mutating future bars does not change a past decision

- GIVEN a fixture replay producing a recorded decision for day N
- WHEN bars dated after day N are mutated and the replay reruns
- THEN day N's recorded decision MUST NOT change

### Requirement: Day-0-only mechanics labeling

Every backtest report MUST carry an explicit label stating it measures current day-0 `CANDIDATE` mechanics, not SPEC's confirmed-entry thesis.

#### Scenario: Report carries the day-0 label

- GIVEN a completed backtest run
- WHEN the report is produced
- THEN it MUST include an explicit field/text stating the results measure day-0 CANDIDATE mechanics, not confirmed-entry

### Requirement: Survivorship-bias disclaimer

Every backtest report MUST carry an explicit, unavoidable disclaimer that the universe is a fixed historical screen, not point-in-time index membership.

#### Scenario: Report carries the survivorship disclaimer

- GIVEN a completed backtest run
- WHEN the report is produced
- THEN it MUST include an explicit disclaimer stating the universe is a fixed historical screen, not point-in-time membership

### Requirement: Cost model reported as approximation

The harness MUST apply fixed-bps slippage, zero commission, and a flat tax haircut per trade. Every report MUST label these as an approximation, not precision.

#### Scenario: Report labels the cost model as approximate

- GIVEN a completed backtest run using this cost model
- WHEN the report is produced
- THEN it MUST label the cost figures as an approximation, not precise costs

### Requirement: Pure backtest metrics

`backtest_metrics.py` MUST compute hit rate, expectancy, max drawdown, and trade count as pure functions of a trade log, deterministic given the same log.

#### Scenario: Same trade log yields identical metrics

- GIVEN a fixed trade log
- WHEN metrics are computed twice
- THEN all four metrics MUST be identical both times

### Requirement: `invest-backtest` CLI never touches BrokerPort

`invest-backtest` MUST read a bulk fixture/snapshot, replay it, and print a machine-readable report with metrics plus both mandatory labels, in the CLI's established single-record-on-failure style. It MUST NOT construct or call `BrokerPort`.

#### Scenario: Successful run prints one machine-readable report

- GIVEN a valid bulk fixture/snapshot
- WHEN `invest-backtest` runs
- THEN it MUST print one report with metrics and both mandatory labels, and call `BrokerPort` zero times

#### Scenario: Failure prints one machine-readable record

- GIVEN an invalid or missing fixture/snapshot
- WHEN `invest-backtest` runs
- THEN it MUST print exactly one machine-readable error record and exit non-zero

### Requirement: Out-of-scope guard

This change MUST NOT introduce gap-trading strategy logic, confirmation-service logic, or any live-trading code path.

#### Scenario: No gap-trading, confirmation, or live-trading code is added

- GIVEN the repository after this change
- WHEN the source tree is reviewed
- THEN no gap-trading strategy module, no confirmation-service module, and no live-trading URL/branch MUST exist
