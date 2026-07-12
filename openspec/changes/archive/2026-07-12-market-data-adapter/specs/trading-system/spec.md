# Delta for trading-system

## ADDED Requirements

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
