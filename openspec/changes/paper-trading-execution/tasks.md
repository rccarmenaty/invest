# Tasks: Paper Trading Execution (Alpaca Bracket Orders)

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 1,850-2,100 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR A: pure domain (indicators + sizing + gates + GateReason contract) + contracts (OrderIntentEvent/ack family) + ports widen + `ExecuteRun` dry-run path (fake `BrokerPort`) -> PR B: `alpaca_broker` adapter (snapshot/find_order/bracket POST, idempotency, no-POST-retry, redaction) + `ExecuteRun` `--execute` wiring + `invest-execute` CLI + `paper_execute` marker/smoke + boundary additions |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | ATR extraction + `AccountSnapshot`/`OrderIntent` models | PR A | `uv run --extra dev pytest tests/domain/test_indicators.py tests/domain/test_scanner.py` | N/A: pure function, scanner-regression fixture only | Revert `scanner.py` import, delete `domain/indicators.py`, revert `models.py` additions |
| 2 | Sizing math + boundary values + gates + `GateReason` contract | PR A | `uv run --extra dev pytest tests/domain/test_sizing.py` | N/A: pure Decimal, no I/O | Delete `domain/sizing.py` |
| 3 | `OrderIntentEvent` + ack/skip/halt event family | PR A | `uv run --extra dev pytest tests/contracts/test_events.py` | N/A: fixed-input id hashing | Revert `contracts/events.py` additions |
| 4 | `BrokerPort` protocol + `ExecuteRun` dry-run/halt orchestration | PR A | `uv run --extra dev pytest tests/application/test_execute_run.py` | N/A: fake `BrokerPort` test double, no network | Delete `application/execute_run.py`, revert `ports.py` widen |
| 5 | `alpaca_broker` adapter (snapshot, find_order, bracket POST, retry, redaction) | PR B | `uv run --extra dev pytest tests/adapters/test_alpaca_broker.py` | N/A: `httpx.MockTransport` substitutes the network | Delete `adapters/alpaca_broker.py` |
| 6 | `ExecuteRun` `--execute` wiring + `invest-execute` CLI + exit codes | PR B | `uv run --extra dev pytest tests/adapters/test_cli_execute.py` | `uv run invest-execute --universe fixtures/v1/universe.json --bars fixtures/v1/bars.json` (dry-run, no creds) | Remove `execute_main`, console script |
| 7 | `paper_execute` marker + boundary additions + env-gated smoke | PR B | `uv run --extra dev pytest tests/test_boundaries.py` | `ALPACA_API_KEY_ID=... uv run --extra dev pytest -m paper_execute` (skipped unless env set) | Remove marker registration and smoke test file |

## Phase 1: ATR Extraction (PR A, satisfies design Decision "ATR sourcing")

- [x] 1.1 RED: `tests/domain/test_scanner.py` — scanner-regression test asserting identical `MomentumScanner.scan()` output on a fixed fixture BEFORE the extraction (baseline snapshot of decisions).
- [x] 1.2 RED: `tests/domain/test_indicators.py` — `average_true_range(history)` missing in `domain/indicators.py`.
- [x] 1.3 GREEN: move `MomentumScanner._average_true_range` (scanner.py:60-66) byte-mechanically to `domain/indicators.py::average_true_range` (no `14` suffix; slices to `ATR_DAYS` internally); `scanner.py` imports and calls it.
- [x] 1.4 GREEN: re-run 1.1's regression test — same scan output before/after extraction, byte-identical.

## Phase 2: Domain Models (PR A)

- [x] 2.1 RED: `tests/domain/test_models.py` (or extend existing) — `AccountSnapshot`/`OrderIntent` frozen dataclasses missing from `domain/models.py`.
- [x] 2.2 GREEN: add `AccountSnapshot` (equity, last_equity, buying_power, open_position_count:int, deployed_value, trading_blocked:bool, account_blocked:bool) and `OrderIntent` (symbol, decision_date, qty:int, entry, stop, take_profit) as `Decimal`-field frozen dataclasses to `domain/models.py`.

## Phase 3: Sizing Math + Boundaries (PR A)

- [x] 3.1 RED: `tests/domain/test_sizing.py` — `compute_intent` missing; valid case expects qty floor, entry=quantize(last_close), stop=entry-ATR, take_profit=entry+2*ATR.
- [x] 3.2 GREEN: implement `compute_intent` + `quantize_price` (tick `0.01` if `p>=1` else `0.0001`, `ROUND_HALF_EVEN`) in `domain/sizing.py`.
- [x] 3.3 RED: boundary test — qty floors to whole shares on a non-integer risk/stop-distance ratio.
- [x] 3.4 RED: boundary test — stop distance yields exactly qty==0 -> `sizing-invalid`, no intent emitted.
- [x] 3.5 RED: boundary test — price exactly at $1.00 quantizes to 2dp; price just below $1.00 (e.g. $0.9999) quantizes to 4dp (tick-boundary case).
- [x] 3.6 GREEN: implement zero/negative-qty skip path returning the `sizing-invalid` reason instead of an intent.

## Phase 4: Pre-Trade Gates + GateReason Contract (PR A)

- [x] 4.1 RED: `tests/domain/test_sizing.py` — `GateReason` StrEnum contract test asserting the enum's value set equals exactly `{kill-switch, broker-account-restricted, max-concurrent-positions, sizing-invalid, max-equity-deployed, insufficient-buying-power, already-submitted}` (no additions, no omissions).
- [x] 4.2 GREEN: define `GateReason` StrEnum in `domain/sizing.py` with those exact kebab-case values.
- [x] 4.3 RED: `evaluate_gates` missing; each skip reason tested independently in gate-order: `max-concurrent-positions` (count>=5) -> `sizing-invalid` (qty==0) -> `max-equity-deployed` (deployed+qty*entry>0.25*equity) -> `insufficient-buying-power` (qty*entry>buying_power); first failure wins.
- [x] 4.4 GREEN: implement `evaluate_gates` per-candidate predicate chain, first-failure-wins.
- [x] 4.5 RED: boundary test — exactly 5 open positions triggers `max-concurrent-positions`; exactly 4 does not.
- [x] 4.6 RED: boundary test — deployed value exactly at 25% of equity triggers `max-equity-deployed`; just under does not.
- [x] 4.7 RED: halt-gate test — `kill-switch` at exactly `(equity-last_equity)/last_equity == -0.03` halts; just above -3% does not.
- [x] 4.8 RED: halt-gate test — `broker-account-restricted` when `trading_blocked` or `account_blocked` is true.
- [x] 4.9 GREEN: implement halt gates (`kill-switch`, `broker-account-restricted`) evaluated once from the snapshot before sizing.
- [x] 4.10 RED then GREEN: running `(count, deployed)` projection seeded from snapshot blocks a 2nd candidate that alone would pass but combined with the 1st exceeds a cap.

## Phase 5: Contracts — Intent + Ack Event Family (PR A)

- [x] 5.1 RED: `tests/contracts/test_events.py` — `OrderIntentEvent(EventBase)` missing `qty`, `entry_price`, `stop_price`, `take_profit_price`, `client_order_id`; deterministic `event_id` must reproduce identically for identical inputs (`sha256("1|order.intent.v1|fixture_version|rule_version|symbol|decision_date|qty|stop|take_profit")`).
- [x] 5.2 GREEN: add `OrderIntentEvent` to `contracts/events.py`; prices serialized as `str(quantized)`.
- [x] 5.3 RED: `ExecutionEventBase` + `OrderSubmitted`, `OrderRejected`, `ExecutionSkipped`, `ExecutionHalted` missing; each ack id must be content-addressed (no wall-clock) and MUST NOT reuse the intent's hash scheme.
- [x] 5.4 GREEN: implement `ExecutionEventBase` (separate from deterministic `EventBase`) and the four ack/skip/halt event classes with their content-addressed id formulas.

## Phase 6: BrokerPort + ExecuteRun Dry-Run Orchestration (PR A)

- [x] 6.1 RED: `tests/application/test_ports.py` (or extend) — `BrokerPort` Protocol (`snapshot`, `find_order`, `submit_bracket`) missing from `application/ports.py`; `Journal.append` still narrowly typed to `EventBase`.
- [x] 6.2 GREEN: add `BrokerPort` Protocol; widen `Journal.append(event: BaseModel)`.
- [x] 6.3 RED: `tests/application/test_execute_run.py` — `ExecuteRun` missing; happy path with a fake `BrokerPort` rescans fixture snapshot, sizes each accepted decision, journals `order.intent.v1`, zero submission calls in dry-run.
- [x] 6.4 GREEN: implement `application/execute_run.py::ExecuteRun` (mirrors `ScanRun`): snapshot -> halt gates once -> rescan via `MomentumScanner` -> per-candidate size+gate+journal.
- [x] 6.5 RED: halt-continues test — on halt, exactly ONE `execution.halted.v1` is journaled, THEN every remaining accepted candidate gets its own `execution.skipped.v1` carrying the SAME halt reason; zero submissions; run completes without raising.
- [x] 6.6 GREEN: implement halt-continues-fail-closed loop in `ExecuteRun` per design (never aborts on halt).

## Phase 7: alpaca_broker Adapter (PR B)

- [ ] 7.1 RED: `tests/adapters/test_alpaca_broker.py` — hardcoded-paper-URL test: assert no live-trading URL string exists anywhere under `src/` (rg-style negative scan) and `AlpacaBroker` constructs requests only against `https://paper-api.alpaca.markets`.
- [ ] 7.2 RED: `snapshot()` missing — `MockTransport` fixture for GET `/v2/account` + GET `/v2/positions` expects mapped `AccountSnapshot` (equity, last_equity, buying_power, open_position_count, deployed_value, trading_blocked, account_blocked).
- [ ] 7.3 GREEN: implement `adapters/alpaca_broker.py::AlpacaBroker.snapshot()`.
- [ ] 7.4 RED: `find_order(client_order_id)` — existing order returns its broker order id; missing order returns `None`.
- [ ] 7.5 RED: bracket POST JSON-shape test pinned to verified fields: `order_class="bracket"`, `take_profit.limit_price`, `stop_loss.stop_price` present, no `stop_loss.limit_price` (stop-market), `time_in_force="day"`, `extended_hours` absent/false.
- [ ] 7.6 GREEN: implement `find_order` (GET by `client_order_id`) and `submit_bracket` (single POST) per the pinned shape.
- [ ] 7.7 RED: GET-before-POST idempotency test — existing order found -> no POST call recorded, reports `already-submitted`.
- [ ] 7.8 RED: POST-never-retried test — injected failing transport counts POST invocations; failure/timeout on the mutating POST must record exactly one POST call, no auto-retry.
- [ ] 7.9 GREEN: wire idempotency check before every `submit_bracket` call; ensure only GETs pass through the retry path.
- [ ] 7.10 RED: GET bounded-retry + error-taxonomy test mirroring market-data constants (`MAX_ATTEMPTS=3`, backoff 0.5s->4s, `Retry-After` honored): 401/403->`auth-failure` (no retry), 429->`rate-limited`, 5xx/timeout->`network-failure`, bad JSON->`malformed-response`.
- [ ] 7.11 GREEN: implement bounded retry/backoff and error mapping for GETs only, reusing the `alpaca_market_data.py` pattern.
- [ ] 7.12 RED: credential-redaction test (traceback formatting) — `ALPACA_API_KEY_ID`/`ALPACA_API_SECRET_KEY` values never appear in error/log output, identical discipline to the market-data adapter.
- [ ] 7.13 GREEN: apply the same redaction discipline to `alpaca_broker.py` error formatting.

## Phase 8: ExecuteRun --execute Wiring + CLI (PR B)

- [ ] 8.1 RED: `tests/application/test_execute_run.py` — `--execute` path: passing intent submits via `BrokerPort.submit_bracket`; 201-equivalent ack journals `order.submitted.v1`; broker rejection journals `order.rejected.v1`; `find_order` hit journals `execution.skipped.v1` (reason=`already-submitted`), no duplicate submit.
- [ ] 8.2 GREEN: implement the `--execute` branch in `ExecuteRun` (idempotency check -> submit -> ack/reject/skip journaling).
- [ ] 8.3 RED: `tests/adapters/test_cli_execute.py` — dry-run default prints computed intents and makes zero broker mutation calls.
- [ ] 8.4 RED: `--execute` flag opts into submission; a broker-acknowledgement event is journaled when gates pass.
- [ ] 8.5 RED: infrastructure-failure test — auth/network/rate-limit/malformed-response/fixture-invalid each print exactly one machine-readable `{"reason": ...}` record and exit 2.
- [ ] 8.6 RED: business-outcome test — a run where every candidate is skipped/halted/already-submitted/rejected exits 0 with the full event list printed.
- [ ] 8.7 GREEN: implement `adapters/cli.py::execute_main` (`--universe`, `--bars`, `--snapshot`, `--format json`, `--execute`) mirroring `fetch_main`; wire `AlpacaBroker` + `ExecuteRun`; add `invest-execute` console script to `pyproject.toml`.

## Phase 9: Marker Registration + Boundary + Smoke (PR B)

- [ ] 9.1 RED: `tests/test_boundaries.py` — `test_paper_execute_marker_is_registered` fails, `paper_execute` marker absent from `pyproject.toml`.
- [ ] 9.2 GREEN: register `paper_execute: submits a real paper order to Alpaca` marker in `pyproject.toml`.
- [ ] 9.3 RED then GREEN: extend `test_boundaries.py`'s forbidden-import scan — `domain/sizing.py` and `domain/indicators.py` stay free of `httpx`/Alpaca imports (existing AST test, no structural change needed beyond covering new files).
- [ ] 9.4 RED then GREEN: `@pytest.mark.paper_execute` smoke test submitting one real paper bracket order and cancelling it; skipped unless `ALPACA_API_KEY_ID`/`ALPACA_API_SECRET_KEY` are set.
