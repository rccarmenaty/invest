# Proposal: Trailing Exit Engine

## Intent

Replace replay’s fixed take-profit with a deterministic research exit policy. Preserve paper-first/no-live gates; defer paper execution to Phase D.

## Scope

### In Scope
- Add a pure, clock-free, replay-only exit engine.
- Default to 10-day-low: when session *t* closes below the prior 10 sessions’ lowest low (excluding *t*), exit at the next observed session’s open with existing slippage. Without a next session, retain existing `open-at-end` handling and warn.
- Ratchet the effective floor daily as `max(initial_stop, prior_floor, candidate_floor)`; it never loosens. Existing hard-stop priority remains conservative.
- After the 20th held trading session closes, signal a next-open time stop unless price reached `entry + 0.5R` (`R = entry - initial_stop`) or a new prior-20-session closing high during the hold.
- Add a selectable 3-ATR high-water, never-loosening grid variant with the same close-signal/next-open semantics.

### Out of Scope
- Changes to `OrderIntent.take_profit`, sizing, Alpaca paper brackets, `ExecuteRun`, broker/account rules, or live trading.
- Selecting paper trailing orders; Phase D owns that decision.
- Other exit variants, regime filters, or volatility sizing.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `trading-system`: replay exits, policy selection/reporting, deterministic ordering, and CLI isolation.

## Approach

Create pure policy state/decisions in `src/invest/domain/exit_policy.py`; add trailing-low support; let `BacktestRun` supply chronological OHLC and position state. Benchmark and Core share one seam; backtest ignores intent take-profit. Priority: context forced-close, hard stop, trailing signal, time stop, open-at-end. Reports identify policy parameters.

## Delivery Slices

1. 10-day-low engine, reasons, replay wiring, tests: **350–500 lines**.
2. Conditional 20-session time stop and tests: **150–250 lines**.
3. 3-ATR variant plus backtest-only grid/CLI seam: **150–300 lines**.

**Forecast:** 650–1000 authored lines; force-chained delivery is required for the 800-line budget.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `src/invest/domain/` | Modified/New | Indicator, policy, exit state |
| `src/invest/application/backtest_run.py` | Modified | Replay-only policy wiring |
| `src/invest/adapters/cli.py` | Modified | Backtest-only policy selection |
| `tests/` | Modified/New | Pure, integration, determinism, boundary coverage |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Look-ahead/session-count errors | Med | Completed-history inputs and strict-TDD cases |
| Paper contract leakage | Med | Boundary tests preserve brackets and `take_profit` |

## Rollback Plan

Revert replay wiring/policy module and restore fixed-TP replay tests; paper behavior remains unchanged throughout.

## Dependencies

- Point-in-time daily OHLC is authoritative; no new feed. Backtest makes zero broker calls; paper rules stay unchanged.

## Success Criteria

- [ ] Repeated inputs produce byte-identical exits, metrics, and policy metadata.
- [ ] Channel, time-stop, and 3-ATR rules pass no-look-ahead and boundary tests.
- [ ] Paper Alpaca brackets and `OrderIntent.take_profit` remain byte-compatible.
