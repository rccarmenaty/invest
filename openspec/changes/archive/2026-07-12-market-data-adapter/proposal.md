# Proposal: Market Data Adapter (Alpaca Daily Bars)

## Intent

Replace hand-authored fixture bars with real Alpaca daily-bar data while preserving the deterministic, replayable, fail-closed pipeline the foundation slice established. The zero-volume "revisit when real data arrives" trigger has now arrived; this slice makes real data arrive without touching domain purity.

## Scope

### In Scope
- New fetch-shaped `MarketDataReader` port: `fetch(universe, as_of) -> FixtureInputs` (data-source-shaped, not path-shaped).
- Raw `httpx` Alpaca REST adapter with Pydantic edge validation (no `alpaca-py` SDK).
- Fetch-to-fixture-then-scan: adapter snapshots validated bars into the existing fixture JSON schema under `fixtures/{as_of_date}/`; `JsonFixtureReader -> ScanRun -> MomentumScanner` runs unchanged.
- CLI `fetch` flow with `--as-of` (wall-clock touchpoint stays in adapter/CLI layer only).
- Auth via `ALPACA_API_KEY_ID` / `ALPACA_API_SECRET_KEY` env vars only — never in fixtures, logs, or events.
- Config-visible `feed` parameter defaulting to `sip` (SPEC §2.2 authority); `iex` is an explicit, loudly documented degraded-data opt-in recorded in snapshot provenance.

### Out of Scope
- Broker execution, orders, streaming/websockets, intraday data.
- NATS/Postgres wiring, Kubernetes, replay engine.
- Dynamic universe construction, corporate-action providers, earnings/news ingestion.

## Design Positions (carried from exploration)

1. **Live symbol gaps**: snapshot writer fails closed at snapshot time when any universe symbol lacks bars, recording the missing symbols and a clear reason; no fixture is written. Downstream symbol-set-equality semantics stay untouched.
2. **Zero-volume halted sessions**: keep the existing `missing-data` rejection for this slice; calendar-aware halt handling is a documented later revisit, not inherited silently.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `trading-system`: add market-data acquisition requirements — fetch port, snapshot provenance, feed authority/degraded-data rules, fail-closed snapshot gaps, secrets handling.

## Approach

Hexagonal: domain and scanner untouched. New adapter owns HTTP, pagination, retry/error mapping, and snapshot writing; all validation reuses the existing edge-validation pattern. Determinism is preserved because scans always run from written snapshots, never live responses.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/invest/application/ports.py` | Modified | Add `MarketDataReader` port. |
| `src/invest/adapters/alpaca_market_data.py` | New | httpx client, validation, snapshot writer. |
| `src/invest/adapters/cli.py` | Modified | Fetch command, `--as-of`, feed config. |
| `pyproject.toml` | Modified | Add `httpx`. |
| `fixtures/{as_of_date}/` | New | Versioned snapshots, existing schema. |
| `tests/` | Modified | Port/adapter/CLI tests (mocked transport). |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| SIP feed unavailable on account tier | Medium | Fail closed with clear error; explicit `iex` opt-in stamped in provenance. |
| Retroactive corporate-action adjustments stale snapshots | Medium | Snapshots dated and reproducible; document non-eternal accuracy. |
| Secret leakage | Low | Env-vars only; boundary tests forbid secrets in fixtures/events; redact logs. |
| Domain purity erosion | Low | Existing boundary tests extended to new adapter imports. |

## Rollback Plan

Remove adapter module, port addition, CLI fetch flow, `httpx` dependency, and snapshot directories; fixture-based scanning is fully restored.

## Dependencies

- Alpaca Market Data REST API + credentials; `httpx`.

## Success Criteria

- [ ] `fetch` writes a validated snapshot that the unchanged pipeline scans deterministically.
- [ ] Missing universe symbols fail closed at snapshot time with named symbols.
- [ ] Feed defaults to `sip`; `iex` requires explicit opt-in and is recorded.
- [ ] No secrets in fixtures, logs, or events; domain stays SDK/clock-free.
