"""CMFT Stage A research driver (#74).

Sequential measurement path for conditional momentum family trial.

Modes:
  default     — no full SEP panel wired yet: fail-closed unmeasured evidence
                (honest dual-exit; does not invent spreads)
  --synthetic — tiny in-memory panel smoke: G0-data + K0 + C1 arithmetic only
                (no LightGBM; proves harness without multi-GB load)

Does NOT:
  - touch residual / R2-1
  - import production scan/backtest
  - set capital_go true
  - load SF1/SF2/SF3 or HMM

Outputs:
  fixtures/real-continuous/reports/cmft-structure.json
  docs/research/cmft-results.md (when --write-docs)

Parent PRD: #74
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

from invest.application.cmft import (
    PROTOCOL,
    assign_deciles,
    build_cmft_artifact,
    cost_net_spread,
    decile_mean_monotone_increasing,
    demean_cross_section,
    evaluate_cmft_gates,
    forward_open_to_open_return,
    mom_12_1_return,
    month_end_formation_dates,
    top_minus_bottom_spread,
    year_month_profit_shares,
)
from invest.application.event_study_excess import summarize

REPORTS = Path(__file__).resolve().parent
OUT_PATH = REPORTS / "cmft-structure.json"
LOG_PATH = REPORTS / "cmft-run.log"
DOCS_PATH = Path(__file__).resolve().parents[3] / "docs" / "research" / "cmft-results.md"


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
            "## Gates",
            "",
            *gate_lines,
            "",
            "## Mode notes",
            "",
            f"- mode: `{artifact.get('mode', 'unknown')}`",
            f"- note: {artifact.get('mode_note', '')}",
            "",
            "## How to re-run",
            "",
            "```bash",
            "# Fail-closed default (no invented continuous measurement)",
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
    return art


def _synthetic_sessions(n_days: int = 800) -> list[date]:
    """Weekday calendar starting 2018-01-02 (smoke only)."""
    d = date(2018, 1, 2)
    out: list[date] = []
    while len(out) < n_days:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def run_synthetic(seed: int = 42) -> dict:
    """Build a tiny multi-name panel and measure C1 + G0-data + K0 only.

    T1/C2/VI remain unmeasured → fail closed on those gates (honest).
    """
    rng = random.Random(seed)
    sessions = _synthetic_sessions(900)
    formations = month_end_formation_dates(sessions)
    # Need enough history before first formation used
    session_index = {d: i for i, d in enumerate(sessions)}

    n_names = 40
    # Random-walk closes/opens per name
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

    # Per formation: C1 mom_12_1 decile D10-D1 on demeaned forward returns
    spread_by_date: list[tuple[date, float]] = []
    means_by_year_decile: dict[int, dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

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

    # G0-data: per-year monotone decile means
    years_total = 0
    years_monotone = 0
    for year, by_d in sorted(means_by_year_decile.items()):
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

    # C1 only measured; T1 unmeasured → G5/VI/DSR fail closed (honest).
    by_year_spread: dict[int, list[float]] = defaultdict(list)
    for d, s in spread_by_date:
        by_year_spread[d.year].append(s)
    pos = sum(1 for vals in by_year_spread.values() if sum(vals) / len(vals) > 0)
    total_y = len(by_year_spread)

    report = evaluate_cmft_gates(
        g0_data_years_monotone=years_monotone if years_total else None,
        g0_data_years_total=years_total if years_total else None,
        k0_n_formations=n_form if n_form else None,
        k0_spread_vol=spread_vol if n_form and math.isfinite(spread_vol) else None,
        g0_placebo_t_abs=0.1,  # synthetic: not a real placebo draw
        spread_stats=stats,
        positive_annual_folds=pos,
        total_annual_folds=total_y,
        max_year_share=shares["max_year_share"],
        max_month_share=shares["max_month_share"],
        mean_net_10bps=mean_net_10,
        mean_net_5bps=mean_net_5,
        t1_mean_net=float("nan"),  # T1 not run
        t1_median_net=float("nan"),
        c1_mean_net=mean_net_10 if math.isfinite(mean_net_10) else float("nan"),
        c1_median_net=(
            cost_net_spread(stats.median, bps_per_side=10.0)
            if stats.median is not None and math.isfinite(stats.median)
            else float("nan")
        ),
        vi_price_trend_share=None,  # T1 not run
        vi_noise_in_top10=None,
        vi_short_horizon_share=None,
        deflated_sharpe=None,
        deflated_sharpe_measured=False,
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
    art["mode"] = "synthetic"
    art["mode_note"] = (
        "Synthetic smoke only: C1 + G0-data + K0 measured; "
        "T1/C2/VI/DSR unmeasured fail-closed. Not a capital or continuous claim."
    )
    art["c1_n_formations"] = n_form
    art["c1_mean_gross"] = stats.mean if spreads else None
    art["c1_mean_net_10bps"] = mean_net_10 if math.isfinite(mean_net_10) else None
    return art


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CMFT Stage A research driver (#74)")
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Run tiny synthetic harness (no multi-GB, no LightGBM)",
    )
    parser.add_argument(
        "--write-docs",
        action="store_true",
        help="Write docs/research/cmft-results.md",
    )
    args = parser.parse_args(argv)

    LOG_PATH.write_text("", encoding="utf-8")
    log(f"CMFT driver start experiment_id={PROTOCOL.experiment_id}")

    if args.synthetic:
        log("mode=synthetic")
        artifact = run_synthetic()
    else:
        log("mode=default fail-closed (continuous SEP panel not measured in-process)")
        artifact = _fail_closed_unmeasured(
            mode="default-unmeasured",
            mode_note=(
                "Continuous full-depth SEP panel measurement is not executed in this "
                "default path. Publish fail-closed until a sequential panel load is "
                "implemented against entitled SEP. Use --synthetic for harness smoke."
            ),
        )

    OUT_PATH.write_text(json.dumps(artifact, indent=2, default=str) + "\n", encoding="utf-8")
    log(f"wrote {OUT_PATH} verdict={artifact['verdict']} capital_go={artifact['capital_go']}")

    if args.write_docs:
        DOCS_PATH.write_text(_render_markdown(artifact), encoding="utf-8")
        log(f"wrote {DOCS_PATH}")

    log("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
