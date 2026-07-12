# Design: Backtest Replay Harness

## Technical Approach

Mirror the prior hexagonal slices. The adapter grows one additive bulk-history method
(`fetch_range`) reusing the existing pagination/retry/error machinery. A new application
service `BacktestRun` replays the fixture **day-by-day**, feeding the UNCHANGED
`MomentumScanner.scan()` a window sliced up to each trading day (no look-ahead structurally
guaranteed by the window, not by scanner changes). Accepted signals become independent
simulated trades filled at next-session open, exited by bar-based stop/TP touch. A new pure
`domain/backtest_metrics.py` is the single accounting authority: it applies the cost model
(slippage + zero commission + tax haircut) and computes hit rate, expectancy, drawdown, and
trade count from a raw trade log. The `invest-backtest` CLI never imports `alpaca_broker` or
`BrokerPort`. Every report carries loud day-0 and survivorship labels.

## Architecture Decisions

### Decision: `fetch_range` shares `fetch()`'s loop via an extracted paginator
**Choice**: Extract the page loop into private `_paginate(universe, start, end) -> FixtureInputs`
and `_request_params(universe, start, end)`. `fetch(universe, as_of)` becomes
`_paginate(universe, as_of - timedelta(days=CALENDAR_BUFFER_DAYS), as_of)`;
`fetch_range(universe, start, end)` calls `_paginate(universe, start, end)` with **no**
`CALENDAR_BUFFER_DAYS` trimming. Same `MAX_PAGES`, `_send_with_retry`, error taxonomy, symbol-ordered output.
**Alternatives**: new standalone adapter (duplicated retry/error logic — rejected); loop `fetch(as_of)` per day (needless N calls — rejected).
**Rationale**: Behavior-preserving refactor. A regression test asserts `fetch()` still emits `start = as_of - 40d`, `end = as_of` and identical results — `fetch()` is untouched observationally.

### Decision: no look-ahead via harness-controlled window, scanner unchanged
**Choice**: `BacktestRun` holds the full sorted bars. For each trading date `d` (from the
first date with `HISTORY_DAYS+1` bars to the last), it builds
`window = tuple(b for b in bars if b.date <= d)` and calls `scanner.scan(universe, window)`.
`scan()` already uses `bars[-1]` as candidate and `bars[-(HISTORY_DAYS+1):-1]` as history, so
day `d` IS the candidate bar. Only decisions with `decision_date == d` and `accepted` are acted on.
ZERO changes to `MomentumScanner`/`sizing`.
**Alternatives**: pass an `as_of` into `scan()` (mutates proven pure function — rejected); precompute per-symbol trailing windows (optimization deferred; correctness first).
**Rationale**: Bars with `date > d` are physically absent from the window, so no future data can influence day `d`. The killer test mutates future bars and asserts the day-`d` decision is byte-identical. Assumes an aligned trading calendar (synthetic fixture guarantees; liquid US daily bars are calendar-aligned).

### Decision: trade simulation — next-open entry, bar-touch exit, stop-wins tie-break
**Choice**: On an accepted day-`N` signal: size via `sizing.compute_intent(symbol, N, EQUITY, history, dayN.close)`
(reuses live stop/TP/qty math; `history`/entry-ref anchored to day `N` close exactly as live).
Simulated **entry fill = day N+1 open** (skip if no N+1 bar). Scan forward from the entry bar
onward: **stop** triggers if `low <= stop` (fill `min(open, stop)` — gap-down honored);
**take-profit** triggers if `high >= take_profit` (fill `take_profit` — gap-up not credited).
Same-bar tie (both touched) → **STOP wins** (worst-case, deterministic). No exit through end of
data → close at last bar `close`, reason `open-at-end`. Portfolio gates (`evaluate_gates`,
concurrency/equity caps) are NOT simulated — each signal is one independent trade at fixed
nominal `EQUITY` to isolate scanner edge, not portfolio construction (documented).
**Alternatives**: same-day close-price entry (look-ahead on the signal bar — rejected); intraday tick fills (no tick data exists — impossible).
**Rationale**: Only OHLC exists; conservative touch detection with stop-wins tie-break never over-credits. Faithful to live bracket mechanics (market entry ~next open, bracket stop/TP from `compute_intent`).

### Decision: all cost application lives in pure `backtest_metrics.py`
**Choice**: `BacktestRun` records `SimulatedTrade` with RAW bar-derived prices only. Metrics
applies costs purely: `entry_fill = entry*(1+bps/10000)`, `exit_fill = exit*(1-bps/10000)`,
`gross = (exit_fill-entry_fill)*qty`, commission `0`, `net = gross if gross<=0 else gross*(1-tax_rate)`
(tax on gains only). `slippage_bps`/`tax_rate` are CLI-configurable, reported as approximation.
**Rationale**: One accounting authority; harness stays cost-free and trivially testable; metrics stay pure Decimal (covered by the existing domain AST ban). Slippage/tax are pure functions with hand-computable outputs.

## Data Flow

    invest-backtest --universe --start --end | --bars  --format json
        │  (--bars) JsonFixtureReader → FixtureInputs
        │  (--start/--end, live) AlpacaMarketDataReader.fetch_range → FixtureInputs
        ▼
    BacktestRun.replay(inputs):
        for d in sorted trading dates:
            window = bars[date <= d]
            MomentumScanner.scan(universe, window)  ← UNCHANGED, no look-ahead
            for accepted decision (decision_date == d):
                compute_intent(dayN.close, history) → qty/stop/take_profit
                entry = bar[N+1].open;  forward-scan bars → stop/TP/open-at-end
                record SimulatedTrade(raw entry/exit/qty/reason/dates)
        ▼
    backtest_metrics: apply slippage+tax (pure) → hit_rate, expectancy,
                      max_drawdown, trade_count, trade_log
        ▼
    JSON report {disclaimers[day0,survivorship], metrics, trades}

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/invest/adapters/alpaca_market_data.py` | Modify | Extract `_paginate`; add `fetch_range`; `_request_params(start,end)`. |
| `src/invest/application/backtest_run.py` | Create | `BacktestRun.replay` day-by-day; next-open entry, bar-touch exit. |
| `src/invest/domain/models.py` | Modify | Add `SimulatedTrade` frozen dataclass. |
| `src/invest/domain/backtest_metrics.py` | Create | `ExitReason`, pure cost fns, `compute_metrics`. |
| `src/invest/adapters/cli.py` | Modify | `backtest_main` (`invest-backtest`), single-record failure. |
| `src/invest/domain/rejection.py` | Modify (if needed) | Reuse existing reasons; add none unless required. |
| `pyproject.toml` | Modify | `invest-backtest` script entry. |
| `fixtures/` | Create | Small synthetic multi-year fixture (aligned calendar). |
| `tests/test_boundaries.py` | Modify | Assert backtest modules never import `alpaca_broker`/`BrokerPort`. |

## Interfaces / Contracts

```python
# models.py
@dataclass(frozen=True)
class SimulatedTrade:
    symbol: str; entry_date: date; exit_date: date
    entry_price: Decimal; exit_price: Decimal; qty: int
    exit_reason: str            # ExitReason value (raw prices — pre-cost)

# backtest_metrics.py (pure, Decimal)
class ExitReason(StrEnum): STOP="stop"; TAKE_PROFIT="take-profit"; OPEN_AT_END="open-at-end"
def apply_costs(t, slippage_bps, tax_rate) -> Decimal          # net P&L per trade
def compute_metrics(trades, slippage_bps, tax_rate) -> Metrics # hit_rate, expectancy, max_drawdown, trade_count, net_pnl
```

**Formulas** (all Decimal, empty-list-safe → zeros): `trade_count = len(trades)`;
`net_i = apply_costs(t_i)`; `hit_rate = count(net_i > 0)/trade_count`;
`expectancy = sum(net_i)/trade_count` (avg net P&L per trade); equity curve = cumulative `net_i`
in `(exit_date, entry_date, symbol)` order, `max_drawdown = max(running_peak - cumulative)` (≥ 0).

**Mandatory report strings** (literal, asserted present by a test — not just field existence),
under JSON key `"disclaimers"`:
- `"DAY-0 MECHANICS ONLY: measures current day-0 paper-trading entry mechanics, NOT SPEC §2.4 confirmed-entry edge."`
- `"SURVIVORSHIP-BIASED UNIVERSE: fixed historical screen, NOT point-in-time index membership; results are optimistically biased."`
- `"COST MODEL IS AN APPROXIMATION: fixed-bps slippage + zero commission + flat tax haircut, not precision accounting."`

**CLI** — `invest-backtest --universe PATH (--bars PATH | --start DATE --end DATE) --format json`
`[--slippage-bps N] [--tax-rate R]`. `--bars` = offline fixture (primary tested path);
`--start/--end` = live `fetch_range` (creds, `live` marker). Success → exit 0, full report JSON.
Failure → exactly one `{"reason": ...}` record, exit 2 (mirrors `execute_main`). Boundary: the
backtest import graph contains NO `alpaca_broker` / `BrokerPort` (new boundary-test assertion).

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit (killer) | Look-ahead prevention: mutate bars `date > N`, assert day-`N` decision unchanged | Fixture + `BacktestRun` |
| Unit | Trade-sim determinism: same fixture → identical trade log | Fixed fixture |
| Unit | Stop/TP same-bar tie → `exit_reason=stop`, fill=`stop`; gap-down fill=`min(open,stop)` | Crafted bars |
| Unit | `open-at-end`; skip when no `N+1` bar | Crafted bars |
| Unit (domain) | `hit_rate`/`expectancy`/`max_drawdown`/`trade_count` vs hand-computed; cost slippage+tax | Pure lists |
| Unit (adapter) | `fetch_range` no buffer trim; `fetch()` params/results UNCHANGED (regression) | `httpx.MockTransport` |
| Unit (CLI) | `--bars` produces report + literal disclaimer strings; exit 0/2 | Synthetic multi-year fixture |
| Boundary | Backtest graph excludes broker/`BrokerPort`; `backtest_metrics` under domain AST ban | AST tests |

**Strict TDD sequence (RED first):** (1) `_paginate` extraction, `fetch()` regression green;
(2) `fetch_range` wider window, no trim; (3) `SimulatedTrade` + `ExitReason`; (4) metrics
formulas hand-computed; (5) cost slippage+tax-on-gains; (6) harness window → correct day-`N`
scan; (7) **killer look-ahead** test; (8) next-open entry + forward stop/TP; (9) tie-break
stop-wins + gap + open-at-end; (10) disclaimer literal-string report; (11) `backtest_main`
exit 0/2; (12) boundary import ban.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or
process integration. `fetch_range` reuses the existing read-only GET client (no mutation, no
new outbound surface beyond the archived market-data adapter). The CLI performs no writes.

## Migration / Rollout

No migration; zero persisted state. Rollback: delete `backtest_run.py`,
`backtest_metrics.py`, `SimulatedTrade`, the CLI entry, fixtures, and boundary-test lines; revert
the `_paginate`/`fetch_range` extraction — scan/execute untouched.

## Decisions and Tradeoffs

| Decision | Rejected alternative | Rationale |
|---|---|---|
| **Day-0-only backtest** (Named Decision 1) | Build confirmation service first | Measures current live paper mechanics; loud label in every report; confirmation needs earnings data that doesn't exist. |
| **Survivorship-biased fixed universe** (Named Decision 2) | Point-in-time index membership | No such data source in scope; mandatory disclaimer in every report, never silent. |
| **Gap-trading rejected** (Named Decision 3) | Defer/queue a gap variant | Out of scope entirely, not deferred. |
| Same-bar tie → **stop wins**; TP gap not credited | TP wins / average | Conservative, deterministic, never over-credits with OHLC-only data. |
| `fetch_range` via extracted `_paginate` | New adapter / daily loop | Additive; regression test proves `fetch()` behavior identical. |
| Scanner UNCHANGED; harness owns the window | `as_of` param on `scan()` | Look-ahead prevented structurally; proven pure function stays pristine. |
| All costs in pure `backtest_metrics` | Costs inside harness | One accounting authority; harness cost-free and testable; stays under domain AST ban. |
| Fixed nominal equity, no portfolio-gate sim | Full `evaluate_gates` sim | Isolates scanner edge, not portfolio construction; deterministic sizing. |

## Open Questions

None.
</content>
</invoke>
