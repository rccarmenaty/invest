# Roadmap

**Purpose**: orient any agent or human picking up this repo from zero. Read this first, then `SPEC.md` (system specification) and `momentum_breakout_swing_trading_research_report.md` (evidence review that drives the strategy direction).

**Last updated**: 2026-07-16

---

## 1. Where we are

The project follows the hard-gated delivery phases in `SPEC.md` §5:

| Phase | Status |
|---|---|
| 1. Signals only | ✅ Done — deterministic scanner + CLI over validated fixtures |
| 2. Replay/backtest | ⏳ **In progress — we are here** |
| 3. Paper loop | Scaffolding exists (`execute_run`, Alpaca paper broker adapter); soak not started |
| 4. Live readiness rehearsal | Not started |
| 5. Live small | Not started |

**Repo reality vs SPEC aspiration**: `SPEC.md` §3 describes an event-driven k8s microservice target (NATS, Postgres, 9 pods). The current codebase is deliberately a **single hexagonal Python package with a CLI** (`src/invest/`: `domain/`, `application/`, `adapters/`, `contracts/`) — the domain logic is being proven first; infrastructure decomposition comes only after Phase 2/3 gates pass. Do not build k8s/NATS/Postgres infrastructure yet.

## 2. What is implemented (as of 2026-07-16)

- **Benchmark scanner** (`domain/scanner.py`): day-0 spike detector — 2× relative volume, ≥1.5 ATR move, close above 20-day high, anti-extension cap. Per the research report this is the **benchmark control strategy**, not the primary model.
- **Core momentum selection scanner** (`domain/momentum_selection_scanner.py`, `domain/indicators.py`): Core-model candidate selection — 12-1 month relative-momentum ranking (top 15%), 52-week-high proximity (≥95%), 50/200-day trend filter with rising SMA200, minimum-history gate, granular per-layer rejection reasons. Wired as `invest-backtest --strategy core` alongside the benchmark scanner (change A, delivered).
- **Sizing & gates** (`domain/sizing.py`): 1% risk/trade, 1 ATR stop, 2 ATR take-profit, max 5 positions, 25% deployment cap, −3% kill switch, broker-restriction gates. (Interim values; change C lowers risk to the 0.35% baseline.)
- **Backtest harness** (`application/backtest_run.py`): day-by-day replay with structural look-ahead prevention, next-open fills, slippage + tax modeling, gap-through stops, conservative stop-wins tie-break, holdout `--split-date`, gate telemetry.
- **Point-in-time market context** (`domain/market_context.py`, `adapters/backtest_context_json.py`): date-effective symbol eligibility, corporate-action and earnings blocker windows, fail-closed validation, forced closes for unsafe positions.
- **Sharadar data adapters** (`adapters/sharadar_market_data.py`, `adapters/sharadar_tickers.py`, `adapters/sharadar_actions.py`): survivorship-bias-free SEP daily bars (delisted names included), ticker reference data (listing/delisting dates, primary-common-stock classification), typed corporate actions (splits, dividends, delistings, ticker changes) — all fail-closed, all Decimal-exact. Selected with `invest-backtest --source sharadar`.
- **Market-context generator** (`domain/liquidity_screen.py`, `domain/market_context_builder.py`, `application/generate_market_context.py`, `adapters/sharadar_context_source.py`, `adapters/generate_context_cli.py`): standalone `invest-generate-context` CLI that produces point-in-time `market-context-v1` files from Sharadar — broad candidate discovery without a pre-supplied roster, configurable liquidity screen (price ≥ $10, 20-bar median dollar volume ≥ $10M, 252-bar history, no look-ahead), corporate-action blocker windows, atomic fail-closed writer.
- **Paper execution slice** (`application/execute_run.py`, `adapters/alpaca_broker.py`): paper-endpoint-only bracket order submission with halt gates.
- **Alpaca market data** (`adapters/alpaca_market_data.py`): historical bars fetch (`fetch_range`), fail-closed on incomplete data.

### Completed openspec changes (archived)

| Date | Change |
|---|---|
| 2026-07-12 | `implementation-foundation` — contracts, scanner, journal, CLI |
| 2026-07-12 | `market-data-adapter` — Alpaca bars adapter |
| 2026-07-12 | `paper-trading-execution` — paper broker + execute flow |
| 2026-07-12 | `backtest-replay` — day-0 replay harness |
| 2026-07-13 | `portfolio-aware-backtest` — cash/equity accounting, gates in replay |
| 2026-07-13 | `point-in-time-market-context` — PIT eligibility, blockers, fail-closed context |
| 2026-07-14 | `momentum-selection-scanner` — Core-model candidate selection (change A) |
| 2026-07-15 | `sharadar-reference-data-adapter` — TICKERS + ACTIONS readers |
| 2026-07-15 | `sharadar-sep-adapter` — SEP daily-bars reader + `--source` selection flag |
| 2026-07-16 | `sharadar-context-generator` — point-in-time market-context generation CLI |

## 3. In flight

Nothing in flight. Change A and the Sharadar data track (a necessary unplanned workstream: reference data → SEP bars → context generator) are delivered and archived. Next up: **change B, `trailing-exit-engine`** (§5).

## 4. Strategy direction (research-driven, 2026-07-13)

`momentum_breakout_swing_trading_research_report.md` reviewed the academic evidence and concluded:

1. **Momentum is a selection effect before it is an entry signal** — the strongest edge is choosing established intermediate-term winners (12-1 month momentum) near their 52-week high, not detecting day-0 spikes.
2. The current scanner ≈ the report's **"plain breakout benchmark"** — keep it as the control the new model must beat.
3. Hard 2× volume vetoes and fixed profit targets are **not** supported by the evidence; volume becomes a tested feature, exits become trailing.

`SPEC.md` §2 has been revised to encode this. The primary research model is the **Core 52-Week-High Momentum Breakout** (report §6).

## 5. Planned changes (Phase 2 continuation)

| # | Change (proposed name) | Scope | Status / depends on |
|---|---|---|---|
| A | `momentum-selection-scanner` | 252-day bar history; 12-1 month relative-momentum ranking (top 15%); 52-week-high proximity filter (≥95%); 50/200-day trend filter. New selection scanner **alongside** the existing benchmark scanner. | ✅ Done — archived 2026-07-14 |
| B | `trailing-exit-engine` | Replace fixed 2 ATR take-profit in the backtest with a trailing 10-day-low exit (daily ratchet, never loosened) + time stop; include the 3 ATR trailing variant in the same grid (feeds conflict #1 resolution). Backtest-side only; Phase-3 execution model decided at D. | **Next** |
| C | `regime-and-vol-sizing` | Benchmark (index) bars port; market-regime filter (benchmark above 200-day SMA); volatility-scaled risk per trade (test 0.20%–0.75%, baseline 0.35%; retires the interim 1%). **Data dependency**: Sharadar SEP excludes ETFs — benchmark daily bars come from the existing Alpaca adapter (SPY closes) unless a Sharadar SFP subscription or a universe-breadth proxy is chosen instead. | B |
| D | Phase 2 exit gate | Run benchmark vs Core through the same harness, same holdout, over 2–3 years of point-in-time data. Judge with the report §12 decision criteria (robust parameter regions, subperiod consistency, cost sensitivity, survivable drawdowns). **Acceptance criteria must be pre-registered in the D proposal, dated, before the first full run** (report §10.3). | B, C |

Optional, only after D passes: objective volatility-contraction features (report §7, one at a time), a separate earnings-gap event module (report §8), and earnings-proximity blocker windows derived from Sharadar fundamentals point-in-time filing dates (verify field semantics first).

Keep every change within the 800-line authored review budget — split like the PIT change if forecast exceeds it.

## 6. Known conflicts to resolve

1. **Trailing exits vs Alpaca bracket orders — mitigations identified (2026-07-16)**: server-side brackets carry a fixed take-profit leg, but Alpaca also supports native **server-side trailing-stop orders** (`trail_price`/`trail_percent`, high-water-mark based). Candidate resolutions: (a) native trailing stop as an always-on catastrophic protection layer, with EOD cancel/replace implementing the exact 10-day-low channel ratchet; (b) if change D shows the 3 ATR trailing variant performs comparably to the 10-day-low exit, use the native trailing stop alone — fully restoring the "positions protected without cluster uptime" property in `SPEC.md` §3.7. Decide at change D with backtest data; change B (backtest-side trailing exits) is safe to build first either way.
2. ~~**Data volume**~~ **Resolved (2026-07-15/16)**: `--source sharadar` provides 252+ bars per symbol via SEP `fetch_range`, and `invest-generate-context` produces matching point-in-time context files for the full range.
3. **Confirmation layer** (`SPEC.md` §2.6 follow-through) is a house hypothesis, not research-validated — test it as an incremental feature against the Core model, never bundle it silently.

## 7. Ground rules (unchanged)

- Strict TDD: red → green → refactor for all trading logic.
- Paper-first: no live keys until Phase 2 and 3 gates pass with pre-registered assumptions.
- Fail closed on missing/invalid data; every rejection is logged with a reason.
- Domain stays pure (no adapter/SDK/clock imports) — enforced by boundary tests.
- Reproducibility: every gate-relevant backtest run should be traceable to a git SHA, context-file hash, data range, and parameter set (see report §11 overfitting warnings).
