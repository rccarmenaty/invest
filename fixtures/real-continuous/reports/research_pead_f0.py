"""R2-2 PEAD F0 data-feasibility probe (no returns).

Builds audit evidence from available fundamentals sources when present;
otherwise fail-closed unmeasured evidence → kill_line.

Does NOT run E1 event study or portfolio replay.

Outputs:
  fixtures/real-continuous/reports/pead-f0-structure.json
  docs/research/pead-f0-results.md (when --write-docs)

Parent PRD: #69
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from invest.application.pead_f0 import (
    KnownTimePolicy,
    PeadF0Evidence,
    build_pead_f0_artifact,
    evaluate_pead_f0_gates,
    passing_evidence,
)

REPORTS = Path(__file__).resolve().parent
OUT_PATH = REPORTS / "pead-f0-structure.json"
LOG_PATH = REPORTS / "pead-f0-run.log"
DOCS_PATH = Path(__file__).resolve().parents[3] / "docs" / "research" / "pead-f0-results.md"

# Optional local cache paths (none required for fail-closed default)
DEFAULT_SF1_CACHE_CANDIDATES = (
    REPORTS.parents[1] / "sf1",
    REPORTS.parents[2] / "data" / "sf1",
    Path.home() / "data" / "sharadar" / "sf1",
)


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, file=sys.stderr, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _has_api_key() -> bool:
    return bool(os.environ.get("NASDAQ_DATA_LINK_API_KEY"))


def _find_local_sf1_cache() -> Path | None:
    for p in DEFAULT_SF1_CACHE_CANDIDATES:
        if p.is_dir() and any(p.iterdir()):
            return p
    return None


def probe_sources() -> dict:
    """Discover whether a fundamentals source is available for a live audit.

    This probe does not download SF1. Absence → unmeasured evidence → kill_line.
    """
    api = _has_api_key()
    cache = _find_local_sf1_cache()
    return {
        "nasdaq_api_key_present": api,
        "local_sf1_cache": str(cache) if cache is not None else None,
        "sf1_adapter_present": False,  # no production SF1 adapter in-repo yet
        "live_audit_capable": False,
    }


def evidence_from_probe(source_info: dict) -> PeadF0Evidence:
    """Map source discovery to F0 evidence.

    Until a dedicated SF1/SEC original-as-published adapter exists and a
    stratified reconcile is run, all data measurements remain unmeasured
    (fail closed). Protocol + trial ledger are always present for this driver.
    """
    capable = bool(source_info.get("live_audit_capable"))
    if not capable:
        return PeadF0Evidence(
            protocol_present=True,
            trial_ledger_present=True,
            # All measurements None → D1–D7 fail closed
            original_eps_reconstructable=None,
            original_revenue_reconstructable=None,
            exact_known_time_proven=None,
            known_time_policy=KnownTimePolicy.UNKNOWN,
            known_time_policy_applied_consistently=None,
            lookahead_detected=None,
            current_id_leakage=None,
            silent_unit_change=None,
            amendment_rewrite=None,
            period_valid_mapping=None,
            terminal_economics_complete=None,
            max_prior_seasonal_changes=None,
            annual_test_folds=None,
            reconcile_pass=None,
            coverage_included=0,
            coverage_rejected=0,
            source_label="no_sf1_or_sec_original_tape",
        )
    # Placeholder branch for future live audit wiring — still fail closed until
    # reconcile is implemented (should not be reached while live_audit_capable
    # is hard-coded False).
    return PeadF0Evidence(
        protocol_present=True,
        trial_ledger_present=True,
        source_label="live_audit_not_implemented",
    )


def render_docs(artifact: dict, source_info: dict) -> str:
    gates = artifact["gates"]
    gate_rows = gates["gates"]
    lines = [
        "# R2-2 results — PEAD F0 data-feasibility",
        "",
        f"**Date:** {time.strftime('%Y-%m-%d')}",
        f"**Driver:** `fixtures/real-continuous/reports/research_pead_f0.py`",
        f"**Artifact:** `fixtures/real-continuous/reports/pead-f0-structure.json`",
        f"**Parent PRD:** #69",
        "",
        "## Verdict",
        "",
        f"### **{gates['verdict']}**",
        "",
        f"- f2_tape_eligible: `{gates['f2_tape_eligible']}`",
        f"- capital_go: `{gates['capital_go']}` (always false for this line)",
        f"- residual claim: **hard frozen** (not reopened)",
        f"- returns_measured: `{artifact['returns_measured']}`",
        f"- e1_status: `{artifact['e1_status']}`",
        "",
        "## Source probe",
        "",
        f"- nasdaq_api_key_present: `{source_info['nasdaq_api_key_present']}`",
        f"- local_sf1_cache: `{source_info['local_sf1_cache']}`",
        f"- sf1_adapter_present: `{source_info['sf1_adapter_present']}`",
        f"- live_audit_capable: `{source_info['live_audit_capable']}`",
        f"- source_label: `{artifact['coverage']['source_label']}`",
        "",
        "## Protocol freeze (recorded)",
        "",
        f"- signal_family: `{artifact['protocol']['signal_family']}`",
        f"- eps_field: `{artifact['protocol']['eps_field']}`",
        f"- revenue_field: `{artifact['protocol']['revenue_field']}`",
        f"- min_prior_seasonal_changes: `{artifact['protocol']['min_prior_seasonal_changes']}`",
        f"- min_annual_test_folds: `{artifact['protocol']['min_annual_test_folds']}`",
        f"- analyst_sue_fallback: `{artifact['protocol']['analyst_sue_fallback']}`",
        f"- known_time_policy (evidence): `{artifact['known_time_policy']}`",
        "",
        "## Coverage",
        "",
        f"- included: `{artifact['coverage']['included']}`",
        f"- rejected: `{artifact['coverage']['rejected']}`",
        "",
        "## Gates",
        "",
    ]
    for g in gate_rows:
        status = "PASS" if g["passed"] else "FAIL"
        lines.append(
            f"- **{g['id']}** [{g['severity']}] **{status}** — {g['reason']}"
        )
    lines += [
        "",
        "## Pass meaning",
        "",
        "Clearing hard data gates ⇒ **F2 immutable-tape PRD eligibility only** — "
        "not E1 returns, not capital, not residual unfreeze, not Form-4 auto-start.",
        "",
        "## Fail meaning",
        "",
        "Publish null / **kill_line** for PEAD under this protocol until a new PRD. "
        "Do not add analyst SUE, ranking, guidance NLP, or threshold retuning as rescue.",
        "",
        "## How to re-run",
        "",
        "```bash",
        "# Fail-closed default when no original-as-published SF1/SEC tape is wired",
        "uv run python fixtures/real-continuous/reports/research_pead_f0.py --write-docs",
        "```",
        "",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="R2-2 PEAD F0 data-feasibility probe")
    parser.add_argument(
        "--write-docs",
        action="store_true",
        help="Write docs/research/pead-f0-results.md",
    )
    parser.add_argument(
        "--synthetic-pass",
        action="store_true",
        help=(
            "Unit/demo only: inject full-pass synthetic evidence. "
            "Never use for research claims."
        ),
    )
    args = parser.parse_args(argv)

    if LOG_PATH.exists():
        LOG_PATH.unlink()

    log("PEAD F0 probe start")
    source_info = probe_sources()
    log(f"source probe: {source_info}")

    if args.synthetic_pass:
        log("WARNING: --synthetic-pass active (not a live audit)")
        evidence = passing_evidence(source_label="synthetic_pass_cli")
    else:
        evidence = evidence_from_probe(source_info)

    report = evaluate_pead_f0_gates(evidence)
    artifact = build_pead_f0_artifact(evidence=evidence, gate_report=report)
    artifact["source_probe"] = source_info

    OUT_PATH.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    log(f"wrote {OUT_PATH}")
    log(f"verdict={report.verdict} f2_tape_eligible={report.f2_tape_eligible}")

    if args.write_docs:
        DOCS_PATH.parent.mkdir(parents=True, exist_ok=True)
        DOCS_PATH.write_text(render_docs(artifact, source_info), encoding="utf-8")
        log(f"wrote {DOCS_PATH}")

    log("PEAD F0 probe done")
    # Exit 0 even on kill_line — research outcome, not process failure
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
