# Delta for Sharadar Market Context Generator

## ADDED Requirements

### Requirement: Scanner-sufficient warmup fetch

Core generation MUST request at least 253 trading sessions of bar history, sharing `MomentumSelectionScanner.HISTORY_DAYS` rather than defining a divergent value. The request MUST be bounded by each symbol's listing date and MUST NOT fabricate unavailable observations.

#### Scenario: Full-history symbol receives scanner depth

- GIVEN a symbol was listed at least 253 sessions before its first replay evaluation
- WHEN Core generation fetches its bars
- THEN the requested history depth MUST be at least 253 trading sessions

#### Scenario: Listing date bounds warmup

- GIVEN a symbol was listed fewer than 253 sessions before its first replay evaluation
- WHEN Core generation fetches its bars
- THEN the request MUST start no earlier than the listing date
- AND insufficient observations MUST remain a scanner-level history outcome

## MODIFIED Requirements

### Requirement: Deterministic schema output

The generator SHALL write one versioned market-context document accepted unchanged by `BacktestContextJsonReader`. The document MUST declare a required top-level generation span. It MUST deterministically serialize the span, symbols, and windows; missing or malformed span data MUST invalidate the artifact without inference or fallback. When bars output is requested, the context artifact and bars fixture MUST form one pair governed by that declared span.
(Previously: Deterministic output contained symbols and windows but declared no authoritative generation span.)

#### Scenario: Reproduce generated JSON

- GIVEN identical validated inputs, configuration, and date range
- WHEN generation runs twice
- THEN both context files MUST be byte-identical and reader-valid

#### Scenario: Reject absent or malformed span

- GIVEN a generated artifact has a missing, empty, malformed, or inverted span
- WHEN output validation or reading occurs
- THEN it MUST be rejected with no usable context artifact

#### Scenario: Pair bars output with the declared span

- GIVEN generation writes both context and bars outputs
- WHEN the pair is read for replay
- THEN the context MUST declare the requested generation span
- AND the bars fixture MAY include pre-span warmup bars governed by that span
