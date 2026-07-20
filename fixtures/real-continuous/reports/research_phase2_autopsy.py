"""Phase 2b concentration autopsy — post-process phase2-structure.json + SPY sidecar.

No multi-GB continuous re-backtest. Sequential research command only for optional
SPY sidecar refresh. Unit CI never loads full bars.

Plan: docs/research/phase2-concentration-autopsy-plan.md
Issue: #64
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx

from invest.application.phase2_report import (
    DEFAULT_SLIPPAGE_BPS,
    PRIMARY_TAX_RATE,
    WALK_FORWARD_YEARS,
    build_phase2_concentration_autopsy_report,
    simulated_trades_from_records,
)

REPORTS = Path(__file__).resolve().parent
PHASE2_JSON = REPORTS / "phase2-structure.json"
SPY_SIDECAR = REPORTS / "spy-opens-sidecar.json"
OUT_JSON = REPORTS / "phase2-concentration-autopsy.json"
OUT_MD = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "research"
    / "phase2-concentration-autopsy.md"
)
LOG_PATH = REPORTS / "phase2-autopsy-run.log"

LEAVE_YEAR = 2020
SPY_TICKER = "SPY"


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, file=sys.stderr, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _load_phase2() -> dict:
    if not PHASE2_JSON.is_file():
        raise FileNotFoundError(f"missing Phase 2 artifact: {PHASE2_JSON}")
    return json.loads(PHASE2_JSON.read_text(encoding="utf-8"))


def _published_full_book_mean(phase2: dict) -> Decimal:
    raw = phase2["after_cost_pre_tax"]["mean_expectancy"]
    return Decimal(str(raw))


def _date_span_for_trades(trades) -> tuple[date, date]:
    starts = [t.entry_date for t in trades]
    ends = [t.exit_date for t in trades]
    return min(starts), max(ends)


def _load_spy_sidecar() -> dict[date, Decimal] | None:
    if not SPY_SIDECAR.is_file():
        return None
    payload = json.loads(SPY_SIDECAR.read_text(encoding="utf-8"))
    opens = payload.get("opens") or payload
    return {date.fromisoformat(k): Decimal(str(v)) for k, v in opens.items()}


def _fetch_spy_opens(start: date, end: date) -> dict[date, Decimal]:
    """Fetch SPY daily opens via Yahoo chart API (no key; full Phase 2 span).

    Sharadar SEP under the project key returned no ETFs; Alpaca IEX SPY history
    starts mid-2020 and cannot cover 2019 leave-year trades.
    """
    from datetime import datetime, timedelta, timezone

    # Yahoo period2 is exclusive-ish; pad end by one day in UTC.
    period1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    end_plus = end + timedelta(days=2)
    period2 = int(
        datetime(end_plus.year, end_plus.month, end_plus.day, tzinfo=timezone.utc).timestamp()
    )
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{SPY_TICKER}"
    resp = httpx.get(
        url,
        params={
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "div,splits",
        },
        timeout=60.0,
        headers={"User-Agent": "invest-research/phase2b"},
        follow_redirects=True,
    )
    resp.raise_for_status()
    body = resp.json()
    result = (body.get("chart") or {}).get("result") or []
    if not result:
        raise RuntimeError(f"Yahoo chart empty for SPY: {body.get('chart', {}).get('error')}")
    series = result[0]
    timestamps = series.get("timestamp") or []
    quote = (series.get("indicators") or {}).get("quote") or [{}]
    open_series = quote[0].get("open") or []
    opens: dict[date, Decimal] = {}
    for ts, raw_open in zip(timestamps, open_series, strict=False):
        if raw_open is None:
            continue
        d = datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
        if d < start or d > end:
            continue
        opens[d] = Decimal(str(raw_open))
    if not opens:
        raise RuntimeError("no SPY opens in Yahoo response for requested span")
    return opens


def _ensure_spy_opens(trades) -> tuple[dict[date, Decimal], dict]:
    start, end = _date_span_for_trades(trades)
    loaded = _load_spy_sidecar()
    provenance: dict = {
        "proxy": SPY_TICKER,
        "sidecar_path": "fixtures/real-continuous/reports/spy-opens-sidecar.json",
        "span": {"start": start.isoformat(), "end": end.isoformat()},
    }
    if loaded is not None:
        missing = [
            t
            for t in trades
            if t.entry_date not in loaded or t.exit_date not in loaded
        ]
        if not missing:
            provenance["source"] = "sidecar-file"
            provenance["session_count"] = len(loaded)
            return loaded, provenance
        log(f"sidecar missing {len(missing)} trade session dates; refreshing SPY")

    log(f"fetching SPY opens {start}..{end}")
    opens = _fetch_spy_opens(start, end)
    payload = {
        "symbol": SPY_TICKER,
        "source": "yahoo-chart-v8",
        "span": {"start": start.isoformat(), "end": end.isoformat()},
        "opens": {d.isoformat(): str(px) for d, px in sorted(opens.items())},
    }
    SPY_SIDECAR.write_text(json.dumps(payload, indent=1, sort_keys=True), encoding="utf-8")
    log(f"wrote {SPY_SIDECAR} ({len(opens)} sessions)")
    provenance["source"] = "yahoo-chart-v8-refresh"
    provenance["session_count"] = len(opens)
    return opens, provenance


def _render_markdown(report: dict, phase2_mean: Decimal) -> str:
    k2 = report["k2"]
    leave = report["leave_year_book"]
    s2 = report["s2_trade_window_spy"]
    lines = [
        "# Phase 2b results — concentration autopsy",
        "",
        f"**Date:** {time.strftime('%Y-%m-%d')}  ",
        f"**Driver:** `fixtures/real-continuous/reports/research_phase2_autopsy.py`  ",
        f"**Artifact:** `fixtures/real-continuous/reports/phase2-concentration-autopsy.json`  ",
        f"**Plan:** `docs/research/phase2-concentration-autopsy-plan.md`  ",
        f"**Parent:** Phase 2 NO-GO · #62 · issue #64",
        "",
        "## Verdict",
        "",
        f"### residual_hope: **{report['residual_hope'].upper()}**",
        "",
        "Promotion remains **blocked** (Phase 2 year concentration). "
        "This field is die|survive only — never GO.",
        "",
        "### K2 legs",
        "",
        "| Leg | Result | Detail |",
        "| --- | --- | --- |",
        (
            f"| Leave-{report['leave_year']} mean > 0 | "
            f"{'PASS' if k2['leave_year_mean_positive'] else 'FAIL'} | "
            f"{k2['leave_year_mean_expectancy']} |"
        ),
        (
            f"| Leave mean > ½ full-book mean | "
            f"{'PASS' if k2['half_mean_ok'] else 'FAIL'} | "
            f"leave {k2['leave_year_mean_expectancy']} vs half of "
            f"{k2['full_book_mean_expectancy']} = {k2['half_full_book_mean']} |"
        ),
        (
            f"| Majority remaining folds mean > 0 | "
            f"{'PASS' if k2['majority_folds_positive'] else 'FAIL'} | "
            f"{k2['positive_fold_count']}/{k2['evaluated_fold_count']} |"
        ),
        (
            f"| S2 mean trade−SPY excess > 0 | "
            f"{'PASS' if k2['spy_excess_ok'] else 'FAIL'} | "
            f"{k2['mean_spy_excess']} |"
        ),
        "",
        "Reasons:",
        "",
    ]
    for reason in k2["reasons"]:
        lines.append(f"- {reason}")
    lines.extend(
        [
            "",
            "## Leave-year book (pre-tax, 5 bps/side)",
            "",
            f"Published full-book mean (denominator): **{phase2_mean}**",
            "",
            "| Book | n | Mean exp | Median exp | Hit | Net P&L |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
            (
                f"| Leave-{report['leave_year']} | {leave['trade_count']} | "
                f"{leave['mean_expectancy']} | {leave['median_expectancy']} | "
                f"{leave['hit_rate']} | {leave['net_pnl']} |"
            ),
            (
                f"| Non-FC | {report['fc_segregated']['non_fc']['trade_count']} | "
                f"{report['fc_segregated']['non_fc']['mean_expectancy']} | "
                f"{report['fc_segregated']['non_fc']['median_expectancy']} | "
                f"{report['fc_segregated']['non_fc']['hit_rate']} | "
                f"{report['fc_segregated']['non_fc']['net_pnl']} |"
            ),
            (
                f"| FC only | {report['fc_segregated']['fc_only']['trade_count']} | "
                f"{report['fc_segregated']['fc_only']['mean_expectancy']} | "
                f"{report['fc_segregated']['fc_only']['median_expectancy']} | "
                f"{report['fc_segregated']['fc_only']['hit_rate']} | "
                f"{report['fc_segregated']['fc_only']['net_pnl']} |"
            ),
            "",
            "## Remaining walk-forward folds",
            "",
            "| Year | n | Mean exp | Median exp | Net P&L |",
            "| ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for year, book in sorted(report["walk_forward_folds_remaining"].items()):
        lines.append(
            f"| {year} | {book['trade_count']} | {book['mean_expectancy']} | "
            f"{book['median_expectancy']} | {book['net_pnl']} |"
        )
    lines.extend(
        [
            "",
            "## S2 trade-window SPY",
            "",
            f"- Proxy: {s2['proxy']}",
            f"- Window: {s2['window']}",
            f"- Notional: {s2['notional']}",
            f"- Mean excess (trade after-cost − matched SPY): **{s2['mean_spy_excess']}**",
            f"- n trades: {s2['trade_count']}",
            "",
            "## Pause-default",
            "",
            "Next research budget defaults to **pause** on the price-event portfolio residual line. "
            "Form-4 PIT audit or a new concentration-policy PRD requires an explicit re-open. "
            "No ranking / Quiet Drift / DAMB package auto-start.",
            "",
            "## How to re-run",
            "",
            "```bash",
            "uv run python fixtures/real-continuous/reports/research_phase2_autopsy.py",
            "```",
            "",
            "Requires committed `phase2-structure.json`. SPY opens load from "
            "`spy-opens-sidecar.json` when present and complete; otherwise refresh via "
            "Yahoo chart API for SPY daily opens. Unit CI must not load multi-GB bars.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    LOG_PATH.write_text("", encoding="utf-8")
    log("Phase 2b concentration autopsy starting")
    phase2 = _load_phase2()
    if phase2.get("status") and phase2.get("status") != "complete":
        log(f"Phase 2 status={phase2.get('status')}; refusing autopsy")
        return 2

    trades = simulated_trades_from_records(phase2["trades"])
    full_mean = _published_full_book_mean(phase2)
    log(f"loaded {len(trades)} trades; published full-book mean={full_mean}")

    leave_year = int(
        phase2.get("go_no_go", {}).get("peak_profit_year") or LEAVE_YEAR
    )
    if leave_year != LEAVE_YEAR:
        log(f"note: peak_profit_year from artifact is {leave_year} (plan default {LEAVE_YEAR})")

    spy_opens, spy_prov = _ensure_spy_opens(trades)
    # Validate coverage before K2
    missing = [
        (t.symbol, t.entry_date, t.exit_date)
        for t in trades
        if t.entry_date.year != leave_year
        and (t.entry_date not in spy_opens or t.exit_date not in spy_opens)
    ]
    if missing:
        log(f"FAIL-CLOSED: missing SPY opens for {len(missing)} leave-year trades")
        OUT_JSON.write_text(
            json.dumps(
                {
                    "experiment": "phase2-concentration-autopsy",
                    "status": "fail-closed",
                    "reason": "missing-spy-opens",
                    "missing_count": len(missing),
                    "residual_hope": "die",
                    "note": "No residual_hope claim without complete SPY sidecar coverage.",
                },
                indent=1,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return 2

    provenance = {
        "parent_experiment": "phase2-fixed-horizon-structure",
        "parent_artifact": "fixtures/real-continuous/reports/phase2-structure.json",
        "parent_go_no_go": phase2.get("go_no_go"),
        "parent_provenance": phase2.get("provenance"),
        "published_full_book_mean_expectancy": str(full_mean),
        "leave_year": leave_year,
        "costs": {
            "slippage_bps": str(DEFAULT_SLIPPAGE_BPS),
            "tax_rate": str(PRIMARY_TAX_RATE),
        },
        "spy": spy_prov,
        "ranking_accept_path": False,
        "plan": "docs/research/phase2-concentration-autopsy-plan.md",
        "issue": 64,
    }

    report = build_phase2_concentration_autopsy_report(
        trades=trades,
        leave_year=leave_year,
        full_book_mean_expectancy=full_mean,
        fold_years=WALK_FORWARD_YEARS,
        spy_opens=spy_opens,
        provenance=provenance,
        slippage_bps=DEFAULT_SLIPPAGE_BPS,
        tax_rate=PRIMARY_TAX_RATE,
    )
    report["status"] = "complete"
    report["trade_count_full"] = len(trades)
    report["trade_count_leave_year"] = report["leave_year_book"]["trade_count"]

    OUT_JSON.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    log(f"wrote {OUT_JSON}")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(_render_markdown(report, full_mean), encoding="utf-8")
    log(f"wrote {OUT_MD}")

    summary = {
        "residual_hope": report["residual_hope"],
        "k2": report["k2"],
        "leave_year_book": report["leave_year_book"],
        "s2_mean_spy_excess": report["s2_trade_window_spy"]["mean_spy_excess"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    log(f"residual_hope={report['residual_hope']}")
    # Exit 0 always on complete measurement (die is a valid scientific outcome)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
