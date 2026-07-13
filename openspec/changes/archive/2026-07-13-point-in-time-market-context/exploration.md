## Exploration: point-in-time-market-context

### Current State
`invest-backtest` already replays bars day-by-day, but it always uses one flat `Universe` with a single `symbols` tuple (`src/invest/domain/models.py`, `src/invest/adapters/fixtures_json.py`). `BacktestRun.scan_decisions()` passes that same universe to `MomentumScanner.scan()` for every replay date (`src/invest/application/backtest_run.py`), so symbols never age into or out of eligibility. The Alpaca adapter can fetch split-adjusted bars and fail closed when a requested symbol has zero returned bars (`src/invest/adapters/alpaca_market_data.py`), but the repo has no historical eligibility source, no earnings-calendar input, and no corporate-action safety gate beyond split-adjusting bars. The CLI still documents the result as static-universe survivorship-biased (`src/invest/adapters/cli.py`).

### Affected Areas
- `src/invest/application/backtest_run.py` — must derive the eligible symbol set per replay day and block/force-close trades when market context says a symbol is unsafe.
- `src/invest/adapters/cli.py` — must accept a PIT market-context input and fail closed when a PIT run lacks required context.
- `src/invest/domain/market_context.py` — new deep module for date-effective eligibility and blocker queries.
- `src/invest/adapters/backtest_context_json.py` — new loader for file-backed eligibility windows and blocker windows, separate from `JsonFixtureReader`.
- `tests/application/test_backtest_run.py` — add eligibility entry/exit, forced-close, and missing-context coverage.
- `tests/adapters/test_cli_backtest.py` — add one-record fail-closed CLI cases for missing/invalid context.

### Approaches
1. **File-backed market-context seam** — Add a separate context file that carries date-effective symbol eligibility plus explicit blocker windows for `corporate-action` and `earnings-context-missing`. `BacktestRun` asks that context for per-symbol/per-date status instead of inferring anything from current assets or bar presence.
   - Pros: Smallest honest slice; no invented Alpaca PIT or earnings capability; keeps `MomentumScanner` pure; makes fail-safe behavior explicit and testable; localizes the change to backtest flow.
   - Cons: Requires prepared context files before PIT runs are credible; direct Alpaca `--start/--end` backtests remain incomplete unless paired with external context.
   - Effort: Medium

2. **Provider-first ref-data ports** — Add ports/adapters for PIT eligibility, corporate actions, and earnings coverage, using Alpaca only where proven.
   - Pros: Strong long-term seam for the target architecture.
   - Cons: Alpaca docs only proved current assets and corporate actions, not historical membership or earnings-calendar coverage; too much unresolved vendor work for a first slice.
   - Effort: High

3. **Infer PIT eligibility from bars or current assets** — Treat historical bar presence or current Alpaca asset status as historical eligibility.
   - Pros: Lowest code volume.
   - Cons: Not defensible; silently reintroduces survivorship/membership assumptions and violates the requirement not to invent vendor capability.
   - Effort: Low

### Recommendation
Choose **Approach 1**. Use **symbol eligibility** as the canonical term, not index membership, because the source may be an index snapshot or a broader historical liquidity screen. Introduce one backtest-only `MarketContext` seam that answers a small interface: is a symbol eligible on a date, and is it blocked by unsafe context on that date? Keep `MomentumScanner` and Alpaca bar fetching unchanged. Do **not** infer PIT history from current Alpaca assets. The smallest defensible slice is file-backed and fail-closed: if eligibility coverage is absent, or a candidate/position intersects a corporate-action or missing-earnings blocker window, the harness records a visible skip/forced-close reason and never treats missing context as safe. Forecast: roughly **500–750 authored lines**, likely one PR within the **800-line** budget.

### Risks
- A prepared context file is honest but pushes PIT/earnings curation outside the codebase; the proposal must say that explicitly.
- `--start/--end` convenience becomes secondary or must require a companion context file, which may surprise users expecting Alpaca-only replay.
- Split-adjusted bars are not enough for symbol changes, mergers, delistings, or earnings safety; blocker windows must stay conservative.
- If market-context reasons are stuffed into `GateReason`, the model gets muddled; keep them separate from sizing/broker gates.

### Ready for Proposal
Yes — if the proposal stays file-backed for PIT context, keeps Alpaca claims limited to bars/current assets/corporate actions, and treats missing earnings context as unsafe rather than optional.
