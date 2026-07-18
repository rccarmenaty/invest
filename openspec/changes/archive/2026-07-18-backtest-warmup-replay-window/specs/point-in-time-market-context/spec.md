# Delta for Point-in-Time Market Context

## ADDED Requirements

### Requirement: Authoritative generation span

`MarketContext` MUST carry one authoritative, inclusive generation span and consumers MUST NOT infer that span from bars or per-symbol coverage. The span MUST represent at least one date and its start MUST be on or before its end.

#### Scenario: Valid span is retained

- GIVEN context is built for a non-empty span from A through B
- WHEN the context is passed to a consumer
- THEN it MUST expose A and B as its authoritative inclusive bounds

#### Scenario: Invalid span is rejected

- GIVEN a span is empty or its start is after its end
- WHEN context construction or loading is attempted
- THEN it MUST fail before a usable `MarketContext` is produced

## MODIFIED Requirements

### Requirement: Context authority and coverage

Replay MUST receive externally prepared context and MUST NOT fetch, infer, or provider-attribute it. For every requested date/symbol inside the declared generation span, `status`, `require_complete`, and `eligible_symbols` MUST resolve one eligibility and blocker state or fail closed. Dates outside the declared span MUST NOT acquire context authority from incidental coverage.
(Previously: Validation required complete requested date/symbol coverage without an authoritative generation span.)

#### Scenario: Complete matrix

- GIVEN context covers every requested date and symbol inside its declared span
- WHEN status, completeness, or eligible symbols are requested
- THEN every pair MUST resolve to one eligibility and blocker state

#### Scenario: Invalid matrix

- GIVEN an in-span pair is missing, malformed, unsupported, or contradictory
- WHEN status, completeness, or eligible symbols are requested
- THEN the operation MUST fail before replay proceeds

#### Scenario: Outside-span authority is rejected

- GIVEN coverage data exists for a date outside the declared span
- WHEN context status is requested for that date
- THEN the request MUST fail closed rather than treat that coverage as authoritative
