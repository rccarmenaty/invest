# Momentum Selection Scanner Specification

## Purpose

Define the Core 52-Week-High Momentum Breakout candidate-selection layer: a cross-sectional scanner that ranks the eligible universe by trailing momentum, filters by 52-week-high proximity and trend, and reuses the existing breakout trigger. Runs as a sibling to the benchmark scanner through the same backtest harness, with no trailing exits, regime filter, or vol sizing in scope.

## Requirements

### Requirement: Minimum history gate

The scanner MUST require at least 253 daily bars per symbol (252 for the momentum look-back plus the candidate day) before evaluating any other rule. Symbols with fewer bars MUST be rejected with reason `insufficient-history` and MUST NOT be ranked.

#### Scenario: Reject a short history

- GIVEN a symbol with fewer than 253 bars
- WHEN the scanner evaluates that symbol
- THEN it MUST be rejected with reason `insufficient-history`
- AND it MUST be excluded from momentum ranking

### Requirement: Cross-sectional momentum ranking with top-15% ceiling

For every symbol with sufficient history, the scanner MUST compute momentum return as the close price 252 trading days before the candidate day compared to the close 21 trading days before the candidate day. The scanner MUST rank all eligible symbols by this return, descending, and retain only `ceil(0.15 × ranked_pool_size)` symbols as candidates for further filtering. Ties MUST break by momentum return descending, then symbol ascending. Retained symbols not selected by rank MUST be rejected with a rank-specific reason distinct from other filter rejections.

#### Scenario: Top-15% ceiling keeps at least one candidate

- GIVEN a ranked pool of eligible symbols smaller than 7 (15% would round below 1)
- WHEN the ceiling cutoff is applied
- THEN at least 1 symbol MUST be retained for further filtering

#### Scenario: Deterministic tie-break

- GIVEN two symbols with identical momentum return at the cutoff boundary
- WHEN the ranking is computed twice
- THEN both runs MUST select the same symbol, breaking the tie by symbol ascending

#### Scenario: Reject below the momentum-rank cutoff

- GIVEN a symbol with sufficient history whose momentum rank falls outside the top-15% ceiling
- WHEN the scanner ranks the pool
- THEN it MUST be rejected with a reason identifying the momentum-rank failure

### Requirement: 52-week-high proximity filter

Each ranked candidate MUST have its candidate-day close at or above 95% of its trailing 252-day high (history excluding the candidate day). Candidates below this proximity MUST be rejected with a distinct reason before the trend filter runs.

#### Scenario: Reject on low 52-week-high proximity

- GIVEN a ranked candidate whose close is below 95% of its trailing 252-day high
- WHEN the proximity filter runs
- THEN it MUST be rejected with a reason identifying the 52-week-high proximity failure

### Requirement: Trend filter with rising SMA200

A candidate MUST satisfy close > SMA50 > SMA200 on the candidate day, and SMA200 computed over the 200 days ending the day before the candidate day MUST be strictly greater than SMA200 computed over the 200 days ending 21 days before the candidate day. The candidate day MUST be excluded from both SMA200 windows.

#### Scenario: Reject a falling or flat SMA200

- GIVEN a candidate passing the proximity filter whose SMA200 (ending t-1) is not strictly greater than SMA200 (ending t-21)
- WHEN the trend filter runs
- THEN it MUST be rejected with a reason identifying the trend-filter failure

#### Scenario: Reject a broken moving-average order

- GIVEN a candidate whose close, SMA50, and SMA200 do not satisfy close > SMA50 > SMA200
- WHEN the trend filter runs
- THEN it MUST be rejected with a reason identifying the trend-filter failure

### Requirement: 20-day-high breakout trigger reuse

A candidate surviving momentum rank, proximity, and trend filters MUST additionally close above its prior 20-trading-day high to be accepted, using the same breakout definition as the benchmark scanner.

#### Scenario: Accept a candidate passing every layer

- GIVEN a candidate passing momentum rank, proximity, and trend filters, with a close above its prior 20-day high
- WHEN the scanner evaluates the candidate
- THEN it MUST be accepted

#### Scenario: Reject a candidate failing only the breakout trigger

- GIVEN a candidate passing every prior filter but not closing above its prior 20-day high
- WHEN the scanner evaluates the candidate
- THEN it MUST be rejected with a reason identifying the breakout-trigger failure

### Requirement: Granular per-layer rejection reasons

Every non-accepted outcome MUST carry a reason identifying the exact filter layer that rejected it (history, momentum-rank, proximity, trend, or breakout-trigger), never a single generic reason for multiple layers.

#### Scenario: Rejection reason identifies the failing layer

- GIVEN candidates rejected at different filter layers in the same run
- WHEN the run completes
- THEN each rejected candidate's reason MUST distinguish which layer rejected it

### Requirement: Deterministic Decimal-only output

The scanner MUST use only `Decimal` arithmetic, no floats and no randomness, and MUST return decisions sorted by `(decision_date, symbol)`. The same universe and bars MUST always yield byte-identical decisions across repeated runs.

#### Scenario: Repeated runs are identical

- GIVEN the same universe and bar set
- WHEN the scanner runs twice
- THEN both runs MUST produce identical ordered decisions
