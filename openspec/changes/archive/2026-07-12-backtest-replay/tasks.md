# Tasks: Backtest Replay Harness

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 800–1,100 (authored; excludes generated fixture JSON) |
| 400-line budget risk | High |
| Chained PRs recommended | No |
| Suggested split | Single PR (size:exception) — same 700–1,100 range as 3 prior single-domain-plus-adapter slices, historically shipped unchained |
| Delivery strategy | ask-on-risk |
| Chain strategy | size-exception |

Decision needed before apply: Yes
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | `fetch_range` via extracted `_paginate`; fetch() regression | PR 1 | `uv run --extra dev pytest tests/adapters/test_alpaca_market_data.py` | N/A: `httpx.MockTransport`, no live network | Revert `_paginate`/`fetch_range`/`_request_params` extraction; `fetch()` untouched |
| 2 | Look-ahead killer test + day-by-day window harness | PR 1 | `uv run --extra dev pytest tests/application/test_backtest_run.py -k "lookahead or window"` | N/A: synthetic fixture bars only | Delete `application/backtest_run.py`'s window loop; scanner/sizing untouched |
| 3 | Trade simulation (entry/exit/tie-break) | PR 1 | `uv run --extra dev pytest tests/application/test_backtest_run.py -k "trade or stop or open_at_end"` | N/A: in-memory bar fixtures | Delete `SimulatedTrade` + simulation loop |
| 4 | `backtest_metrics.py` + cost model + disclaimers + JSON keys | PR 1 | `uv run --extra dev pytest tests/domain/test_backtest_metrics.py` | N/A: pure Decimal, hand-computed | Delete `domain/backtest_metrics.py` |
| 5 | `invest-backtest` CLI + boundary + out-of-scope guard | PR 1 | `uv run --extra dev pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py` | `uv run invest-backtest --universe fixtures/backtest/universe.json --bars fixtures/backtest/bars.json --format json` | Remove `backtest_main`, console script, boundary-test additions |

## Phase 1: Fixture + fetch_range Extraction

- [x] 1.1 Create `fixtures/backtest/` synthetic multi-year fixture: few symbols, several years of aligned bars; one clean win, one clean loss, one open-at-end case. — WIN/LOSS/OPENEND symbols, 20 flat + breakout + divergent tail; verified by hand (script run) to produce exactly 1 take-profit, 1 stop, 1 open-at-end trade.
- [x] 1.2 RED: `tests/adapters/test_alpaca_market_data.py` — pin `fetch()`'s current `start=as_of-40d`/`end=as_of` params + output as a baseline snapshot, before any refactor. — GREEN pre-refactor too (behavior-preserving regression pin, not new behavior); re-confirmed GREEN post-refactor (1.5).
- [x] 1.3 RED: same file — `fetch_range(universe, start, end)` missing from `AlpacaMarketDataReader`. — confirmed `AttributeError: 'AlpacaMarketDataReader' object has no attribute 'fetch_range'`.
- [x] 1.4 GREEN: extract `_paginate(universe, start, end)` + `_request_params(start, end)` in `adapters/alpaca_market_data.py`; `fetch()` becomes `_paginate(as_of-CALENDAR_BUFFER_DAYS, as_of)`; `fetch_range` calls `_paginate` untrimmed.
- [x] 1.5 GREEN: re-run 1.2 — `fetch()` output byte-identical pre/post extraction. — 20 passed, 1 skipped in test_alpaca_market_data.py.

## Phase 2: Look-Ahead Prevention + Day-by-Day Harness

- [x] 2.1 RED (killer test): `tests/application/test_backtest_run.py` — replay day N, mutate bars dated after N, rerun; day N's decision must be byte-identical. Must fail first (harness absent). — confirmed `ModuleNotFoundError: No module named 'invest.application.backtest_run'`.
- [x] 2.2 RED: same file — `BacktestRun` missing; window-slicing test asserts `scanner.scan()` receives only bars `date <= d`. — same ModuleNotFoundError, confirmed alongside 2.1.
- [x] 2.3 GREEN: create `application/backtest_run.py::BacktestRun` — per day `d`, `window = bars[date<=d]`, call unchanged `MomentumScanner.scan()`, act only on `decision_date==d` accepted signals. Re-run 2.1 green. — 9/9 passed in test_backtest_run.py (includes 3.x trade-sim tests, implemented together).

## Phase 3: Trade Simulation

Note (reconcile #4): "sizing functions" here = `compute_intent` ONLY. `evaluate_gates`/portfolio caps are explicitly out of scope — this replay isolates scanner edge, not portfolio construction. No code change beyond the `compute_intent` call in 3.5.

- [x] 3.1 RED: accepted day-N signal sizes via `compute_intent`; entry fills at day N+1 open; skip when no N+1 bar exists. — RED via same ModuleNotFoundError as 2.1/2.2 (single test file authored together); GREEN after 3.5.
- [x] 3.2 RED: forward bar-touch exit — stop on `low<=stop` (fill `min(open,stop)`); TP on `high>=take_profit` (fill `take_profit`). — GREEN after 3.5.
- [x] 3.3 RED: same-bar stop+TP tie resolves `exit_reason="stop"` (worst-case, deterministic). — GREEN after 3.5.
- [x] 3.4 RED: no exit through end of data closes at last bar's close, `exit_reason="open-at-end"`. — GREEN after 3.5.
- [x] 3.5 GREEN: implement simulation loop in `BacktestRun`; add frozen `SimulatedTrade` to `domain/models.py` (symbol, entry_date, exit_date, entry_price, exit_price, qty, exit_reason). Re-run 3.1–3.4 green. — all 9 tests in test_backtest_run.py pass.

## Phase 4: Pure Backtest Metrics + Cost Model

- [x] 4.1 RED: `tests/domain/test_backtest_metrics.py` — `compute_metrics` missing; hand-computed `hit_rate`/`expectancy`/`max_drawdown`/`trade_count` from a fixed 3-trade mixed win/loss log. — confirmed `ModuleNotFoundError: No module named 'invest.domain.backtest_metrics'`.
- [x] 4.2 RED: same file — `apply_costs` hand-computed: slippage both sides, zero commission, tax on gains only. — same ModuleNotFoundError, confirmed alongside 4.1.
- [x] 4.3 GREEN: create `domain/backtest_metrics.py` — `ExitReason` StrEnum (`stop`/`take-profit`/`open-at-end`), `apply_costs`, `compute_metrics` returning `Metrics` (`hit_rate`, `expectancy`, `max_drawdown`, `trade_count`, `net_pnl`); empty log → zeros. — 5/5 passed in test_backtest_metrics.py.

## Phase 5: Report Contract — Disclaimers + Literal JSON Keys

- [x] 5.1 RED (reconcile #2): literal-string presence test for ALL THREE disclaimers — day0, survivorship, AND cost_model (cost_model must not be omitted). — RED via `AttributeError: module 'invest.adapters.cli' has no attribute 'backtest_main'` (authored together with 6.1/6.2 in test_cli_backtest.py).
- [x] 5.2 GREEN: report builder emits `"disclaimers": {"day0": "...", "survivorship": "...", "cost_model": "..."}` as an object keyed by all three — not an array, not partial. — note: design.md ALREADY specifies the exact cost_model literal string verbatim (contradicting the instruction to compose it); used design.md's literal string for consistency (judgment call, documented in final report).
- [x] 5.3 RED (reconcile #3): `tests/adapters/test_cli_backtest.py` — CLI JSON output has exact top-level keys `hit_rate`, `expectancy`, `max_drawdown`, `trade_count`, `net_pnl` (snake_case), not just internal `compute_metrics` fields. — same RED batch as 5.1.
- [x] 5.4 GREEN: CLI report serializer surfaces `Metrics` fields as top-level snake_case JSON keys. — verified via manual `invest-backtest --bars` run + test assertions.

## Phase 6: invest-backtest CLI

- [x] 6.1 RED: successful `--bars` run prints one report with metrics + both mandatory labels, zero `BrokerPort` calls. — confirmed RED via `AttributeError` (backtest_main absent), 6 failures in test_cli_backtest.py.
- [x] 6.2 RED: invalid/missing fixture prints exactly one `{"reason": ...}` record, exit 2. — same RED batch.
- [x] 6.3 GREEN: implement `adapters/cli.py::backtest_main` (`--universe`, `--bars` | `--start`/`--end` via `fetch_range`, `--format json`, `--slippage-bps`, `--tax-rate`); register `invest-backtest` in `pyproject.toml`. — 6/6 passed in test_cli_backtest.py; manual run against `fixtures/backtest/` and live `--start/--end` path both verified (see final report).

## Phase 7: Boundaries + Out-of-Scope Guard

- [x] 7.1 RED: `tests/test_boundaries.py` — backtest import graph (`backtest_run.py`, `backtest_metrics.py`, `backtest_main`) contains no `alpaca_broker`/`BrokerPort` import. — test authored fresh (negative-space guard); confirmed GREEN immediately since no violation was ever introduced (no code change needed, per 7.2's own note).
- [x] 7.2 GREEN: confirm assertion passes (additive-only design; no expected production change). — confirmed, 6/6 passed in test_boundaries.py.
- [x] 7.3 RED (reconcile #1): repo-scan test, mirroring the paper-execution hardcoded-paper-URL negative test — no gap-trading strategy module, no confirmation-service module, no live-trading URL/branch string exists anywhere under `src/`. — test authored fresh (negative-space guard); confirmed GREEN immediately, no violation ever introduced.
- [x] 7.4 GREEN: confirm assertion passes as-is (negative-space guard against future scope creep). — confirmed, 6/6 passed in test_boundaries.py.
