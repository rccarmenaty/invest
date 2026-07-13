# Exploration: Core 52-Week-High Momentum Breakout candidate-selection layer

**Change**: `momentum-selection-scanner`
**Date**: 2026-07-13
**Engram**: `sdd/momentum-selection-scanner/explore` (obs #2953)

## Current State

- `domain/scanner.py`: `MomentumScanner.scan(universe, bars)` groups bars by symbol, then runs a **per-symbol** rejection pipeline (`_scan_symbol`): needs `HISTORY_DAYS=20` history, rejects on missing/invalid bars, then checks rel-volume ≥2x, ATR(14) move ≥1.5x, close > 20-day-high, close < 1.15x 20-day MA. This is the SPEC §2.5 benchmark control, kept as-is.
- Crucially, `scan()` already receives the FULL cross-sectional bar set for the day — `application/backtest_run.py::BacktestRun.scan_decisions()` builds `window = bars for all eligible symbols dated <= d` and calls `self._scanner.scan(replay_universe, window)` once per day. The interface is already cross-sectional-capable; only `MomentumScanner`'s internal logic is per-symbol. A new selection scanner implementing the same `scan(universe, bars) -> list[ScanDecision]` shape can rank across the whole window internally without any change to `BacktestRun`'s day-by-day replay loop.
- `domain/indicators.py` only has `average_true_range` (ATR14). No SMA, no rolling-high, no momentum-return, no slope helpers yet.
- `domain/rejection.py` (`RejectionReason` StrEnum) has no momentum-rank/52w-high/trend-filter reasons yet.
- `application/ports.py` has `FixtureReader`, `MarketDataReader`, `BrokerPort`, `Journal` protocols — **no `ScannerPort` protocol**. `BacktestRun.__init__` types the scanner param concretely as `MomentumScanner | None` (structurally any object with `.scan()` works today, but there's no formal port).
- `adapters/fixtures_json.py` (`JsonFixtureReader`/`_BarPayload`/`_BarsPayload`) validates OHLC relationships, fixture-version match, duplicate/non-monotonic dates — but has **no minimum-bar-count constraint**. 252+ bars is purely a fixture-generation problem, not a schema/validation change.
- `fixtures/backtest/bars.json` has 68 bar rows across ~4 symbols (~17 bars/symbol); `fixtures/v1/` similarly short. `fixtures/backtest/market-context.json` (read by `adapters/backtest_context_json.py` into `domain/market_context.MarketContext`) has coverage/eligibility windows matching those short ranges exactly (e.g. 2024-01-02..2024-01-24).
- `BacktestRun.replay()` calls `self._market_context.require_complete(replay_dates, inputs.universe.symbols)` up front and fails closed (`MarketContextIncompleteError`) if any date/symbol pair lacks coverage — a longer bar fixture MUST ship with a correspondingly extended market-context fixture, or replay will not even start.
- `tests/test_boundaries.py` enforces: no `invest.adapters`/`invest.application`/SDK imports and no `datetime.now/date.today/open/eval/exec` calls anywhere under `src/invest/domain/*.py` (auto-globbed, so new domain files are automatically covered) plus several backtest-path/out-of-scope-guard regression tests (bans `gap`/`confirmation` module names, non-paper Alpaca URLs, and requires `market_context` flag on the backtest parser only, never the execute parser) — precedent for how a new CLI flag must be boundary-tested.
- `SPEC.md` §2.3–2.5 / research report §6.2–6.3 define the exact baseline rule set: momentum rank = return(252d ago → 21d ago), top 15%; 52w-high proximity = close ≥ 95% of trailing-252-day high; trend = close > SMA50 > SMA200 and SMA200 rising over prior 20 days; entry trigger reuses the existing "close above prior 20-day high" concept (§2.4) — the *existing* benchmark scanner already computes `prior_high = max(history highs)` over 20 days and requires `candidate.close > prior_high`, so that piece is reusable/extractable, not net-new.
- `ROADMAP.md` §5/§6 explicitly scope this change (A) to selection-layer + fixtures only; trailing exits/time stops (B), regime filter + vol-sizing (C), and the pass/fail gate (D) are separate later changes.

## Affected Areas

- `src/invest/domain/indicators.py` — add SMA(n), trailing-N-day-high, momentum-return(from,to), and an "SMA rising over k days" helper. Extend, don't replace ATR.
- `src/invest/domain/rejection.py` — add new `RejectionReason` members (e.g. not-top-momentum-rank, below-52-week-high-proximity, trend-filter-failed); reuse `INSUFFICIENT_HISTORY`/`MISSING_DATA`/`DOMAIN_INVARIANT_VIOLATION` where semantics match.
- New `src/invest/domain/momentum_selection_scanner.py` — the Core model, same `scan(universe, bars) -> list[ScanDecision]` shape as `MomentumScanner`, ranking cross-sectionally: (1) require 252+1 bars/symbol else `INSUFFICIENT_HISTORY`; (2) compute momentum-return per symbol with sufficient history; (3) keep only the top-15% (rounding rule TBD); (4) apply 52w-high-proximity and trend filters to the retained set; (5) apply the existing 20-day-high breakout trigger. Must sort output deterministically (decision_date, symbol) and tie-break ranking deterministically (return desc, then symbol asc) — Decimal only, no floats, no randomness.
- `src/invest/application/ports.py` — add a `ScannerPort` Protocol (`scan(universe, bars) -> list[ScanDecision]`) so `BacktestRun` depends on an abstraction instead of the concrete `MomentumScanner` class.
- `src/invest/application/backtest_run.py` — loosen `scanner: MomentumScanner | None` to `scanner: ScannerPort | None`; the day-by-day replay loop needs NO other change since it already passes the full per-day cross-sectional window.
- `src/invest/adapters/cli.py` — `_backtest_parser`/`backtest_main`: add a strategy-selection flag wiring the chosen scanner into `BacktestRun(...)`. Must not touch `_execute_parser`/`_scan_parser` (mirrors the existing `market_context`-is-backtest-only boundary test pattern).
- `tests/test_boundaries.py` — likely needs one new analogous assertion (new flag lives only on backtest parser); new domain file is automatically covered by the existing glob-based import/nondeterminism check.
- Fixtures: new 252+-bar fixture set (do NOT edit `fixtures/backtest/bars.json`/`market-context.json` in place — those back unrelated existing tests). Needs a matching extended `market-context.json` for every new symbol/date range. Bar generation is mechanical/generated data — per the shared review-budget convention, generated goldens are excluded from the 800-line authored count but still count for full snapshot/diff identity.
- `tests/domain/test_scanner.py` pattern (small `_bar`/`_accepted_history` helpers) is the template to replicate for the new scanner's unit tests, but at 252-bar scale.

## Approaches

1. **New sibling domain scanner + `ScannerPort` + CLI `--strategy` flag (default `benchmark`)** — implement the Core model as a new class satisfying the same `scan()` shape, add a thin `ScannerPort` Protocol, inject via a new optional CLI arg on `invest-backtest` only, defaulting to today's `MomentumScanner` so all existing CLI/backtest tests and golden JSON output stay unchanged.
   - Pros: minimal churn to `BacktestRun`'s proven replay loop; fully backward compatible; reuses the existing 20-day-high-breakout logic; keeps benchmark and Core comparable "through the same harness."
   - Cons: still meaningful new domain logic (ranking + 3 filter layers + new indicators) and thorough TDD coverage that will consume most of the review budget; requires careful fixture-generation isolation.
   - Effort: Medium-High.

2. **Separate CLI entrypoint (`invest-backtest-core`)** — duplicate `_backtest_parser`/`backtest_main` for the Core strategy.
   - Pros: zero risk to the existing `invest-backtest` contract/tests.
   - Cons: duplicates argparse/report-building code, doubles CLI test surface, works against "both must run through the same harness" comparability goal. Not recommended.
   - Effort: Medium (more line count for less benefit).

3. **Config/manifest-driven strategy selection (`--scanner-config path.json`)**.
   - Pros: extensible if many strategy variants appear later (parameter grid, report §10.5).
   - Cons: premature (YAGNI) — only two strategies exist today; parameter-grid testing is explicitly a later research activity, not part of change A.
   - Effort: High for no current benefit.

## Recommendation

Approach 1 (new domain scanner + `ScannerPort` Protocol + a `--strategy {benchmark,core}` flag defaulting to `benchmark` on `invest-backtest` only). It's the only option satisfying "both must run through `application/backtest_run.py` so results are comparable" without duplicating the harness — `BacktestRun.scan_decisions()` already hands the scanner a full per-day cross-sectional window, so the seam is already in the right place.

Recommend splitting delivery (mirrors the `point-in-time-market-context` change's 3-chained-PR precedent, `ROADMAP.md` §3):

- Slice 1: `indicators.py` + `rejection.py` additions + new 252-day fixture set + fixture-level tests.
- Slice 2: the new domain scanner itself (ranking + 3 filters + breakout-trigger reuse) with full TDD coverage — largest authored-line slice.
- Slice 3: `ScannerPort` + `BacktestRun` type-hint loosening + CLI `--strategy` flag + boundary test.

## Risks

- **800-line authored budget**: domain scanner + new indicators + rejection reasons + ports/backtest_run/cli wiring + thorough strict-TDD test coverage plausibly totals 600-900+ authored lines even excluding generated fixture JSON. Flag for `sdd-tasks` to forecast explicitly; a 2-3 slice chain is likely needed.
- **Fixture/market-context coupling**: `BacktestRun.replay()` fails closed via `require_complete()` if bar-date coverage in the new 252-day fixture isn't mirrored exactly in an extended `market-context.json` — easy to break replay entirely if these drift. Must NOT edit the existing short `fixtures/backtest/bars.json`/`market-context.json` in place.
- **Open design questions for sdd-propose/sdd-design** (not decided here):
  - Rounding rule for "top 15% of universe" when not evenly divisible (floor/ceil/nearest) — undefined in SPEC/report.
  - Exact index math for "SMA200 rising over prior 20 days" (which two 200-day windows, offset, candidate-day exclusion convention).
  - Whether new rejection reasons should be granular per filter layer (recommended, matches "rejections are journal gold") vs one generic catch-all.
- **Domain purity**: new scanner/indicators must stay free of adapter/SDK imports and wall-clock calls; automatically checked by the existing glob-based `test_boundaries.py`, but must be respected during implementation (Decimal-only, deterministic tie-break).

## Ready for Proposal

Yes — scope, seam, affected files, and the fixture/CLI coexistence approach are clear enough to proceed to `sdd-propose`. Flag the two open design questions and the likely need for chained-PR slicing.
