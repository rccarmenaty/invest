# Delta for Trading System

## MODIFIED Requirements

### Requirement: Position sizing and bracket price math

Each order MUST size at 0.35% (0.0035) of equity risked per trade. Entry MUST be the actual fill price (the fill-day open in backtest). Initial stop MUST be `min(breakout-day low, entry − 2×ATR(period))`, where `average_true_range()` accepts an optional `period` parameter defaulting to 14 to preserve existing ATR(14) callers (spike scanner, ATR-trail exit); the stop/sizing path MUST call it with `period=20`. Take-profit MUST be `entry + 2×ATR(period)`, using the same parameterized ATR value as the stop path (ATR(20) where the structural stop path runs). Qty MUST equal `floor(risk_capital / (entry − stop))`. Qty MUST floor to whole shares. Prices MUST quantize to valid increments (whole cents above $1, 4dp below $1). Zero/negative or otherwise degenerate stop distance (entry ≤ stop) MUST skip the intent with a machine-readable reason instead of an order. Backtest replay continues to ignore `OrderIntent.take_profit` for exits per the existing replay-only pure exit engine requirement; this field remains required and byte-compatible for the paper bracket path.
(Previously: 1% risk, stop at entry − 1×ATR14, take-profit at entry + 2×ATR14 bracket, no structural-low comparison. New behavior keeps the take-profit leg, now computed with the same parameterized ATR as the stop.)

#### Scenario: Structural stop picks the lower of the two candidates

- GIVEN a breakout-day low and an `entry − 2×ATR(20)` value where the breakout-day low is lower
- WHEN the initial stop is computed
- THEN the stop MUST equal the breakout-day low, not the ATR-derived candidate
- AND take-profit MUST still be computed as `entry + 2×ATR(20)`, independent of which stop candidate wins

#### Scenario: Gap-up entry re-sizes from the actual fill price

- GIVEN a candidate whose fill-day open gaps above the signal-day close used at scan time
- WHEN sizing runs at fill time
- THEN entry, stop, and qty MUST be computed from the actual fill-day open, not the signal-day close
- AND qty MUST reflect the resulting stop distance from that fill price

#### Scenario: Degenerate stop distance skips the intent

- GIVEN a computed stop that is greater than or equal to entry
- WHEN sizing runs
- THEN no order intent MUST be emitted
- AND the skip MUST carry a machine-readable `sizing-invalid` reason

#### Scenario: Zero or negative quantity skips the intent

- GIVEN a risk budget and stop distance computing to zero or negative shares
- WHEN sizing runs
- THEN no order intent MUST be emitted
- AND the skip MUST carry the machine-readable reason `sizing-invalid`

### Requirement: Pre-trade risk gates

Before submission, the system MUST evaluate pre-trade risk gates as pure predicates over the account/positions snapshot. Any gate failure MUST block submission with a machine-readable skip/halt reason; the run MUST continue fail-closed rather than aborting. After ANY position close (trailing exit, hard stop, time stop, or forced/broker close), the symbol MUST NOT re-enter for 10 trading sessions counted from the close date; a blocked re-entry attempt MUST be skipped with a machine-readable `cooldown-active` reason. The cooldown gate MUST evaluate only inside the position-aware submission path and MUST NOT affect the position-blind `scan_decisions()` collector.
(Previously: gates covered max concurrent positions, max deployed equity, kill-switch, and broker guard only — no re-entry cooldown.)

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

#### Scenario: Cooldown blocks re-entry within 10 sessions of any close

- GIVEN a symbol whose position closed (by trailing exit, stop, time stop, or forced close) on session T
- WHEN a new candidate for that symbol is evaluated on sessions T+1 through T+10
- THEN the order MUST NOT be submitted, with reason `cooldown-active`
- AND on session T+11 the symbol MUST be eligible for re-entry again, subject to other gates

#### Scenario: Forced close also starts the cooldown

- GIVEN an open position that is closed by a forced/broker-action close rather than a trailing exit or stop
- WHEN a later candidate for that symbol is evaluated within 10 sessions
- THEN the order MUST NOT be submitted, with reason `cooldown-active`

#### Scenario: scan_decisions() remains unaffected by cooldown

- GIVEN a symbol currently inside its post-close cooldown window
- WHEN `scan_decisions()` runs
- THEN it MUST evaluate the candidate the same as if no cooldown were active
- AND cooldown state MUST NOT be read or written by the position-blind collector

### Requirement: Portfolio-aware backtest accounting

The backtest harness MUST simulate finite starting capital, cash, equity, open positions, deployed capital, and closed trades across the replay range. Entries MUST size from current equity using the existing risk-based sizing rules and current fixed cost model. Same-day pending candidates MUST be filled in ranked order: momentum rank (descending) first, then 52-week-high proximity, then liquidity (dollar volume, descending); ties MUST break deterministically by symbol ascending as the final tiebreaker. This change MUST NOT alter `MomentumScanner`, static universe semantics, cost assumptions, broker isolation, or paper-first/no-live validation gates.
(Previously: same-day pending candidates were filled in alphabetical symbol order.)

#### Scenario: Higher-momentum symbol fills first when capital admits only one

- GIVEN two same-day pending candidates where capital is sufficient for only one entry
- WHEN entries are evaluated in ranked order
- THEN the candidate with the higher momentum rank MUST fill
- AND the lower-momentum candidate MUST be skipped with reason `insufficient-buying-power`

#### Scenario: Overlapping entries consume finite capital

- GIVEN a replay day with multiple accepted candidates and limited cash
- WHEN entries are evaluated in deterministic ranked order
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

### Requirement: Backtest strategy selection

`invest-backtest` MUST accept a `--strategy` flag with values `benchmark` and `core`, defaulting to `benchmark` when omitted. `BacktestRun` MUST depend on a `ScannerPort` abstraction rather than the concrete `MomentumScanner` class, so either strategy runs through the identical unmodified replay harness. Selecting `benchmark` (or omitting the flag) MUST reproduce the same scan decisions, trade logs, and metrics byte-for-byte as explicitly passing `--strategy benchmark` under the same code version (default-vs-explicit equivalence, not a cross-version guarantee). The `period` parameter added to `average_true_range()` MUST default to 14 so existing non-sizing callers (spike scanner, ATR-trail exit variant) are unchanged. The sizing/stop/risk, cooldown, and ranked fill-ordering changes in this delta apply identically to both `benchmark` and `core` strategies through the shared replay harness; `compute_intent()` is strategy-agnostic, so benchmark trades WILL resize and re-stop under the new constants — this is intended, not a byte-identity break.
(Previously: no explicit dependency on the ATR default period; no statement that shared-harness sizing/cooldown/fill-ordering changes apply to both strategies alike.)

#### Scenario: Default and explicit benchmark are identical

- GIVEN the same fixtures and universe, on the same code version after this delta
- WHEN `invest-backtest` runs once with no `--strategy` flag and once with `--strategy benchmark`
- THEN both runs MUST produce byte-identical scan decisions, trade logs, and metrics
- AND that equivalence MUST hold because both runs share the same updated harness, sizing, and gates — not because output matches pre-delta output

#### Scenario: Core strategy replays through the same harness

- GIVEN the same fixtures and universe
- WHEN `invest-backtest --strategy core` runs
- THEN it MUST replay day-by-day through the unmodified `BacktestRun` harness
- AND its output MUST use the same report shape as the benchmark strategy

#### Scenario: Unknown strategy value is rejected

- GIVEN `--strategy` is set to a value other than `benchmark` or `core`
- WHEN `invest-backtest` starts
- THEN it MUST fail with a machine-readable error and exit non-zero before any replay begins
