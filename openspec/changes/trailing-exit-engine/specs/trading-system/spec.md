# Delta for Trading System

## ADDED Requirements

### Requirement: Replay-only pure exit engine

Backtest MUST evaluate position exits via pure, clock-free engine (no wall-clock, I/O, network, broker) on backtest path only. Paper `ExecuteRun`, Alpaca brackets, `OrderIntent` sizing, and live trading MUST stay unchanged. Backtest MUST ignore `OrderIntent.take_profit` for exits while preserving field and paper brackets byte-compatibly.

#### Scenario: Pure domain evaluation

- GIVEN in-memory bars and position state
- WHEN exit engine evaluates
- THEN no wall-clock, I/O, brokers, or adapters

#### Scenario: Paper contracts preserved

- GIVEN paper sizing and bracket submission
- WHEN compared to baselines
- THEN `OrderIntent.take_profit` and bracket TP stay required and byte-compatible; no paper path selects trailing

### Requirement: Default 10-day-low trailing exit

Default MUST be 10-day-low: after session *t*, if `close_t` is strictly below lowest low of prior 10 sessions excluding *t*, signal trailing exit; do not exit on signal bar; fill next open with existing slippage. Close equal to prior low MUST NOT signal. Missing next session MUST use `open-at-end` and warn.

#### Scenario: Below prior low fills next open

- GIVEN close below prior-10 low excluding signal
- WHEN next session arrives
- THEN exit at open with existing slippage and trailing-channel reason

#### Scenario: Equal close does not signal

- GIVEN close equal prior-10 low excluding session
- WHEN evaluation runs
- THEN no trailing exit signals

#### Scenario: Missing next bar

- GIVEN trailing signal on last session
- WHEN no next session exists
- THEN use `open-at-end` and record missing-next-session warning

### Requirement: Never-loosening floor and exit priority

Effective floor MUST update each session as `max(initial_stop, prior_floor, candidate_floor)` and only ratchet upward. Existing hard-stop and conservative stop priority MUST remain. Priority MUST be: (1) context forced-close, (2) hard stop (existing conservative), (3) trailing/ATR fill, (4) time stop, (5) open-at-end.

#### Scenario: Floor only ratchets up

- GIVEN prior floor F and lower candidate C
- WHEN floor updates
- THEN floor stays F

#### Scenario: Forced-close beats ordinary exits

- GIVEN forced-close and trailing eligibility
- WHEN exits process
- THEN exit is context forced-close

#### Scenario: Hard stop beats trailing and time stop

- GIVEN trailing/time-stop eligibility and hard-stop touch
- WHEN bar evaluated
- THEN exit is hard stop

### Requirement: Conditional 20-session time stop

Hold count MUST use observed trading sessions. After 20th held session closes, signal next-open time stop unless during hold price reached `entry + 0.5R` (`R = entry - initial_stop`) or printed a new prior-20 high. Fill next open with existing slippage; missing next bar uses trailing `open-at-end` + warning.

#### Scenario: Time stop without progress

- GIVEN 20 held sessions without +0.5R or new prior-20 high
- WHEN 20th session closes
- THEN signal time-stop for next open

#### Scenario: Progress suppresses time stop

- GIVEN +0.5R or new prior-20 high during hold
- WHEN 20th session closes
- THEN no time-stop signals

### Requirement: Selectable 3-ATR high-water variant

MUST provide 3-ATR high-water, never-loosening variant with same close-signal/next-open semantics. Selection MUST be backtest-only (`invest-backtest`). `invest-execute` and day-0 scan MUST NOT accept exit-policy selection. Reports MUST record policy/parameters.

#### Scenario: 3-ATR selected on backtest

- GIVEN backtest selects 3-ATR high-water
- WHEN replay completes
- THEN exits follow 3-ATR never-loosen close-signal/next-open rules; report records policy/parameters

#### Scenario: CLI isolation

- GIVEN `invest-execute` and day-0 scan parsers
- WHEN args inspected
- THEN neither defines exit-policy flag

### Requirement: No look-ahead and deterministic exit provenance

Day-N exits MUST use only completed history on or before day N. Identical inputs MUST yield identical exits, logs, metrics, and policy metadata.

#### Scenario: No look-ahead

- GIVEN recorded exit on day N
- WHEN post-N bars mutate and replay reruns
- THEN day N exit is unchanged

#### Scenario: Deterministic twin runs

- GIVEN identical fixtures, capital, split date, exit-policy
- WHEN backtest runs twice
- THEN exits, logs, metrics, and policy metadata match
