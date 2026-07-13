# Proposal: Portfolio-Aware Backtest

## Intent

Make historical replay account for finite capital and overlapping positions, expose simulated risk-gate pressure, summarize equity evolution, and separate in-sample (IS) from out-of-sample (OOS) results. This improves validation without claiming confirmed-entry, point-in-time-universe, or broker execution realism. Paper-first and no-live-before-validation gates remain unchanged.

## Scope

### In Scope
- Evolving portfolio equity, cash, open positions, and deployed capital using the existing cost and 1%-risk sizing rules.
- Harness-enforced concurrency, deployed-equity, buying-power, and kill-switch gates, with per-reason telemetry.
- Deterministic daily equity-curve summary and explicit split-date IS/OOS metrics.
- CLI/report changes and focused fixtures/tests for contention, gates, equity, and split behavior.

### Out of Scope
- Universe evolution or a real point-in-time provider; the static fixture remains authoritative.
- Day+1/+2 confirmation, trend/follow-through, earnings, or gap logic.
- Richer execution realism: spreads, volume slippage, commissions, borrow costs, or partial fills.
- Live trading or broker-enforced backtest controls.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `trading-system`: Replay requirements gain portfolio accounting, simulated-gate telemetry, equity summary, and explicit IS/OOS reporting.

## Approach

Deepen `BacktestRun` as the portfolio simulation module while keeping `MomentumScanner` and the static universe unchanged. Size from current equity, evaluate existing pure gates before entry, update positions/equity deterministically, and summarize daily equity without serializing the full curve. Use prior-session equity for the simulated kill-switch. Classify trades by entry date around an explicit split date. Preserve day-0, survivorship-bias, and approximate-cost labels; add `portfolio-gates-simulated` and static-universe OOS warnings.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `src/invest/application/backtest_run.py` | Modified | Portfolio lifecycle, gates, telemetry, split |
| `src/invest/domain/models.py` | Modified | Portfolio/result value objects |
| `src/invest/domain/backtest_metrics.py` | Modified | Equity and IS/OOS summaries |
| `src/invest/adapters/cli.py` | Modified | Split input and report labels |
| `tests/`, `fixtures/` | Modified | Deterministic portfolio scenarios |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Static universe inflates OOS results | High | Unavoidable report warning |
| Simulated gates differ from broker state | Med | Label and report gate counts |
| Scope exceeds review budget | Low | Keep scanner, universe, and costs unchanged; tasks revalidate 400–600 lines against 800 |

## Rollback Plan

Revert portfolio result/report changes and restore fixed-equity replay; fixtures and source data require no migration.

## Dependencies

- Existing pure sizing gates, fixture bars, static universe, and fixed cost model.

## Success Criteria

- [ ] Overlapping entries respect capital, concurrency, and halt rules with deterministic telemetry.
- [ ] Reports include equity summary plus separate IS/OOS metrics and all required warnings.
- [ ] Existing scanner, static-universe behavior, broker isolation, and paper-first gates remain unchanged.
