"""Gate 1a measurement: h60 (primary) and h120 excess vs same-date universe.

Extends Step 2 event study with the missing beta-separation at long horizons.
Does NOT re-audit forced closes; only needs FC symbol set for cohort splits.

Outputs: fixtures/real-continuous/reports/gate1a-excess.json

Primary gate (meta-judge):
  h60 excess mean > 0 AND date-clustered t >= 2.5 → Gate 1a PASS
"""

from __future__ import annotations

import json
import sys
import time
from bisect import bisect_left
from collections import defaultdict
from datetime import date
from pathlib import Path

from invest.adapters.backtest_context_json import BacktestContextJsonReader
from invest.adapters.fixtures_json import JsonFixtureReader
from invest.application.backtest_run import BacktestRun
from invest.application.event_study_excess import (
    SymbolBarSeries,
    bucket_by_score_quintiles,
    evaluate_gate_1a,
    excess_return,
    formation_daily_returns,
    forward_session_return,
    high_proximity_52w,
    information_discreteness,
    summarize,
    universe_mean_forward_return,
)
from invest.domain.momentum_selection_scanner import MomentumSelectionScanner

FIXTURES = Path(__file__).resolve().parents[1]
REPORTS = Path(__file__).resolve().parent
FC_REASON = "context-position-forced-closed"
EXCESS_HORIZONS = (20, 60, 120)  # 20 = regression check vs event-study.json
PRIMARY_HORIZON = 60
MIN_T = 2.5
ID_LOOKBACK = 60
PROX_WINDOW = 252


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def main() -> None:
    log("loading market context")
    context = BacktestContextJsonReader().load(FIXTURES / "market-context.json")

    fc_symbols: set[str] = set()
    uncapped_path = REPORTS / "backtest-uncapped.json"
    if uncapped_path.exists():
        trades = json.loads(uncapped_path.read_text())["trades"]
        fc_symbols = {t["symbol"] for t in trades if t["exit_reason"] == FC_REASON}
        log(f"FC cohort symbols: {len(fc_symbols)}")
    else:
        log("backtest-uncapped.json missing — FC cohort split empty")

    log("loading bars (slow)")
    inputs = JsonFixtureReader().load(
        FIXTURES / "bars" / "universe.json", FIXTURES / "bars" / "bars.json"
    )
    log(f"bars loaded: {len(inputs.bars)}")

    series_by_symbol: dict[str, SymbolBarSeries] = {}
    closes_by_symbol: dict[str, list[float]] = {}
    dates_by_symbol: dict[str, list[date]] = {}
    _grouped: dict[str, list] = defaultdict(list)
    for bar in inputs.bars:
        _grouped[bar.symbol].append(bar)
    for sym, bars in _grouped.items():
        bars.sort(key=lambda b: b.date)
        dates = [b.date for b in bars]
        opens = [float(b.open) for b in bars]
        closes = [float(b.close) for b in bars]
        dates_by_symbol[sym] = dates
        closes_by_symbol[sym] = closes
        series_by_symbol[sym] = SymbolBarSeries(dates=dates, opens=opens, closes=closes)
    log(f"per-symbol series: {len(series_by_symbol)}")

    log("collecting position-blind signals (slow, tens of minutes)")
    run = BacktestRun(market_context=context, scanner=MomentumSelectionScanner())
    decisions = run.scan_decisions(inputs)
    log(f"accepted signals: {len(decisions)}")

    signals: list[dict] = []
    for d in decisions:
        sym = d.symbol
        series = series_by_symbol.get(sym)
        if series is None:
            continue
        i = bisect_left(series.dates, d.decision_date)
        if i >= len(series.dates) or series.dates[i] != d.decision_date:
            continue
        rets: dict[int, float | None] = {}
        for h in EXCESS_HORIZONS:
            rets[h] = forward_session_return(
                opens=series.opens,
                closes=series.closes,
                dates=series.dates,
                decision_date=d.decision_date,
                horizon=h,
            )
        if all(rets[h] is None for h in EXCESS_HORIZONS):
            continue
        form = formation_daily_returns(
            closes_by_symbol[sym], decision_index=i, lookback=ID_LOOKBACK
        )
        id_score = information_discreteness(form) if form is not None else None
        prox = high_proximity_52w(
            closes_by_symbol[sym], decision_index=i, window=PROX_WINDOW
        )
        signals.append(
            {
                "symbol": sym,
                "decision_date": d.decision_date,
                "entry_year": series.dates[i + 1].year
                if i + 1 < len(series.dates)
                else d.decision_date.year,
                "rets": rets,
                "fc_symbol": sym in fc_symbols,
                "id": id_score,
                "prox_52w": prox,
            }
        )
    log(f"signals with any horizon: {len(signals)}")

    decision_dates = sorted({s["decision_date"] for s in signals})
    uni_base: dict[int, dict[date, float]] = {h: {} for h in EXCESS_HORIZONS}
    log(f"universe baselines for {len(decision_dates)} dates × {len(EXCESS_HORIZONS)} horizons")
    for di, dd in enumerate(decision_dates, start=1):
        eligible = context.eligible_symbols(inputs.universe.symbols, dd)
        for h in EXCESS_HORIZONS:
            mean = universe_mean_forward_return(
                series_by_symbol, eligible=eligible, decision_date=dd, horizon=h
            )
            if mean is not None:
                uni_base[h][dd] = mean
        if di % 200 == 0 or di == len(decision_dates):
            log(f"  baseline progress {di}/{len(decision_dates)}")

    out: dict = {
        "experiment": "gate1a-excess-vs-universe",
        "n_signals": len(signals),
        "primary_horizon": PRIMARY_HORIZON,
        "min_clustered_t": MIN_T,
        "cost_note": "excess is pre-cost; costs applied only in portfolio phases",
        "horizons": {},
    }

    for h in EXCESS_HORIZONS:
        vals: list[float] = []
        clusters: list[str] = []
        by_year: dict[int, list[tuple[float, str]]] = defaultdict(list)
        fc_vals: list[float] = []
        fc_cl: list[str] = []
        non_fc_vals: list[float] = []
        non_fc_cl: list[str] = []
        id_pairs: list[tuple[float, float, str]] = []  # id, excess, cluster
        prox_pairs: list[tuple[float, float, str]] = []

        for s in signals:
            ret = s["rets"][h]
            dd = s["decision_date"]
            if ret is None or dd not in uni_base[h]:
                continue
            ex = excess_return(ret, uni_base[h][dd])
            cl = dd.isoformat()
            vals.append(ex)
            clusters.append(cl)
            by_year[s["entry_year"]].append((ex, cl))
            if s["fc_symbol"]:
                fc_vals.append(ex)
                fc_cl.append(cl)
            else:
                non_fc_vals.append(ex)
                non_fc_cl.append(cl)
            if s["id"] is not None:
                id_pairs.append((s["id"], ex, cl))
            if s["prox_52w"] is not None:
                prox_pairs.append((s["prox_52w"], ex, cl))

        full = summarize(vals, clusters)
        section: dict = {
            "excess_vs_universe": full.to_dict(),
            "n_universe_dates": len(uni_base[h]),
            "by_year": {
                str(y): summarize([p[0] for p in rows], [p[1] for p in rows]).to_dict()
                for y, rows in sorted(by_year.items())
            },
            "cohorts": {
                "fc_symbols": summarize(fc_vals, fc_cl).to_dict(),
                "non_fc_symbols": summarize(non_fc_vals, non_fc_cl).to_dict(),
            },
            "survivorship_note": (
                "full-window only; missing terminal bars drop the observation"
                if h >= 120
                else None
            ),
        }

        if id_pairs:
            buckets = bucket_by_score_quintiles(id_pairs)
            section["id_quintiles"] = {
                str(q): {
                    **summarize([p[0] for p in rows], [p[1] for p in rows]).to_dict(),
                    "note": "q1=lowest ID (smoothest); q5=highest ID (most discrete)",
                }
                for q, rows in sorted(buckets.items())
            }
            # monotone check: q1 mean excess - q5 mean excess (lower ID better)
            if 1 in buckets and 5 in buckets:
                q1 = summarize([p[0] for p in buckets[1]], [p[1] for p in buckets[1]])
                q5 = summarize([p[0] for p in buckets[5]], [p[1] for p in buckets[5]])
                spread = q1.mean - q5.mean
                section["id_top_minus_bottom_mean"] = spread
                section["id_monotone_direction"] = (
                    "smooth_better" if spread > 0 else "discrete_better_or_flat"
                )

        if prox_pairs:
            buckets = bucket_by_score_quintiles(prox_pairs)
            section["prox52w_quintiles"] = {
                str(q): summarize([p[0] for p in rows], [p[1] for p in rows]).to_dict()
                for q, rows in sorted(buckets.items())
            }

        if h == PRIMARY_HORIZON:
            gate = evaluate_gate_1a(full, min_t=MIN_T, horizon=PRIMARY_HORIZON)
            section["gate_1a"] = gate.to_dict()
            out["gate_1a"] = gate.to_dict()

        out["horizons"][str(h)] = section
        log(
            f"h{h} excess: n={full.n} mean={full.mean:+.4%} t={full.clustered_t:.3f} "
            f"hit={full.hit_rate_gt0}"
        )

    path = REPORTS / "gate1a-excess.json"
    path.write_text(json.dumps(out, indent=1, sort_keys=True))
    log(f"wrote {path}")
    gate = out.get("gate_1a", {})
    print(
        json.dumps(
            {
                "gate_1a": gate,
                "h60_excess": out["horizons"].get("60", {}).get("excess_vs_universe"),
                "h20_excess": out["horizons"].get("20", {}).get("excess_vs_universe"),
                "h120_excess": out["horizons"].get("120", {}).get("excess_vs_universe"),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
