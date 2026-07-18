# Sharadar Market Context Generator Specification

## Purpose

Generate deterministic, backtest-only `market-context-v1` files for later replay.

## Requirements

### Requirement: Broad point-in-time candidate discovery

The generator SHALL discover, deduplicate, and deterministically order TICKERS without a pre-supplied roster. It MUST preserve listing/delisting dates and reuse, not reclassify, primary-common-stock status.

#### Scenario: Discover a broad eligible candidate set

- GIVEN paginated TICKERS rows for eligible and ineligible listings
- WHEN generation starts for a date range
- THEN it MUST consider every unique returned ticker in deterministic order
- AND only primary common stocks on AMEX, ARCA, NASDAQ, or NYSE MAY pass listing eligibility

#### Scenario: Preserve historical listing status

- GIVEN a ticker listed after, or delisted during, the requested range
- WHEN daily context is derived
- THEN dates outside its point-in-time listing status MUST be ineligible

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

### Requirement: Configurable point-in-time liquidity screen

The generator SHALL apply a daily, parameterized, no-look-ahead screen. Core defaults MUST remain price >= $10, median 20-bar dollar volume >= $10M, and 252 observed bars. Dollar volume MUST multiply adjusted close by canonical volume using exact `Decimal` arithmetic through median and threshold evaluation. AUM, ADV-fraction, and price-impact rules MUST remain excluded.
(Previously: Fractional volume and exact Decimal arithmetic were not explicit.)

#### Scenario: Apply Core defaults

- GIVEN a listed primary common stock with 252 bars
- WHEN its current price and exact trailing 20-bar median dollar volume meet Core defaults
- THEN its current date MUST be eligible

#### Scenario: Reject insufficient or failing history

- GIVEN insufficient history, price, or rolling volume
- WHEN the screen evaluates that date
- THEN it MUST produce an ineligible date without using later bars

#### Scenario: Retain fractional liquidity at the threshold

- GIVEN fractional volumes whose exact products pass the threshold but truncated products fail it
- WHEN the liquidity screen evaluates the date
- THEN the date MUST pass the liquidity threshold
- AND no intermediate value MAY be converted to an integer or binary floating-point value

### Requirement: Complete safe MarketContext decisions

The generator SHALL emit `MarketContext`-compatible coverage, eligibility, and blocker windows. It MUST cover each evaluated output date; missing/partial data MUST fail closed. Listing/liquidity failure MUST be `eligible=false`, not a blocker. ACTIONS MUST create only effective-date `corporate-action` blockers, omit them on ineligible dates, and never emit earnings-context-missing.

#### Scenario: Encode a corporate action safely

- GIVEN an eligible symbol with one or more ACTIONS events on a covered date
- WHEN context is built
- THEN that date MUST be blocked as `corporate-action` without overlapping windows

#### Scenario: Refuse incomplete context

- GIVEN any requested candidate has malformed, missing, or incomplete required TICKERS, SEP, or ACTIONS data
- WHEN generation cannot establish its decision
- THEN it MUST fail and write no context file

### Requirement: Deterministic schema output

The generator SHALL write one versioned market-context document accepted unchanged by `BacktestContextJsonReader`. The document MUST declare a required top-level generation span. It MUST deterministically serialize the span, symbols, and windows; missing or malformed span data MUST invalidate the artifact without inference or fallback. When bars output is requested, the context artifact and bars fixture MUST form one pair governed by that declared span.

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

### Requirement: Standalone generator interface and failure behavior

The standalone entrypoint MUST take date range, screen inputs, and output destination, and write context only. It MUST NOT invoke replay, `BacktestRun`, broker, execution, scanner, live, or paper paths. Tests MUST mock transport and make zero external calls. Invalid input/schema, partial/duplicate data, or exhausted/blank pagination MUST emit one machine-readable failure and no partial output.

#### Scenario: Generate without replay

- GIVEN valid mocked Sharadar responses and explicit output inputs
- WHEN the standalone entrypoint succeeds
- THEN it MUST write the context file and make zero replay or broker calls

#### Scenario: Bound unsafe pagination

- GIVEN a paginated response exceeds its configured bound or has a blank cursor
- WHEN the generator fetches inputs
- THEN it MUST fail closed with no output file

### Requirement: Backtest-only scope compatibility

This capability MUST remain backtest-only and MUST NOT change `backtest_main`, `BacktestContextJsonReader`, `MarketContext`, or `BacktestRun` contracts.

#### Scenario: Preserve existing consumers

- GIVEN a reader-valid generated context file
- WHEN an existing backtest consumes it
- THEN its existing context-reader and replay contracts MUST remain unchanged
