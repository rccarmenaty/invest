# Delta for Trading System

## ADDED Requirements

### Requirement: Authoritative replay window and bar partition

Backtest replay MUST use the context's declared generation span as its replay window and MUST NOT derive or shrink it from bar extrema or context coverage. Bars before the span MUST be classified as warmup, bars inside it as replay input, and bars after it MUST cause a deterministic input error. At least one in-window replay session MUST be present.

#### Scenario: Partition warmup and replay bars

- GIVEN a declared span and bars both before and inside it
- WHEN replay input is prepared
- THEN pre-span bars MUST be warmup and in-span bars MUST be replay input

#### Scenario: Reject post-span bars

- GIVEN any fixture bar is dated after the declared span end
- WHEN replay input is prepared
- THEN preparation MUST fail with a deterministic input error

#### Scenario: Require an in-window session

- GIVEN bars exist only before the declared span
- WHEN replay input is prepared
- THEN preparation MUST fail before replay starts

### Requirement: Warmup bars are history-only

Warmup bars MAY be supplied to a scanner only as history for an in-window replay date. The harness MUST NOT emit decisions, entries, exits, validation results, context outcomes, equity observations, or other portfolio events before the span start.

#### Scenario: First replay date sees warmup history

- GIVEN warmup bars precede the first in-window replay session
- WHEN the scanner evaluates that session
- THEN it MUST receive history through that session, including the warmup bars

#### Scenario: No pre-span events

- GIVEN a fixture contains pre-span warmup bars
- WHEN replay completes
- THEN every decision, validation, trade, context, and portfolio event MUST be dated on or after the span start

### Requirement: Full-window fixture context completeness

Before replay, the harness MUST apply `require_complete` across every in-window replay session in the full declared span and every symbol present in the fixture. It MUST NOT reduce this matrix to observed context coverage.

#### Scenario: In-window gap fails closed

- GIVEN one fixture symbol lacks context on one in-window replay session
- WHEN completeness is checked for the declared window
- THEN replay MUST fail before any decision or portfolio event

## MODIFIED Requirements

### Requirement: Daily equity summary and split-date metrics

The report MUST include a deterministic daily equity summary without requiring full equity-curve serialization. Summary fields MUST include starting equity, ending equity, min/max equity, max drawdown, total return, and covered trading-day count. The report MUST require an explicit split date for IS/OOS reporting and MUST classify trades by entry date: entries before the split are IS; entries on or after the split are OOS. The split date MUST be validated using only in-window replay dates under a deterministic acceptance policy; warmup or post-span bars MUST NOT make it valid.
(Previously: Split-date validation used the undifferentiated replay input range.)

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

- GIVEN a missing, malformed, or disallowed split date under the in-window replay-date policy
- WHEN `invest-backtest` runs
- THEN it MUST print one machine-readable error record and exit non-zero

#### Scenario: Warmup date cannot validate split

- GIVEN a split date appears only among pre-span warmup bars
- WHEN `invest-backtest` validates it
- THEN it MUST fail closed before replay
