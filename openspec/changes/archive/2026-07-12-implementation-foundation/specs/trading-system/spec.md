# Delta for trading-system

## ADDED Requirements

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

## MODIFIED Requirements

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

