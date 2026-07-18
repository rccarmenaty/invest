# Point-in-Time Market Context

## Purpose

Define externally prepared, date-effective context without implying provider capability.

## Requirements

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

### Requirement: Context authority and coverage

Replay MUST receive externally prepared context and MUST NOT fetch, infer, or provider-attribute it. For every requested date/symbol inside the declared generation span, `status`, `require_complete`, and `eligible_symbols` MUST resolve one eligibility and blocker state or fail closed. Dates outside the declared span MUST NOT acquire context authority from incidental coverage.

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

### Requirement: Point-in-time eligibility

Eligibility on D MUST use records effective by D only; future records MUST NOT influence it.

#### Scenario: Future mutation

- GIVEN eligibility recorded for D
- WHEN post-D records change
- THEN D's decision MUST remain identical

### Requirement: Inclusive blockers and outcomes

`corporate-action` and `earnings-context-missing` windows MUST include both endpoints. Blocked candidates MUST produce `context-entry-blocked`; unsafe positions MUST produce `context-position-forced-closed`. Outcomes MUST retain reason `corporate-action`, `earnings-context-missing`, or `symbol-ineligible`, separate from portfolio gates.

#### Scenario: Blocker boundaries

- GIVEN a blocker from A through B
- WHEN entry is evaluated on A, inside, or on B
- THEN it MUST be context-blocked with the applicable reason

#### Scenario: Unsafe position

- GIVEN an open position becomes blocked or ineligible on D
- WHEN D is processed
- THEN its forced-close outcome, reason, symbol, and date MUST be visible

### Requirement: Conservative forced close

A forced close MUST precede entries on the first unsafe date, use no future data, and choose the position's least favorable admissible same-day price. Identical inputs MUST yield identical exits.

#### Scenario: Repeat exit

- GIVEN identical bars, context, and a position unsafe on D
- WHEN replay runs twice
- THEN forced-close records MUST match and use D's least favorable admissible same-day price
