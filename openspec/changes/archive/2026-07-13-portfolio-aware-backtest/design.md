# Design: Portfolio-Aware Backtest

## Technical Approach

Deepen `BacktestRun` into the portfolio simulation module while preserving the existing hexagonal shape: scanner and sizing remain pure domain inputs, `backtest_metrics.py` remains the only cost-accounting module, and `cli.py` stays the thin reporting adapter. The first slice replaces independent fixed-equity trade replay with deterministic portfolio accounting, gate telemetry, equity summaries, and split-date IS/OOS metrics. It explicitly does not add point-in-time universe logic, day+1/+2 confirmation, gap/earnings/follow-through logic, richer fills, or live/broker execution behavior.

## Architecture Decisions

| Option | Tradeoff | Decision |
|---|---|---|
| Add a separate portfolio engine | Cleaner name, but creates a new seam before a second adapter exists | Keep the seam at `BacktestRun.replay(...)`; deepen the existing module for locality and caller leverage. |
| Reimplement gates inside backtest | Could tailor messages, but risks divergence from execution | Reuse `compute_intent`, `evaluate_halt_gates`, and `evaluate_gates` unchanged; telemetry counts their `GateReason` values. |
| Emit full daily equity curve | More detail, larger unstable report | Track deterministic daily telemetry internally and report summaries only: start/end equity, peak/trough, max drawdown, day count. |
| Segment by exit date or P&L realization | Aligns with realized accounting, but hides entry-regime exposure | Segment IS/OOS by `entry_date` around explicit `--split-date`. |

## Data Flow

```text
Fixture/Alpaca bars -> BacktestRun.scan_decisions() -> pending entries by next session
         -> portfolio state -> pure gate predicates -> SimulatedTrade log
         -> compute_metrics()/equity summary/split metrics -> CLI JSON report
```

Daily order is deterministic: sort dates, symbols, and same-day candidates; process exits/marks before new entries; scan day `d` using only bars `<= d`; queue accepted signals for the next available symbol session. The simulated kill-switch uses prior-session equity as `last_equity`; no wall clock, broker, SDK, or random source enters the domain/application replay path.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/invest/application/backtest_run.py` | Modify | Replace fixed-equity independent replay with portfolio state, open-position lifecycle, pure gate evaluation, telemetry counts, and deterministic daily equity summary. |
| `src/invest/domain/models.py` | Modify | Add frozen value objects for `BacktestResult`, `PortfolioSummary`, `GateTelemetry`, and optional split metadata while keeping `SimulatedTrade` raw pre-cost prices. |
| `src/invest/domain/backtest_metrics.py` | Modify | Add pure helpers to compute segment metrics and equity-summary drawdown from deterministic daily samples/trade log. |
| `src/invest/adapters/cli.py` | Modify | Add `--split-date`; include portfolio, gate, equity, IS/OOS, and warning fields in one stable JSON report. |
| `tests/application/test_backtest_run.py` | Modify | Add RED tests for overlapping positions, cash/buying-power, concurrency, deployed-equity, kill-switch, and deterministic equity telemetry. |
| `tests/domain/test_backtest_metrics.py` | Modify | Add RED tests for segment metrics and equity-summary math. |
| `tests/adapters/test_cli_backtest.py` | Modify | Add RED tests for report shape, split output, disclaimers, and broker isolation. |
| `fixtures/backtest/*` | Modify | Extend deterministic scenarios only as needed for contention/split coverage. |

## Interfaces / Contracts

`BacktestRun.replay(inputs, *, split_date: date | None = None) -> BacktestResult` becomes the main interface. `BacktestResult` contains raw `trades`, `metrics`, `gate_counts: dict[str, int]`, `equity_summary`, `segments` (`is`, `oos`, keyed by entry date when `split_date` is present), and `warnings`. CLI JSON keeps existing top-level metrics for compatibility and adds nested `portfolio`, `gates`, `equity`, `segments`, and disclaimer/warning keys.

Warnings MUST include current day-0 mechanics, approximate cost model, simulated portfolio gates, and static-universe OOS bias. Survivorship wording remains unavoidable.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Gate reuse, equity summary, split metrics | Strict TDD with focused pytest cases over frozen models and pure functions. |
| Integration | Portfolio replay ordering and overlapping positions | Fixture-driven `BacktestRun` tests with hand-computed cash/equity/gate counts. |
| E2E | CLI report contract and no broker touch | `cli.backtest_main` tests asserting one JSON record, warnings, segments, and AST/monkeypatch broker guards. |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. This change adjusts an existing CLI's arguments/report only and does not execute commands or integrate processes.

## Migration / Rollout

No data migration required. Rollback is a source-only revert of portfolio result/report changes to restore fixed-equity replay; fixtures remain compatible or can be reverted with the same change.

## Open Questions

None.

## Next Recommended Phase: sdd-tasks
