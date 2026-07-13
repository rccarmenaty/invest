# Roadmap

**Purpose**: orient any agent or human picking up this repo from zero. Read this first, then `SPEC.md` (system specification) and `momentum_breakout_swing_trading_research_report.md` (evidence review that drives the strategy direction).

**Last updated**: 2026-07-13

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

## 2. What is implemented (as of 2026-07-13)

- **Scanner** (`domain/scanner.py`): day-0 spike detector — 2× relative volume, ≥1.5 ATR move, close above 20-day high, anti-extension cap. Per the research report this is the **benchmark control strategy**, not the primary model.
- **Sizing & gates** (`domain/sizing.py`): 1% risk/trade, 1 ATR stop, 2 ATR take-profit, max 5 positions, 25% deployment cap, −3% kill switch, broker-restriction gates.
- **Backtest harness** (`application/backtest_run.py`): day-by-day replay with structural look-ahead prevention, next-open fills, slippage + tax modeling, gap-through stops, conservative stop-wins tie-break, holdout `--split-date`, gate telemetry.
- **Point-in-time market context** (`domain/market_context.py`, `adapters/backtest_context_json.py`): date-effective symbol eligibility, corporate-action and earnings blocker windows, fail-closed validation, forced closes for unsafe positions.
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

## 3. In flight

**`point-in-time-market-context`**: DONE — verified (pass, 210 tests), 4R-review approved, archived to `openspec/changes/archive/2026-07-13-point-in-time-market-context/`, and **merged to main** via PR #20 (squash, `143bb9f`). Local `feat/pit-*` and `fix/pit-*` branches plus OpenCode worktrees are leftover scaffolding, safe to prune.

**`momentum-selection-scanner`** (change A below): SDD chain active on branch `feat/momentum-selection-scanner` — exploration and proposal complete (`openspec/changes/momentum-selection-scanner/`), spec/design/tasks/apply pending.

## 4. Strategy direction (research-driven, 2026-07-13)

`momentum_breakout_swing_trading_research_report.md` reviewed the academic evidence and concluded:

1. **Momentum is a selection effect before it is an entry signal** — the strongest edge is choosing established intermediate-term winners (12-1 month momentum) near their 52-week high, not detecting day-0 spikes.
2. The current scanner ≈ the report's **"plain breakout benchmark"** — keep it as the control the new model must beat.
3. Hard 2× volume vetoes and fixed profit targets are **not** supported by the evidence; volume becomes a tested feature, exits become trailing.

`SPEC.md` §2 has been revised to encode this. The primary research model is the **Core 52-Week-High Momentum Breakout** (report §6).

## 5. Planned changes (Phase 2 continuation)

Sequence after the in-flight change is delivered and archived:

| # | Change (proposed name) | Scope | Depends on |
|---|---|---|---|
| A | `momentum-selection-scanner` | 252-day bar history fixtures; 12-1 month relative-momentum ranking (top 15%); 52-week-high proximity filter (≥95%); 50/200-day trend filter. New selection scanner **alongside** the existing benchmark scanner. | PIT market context delivered |
| B | `trailing-exit-engine` | Replace fixed 2 ATR take-profit in the backtest with a trailing 10-day-low exit (daily ratchet, never loosened) + time stop. Requires `SPEC.md` §2.5 exit-model change and has Phase-3 implications (see conflicts). | A |
| C | `regime-and-vol-sizing` | Benchmark (index) bars port; market-regime filter (benchmark above 200-day SMA); volatility-scaled risk per trade (test 0.20%–0.75%, baseline 0.35%). | A |
| D | Phase 2 exit gate | Run benchmark vs Core through the same harness, same holdout, over 2–3 years of point-in-time data. Judge with the report §12 decision criteria (robust parameter regions, subperiod consistency, cost sensitivity, survivable drawdowns). | A, B, C |

Optional, only after D passes: objective volatility-contraction features (report §7, one at a time) and a separate earnings-gap event module (report §8 — needs earnings-timestamp data we do not have).

Keep every change within the 800-line authored review budget — split like the PIT change if forecast exceeds it.

## 6. Known conflicts to resolve

1. **Trailing exits vs Alpaca bracket orders**: server-side brackets carry a fixed take-profit leg; a trailing exit means stop-only orders with daily cancel/replace. This changes the Phase 3 execution model and the "positions protected without cluster uptime" property in `SPEC.md` §3.7. Decide before implementing change B in the live path (backtest-side trailing exits are safe to build first).
2. **Data volume**: fixtures currently hold ~21 bars/symbol; change A needs 252+. Use `fetch_range` or extended curated fixtures, and extend the point-in-time context files to match the longer range.
3. **Confirmation layer** (`SPEC.md` §2.4 follow-through) is a house hypothesis, not research-validated — test it as an incremental feature against the Core model, never bundle it silently.

## 7. Ground rules (unchanged)

- Strict TDD: red → green → refactor for all trading logic.
- Paper-first: no live keys until Phase 2 and 3 gates pass with pre-registered assumptions.
- Fail closed on missing/invalid data; every rejection is logged with a reason.
- Domain stays pure (no adapter/SDK/clock imports) — enforced by boundary tests.
