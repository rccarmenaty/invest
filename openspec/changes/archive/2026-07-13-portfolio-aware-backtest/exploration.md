# Exploration: portfolio-aware-backtest

Evolve the current day-0-only historical replay harness into a credible multi-year strategy evaluation with portfolio-aware capital/exposure handling, point-in-time universe semantics, realistic execution assumptions, and out-of-sample validation. The existing three-symbol backtest fixture validates pipeline mechanics only — not strategy edge.

## Current State

### What the backtest-replay harness does today

`BacktestRun` (`src/invest/application/backtest_run.py`) replays a sorted bar history day-by-day through the unchanged `MomentumScanner` and `compute_intent`, producing `SimulatedTrade` objects with raw (pre-cost) prices. `backtest_metrics.py` applies a fixed-bps cost model and computes hit rate, expectancy, max drawdown, and trade count. The `invest-backtest` CLI prints a JSON report with mandatory disclaimers.

### Critical limitations (by design, per backtest-replay Named Decisions)

1. **No portfolio accounting** (line 13-14 of backtest_run.py: "Portfolio construction ... is deliberately NOT simulated"): Every accepted signal is sized independently at fixed `NOMINAL_EQUITY = Decimal("100000")`. Equity never evolves across trades. `evaluate_gates` (concurrency cap, equity cap) and `evaluate_halt_gates` (kill-switch, broker guard) exist proven in `sizing.py` but are explicitly NOT called by the backtest harness.

2. **Day-0 CANDIDATE mechanics only** (Named Decision 1): The scanner detects spike day-0 rules (rel-vol, ATR move, breakout, not extended). No day+1/+2 confirmation exists — the `confirmator` service from SPEC §3.3 has never been built. No trend filter (50 MA vs 200 MA), no follow-through check, no earnings/gap check. The harness explicitly labels itself "day-0 mechanics only."

3. **Static, survivorship-biased universe** (Named Decision 2): Universe loaded from a static JSON fixture. The 3-symbol backtest fixture (WIN, LOSS, OPENEND) is synthetic — the latest `universe.json` has AAPL, MSFT, NVDA. Zero universe evolution across time: no symbols added, removed, delisted, or merged. The report carries a survivorship-bias disclaimer but the code does not enforce anything beyond it.

4. **No out-of-sample validation**: `invest-backtest` replays the entire range as one flat run. No train/test split, no walk-forward optimization framework, no rolling window. There is no way to test whether signals identified in one period generalize to the next.

5. **No execution realism**: Fixed 5bps slippage, zero commission, flat 15% tax on gains. No volume-dependent slippage, no spread modeling, no borrow costs, no partial-fill simulation. Reported as approximation only.

6. **Cost model is not portfolio-aware**: Costs are applied per-trade in `apply_costs` but there's no capital allocation tracking — a $100k equity account taking 5 concurrent $20k positions deploys 100% of capital, which the current harness can't detect or prevent.

### What exists and is reusable

- **Pure domain functions**: `MomentumScanner.scan()`, `compute_intent()`, `evaluate_gates()`, `evaluate_halt_gates()`, `average_true_range()`, `backtest_metrics.compute_metrics()` and `apply_costs()` are all pure, tested, and replay-safe.
- **Structured data contracts**: `DailyBar`, `ScanDecision`, `OrderIntent`, `SimulatedTrade`, `AccountSnapshot`, `Metrics` are frozen dataclasses.
- **Adapter boundaries**: `AlpacaMarketDataReader.fetch_range()` handles bulk historical fetch. `JsonFixtureReader` loads fixtures. Domain boundary tests (AST-based import bans) enforce hexagonal isolation.
- **Pydantic contract events**: `contracts/events.py` has versioned event schemas.
- **CLI pattern**: `invest-backtest --universe ... --bars ... --format json` with single-record failure style, exit 0/2.

### SPEC requirements this change addresses

- SPEC §2.1: "Never backtest using today's index membership retroactively" (PIT universe)
- SPEC §2.6: Risk rules — 1% per trade, max 5 concurrent, max 25% equity deployed, kill-switch
- SPEC §2.7: Expectancy math — hit rate ≥ ~40%; paper results must roughly match replay
- SPEC §5 Phase 2: "Replay/backtest over 2–3 years of point-in-time daily bars ... Positive expectancy"
- SPEC §7 checklist: point-in-time universe, adjusted bars, survivorship-bias guard, pre-registered assumptions

## Affected Areas

- `src/invest/application/backtest_run.py` — **Heavily modified.** Add portfolio state tracking (equity evolution, open positions, deployed capital), call `evaluate_gates`/`evaluate_halt_gates` before each entry, track equity curve, support OOS split boundary.
- `src/invest/domain/backtest_metrics.py` — **Extended.** Add `EquityCurve` metric, in-sample/out-of-sample breakdown, rolling-window metrics, drawdown duration, Sharpe-like ratio. Possibly a new `PortfolioMetrics` frozen dataclass alongside existing `Metrics`.
- `src/invest/domain/models.py` — **Extended.** May need `PortfolioState` (equity, cash, positions, daily snapshots for equity curve), `UniverseWindow` (symbols active for a date range), `DailyAccount` (tracked per-session state). `SimulatedTrade` may need `allocated_capital` field.
- `src/invest/domain/sizing.py` — **Unchanged or minimal.** `evaluate_gates` and `evaluate_halt_gates` are already proven pure and reusable as-is. May need `compute_allocated_capital` (equity / max_positions for equal-weight allocation) if not using the existing 1%-risk sizing.
- `src/invest/domain/scanner.py` — **Unchanged.** Design philosophy holds: scanner stays pure, harness owns window slicing.
- `src/invest/adapters/cli.py` — **Modified.** New flags: `--split-date` (ISO date for train/test boundary), `--portfolio-aware` (boolean or default-on), `--max-positions` (override), `--equity-model` (fixed vs evolving). `_backtest_report` extended with OOS metrics, equity curve summary.
- `src/invest/adapters/fixtures_json.py` — **May be extended.** If universe evolution is in first slice: support multi-period universe fixtures (universe per date range). If deferred: no change.
- `src/invest/domain/indicators.py` — **Possibly extended.** If trend filter (50/200 MA) is in scope: add `simple_moving_average(history, period)` pure function.
- `fixtures/` — **New fixtures needed.** Multi-symbol, multi-year test fixture with portfolio-contention scenarios (5+ concurrent signals, equity cap, kill-switch trigger). Realistic universe fixture for integration tests.
- `tests/` — **New test modules.** `tests/application/test_backtest_run_portfolio.py` (portfolio gates, equity evolution, concurrency), `tests/domain/test_backtest_metrics_portfolio.py` (equity curve, OOS split), `tests/adapters/test_cli_backtest_portfolio.py` (CLI flags, report shape). Existing boundary and broker-isolation tests must stay green.
- `pyproject.toml` — Likely no new dependencies. Possibly new pytest markers.

## Approaches

### Approach A: Minimal Portfolio Accounting (recommended first slice)

Additive to `BacktestRun`: evolve equity per trade, apply existing `evaluate_gates` for concurrency/deployment caps, track equity curve, add `--split-date` OOS split.

| Aspect | Detail |
|---|---|
| **Portfolio state** | `PortfolioState(equity, cash, positions: dict[symbol, Position])` updated after each `_simulate_trade`. `compute_intent` receives current equity instead of fixed nominal. |
| **Gate evaluation** | Before each entry: `evaluate_gates(intent, reason, snapshot, open_count, deployed_value, buying_power)`. Caps enforced exactly as in `execute_run.py`. Kill-switch baseline = starting equity. |
| **Equity curve** | Daily snapshots of equity recorded. `compute_metrics` extended with `EquityCurveMetrics` (total return, CAGR, max drawdown duration, Sharpe approximation). |
| **OOS split** | `--split-date 2024-01-01`: trades before = IS, after = OOS. Metrics computed separately for each set. Report surfaces IS/OOS divergence. |
| **Universe** | Static (unchanged from backtest-replay). Survivorship-bias disclaimer remains. |
| **Scanner** | Unchanged. Day-0 CANDIDATE mechanics. |
| **Cost model** | Unchanged. Fixed-bps approximation. |
| **Disclaimers** | Extended: new "portfolio-gates-simulated" label stating caps are simulated, not broker-enforced. Existing day-0 and survivorship labels stay. |

- **Pros**: Minimal new domain logic — `sizing.py`'s gates already tested and proven. Additive to BacktestRun, not a rewrite. Equity curve and OOS split are immediate, high-value additions. Can ship as one PR (~400–600 authored lines). Portfolio gates are the bottleneck capability — without them, multi-year backtests produce nonsense (every trade gets $100k independently).
- **Cons**: Still day-0 only (no confirmation). Still survivorship-biased (no PIT universe). OOS split on static universe is a weak validation signal. Doesn't address SPEC's core confirmation-based edge thesis.
- **Effort**: Medium
- **Lines estimate**: 400–600 authored (within 800-line review budget; no size:exception required)

### Approach B: Portfolio Accounting + Simulated Universe Evolution

Approach A plus a `UniverseCalendar` module that simulates symbol additions, removals, and delistings over time without real PIT vendor data.

| Aspect | Detail |
|---|---|
| **Universe evolution** | `UniverseCalendar` — a JSON schedule of symbol lifecycle events (active_from, active_until). Per-bar check: is this symbol in universe on this date? Exits triggered by delisting force close at next available bar. |
| **Fixture format** | `universe-calendar.json` with `events: [{symbol, active_from, active_until, reason}]`. Backward-compatible with existing flat `universe.json`. |
| **Harness integration** | `BacktestRun.replay()` checks universe membership per trading day. Symbols not yet listed or already delisted → scanner never sees them. Symbols delisted mid-trade → forced close. |
| **Metrics** | Trade log records `universe_event` for delisting-forced closes. Distinguish strategy exits from universe-driven exits. |

- **Pros**: Realistic multi-year portfolio simulation without vendor data dependency. Tests portfolio-level behavior when symbols enter/exit. Framework-ready: swap simulated universe for real PIT provider at same seam later. Addresses SPEC §2.1 more honestly than static universe (even if still simulated rather than real).
- **Cons**: More new code (new `domain/universe_calendar.py`, new fixture format, new test fixtures). Still not real PIT data — must be loudly disclaimed. Testing complexity increases (universe-event timeline fixtures). May exceed 800-line budget.
- **Effort**: Medium-High
- **Lines estimate**: 600–900 authored

### Approach C: Full Portfolio Stack + Confirmation Scaffold

Approaches A+B plus minimal confirmation logic (trend filter + follow-through only; no earnings/gap/catalyst data needed).

| Aspect | Detail |
|---|---|
| **Confirmation rules** | `ConfirmationChecker`: trend (50 MA > 200 MA on signal date), follow-through (price holds above breakout level after 1–2 sessions). No earnings check (no CorporateCalendarPort exists yet). |
| **Scanner interaction** | Scanner still emits day-0 CANDIDATE. ConfirmationChecker gates promotion to CONFIRMED. Harness only enters on CONFIRMED signals. |
| **New indicators** | `simple_moving_average(history, period)` in `indicators.py`. |
| **Labeling** | New disclaimer: "CONFIRMATION IS PARTIAL: uses trend and follow-through rules only; earnings, catalyst, and corporate-action checks are not implemented." |

- **Pros**: Measures closer to SPEC's intended edge (confirmation, not day-0 spike). Trend + follow-through use data already present (just need longer history windows). Most honest answer to "does the strategy work?" at this stage.
- **Cons**: Largest scope — new confirmation domain module, new MA indicators, new scanner interactions. Risk of building a confirmation that's still incomplete (no earnings/gap). Highest testing burden. Almost certainly exceeds 800-line budget.
- **Effort**: High
- **Lines estimate**: 800–1,200 authored (definitely needs chained PRs)

## Recommendation

**Approach A as the first slice (portfolio-aware-backtest), with Approach B and C as designated follow-ups.**

### Rationale

1. **Portfolio accounting is the bottleneck capability.** Without evolving equity and position caps, multi-year backtests produce nonsense — every trade gets $100k regardless of prior outcomes. Approach A unlocks credible multi-year simulation immediately with minimal new code.

2. **`evaluate_gates` / `evaluate_halt_gates` are already built, tested, and proven** in `sizing.py`. The backtest harness just needs to call them. This is the smallest code change with the highest impact — reusing proven domain functions rather than rewriting.

3. **OOS split is a cheap, high-value addition.** Adding `--split-date` and computing IS/OOS metrics separately requires ~50 lines. It immediately surfaces whether day-0 signals are curve-fitted to the training period. The project currently has zero OOS validation anywhere.

4. **Approach B (universe evolution) depends on Approach A.** Portfolio caps only matter when multiple positions compete for capital. Without portfolio accounting, universe evolution is cosmetic — every trade still gets $100k independently regardless of how many symbols are active.

5. **Approach C (confirmation) has a blocking dependency on Approach A.** Confirmation signals will produce different entry rates and different position overlap patterns. Testing confirmation's impact on portfolio behavior requires portfolio accounting to exist first.

6. **The SPEC's Phase 2 gate explicitly requires OOS.** The current backtest has zero out-of-sample validation. Adding it honors the SPEC's spirit even within the acknowledged day-0 limitation.

### Designated follow-up slices (not in scope for this change)

- **Slice 2** (`universe-evolution`): UniverseCalendar with simulated symbol lifecycle events → realistic multi-symbol portfolio behavior over years. Depends on Slice 1 (portfolio accounting).
- **Slice 3** (`confirmation-scaffold`): Trend filter + follow-through confirmation, 50/200 MA indicators, partial-confirmation labeling. Depends on Slices 1+2.
- **Slice 4** (`pit-universe-provider`): Real point-in-time index membership provider (vendor-dependent, deferred pending data source selection).
- **Slice 5** (`execution-realism`): Dynamic spread modeling, volume-dependent slippage, borrow costs, partial-fill simulation.

### Named decisions to carry forward from backtest-replay

1. **Day-0-only mechanics** (carried from backtest-replay Decision 1): This change validates day-0 CANDIDATE mechanics — confirmation edge is a separate future slice. Every report must carry the existing day-0 label.
2. **Survivorship-biased universe** (carried from Decision 2): Static universe remains. Every report must carry the existing survivorship-bias disclaimer.
3. **Portfolio-gates-simulated** (new label): Gates are enforced by the harness, not by a broker. Especially important for the kill-switch which in production reads live account state.

## Risks

- **Portfolio-gate simulation might mask real strategy defects.** A strategy that hits the 5-position cap 90% of the time in simulation would be starved in live trading. The gates should be reported as a metric (how often they fire) not just enforced silently.
- **Fixed starting equity doesn't model deposits/withdrawals.** Acceptable for a first slice (no live account integration exists) but must be documented.
- **OOS split on a static universe is a weak signal.** Without PIT universe, the OOS period sees the same symbols as IS — this inflates OOS performance artificially. The disclaimer must state "OOS validation operates on the same survivorship-biased universe as in-sample; this inflates OOS results."
- **Kill-switch baseline ambiguity.** In live trading, `last_equity` is the prior day's close. In backtest, the baseline could be starting equity (one-time) or prior-session equity (daily). Daily is more realistic but more complex. Recommendation for Slice 1: prior-session equity for kill-switch, starting equity for drawdown from inception.
- **Equity curve serialization risk.** Adding daily equity snapshots to a multi-year backtest of 700+ symbols could produce large JSON output. Recommend summary statistics in the CLI report + optional full-curve file output.
- **Review budget.** Approach A is estimated at 400–600 authored lines. Within the 800-line session preflight budget, this fits comfortably as a single PR with Low risk; no `size:exception` is required. The sdd-tasks forecast should confirm the estimate and note the low risk.

## Ready for Proposal

**Yes**, with the following constraints to carry forward into sdd-propose:

1. First slice is Approach A (portfolio accounting + equity curve + OOS split). Approaches B and C are out of scope for this change — named as deferred follow-ups.
2. The three backtest-replay Named Decisions (day-0-only, survivorship-biased, gap-trading-rejected) carry forward unchanged.
3. A new Named Decision "portfolio-gates-simulated" must be recorded: gates are harness-enforced, not broker-enforced.
4. Proposal must explicitly state that portal gates (kill-switch, concurrency cap, equity cap) are reported as metrics (how often they fire), not just enforced silently.
5. OOS disclaimer must warn that the same survivorship-biased universe spans both IS and OOS periods.
6. The `sdd-tasks` forecast must confirm the 400–600 line estimate fits within the 800-line preflight budget (Low risk, single PR).
