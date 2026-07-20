# Delta for Sharadar SEP Market Data

## Purpose

Preserve strict dense coverage for direct Sharadar replay while adding an explicit context-only sparse-observation contract and restoring adjusted OHLC containment without repairing invalid raw rows.

## MODIFIED Requirements

### Requirement: Deterministic OHLC adjustment

Raw SEP OHLC prices MUST be positive and finite and MUST satisfy `low <= open <= high` and `low <= close <= high` before adjustment; a raw relationship violation MUST fail closed with reason `malformed-response`. For each valid raw bar, open, high, and low MUST first be adjusted using factor `closeadj/close`, computed and applied with exact `Decimal` arithmetic, while adjusted close MUST equal `closeadj`. After that arithmetic, the final adjusted high MUST equal the maximum and the final adjusted low MUST equal the minimum of the four adjusted OHLC values. This re-enveloping MUST use no tolerance threshold and MUST NOT change adjusted open, adjusted close, the adjustment factor, Decimal precision, or `DailyBar` shape.

(Previously: open, high, and low were adjusted independently without a final deterministic envelope restoration, allowing Decimal drift to place adjusted open or close outside adjusted low/high.)

#### Scenario: Adjustment factor scales candidate values

- GIVEN a raw SEP bar with valid `close`, `closeadj`, `open`, `high`, and `low`
- WHEN the reader adjusts the bar
- THEN candidate adjusted open, high, and low MUST equal their raw values multiplied by `closeadj/close` using exact `Decimal` arithmetic
- AND adjusted close MUST equal `closeadj`

#### Scenario: Adjusted drift is re-enveloped without tolerance

- GIVEN a raw-valid SEP bar whose independent Decimal adjustment places adjusted open or close outside adjusted low/high by `1E-27` or any other magnitude
- WHEN the reader finalizes the adjusted bar
- THEN final adjusted high MUST be the maximum of adjusted open, high, low, and close
- AND final adjusted low MUST be the minimum of adjusted open, high, low, and close
- AND the reader MUST NOT apply a tolerance threshold

#### Scenario: Unadjusted valid bar is unchanged

- GIVEN a raw-valid bar where `closeadj` equals `close`
- WHEN adjustment and re-enveloping are applied
- THEN final OHLC values MUST equal their raw input values exactly

#### Scenario: Raw OHLC violation fails before adjustment

- GIVEN a raw SEP row where `low > high` or open or close lies outside `[low, high]`
- WHEN raw row validation runs
- THEN the fetch MUST fail with reason `malformed-response`
- AND the reader MUST NOT repair or adjust that row

## ADDED Requirements

### Requirement: Explicit context-only sparse SEP observations

The system MUST expose an explicit context-only SEP observation seam distinct from the default strict `fetch_range` contract. A sparse request MUST accept per-symbol and per-cohort missing XNYS sessions only when every returned row is structurally valid, every `(symbol, date)` pair is unique, every returned date is an expected XNYS session within that request's range, and every requested symbol has at least one returned row. Missing required columns, short rows, duplicate `(symbol, date)` pairs, invalid prices or raw OHLC relationships, out-of-range or non-session dates, an empty result, or a requested symbol with no rows MUST fail closed without partial bars. Results MUST remain deterministically sorted by symbol and date.

The default `fetch_range` used by direct `invest-backtest --source sharadar` MUST retain strict dense coverage: every requested symbol MUST be present, per-symbol date sets MUST be equal, and their date union MUST equal every expected XNYS session in the requested range. Direct replay MUST NOT use the context-only sparse seam.

#### Scenario: Structurally valid ragged cohort is accepted

- GIVEN a context-only SEP request where every requested symbol has at least one valid row but symbols and the cohort omit different expected sessions
- WHEN the sparse-observation seam validates the result
- THEN it MUST return all observed bars in deterministic symbol-and-date order
- AND it MUST NOT require equal per-symbol date sets or complete per-cohort session coverage

#### Scenario: Requested symbol with no observations fails closed

- GIVEN a context-only SEP request where one requested symbol has no returned row
- WHEN the sparse-observation seam validates the result
- THEN it MUST fail with reason `symbol-missing-at-fetch` naming the missing symbol
- AND it MUST return no partial bars

#### Scenario: Sparse mode preserves structural guards

- GIVEN a context-only SEP result with a missing required field, short row, duplicate `(symbol, date)`, invalid raw price relationship, or date outside the requested XNYS sessions
- WHEN the sparse-observation seam validates the result
- THEN it MUST fail with reason `malformed-response`
- AND it MUST return no partial bars

#### Scenario: Direct replay remains strict

- GIVEN a default `fetch_range` request whose returned bars omit an expected session for any symbol or have unequal per-symbol date sets
- WHEN strict validation runs for direct Sharadar replay
- THEN it MUST fail with reason `malformed-response`
- AND it MUST NOT fall back to context-only sparse semantics
