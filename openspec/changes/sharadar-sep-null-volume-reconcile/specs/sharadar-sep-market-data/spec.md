# Delta for Sharadar SEP Market Data

## MODIFIED Requirements

### Requirement: Fractional SEP volume preservation

The reader MUST preserve every non-null, non-negative SEP volume as canonical `Decimal` in `DailyBar.volume` without rounding, truncation, or quantization. When SEP supplies an explicit `null` only for `volume` on an otherwise valid row, the reader MUST interpret that value as `Decimal("0")` and MUST retain the bar. Negative volume, an absent volume field, or any invalid required non-volume field MUST fail closed with reason `malformed-response` and no partial bars. Public fetch interfaces, `FixtureInputs`, `DailyBar` shape, OHLC adjustment, pagination, chunking, ordering, and backtest-only boundaries MUST remain unchanged.

(Previously: every valid SEP volume had to be non-null; fractional values were preserved and negative values failed closed.)

#### Scenario: Reconcile a volume-only null as a retained zero-volume bar

- GIVEN an SEP row for an XNYS session with valid ticker, date, OHLC, and adjusted close, and explicit `volume=null`
- WHEN the reader completes `fetch` or `fetch_range`
- THEN it MUST retain that session's `DailyBar` with `volume == Decimal("0")`
- AND the bar MUST participate normally in complete-universe and complete-date coverage

#### Scenario: Preserve valid integer and fractional volume

- GIVEN SEP rows whose non-negative volumes are an integer and `48037.936`
- WHEN the reader constructs their `DailyBar` values
- THEN each `DailyBar.volume` MUST be an exact `Decimal` equal to its source value
- AND neither value MAY be rounded, truncated, or quantized

#### Scenario: Reject negative volume

- GIVEN an SEP row whose volume is negative
- WHEN response validation runs
- THEN the fetch MUST fail with reason `malformed-response`
- AND no partial bars MUST be returned

#### Scenario: Reject an absent volume field

- GIVEN an SEP response whose required volume column or row value is absent
- WHEN response validation runs
- THEN the fetch MUST fail with reason `malformed-response`
- AND no partial bars MUST be returned

#### Scenario: Reject a null or invalid non-volume field

- GIVEN an SEP row whose volume is valid but another required field is null or invalid
- WHEN response validation runs
- THEN the fetch MUST fail with reason `malformed-response`
- AND no partial bars MUST be returned

#### Scenario: Preserve public behavior outside null-volume reconciliation

- GIVEN otherwise identical valid SEP responses
- WHEN the changed reader produces bars through `fetch` or `fetch_range`
- THEN method signatures, return types, OHLC values, adjustments, ordering, pagination, and chunk merging MUST remain unchanged
- AND no live, broker, execution, or scanner path MAY use the reader

### Requirement: Deterministic OHLC adjustment

Per-bar open/high/low MUST be computed as the raw value times factor `closeadj/close` with exact Decimal arithmetic, then minimally re-enveloped before constructing `DailyBar`: high MUST become `max(high, open, close, low)` and low MUST become `min(low, open, close, high)`, so every adjusted bar satisfies `low <= min(open, close)` and `high >= max(open, close)`. The re-envelope MUST NOT alter open or close, and adjusted values MUST deviate from the exact Decimal products only when the exact products themselves violate the OHLC envelope (Decimal rounding/ULP drift, e.g. raw `high == close` combined with a fractional `closeadj/close` ratio). The adjustment MUST remain deterministic, and `DailyBar`'s shape MUST remain unchanged.

(Previously: open/high/low had to equal the raw value times `closeadj/close` exactly, with no re-envelope; exact-product bars whose Decimal drift broke the OHLC envelope were emitted as-is and later failed `JsonFixtureReader` validation. Scope amended during review — see REL-101/REL-102.)

#### Scenario: Adjustment factor scales open/high/low

- GIVEN a raw SEP bar with `close`, `closeadj`, `open`, `high`, `low` whose exact Decimal products already satisfy the OHLC envelope
- WHEN the reader builds the `DailyBar`
- THEN open/high/low MUST equal the raw value times `closeadj/close` exactly, computed with Decimal precision, with no re-envelope deviation

#### Scenario: Unadjusted bar is unchanged

- GIVEN a bar where `closeadj` equals `close`
- WHEN the adjustment is applied
- THEN open/high/low MUST equal their raw input values exactly

#### Scenario: Envelope drift clamps adjusted high minimally

- GIVEN the live GSBD 2024-12-13 bar shape where raw `high` equals raw `close` (open `12.83`, high `12.87`, low `12.75`, close `12.87`, closeadj `9.711`) and the exact Decimal product for high falls below `closeadj` by rounding drift
- WHEN the reader builds the `DailyBar`
- THEN adjusted high MUST equal the maximum of the four adjusted candidates — exactly `closeadj` here — and not any wider value
- AND adjusted open and low MUST remain their exact Decimal products
