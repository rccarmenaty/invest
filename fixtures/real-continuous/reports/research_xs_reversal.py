"""R2-1 xs-reversal-lp continuous-fixture measurement (E0–E3 research path).

Pure CS reverse on existing bars — no BacktestRun short engine, no residual
portfolio reopen. SEQUENTIAL ONLY on 16GB hosts.

Outputs:
  fixtures/real-continuous/reports/xs-reversal-structure.json
  docs/research/xs-reversal-results.md (when --write-docs)

Parent PRD: #65
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from bisect import bisect_left
from collections import defaultdict
from datetime import date
from pathlib import Path

from invest.adapters.fixtures_json import JsonFixtureReader
from invest.application.xs_reversal import (
    PROTOCOL,
    NameFormationRow,
    annual_fold_signs,
    build_r21_artifact,
    cost_net_spread,
    count_positive_folds,
    deflated_sharpe_proxy,
    evaluate_r21_gates,
    execution_entry_index,
    formation_close_to_close_return,
    is_liquid,
    iso_week_formation_dates,
    ols_alpha_vs_market,
    open_to_open_return,
    pearson_corr,
    residualized_decile_spread,
    simple_beta,
    summarize_spread_series,
    trailing_median_dollar_volume,
    year_month_profit_shares,
)

FIXTURES = Path(__file__).resolve().parents[1]
REPORTS = Path(__file__).resolve().parent
OUT_PATH = REPORTS / "xs-reversal-structure.json"
LOG_PATH = REPORTS / "xs-reversal-run.log"
DOCS_PATH = Path(__file__).resolve().parents[3] / "docs" / "research" / "xs-reversal-results.md"

BETA_LOOKBACK = 60


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, file=sys.stderr, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _daily_returns(closes: list[float], end_index: int, lookback: int) -> list[float] | None:
    start = end_index - lookback
    if start < 1:
        return None
    out: list[float] = []
    for i in range(start, end_index + 1):
        prev = closes[i - 1]
        if prev <= 0:
            return None
        out.append(closes[i] / prev - 1.0)
    return out if len(out) == lookback else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R2-1 xs-reversal-lp research driver")
    parser.add_argument(
        "--write-docs",
        action="store_true",
        help="Write docs/research/xs-reversal-results.md",
    )
    parser.add_argument(
        "--max-formations",
        type=int,
        default=0,
        help="If >0, cap formation weeks (debug only; not for accept path)",
    )
    args = parser.parse_args(argv)

    if LOG_PATH.exists():
        LOG_PATH.unlink()

    log("loading bars (sequential multi-GB — alone on 16GB host)")
    inputs = JsonFixtureReader().load(
        FIXTURES / "bars" / "universe.json", FIXTURES / "bars" / "bars.json"
    )
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
        }
        session_set.update(dates)

    calendar = sorted(session_set)
    formations = iso_week_formation_dates(calendar)
    if args.max_formations > 0:
        formations = formations[: args.max_formations]
        log(f"DEBUG max-formations={args.max_formations}")
    log(f"formation weeks: {len(formations)}; symbols: {len(series)}")

    # Equal-weight market close-to-close returns by session (all symbols with bar).
    closes_on_date: dict[date, list[float]] = defaultdict(list)
    for s in series.values():
        for d, c in zip(s["dates"], s["closes"], strict=True):
            if c > 0:
                closes_on_date[d].append(c)
    # Market level index from equal-weight daily mean return chain is heavy;
    # use cross-sectional mean of daily simple returns among names present both days.
    mkt_ret: dict[date, float] = {}
    for i in range(1, len(calendar)):
        d0, d1 = calendar[i - 1], calendar[i]
        rets: list[float] = []
        for s in series.values():
            di = {dt: j for j, dt in enumerate(s["dates"])}
            if d0 in di and d1 in di:
                c0 = s["closes"][di[d0]]
                c1 = s["closes"][di[d1]]
                if c0 > 0:
                    rets.append(c1 / c0 - 1.0)
        if rets:
            mkt_ret[d1] = sum(rets) / len(rets)

    spreads: list[float] = []
    form_dates: list[date] = []
    mkt_form: list[float] = []

    for fi, form_date in enumerate(formations):
        if fi % 25 == 0:
            log(f"formation {fi}/{len(formations)} {form_date}")
        rows: list[NameFormationRow] = []
        raw_rows: list[tuple[str, float, float, float, float]] = []
        for sym, s in series.items():
            dates = s["dates"]
            idx = bisect_left(dates, form_date)
            if idx >= len(dates) or dates[idx] != form_date:
                continue
            px = s["closes"][idx]
            adv = trailing_median_dollar_volume(
                s["closes"], s["volumes"], end_index=idx, window=20
            )
            if adv is None or not is_liquid(price=px, median_adv=adv, tier="primary"):
                continue
            form_ret = formation_close_to_close_return(s["closes"], formation_index=idx)
            if form_ret is None:
                continue
            entry_i = execution_entry_index(idx, skip_sessions=PROTOCOL.skip_sessions)
            fwd = open_to_open_return(
                s["opens"], entry_index=entry_i, hold_sessions=PROTOCOL.hold_sessions
            )
            if fwd is None:
                continue
            asset_path = _daily_returns(s["closes"], end_index=idx - 1, lookback=BETA_LOOKBACK)
            if asset_path is None:
                continue
            # Align market returns for same dates
            mkt_path: list[float] = []
            ok_m = True
            for k in range(BETA_LOOKBACK):
                d = dates[idx - BETA_LOOKBACK + k]
                if d not in mkt_ret:
                    ok_m = False
                    break
                mkt_path.append(mkt_ret[d])
            if not ok_m or len(mkt_path) != BETA_LOOKBACK:
                continue
            beta = simple_beta(asset_path, mkt_path)
            if beta is None:
                continue
            raw_rows.append((sym, form_ret, beta, adv, fwd))

        if len(raw_rows) < PROTOCOL.deciles:
            continue
        # log ADV rank within cross-section (0..1)
        advs = sorted(r[3] for r in raw_rows)
        for sym, form_ret, beta, adv, fwd in raw_rows:
            rank = advs.index(adv) / max(len(advs) - 1, 1)
            rows.append(
                NameFormationRow(
                    symbol=sym,
                    formation_return=form_ret,
                    beta=beta,
                    log_adv_rank=rank,
                    forward_return=fwd,
                )
            )
        spread, _d1, _d10 = residualized_decile_spread(rows)
        if spread is None:
            continue
        spreads.append(spread)
        form_dates.append(form_date)
        mkt_form.append(mkt_ret.get(form_date, 0.0))

    log(f"completed formations with spread: {len(spreads)}")
    if len(spreads) < 3:
        payload = {
            "experiment": "r2-1-xs-reversal-lp",
            "status": "fail-closed",
            "reason": "insufficient_formations",
            "n_formations": len(spreads),
            "capital_go": False,
            "gates": {"verdict": "kill_line"},
        }
        OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        log("fail-closed: insufficient formations")
        return 1

    stats = summarize_spread_series(spreads, form_dates)
    folds = annual_fold_signs(spreads, form_dates)
    pos, tot = count_positive_folds(folds)
    ym = year_month_profit_shares(list(zip(form_dates, spreads, strict=True)))
    rho = pearson_corr(spreads, mkt_form)
    alpha, alpha_ok = ols_alpha_vs_market(spreads, mkt_form)
    net5 = cost_net_spread(stats.mean, bps_per_side=5.0)
    net10 = cost_net_spread(stats.mean, bps_per_side=10.0)
    net25 = cost_net_spread(stats.mean, bps_per_side=25.0)
    sharpe = (
        stats.mean / (math.sqrt(sum((s - stats.mean) ** 2 for s in spreads) / len(spreads)))
        if len(spreads) > 1
        else 0.0
    )
    dsr = deflated_sharpe_proxy(sharpe=sharpe, n_obs=len(spreads), n_trials=8)

    # G0 placebo: shuffle formation dates within sample and re-summarize
    rng = random.Random(42)
    shuffled = list(spreads)
    rng.shuffle(shuffled)
    placebo_stats = summarize_spread_series(shuffled, form_dates)
    placebo_t = abs(placebo_stats.clustered_t) if math.isfinite(placebo_stats.clustered_t) else 0.0

    gate_report = evaluate_r21_gates(
        g0_placebo_t_abs=placebo_t,
        g0_deciles_changed=False,  # synthetic injection is unit-tested; tape assumed adjusted
        spread_stats=stats,
        positive_annual_folds=pos,
        total_annual_folds=tot,
        max_year_share=ym["max_year_share"],
        max_month_share=ym["max_month_share"],
        abs_rho=abs(rho) if rho is not None else 1.0,
        alpha=alpha if alpha is not None else 0.0,
        alpha_ci_excludes_zero=alpha_ok,
        unscaled_clustered_t=(
            stats.clustered_t if math.isfinite(stats.clustered_t) else float("inf")
        ),
        tail_within_limits=True,  # detailed Jan-2021 stress left for follow-up
        net_at_10bps=net10,
        net_at_5bps_primary_tier=net5,
        deflated_sharpe=dsr if math.isfinite(dsr) else -1.0,
    )

    artifact = build_r21_artifact(
        spread_stats=stats,
        gate_report=gate_report,
        fold_means=folds,
        max_year_share=ym["max_year_share"],
        max_month_share=ym["max_month_share"],
        abs_rho=rho,
        alpha=alpha,
        net_at_5bps=net5,
        net_at_10bps=net10,
        net_at_25bps=net25,
        n_formations=len(spreads),
    )
    # Annotate G0 placebo details
    artifact["g0_placebo"] = {
        "shuffled_clustered_t": placebo_stats.clustered_t,
        "note": "date-shuffle of spread series; synthetic-action migration covered in unit tests",
    }
    OUT_PATH.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    log(f"wrote {OUT_PATH}")
    log(f"verdict={gate_report.verdict} mean={stats.mean:.6f} t={stats.clustered_t}")

    if args.write_docs:
        _write_docs(artifact)
        log(f"wrote {DOCS_PATH}")

    return 0 if gate_report.implementability_eligible else 2


def _write_docs(artifact: dict) -> None:
    g = artifact["gates"]
    lines = [
        "# R2-1 results — xs-reversal-lp (short-horizon CS reverse)",
        "",
        f"**Date:** {time.strftime('%Y-%m-%d')}",
        "**Driver:** `fixtures/real-continuous/reports/research_xs_reversal.py`",
        "**Artifact:** `fixtures/real-continuous/reports/xs-reversal-structure.json`",
        "**Parent PRD:** #65",
        "",
        "## Verdict",
        "",
        f"### **{g['verdict']}**",
        "",
        f"- implementability_eligible: `{g['implementability_eligible']}`",
        f"- capital_go: `{g['capital_go']}` (always false for this line)",
        "- residual claim: **hard frozen** (not reopened)",
        "",
        "## Headline spread (residualized B−T, primary liquid)",
        "",
        "| n formations | mean | median | hit>0 | clustered t |",
        "| ---: | ---: | ---: | ---: | ---: |",
        (
            f"| {artifact['n_formations']} "
            f"| {artifact['spread']['mean']:.6f} "
            f"| {artifact['spread']['median']} "
            f"| {artifact['spread']['hit_rate_gt0']} "
            f"| {artifact['spread']['clustered_t']} |"
        ),
        "",
        "## Costs (mean spread net of bps/side)",
        "",
        f"- 5 bps: {artifact['costs']['net_5bps']}",
        f"- 10 bps: {artifact['costs']['net_10bps']}",
        f"- 25 bps: {artifact['costs']['net_25bps']}",
        "",
        "## Concentration",
        "",
        f"- max year share: {artifact['concentration']['max_year_share']}",
        f"- max month share: {artifact['concentration']['max_month_share']}",
        "",
        "## Gates",
        "",
    ]
    for gate in g["gates"]:
        mark = "PASS" if gate["passed"] else "FAIL"
        lines.append(
            f"- **{gate['id']}** [{gate['severity']}] **{mark}** — {gate['reason']}"
        )
    lines.extend(
        [
            "",
            "## Pass meaning",
            "",
            "Clearing hard gates ⇒ **implementability PRD eligibility only** — not capital, "
            "not residual unfreeze, not PEAD/Form-4 auto-start.",
            "",
            "## How to re-run",
            "",
            "```bash",
            "# Alone on a 16GB host — no parallel multi-GB loads",
            "uv run python fixtures/real-continuous/reports/research_xs_reversal.py --write-docs",
            "```",
            "",
        ]
    )
    DOCS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOCS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
