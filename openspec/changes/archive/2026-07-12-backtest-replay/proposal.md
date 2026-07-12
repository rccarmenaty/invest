# Proposal: Backtest Replay Harness

## Intent

SPEC mandates proving expectancy via backtest/replay before live trading — a phase this project built out of order (paper execution shipped first). This change adds a CLI-first backtest harness that replays 2–3 years of daily history through the existing pure scanner/sizing functions and reports whether the momentum strategy has measurable edge.

## Named Decision 1: Day-0-only backtest (user-resolved)

The harness validates exactly the day-0 `CANDIDATE` mechanics that `paper-trading-execution` already runs live — explicitly labeled as measuring CURRENT mechanics, NOT SPEC §2.4's confirmed-entry thesis. A future confirmation-service slice needs its own separate backtest once built. Mirrors the day-0 interim decision already recorded in `paper-trading-execution`.

## Named Decision 2: Survivorship-biased universe (user-resolved)

NOT compliant with true point-in-time index membership (no such data source exists or is in scope). A fixed historical liquid-universe screen is used instead, loudly disclaimed as survivorship-biased in EVERY report the harness produces — never silently claimed point-in-time-correct.

## Named Decision 3: Gap-trading rejected (user-resolved)

A close-to-open gap-trading strategy variant was explicitly considered and REJECTED — out of scope entirely, not deferred to a queued future change.

## Scope

### In Scope
- `invest-backtest` CLI harness replaying `MomentumScanner`/`sizing.py` day-by-day; no new infra.
- Extend `AlpacaMarketDataReader` with `fetch_range(universe, start, end)` for bulk history (additive).
- New pure `domain/backtest_metrics.py`: hit rate, expectancy, drawdown, trade count/log.
- Cost model: fixed-bps slippage + zero commission (Alpaca equities) + flat tax haircut — reported as an approximation, not precision.
- SPEC acceptance framing: hit rate ≥ ~40% = positive signal; <35% = filters broken. Report the number; never gate CI on it (research result, not merge gate).

### Out of Scope
- Gap-trading strategy (rejected, Decision 3); confirmation-service build-out; live trading.
- NATS/Postgres/Kubernetes; walk-forward optimization/parameter tuning; options/multi-asset; real point-in-time universe provider.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `trading-system`: add backtest-replay requirements — bulk range fetch, day-by-day replay harness, pure metrics, cost-model approximation, mandatory disclaimers, non-gating acceptance framing.

## Approach

Hexagonal, mirroring prior slices: pure domain (`backtest_metrics.py`) computes metrics from replayed deterministic events; the application harness iterates days reusing proven pure functions; the adapter owns bulk HTTP fetch. CLI never touches `BrokerPort`. Small synthetic multi-year fixture for tests.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/invest/application/backtest_run.py` | New | Day-by-day replay harness. |
| `src/invest/domain/backtest_metrics.py` | New | Pure metrics + trade log. |
| `src/invest/adapters/alpaca_market_data.py` | Modified | Add `fetch_range()`. |
| `src/invest/adapters/cli.py` | Modified | `invest-backtest` entrypoint. |
| `fixtures/` | New | Synthetic multi-year fixture. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Day-0 result misread as confirmed-entry validation | Medium | Loud labeling in every report (Decision 1). |
| Survivorship bias inflates results | Certain (accepted) | Mandatory disclaimer in every report (Decision 2). |
| Cost model too coarse | Medium | Reported as approximation; bps configurable. |
| Hit rate legitimately <35% | Possible | Valid research outcome, not a harness defect; no CI gate. |

## Rollback Plan

Delete `backtest_run.py`, `backtest_metrics.py`, the CLI entrypoint, and fixtures; revert `fetch_range()` addition. Scan/execute pipeline untouched — zero persisted state.

## Dependencies

- Alpaca Market Data API history depth (2–3 years daily bars) via existing env vars; `httpx` (present).
- Archived `implementation-foundation`, `market-data-adapter`, `paper-trading-execution` slices.

## Success Criteria

- [ ] `invest-backtest` produces hit rate, expectancy, drawdown, and trade log over a multi-year range.
- [ ] Every report carries the day-0-mechanics label and survivorship-bias disclaimer.
- [ ] `fetch_range()` is additive; existing `fetch()` behavior unchanged.
- [ ] Metrics module is pure and deterministic on the synthetic fixture.
- [ ] No CI gate on hit-rate thresholds; number is reported only.
