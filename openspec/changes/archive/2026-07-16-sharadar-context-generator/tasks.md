# Tasks: Sharadar Market Context Generator

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 1,040–1,120 total; S1 330–360, S2 380–400, S3 330–360 |
| 400-line budget risk | High; S2 Medium |
| Chained PRs recommended | Yes |
| Delivery strategy | force-chained |
| Chain strategy | feature-branch-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

Tracker → `main`; PR1 → tracker, PR2 → PR1, PR3 → PR2. Fix polluted diffs.

### Suggested Work Units

| Unit | Exact scope / branch intent | Focused test | Runtime harness | Rollback boundary |
|---|---|---|---|---|
| 1 | Screen/builder/tests; PR1 → tracker | `python -m pytest tests/domain/test_liquidity_screen.py tests/domain/test_market_context_builder.py` | N/A: pure domain | Delete domain modules/tests |
| 2 | App/source/writer/tests; PR2 → PR1 | `python -m pytest tests/application/test_generate_market_context.py tests/adapters/test_sharadar_context_source.py tests/adapters/test_backtest_context_json.py` | MockTransport → reader round-trip | Delete app/source/writer |
| 3 | CLI/allowlist/docs/tests; PR3 → PR2 | `python -m pytest tests/adapters/test_generate_context_cli.py tests/test_boundaries.py` | mocked CLI → output | Remove CLI; empty allowlist |

## Phase 1: Slice 1 — Pure domain

- [x] 1.1 **RED** `tests/domain/test_liquidity_screen.py`: defaults, finite-positive config, inclusive listing, 252 bars, trailing 20-bar adjusted-close×volume median, no look-ahead, `eligible=False`; no AUM/ADV/impact.
- [x] 1.2 **GREEN** create `src/invest/domain/liquidity_screen.py` (`ScreenConfig`, Decimal/date policy); **REFACTOR** isolate pure helpers.
- [x] 1.3 **RED** `tests/domain/test_market_context_builder.py`: sorted coalescing, coverage, ever-eligible union, RLE, exact-day eligible corporate-action, no earnings blocker, invariant rejection.
- [x] 1.4 **GREEN** create `src/invest/domain/market_context_builder.py` using unchanged `MarketContext`; **REFACTOR** canonical windows/order.

## Phase 2: Slice 2 — Source, application, writer

- [x] 2.1 **RED** `tests/application/test_generate_market_context.py`: immutable inputs; `run(inputs, config)` maps malformed/partial to `reference-data-incomplete`; rejects raw Sharadar classes.
- [x] 2.2 **GREEN** create `src/invest/application/generate_market_context.py`; **REFACTOR** preserve adapter → application → domain.
- [x] 2.3 **RED** `tests/adapters/test_sharadar_context_source.py`: MockTransport reuses primary/listing facts; detects ticker conflicts, preceding-XNYS cohorts, complete unique SEP, one ACTIONS fetch, blank/exhausted pagination.
- [x] 2.4 **GREEN** create sole reader-importer `src/invest/adapters/sharadar_context_source.py`, reusing SEP `fetch_range`; **REFACTOR** cohort normalization.
- [x] 2.5 **RED** extend `tests/adapters/test_backtest_context_json.py`: canonical newline, reader round-trip, existing-target refusal, fsync/temp cleanup, invalid rejection, atomic no-replace.
- [x] 2.6 **GREEN** add `BacktestContextJsonWriter` to `src/invest/adapters/backtest_context_json.py`; **REFACTOR** do not alter reader behavior.

## Phase 3: Slice 3 — CLI and boundary

- [x] 3.1 **RED** `tests/adapters/test_generate_context_cli.py`: start/end/out, ordered dates, finite-positive decimals/counts, seasoning≥window, absent writable output, sorted one-line stdout/empty stderr, 0/2, no partial or replay/broker/scanner/live/paper call.
- [x] 3.2 **GREEN** create `src/invest/adapters/generate_context_cli.py`; register in `pyproject.toml`; **REFACTOR** orchestration-only; no source/replay/universe/overwrite/AUM/ADV/impact flags.
- [x] 3.3 **RED** extend `tests/test_boundaries.py`: AST allows only `sharadar_context_source.py`; protected CLI/domain/backtest paths denied; consumers unchanged.
- [x] 3.4 **GREEN** set one-path allowlist; **REFACTOR** retain default-deny. Update `README.md` with mocked-only generation/replay separation.

## Requirements → Tasks

| Requirement | Tasks |
|---|---|
| Discovery and historical status | 1.3–1.4, 2.3–2.4 |
| Liquidity/no-impact rule | 1.1–1.2 |
| Complete safe context/actions | 1.3–1.4, 2.1–2.4 |
| Deterministic valid atomic JSON | 2.5–2.6 |
| Standalone failure/no-network/no-replay | 3.1–3.2 |
| Unchanged consumer/backtest-only boundary | 3.3–3.4 |

Threat matrix rows are N/A. During apply/verify only, run listed commands, `python -m pytest`, then `python -m ruff check src tests`.
