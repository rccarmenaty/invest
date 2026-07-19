"""Steps 1+2 of the revised research program (fable-5 plan).

Phase A — forced-close audit (market-context only):
  classify each context-position-forced-closed trade by ContextReason,
  terminal vs transient (coverage-window proxy), blocker-window span,
  IS/OOS segment; aggregate raw P&L per cohort.

Phase B — forced-close revaluation sensitivity (needs bars):
  as-run exit is same-day LOW (already conservative intraday); compare
  total FC P&L valued at same-day open and prior close.

Phase C — signal event study (exit-blind, portfolio-blind):
  every accepted scanner decision via BacktestRun.scan_decisions (no
  position suppression). Forward returns from next-session open at
  +1/5/10/20/60/120 sessions, MFE/MAE over 20 sessions, P(+1R before -1R)
  with 1xATR(14) at signal, by entry year, FC-symbol cohort, signal-day
  safety cohort, date-clustered t-stats, after-cost (10bps round trip),
  and excess vs same-date eligible-universe mean at the 20-session horizon.

Outputs: fixtures/real-continuous/reports/{fc-audit.json,event-study.json}
"""

import json
import math
import sys
import time
from bisect import bisect_left
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from invest.adapters.backtest_context_json import BacktestContextJsonReader
from invest.adapters.fixtures_json import JsonFixtureReader
from invest.application.backtest_run import BacktestRun
from invest.domain.indicators import average_true_range
from invest.domain.momentum_selection_scanner import MomentumSelectionScanner

FIXTURES = Path("/Users/rcty/invest/fixtures/real-continuous")
REPORTS = FIXTURES / "reports"
SPLIT = date(2023, 1, 3)
FC_REASON = "context-position-forced-closed"
HORIZONS = (1, 5, 10, 20, 60, 120)
MFE_MAE_SESSIONS = 20
RACE_SESSIONS = 60
ROUND_TRIP_COST = 0.001  # 5 bps per side
TERMINAL_GRACE_DAYS = 7


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def clustered_t(values: list[float], clusters: list) -> tuple[float, float, int]:
    """Mean, CR0 cluster-robust t (clustered by entry date), n."""
    n = len(values)
    if n < 2:
        return (values[0] if values else float("nan"), float("nan"), n)
    mean = sum(values) / n
    sums: dict = defaultdict(float)
    for v, c in zip(values, clusters):
        sums[c] += v - mean
    se = math.sqrt(sum(s * s for s in sums.values())) / n
    return (mean, mean / se if se > 0 else float("nan"), n)


def summarize(values: list[float], clusters: list) -> dict:
    mean, t, n = clustered_t(values, clusters)
    ordered = sorted(values)
    return {
        "n": n,
        "mean": mean,
        "median": ordered[n // 2] if n else None,
        "hit_rate_gt0": sum(1 for v in values if v > 0) / n if n else None,
        "clustered_t": t,
    }


# ---------------------------------------------------------------- Phase A
log("Phase A: loading market context + uncapped ledger")
context = BacktestContextJsonReader().load(FIXTURES / "market-context.json")
report = json.loads((REPORTS / "backtest-uncapped.json").read_text())
all_trades = report["trades"]
fc_trades = [t for t in all_trades if t["exit_reason"] == FC_REASON]
log(f"forced closes: {len(fc_trades)} of {len(all_trades)} trades")

fc_rows = []
for t in fc_trades:
    sym = t["symbol"]
    exit_d = date.fromisoformat(t["exit_date"])
    entry_d = date.fromisoformat(t["entry_date"])
    raw = (float(t["exit_price"]) - float(t["entry_price"])) * t["qty"]
    status = context.status(sym, exit_d)
    sym_ctx = context.by_symbol[sym]
    coverage_end = max(w.end for w in sym_ctx.coverage)
    blocker = next((w for w in sym_ctx.blockers if w.contains(exit_d)), None)
    fc_rows.append(
        {
            "symbol": sym,
            "entry_date": t["entry_date"],
            "exit_date": t["exit_date"],
            "raw_pnl": raw,
            "hold_days": (exit_d - entry_d).days,
            "reason": status.reason.value if status.reason else "safe?",
            "terminal": (coverage_end - exit_d).days <= TERMINAL_GRACE_DAYS,
            "blocker_span_days": (blocker.end - blocker.start).days + 1 if blocker else None,
            "segment": "oos" if entry_d >= SPLIT else "is",
        }
    )

fc_agg: dict = defaultdict(lambda: {"n": 0, "raw_pnl": 0.0})
for r in fc_rows:
    for key in (
        f"reason={r['reason']}",
        f"terminal={r['terminal']}",
        f"reason={r['reason']}|terminal={r['terminal']}",
        f"segment={r['segment']}",
        f"segment={r['segment']}|terminal={r['terminal']}",
    ):
        fc_agg[key]["n"] += 1
        fc_agg[key]["raw_pnl"] += r["raw_pnl"]
log("Phase A aggregates:")
for key in sorted(fc_agg):
    a = fc_agg[key]
    log(f"  {key}: n={a['n']} raw={a['raw_pnl']:+,.0f}")

# ---------------------------------------------------------------- Phase B
log("Phase B: loading bars (slow, ~minutes)")
inputs = JsonFixtureReader().load(FIXTURES / "bars" / "universe.json", FIXTURES / "bars" / "bars.json")
log(f"bars loaded: {len(inputs.bars)}")

sym_dates: dict[str, list[date]] = {}
sym_open: dict[str, list[float]] = {}
sym_high: dict[str, list[float]] = {}
sym_low: dict[str, list[float]] = {}
sym_close: dict[str, list[float]] = {}
_grouped: dict[str, list] = defaultdict(list)
for bar in inputs.bars:
    _grouped[bar.symbol].append(bar)
for sym, bars in _grouped.items():
    bars.sort(key=lambda b: b.date)
    sym_dates[sym] = [b.date for b in bars]
    sym_open[sym] = [float(b.open) for b in bars]
    sym_high[sym] = [float(b.high) for b in bars]
    sym_low[sym] = [float(b.low) for b in bars]
    sym_close[sym] = [float(b.close) for b in bars]
log("per-symbol arrays built")

reval = {"as_run_low": 0.0, "same_day_open": 0.0, "prior_close": 0.0, "n": 0, "skipped": 0}
for r in fc_rows:
    sym = r["symbol"]
    exit_d = date.fromisoformat(r["exit_date"])
    dates = sym_dates.get(sym, [])
    i = bisect_left(dates, exit_d)
    if i >= len(dates) or dates[i] != exit_d or i == 0:
        reval["skipped"] += 1
        continue
    trade = next(
        t for t in fc_trades if t["symbol"] == sym and t["exit_date"] == r["exit_date"] and t["entry_date"] == r["entry_date"]
    )
    entry_price, qty = float(trade["entry_price"]), trade["qty"]
    reval["n"] += 1
    reval["as_run_low"] += (sym_low[sym][i] - entry_price) * qty
    reval["same_day_open"] += (sym_open[sym][i] - entry_price) * qty
    reval["prior_close"] += (sym_close[sym][i - 1] - entry_price) * qty
log(f"Phase B revaluation: {reval}")

(REPORTS / "fc-audit.json").write_text(
    json.dumps(
        {
            "experiment": "forced-close-audit",
            "n_forced_closes": len(fc_rows),
            "aggregates": {k: v for k, v in sorted(fc_agg.items())},
            "revaluation_totals": reval,
            "terminal_grace_days": TERMINAL_GRACE_DAYS,
            "rows": fc_rows,
        },
        indent=1,
        sort_keys=True,
    )
)
log("fc-audit.json written")

# ---------------------------------------------------------------- Phase C
log("Phase C: collecting position-blind signals (slow, ~45 min)")
run = BacktestRun(market_context=context, scanner=MomentumSelectionScanner())
decisions = run.scan_decisions(inputs)
log(f"accepted signals: {len(decisions)}")

fc_symbols = {r["symbol"] for r in fc_rows}
signals = []
for d in decisions:
    sym = d.symbol
    dates = sym_dates[sym]
    i = bisect_left(dates, d.decision_date)
    if i >= len(dates) or dates[i] != d.decision_date:
        continue
    entry_i = i + 1
    if entry_i >= len(dates):
        continue
    entry = sym_open[sym][entry_i]
    if entry <= 0:
        continue
    history = _grouped[sym][: i + 1]
    atr = float(average_true_range(history))
    try:
        safe = context.status(sym, d.decision_date).is_safe
    except Exception:
        safe = None

    rets = {}
    for h in HORIZONS:
        j = entry_i + h
        rets[h] = sym_close[sym][j] / entry - 1 if j < len(dates) else None

    end_m = min(entry_i + MFE_MAE_SESSIONS, len(dates) - 1)
    mfe = max(sym_high[sym][entry_i : end_m + 1]) / entry - 1
    mae = min(sym_low[sym][entry_i : end_m + 1]) / entry - 1

    race = "neither"
    up_level, dn_level = entry + atr, entry - atr
    if atr > 0:
        for j in range(entry_i, min(entry_i + RACE_SESSIONS, len(dates) - 1) + 1):
            hit_up = sym_high[sym][j] >= up_level
            hit_dn = sym_low[sym][j] <= dn_level
            if hit_up and hit_dn:
                race = "ambiguous"
                break
            if hit_up:
                race = "up_first"
                break
            if hit_dn:
                race = "down_first"
                break
    else:
        race = "no_atr"

    signals.append(
        {
            "symbol": sym,
            "decision_date": d.decision_date,
            "entry_date": dates[entry_i],
            "rets": rets,
            "mfe": mfe,
            "mae": mae,
            "race": race,
            "safe": safe,
            "fc_symbol": sym in fc_symbols,
        }
    )
log(f"signals with entries: {len(signals)}")

# same-date eligible-universe baseline at 20 sessions
log("computing universe baseline (20-session horizon)")
uni_base: dict[date, float] = {}
for dd in sorted({s["decision_date"] for s in signals}):
    vals = []
    for sym in context.eligible_symbols(inputs.universe.symbols, dd):
        dates = sym_dates.get(sym)
        if not dates:
            continue
        i = bisect_left(dates, dd)
        if i >= len(dates) or dates[i] != dd:
            continue
        entry_i, j = i + 1, i + 1 + 20
        if j < len(dates) and sym_open[sym][entry_i] > 0:
            vals.append(sym_close[sym][j] / sym_open[sym][entry_i] - 1)
    if vals:
        uni_base[dd] = sum(vals) / len(vals)
log(f"baseline dates: {len(uni_base)}")

out: dict = {"experiment": "signal-event-study", "n_signals": len(signals), "horizons": {}}
for h in HORIZONS:
    rows = [(s["rets"][h], s["decision_date"]) for s in signals if s["rets"][h] is not None]
    vals = [r[0] for r in rows]
    cl = [r[1].isoformat() for r in rows]
    stats = summarize(vals, cl)
    stats["mean_after_cost"] = stats["mean"] - ROUND_TRIP_COST if stats["n"] else None
    out["horizons"][h] = stats

h20 = [s for s in signals if s["rets"][20] is not None]
out["by_year_h20"] = {
    y: summarize(
        [s["rets"][20] for s in h20 if s["entry_date"].year == y],
        [s["decision_date"].isoformat() for s in h20 if s["entry_date"].year == y],
    )
    for y in sorted({s["entry_date"].year for s in h20})
}
out["cohorts_h20"] = {
    "fc_symbols": summarize(
        [s["rets"][20] for s in h20 if s["fc_symbol"]],
        [s["decision_date"].isoformat() for s in h20 if s["fc_symbol"]],
    ),
    "non_fc_symbols": summarize(
        [s["rets"][20] for s in h20 if not s["fc_symbol"]],
        [s["decision_date"].isoformat() for s in h20 if not s["fc_symbol"]],
    ),
    "signal_day_safe": summarize(
        [s["rets"][20] for s in h20 if s["safe"] is True],
        [s["decision_date"].isoformat() for s in h20 if s["safe"] is True],
    ),
    "signal_day_blocked": summarize(
        [s["rets"][20] for s in h20 if s["safe"] is False],
        [s["decision_date"].isoformat() for s in h20 if s["safe"] is False],
    ),
}
excess_rows = [
    (s["rets"][20] - uni_base[s["decision_date"]], s["decision_date"])
    for s in h20
    if s["decision_date"] in uni_base
]
out["excess_vs_universe_h20"] = summarize([r[0] for r in excess_rows], [r[1].isoformat() for r in excess_rows])
out["mfe_mae_20s"] = {
    "mean_mfe": sum(s["mfe"] for s in signals) / len(signals),
    "mean_mae": sum(s["mae"] for s in signals) / len(signals),
    "median_mfe": sorted(s["mfe"] for s in signals)[len(signals) // 2],
    "median_mae": sorted(s["mae"] for s in signals)[len(signals) // 2],
}
race_counts: dict = defaultdict(int)
for s in signals:
    race_counts[s["race"]] += 1
resolved = race_counts["up_first"] + race_counts["down_first"]
out["race_1atr"] = {
    "counts": dict(race_counts),
    "p_up_first_resolved": race_counts["up_first"] / resolved if resolved else None,
    "race_window_sessions": RACE_SESSIONS,
}
out["cost_assumption_round_trip"] = ROUND_TRIP_COST

(REPORTS / "event-study.json").write_text(json.dumps(out, indent=1, sort_keys=True))
log("event-study.json written")
print(json.dumps({k: v for k, v in out.items() if k != "horizons"} | {"horizons": out["horizons"]}, indent=1, sort_keys=True, default=str))
