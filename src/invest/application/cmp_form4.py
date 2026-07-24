"""CMP-B — Cohen–Malloy–Pomorski opportunistic Form-4 baseline (pure helpers).

Primary seam for PRD #79 / ADR 0003. Stages C (classification + event object)
and D (density / power). Stage E1 returns helpers exist only as frozen protocol
stubs; the research driver must refuse E1 without an explicit human go.

This module does **not** share verdict paths with CFOB purchase-cluster kill
(#76). Shared seams are qualification filters, CIK mapping, habitat, and
MDS arithmetic — not the cluster object.

No I/O. ``capital_go`` is false in every artifact this module builds.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from math import sqrt

from invest.domain.models import InsiderTransaction


class GateSeverity(StrEnum):
    HARD = "hard"
    INFO = "info"


class Verdict(StrEnum):
    """Dual-exit vocabulary. ``capital_go`` is never among these."""

    KILL_LINE = "kill_line"
    UNDERPOWERED_STOP = "underpowered_stop"
    STAGE_PASS = "stage_pass"
    IMPLEMENTABILITY_ELIGIBLE = "implementability_eligible"


class CmpClass(StrEnum):
    """Point-in-time CMP label for one reporting person at one evaluation time."""

    OPPORTUNISTIC = "opportunistic"
    ROUTINE = "routine"
    UNCLASSIFIED = "unclassified"


@dataclass(frozen=True)
class ProtocolConfig:
    """Frozen CMP opportunistic baseline protocol (PRD #79 grill 2026-07-22).

    Changing any field is a new trial and must be recorded as such.
    """

    line: str = "cmp-opportunistic-form4-baseline"
    experiment_id: str = "cmp-b-c-d"
    capital_go: bool = False

    # Qualifying purchase (same freezes as CFOB purchase filters)
    transaction_code: str = "P"
    min_gross_value: Decimal = Decimal("10000")
    staleness_cap_days: int = 10

    # CMP classification window
    history_years: int = 3

    # Universe (habitat floor; ADR 0002)
    min_price: Decimal = Decimal("5")
    gate_on_min_price: bool = False
    min_dollar_volume: Decimal = Decimal("2000000")
    dollar_volume_window: int = 20
    min_history_bars: int = 252
    secondary_min_dollar_volume: Decimal = Decimal("10000000")

    # Density floors (bind on de-overlapped opportunistic n)
    min_events: int = 7500
    min_contributing_years: int = 12
    min_year_share: float = 0.02
    max_year_share: float = 0.25

    # Power
    horizon_sessions: int = 60
    mds_bar: float = 0.0125
    excess_dispersion: float = 0.38
    power_z: float = 2.8

    # Integrity
    min_mapping_rate: float = 0.90

    # E1 bars (frozen; evaluated only after human go)
    future_min_clustered_t: float = 3.0
    future_trimmed_min_t: float = 2.0
    future_winsor_tail: float = 0.01
    future_primary_cost_bps: float = 25.0
    future_placebo_draws: int = 100
    future_placebo_seed: int = 79_2026_07_22


PROTOCOL = ProtocolConfig()


@dataclass(frozen=True)
class CmpGateResult:
    id: str
    passed: bool
    severity: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CmpGateReport:
    gates: tuple[CmpGateResult, ...]
    all_hard_gates_passed: bool
    capital_go: bool
    verdict: str

    def to_dict(self) -> dict:
        return {
            "gates": [g.to_dict() for g in self.gates],
            "all_hard_gates_passed": self.all_hard_gates_passed,
            "capital_go": self.capital_go,
            "verdict": self.verdict,
        }


@dataclass(frozen=True)
class ClassificationCounts:
    """How qualifying purchases split under point-in-time CMP labels."""

    total_purchases: int = 0
    opportunistic: int = 0
    routine: int = 0
    unclassified: int = 0
    opportunistic_events: int = 0
    routine_events: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PurchaseEvent:
    """One CMP-classified purchase event (issuer × person × filing known-time)."""

    trading_symbol: str
    issuer_cik: str
    owner_cik: str
    known_time: date
    first_transaction_date: date
    last_transaction_date: date
    purchase_count: int
    gross_value: Decimal
    cmp_class: CmpClass

    @property
    def year(self) -> int:
        return self.known_time.year


def _gate(gate_id: str, *, passed: bool, severity: GateSeverity, reason: str) -> CmpGateResult:
    return CmpGateResult(id=gate_id, passed=passed, severity=str(severity), reason=reason)


# --- CMP classification (point-in-time) --------------------------------------


def classify_at(
    history: Sequence[tuple[date, int, int]],
    *,
    evaluation_known_time: date,
    config: ProtocolConfig = PROTOCOL,
) -> CmpClass:
    """Classify one reporting person at one evaluation known-time.

    ``history`` is a sequence of ``(known_time, trade_year, trade_month)`` for
    that person's prior trades. Only rows with ``known_time`` **strictly
    before** ``evaluation_known_time`` are used — look-ahead into contemporaneous
    or future filings is forbidden.

    Protocol (PRD #79): require activity in each of the prior three calendar
    years relative to the evaluation known-time's year. If the person traded in
    the **same calendar month** in each of those three years → routine; else
    among three-year traders → opportunistic; else unclassified.
    """

    prior = [
        (known, year, month)
        for known, year, month in history
        if known < evaluation_known_time
    ]
    if not prior:
        return CmpClass.UNCLASSIFIED

    evaluation_year = evaluation_known_time.year
    required_years = {
        evaluation_year - offset for offset in range(1, config.history_years + 1)
    }
    months_by_year: dict[int, set[int]] = defaultdict(set)
    for _, year, month in prior:
        if year in required_years:
            months_by_year[year].add(month)

    if any(year not in months_by_year or not months_by_year[year] for year in required_years):
        return CmpClass.UNCLASSIFIED

    shared_months = set.intersection(*(months_by_year[year] for year in required_years))
    if shared_months:
        return CmpClass.ROUTINE
    return CmpClass.OPPORTUNISTIC


def history_rows_from_transactions(
    transactions: Iterable[InsiderTransaction],
) -> dict[str, list[tuple[date, int, int]]]:
    """Build per-owner history rows from raw tape transactions.

    Uses filing_date as known-time and transaction_date year/month for the
    calendar pattern. Any transaction code may contribute history so the
    classification is not circular on the qualified-purchase filter alone.
    """

    by_owner: dict[str, list[tuple[date, int, int]]] = defaultdict(list)
    for txn in transactions:
        by_owner[txn.owner_cik].append(
            (txn.filing_date, txn.transaction_date.year, txn.transaction_date.month)
        )
    for owner, rows in by_owner.items():
        by_owner[owner] = sorted(rows, key=lambda row: (row[0], row[1], row[2]))
    return dict(by_owner)


def classify_purchase(
    purchase: InsiderTransaction,
    *,
    owner_history: Sequence[tuple[date, int, int]],
    config: ProtocolConfig = PROTOCOL,
) -> CmpClass:
    """Classify one qualifying purchase using only prior known history."""

    return classify_at(
        owner_history,
        evaluation_known_time=purchase.filing_date,
        config=config,
    )


# --- Event construction ------------------------------------------------------


def build_purchase_events(
    purchases: Iterable[InsiderTransaction],
    *,
    history_by_owner: Mapping[str, Sequence[tuple[date, int, int]]],
    config: ProtocolConfig = PROTOCOL,
) -> tuple[tuple[PurchaseEvent, ...], ClassificationCounts]:
    """Collapse qualifying purchases into CMP-classified events.

    Event key: issuer trading symbol × issuer CIK × owner CIK × filing known-time.
    Multiple same-day purchases for that key aggregate dollar value into one event.
    """

    # First pass: classify each purchase row
    labeled: list[tuple[InsiderTransaction, CmpClass]] = []
    for purchase in purchases:
        label = classify_purchase(
            purchase,
            owner_history=history_by_owner.get(purchase.owner_cik, ()),
            config=config,
        )
        labeled.append((purchase, label))

    # Aggregate by event key
    buckets: dict[
        tuple[str, str, str, date],
        list[tuple[InsiderTransaction, CmpClass]],
    ] = defaultdict(list)
    for purchase, label in labeled:
        key = (
            purchase.trading_symbol,
            purchase.issuer_cik,
            purchase.owner_cik,
            purchase.filing_date,
        )
        buckets[key].append((purchase, label))

    events: list[PurchaseEvent] = []
    for (symbol, issuer_cik, owner_cik, known_time), members in buckets.items():
        # Same key shares one filing known-time; labels must agree (same history)
        labels = {label for _, label in members}
        if len(labels) != 1:
            # Defensive: history is per-owner and known-time is identical, so
            # labels cannot diverge under a pure function. Fail closed.
            raise ValueError(
                f"inconsistent CMP labels for event {symbol}/{owner_cik}/{known_time}: {labels}"
            )
        label = next(iter(labels))
        tx_dates = [p.transaction_date for p, _ in members]
        events.append(
            PurchaseEvent(
                trading_symbol=symbol,
                issuer_cik=issuer_cik,
                owner_cik=owner_cik,
                known_time=known_time,
                first_transaction_date=min(tx_dates),
                last_transaction_date=max(tx_dates),
                purchase_count=len(members),
                gross_value=sum((p.gross_value for p, _ in members), Decimal(0)),
                cmp_class=label,
            )
        )

    events_sorted = tuple(sorted(events, key=lambda e: (e.known_time, e.trading_symbol, e.owner_cik)))
    opportunistic = sum(1 for _, label in labeled if label is CmpClass.OPPORTUNISTIC)
    routine = sum(1 for _, label in labeled if label is CmpClass.ROUTINE)
    unclassified = sum(1 for _, label in labeled if label is CmpClass.UNCLASSIFIED)
    counts = ClassificationCounts(
        total_purchases=len(labeled),
        opportunistic=opportunistic,
        routine=routine,
        unclassified=unclassified,
        opportunistic_events=sum(1 for e in events_sorted if e.cmp_class is CmpClass.OPPORTUNISTIC),
        routine_events=sum(1 for e in events_sorted if e.cmp_class is CmpClass.ROUTINE),
    )
    return events_sorted, counts


def opportunistic_events(events: Sequence[PurchaseEvent]) -> tuple[PurchaseEvent, ...]:
    """Primary cohort: opportunistic only."""

    return tuple(e for e in events if e.cmp_class is CmpClass.OPPORTUNISTIC)


def routine_events(events: Sequence[PurchaseEvent]) -> tuple[PurchaseEvent, ...]:
    """Negative-control cohort (diagnostic; never primary)."""

    return tuple(e for e in events if e.cmp_class is CmpClass.ROUTINE)


# --- De-overlap (first-wins, ticker horizon) ---------------------------------


def de_overlap_events(
    events: Sequence[PurchaseEvent],
    *,
    horizon_sessions: int | None = None,
    sessions_by_symbol: Mapping[str, Sequence[date]] | None = None,
    config: ProtocolConfig = PROTOCOL,
) -> tuple[PurchaseEvent, ...]:
    """First-wins: a ticker cannot re-enter until its h60 window completes.

    Density floors bind on the de-overlapped **opportunistic** cohort.
    """

    horizon = horizon_sessions if horizon_sessions is not None else config.horizon_sessions
    kept: list[PurchaseEvent] = []
    blocked_until: dict[str, date] = {}

    for event in sorted(events, key=lambda e: (e.known_time, e.trading_symbol, e.owner_cik)):
        block = blocked_until.get(event.trading_symbol)
        if block is not None and event.known_time <= block:
            continue
        kept.append(event)
        sessions = sessions_by_symbol.get(event.trading_symbol) if sessions_by_symbol else None
        if sessions and sessions[0] > event.known_time:
            raise ValueError(
                f"session calendar for {event.trading_symbol} starts "
                f"{sessions[0]}, after event known-time {event.known_time}"
            )
        if sessions:
            future = [s for s in sessions if s > event.known_time]
            close = future[horizon - 1] if len(future) >= horizon else None
            blocked_until[event.trading_symbol] = close or date.max
        else:
            blocked_until[event.trading_symbol] = event.known_time + timedelta(
                days=round(horizon * 7 / 5)
            )

    return tuple(kept)


# --- Density statistics ------------------------------------------------------


def year_shares(events: Sequence[PurchaseEvent]) -> dict[int, float]:
    if not events:
        return {}
    counts: dict[int, int] = defaultdict(int)
    for event in events:
        counts[event.year] += 1
    total = len(events)
    return {year: count / total for year, count in sorted(counts.items())}


def min_detectable_size(*, n_events: int, config: ProtocolConfig = PROTOCOL) -> float:
    if n_events <= 0:
        return float("inf")
    return config.power_z * config.excess_dispersion / sqrt(n_events)


def required_events(*, config: ProtocolConfig = PROTOCOL) -> int:
    return int((config.power_z * config.excess_dispersion / config.mds_bar) ** 2) + 1


# --- Stage C gates (no returns) ----------------------------------------------


def evaluate_c1_parse(
    *,
    archives_expected: int | None,
    archives_parsed: int | None,
    reconciled: bool | None,
) -> CmpGateResult:
    """Tape parse / reconcile fail-closed (F0 spirit from CFOB, CMP gate ids)."""

    if archives_expected is None or archives_parsed is None:
        return _gate(
            "C1-parse",
            passed=False,
            severity=GateSeverity.HARD,
            reason="parse coverage unmeasured — fail closed",
        )
    if archives_expected <= 0:
        return _gate(
            "C1-parse",
            passed=False,
            severity=GateSeverity.HARD,
            reason="no archives expected — fail closed",
        )
    if archives_parsed < archives_expected:
        return _gate(
            "C1-parse",
            passed=False,
            severity=GateSeverity.HARD,
            reason=(
                f"archives parsed={archives_parsed} < expected={archives_expected}"
            ),
        )
    if reconciled is None:
        return _gate(
            "C1-parse",
            passed=False,
            severity=GateSeverity.HARD,
            reason="EDGAR reconcile unmeasured — fail closed",
        )
    if not reconciled:
        return _gate(
            "C1-parse",
            passed=False,
            severity=GateSeverity.HARD,
            reason="EDGAR reconcile failed — fail closed",
        )
    return _gate(
        "C1-parse",
        passed=True,
        severity=GateSeverity.HARD,
        reason=(
            f"archives parsed={archives_parsed}/{archives_expected}; reconcile ok"
        ),
    )


def evaluate_c2_map(
    *,
    mapped: int,
    total: int,
    config: ProtocolConfig = PROTOCOL,
) -> CmpGateResult:
    if total <= 0:
        return _gate(
            "C2-map",
            passed=False,
            severity=GateSeverity.HARD,
            reason="no qualifying purchases to map — fail closed",
        )
    rate = mapped / total
    passed = rate >= config.min_mapping_rate
    return _gate(
        "C2-map",
        passed=passed,
        severity=GateSeverity.HARD,
        reason=f"mapping rate={rate:.4f} ({mapped}/{total}) vs floor {config.min_mapping_rate}",
    )


def evaluate_c3_class(*, counts: ClassificationCounts) -> CmpGateResult:
    """Both opportunistic and routine counts must be reported; primary is opp only."""

    if counts.total_purchases <= 0:
        return _gate(
            "C3-class",
            passed=False,
            severity=GateSeverity.HARD,
            reason="no classified purchases — fail closed",
        )
    if counts.opportunistic <= 0:
        return _gate(
            "C3-class",
            passed=False,
            severity=GateSeverity.HARD,
            reason=(
                f"opportunistic=0 (routine={counts.routine}, "
                f"unclassified={counts.unclassified}) — no primary object"
            ),
        )
    if counts.routine <= 0:
        return _gate(
            "C3-class",
            passed=False,
            severity=GateSeverity.HARD,
            reason=(
                f"routine=0 with opportunistic={counts.opportunistic} — "
                "negative control empty; classification integrity fail"
            ),
        )
    return _gate(
        "C3-class",
        passed=True,
        severity=GateSeverity.HARD,
        reason=(
            f"opportunistic={counts.opportunistic} "
            f"(events={counts.opportunistic_events}); "
            f"routine={counts.routine} (events={counts.routine_events}); "
            f"unclassified={counts.unclassified}; primary=opportunistic only"
        ),
    )


def evaluate_c4_protocol(
    *,
    protocol_present: bool,
    trial_ledger_present: bool,
    primary_is_cluster: bool = False,
) -> CmpGateResult:
    if primary_is_cluster:
        return _gate(
            "C4-protocol",
            passed=False,
            severity=GateSeverity.HARD,
            reason="cluster object used as primary — forbidden under #79 path",
        )
    if protocol_present and trial_ledger_present:
        return _gate(
            "C4-protocol",
            passed=True,
            severity=GateSeverity.HARD,
            reason="protocol freeze and trial ledger present; primary=CMP opportunistic",
        )
    return _gate(
        "C4-protocol",
        passed=False,
        severity=GateSeverity.HARD,
        reason=(
            f"protocol_present={protocol_present}; "
            f"trial_ledger_present={trial_ledger_present}"
        ),
    )


def evaluate_stage_c(
    *,
    archives_expected: int | None,
    archives_parsed: int | None,
    reconciled: bool | None,
    mapped: int,
    total: int,
    counts: ClassificationCounts,
    protocol_present: bool,
    trial_ledger_present: bool,
    primary_is_cluster: bool = False,
    config: ProtocolConfig = PROTOCOL,
) -> CmpGateReport:
    gates = (
        evaluate_c1_parse(
            archives_expected=archives_expected,
            archives_parsed=archives_parsed,
            reconciled=reconciled,
        ),
        evaluate_c2_map(mapped=mapped, total=total, config=config),
        evaluate_c3_class(counts=counts),
        evaluate_c4_protocol(
            protocol_present=protocol_present,
            trial_ledger_present=trial_ledger_present,
            primary_is_cluster=primary_is_cluster,
        ),
    )
    return _report(gates, power_fail_ids=frozenset())


# --- Stage D gates (no returns) ----------------------------------------------


def evaluate_d1_volume(
    *, de_overlapped_events: int, config: ProtocolConfig = PROTOCOL
) -> CmpGateResult:
    passed = de_overlapped_events >= config.min_events
    mds = min_detectable_size(n_events=de_overlapped_events, config=config)
    return _gate(
        "D1-volume",
        passed=passed,
        severity=GateSeverity.HARD,
        reason=(
            f"de-overlapped opportunistic events={de_overlapped_events} "
            f"vs floor {config.min_events} (MDS={mds:.4f} vs bar {config.mds_bar})"
        ),
    )


def evaluate_d2_year_spread(
    *, shares: Mapping[int, float], config: ProtocolConfig = PROTOCOL
) -> CmpGateResult:
    if not shares:
        return _gate(
            "D2-spread",
            passed=False,
            severity=GateSeverity.HARD,
            reason="no events — spread not measurable, fail closed",
        )
    contributing = sum(1 for share in shares.values() if share >= config.min_year_share)
    passed = contributing >= config.min_contributing_years
    return _gate(
        "D2-spread",
        passed=passed,
        severity=GateSeverity.HARD,
        reason=(
            f"years contributing >={config.min_year_share:.0%}: {contributing} "
            f"vs floor {config.min_contributing_years}"
        ),
    )


def evaluate_d3_year_mass(
    *, shares: Mapping[int, float], config: ProtocolConfig = PROTOCOL
) -> CmpGateResult:
    if not shares:
        return _gate(
            "D3-year-mass",
            passed=False,
            severity=GateSeverity.HARD,
            reason="no events — year mass not measurable, fail closed",
        )
    worst_year, worst_share = max(shares.items(), key=lambda item: item[1])
    passed = worst_share <= config.max_year_share
    return _gate(
        "D3-year-mass",
        passed=passed,
        severity=GateSeverity.HARD,
        reason=(
            f"max year event share={worst_share:.4f} ({worst_year}) "
            f"vs cap {config.max_year_share}"
        ),
    )


def evaluate_d4_mds(
    *, de_overlapped_events: int, config: ProtocolConfig = PROTOCOL
) -> CmpGateResult:
    mds = min_detectable_size(n_events=de_overlapped_events, config=config)
    passed = mds <= config.mds_bar
    return _gate(
        "D4-mds",
        passed=passed,
        severity=GateSeverity.HARD,
        reason=f"MDS={mds:.4f} at n={de_overlapped_events} vs bar {config.mds_bar}",
    )


def evaluate_stage_d(
    *,
    de_overlapped_events: int,
    shares: Mapping[int, float],
    config: ProtocolConfig = PROTOCOL,
) -> CmpGateReport:
    gates = (
        evaluate_d1_volume(de_overlapped_events=de_overlapped_events, config=config),
        evaluate_d2_year_spread(shares=shares, config=config),
        evaluate_d3_year_mass(shares=shares, config=config),
        evaluate_d4_mds(de_overlapped_events=de_overlapped_events, config=config),
    )
    return _report(
        gates,
        power_fail_ids=frozenset({"D1-volume", "D4-mds"}),
    )


# --- Reports / artifact ------------------------------------------------------


def _report(
    gates: Sequence[CmpGateResult],
    *,
    power_fail_ids: frozenset[str],
) -> CmpGateReport:
    hard = [g for g in gates if g.severity == str(GateSeverity.HARD)]
    hard_passed = all(g.passed for g in hard)
    if hard_passed:
        verdict = str(Verdict.STAGE_PASS)
    else:
        failed = {g.id for g in hard if not g.passed}
        if failed and failed <= power_fail_ids:
            verdict = str(Verdict.UNDERPOWERED_STOP)
        else:
            verdict = str(Verdict.KILL_LINE)
    return CmpGateReport(
        gates=tuple(gates),
        all_hard_gates_passed=hard_passed,
        capital_go=False,
        verdict=verdict,
    )


def combine_stage_reports(*reports: CmpGateReport) -> CmpGateReport:
    if not reports:
        raise ValueError("combine_stage_reports requires at least one report")
    gates = tuple(gate for report in reports for gate in report.gates)
    # Power-only underpowered if every failed hard gate is a D power id
    return _report(gates, power_fail_ids=frozenset({"D1-volume", "D4-mds"}))


def require_e1_authorisation(*, e1_flag: bool, human_go_recorded: bool) -> None:
    """Driver seam: refuse E1 unless both CLI flag and human-go record exist."""

    if not e1_flag:
        raise PermissionError(
            "Stage E1 refused: pass --e1 only after human go is recorded "
            "(PRD #79 authorises C+D only by default)"
        )
    if not human_go_recorded:
        raise PermissionError(
            "Stage E1 refused: human go timestamp/SHA must be recorded in results "
            "before --e1 measurement (PRD #79 scar: do not auto-run first edge number)"
        )


def evaluate_stage_e1_authorisation(
    *, e1_flag: bool, human_go_recorded: bool
) -> CmpGateResult:
    """Info/hard gate surface for the driver — never measures returns itself."""

    try:
        require_e1_authorisation(e1_flag=e1_flag, human_go_recorded=human_go_recorded)
    except PermissionError as exc:
        return _gate(
            "E1-auth",
            passed=False,
            severity=GateSeverity.HARD,
            reason=str(exc),
        )
    return _gate(
        "E1-auth",
        passed=True,
        severity=GateSeverity.HARD,
        reason="E1 authorised by --e1 flag and recorded human go",
    )


def build_cmp_artifact(
    *,
    stage: str,
    report: CmpGateReport,
    qualification_counts: Mapping[str, object],
    classification: ClassificationCounts,
    raw_opportunistic_events: int,
    universe_eligible_events: int,
    de_overlapped_events: int,
    shares: Mapping[int, float],
    mode: str,
    git_sha: str | None = None,
    notes: Mapping[str, object] | None = None,
    config: ProtocolConfig = PROTOCOL,
) -> dict:
    """Measurement artifact. ``capital_go`` is false by construction."""

    return {
        "stage": stage,
        "line": config.line,
        "experiment_id": config.experiment_id,
        "git_sha": git_sha,
        "verdict": report.verdict,
        "capital_go": False,
        "implementability_eligible": False,
        "protocol": {
            "transaction_code": config.transaction_code,
            "min_gross_value": str(config.min_gross_value),
            "staleness_cap_days": config.staleness_cap_days,
            "history_years": config.history_years,
            "cmp_primary_class": CmpClass.OPPORTUNISTIC.value,
            "cmp_negative_control": CmpClass.ROUTINE.value,
            "cluster_object_primary": False,
            "min_price": str(config.min_price),
            "gate_on_min_price": config.gate_on_min_price,
            "min_price_role": (
                "primary_habitat_gate"
                if config.gate_on_min_price
                else "diagnostic_on_adjusted_close"
            ),
            "min_dollar_volume": str(config.min_dollar_volume),
            "min_dollar_volume_role": "primary_habitat_gate",
            "dollar_volume_window": config.dollar_volume_window,
            "min_history_bars": config.min_history_bars,
            "secondary_min_dollar_volume": str(config.secondary_min_dollar_volume),
            "min_events": config.min_events,
            "min_contributing_years": config.min_contributing_years,
            "min_year_share": config.min_year_share,
            "max_year_share": config.max_year_share,
            "mds_bar": config.mds_bar,
            "excess_dispersion": config.excess_dispersion,
            "power_z": config.power_z,
            "horizon_sessions": config.horizon_sessions,
            "min_mapping_rate": config.min_mapping_rate,
            "future_e1_bars": {
                "min_clustered_t": config.future_min_clustered_t,
                "trimmed_min_t": config.future_trimmed_min_t,
                "winsor_tail": config.future_winsor_tail,
                "primary_cost_bps": config.future_primary_cost_bps,
                "placebo_draws": config.future_placebo_draws,
                "placebo_seed": config.future_placebo_seed,
            },
            "known_time_axis": "filing_date_day_granular",
            "known_time_conservatism": (
                "SEC Insider Transactions Data Sets carry no acceptance timestamp; "
                "entry is the open of the first trading day strictly after filing_date"
            ),
            "entry_rule": "next_open_after_filing_date",
            "classification_rule": (
                f"activity in each of prior {config.history_years} calendar years "
                "using only known_time < evaluation; same calendar month in all "
                "three years → routine; else opportunistic; else unclassified"
            ),
        },
        "counts": dict(qualification_counts),
        "classification": classification.to_dict(),
        "events": {
            "raw_opportunistic": raw_opportunistic_events,
            "universe_eligible_opportunistic": universe_eligible_events,
            "de_overlapped_opportunistic": de_overlapped_events,
            "required_for_mds_bar": required_events(config=config),
            "mds_at_measured_n": min_detectable_size(
                n_events=de_overlapped_events, config=config
            ),
            "year_shares": {str(year): share for year, share in shares.items()},
        },
        "gates": report.to_dict()["gates"],
        "all_hard_gates_passed": report.all_hard_gates_passed,
        "mode": mode,
        "notes": dict(notes or {}),
    }
