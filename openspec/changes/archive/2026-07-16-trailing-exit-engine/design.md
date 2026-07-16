# Design: Trailing Exit Engine

## Technical Approach

Replace fixed take-profit replay exits with a pure, clock-free exit policy in `domain/exit_policy.py`, wired only into `BacktestRun`. `OrderIntent.take_profit`, sizing, paper brackets, and `ExecuteRun` stay untouched; backtest ignores intent TP for exits. Benchmark and Core share one policy seam. Maps to proposal Approach 1 and trading-system delta specs.

## Architecture Decisions

| Decision | Options | Tradeoff | Choice |
|----------|---------|----------|--------|
| Policy placement | Inline `_exit_for_bar` vs pure module | Inline faster; pure enables TDD/grid | **`domain/exit_policy.py` pure** |
| Scope | Paper+backtest vs backtest-only | Paper needs Phase D | **Replay-only** |
| Channel signal | Close &lt; prior-10 low vs close &lt; ratcheted floor | Spec requires prior-10 excluding *t* | **Strict prior-10 low break** |
| ATR signal | Close &lt; never-loosening floor | Same next-open semantics | **Close &lt; post-update floor** |
| Fill timing | Same-bar touch vs close-signal/next-open | Spec rejects same-bar TP | **Hard stop same-bar; trail/time next-open** |
| Missing next bar | Fail closed vs open-at-end+warn | Matches existing end handling | **`open-at-end` + warning** |
| Dead `_simulate_trade` | Dual-implement vs delete | Drift risk | **Delete in slice 1** |
| CLI selection | Always 10-day-low vs flag | Grid needs ATR cell | **`--exit-policy` backtest-only** |

## State Representation

Extend `_OpenPosition` (drop unused `take_profit` storage on the position):

| Field | Role |
|-------|------|
| `initial_stop` | Hard floor from sizing (`intent.stop`); never changes |
| `effective_floor` | Starts = `initial_stop`; ratchets `max(initial_stop, prior, candidate)` |
| `sessions_held` | Observed symbol sessions with a bar while open (entry day = 1) |
| `pending_exit_reason` | `None` or `trailing-channel` / `atr-trail` / `time-stop` |
| `reached_half_r` | High touched `entry + 0.5R`, `R = entry_price - initial_stop` |
| `printed_new_prior20_high` | Close &gt; max close of prior 20 sessions excluding that session |
| `high_water` | Max high since entry (ATR variant; channel may ignore) |

`ExitPolicyConfig` (frozen): `kind` (`ten-day-low` default \| `atr-3-high-water`), `channel_window=10`, `time_stop_sessions=20`, `half_r=0.5`, `atr_mult=3`, ATR window = existing `ATR_DAYS`.

## Chronological Lifecycle (per day, per open position)

Existing order preserved; ordinary exits become three pure steps:

```
forced-close (app) → settle
  → ordinary on_bar (priority: hard-stop > pending next-open > update/evaluate)
  → entries (hard-stop may fire entry bar; no TP)
  → open-at-end residual
```

**Update (close of session *t*, history ≤ *t* only):**
1. Increment `sessions_held` when symbol has a bar.
2. Progress: `high >= entry + 0.5R` → `reached_half_r`; new prior-20 closing high → flag.
3. Candidate floor: channel = `trailing_low(prior window excluding t)`; ATR = `high_water - 3×ATR(history)`.
4. `effective_floor = max(initial_stop, prior_floor, candidate)`.

**Evaluate signals (no fill today):**
- Channel: `close_t < prior_10_low` (strict; equal does not signal) → pending `trailing-channel`.
- ATR: `close_t < effective_floor` (post-ratchet) → pending `atr-trail`.
- Time (slice 2): after 20th held close, if neither progress flag → pending `time-stop`.
- Missing next session later: materialize `open-at-end` + warning `missing-next-session-after-exit-signal`.

**Priority (deterministic):** (1) context forced-close (app, before ordinary exits) (2) hard stop (3) pending trailing/ATR fill (4) pending time-stop (5) open-at-end. **Per-bar ordinary rule:** (a) if `low <= initial_stop` → stop wins, fill `min(open, initial_stop)`; (b) else if pending → fill next-open (raw open); (c) else update/evaluate (set pending only). Hard stop always beats trailing/time on the same bar.

## Data Flow

```
bars/history (≤ d) ──► exit_policy.update/evaluate ──► pending | stop decision
                              ▲
_OpenPosition state ──────────┘
                              │
BacktestRun ──► SimulatedTrade ──► metrics / report.exit_policy
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/invest/domain/indicators.py` | Modify | Add `trailing_low` (mirror `trailing_high`) |
| `src/invest/domain/exit_policy.py` | Create | Config, state helpers, update/evaluate pure API |
| `src/invest/domain/backtest_metrics.py` | Modify | `ExitReason`: add `trailing-channel`, `time-stop`, `atr-trail`; drop active `take-profit` from contract set |
| `src/invest/application/backtest_run.py` | Modify | Policy state on `_OpenPosition`; replace TP path; inject config; warnings; delete `_simulate_trade` |
| `src/invest/domain/models.py` | Modify | Optional report-facing policy metadata on `BacktestResult` if cleaner than warnings-only |
| `src/invest/adapters/cli.py` | Modify | Slice 3: `--exit-policy`; report `exit_policy` object |
| `tests/domain/test_indicators.py` | Modify | `trailing_low` RED/GREEN |
| `tests/domain/test_exit_policy.py` | Create | Ratchet, channel, ATR, time-stop, priority pure |
| `tests/domain/test_backtest_metrics.py` | Modify | New `ExitReason` set |
| `tests/application/test_backtest_run.py` | Modify | Replace TP cases; next-open, missing-next, priority |
| `tests/adapters/test_cli_backtest.py` | Modify | Policy flag + report metadata |
| `tests/test_boundaries.py` | Modify | Flag backtest-only; absent from execute/day-0 |

## Interfaces / Contracts

```python
# domain/exit_policy.py (sketch)
@dataclass(frozen=True)
class ExitPolicyConfig:
    kind: str  # "ten-day-low" | "atr-3-high-water"
    ...

@dataclass(frozen=True)
class ExitDecision:
    reason: str          # stop | trailing-channel | atr-trail | time-stop
    fill_price: Decimal  # stop: min(open, stop); pending fills use next open in harness

def on_bar(state, bar, history_through_bar, config) -> tuple[state, ExitDecision | None]:
    """Hard-stop same-bar decision OR state+pending update. No I/O/clock."""
```

Report (slice 3): `"exit_policy": {"kind": "...", "channel_window": 10, ...}` sorted JSON. Warning token for missing next session after signal.

## Testing Strategy (strict TDD order)

| Order | Layer | What | Approach |
|------:|-------|------|----------|
| 1 | Unit | `trailing_low` | Hand windows; exclude signal day by caller slice |
| 2 | Unit | Floor ratchet never loosens | Pure state transitions |
| 3 | Unit | Channel equal/strict; ATR floor signal | Synthetic bars |
| 4 | Unit | Time-stop progress suppress | 20 sessions ± half-R / prior-20 high |
| 5 | Unit | Priority: stop &gt; trail &gt; time | Same-bar fixtures |
| 6 | Integration | Next-open fill + slippage path | `BacktestRun.replay` |
| 7 | Integration | Missing next → open-at-end + warning | Tail signal |
| 8 | Contract | `ExitReason` set; paper `take_profit` unchanged | Metrics + execute/broker tests untouched |
| 9 | Boundary | CLI isolation | Parser dest sets |
| 10 | Determinism | Twin runs + no-look-ahead mutate post-N | Existing twin pattern |

RED pure functions → GREEN → then wire `BacktestRun`. No policy logic proven only via huge integration fixtures.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Migration / Rollout — Force-Chained Slices

| Slice | Scope | Authored est. | Rollback boundary |
|------:|-------|---------------|-------------------|
| **1** | `trailing_low` + pure 10-day-low engine + `ExitReason` + `BacktestRun` wiring (ignore TP) + delete `_simulate_trade` + tests | 350–500 | Revert module + replay wiring; restore fixed-TP tests; paper unchanged |
| **2** | Conditional 20-session time stop + pure/integration tests | 150–250 | Revert time-stop fields/eval only; channel path remains |
| **3** | 3-ATR high-water variant + `--exit-policy` + report metadata + boundary tests | 150–300 | Revert ATR branch + CLI flag; default 10-day-low remains |

Delivery: feature-branch chain; each PR autonomous, green tests, ≤800 authored session budget (target ≤400 when feasible). **No Phase-D execution behavior.**

## Open Questions

None blocking — product forks pinned above from accepted proposal/spec.
