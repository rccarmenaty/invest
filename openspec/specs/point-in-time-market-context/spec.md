# Point-in-Time Market Context

## Purpose

Define externally prepared, date-effective context without implying provider capability.

## Requirements

### Requirement: Context authority and coverage

Replay MUST receive externally prepared context and MUST NOT fetch, infer, or provider-attribute it. Validation MUST resolve one eligibility and blocker state per requested date/symbol before replay.

#### Scenario: Complete matrix

- GIVEN context covers every requested date and symbol
- WHEN coverage is validated
- THEN every pair MUST resolve to one eligibility and blocker state

#### Scenario: Invalid matrix

- GIVEN a pair is missing, malformed, unsupported, or contradictory
- WHEN coverage is validated
- THEN validation MUST fail before replay

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
