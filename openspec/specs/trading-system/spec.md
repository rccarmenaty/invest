# Trading System Specification

This main OpenSpec spec is scaffolded from `SPEC.md` and should be treated as the current source seed until later SDD changes refine individual requirements.

## Overview

Build a paper-first swing-trading system that detects confirmed momentum breakouts, sizes positions mechanically, submits protected bracket orders, and proves expectancy through replay/backtest plus paper trading before any live key is used.

## Core Requirements

### Requirement: Paper-first validation gates

The system MUST run through signals-only, replay/backtest, paper loop, live-readiness rehearsal, and live-small phases in order. Live trading MUST NOT occur until replay and paper expectancy gates pass.

### Requirement: Authoritative daily decisions

Candidate promotion, relative volume, breakout checks, ATR, and moving average decisions MUST use consolidated/SIP daily bars or delayed consolidated historical bars. IEX-only intraday data MAY be used for awareness only unless explicitly configured as a degraded-data experiment.

### Requirement: Momentum signal confirmation

The system MUST detect spike candidates on daily close, then require day +1/+2 confirmation before emitting entry signals. It MUST reject or hold candidates when earnings data is missing or unsafe.

### Requirement: Mechanical risk and order safety

Risk per trade MUST be 1% of account equity, max concurrent positions MUST be 5, max deployed equity MUST be 25%, and a 3% intraday drawdown MUST halt new entries. Broker/account restrictions MUST be read from Alpaca/account state rather than hard-coded PDT assumptions.

### Requirement: Hexagonal event-driven services

Each service MUST keep pure domain logic separate from adapters and SDKs. NATS JetStream events and Pydantic contracts are the API between services, and consumers MUST be idempotent for at-least-once delivery.

### Requirement: Replay and observability

Every trading day MUST be replayable from persisted events and historical point-in-time data.
For the implementation foundation slice, replayability MUST be represented by the fixture-driven scan, deterministic journal ordering, and machine-readable emitted events.
Journal, rejection reasons, data freshness, broker mismatches, and risk halts MUST be observable.
(Previously: Observability was defined at the full-system level without the local signals-only fixture/journal slice.)

#### Scenario: Observe a local scan run

- GIVEN a valid fixture-driven scan
- WHEN the CLI finishes
- THEN the journaled events and rejection reasons MUST be available in machine-readable form
- AND the output MUST be sufficient to reconstruct the scan result without replay infrastructure

#### Scenario: Preserve rejection observability on failure

- GIVEN a scan that rejects one or more candidates
- WHEN the run completes
- THEN the rejection reasons MUST remain visible in the journal and CLI output
- AND no rejected outcome MAY be silently dropped

### Requirement: Versioned foundation contracts

The system MUST define versioned Pydantic contracts for candidate signals, acceptance events, rejection events, scanner outputs, journal entries, and CLI event payloads.

Each contract MUST expose an explicit schema version and MUST be backward-compatible only by version bump, not by silent field reinterpretation.

#### Scenario: Accept a candidate with versioned output

- GIVEN a valid fixture bar set and universe fixture
- WHEN the scanner emits an accepted signal
- THEN the emitted event MUST include a schema version, an event type, and the minimum fields required to identify the symbol, date, and decision
- AND the contract MUST validate without importing adapters or infrastructure

#### Scenario: Reject an incompatible payload

- GIVEN a payload missing a required version field
- WHEN validation is attempted
- THEN validation MUST fail with a deterministic contract error
- AND no domain event MUST be produced

### Requirement: Static universe and fixture validation

The system MUST load a static, versioned universe fixture and daily bar fixtures as the only initial market inputs.

Fixture files MUST be validated before scanner execution. Invalid schemas, missing symbols, duplicate rows, non-monotonic dates, or bars outside the declared fixture version MUST be rejected before any trading decision is made.

#### Scenario: Load a valid fixture set

- GIVEN a versioned universe fixture and matching daily bar fixtures
- WHEN the CLI starts a scan
- THEN the fixtures MUST load successfully
- AND the scanner MUST receive only validated in-memory data structures

#### Scenario: Reject malformed fixture data

- GIVEN a fixture file with duplicate rows for the same symbol and date
- WHEN fixture validation runs
- THEN validation MUST fail
- AND the failure MUST identify the rejection reason as duplicate-bar

#### Scenario: Reject a version mismatch

- GIVEN a universe fixture version that does not match the bar fixture version
- WHEN the loader compares fixture metadata
- THEN the loader MUST stop before scanning
- AND the failure MUST be classified as fixture-version-mismatch

### Requirement: Deterministic scanner behavior

The system MUST implement a pure deterministic scanner over fixture daily bars.

The scanner MUST be free of wall-clock access, randomness, network access, broker calls, SDK imports, and other adapter dependencies.

Given the same validated inputs, the scanner MUST always produce the same ordered sequence of accepted and rejected outputs.

#### Scenario: Produce the same results twice

- GIVEN the same universe fixture and the same daily bar fixture set
- WHEN the scanner is run twice
- THEN both runs MUST produce identical outputs in the same order
- AND the outputs MUST not depend on execution time

#### Scenario: Reject insufficient history

- GIVEN a symbol with fewer bars than the scanner requires for its rule
- WHEN the scanner evaluates that symbol
- THEN the symbol MUST be rejected
- AND the rejection reason MUST be insufficient-history

#### Scenario: Reject unsafe or missing context deterministically

- GIVEN a symbol whose inputs do not satisfy the scanner's rule prerequisites
- WHEN the scanner evaluates the candidate
- THEN the scanner MUST emit a rejection event rather than an acceptance event
- AND the rejection MUST include a stable reason code

### Requirement: Explicit rejection taxonomy

The system MUST classify every non-accepted scan outcome with a stable, machine-readable rejection reason code.

The rejection taxonomy MUST distinguish fixture validation failures, missing or insufficient data, rule failures, and explicit non-candidate outcomes.

#### Scenario: Reject a non-candidate cleanly

- GIVEN a symbol that passes fixture validation but does not satisfy the scanner rule
- WHEN the scanner evaluates the symbol
- THEN the system MUST emit a rejected candidate event
- AND the rejection reason MUST be no-signal

#### Scenario: Reject unsupported input conditions

- GIVEN inputs that violate prerequisite assumptions for the scanner
- WHEN the scan is attempted
- THEN the system MUST reject the symbol or run as appropriate
- AND the reason code MUST indicate the exact failure class rather than a generic error

### Requirement: In-memory journal behavior

The system MUST persist emitted scan decisions to an in-memory journal during a run.

The journal MUST store accepted and rejected events in deterministic order and MUST be queryable by the CLI for final reporting.

#### Scenario: Record an accepted event

- GIVEN the scanner accepts a candidate
- WHEN the acceptance is handed to the journal
- THEN the journal MUST store the event exactly once
- AND the stored record MUST preserve the event version and reason metadata

#### Scenario: Record a rejected event

- GIVEN the scanner rejects a candidate
- WHEN the rejection is handed to the journal
- THEN the journal MUST store the rejection exactly once
- AND the stored record MUST be available for machine-readable output

### Requirement: Machine-readable CLI output

The thin CLI MUST read validated fixtures, invoke the scanner, write to the in-memory journal, and print machine-readable event output.

The CLI MUST support a stable machine-readable format suitable for downstream parsing and MUST not require interactive prompts.

#### Scenario: Print scan events in machine-readable form

- GIVEN valid fixtures and a successful scan run
- WHEN the CLI finishes
- THEN it MUST print a machine-readable list of journaled events
- AND each entry MUST include the event type, symbol, date, version, and decision outcome

#### Scenario: Exit cleanly on validation failure

- GIVEN malformed fixture input
- WHEN the CLI attempts to load the fixtures
- THEN it MUST exit with a non-zero status
- AND it MUST print a machine-readable error record instead of partial scan output

### Requirement: Domain isolation from adapters and time

Domain modules MUST remain isolated from adapters, SDKs, infrastructure packages, and wall-clock calls.

Any access to fixture files, CLI I/O, container entrypoints, or logging infrastructure MUST occur outside the domain package.

#### Scenario: Prevent adapter imports in domain code

- GIVEN the domain package source tree
- WHEN the project test suite checks module boundaries
- THEN the domain package MUST not import brokers, network clients, storage drivers, CLI frameworks, or wall-clock APIs

#### Scenario: Keep scanner logic pure

- GIVEN scanner inputs already loaded into memory
- WHEN the scanner runs
- THEN it MUST not read files, query the system clock, or mutate external state

### Requirement: Container packaging without Kubernetes infrastructure

The system MUST provide container packaging for the local services and CLI artifacts intended for later deployment on user-owned Kubernetes.

The packaging MUST stop at the container boundary and MUST NOT include Kubernetes manifests, Helm charts, operators, provisioning scripts, or cluster infrastructure definitions.

#### Scenario: Build a container image

- GIVEN a packaged application source tree
- WHEN the container build runs
- THEN it MUST produce an image that can run the CLI or service entrypoint
- AND the build MUST not require cluster access

#### Scenario: Exclude Kubernetes infrastructure artifacts

- GIVEN the repository contents
- WHEN the packaging scope is reviewed
- THEN no Kubernetes manifests, Helm charts, operators, or provisioning assets MUST be required for this change
- AND the change MUST remain container-only

### Requirement: Market data fetch port and adapter boundary

The system MUST expose a `MarketDataReader` port shaped as `fetch(universe, as_of) -> FixtureInputs`, read-only, with no order/broker capability. Only the Alpaca adapter, using raw `httpx`, MAY implement it; the domain package MUST remain free of `httpx` and Alpaca imports.

#### Scenario: Adapter satisfies the fetch port

- GIVEN a universe and an as-of date
- WHEN the Alpaca adapter fetches bars
- THEN it MUST return `FixtureInputs` without exposing HTTP or SDK types to callers

#### Scenario: Domain boundary rejects market-data adapter imports

- GIVEN the domain package source tree
- WHEN boundary tests run
- THEN `httpx` and Alpaca imports MUST be forbidden in domain modules, alongside existing forbidden imports

### Requirement: Fetch-to-fixture snapshot semantics

Fetched, validated bars MUST be written as a dated snapshot in the existing fixture JSON schema. The scan pipeline MUST consume snapshots through the unmodified `JsonFixtureReader`.

#### Scenario: Snapshot feeds the unchanged scan pipeline

- GIVEN a completed fetch for an as-of date
- WHEN the adapter writes the snapshot
- THEN `JsonFixtureReader` MUST load it without schema changes
- AND `MomentumScanner` MUST run unchanged against it

### Requirement: Fail-closed snapshot on missing universe symbols

Any universe symbol absent from fetched data MUST abort the snapshot before write, with a machine-readable reason naming the missing symbols.

#### Scenario: Complete universe data snapshots successfully

- GIVEN fetched bars covering every universe symbol
- WHEN the snapshot writer runs
- THEN the snapshot MUST be written

#### Scenario: Missing symbol aborts the snapshot

- GIVEN fetched data missing one or more universe symbols
- WHEN the snapshot writer runs
- THEN no fixture file MUST be written
- AND the failure MUST report reason `symbol-missing-at-fetch` naming the missing symbols

### Requirement: Feed authority and degraded-data opt-in

The feed parameter MUST default to `sip`. Selecting `iex` MUST require explicit configuration and MUST be recorded as a degraded-data flag in snapshot provenance metadata.

#### Scenario: Default feed is SIP

- GIVEN no explicit feed configuration
- WHEN a fetch runs
- THEN the adapter MUST request `sip` data
- AND the snapshot provenance MUST record feed `sip`

#### Scenario: IEX opt-in is recorded as degraded

- GIVEN an explicit `iex` feed configuration
- WHEN a fetch runs
- THEN the snapshot provenance MUST record feed `iex` and a degraded-data flag

### Requirement: Alpaca credential handling

Alpaca credentials MUST be read only from `ALPACA_API_KEY_ID` and `ALPACA_API_SECRET_KEY` environment variables and MUST NOT appear in fixtures, snapshots, provenance, logs, events, or error output.

#### Scenario: Credentials load from environment only

- GIVEN both env vars set
- WHEN the adapter authenticates
- THEN no credential value MUST be accepted from any other source

#### Scenario: Credentials never leak into observable output

- GIVEN a fetch failure or successful snapshot
- WHEN any fixture, snapshot, provenance, log, event, or error is produced
- THEN it MUST NOT contain the API key ID or secret key value

### Requirement: Deterministic as-of date handling

The CLI and adapter MUST accept an explicit as-of date; the domain MUST remain clock-free. The same snapshot and universe MUST always produce identical scan output.

#### Scenario: As-of date stays outside the domain

- GIVEN a CLI fetch invocation with `--as-of`
- WHEN the fetch executes
- THEN only the adapter/CLI layer MUST read the as-of date
- AND the domain MUST receive it as plain input data, not via a clock call

#### Scenario: Same snapshot and universe reproduce identical results

- GIVEN one written snapshot and its universe
- WHEN the scan runs twice against it
- THEN both runs MUST produce identical ordered output

### Requirement: Fetch error taxonomy

Fetch failures MUST be classified with a stable, machine-readable reason and MUST NOT produce partial snapshot output.

#### Scenario: Authentication failure

- GIVEN invalid or missing Alpaca credentials
- WHEN a fetch is attempted
- THEN it MUST fail with reason `auth-failure` and write no fixture

#### Scenario: Network failure

- GIVEN the Alpaca API is unreachable
- WHEN a fetch is attempted
- THEN it MUST fail with reason `network-failure` and write no fixture

#### Scenario: Rate limit exceeded

- GIVEN the Alpaca API returns a rate-limit response
- WHEN a fetch is attempted
- THEN it MUST fail with reason `rate-limited` and write no fixture

#### Scenario: Empty or malformed response

- GIVEN an empty or schema-invalid API response
- WHEN validation runs
- THEN it MUST fail with reason `malformed-response` and write no fixture

#### Scenario: Unbounded pagination is refused

- GIVEN an API that keeps returning a non-null `next_page_token` beyond a bounded page limit
- WHEN the fetch paginates
- THEN it MUST fail with reason `malformed-response` and write no fixture

#### Scenario: Existing snapshot is not overwritten

- GIVEN a snapshot directory already exists for the requested as-of date
- WHEN a fetch is attempted for that date
- THEN it MUST fail with reason `snapshot-exists` and leave the existing snapshot untouched

#### Scenario: Local storage failure

- GIVEN the snapshot destination cannot be written (disk failure, permissions)
- WHEN the snapshot writer runs
- THEN it MUST fail with reason `storage-failure` and leave no partial snapshot

#### Scenario: Invalid universe input file

- GIVEN a missing, unreadable, or schema-invalid universe file
- WHEN a fetch CLI invocation starts
- THEN it MUST fail with reason `fixture-invalid` before any network request
- AND every fetch CLI failure above MUST print exactly one machine-readable record and exit non-zero

### Requirement: Snapshot-time and scan-time rejection boundary

Zero-volume halted-session bars MUST still snapshot successfully when the symbol itself is present; the existing scan-time `missing-data` rejection for insufficient/zero-volume history remains unchanged this slice.

#### Scenario: Halted-session bars pass snapshot but stay rejected at scan time

- GIVEN fetched bars for a symbol including a zero-volume halted session
- WHEN the snapshot is written and later scanned
- THEN the snapshot writer MUST NOT treat zero-volume bars as a missing-symbol failure
- AND the scanner MUST still reject that symbol as `missing-data`, unchanged from current behavior

### Requirement: Deterministic order intent computation

`order.intent.v1` MUST be a pure function of an accepted candidate plus an account snapshot (equity, open positions). The intent function MUST NOT perform I/O, wall-clock access, or network calls. Identical inputs MUST always yield an identical intent, including `client_order_id`, which MUST equal the intent's deterministic content hash.

#### Scenario: Same inputs produce identical intent

- GIVEN an accepted candidate and an account snapshot
- WHEN the intent function runs twice with the same inputs
- THEN both runs MUST produce byte-identical `order.intent.v1` payloads, including `client_order_id`

#### Scenario: Intent computation stays free of I/O

- GIVEN the domain intent module source
- WHEN boundary tests run
- THEN the module MUST not import `httpx`, Alpaca SDK, wall-clock APIs, or `random`

### Requirement: Position sizing and bracket price math

Each order MUST size at 1% of equity risked per trade, stop at entry − 1x ATR14, take-profit at entry + 2x ATR14. Qty MUST floor to whole shares. Prices MUST quantize to valid increments (whole cents above $1, 4dp below $1). Zero/negative computed qty MUST skip the intent with a machine-readable reason instead of an order.

#### Scenario: Compute a valid sized bracket

- GIVEN an accepted candidate, equity, and ATR14
- WHEN sizing runs
- THEN qty MUST floor to whole shares, stop/take-profit MUST use the 1x/2x ATR14 formula
- AND both prices MUST be quantized to their price-band increment

#### Scenario: Zero or negative quantity skips the intent

- GIVEN a risk budget and stop distance computing to zero or negative shares
- WHEN sizing runs
- THEN no order intent MUST be emitted
- AND the skip MUST carry a machine-readable sizing-failure reason

### Requirement: Pre-trade risk gates

Before submission, the system MUST evaluate pre-trade risk gates as pure predicates over the account/positions snapshot. Any gate failure MUST block submission with a machine-readable skip/halt reason; the run MUST continue fail-closed rather than aborting.

#### Scenario: Max concurrent positions gate blocks submission

- GIVEN 5 open positions already held
- WHEN a new intent is evaluated
- THEN the order MUST NOT be submitted, with reason max-concurrent-positions

#### Scenario: Max deployed equity gate blocks submission

- GIVEN open positions deploying 25% or more of equity
- WHEN a new intent is evaluated
- THEN the order MUST NOT be submitted, with reason max-equity-deployed

#### Scenario: Kill-switch halts new entries on drawdown

- GIVEN intraday drawdown of equity vs last_equity is <= -3%
- WHEN any intent is evaluated
- THEN no order MUST be submitted for that run, with halt reason `kill-switch`
- AND the run MUST continue reporting remaining skips rather than crashing

#### Scenario: Missing drawdown baseline fails closed

- GIVEN the account snapshot reports `last_equity` of zero or less
- WHEN halt gates are evaluated
- THEN the run MUST halt with reason `kill-switch` (no drawdown baseline means no drawdown protection; the system MUST NOT trade unprotected)

#### Scenario: Broker guard blocks submission on restricted account

- GIVEN the account reports `trading_blocked`, `account_blocked`, or insufficient buying power
- WHEN the intent is evaluated
- THEN the order MUST NOT be submitted, with a reason naming the specific broker-guard condition

### Requirement: Paper-only broker boundary

The broker adapter MUST target the hardcoded Alpaca paper base URL. The change MUST NOT introduce any live-trading URL, live-URL branch, or live code path, feature-flagged or otherwise. Credentials MUST be read only from environment variables and MUST NOT appear in output, logs, events, or errors.

#### Scenario: Adapter only calls the paper base URL

- GIVEN the broker adapter issues any request
- WHEN the request is constructed
- THEN the base URL MUST be the hardcoded paper URL, and no live-trading URL or branch MUST exist in the codebase

#### Scenario: Credentials never leak into observable output

- GIVEN a broker request succeeds or fails
- WHEN any log, event, error, or CLI output is produced
- THEN it MUST NOT contain the API key ID or secret key value

### Requirement: Idempotent order submission

Before a bracket-order POST, the adapter MUST query the broker for an existing order by `client_order_id`. An existing order MUST be reported as already-submitted with no duplicate POST. The mutating POST MUST NOT be blind-retried; bounded retry MAY apply only to idempotent GETs.

#### Scenario: Existing order is reported without duplicate submission

- GIVEN an order already exists for a `client_order_id`
- WHEN submission is attempted again
- THEN the adapter MUST report already-submitted with no duplicate POST

#### Scenario: Mutating POST is never blind-retried

- GIVEN the submission POST fails or times out
- WHEN the adapter handles the failure
- THEN it MUST NOT auto-retry the POST
- AND retry logic MUST apply only to the idempotent GET-by-`client_order_id` check

### Requirement: Bracket order shape

Every order MUST use `order_class=bracket` with a stop-market stop-loss leg (no limit price) and a limit take-profit leg. Entry `time_in_force` MUST be `day`; `extended_hours` MUST never be enabled.

#### Scenario: Submitted bracket matches the required shape

- GIVEN a passing intent ready for submission
- WHEN the order is submitted
- THEN `order_class` MUST be `bracket`, stop-loss MUST be stop-market and take-profit MUST be limit
- AND entry `time_in_force` MUST be `day` and `extended_hours` MUST be false

### Requirement: Dry-run default execution CLI

`invest-execute` MUST default to dry-run: print computed intents, submit nothing. Any broker mutation MUST require explicit `--execute`. Infrastructure failures MUST emit exactly one machine-readable record with a stable kebab-case reason from the fetch taxonomy (`auth-failure`, `network-failure`, `rate-limited`, `malformed-response`, `fixture-invalid`) and exit non-zero. Order-family outcomes (`kill-switch`, `broker-account-restricted`, `max-concurrent-positions`, `max-equity-deployed`, `insufficient-buying-power`, `sizing-invalid`, `already-submitted`, broker rejection) are journaled results of a completed run: the run exits zero and every outcome remains visible as an event.

#### Scenario: Default run submits nothing

- GIVEN `invest-execute` runs without `--execute`
- WHEN the CLI finishes
- THEN it MUST print computed intents and make zero broker mutation calls

#### Scenario: Explicit execute opts into submission

- GIVEN `invest-execute --execute` runs
- WHEN gates pass for an intent
- THEN the CLI MUST submit the order, and a broker-acknowledgement event MUST be journaled

#### Scenario: Pre-submission infrastructure failure emits one machine-readable record

- GIVEN an infrastructure failure (auth, network, rate limit, malformed response, invalid input files) BEFORE any candidate has been processed
- WHEN the failure occurs
- THEN the CLI MUST print exactly one machine-readable record with a stable kebab-case reason and exit non-zero

#### Scenario: Mid-run infrastructure failure preserves the journal

- GIVEN an infrastructure failure occurs after one or more orders have already been submitted in the same run
- WHEN the failure occurs
- THEN every event journaled so far (including submitted-order acknowledgements) MUST be printed
- AND the run MUST stop submitting further candidates, journaling the failure reason for the affected candidate and skips for the remainder
- AND the CLI MUST exit non-zero

#### Scenario: Ambiguous submission outcome is marked uncertain

- GIVEN the order-submission POST fails with a transport error after the broker may have accepted the order
- WHEN the failure is journaled
- THEN the affected candidate's record MUST carry reason `submission-uncertain` (distinct from `network-failure`)
- AND a subsequent run's idempotency check MUST detect any order the broker actually accepted

#### Scenario: Order-family outcomes complete the run with exit zero

- GIVEN a run where every candidate is skipped, halted, already submitted, or rejected by the broker as a business outcome
- WHEN the run finishes
- THEN each outcome MUST be journaled as an event with its stable kebab-case reason
- AND the CLI MUST exit zero with the full event list printed

### Requirement: Deterministic intent vs non-deterministic acknowledgement event families

Deterministic `order.intent.v1` events MUST be journaled separately from non-deterministic broker-acknowledgement events (`order.submitted.v1`, `order.rejected.v1`) and skip records. Acknowledgements MUST NOT reuse the deterministic content-hash scheme. This slice executes on day-0 `candidate.accepted.v1` as an explicitly-labeled interim simplification; a future confirmation-service slice is designated to re-point execution at confirmed signals.

#### Scenario: Intent and acknowledgement events are journaled separately

- GIVEN an intent is computed and later submitted
- WHEN both events are journaled
- THEN `order.intent.v1` MUST be the deterministic pre-submission record and the broker-acknowledgement event MUST be a distinct non-deterministic record

#### Scenario: Acknowledgement events do not reuse the deterministic hash scheme

- GIVEN a broker acknowledgement event is created
- WHEN its identifier is assigned
- THEN it MUST NOT use the same content-hash function used for `order.intent.v1`

### Requirement: Bulk historical range fetch

`AlpacaMarketDataReader` MUST add `fetch_range(universe, start, end)` returning validated bars for `[start, end]` in the existing schema. Additive only: `fetch(universe, as_of)` MUST NOT change. Failures MUST use the existing fetch error taxonomy.

#### Scenario: Range fetch returns validated multi-day bars

- GIVEN a universe and a date range
- WHEN `fetch_range` runs successfully
- THEN it MUST return validated bars for every trading day in range, in the existing schema

#### Scenario: Existing fetch is unchanged

- GIVEN the existing `fetch(universe, as_of)` call
- WHEN `fetch_range` is added
- THEN `fetch`'s inputs, outputs, and errors MUST stay identical to before this change

#### Scenario: Range fetch failure uses the existing taxonomy

- GIVEN an auth, network, rate-limit, or malformed-response failure during a range fetch
- WHEN it occurs
- THEN it MUST fail with the matching existing reason code and write no partial output

### Requirement: Deterministic day-by-day replay without look-ahead

The harness MUST evaluate the pure `MomentumScanner`/sizing functions once per historical day, using only bars dated on or before that day. The same range replayed twice MUST yield identical trade logs and metrics.

#### Scenario: Replaying the same range twice is identical

- GIVEN the same historical bar range and universe
- WHEN the harness replays it twice
- THEN both runs MUST produce byte-identical trade logs and metrics

#### Scenario: Each day sees only its own history

- GIVEN a replay in progress on day N
- WHEN the harness evaluates day N
- THEN it MUST pass only bars dated on or before day N to the scanner/sizing functions

### Requirement: Look-ahead prevention is a testable property

A fixture-based test MUST prove that day N's recorded decision is unaffected by bars dated after day N.

#### Scenario: Mutating future bars does not change a past decision

- GIVEN a fixture replay producing a recorded decision for day N
- WHEN bars dated after day N are mutated and the replay reruns
- THEN day N's recorded decision MUST NOT change

### Requirement: Day-0-only mechanics labeling

Every backtest report MUST carry an explicit label stating it measures current day-0 `CANDIDATE` mechanics, not SPEC's confirmed-entry thesis.

#### Scenario: Report carries the day-0 label

- GIVEN a completed backtest run
- WHEN the report is produced
- THEN it MUST include an explicit field/text stating the results measure day-0 CANDIDATE mechanics, not confirmed-entry

### Requirement: Survivorship-bias disclaimer

Reports MUST show the static-universe warning unless the entire run has validated PIT date/symbol coverage. Only then MUST a machine-readable PIT statement replace it.
(Previously: Every report always warned that its universe was a fixed historical screen.)

#### Scenario: Replace warning

- GIVEN complete validated PIT coverage
- WHEN reporting succeeds
- THEN the PIT statement MUST replace the static-universe warning

#### Scenario: Reject uncovered claim

- GIVEN missing, incomplete, or invalid context
- WHEN backtest starts
- THEN it MUST fail without a success report or PIT statement

### Requirement: Cost model reported as approximation

The harness MUST apply fixed-bps slippage, zero commission, and a flat tax haircut per trade. Every report MUST label these as an approximation, not precision.

#### Scenario: Report labels the cost model as approximate

- GIVEN a completed backtest run using this cost model
- WHEN the report is produced
- THEN it MUST label the cost figures as an approximation, not precise costs

### Requirement: Pure backtest metrics

`backtest_metrics.py` MUST compute hit rate, expectancy, max drawdown, and trade count as pure functions of a trade log, deterministic given the same log.

#### Scenario: Same trade log yields identical metrics

- GIVEN a fixed trade log
- WHEN metrics are computed twice
- THEN all four metrics MUST be identical both times

### Requirement: `invest-backtest` CLI never touches BrokerPort

`invest-backtest` MUST require externally prepared context, validate complete date/symbol coverage, replay the bulk fixture, and print one machine-readable report with metrics and labels. It MUST NOT use `BrokerPort`.
(Previously: The CLI required only a bulk fixture/snapshot and always emitted both existing mandatory labels.)

#### Scenario: Successful report

- GIVEN valid bars, split date, and complete context
- WHEN `invest-backtest` runs
- THEN it MUST print one report with metrics, labels, context outcomes, and zero broker calls

#### Scenario: Context failure

- GIVEN context is absent, incomplete, unreadable, malformed, contradictory, or unsupported
- WHEN `invest-backtest` starts
- THEN it MUST print one machine-readable context error, exit non-zero, and output no partial replay

### Requirement: Out-of-scope guard

This change MUST NOT introduce gap-trading strategy logic, confirmation-service logic, or any live-trading code path.

#### Scenario: No gap-trading, confirmation, or live-trading code is added

- GIVEN the repository after this change
- WHEN the source tree is reviewed
- THEN no gap-trading strategy module, no confirmation-service module, and no live-trading URL/branch MUST exist

### Requirement: Portfolio-aware backtest accounting

The backtest harness MUST simulate finite starting capital, cash, equity, open positions, deployed capital, and closed trades across the replay range. Entries MUST size from current equity using the existing 1%-risk sizing rules and current fixed cost model. This change MUST NOT alter `MomentumScanner`, static universe semantics, cost assumptions, broker isolation, or paper-first/no-live validation gates.

#### Scenario: Overlapping entries consume finite capital

- GIVEN a replay day with multiple accepted candidates and limited cash
- WHEN entries are evaluated in deterministic order
- THEN accepted simulated positions MUST reduce available cash/deployed capacity
- AND later candidates MUST respect the updated portfolio state

#### Scenario: Capital unavailable skips entry

- GIVEN a candidate whose sized entry exceeds available buying power
- WHEN the harness evaluates the simulated entry
- THEN no position MUST open
- AND the trade log MUST record reason `insufficient-buying-power`

#### Scenario: Exits release portfolio capacity

- GIVEN an open simulated position reaches its modeled exit
- WHEN the exit is recorded
- THEN cash, equity, open positions, and deployed capital MUST update deterministically

### Requirement: Deterministic simulated gate telemetry

The harness MUST apply the existing pure pre-trade gates before simulated entry: max concurrent positions, max deployed equity, buying power, and kill-switch. Every blocked candidate MUST increment stable per-reason telemetry. Gate telemetry MUST be labeled `portfolio-gates-simulated` and MUST NOT be presented as broker/account enforcement.

#### Scenario: Gate pressure is counted by reason

- GIVEN candidates blocked by different simulated gates
- WHEN the backtest report is produced
- THEN the report MUST include deterministic counts by gate reason
- AND skipped entries MUST remain visible in the trade log

#### Scenario: Kill-switch uses prior-session equity

- GIVEN current equity breaches the 3% drawdown threshold versus prior-session equity
- WHEN later candidates are evaluated that day
- THEN simulated entries MUST be blocked with reason `kill-switch`

#### Scenario: Same replay has same telemetry

- GIVEN identical fixtures, universe, starting capital, and split date
- WHEN the replay runs twice
- THEN gate counts, trade logs, and metrics MUST be byte-identical

### Requirement: Daily equity summary and split-date metrics

The report MUST include a deterministic daily equity summary without requiring full equity-curve serialization. Summary fields MUST include starting equity, ending equity, min/max equity, max drawdown, total return, and covered trading-day count. The report MUST require an explicit split date for IS/OOS reporting and MUST classify trades by entry date: entries before the split are IS; entries on or after the split are OOS.

#### Scenario: Daily summary is observable

- GIVEN a completed replay with open and closed positions
- WHEN the report is produced
- THEN it MUST include the required daily equity summary fields
- AND repeated runs over the same inputs MUST produce identical values

#### Scenario: Trades are split by entry date

- GIVEN trades before, on, and after the split date
- WHEN IS/OOS metrics are computed
- THEN pre-split entries MUST contribute only to IS metrics
- AND split-date-or-later entries MUST contribute only to OOS metrics

#### Scenario: Invalid split date fails closed

- GIVEN a missing, malformed, or out-of-range split date for IS/OOS reporting
- WHEN `invest-backtest` runs
- THEN it MUST print one machine-readable error record and exit non-zero

### Requirement: Mandatory portfolio-backtest limitations

Every backtest report MUST preserve existing limitation labels for day-0 candidate mechanics, static universe survivorship bias, and approximate costs. It MUST additionally warn that OOS results still use the static universe, portfolio gates are simulated, and broker execution realism is out of scope. Missing market, earnings, or corporate-action data MUST fail safe rather than imply confirmed-entry or execution realism.

#### Scenario: Required limitation labels are present

- GIVEN a successful portfolio-aware backtest
- WHEN the report is rendered in any supported format
- THEN all mandatory limitation labels MUST be present and machine-readable

#### Scenario: Broker and live trading remain isolated

- GIVEN the portfolio-aware backtest executes
- WHEN the harness evaluates entries and exits
- THEN it MUST NOT construct or call `BrokerPort`
- AND it MUST NOT introduce any live-trading code path or broker-enforced backtest control

### Requirement: Preserve existing boundaries

Context filtering MUST NOT change `MomentumScanner`, Alpaca bars, portfolio accounting, costs, broker paths, or paper-first/live gates. Alpaca MUST remain bars-only; backtests MUST make zero broker calls.

#### Scenario: Preserve behavior

- GIVEN complete context marks every symbol eligible and unblocked
- WHEN the same replay runs with context filtering
- THEN scanner outputs, accounting, costs, and ordinary exits MUST remain unchanged

#### Scenario: Preserve boundaries

- GIVEN a context-backed replay
- WHEN calls are observed
- THEN Alpaca MUST NOT supply context and `BrokerPort` MUST receive zero calls

### Requirement: Backtest strategy selection

`invest-backtest` MUST accept a `--strategy` flag with values `benchmark` and `core`, defaulting to `benchmark` when omitted. `BacktestRun` MUST depend on a `ScannerPort` abstraction rather than the concrete `MomentumScanner` class, so either strategy runs through the identical unmodified replay harness. Selecting `benchmark` (or omitting the flag) MUST reproduce today's scan decisions, trade logs, and metrics byte-for-byte.

#### Scenario: Default and explicit benchmark are identical

- GIVEN the same fixtures and universe
- WHEN `invest-backtest` runs once with no `--strategy` flag and once with `--strategy benchmark`
- THEN both runs MUST produce byte-identical scan decisions, trade logs, and metrics

#### Scenario: Core strategy replays through the same harness

- GIVEN the same fixtures and universe
- WHEN `invest-backtest --strategy core` runs
- THEN it MUST replay day-by-day through the unmodified `BacktestRun` harness
- AND its output MUST use the same report shape as the benchmark strategy

#### Scenario: Unknown strategy value is rejected

- GIVEN `--strategy` is set to a value other than `benchmark` or `core`
- WHEN `invest-backtest` starts
- THEN it MUST fail with a machine-readable error and exit non-zero before any replay begins

### Requirement: Strategy flag stays backtest-only

The `--strategy` flag MUST exist only on the `invest-backtest` CLI parser. `invest-execute` and the day-0 scan CLI MUST NOT expose or accept a strategy-selection flag.

#### Scenario: Execute and scan parsers reject the flag

- GIVEN the `invest-execute` and scan CLI parsers
- WHEN their argument definitions are inspected
- THEN neither MUST define a `--strategy` argument

### Requirement: Backtest data source selection

`invest-backtest` MUST accept `--source {fixture,alpaca,sharadar}` on `_backtest_parser`. Omitting `--source` MUST preserve today's implicit inference (fixture via `--bars`, Alpaca via `--start`/`--end`) byte-identically. Selecting `sharadar` MUST route the fetch to `SharadarMarketDataReader.fetch_range`. An unknown `--source` value MUST fail closed before any fetch or replay.

#### Scenario: Default inference is unchanged

- GIVEN the same fixtures/universe/date arguments as before this change
- WHEN `invest-backtest` runs without `--source`
- THEN it MUST select fixture or Alpaca exactly as it did before this change, byte-identically

#### Scenario: Explicit sharadar source routes to the new reader

- GIVEN `--source sharadar` with a universe and date range
- WHEN `invest-backtest` runs
- THEN it MUST fetch bars via `SharadarMarketDataReader.fetch_range`

#### Scenario: Unknown source value fails closed

- GIVEN `--source` set to a value other than `fixture`, `alpaca`, or `sharadar`
- WHEN `invest-backtest` starts
- THEN it MUST fail with a machine-readable error and exit non-zero before any fetch or replay begins

### Requirement: Source flag stays backtest-only

The `--source` flag MUST exist only on the `invest-backtest` CLI parser. `invest-execute` and the day-0 scan CLI MUST NOT define or accept a source-selection flag.

#### Scenario: Execute and scan parsers reject the flag

- GIVEN the `invest-execute` and scan CLI parsers
- WHEN their argument definitions are inspected
- THEN neither MUST define a `--source` argument

### Requirement: Backtest-only reference-data adapter boundary

`SharadarTickersReader` and `SharadarActionsReader` MUST remain backtest-only adapters. Exactly one deliberate caller, the standalone Sharadar market-context generator route, MAY import and invoke them solely to write `market-context-v1` context for later backtest use. They MUST NOT be imported, invoked, or selected by broker, execution, scanner, live-trading, paper-trading, `backtest_main`, `BacktestContextJsonReader`, `MarketContext`, or `BacktestRun` paths. The generator MUST NOT alter `SharadarMarketDataReader` or existing context/replay behavior.
(Previously: No CLI source or generator route could use the reference-data readers.)

#### Scenario: Only the generator may depend on reference readers

- GIVEN the source tree and reference-reader caller allowlist
- WHEN boundary checks inspect imports and reader-name references
- THEN exactly the standalone backtest-only generator route MAY reference either reader
- AND every other protected path MUST remain denied

#### Scenario: Protected paths have no reference-data reader dependency

- GIVEN the source tree's broker, execution, scanner, live/paper trading, CLI, and protected backtest/domain modules
- WHEN boundary checks inspect imports and reader-name references
- THEN none of those paths other than the dedicated generator MUST reference `SharadarTickersReader` or `SharadarActionsReader`
- AND no existing SEP, market-context, backtest-run, or backtest-context JSON behavior MUST be altered

## Source

Seeded from `/Users/rcty/invest/SPEC.md` on 2026-07-11. Keep SPEC.md available as the detailed narrative until SDD deltas replace or expand this main spec.
