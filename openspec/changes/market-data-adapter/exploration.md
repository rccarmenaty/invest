# Exploration: market-data-adapter

Read-only Alpaca daily bars behind the existing port seam. Signals-only; no broker execution, no orders, no NATS/Postgres, no Kubernetes.

## Current State

`FixtureReader.load(universe_path, bars_path) -> FixtureInputs` is filesystem-path-shaped, not data-source-shaped. `JsonFixtureReader` does all validation (schema, version match, symbol-set equality fail-closed, duplicate-bar, non-monotonic-bars) before the pure `MomentumScanner` ever runs. Scanner requires `HISTORY_DAYS(20) + 1 = 21` bars per symbol; any zero-volume bar in that window rejects as `missing-data` — design.md explicitly flags this as a "revisit when real data arrives" trigger. There is no clock port anywhere; `decision_date` is derived implicitly from `bars[-1].date`. `tests/test_boundaries.py` already forbids `alpaca`/`requests`/`urllib`/`socket` imports inside `src/invest/domain/*.py` — the project pre-committed to keeping any Alpaca SDK out of the domain layer. `pyproject.toml` has zero HTTP dependencies today.

## Affected Areas

- `src/invest/application/ports.py` — add new `MarketDataReader` port (fetch-shaped: `fetch(universe, as_of) -> FixtureInputs`, not path-shaped)
- `src/invest/adapters/alpaca_market_data.py` (new) — HTTP client + Pydantic response validation + fixture-snapshot writer
- `src/invest/adapters/cli.py` — new `--as-of` argument / clock handling (adapter layer only; domain stays clock-free)
- `pyproject.toml` — new `httpx` dependency
- `fixtures/{as_of_date}/` — new versioned snapshot convention, reusing the existing `_UniversePayload`/`_BarsPayload` schema so `JsonFixtureReader` needs zero changes

## Approaches

1. **Raw `httpx` REST client** (recommended over SDK) — Pros: minimal dependency footprint, full control, fits the existing "validate at the edge" Pydantic pattern. Cons: adapter owns pagination/retry/error mapping. Effort: Medium.
2. **`alpaca-py` official SDK** — Pros: official, handles auth/pagination. Cons: drags in `pandas`, `msgpack`, `websockets`, `sseclient-py` for a pure REST daily-bars need with zero streaming in this signals-only slice; still needs boundary validation anyway. Effort: Low-Medium code / Medium-High maintenance.
3. **Live-fetch-then-scan** — Pros: simplest, always latest. Cons: breaks the deterministic-replay property the foundation was explicitly built for; no audit trail; every test mocks network. Effort: Low.
4. **Fetch-to-fixture-then-scan** (recommended) — the new adapter fetches, validates, and writes a versioned snapshot in the existing fixture JSON schema; the unmodified `JsonFixtureReader -> ScanRun -> MomentumScanner` pipeline runs against it. Pros: reuses 100% of already-tested validation/scanning code, preserves deterministic replay, gives an audit trail. Cons: two-step workflow; snapshot not eternally "current" after retroactive corporate-action adjustments. Effort: Medium.

## Recommendation

New `MarketDataReader` port + raw-`httpx` Alpaca adapter that snapshots validated bars into the existing fixture schema, then hands off unchanged to `JsonFixtureReader`. Reject `alpaca-py` (dependency weight unjustified) and reject live-fetch-then-scan as the default mode (breaks replay determinism).

## Risks

- `fixture-symbol-missing` fail-closed-on-any-gap may be too strict for live halts/delistings — needs an explicit design decision, not inherited fixture behavior.
- Zero-volume → `missing-data` is a documented revisit trigger now arriving for real — needs an explicit halted-session design decision.
- Free-tier IEX feed conflicts with SPEC.md §2.2's requirement that authoritative daily decisions use consolidated/SIP data — must be a loud, config-visible limitation.
- Corporate-action-adjusted history can change retroactively; snapshots are reproducible but not eternally accurate.
- This change introduces the codebase's first wall-clock touchpoint (adapter/CLI only); no clock port exists yet.

## Ready for Proposal

Yes. Two open design questions (fixture-symbol-missing fail-closed behavior for live gaps; zero-volume/halted-session semantics) must carry into `sdd-propose`/`sdd-design` explicitly.
