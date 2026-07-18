# Design: `--bars-out` fixture export for invest-generate-context

## Technical Approach

Add a CLI-only seam. `main()` already holds `inputs = SharadarContextSource(...).load(...)` before `GenerateMarketContext().run`. A new deep adapter `BarsFixtureWriter` serializes the already-fetched `inputs.bars` + a listings-derived `Universe` into a `JsonFixtureReader`-compatible pair. No second fetch, no domain/application change. Mirrors (does not import) `SnapshotWriter`'s serialization + atomic publish.

## Architecture Decisions

| Decision | Choice | Rejected alternative | Rationale |
|----------|--------|----------------------|-----------|
| Seam | CLI wires new writer after `--out` write | Thread bars-out through `GenerateMarketContext`/`GeneratorInputs` | Keeps application pure I/O-free; `inputs` already in CLI scope; matches `SnapshotWriter` precedent |
| Reuse `SnapshotWriter` | Duplicate serialization in new module | `import SnapshotWriter` from `alpaca_market_data` | Alpaca vs Sharadar concern separation; keeps adapter a self-contained deep module (boundary tests unaffected) |
| PATH shape | `--bars-out DIR` (directory) | Single `bars.json` + `--universe-out`, or `DIR/{version}/` subdir | Reader needs universe+bars pair; matches `fixtures/backtest/` layout; no second flag; `--out` anchors provenance so no `provenance.json`/version subdir |
| Atomicity | Stage temp dir, write both files, single `staging.replace(DIR)` | Two separate `Path.replace` into a pre-existing DIR | One dir-replace is fully atomic across the pair; refuse-if-DIR-exists mirrors `--out` idiom exactly |
| `fixture_version` | `args.end.isoformat()` (written to BOTH payloads) | Composite `f"{start}_{end}"` | Consistent with `SnapshotWriter`; reader treats it as opaque equality |
| Error types | New per-adapter errors with `.reason` | Reuse `MarketDataFetchError` | Mirrors `backtest_context_json` error pattern; self-contained reasons |
| Fail-closed guard | Writer asserts `set(universe.symbols) == {bar.symbol}` and bars non-empty | Rely on upstream emergent invariant | Silent violation yields an unreplayable fixture; guard is independent of upstream |

## Data Flow

    SharadarContextSource.load ──→ inputs (listings, bars, ...)
             │                          │
             │              ┌───────────┴─────────────┐
             ▼              ▼                         ▼
    GenerateMarketContext   BacktestContextJsonWriter  BarsFixtureWriter (new, if --bars-out)
             │              (--out market-context.json) │
             ▼                                          ▼
        MarketContext                        DIR/universe.json + DIR/bars.json  (atomic)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/invest/adapters/bars_fixture_json.py` | Create | `BarsFixtureWriter` + `BarsFixture*` errors; pure JSON serialization + atomic dir publish |
| `src/invest/adapters/generate_context_cli.py` | Modify | `--bars-out` arg (dest `bars_out`, `type=Path`); build `Universe`, call writer after `--out`; catch new errors |
| `tests/adapters/test_bars_fixture_json.py` | Create | Writer unit + round-trip tests |
| `tests/adapters/test_generate_context_cli.py` | Modify | CLI wiring tests; extend guard test |

## Interfaces / Contracts

```python
# bars_fixture_json.py
class BarsFixtureError(OSError): ...            # base, .reason
class BarsFixtureExistsError(BarsFixtureError): # .reason = "bars-out-exists"
class BarsFixtureStorageError(BarsFixtureError):# .reason = "storage-failure"
class BarsFixtureSymbolMismatchError(BarsFixtureError): # .reason = "bars-universe-mismatch"

class BarsFixtureWriter:
    def write(self, inputs: FixtureInputs, out: Path) -> Path: ...
```

- `inputs.universe.fixture_version` (set by CLI to `args.end.isoformat()`) is written to BOTH `universe.json` and `bars.json`.
- Guard: raise `BarsFixtureSymbolMismatchError` if `not inputs.bars` or `set(universe.symbols) != {b.symbol for b in inputs.bars}`.
- Serialization mirrors `SnapshotWriter`: OHLC as `str(Decimal)`; volume `int(v)` when whole else `str(v)`; `json.dumps(payload, sort_keys=True, separators=(",", ":"))`.
- Atomicity: refuse if `DIR` exists → `BarsFixtureExistsError`; else `tempfile.mkdtemp` staging, write both files, `staging.replace(DIR)`; `OSError` → `BarsFixtureStorageError` with cleanup, leaving no partial `DIR`.

CLI wiring (after `BacktestContextJsonWriter().write(context, out)`):

```python
if args.bars_out is not None:
    universe = Universe(args.end.isoformat(),
                        tuple(sorted({l.symbol for l in inputs.listings})))
    BarsFixtureWriter().write(FixtureInputs(universe, inputs.bars), args.bars_out)
```

Add `except BarsFixtureExistsError: return _fail("bars-out-exists")` and mismatch/storage handlers (storage reuses `"storage-failure"`).

## Testing Strategy (TDD — RED first)

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Round-trip | Write, then `JsonFixtureReader().load(DIR/universe.json, DIR/bars.json)` equals input bars |
| Unit | Ragged coverage | Symbols with differing bar counts round-trip (writer imposes no full-calendar rule) |
| Unit | Fail-closed | universe-symbol-without-bars, bar-not-in-universe, empty bars → `BarsFixtureSymbolMismatchError` |
| Unit | Atomicity | Pre-existing DIR → `BarsFixtureExistsError`, nothing written; injected `OSError` → `BarsFixtureStorageError`, no partial DIR |
| Unit | Decimal/volume | OHLC strings; fractional volume preserved; whole-number volume collapses to int; reloads canonical `Decimal` |
| Integration (CLI) | Wiring | `--bars-out DIR` writes both files, source `.load` called exactly once (no re-fetch) |
| Integration (CLI) | No-op | Flag omitted → no bars dir created |
| Guard | `test_core_defaults_and_no_banned_flags` | `bars` still banned in dests; add assertion `bars_out` present |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. Change is local JSON file I/O with atomic replace.

## Migration / Rollout

No migration. Flag is optional/additive; live `--source sharadar` path unchanged. Rollback = revert commit.

## Open Questions

- None. Directory semantics, `fixture_version`, no-provenance, and error reasons are all resolved by the proposal's automatic-mode defaults.
