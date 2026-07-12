# Tasks: Market Data Adapter (Alpaca Daily Bars)

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 750-1,050 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR A: port + Alpaca client + error taxonomy -> PR B: snapshot writer + provenance + `invest-fetch` CLI + boundary/live tests |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Port + client happy path/pagination | PR A | `uv run --extra dev pytest tests/adapters/test_alpaca_market_data.py -k "port or pagination or happy"` | N/A: MockTransport substitutes the network | Remove `MarketDataReader` from `ports.py` and the reader class |
| 2 | Error taxonomy + bounded retry | PR A | `uv run --extra dev pytest tests/adapters/test_alpaca_market_data.py -k "error or retry or redact"` | N/A: injected no-op sleep + MockTransport | Remove error-mapping/retry logic, revert to Unit 1 |
| 3 | Snapshot writer + provenance + fail-closed | PR B | `uv run --extra dev pytest tests/adapters/test_alpaca_market_data.py -k "snapshot or provenance or symbol_missing or halted"` | Temp-dir round trip through `JsonFixtureReader` | Remove `SnapshotWriter` and `fixtures/snapshots/` writes |
| 4 | `invest-fetch` CLI + packaging | PR B | `uv run --extra dev pytest tests/adapters/test_cli_fetch.py` | `uv run invest-fetch --universe fixtures/v1/universe.json --as-of 2026-06-01 --out /tmp/snap` | Remove `fetch_main`, console script, `httpx` dep |
| 5 | Boundary + live + calendar coverage | PR B | `uv run --extra dev pytest tests/test_boundaries.py tests/adapters/test_alpaca_market_data.py -k "calendar or live"` | `ALPACA_API_KEY_ID=... uv run --extra dev pytest -m live` (skipped unless env set) | Remove boundary-rule addition and live-marked test file |

## Phase 1: Port + Client Happy Path (PR A)

- [x] 1.1 RED: `tests/adapters/test_alpaca_market_data.py` — `MarketDataReader` Protocol/`fetch()` shape missing; single-page MockTransport fixture expects mapped `FixtureInputs` with `adjustment=split`.
- [x] 1.2 GREEN: add `MarketDataReader` Protocol to `src/invest/application/ports.py`; create `src/invest/adapters/alpaca_market_data.py` with Pydantic response models + single-page GET (`symbols`, `timeframe=1Day`, `start`/`end`≈as_of-40d, `feed=sip` default, `adjustment=split`, `limit=10000`).
- [x] 1.3 RED: two-response MockTransport fixture with `next_page_token` expects merged per-symbol bars.
- [x] 1.4 GREEN: implement pagination loop until `next_page_token` is null; REFACTOR request builder.

## Phase 2: Error Taxonomy + Retry (PR A)

- [x] 2.1 RED: 401 / malformed-body MockTransport fixtures expect reasons `auth-failure` / `malformed-response`, no retry, no files written.
- [x] 2.2 GREEN: map 401/403 → `auth-failure`; schema/parse/value errors → `malformed-response` (no retry, fail closed). Use these exact SPEC reason strings everywhere (not design's shorter `auth`/`invalid-response`).
- [x] 2.3 RED: 429 and 5xx/timeout fixtures exhausted across 3 attempts (injected no-op sleep spy) expect reasons `rate-limited` / `network-failure`, deterministic backoff (0.5s/1s/2s capped 4s), no files.
- [x] 2.4 GREEN: implement bounded retry (max 3, fixed schedule, `Retry-After` capped, injected `sleep`); map 429→`rate-limited`, 5xx/timeout/connection→`network-failure`.
- [x] 2.5 RED then GREEN: secret-redaction test — `ALPACA_API_KEY_ID`/`ALPACA_API_SECRET_KEY` values never appear in error/log output; redact in error formatting.

## Phase 3: Snapshot Writer + Provenance (PR B)

- [ ] 3.1 RED: universe symbol with zero returned bars expects pre-write abort, reason `symbol-missing-at-fetch` naming the missing symbols, no fixture written.
- [ ] 3.2 GREEN: implement fail-closed check in `SnapshotWriter.write` before any file I/O.
- [ ] 3.3 RED: complete-universe fixture expects `fixtures/snapshots/{as-of}/universe.json` + `bars.json` (byte-compatible `_UniversePayload`/`_BarsPayload`) and `provenance.json` with `feed`, `adjustment`, `timeframe`, `endpoint`, `as_of`, `fetch_timestamp`, `symbol_count`, `bar_count`, `universe_sha256`, `bars_sha256`, `fixture_version`, and boolean `degraded`.
- [ ] 3.4 GREEN: implement `SnapshotWriter` writing all three files under `fixtures/snapshots/{as-of}/` — deviation: supersedes proposal's `fixtures/{as_of_date}/`, keeping generated snapshots separate from static `fixtures/v1/`; set `degraded = (feed == "iex")`.
- [ ] 3.5 RED then GREEN: `iex` config expects provenance `feed: iex`, `degraded: true`; `sip` default expects `degraded: false`.
- [ ] 3.6 RED then GREEN: integration round trip — written snapshot loads unchanged via `JsonFixtureReader`; `MomentumScanner` runs against it.
- [ ] 3.7 RED then GREEN: halted-session zero-volume bar (symbol present) passes snapshot write; scanner still rejects that symbol as `missing-data`, unchanged.

## Phase 4: `invest-fetch` CLI + Packaging (PR B)

- [ ] 4.1 RED: `tests/adapters/test_cli_fetch.py` — missing `--as-of` errors before any fetch attempt; success path exits 0 and writes snapshot; mocked `auth-failure` exits 2 printing the reason, no partial files.
- [ ] 4.2 GREEN: implement `fetch_main` (`--universe`, `--as-of` required, `--feed sip|iex`, `--out`) wiring `AlpacaMarketDataReader` + `SnapshotWriter`; add `invest-fetch` console script and `httpx` dependency to `pyproject.toml`.

## Phase 5: Boundary + Live/Calendar Coverage (PR B)

- [ ] 5.1 RED then GREEN: extend `tests/test_boundaries.py` forbidding `httpx` and Alpaca imports under `src/invest/domain`.
- [ ] 5.2 RED then GREEN: add `@pytest.mark.live` smoke test, skipped unless `ALPACA_API_KEY_ID` is set, fetching a tiny real universe.
- [ ] 5.3 RED then GREEN: calendar-buffer test pinning the as_of−40d…as_of window across a holiday cluster (e.g. Thanksgiving weekend) yields ≥21 trading bars per symbol.
