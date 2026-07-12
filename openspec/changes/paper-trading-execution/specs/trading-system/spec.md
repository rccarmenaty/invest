# Delta for trading-system

## ADDED Requirements

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

#### Scenario: Infrastructure failure emits one machine-readable record

- GIVEN an infrastructure failure (auth, network, rate limit, malformed response, invalid input files)
- WHEN the failure occurs
- THEN the CLI MUST print exactly one machine-readable record with a stable kebab-case reason and exit non-zero

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
