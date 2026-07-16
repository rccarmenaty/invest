# Tasks: `--bars-out` fixture export for invest-generate-context

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~260-320 (new adapter ~110, new adapter tests ~140, CLI diff ~25, CLI test diff ~30) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | `BarsFixtureWriter` adapter + errors, fully unit-tested in isolation | PR 1 (single) | `pytest tests/adapters/test_bars_fixture_json.py` | N/A — pure local file I/O, no live API required | `src/invest/adapters/bars_fixture_json.py` + its test file are removable without touching CLI |
| 2 | CLI wiring (`--bars-out`, guard test update, no-op regression) | PR 1 (single) | `pytest tests/adapters/test_generate_context_cli.py` | `invest-generate-context --start 2024-01-02 --end 2024-01-04 --out /tmp/ctx.json --bars-out /tmp/fixtures` against a stubbed/mocked source | CLI diff is additive (`if args.bars_out is not None:` block + new arg + 3 except clauses); revertable as one hunk without touching context-writing path |

Given Medium risk and a single cohesive vertical slice (adapter feeds directly into CLI wiring with no independent value split), keep as one PR; ask user to confirm before apply per `ask-on-risk`.

## Phase 1: Adapter — `BarsFixtureWriter` (TDD, RED first)

- [x] 1.1 RED: `tests/adapters/test_bars_fixture_json.py` — round-trip test: write via `BarsFixtureWriter().write(FixtureInputs(universe, bars), tmp_path / "fixdir")`, then `JsonFixtureReader().load(dir/"universe.json", dir/"bars.json")` returns equal `FixtureInputs`.
- [x] 1.2 RED: same file — ragged coverage test: two symbols with differing bar-date ranges (partial IPO/delisting window) round-trip without a full-calendar requirement.
- [x] 1.3 RED: same file — fail-closed tests: universe-symbol-without-bars, bar-not-in-universe, and empty-bars each raise `BarsFixtureSymbolMismatchError`; assert no fixture files/dir created after the raise (`set(universe.symbols) == {bar.symbol for bar in bars}` guard, per design.md).
- [x] 1.4 RED: same file — atomicity tests: pre-existing `DIR` raises `BarsFixtureExistsError` and leaves it untouched; monkeypatched `Path.replace`/write to raise `OSError` raises `BarsFixtureStorageError` and leaves no partial `DIR` (staging dir cleaned up).
- [x] 1.5 RED: same file — serialization tests: OHLC values serialize as `str(Decimal)`; whole-number volume collapses to `int`; fractional volume is preserved as `str`; re-dump determinism via `json.dumps(..., sort_keys=True, separators=(",", ":"))`.
- [x] 1.6 RED: same file — `fixture_version` test: both `universe.json` and `bars.json` share `fixture_version == universe.fixture_version` (CLI sets this to `end.isoformat()`).
- [x] 1.7 GREEN: create `src/invest/adapters/bars_fixture_json.py` with `BarsFixtureError(OSError)` base (`.reason`), `BarsFixtureExistsError` (`.reason="bars-out-exists"`), `BarsFixtureStorageError` (`.reason="storage-failure"`), `BarsFixtureSymbolMismatchError` (`.reason="bars-universe-mismatch"`).
- [x] 1.8 GREEN: implement `BarsFixtureWriter.write(inputs: FixtureInputs, out: Path) -> Path` — mirror `SnapshotWriter` (alpaca_market_data.py:168-242) serialization (do not import it): fail-closed symbol-set guard first, then `tempfile.mkdtemp` staging, write `universe.json` + `bars.json`, `staging.replace(out)`; refuse if `out` exists; `OSError` → cleanup staging, raise `BarsFixtureStorageError`.
- [x] 1.9 REFACTOR: extract shared `_json_bytes` helper if duplication with `SnapshotWriter`-style serialization becomes awkward; confirm all Phase 1 tests still pass.

## Phase 2: CLI Wiring — `--bars-out`

- [x] 2.1 RED: `tests/adapters/test_generate_context_cli.py` — new test asserting `--bars-out DIR` invocation (with `SharadarContextSource.load` mocked/stubbed) writes both `DIR/universe.json` and `DIR/bars.json`, `--out` context file is also written, and the source `.load` is called exactly once (no second fetch).
- [x] 2.2 RED: same file — no-op regression test: invocation without `--bars-out` writes only the `--out` context file; no fixture directory is created anywhere.
- [x] 2.3 RED: same file — error-mapping tests: pre-existing `bars_out` dir → CLI exits 2 with `{"reason": "bars-out-exists"}`; injected storage failure → `{"reason": "storage-failure"}`; symbol-mismatch → `{"reason": "bars-universe-mismatch"}`.
- [x] 2.4 RED: extend `test_core_defaults_and_no_banned_flags` (tests/adapters/test_generate_context_cli.py:175-192) — keep `bars` (singular) in the banned-dests tuple, and ADD a positive assertion that `bars_out` IS present in `dests` (`assert "bars_out" in dests`). Call out explicitly: do not delete or weaken this guard, only extend it.
- [x] 2.5 GREEN: in `src/invest/adapters/generate_context_cli.py` add `parser.add_argument("--bars-out", type=Path, default=None, dest="bars_out")` to `_parser()` (near `--out`, generate_context_cli.py:49).
- [x] 2.6 GREEN: in `main()` (generate_context_cli.py:97-117), after `BacktestContextJsonWriter().write(context, out)`, add: `if args.bars_out is not None: universe = Universe(args.end.isoformat(), tuple(sorted({l.symbol for l in inputs.listings}))); BarsFixtureWriter().write(FixtureInputs(universe, inputs.bars), args.bars_out)`. Import `Universe`, `FixtureInputs` from `invest.domain.models` and `BarsFixtureWriter`, `BarsFixtureExistsError`, `BarsFixtureStorageError`, `BarsFixtureSymbolMismatchError` from `invest.adapters.bars_fixture_json`.
- [x] 2.7 GREEN: add except clauses to `main()`: `except BarsFixtureExistsError: return _fail("bars-out-exists")`, `except BarsFixtureSymbolMismatchError as error: return _fail(error.reason)`, `except BarsFixtureStorageError: return _fail("storage-failure")` — placed before the generic `except (ValueError, TypeError, InvalidOperation, OSError)` fallback so specific reasons take priority.
- [x] 2.8 REFACTOR: verify import ordering/boundary — confirm `tests/test_boundaries.py:460-465` still passes unmodified (sharadar_context_source import allowed, backtest_run import still absent) after adding new imports.

## Phase 3: Integration Verification

- [x] 3.1 Run full targeted suite: `pytest tests/adapters/test_bars_fixture_json.py tests/adapters/test_generate_context_cli.py -v`.
- [x] 3.2 Run `pytest tests/test_boundaries.py` to confirm no new forbidden import edges were introduced by the CLI's new imports.
- [x] 3.3 Manual smoke: run `invest-generate-context` with `--bars-out` against a stubbed source (matches Suggested Work Units Unit 2 runtime harness) and confirm `universe.json`/`bars.json` load via `JsonFixtureReader().load(...)` with no exception. Ran from scratchpad, not committed; output: `SMOKE OK: 5 bars loaded, universe: ('ACME',) load_calls: 1`.

## Phase 4: Cleanup

- [x] 4.1 Confirm `design.md` interface signatures (`BarsFixtureWriter.write`, error `.reason` values) match the final implementation exactly; fix any drift. No drift found.
- [x] 4.2 Remove any stray debug prints/temp files created during manual smoke testing (Phase 3.3). Smoke script lived only in the session scratchpad (`/private/tmp/...`), not the repo; nothing to clean up in-tree.
