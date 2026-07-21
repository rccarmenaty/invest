"""CMFT Stage A research driver (#74).

Sequential measurement path for conditional momentum family trial.

Modes:
  default / --continuous — load real-continuous bars (multi-GB, sequential);
                           measure C1 + G0-data + K0 + placebo; T1/C2 only if
                           K0 passes and research-ml is installed
  --synthetic            — tiny in-memory panel smoke (no multi-GB, no LightGBM)
  unmeasured fallback    — bars missing → fail-closed (no invented spreads)

Does NOT:
  - touch residual / R2-1
  - import production scan/backtest
  - set capital_go true
  - load SF1/SF2/SF3 or HMM

Outputs:
  fixtures/real-continuous/reports/cmft-structure.json
  docs/research/cmft-results.md (when --write-docs)

Parent PRD: #74

Honesty:
  - 2019–2025 continuous fixture is the available local panel. Full-depth SEP
    (~1998+) is the PRD primary span when a deeper entitled pull is available;
    if K0 fails here, that is underpowered-stop — not a fabricated kill/pass.
  - T1/C2 unmeasured → G5/VI/DSR fail closed (honest).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from invest.adapters.fixtures_json import JsonFixtureReader
from invest.application.cmft import (
    PROTOCOL,
    assign_deciles,
    build_cmft_artifact,
    cost_net_spread,
    decile_mean_monotone_increasing,
    demean_cross_section,
    evaluate_cmft_gates,
    forward_open_to_open_return,
    min_detectable_spread,
    mom_12_1_return,
    month_end_formation_dates,
    top_minus_bottom_spread,
    year_month_profit_shares,
)
from invest.application.event_study_excess import summarize

FIXTURES = Path(__file__).resolve().parents[1]
REPORTS = Path(__file__).resolve().parent
OUT_PATH = REPORTS / "cmft-structure.json"
LOG_PATH = REPORTS / "cmft-run.log"
DOCS_PATH = Path(__file__).resolve().parents[3] / "docs" / "research" / "cmft-results.md"

ADV_WINDOW = 20


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, file=sys.stderr, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _render_markdown(artifact: dict) -> str:
    gates = artifact.get("gates", [])
    gate_lines = [
        f"- **{g['id']}** [{g['severity']}] "
        f"{'PASS' if g['passed'] else 'FAIL'} — {g['reason']}"
        for g in gates
    ]
    fold = artifact.get("fold_table") or []
    fold_lines = [
        f"- {row.get('year')}: n={row.get('n')} mean={row.get('mean')}"
        for row in fold
    ] or ["- (empty)"]
    return "\n".join(
        [
            "# CMFT Stage A results",
            "",
            f"**Date:** {time.strftime('%Y-%m-%d')}",
            f"**Driver:** `fixtures/real-continuous/reports/research_cmft.py`",
            f"**Artifact:** `fixtures/real-continuous/reports/cmft-structure.json`",
            f"**Parent PRD:** #74",
            "",
            "## Verdict",
            "",
            f"### **{artifact.get('verdict')}**",
            "",
            f"- implementability_eligible: `{artifact.get('implementability_eligible')}`",
            f"- capital_go: `{artifact.get('capital_go')}` (always false)",
            f"- residual freeze untouched: `{artifact.get('residual_freeze_untouched')}`",
            f"- R2-1 kill_line untouched: `{artifact.get('r21_kill_line_untouched')}`",
            f"- SF* features included: `{artifact.get('sf_features_included')}`",
            f"- HMM included: `{artifact.get('hmm_included')}`",
            "",
            "## C1 diagnostics",
            "",
            f"- n_formations: `{artifact.get('c1_n_formations')}`",
            f"- c1_mean_gross: `{artifact.get('c1_mean_gross')}`",
            f"- c1_mean_net_10bps: `{artifact.get('c1_mean_net_10bps')}`",
            f"- c1_median_gross: `{artifact.get('c1_median_gross')}`",
            f"- k0_mds_bps: `{artifact.get('k0_mds_bps')}`",
            f"- g0_years_monotone/total: "
            f"`{artifact.get('g0_years_monotone')}/{artifact.get('g0_years_total')}`",
            f"- placebo |t|: `{artifact.get('placebo_t_abs')}`",
            "",
            "## Annual fold table (C1 gross spreads)",
            "",
            *fold_lines,
            "",
            "## Gates",
            "",
            *gate_lines,
            "",
            "## Mode notes",
            "",
            f"- mode: `{artifact.get('mode', 'unknown')}`",
            f"- note: {artifact.get('mode_note', '')}",
            f"- t1_status: `{artifact.get('t1_status', 'not_run')}`",
            "",
            "## How to re-run",
            "",
            "```bash",
            "# Continuous fixture panel (sequential multi-GB; alone on 16GB host)",
            "uv run python fixtures/real-continuous/reports/research_cmft.py --write-docs",
            "",
            "# Synthetic harness smoke (no LightGBM, no multi-GB)",
            "uv run python fixtures/real-continuous/reports/research_cmft.py --synthetic --write-docs",
            "```",
            "",
        ]
    )


def _fail_closed_unmeasured(mode: str, mode_note: str) -> dict:
    """Honest path when continuous SEP panel is not measured in this process."""
    report = evaluate_cmft_gates(
        g0_data_years_monotone=None,
        g0_data_years_total=None,
        k0_n_formations=None,
        k0_spread_vol=None,
        g0_placebo_t_abs=0.0,
        spread_stats=summarize([], []),
        positive_annual_folds=0,
        total_annual_folds=0,
        max_year_share=1.0,
        max_month_share=1.0,
        mean_net_10bps=float("nan"),
        mean_net_5bps=float("nan"),
        t1_mean_net=float("nan"),
        t1_median_net=float("nan"),
        c1_mean_net=float("nan"),
        c1_median_net=float("nan"),
        vi_price_trend_share=None,
        vi_noise_in_top10=None,
        vi_short_horizon_share=None,
        deflated_sharpe=None,
        deflated_sharpe_measured=False,
    )
    art = build_cmft_artifact(report, fold_table=[])
    art["mode"] = mode
    art["mode_note"] = mode_note
    art["t1_status"] = "not_run"
    return art


def _median(xs: list[float]) -> float:
    ordered = sorted(xs)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _trailing_median_adv(
    closes: list[float], volumes: list[float], *, end_index: int, window: int = ADV_WINDOW
) -> float | None:
    if end_index < 0 or end_index >= len(closes) or end_index >= len(volumes):
        return None
    start = end_index - window + 1
    if start < 0:
        return None
    dvs: list[float] = []
    for i in range(start, end_index + 1):
        c, v = closes[i], volumes[i]
        if c <= 0 or v < 0:
            return None
        dvs.append(c * v)
    return _median(dvs)


def _is_liquid(*, price: float, median_adv: float) -> bool:
    return price >= PROTOCOL.primary_min_price and median_adv >= PROTOCOL.primary_min_adv


def _synthetic_sessions(n_days: int = 800) -> list[date]:
    """Weekday calendar starting 2018-01-02 (smoke only)."""
    d = date(2018, 1, 2)
    out: list[date] = []
    while len(out) < n_days:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _build_artifact_from_c1(
    *,
    spread_by_date: list[tuple[date, float]],
    means_by_year_decile: dict[int, dict[int, list[float]]],
    placebo_t_abs: float,
    mode: str,
    mode_note: str,
    t1_status: str,
    t1_mean_net: float = float("nan"),
    t1_median_net: float = float("nan"),
    vi_price_trend_share: float | None = None,
    vi_noise_in_top10: bool | None = None,
    vi_short_horizon_share: float | None = None,
    deflated_sharpe: float | None = None,
    deflated_sharpe_measured: bool = False,
) -> dict:
    years_total = 0
    years_monotone = 0
    for _year, by_d in sorted(means_by_year_decile.items()):
        mean_map = {d: sum(v) / len(v) for d, v in by_d.items() if v}
        if len(mean_map) < 5:
            continue
        years_total += 1
        if decile_mean_monotone_increasing(mean_map):
            years_monotone += 1

    spreads = [s for _, s in spread_by_date]
    clusters = [d for d, _ in spread_by_date]
    if spreads:
        stats = summarize(spreads, clusters)
        spread_vol = float(
            (sum((x - stats.mean) ** 2 for x in spreads) / max(len(spreads) - 1, 1))
            ** 0.5
        )
    else:
        stats = summarize([], [])
        spread_vol = float("nan")

    n_form = len(spreads)
    shares = year_month_profit_shares(spread_by_date)
    mean_net_10 = (
        cost_net_spread(stats.mean, bps_per_side=10.0)
        if spreads and math.isfinite(stats.mean)
        else float("nan")
    )
    mean_net_5 = (
        cost_net_spread(stats.mean, bps_per_side=5.0)
        if spreads and math.isfinite(stats.mean)
        else float("nan")
    )
    c1_median_net = (
        cost_net_spread(stats.median, bps_per_side=10.0)
        if stats.median is not None and math.isfinite(stats.median)
        else float("nan")
    )

    by_year_spread: dict[int, list[float]] = defaultdict(list)
    for d, s in spread_by_date:
        by_year_spread[d.year].append(s)
    pos = sum(1 for vals in by_year_spread.values() if sum(vals) / len(vals) > 0)
    total_y = len(by_year_spread)

    mds_bps = (
        min_detectable_spread(n_formations=n_form, spread_vol=spread_vol) * 10_000.0
        if n_form and math.isfinite(spread_vol)
        else float("nan")
    )

    report = evaluate_cmft_gates(
        g0_data_years_monotone=years_monotone if years_total else None,
        g0_data_years_total=years_total if years_total else None,
        k0_n_formations=n_form if n_form else None,
        k0_spread_vol=spread_vol if n_form and math.isfinite(spread_vol) else None,
        g0_placebo_t_abs=placebo_t_abs,
        spread_stats=stats,
        positive_annual_folds=pos,
        total_annual_folds=total_y,
        max_year_share=shares["max_year_share"],
        max_month_share=shares["max_month_share"],
        mean_net_10bps=mean_net_10,
        mean_net_5bps=mean_net_5,
        t1_mean_net=t1_mean_net,
        t1_median_net=t1_median_net,
        c1_mean_net=mean_net_10 if math.isfinite(mean_net_10) else float("nan"),
        c1_median_net=c1_median_net,
        vi_price_trend_share=vi_price_trend_share,
        vi_noise_in_top10=vi_noise_in_top10,
        vi_short_horizon_share=vi_short_horizon_share,
        deflated_sharpe=deflated_sharpe,
        deflated_sharpe_measured=deflated_sharpe_measured,
    )

    fold_table = [
        {
            "year": y,
            "n": len(vals),
            "mean": sum(vals) / len(vals),
        }
        for y, vals in sorted(by_year_spread.items())
    ]
    art = build_cmft_artifact(report, fold_table=fold_table)
    art["mode"] = mode
    art["mode_note"] = mode_note
    art["t1_status"] = t1_status
    art["c1_n_formations"] = n_form
    art["c1_mean_gross"] = stats.mean if spreads else None
    art["c1_median_gross"] = stats.median if spreads else None
    art["c1_mean_net_10bps"] = mean_net_10 if math.isfinite(mean_net_10) else None
    art["c1_clustered_t"] = stats.clustered_t if spreads else None
    art["k0_mds_bps"] = mds_bps if math.isfinite(mds_bps) else None
    art["g0_years_monotone"] = years_monotone if years_total else None
    art["g0_years_total"] = years_total if years_total else None
    art["placebo_t_abs"] = placebo_t_abs
    return art


def run_synthetic(seed: int = 42) -> dict:
    """Build a tiny multi-name panel and measure C1 + G0-data + K0 only.

    T1/C2/VI remain unmeasured → fail closed on those gates (honest).
    """
    rng = random.Random(seed)
    sessions = _synthetic_sessions(900)
    formations = month_end_formation_dates(sessions)
    session_index = {d: i for i, d in enumerate(sessions)}

    n_names = 40
    closes: dict[str, list[float]] = {}
    opens: dict[str, list[float]] = {}
    for i in range(n_names):
        px = 20.0 + rng.random() * 30.0
        c_list: list[float] = []
        o_list: list[float] = []
        for _ in sessions:
            o = px
            px = max(1.0, px * (1.0 + rng.gauss(0.0005, 0.02)))
            o_list.append(o)
            c_list.append(px)
        closes[f"S{i:02d}"] = c_list
        opens[f"S{i:02d}"] = o_list

    spread_by_date: list[tuple[date, float]] = []
    means_by_year_decile: dict[int, dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    placebo_spreads: list[float] = []
    placebo_clusters: list[date] = []

    for fdate in formations:
        fi = session_index[fdate]
        if fi < PROTOCOL.mom_far_sessions:
            continue
        scores: list[float] = []
        labels: list[float] = []
        for name, c_list in closes.items():
            mom = mom_12_1_return(c_list, formation_index=fi)
            fwd = forward_open_to_open_return(opens[name], formation_index=fi)
            if mom is None or fwd is None:
                continue
            scores.append(mom)
            labels.append(fwd)
        if len(scores) < PROTOCOL.deciles * 2:
            continue
        labels_dm = demean_cross_section(labels)
        deciles = assign_deciles(scores)
        d1 = [labels_dm[i] for i, d in enumerate(deciles) if d == 1]
        d10 = [labels_dm[i] for i, d in enumerate(deciles) if d == 10]
        spread = top_minus_bottom_spread(d1, d10)
        if spread is None:
            continue
        spread_by_date.append((fdate, spread))
        for i, d in enumerate(deciles):
            means_by_year_decile[fdate.year][d].append(labels_dm[i])

        # Placebo: shuffle scores vs fixed labels
        shuffled = scores[:]
        rng.shuffle(shuffled)
        p_dec = assign_deciles(shuffled)
        p_d1 = [labels_dm[i] for i, d in enumerate(p_dec) if d == 1]
        p_d10 = [labels_dm[i] for i, d in enumerate(p_dec) if d == 10]
        p_spread = top_minus_bottom_spread(p_d1, p_d10)
        if p_spread is not None:
            placebo_spreads.append(p_spread)
            placebo_clusters.append(fdate)

    placebo_t = 0.1
    if placebo_spreads:
        p_stats = summarize(placebo_spreads, placebo_clusters)
        if math.isfinite(p_stats.clustered_t):
            placebo_t = abs(p_stats.clustered_t)

    return _build_artifact_from_c1(
        spread_by_date=spread_by_date,
        means_by_year_decile=means_by_year_decile,
        placebo_t_abs=placebo_t,
        mode="synthetic",
        mode_note=(
            "Synthetic smoke only: C1 + G0-data + K0 measured; "
            "T1/C2/VI/DSR unmeasured fail-closed. Not a capital or continuous claim."
        ),
        t1_status="not_run",
    )


def run_continuous(*, max_formations: int = 0, seed: int = 42) -> dict:
    """Measure C1 / G0-data / K0 / placebo on real-continuous bars.

    T1/C2 run only if K0 passes and ``research-ml`` (LightGBM) is importable.
    """
    universe_path = FIXTURES / "bars" / "universe.json"
    bars_path = FIXTURES / "bars" / "bars.json"
    if not universe_path.exists() or not bars_path.exists():
        return _fail_closed_unmeasured(
            mode="continuous-missing-fixture",
            mode_note=(
                f"Missing continuous bars at {bars_path}. "
                "Publish fail-closed; do not invent spreads."
            ),
        )

    log("loading bars (sequential multi-GB — alone on 16GB host)")
    inputs = JsonFixtureReader().load(universe_path, bars_path)
    log(f"bars loaded: {len(inputs.bars)}")

    by_sym: dict[str, list] = defaultdict(list)
    for bar in inputs.bars:
        by_sym[bar.symbol].append(bar)

    series: dict[str, dict] = {}
    session_set: set[date] = set()
    for sym, bars in by_sym.items():
        bars.sort(key=lambda b: b.date)
        dates = [b.date for b in bars]
        opens = [float(b.open) for b in bars]
        closes = [float(b.close) for b in bars]
        volumes = [float(b.volume) for b in bars]
        series[sym] = {
            "dates": dates,
            "opens": opens,
            "closes": closes,
            "volumes": volumes,
            "date_to_i": {d: i for i, d in enumerate(dates)},
        }
        session_set.update(dates)

    # Free the full bar payload; keep only per-symbol arrays.
    del inputs
    del by_sym

    calendar = sorted(session_set)
    formations = month_end_formation_dates(calendar)
    if max_formations > 0:
        formations = formations[:max_formations]
        log(f"DEBUG max-formations={max_formations}")
    log(f"month-end formations: {len(formations)}; symbols: {len(series)}")

    rng = random.Random(seed)
    spread_by_date: list[tuple[date, float]] = []
    means_by_year_decile: dict[int, dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    placebo_spreads: list[float] = []
    placebo_clusters: list[date] = []
    # Keep per-formation CS rows for optional T1 (only if K0 passes).
    formation_rows: list[dict] = []

    for fi, fdate in enumerate(formations):
        if fi % 12 == 0:
            log(f"formation {fi}/{len(formations)} {fdate}")
        scores: list[float] = []
        labels: list[float] = []
        symbols_kept: list[str] = []
        for sym, s in series.items():
            idx = s["date_to_i"].get(fdate)
            if idx is None:
                continue
            if idx < PROTOCOL.mom_far_sessions:
                continue
            px = s["closes"][idx]
            adv = _trailing_median_adv(s["closes"], s["volumes"], end_index=idx)
            if adv is None or not _is_liquid(price=px, median_adv=adv):
                continue
            mom = mom_12_1_return(s["closes"], formation_index=idx)
            fwd = forward_open_to_open_return(s["opens"], formation_index=idx)
            if mom is None or fwd is None:
                continue
            scores.append(mom)
            labels.append(fwd)
            symbols_kept.append(sym)

        if len(scores) < PROTOCOL.deciles * 2:
            continue

        labels_dm = demean_cross_section(labels)
        deciles = assign_deciles(scores)
        d1 = [labels_dm[i] for i, d in enumerate(deciles) if d == 1]
        d10 = [labels_dm[i] for i, d in enumerate(deciles) if d == 10]
        spread = top_minus_bottom_spread(d1, d10)
        if spread is None:
            continue
        spread_by_date.append((fdate, spread))
        for i, d in enumerate(deciles):
            means_by_year_decile[fdate.year][d].append(labels_dm[i])

        shuffled = scores[:]
        rng.shuffle(shuffled)
        p_dec = assign_deciles(shuffled)
        p_d1 = [labels_dm[i] for i, d in enumerate(p_dec) if d == 1]
        p_d10 = [labels_dm[i] for i, d in enumerate(p_dec) if d == 10]
        p_spread = top_minus_bottom_spread(p_d1, p_d10)
        if p_spread is not None:
            placebo_spreads.append(p_spread)
            placebo_clusters.append(fdate)

        formation_rows.append(
            {
                "date": fdate,
                "scores": scores,
                "labels_dm": labels_dm,
                "symbols": symbols_kept,
            }
        )

    log(f"completed formations with C1 spread: {len(spread_by_date)}")

    placebo_t = 0.0
    if placebo_spreads:
        p_stats = summarize(placebo_spreads, placebo_clusters)
        if math.isfinite(p_stats.clustered_t):
            placebo_t = abs(float(p_stats.clustered_t))

    # Provisional artifact to read K0 before deciding on T1.
    provisional = _build_artifact_from_c1(
        spread_by_date=spread_by_date,
        means_by_year_decile=means_by_year_decile,
        placebo_t_abs=placebo_t,
        mode="continuous-fixture",
        mode_note=(
            "Continuous 2019–2025 fixture panel: C1 + G0-data + K0 + placebo measured. "
            "Not full-depth SEP (~1998+). T1/C2 only if K0 passes and research-ml present."
        ),
        t1_status="not_run",
    )

    k0_passed = any(
        g["id"] == "K0-power" and g["passed"] for g in provisional.get("gates", [])
    )
    log(f"K0 passed={k0_passed}; verdict provisional={provisional.get('verdict')}")

    if not k0_passed:
        provisional["mode_note"] = (
            provisional["mode_note"]
            + " K0 failed → T1/C2 not trained (cheap kill / underpowered-stop path)."
        )
        provisional["t1_status"] = "skipped_k0"
        return provisional

    # K0 passed: attempt T1 if research-ml available.
    try:
        import lightgbm as lgb  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        provisional["mode_note"] = (
            provisional["mode_note"]
            + " K0 passed but research-ml (lightgbm) not installed → T1 unmeasured fail-closed. "
            "Install with: uv sync --extra research-ml"
        )
        provisional["t1_status"] = "skipped_no_ml"
        return provisional

    log("K0 passed + lightgbm present — building F0 feature panel for T1")
    t1_spreads = _run_t1_walk_forward(
        series=series,
        formation_rows=formation_rows,
        lgb=lgb,
        np=np,
        seed=seed,
    )
    if not t1_spreads:
        provisional["t1_status"] = "failed_empty"
        provisional["mode_note"] = (
            provisional["mode_note"] + " T1 walk-forward produced no OOS spreads."
        )
        return provisional

    t1_stats = summarize(
        [s for _, s in t1_spreads],
        [d for d, _ in t1_spreads],
    )
    t1_mean_net = (
        cost_net_spread(t1_stats.mean, bps_per_side=10.0)
        if math.isfinite(t1_stats.mean)
        else float("nan")
    )
    t1_median_net = (
        cost_net_spread(t1_stats.median, bps_per_side=10.0)
        if t1_stats.median is not None and math.isfinite(t1_stats.median)
        else float("nan")
    )
    log(
        f"T1 OOS n={t1_stats.n} mean_net_10={t1_mean_net} "
        f"median_net_10={t1_median_net}"
    )

    # Rebuild with T1 measured; VI/DSR still fail-closed unless measured below.
    final = _build_artifact_from_c1(
        spread_by_date=spread_by_date,
        means_by_year_decile=means_by_year_decile,
        placebo_t_abs=placebo_t,
        mode="continuous-fixture",
        mode_note=(
            "Continuous 2019–2025 fixture: C1 + G0 + K0 + placebo + T1 shallow LGBM OOS. "
            "Not full-depth SEP primary span. VI/DSR may still fail-closed if not audited."
        ),
        t1_status="measured",
        t1_mean_net=t1_mean_net,
        t1_median_net=t1_median_net,
        # VI not fully audited on this path → fail closed G6/G7/G8 honestly
        vi_price_trend_share=None,
        vi_noise_in_top10=None,
        vi_short_horizon_share=None,
        deflated_sharpe=None,
        deflated_sharpe_measured=False,
    )
    final["t1_n_formations"] = t1_stats.n
    final["t1_mean_gross"] = t1_stats.mean
    final["t1_mean_net_10bps"] = t1_mean_net if math.isfinite(t1_mean_net) else None
    return final


def _feature_row(closes: list[float], *, idx: int, rng: random.Random) -> dict[str, float] | None:
    """F0 price-trend features + seeded noise probe at formation index."""
    if idx < PROTOCOL.mom_far_sessions:
        return None
    mom12 = mom_12_1_return(closes, formation_index=idx, far=252, near=21)
    mom6 = mom_12_1_return(closes, formation_index=idx, far=126, near=21)
    mom3 = mom_12_1_return(closes, formation_index=idx, far=63, near=21)
    if idx < 21:
        ret21 = None
    else:
        c_near = closes[idx]
        c_far = closes[idx - 21]
        ret21 = (c_near / c_far - 1.0) if c_far > 0 else None

    if any(v is None for v in (mom12, mom6, mom3, ret21)):
        return None

    # 52w high proximity (252 sessions)
    window = closes[idx - 251 : idx + 1]
    if len(window) < 252:
        return None
    hi52 = max(window)
    if hi52 <= 0:
        return None
    pct_hi = closes[idx] / hi52

    # SMA geometry
    if idx < 200:
        return None
    sma50 = sum(closes[idx - 49 : idx + 1]) / 50.0
    sma200 = sum(closes[idx - 199 : idx + 1]) / 200.0
    if sma50 <= 0 or sma200 <= 0:
        return None
    close_over_sma50 = closes[idx] / sma50
    sma50_over_sma200 = sma50 / sma200
    if idx < 220:
        return None
    sma200_prev = sum(closes[idx - 219 : idx - 19]) / 200.0
    if sma200_prev <= 0:
        return None
    sma200_slope = sma200 / sma200_prev - 1.0

    hi20 = max(closes[idx - 19 : idx + 1])
    if hi20 <= 0:
        return None
    dist_20 = closes[idx] / hi20 - 1.0

    return {
        "mom_12_1": float(mom12),  # type: ignore[arg-type]
        "mom_6_1": float(mom6),  # type: ignore[arg-type]
        "mom_3_1": float(mom3),  # type: ignore[arg-type]
        "ret_21d": float(ret21),  # type: ignore[arg-type]
        "pct_of_52w_high": float(pct_hi),
        "close_over_sma50": float(close_over_sma50),
        "sma50_over_sma200": float(sma50_over_sma200),
        "sma200_slope_20d": float(sma200_slope),
        "dist_to_20d_high": float(dist_20),
        "noise_probe": rng.gauss(0.0, 1.0),
    }


def _run_t1_walk_forward(
    *,
    series: dict[str, dict],
    formation_rows: list[dict],
    lgb: object,
    np: object,
    seed: int,
) -> list[tuple[date, float]]:
    """Shallow LightGBM OOS D10−D1 on walk-forward year folds with purge.

    First train year(s) → predict next year formations. Purge = label horizon
    sessions after last train formation (enforced by year boundaries ≈ enough).
    """
    feature_names = [
        "mom_12_1",
        "mom_6_1",
        "mom_3_1",
        "ret_21d",
        "pct_of_52w_high",
        "close_over_sma50",
        "sma50_over_sma200",
        "sma200_slope_20d",
        "dist_to_20d_high",
        "noise_probe",
    ]
    rng = random.Random(seed + 7)

    # Build full feature matrix per formation (recompute from series).
    panels: list[dict] = []
    for row in formation_rows:
        fdate: date = row["date"]
        X_rows: list[list[float]] = []
        y_rows: list[float] = []
        for sym, score, lab in zip(row["symbols"], row["scores"], row["labels_dm"], strict=True):
            s = series[sym]
            idx = s["date_to_i"].get(fdate)
            if idx is None:
                continue
            feats = _feature_row(s["closes"], idx=idx, rng=rng)
            if feats is None:
                continue
            X_rows.append([feats[k] for k in feature_names])
            y_rows.append(lab)
        if len(X_rows) < PROTOCOL.deciles * 2:
            continue
        panels.append({"date": fdate, "X": X_rows, "y": y_rows})

    if not panels:
        return []

    years = sorted({p["date"].year for p in panels})
    if len(years) < 2:
        log("T1: need >=2 years for walk-forward")
        return []

    oos_spreads: list[tuple[date, float]] = []
    # Expanding train: train on all years < test_year
    for test_year in years[1:]:
        train_panels = [p for p in panels if p["date"].year < test_year]
        test_panels = [p for p in panels if p["date"].year == test_year]
        if not train_panels or not test_panels:
            continue
        X_train = np.vstack([np.asarray(p["X"], dtype=float) for p in train_panels])  # type: ignore[attr-defined]
        y_train = np.concatenate([np.asarray(p["y"], dtype=float) for p in train_panels])  # type: ignore[attr-defined]
        if len(y_train) < PROTOCOL.t1_min_data_in_leaf * 2:
            log(f"T1 skip year={test_year}: train n={len(y_train)} too small")
            continue

        # Single frozen shallow config (predeclared upper bounds).
        params = {
            "objective": "regression",
            "metric": "l2",
            "learning_rate": 0.05,
            "num_leaves": min(8, PROTOCOL.t1_max_leaves),
            "max_depth": PROTOCOL.t1_max_depth,
            "min_data_in_leaf": PROTOCOL.t1_min_data_in_leaf,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 1,
            "verbosity": -1,
            "seed": seed,
        }
        dtrain = lgb.Dataset(X_train, label=y_train, feature_name=feature_names)  # type: ignore[attr-defined]
        booster = lgb.train(  # type: ignore[attr-defined]
            params,
            dtrain,
            num_boost_round=100,
        )
        log(f"T1 trained for test_year={test_year} n_train={len(y_train)}")

        for p in test_panels:
            X_te = np.asarray(p["X"], dtype=float)  # type: ignore[attr-defined]
            y_te = p["y"]
            pred = list(booster.predict(X_te))
            if len(pred) < PROTOCOL.deciles * 2:
                continue
            deciles = assign_deciles(pred)
            d1 = [y_te[i] for i, d in enumerate(deciles) if d == 1]
            d10 = [y_te[i] for i, d in enumerate(deciles) if d == 10]
            spread = top_minus_bottom_spread(d1, d10)
            if spread is None:
                continue
            oos_spreads.append((p["date"], spread))

    log(f"T1 OOS formations: {len(oos_spreads)}")
    return oos_spreads


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CMFT Stage A research driver (#74)")
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Run tiny synthetic harness (no multi-GB, no LightGBM)",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Force continuous fixture path (default when not --synthetic)",
    )
    parser.add_argument(
        "--write-docs",
        action="store_true",
        help="Write docs/research/cmft-results.md",
    )
    parser.add_argument(
        "--max-formations",
        type=int,
        default=0,
        help="If >0, cap month-end formations (debug only; not for accept path)",
    )
    args = parser.parse_args(argv)

    LOG_PATH.write_text("", encoding="utf-8")
    log(f"CMFT driver start experiment_id={PROTOCOL.experiment_id}")

    if args.synthetic:
        log("mode=synthetic")
        artifact = run_synthetic()
    else:
        log("mode=continuous-fixture")
        artifact = run_continuous(max_formations=args.max_formations)

    OUT_PATH.write_text(json.dumps(artifact, indent=2, default=str) + "\n", encoding="utf-8")
    log(f"wrote {OUT_PATH} verdict={artifact['verdict']} capital_go={artifact['capital_go']}")

    if args.write_docs:
        DOCS_PATH.write_text(_render_markdown(artifact), encoding="utf-8")
        log(f"wrote {DOCS_PATH}")

    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
