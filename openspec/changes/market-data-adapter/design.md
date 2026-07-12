# Design: Market Data Adapter (Alpaca Daily Bars)

## Technical Approach

Fetch-to-fixture-then-scan. A new `AlpacaMarketDataReader` (raw `httpx`, Pydantic edge validation, pagination, bounded retry, error mapping) fetches split-adjusted daily bars for an input universe and returns a validated `FixtureInputs`. A `SnapshotWriter` serializes that into the **existing byte-compatible fixture JSON schema** plus a provenance sidecar under `fixtures/snapshots/{as-of}/`. The unchanged `JsonFixtureReader -> ScanRun -> MomentumScanner` pipeline then replays the snapshot. Domain stays pure, clock-free, SDK-free; determinism is preserved because scans always run from written snapshots, never live responses.

## Architecture Decisions

### Decision: Separate `invest-fetch` entrypoint (not a `invest-scan` subcommand/flag)
**Choice**: New console script `invest-fetch --universe <path> --as-of <YYYY-MM-DD> [--feed sip|iex] [--out fixtures/snapshots]`.
**Alternatives**: `invest-scan fetch` subparser; `--fetch` flag on scan.
**Rationale**: Fetch (network, secrets, writes) and scan (offline, deterministic replay) are distinct concerns. A separate binary keeps `invest-scan` pinned, offline, and secret-free, matches the hexagonal seam, and avoids retrofitting subparsers onto the tested scan CLI.

### Decision: One adapter module, two SRP classes
**Choice**: `alpaca_market_data.py` holds Pydantic response models, `AlpacaMarketDataReader` (port impl), and `SnapshotWriter`.
**Alternatives**: Separate writer module; writer folded into the reader.
**Rationale**: Cohesion mirrors the single-file `fixtures_json.py` adapter; separate classes keep fetch vs persistence responsibilities clean.

### Decision: `as-of` is a required explicit argument (no wall-clock default)
**Choice**: `--as-of` required; the only wall-clock touch is `fetch_timestamp` in provenance (audit metadata, never a decision input).
**Alternatives**: Default to today with loud provenance.
**Rationale**: SPEC §2.1 point-in-time reproducibility. A today-default invites accidental non-reproducible snapshots on re-run. Domain stays clock-free either way.

### Decision: `adjustment=split` (split-adjusted, not raw, not `all`)
**Choice**: Request split-adjusted daily bars.
**Alternatives**: `raw`; `all` (split+dividend).
**Rationale**: Spike/breakout/rel-vol/ATR compare close to the 20-day high; an unadjusted split fabricates a false breakout/gap (SPEC §2.1 requires adjusted series). Split-only keeps prices near tradable levels while removing split discontinuities; dividend adjustment shifts absolute levels used by the breakout check. Position-layer corporate-action reconciliation (SPEC §2.5) stays out of scope. Recorded in provenance.

### Decision: Fail-closed pre-write on symbol gaps; `SnapshotWriter` writes nothing on any gap
**Choice**: If any requested universe symbol has zero returned bars, raise naming the missing symbols; no partial snapshot is written.
**Rationale**: Carries the proposal position and mirrors `FIXTURE_SYMBOL_MISSING`; `JsonFixtureReader` symbol-set-equality remains defense-in-depth after write.

## Data Flow

    invest-fetch --universe --as-of
        │  read input universe (existing _UniversePayload schema)
        ▼
    AlpacaMarketDataReader.fetch(universe, as_of)
        │  httpx GET /v2/stocks/bars (paginated) → Pydantic validate → FixtureInputs
        ▼
    SnapshotWriter.write(inputs, provenance)   ── fail-closed on symbol gap ──▶ exit 2, no files
        │  fixtures/snapshots/{as-of}/{universe.json,bars.json,provenance.json}
        ▼
    invest-scan --universe … --bars …  (UNCHANGED: JsonFixtureReader → ScanRun → MomentumScanner)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/invest/application/ports.py` | Modify | Add `MarketDataReader` Protocol. |
| `src/invest/adapters/alpaca_market_data.py` | Create | httpx client, Pydantic models, pagination, retry, error map, `SnapshotWriter`. |
| `src/invest/adapters/cli.py` | Modify | Add `fetch_main` (`invest-fetch`); `invest-scan` untouched. |
| `pyproject.toml` | Modify | Add `httpx`; add `invest-fetch` console script. |
| `fixtures/snapshots/{as-of}/` | Create | Versioned snapshots + provenance. |
| `tests/` | Modify | Port/adapter/CLI/boundary/live tests. |

## Interfaces / Contracts

```python
# ports.py
class MarketDataReader(Protocol):
    def fetch(self, universe: Universe, as_of: date) -> FixtureInputs: ...
```

Snapshot files (`fixture_version = as-of date string`, shared across both, so version-match holds):
- `universe.json` → `{fixture_version, symbols}` (byte-compatible `_UniversePayload`).
- `bars.json` → `{fixture_version, bars:[{symbol,date,open,high,low,close,volume}]}` (byte-compatible `_BarsPayload`).
- `provenance.json` (sidecar, NOT read by `JsonFixtureReader`): `{feed, adjustment, timeframe:"1Day", endpoint, as_of, fetch_timestamp (UTC ISO8601), symbol_count, bar_count, universe_sha256, bars_sha256, fixture_version}`.

Alpaca mapping: `GET https://data.alpaca.markets/v2/stocks/bars`, params `symbols` (comma-join), `timeframe=1Day`, `start`/`end` (calendar window ≈ as_of−40d … as_of, buffering weekends/holidays for the 21-bar need), `feed`, `adjustment=split`, `limit=10000`, `page_token`. Auth headers `APCA-API-KEY-ID`/`APCA-API-SECRET-KEY` from env `ALPACA_API_KEY_ID`/`ALPACA_API_SECRET_KEY`. Pagination loops on `next_page_token` until null, merging per-symbol bars.

Fetch error taxonomy (`MarketDataFetchError`, distinct from scan-phase `RejectionReason`; all fail closed, no snapshot, CLI exit 2):

| Condition | Reason | Handling |
|---|---|---|
| 401 / 403 | `auth` | No retry; fail closed. |
| 429 | `rate-limit` | Bounded retry (max 3), backoff base 0.5s cap 4s, honor `Retry-After` capped; then fail. |
| 5xx / timeout / connection | `network` | Bounded retry (max 3), same backoff; then fail. |
| 200 but symbol has zero bars | `symbol-gap` | Fail closed naming symbols. |
| Schema/parse/value error | `invalid-response` | No retry; fail closed. |

Retry is bounded, deterministic (fixed schedule, no jitter), adapter-only; `sleep` is injected (tests pass a no-op). Secrets are read from env only, never logged, never written to fixtures/provenance/events.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Pagination merge, split-adjust param, error→reason mapping, retry exhaustion, secret redaction | `httpx.MockTransport` (no new dep) + recorded JSON under `tests/fixtures/alpaca/`; injected no-op sleep |
| Unit | Fail-closed: 401→auth, 429-exhausted→rate-limit, 5xx-exhausted→network, missing symbol→symbol-gap, bad JSON→invalid-response; assert no files written | MockTransport |
| Integration | Written snapshot loads unchanged through `JsonFixtureReader`; provenance hashes match file bytes | Temp dir round-trip |
| Boundary | `httpx` added to domain forbidden imports; domain stays clock/SDK-free | Extend `tests/test_boundaries.py` |
| Smoke | Real API tiny universe | `@pytest.mark.live`, skipped unless `ALPACA_API_KEY_ID` set |

**Mock choice**: `httpx.MockTransport` over `respx` — zero extra dependency, deterministic, consistent with the raw-httpx-over-SDK stance.

Strict TDD sequence (RED first per unit):

| Step | First failing behavior |
|---|---|
| 1 | `MarketDataReader` Protocol / `fetch` shape exists and returns `FixtureInputs`. |
| 2 | Single-page happy path maps Alpaca JSON → validated `FixtureInputs`. |
| 3 | Multi-page `next_page_token` merges bars per symbol. |
| 4 | 401→`auth`, malformed→`invalid-response` (no retry, no files). |
| 5 | 429/5xx retry bounded then `rate-limit`/`network`; injected sleep asserted. |
| 6 | Missing universe symbol → `symbol-gap`, no snapshot written. |
| 7 | `SnapshotWriter` emits byte-compatible files + provenance; `JsonFixtureReader` loads them. |
| 8 | `invest-fetch` CLI: success writes snapshot exit 0; failure exit 2 with reason; `--as-of` required. |
| 9 | Boundary test fails on `httpx` import under `src/invest/domain`. |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. This change adds an outbound HTTPS client; secret handling is covered by env-only reads, log redaction, and boundary tests (see Testing).

## Migration / Rollout

No data migration. Rollback removes the adapter module, the port addition, the `invest-fetch` script, the `httpx` dependency, and `fixtures/snapshots/`; fixture-based scanning is fully restored.

## Decisions and Tradeoffs

| Decision | Rejected alternative | Rationale |
|---|---|---|
| Separate `invest-fetch` entrypoint | Scan subcommand/flag | Keeps `invest-scan` offline, deterministic, secret-free. |
| `httpx.MockTransport` | `respx` | No extra dependency; deterministic. |
| Required `--as-of` | Wall-clock default | Point-in-time reproducibility (SPEC §2.1). |
| `adjustment=split` | `raw` / `all` | Continuous series for breakout/rel-vol; avoids false split gaps. |
| Fetch taxonomy distinct from `RejectionReason` | Reuse scan reasons | Fetch fails before any scan; no `scan.failed` events. |
| Snapshot `fixture_version = as-of` | Static `v1` | Self-identifying, unique, deterministic per snapshot. |

**Carried decisions**: fail-closed symbol gaps (no partial snapshot); zero-volume still `missing-data` unchanged (halted-session semantics deferred); `feed=sip` default with explicit, provenance-stamped `iex` degraded-data opt-in (SPEC §2.2 authority).

## Open Questions

None.
