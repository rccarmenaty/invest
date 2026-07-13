# Proposal: Momentum Selection Scanner

## Intent

Only the benchmark day-0 spike detector (SPEC §2.5) is implemented; the research-primary Core 52-Week-High Momentum Breakout selection layer (SPEC §2.3–2.4) has no code, blocking ROADMAP §5 changes B/C/D. Add the Core model as a sibling scanner running through the same backtest harness so results are directly comparable against the benchmark control.

## Scope

### In Scope
- New cross-sectional `domain/momentum_selection_scanner.py`: 12-1 momentum rank (top 15%), 52-week-high proximity (≥95%), 50/200-day trend filter, reuse of the 20-day-high breakout trigger.
- New indicator helpers (SMA, trailing high, momentum return, SMA-rising) and granular `RejectionReason` members.
- `ScannerPort` Protocol; `--strategy {benchmark,core}` on `invest-backtest` only, default `benchmark`.
- New 252-day bar fixture set with paired extended market-context fixture.

### Out of Scope
- Trailing exits/time stops (B), regime filter and volatility sizing (C), pass/fail gate (D).
- Live/paper execution changes; parameter-grid tooling.
- Editing existing `MomentumScanner` or existing short fixtures in place.

## Proposal Question Round

Defaults chosen (delegated run; flag for user review):
- **Top-15% cutoff**: `k = ceil(0.15 × ranked_pool_size)` over symbols with full history; ties broken by return desc, then symbol asc. Ceiling guarantees ≥1 candidate on small universes and stays deterministic.
- **SMA200 rising**: candidate day excluded; SMA200 over closes ending at t−1 must be strictly greater than SMA200 ending at t−21. Fits within the 253-bar momentum history requirement.
- **Rejection granularity**: one reason per filter layer — "rejections are journal gold" (SPEC §2.6).

## Capabilities

### New Capabilities
- `momentum-selection-scanner`: cross-sectional Core selection rules, deterministic ranking/tie-breaks, granular rejection reporting.

### Modified Capabilities
- `trading-system`: backtest strategy selection via CLI flag; default preserves current benchmark behavior unchanged.

## Approach

Exploration Approach 1: `BacktestRun.scan_decisions()` already passes the full per-day cross-sectional window, so the seam exists. Add `ScannerPort`, loosen the `BacktestRun` type hint, wire the flag in the backtest parser only. Decimal-only, clock-free, output sorted `(decision_date, symbol)`. Forecast 600–900 authored lines against the 800-line budget → 3 chained PR slices: (1) indicators + rejections + fixtures, (2) domain scanner TDD, (3) port + CLI + boundary tests.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `src/invest/domain/momentum_selection_scanner.py` | New | Core selection scanner |
| `src/invest/domain/indicators.py` | Modified | SMA, trailing high, momentum return, rising check |
| `src/invest/domain/rejection.py` | Modified | Per-layer rejection reasons |
| `src/invest/application/ports.py` | Modified | `ScannerPort` Protocol |
| `src/invest/application/backtest_run.py` | Modified | Type hint loosened to port |
| `src/invest/adapters/cli.py` | Modified | `--strategy` on backtest parser only |
| `tests/test_boundaries.py` | Modified | Flag stays backtest-only |
| `fixtures/` | New | 252-day bars + paired market context |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Authored lines exceed 800 budget | High | Pre-committed 3-slice chained delivery |
| Fixture/market-context date drift | Med | Generate both together; `require_complete` fails closed |
| Benchmark path regression | Low | Default `benchmark`; existing tests untouched |

## Rollback Plan

Revert the new domain module, port, CLI flag, fixtures, and tests; default `benchmark` means removal restores current behavior exactly. No state migration.

## Dependencies

- `point-in-time-market-context` delivered (in flight per ROADMAP §3).

## Success Criteria

- [ ] `invest-backtest --strategy core` replays the Core model through the unchanged harness; `benchmark` (and no flag) reproduces current output byte-for-byte.
- [ ] Ranking and filters are deterministic (Decimal-only, documented tie-breaks) across repeated runs.
- [ ] Every rejection carries a per-layer reason visible in the journal.
- [ ] Boundary tests pass for the new domain file and backtest-only flag.
