# Delta for Sharadar Actions Reference Data

## Purpose

Accept live exact-zero mapped dividend values without weakening validation for split ratios, invalid valued actions, or empty ACTIONS responses.

## MODIFIED Requirements

### Requirement: Typed corporate-action events

Each returned event MUST contain a ticker, effective date, event kind, and optional value. The reader MUST map the ACTIONS literals `split`, `adrratiosplit`, `dividend`, `spinoffdividend`, `delisted`, `regulatorydelisting`, `voluntarydelisting`, `bankruptcyliquidation`, `tickerchangeto`, and `tickerchangefrom` to typed events: `split` and `adrratiosplit` MUST both produce a split event; `dividend` and `spinoffdividend` MUST both produce a dividend event; `delisted`, `regulatorydelisting`, `voluntarydelisting`, and `bankruptcyliquidation` MUST all produce a delisted event; `tickerchangeto` and `tickerchangefrom` MUST both produce a ticker-change event, without preserving directionality. Every present monetary or ratio value MUST be represented as an exact `Decimal`, including values supplied as JSON floats, coerced without precision loss. A mapped dividend MUST have a present, finite, non-negative value and MUST accept exact zero as `Decimal("0")`. A mapped split MUST have a present, finite value strictly greater than zero. A negative, absent, or non-finite value on any mapped dividend or split MUST fail closed with reason `malformed-response`. A delisted or ticker-change row MAY carry any source value; the reader MUST accept the row and normalize its value to absent.

(Previously: exact zero was accepted for both mapped dividend and mapped split events; the corrected contract accepts zero only for mapped dividends and keeps mapped split ratios strictly positive.)

#### Scenario: Mapped literals parse to their normalized kind

- GIVEN ACTIONS rows using each mapped literal
- WHEN the reader converts the rows to events
- THEN `split` and `adrratiosplit` rows MUST produce split events
- AND `dividend` and `spinoffdividend` rows MUST produce dividend events
- AND the mapped delisting literals MUST produce delisted events
- AND `tickerchangeto` and `tickerchangefrom` rows MUST produce ticker-change events

#### Scenario: Float values coerce to exact Decimals

- GIVEN a dividend value `9.00009000090001` and a split ratio `0.04545`, both supplied as JSON floats
- WHEN the reader converts the rows to events
- THEN each event value MUST be an exact `Decimal` matching the source float's full decimal representation

#### Scenario: Valueless kinds accept and drop any source value

- GIVEN a delisted or ticker-change row carrying any source value
- WHEN the reader converts the row to an event
- THEN it MUST produce the event with an absent value
- AND it MUST NOT fail the fetch

#### Scenario: Exact-zero dividend is retained

- GIVEN the mapped live row `RVPH | 2026-02-23 | dividend | 0`
- WHEN the reader converts the row
- THEN it MUST produce a dividend event with value `Decimal("0")`
- AND it MUST NOT abort the containing paginated ACTIONS fetch

#### Scenario: Exact-zero split fails closed

- GIVEN a `split` or `adrratiosplit` row with an exact-zero ratio
- WHEN the reader validates the row
- THEN it MUST fail with reason `malformed-response`
- AND it MUST return no partial events

#### Scenario: Invalid valued actions fail closed

- GIVEN a mapped dividend or split row whose value is negative, absent, or non-finite
- WHEN the reader validates the row
- THEN it MUST fail with reason `malformed-response`
- AND it MUST return no partial events
