# Delta for Sharadar SEP Market Data

## ADDED Requirements

### Requirement: Fractional SEP volume preservation

The reader MUST preserve non-negative SEP volume as canonical `Decimal` in `DailyBar.volume` without rounding, truncation, or quantization. Negative volume MUST fail closed. OHLC, adjustments, pagination, and unrelated reconciliation MUST remain unchanged.

#### Scenario: Preserve valid fractional volume

- GIVEN an SEP row whose adjusted volume is `48037.936`
- WHEN the reader constructs its `DailyBar`
- THEN `DailyBar.volume` MUST equal `Decimal("48037.936")` exactly

#### Scenario: Reject negative volume

- GIVEN an SEP row whose volume is negative
- WHEN response validation runs
- THEN the fetch MUST fail with reason `malformed-response`
- AND no partial bars MUST be returned

#### Scenario: Preserve unrelated SEP behavior

- GIVEN otherwise identical SEP rows
- WHEN the changed reader produces bars
- THEN OHLC, adjustments, and ordering MUST remain unchanged
