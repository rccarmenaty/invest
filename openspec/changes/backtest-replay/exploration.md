# Exploration: backtest-replay

Validate whether the momentum strategy has edge before any live trading, per SPEC.md's mandate that backtest/replay proves expectancy before paper execution — a phase this project built out of order.

## Current State

Three archived slices (`implementation-foundation`, `market-data-adapter`, `paper-trading-execution`) form an in-memory/CLI-only hexagonal codebase — no NATS/Postgres/k8s despite SPEC.md's target architecture. `MomentumScanner.scan()` (`src/invest/domain/scanner.py`) is a pure, deterministic day-0 `CANDIDATE` filter (rel-vol, ATR move, breakout, not-extended). `sizing.py` (`compute_intent`, `evaluate_gates`, `GateReason`) is pure Decimal sizing/risk math, already reusable. `AlpacaMarketDataReader.fetch()` (`src/invest/adapters/alpaca_market_data.py`) hardcodes a 40-day trailing window (`CALENDAR_BUFFER_DAYS`) sized for one scan decision, not bulk history — but the underlying Alpaca endpoint already accepts arbitrary start/end, so extending it is additive, not a rewrite. `ExecuteRun` executes directly on day-0 `candidate.accepted.v1`, an explicit user-resolved "interim simplification" recorded in `paper-trading-execution/proposal.md` — SPEC §2.4's confirmation stage (`CANDIDATE → WATCHING → CONFIRMED`) was never built, and no `CorporateCalendarPort`/earnings/point-in-time-universe provider exists anywhere (grep confirms zero hits). The universe is a fully static fixture. SPEC's "replay is the backtesting substrate" (NATS JetStream framing) maps cleanly onto this codebase's existing pattern: the pure domain functions are already proven replay-safe (deterministic sha256 event IDs), so no transport is needed to satisfy the requirement's intent.

## Affected Areas

- `src/invest/application/backtest_run.py` (new) — day-by-day harness reusing `MomentumScanner`/`sizing.py`
- `src/invest/domain/backtest_metrics.py` (new, pure) — hit rate/expectancy/drawdown/trade log
- `src/invest/adapters/alpaca_market_data.py` — extend with `fetch_range(universe, start, end)`
- `src/invest/adapters/cli.py` — new `invest-backtest` entrypoint (never touches `BrokerPort`)
- `fixtures/` — small synthetic multi-year fixture for tests

## Approaches

**A. Confirmation-dependency** (requires explicit user decision):
1. Day-0-only backtest, labeled — Effort: Low. Cheapest, but may answer the wrong question per SPEC's own edge thesis.
2. Build minimal confirmation first — Effort: Medium-High. Answers SPEC's real question but needs data (earnings) this project doesn't have.
3. Both, side by side — Effort: High. Most honest, most work.

**B. Bulk historical fetch**:
1. Extend `AlpacaMarketDataReader` with `fetch_range()` — Effort: Low. **Recommended.**
2. New standalone adapter — duplicated logic, rejected.
3. Loop narrow `fetch(as_of)` daily — needless complexity, rejected.

**C. Point-in-time universe honesty**:
1. Reuse static current universe as historical — exactly what SPEC forbids. Rejected outright.
2. Real point-in-time index-membership provider — Effort: High, out of scope (new paid-vendor dependency, no seam).
3. Fixed historical liquid-universe screen, loudly labeled survivorship-biased — Effort: Low-Medium. **Recommended.**

## Recommendation

CLI-first `invest-backtest` harness reusing the existing pure scanner/sizing functions day-by-day (B.1 for data), pure `backtest_metrics.py` for reporting, C.3 for universe honesty (loud disclaimer, never silent), fixed-bps slippage + zero-commission + flat tax-haircut for fees (documented as an approximation, not precision). **Approach A is flagged for explicit user decision** before `sdd-propose` — recommendation if forced: day-0-only first, explicitly labeled as measuring current paper-trading mechanics, not SPEC's confirmed-entry thesis, mirroring the day-0 pattern already used in `paper-trading-execution`.

## Risks

- Confirmation-dependency decision unresolved — must be named in proposal.
- Point-in-time universe remains genuinely non-compliant even under the recommended interim.
- No earnings/corporate-action data exists for any confirmation variant.
- Fees/slippage/tax model is a defensible approximation, not precision — must be reported as such.
- Results could legitimately fail SPEC's own 35-40% gate — expected valid outcome, not a harness defect.

## Ready for Proposal

Yes, with required carry-forward: `sdd-propose` must explicitly resolve the confirmation-dependency decision (Approach A) and the point-in-time-universe honesty disclaimer (Approach C.3) as named, non-silent decisions.
