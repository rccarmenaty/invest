# Tasks: Backtest Warmup Replay Window

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 500–700 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Delivery strategy | single-pr (user decision) |
| Chain strategy | single-pr |

Decision needed before apply: No — user pre-decided single-pr delivery for this chain
Chained PRs recommended: Yes (forecast); overridden by explicit user choice
Chain strategy: single-pr
400-line budget risk: High

### Suggested Work Units

| Unit | Scope | Focused test | Runtime harness | Rollback boundary |
|---|---|---|---|---|
| 1 | Span/v2 JSON | `uv run pytest tests/domain/test_market_context.py tests/domain/test_market_context_builder.py tests/adapters/test_backtest_context_json.py` | N/A: pure contracts | Groups 1–2 files |
| 2 | Replay/CLI/warmup | `uv run pytest tests/application/test_backtest_run.py tests/adapters/test_cli_backtest.py tests/adapters/test_sharadar_context_source.py` | `uv run invest-backtest` with `fixtures/backtest-252/*` | Groups 3–5 files |
| 3 | Output/fixtures | `uv run pytest tests/adapters/test_generate_context_cli.py tests/domain/test_momentum_selection_scanner.py tests/fixtures/test_backtest_252_fixtures.py` | Mocked generation/replay | Groups 6–8 files |

## 1. Domain generation span

- [x] 1.1 **RED** Extend `tests/domain/test_market_context.py` for immutable `GenerationSpan(start, end)`, inversion, and fail-closed out-of-span status/completeness/eligibility.
- [x] 1.2 **GREEN/REFACTOR** Add required `GenerationSpan` and span authority in `src/invest/domain/market_context.py`.
- [x] 1.3 **RED** Extend `tests/domain/test_market_context_builder.py` for exact first/last-session propagation and empty-span rejection.
- [x] 1.4 **GREEN/REFACTOR** Propagate normalized session bounds in `src/invest/domain/market_context_builder.py` and `src/invest/application/generate_market_context.py`.

## 2. Versioned context JSON

- [x] 2.1 **RED** Extend `tests/adapters/test_backtest_context_json.py` for deterministic `market-context-v2` round-trip and rejection of v1, missing, malformed, empty, or inverted spans.
- [x] 2.2 **GREEN/REFACTOR** Require canonical top-level `generation_span` in `src/invest/adapters/backtest_context_json.py`; no inference or compatibility fallback.

## 3. Replay partition

- [x] 3.1 **RED** Extend `tests/application/test_backtest_run.py` for warmup/replay partitioning, scanner-visible history, full in-span completeness gaps, no pre-span events, and `replay-window-invalid` for post-span or empty replay input.
- [x] 3.2 **GREEN/REFACTOR** Partition once in `src/invest/application/backtest_run.py`; scan only replay dates with prior history and process only replay bars/events.

## 4. Backtest CLI coherence

- [x] 4.1 **RED** Extend `tests/adapters/test_cli_backtest.py` for exact observed in-span `--split-date`, exact live `--start/--end`, warmup-date rejection, and one `{"reason":"replay-window-invalid"}` record.
- [x] 4.2 **GREEN/REFACTOR** Enforce split/range coherence and stable error serialization in `src/invest/adapters/cli.py`.

## 5. Scanner-sufficient warmup

- [x] 5.1 **RED** Extend `tests/adapters/test_sharadar_context_source.py` for depth `max(min_observed_bars, dollar_volume_window, HISTORY_DAYS)` = at least 253 and listing-date clipping.
- [x] 5.2 **GREEN/REFACTOR** Import domain `HISTORY_DAYS` and apply bounded warmup depth in `src/invest/adapters/sharadar_context_source.py`.

## 6. Paired generation outputs

- [x] 6.1 **RED** Extend `tests/adapters/test_generate_context_cli.py` for v2 span output, byte determinism, and paired bars containing permitted pre-span warmup.
- [x] 6.2 **GREEN/REFACTOR** Wire span-bearing context and paired bars in `src/invest/adapters/generate_context_cli.py` and `src/invest/application/generate_market_context.py`.

## 7. Scanner contract guard

- [x] 7.1 Verify `HISTORY_DAYS == 253` and unchanged insufficient-history behavior in `tests/domain/test_momentum_selection_scanner.py`; preserve `src/invest/domain/momentum_selection_scanner.py` strategy logic.

## 8. Deterministic fixture regression

- [x] 8.1 **RED** Update `tests/fixtures/test_backtest_252_fixtures.py` to require v2 span, allow pre-span bars as history, require in-span completeness, and reject pre-span replay events.
- [x] 8.2 **GREEN** Regenerate `fixtures/backtest-252/{bars,market-context,universe}.json` and associated checked-in replay goldens; confirm all emitted events are in-span.

## 9. Final verification

- [ ] 9.1 Run the full suite: `uv run pytest`.
- [ ] 9.2 Run lint: `uv run ruff check`.

> Post-merge operational note: regenerate `fixtures/real-years/**`; this is not part of the code change.
