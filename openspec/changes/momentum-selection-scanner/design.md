# Design: Momentum Selection Scanner

## Technical Approach

Add a new deep domain module `MomentumSelectionScanner` implementing the same
`scan(universe, bars) -> list[ScanDecision]` interface as `MomentumScanner`, so it
drops into the existing seam. `BacktestRun.scan_decisions()` already hands the
scanner the full per-day cross-sectional window (`bars <= d`), so the Core model
ranks across that window internally with NO replay-loop change. A thin
`ScannerPort` Protocol formalizes the seam; the backtest CLI selects the scanner
via `--strategy {benchmark,core}` (default `benchmark`). Decimal-only, clock-free,
output sorted `(decision_date, symbol)`. Implements SPEC §2.3–2.4 and the three
DECIDED Proposal Question Round defaults (ceil-15% cutoff, candidate-excluded
SMA200-rising, per-layer rejections). Delivered as a 3-slice chained PR.

## Architecture Decisions

| Option | Tradeoff | Decision |
|---|---|---|
| New sibling scanner behind existing `scan()` shape | Meaningful new domain logic | Chosen; reuses the proven replay seam, keeps benchmark/Core comparable through one harness. |
| Cross-sectional rank INSIDE the scanner | Scanner sees whole window | Chosen; the window is already cross-sectional-capable, so no `BacktestRun` change. |
| `ScannerPort` Protocol + loosen `scanner` hint | One more abstraction | Chosen; two adapters (benchmark, Core) make the seam real, not hypothetical. |
| Per-layer rejection reasons | 3 new enum members | Chosen; "rejections are journal gold" (SPEC §2.6). |
| Indicators as windowed reducers over a passed slice; scanner owns offset/exclusion conventions | Offset math lives in one place | Chosen; localizes candidate-day-exclusion to the scanner, keeps helpers trivially testable. |
| Separate `invest-backtest-core` entrypoint | Duplicates argparse/report | Rejected; breaks "same harness" comparability, doubles CLI surface. |
| `--scanner-config path.json` | Extensible manifest | Rejected; YAGNI, only two strategies exist. |

## Data Flow

    per-day window (bars <= d) -> MomentumSelectionScanner.scan
      group by symbol
      Stage 0 history gate  (>=253 bars) -> INSUFFICIENT_HISTORY / MISSING_DATA / DOMAIN_INVARIANT_VIOLATION
      Stage 1 momentum rank (cross-sectional, top ceil(0.15*pool)) -> NOT_TOP_MOMENTUM_RANK
      Stage 2 52w-high proximity (close >= 0.95 * trailing252High) -> BELOW_52_WEEK_HIGH_PROXIMITY
      Stage 3 trend (close > SMA50 > SMA200 AND SMA200 rising)     -> TREND_FILTER_FAILED
      Stage 4 breakout (close > prior 20-day high)                 -> NO_SIGNAL
      accepted -> ScanDecision(accepted=True)
    -> sorted (decision_date, symbol) -> BacktestRun (unchanged)

Every universe symbol yields exactly one `ScanDecision`; `decision_date = last
window bar` (candidate) or `date.min` if absent. Ranking uses Decimal; ties break
return desc, then symbol asc. `k = ceil(Decimal("0.15") * pool_size)` over symbols
passing Stage 0 (guarantees >=1).

## File Changes

| File | Action | Description |
|---|---|---|
| `src/invest/domain/momentum_selection_scanner.py` | Create | Core 5-stage cross-sectional scanner. |
| `src/invest/domain/indicators.py` | Modify | Add SMA, trailing high, momentum return, SMA-rising; keep ATR. |
| `src/invest/domain/rejection.py` | Modify | Add `NOT_TOP_MOMENTUM_RANK`, `BELOW_52_WEEK_HIGH_PROXIMITY`, `TREND_FILTER_FAILED`. |
| `src/invest/application/ports.py` | Modify | Add `ScannerPort` Protocol. |
| `src/invest/application/backtest_run.py` | Modify | Loosen `scanner: MomentumScanner \| None` -> `ScannerPort \| None`; no other change. |
| `src/invest/adapters/cli.py` | Modify | `--strategy {benchmark,core}` on `_backtest_parser` only; build scanner in `backtest_main`. |
| `fixtures/backtest-252/{universe,bars,market-context}.json` | Create | Deterministic 253+-bar set with paired coverage. |
| `tests/domain/test_indicators.py` | Create | Windowed-reducer + offset conventions. |
| `tests/domain/test_momentum_selection_scanner.py` | Create | Rank/tie-break, each filter layer, determinism. |
| `tests/adapters/test_cli_backtest.py` | Modify | `--strategy core` replay; `benchmark`/no-flag byte-parity. |
| `tests/test_boundaries.py` | Modify | `strategy` flag backtest-only. |

No changes to `MomentumScanner`, replay/execution/accounting logic, or existing fixtures.

## Interfaces / Contracts

```python
# ports.py
class ScannerPort(Protocol):
    def scan(self, universe: Universe, bars: tuple[DailyBar, ...]) -> list[ScanDecision]: ...

# indicators.py — helpers over a passed slice; scanner slices to exclude candidate
def simple_moving_average(bars: Sequence[DailyBar], window: int) -> Decimal      # mean of last `window` closes
def trailing_high(bars: Sequence[DailyBar], window: int) -> Decimal              # max high over last `window`
def momentum_return(bars: Sequence[DailyBar], far: int, near: int) -> Decimal    # close[-1-near]/close[-1-far] - 1
def sma_is_rising(bars: Sequence[DailyBar], window: int, lookback: int) -> bool  # SMA ending t-1 > SMA ending t-1-lookback
```

Conventions: candidate = `bars[-1]`. Momentum uses `far=252, near=21` (needs
index `t-252` present -> history gate 253). Trend/proximity read closes/highs
ending at `t-1` (candidate excluded); SMA200-rising uses `window=200, lookback=20`.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit (indicators) | SMA/high/return/rising exact values; offset/exclusion; Decimal | RED tables, small crafted series. |
| Unit (scanner) | ceil-15% cutoff, ties (return desc/symbol asc), each layer's rejection, all-symbols emission, deterministic sort | In-code 253-bar builders (mirror `test_scanner.py`). |
| Integration (CLI) | `--strategy core` runs Core through harness; `benchmark`/no-flag byte-parity | 252-day JSON fixtures + paired context. |
| Boundary | `strategy` on backtest parser only; new domain file purity | AST/glob guards. |

Strict TDD, 3-slice chain: (1) indicators + rejections + fixtures —
`pytest tests/domain/test_indicators.py`; (2) scanner —
`pytest tests/domain/test_momentum_selection_scanner.py`; (3) port + CLI +
boundaries — `pytest tests/adapters/test_cli_backtest.py tests/test_boundaries.py`.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. `--strategy` is an argparse `choices` enum, not shell input.

## Migration / Rollout

No state migration. Default `benchmark` preserves current output byte-for-byte;
rollback = revert the new module, port, flag, fixtures, and tests.

## Open Questions

None — the three Proposal Question Round defaults are DECIDED and implemented above.

Next Recommended Phase: sdd-tasks
