"""R2-2 PEAD F0: pure data-feasibility audit (no returns).

Revenue-confirmed public-time GAAP earnings-surprise line — F0 only.
Primary seam: pure application helpers for protocol freeze, audit evidence,
and D0–D7 fail-closed data gates. E1 event study / portfolio are out of scope.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum


class GateSeverity(StrEnum):
    HARD = "hard"
    INFO = "info"


class KnownTimePolicy(StrEnum):
    """How public availability time is established for an event."""

    EXACT_TIMESTAMP = "exact_timestamp"
    SECOND_OPEN_DATE_ONLY = "second_open_date_only"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ProtocolConfig:
    """Frozen F0 protocol. Future E1 knobs recorded only — never measured here."""

    signal_family: str = "revenue_confirmed_gaap_earnings_surprise"
    eps_field: str = "diluted_gaap_eps"
    revenue_field: str = "gaap_revenue"
    min_prior_seasonal_changes: int = 8
    min_annual_test_folds: int = 10
    capital_go: bool = False
    analyst_sue_fallback: bool = False
    # Future E1 freezes (not evaluated in F0)
    future_primary_horizon_sessions: int = 60
    future_entry: str = "next_open"
    future_primary_min_adv: float = 10_000_000.0
    future_accept_cost_bps: float = 5.0
    future_year_share_max: float = 0.25
    experiment_id: str = "r2-2-pead-f0"
    line: str = "pead-revenue-confirmed"


PROTOCOL = ProtocolConfig()


@dataclass(frozen=True)
class PeadGateResult:
    id: str
    passed: bool
    severity: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PeadF0GateReport:
    gates: tuple[PeadGateResult, ...]
    all_hard_gates_passed: bool
    f2_tape_eligible: bool
    capital_go: bool
    verdict: str

    def to_dict(self) -> dict:
        return {
            "gates": [g.to_dict() for g in self.gates],
            "all_hard_gates_passed": self.all_hard_gates_passed,
            "f2_tape_eligible": self.f2_tape_eligible,
            "capital_go": self.capital_go,
            "verdict": self.verdict,
        }


@dataclass(frozen=True)
class PeadF0Evidence:
    """Structured audit evidence for F0 gates. None fields mean not measured."""

    protocol_present: bool = True
    trial_ledger_present: bool = False
    original_eps_reconstructable: bool | None = None
    original_revenue_reconstructable: bool | None = None
    exact_known_time_proven: bool | None = None
    known_time_policy: KnownTimePolicy = KnownTimePolicy.UNKNOWN
    known_time_policy_applied_consistently: bool | None = None
    lookahead_detected: bool | None = None
    current_id_leakage: bool | None = None
    silent_unit_change: bool | None = None
    amendment_rewrite: bool | None = None
    period_valid_mapping: bool | None = None
    terminal_economics_complete: bool | None = None
    max_prior_seasonal_changes: int | None = None
    annual_test_folds: int | None = None
    reconcile_pass: bool | None = None
    coverage_included: int = 0
    coverage_rejected: int = 0
    source_label: str = "unspecified"


def _gate(
    gate_id: str,
    *,
    passed: bool,
    severity: GateSeverity,
    reason: str,
) -> PeadGateResult:
    return PeadGateResult(
        id=gate_id,
        passed=passed,
        severity=str(severity),
        reason=reason,
    )


def evaluate_d0_protocol(
    *,
    protocol_present: bool,
    trial_ledger_present: bool,
) -> PeadGateResult:
    if protocol_present and trial_ledger_present:
        return _gate(
            "D0",
            passed=True,
            severity=GateSeverity.HARD,
            reason="protocol freeze and trial ledger present",
        )
    missing = []
    if not protocol_present:
        missing.append("protocol")
    if not trial_ledger_present:
        missing.append("trial_ledger")
    return _gate(
        "D0",
        passed=False,
        severity=GateSeverity.HARD,
        reason=f"missing: {', '.join(missing)}",
    )


def evaluate_d1_original_eps(*, reconstructable: bool | None) -> PeadGateResult:
    if reconstructable is None:
        return _gate(
            "D1",
            passed=False,
            severity=GateSeverity.HARD,
            reason="original EPS reconstructability not measured — fail closed",
        )
    if reconstructable:
        return _gate(
            "D1",
            passed=True,
            severity=GateSeverity.HARD,
            reason="original-as-published diluted GAAP EPS reconstructable",
        )
    return _gate(
        "D1",
        passed=False,
        severity=GateSeverity.HARD,
        reason="original-as-published diluted GAAP EPS not reconstructable",
    )


def evaluate_d2_original_revenue(*, reconstructable: bool | None) -> PeadGateResult:
    if reconstructable is None:
        return _gate(
            "D2",
            passed=False,
            severity=GateSeverity.HARD,
            reason="original revenue reconstructability not measured — fail closed",
        )
    if reconstructable:
        return _gate(
            "D2",
            passed=True,
            severity=GateSeverity.HARD,
            reason="original-as-published GAAP revenue reconstructable",
        )
    return _gate(
        "D2",
        passed=False,
        severity=GateSeverity.HARD,
        reason="original-as-published GAAP revenue not reconstructable",
    )


def evaluate_d3_known_time(
    *,
    exact_known_time_proven: bool | None,
    policy: KnownTimePolicy,
    policy_applied_consistently: bool | None,
) -> PeadGateResult:
    if policy_applied_consistently is None:
        return _gate(
            "D3",
            passed=False,
            severity=GateSeverity.HARD,
            reason="known-time policy consistency not measured — fail closed",
        )
    if not policy_applied_consistently:
        return _gate(
            "D3",
            passed=False,
            severity=GateSeverity.HARD,
            reason="known-time policy not applied consistently",
        )
    if policy == KnownTimePolicy.UNKNOWN:
        return _gate(
            "D3",
            passed=False,
            severity=GateSeverity.HARD,
            reason="known-time policy unknown — fail closed",
        )
    if policy == KnownTimePolicy.EXACT_TIMESTAMP:
        if exact_known_time_proven is True:
            return _gate(
                "D3",
                passed=True,
                severity=GateSeverity.HARD,
                reason="exact known_time proven; policy applied consistently",
            )
        return _gate(
            "D3",
            passed=False,
            severity=GateSeverity.HARD,
            reason="exact_timestamp policy but exact known_time not proven",
        )
    # SECOND_OPEN_DATE_ONLY
    if policy == KnownTimePolicy.SECOND_OPEN_DATE_ONLY:
        return _gate(
            "D3",
            passed=True,
            severity=GateSeverity.HARD,
            reason="conservative second-open date-only policy applied consistently",
        )
    return _gate(
        "D3",
        passed=False,
        severity=GateSeverity.HARD,
        reason=f"unrecognized known-time policy {policy}",
    )


def evaluate_d4_integrity(
    *,
    lookahead_detected: bool | None,
    current_id_leakage: bool | None,
    silent_unit_change: bool | None,
    amendment_rewrite: bool | None,
) -> PeadGateResult:
    flags = {
        "lookahead": lookahead_detected,
        "current_id_leakage": current_id_leakage,
        "silent_unit_change": silent_unit_change,
        "amendment_rewrite": amendment_rewrite,
    }
    unmeasured = [k for k, v in flags.items() if v is None]
    if unmeasured:
        return _gate(
            "D4",
            passed=False,
            severity=GateSeverity.HARD,
            reason=f"integrity not measured ({', '.join(unmeasured)}) — fail closed",
        )
    leaks = [k for k, v in flags.items() if v is True]
    if leaks:
        return _gate(
            "D4",
            passed=False,
            severity=GateSeverity.HARD,
            reason=f"integrity leak: {', '.join(leaks)}",
        )
    return _gate(
        "D4",
        passed=True,
        severity=GateSeverity.HARD,
        reason="zero lookahead / current-id / unit-change / amendment-rewrite in sample",
    )


def evaluate_d5_mapping_terminals(
    *,
    period_valid_mapping: bool | None,
    terminal_economics_complete: bool | None,
) -> PeadGateResult:
    if period_valid_mapping is None or terminal_economics_complete is None:
        return _gate(
            "D5",
            passed=False,
            severity=GateSeverity.HARD,
            reason="mapping/terminals not measured — fail closed",
        )
    if period_valid_mapping and terminal_economics_complete:
        return _gate(
            "D5",
            passed=True,
            severity=GateSeverity.HARD,
            reason="period-valid mapping and terminal economics complete for included rows",
        )
    parts = []
    if not period_valid_mapping:
        parts.append("period_valid_mapping")
    if not terminal_economics_complete:
        parts.append("terminal_economics")
    return _gate(
        "D5",
        passed=False,
        severity=GateSeverity.HARD,
        reason=f"mapping/terminals fail: {', '.join(parts)}",
    )


def evaluate_d6_fold_floors(
    *,
    max_prior_seasonal_changes: int | None,
    annual_test_folds: int | None,
    min_prior: int | None = None,
    min_folds: int | None = None,
) -> PeadGateResult:
    need_prior = PROTOCOL.min_prior_seasonal_changes if min_prior is None else min_prior
    need_folds = PROTOCOL.min_annual_test_folds if min_folds is None else min_folds
    if max_prior_seasonal_changes is None or annual_test_folds is None:
        return _gate(
            "D6",
            passed=False,
            severity=GateSeverity.HARD,
            reason="fold floors not measured — fail closed",
        )
    prior_ok = max_prior_seasonal_changes >= need_prior
    folds_ok = annual_test_folds >= need_folds
    if prior_ok and folds_ok:
        return _gate(
            "D6",
            passed=True,
            severity=GateSeverity.HARD,
            reason=(
                f"warmup prior_changes={max_prior_seasonal_changes}>={need_prior}; "
                f"annual_folds={annual_test_folds}>={need_folds}"
            ),
        )
    return _gate(
        "D6",
        passed=False,
        severity=GateSeverity.HARD,
        reason=(
            f"underidentified: prior_changes={max_prior_seasonal_changes} "
            f"(need>={need_prior}); annual_folds={annual_test_folds} (need>={need_folds})"
        ),
    )


def evaluate_d7_reconcile(*, reconcile_pass: bool | None) -> PeadGateResult:
    if reconcile_pass is None:
        return _gate(
            "D7",
            passed=False,
            severity=GateSeverity.HARD,
            reason="stratified reconcile not measured — fail closed",
        )
    if reconcile_pass:
        return _gate(
            "D7",
            passed=True,
            severity=GateSeverity.HARD,
            reason="stratified reconcile sample met predeclared pass criteria",
        )
    return _gate(
        "D7",
        passed=False,
        severity=GateSeverity.HARD,
        reason="stratified reconcile sample failed predeclared pass criteria",
    )


def evaluate_pead_f0_gates(evidence: PeadF0Evidence) -> PeadF0GateReport:
    gates = (
        evaluate_d0_protocol(
            protocol_present=evidence.protocol_present,
            trial_ledger_present=evidence.trial_ledger_present,
        ),
        evaluate_d1_original_eps(
            reconstructable=evidence.original_eps_reconstructable
        ),
        evaluate_d2_original_revenue(
            reconstructable=evidence.original_revenue_reconstructable
        ),
        evaluate_d3_known_time(
            exact_known_time_proven=evidence.exact_known_time_proven,
            policy=evidence.known_time_policy,
            policy_applied_consistently=evidence.known_time_policy_applied_consistently,
        ),
        evaluate_d4_integrity(
            lookahead_detected=evidence.lookahead_detected,
            current_id_leakage=evidence.current_id_leakage,
            silent_unit_change=evidence.silent_unit_change,
            amendment_rewrite=evidence.amendment_rewrite,
        ),
        evaluate_d5_mapping_terminals(
            period_valid_mapping=evidence.period_valid_mapping,
            terminal_economics_complete=evidence.terminal_economics_complete,
        ),
        evaluate_d6_fold_floors(
            max_prior_seasonal_changes=evidence.max_prior_seasonal_changes,
            annual_test_folds=evidence.annual_test_folds,
        ),
        evaluate_d7_reconcile(reconcile_pass=evidence.reconcile_pass),
    )
    hard = [g for g in gates if g.severity == GateSeverity.HARD]
    all_hard = all(g.passed for g in hard)
    return PeadF0GateReport(
        gates=gates,
        all_hard_gates_passed=all_hard,
        f2_tape_eligible=all_hard,
        capital_go=False,
        verdict="f2_tape_eligible" if all_hard else "kill_line",
    )


def passing_evidence(**overrides: object) -> PeadF0Evidence:
    """Synthetic full-pass evidence for unit tests / dry runs (not a live audit)."""
    base = dict(
        protocol_present=True,
        trial_ledger_present=True,
        original_eps_reconstructable=True,
        original_revenue_reconstructable=True,
        exact_known_time_proven=False,
        known_time_policy=KnownTimePolicy.SECOND_OPEN_DATE_ONLY,
        known_time_policy_applied_consistently=True,
        lookahead_detected=False,
        current_id_leakage=False,
        silent_unit_change=False,
        amendment_rewrite=False,
        period_valid_mapping=True,
        terminal_economics_complete=True,
        max_prior_seasonal_changes=8,
        annual_test_folds=10,
        reconcile_pass=True,
        coverage_included=1000,
        coverage_rejected=50,
        source_label="synthetic_pass",
    )
    base.update(overrides)
    return PeadF0Evidence(**base)  # type: ignore[arg-type]


def build_pead_f0_artifact(
    *,
    evidence: PeadF0Evidence,
    gate_report: PeadF0GateReport,
    protocol: ProtocolConfig = PROTOCOL,
) -> dict:
    """JSON-serializable F0 research artifact (no multi-GB dependency)."""
    return {
        "experiment": protocol.experiment_id,
        "line": protocol.line,
        "status": "complete",
        "protocol": asdict(protocol),
        "known_time_policy": str(evidence.known_time_policy),
        "exact_known_time_proven": evidence.exact_known_time_proven,
        "coverage": {
            "included": evidence.coverage_included,
            "rejected": evidence.coverage_rejected,
            "source_label": evidence.source_label,
        },
        "gates": gate_report.to_dict(),
        "capital_go": False,
        "pass_meaning": "f2_tape_eligible_only",
        "residual_claim": "hard_frozen",
        "returns_measured": False,
        "e1_status": "not_started",
        "f2_tape_eligible": gate_report.f2_tape_eligible,
    }
