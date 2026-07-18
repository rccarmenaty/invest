# Delta for Trading System

## ADDED Requirements

### Requirement: Canonical daily-bar volume

`DailyBar.volume` MUST be non-negative `Decimal`. Alpaca and JSON fixture adapters MUST preserve valid source volume without rounding or truncation. Negative volume MUST be rejected before domain processing. This change MUST NOT add providers or live-execution behavior.

#### Scenario: Preserve Alpaca fractional volume

- GIVEN an Alpaca bar with valid fractional volume
- WHEN the adapter constructs a `DailyBar`
- THEN its volume MUST equal the source value as an exact `Decimal`

#### Scenario: Reject negative fixture volume

- GIVEN a fixture bar with negative volume
- WHEN fixture validation runs
- THEN validation MUST fail before scanning
- AND no `DailyBar` MUST be produced for that input

## MODIFIED Requirements

### Requirement: Fetch-to-fixture snapshot semantics

Fetched bars MUST be written as dated snapshots consumable by `JsonFixtureReader`. Integral volume MUST remain a JSON number; fractional volume MUST use an exact decimal string. Both MUST restore equivalent canonical `Decimal`, with deterministic repeated round trips.
(Previously: Snapshot semantics had no fractional-volume representation or round-trip guarantee.)

#### Scenario: Snapshot feeds the unchanged scan pipeline

- GIVEN a completed fetch for an as-of date
- WHEN the adapter writes the snapshot
- THEN `JsonFixtureReader` MUST load it without scanner contract changes
- AND `MomentumScanner` MUST run unchanged against it

#### Scenario: Fractional volume round-trips exactly

- GIVEN a validated bar with fractional volume `48037.936`
- WHEN it is snapshotted and loaded through `JsonFixtureReader`
- THEN the loaded volume MUST equal `Decimal("48037.936")` exactly
- AND repeated round trips MUST serialize identically

#### Scenario: Integral snapshot compatibility

- GIVEN a validated bar with integral volume
- WHEN it is snapshotted
- THEN volume MUST remain a JSON number accepted by `JsonFixtureReader`
