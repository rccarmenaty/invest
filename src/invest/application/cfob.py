"""CFOB — Cluster Form-4 Opportunistic Buys: pure Stage D / F0 helpers.

Primary seam for the insider purchase-cluster line (PRD #76, grilled
2026-07-21). Holds qualification filters, cluster construction, de-overlap,
and the fail-closed D (density) and F0 (integrity) gates. No I/O.

Stage E1 (returns) is authorised separately and is not implemented here.
``capital_go`` is false in every artifact this module builds.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from math import sqrt
from typing import Iterable, Mapping, Sequence

from invest.domain.models import InsiderTransaction


class GateSeverity(StrEnum):
    HARD = "hard"
    INFO = "info"


class Verdict(StrEnum):
    """Dual-exit vocabulary. ``capital_go`` is never among these."""

    KILL_LINE = "kill_line"
    UNDERPOWERED_STOP = "underpowered_stop"
    STAGE_PASS = "stage_pass"


@dataclass(frozen=True)
class ProtocolConfig:
    """Frozen CFOB protocol. Every threshold here was set in the PRD #76 grill.

    Changing any field is a new trial and must be recorded as such.
    """

    line: str = "cfob-insider-purchase-clusters"
    experiment_id: str = "cfob-d-f0"
    capital_go: bool = False

    # Qualifying purchase
    transaction_code: str = "P"
    min_gross_value: Decimal = Decimal("10000")
    staleness_cap_days: int = 10

    # Cluster
    cluster_window_days: int = 30
    min_distinct_insiders: int = 2
    secondary_cluster_window_days: int = 60

    # Universe (habitat floor; house $10M screen is a secondary diagnostic)
    min_price: Decimal = Decimal("5")
    min_dollar_volume: Decimal = Decimal("2000000")
    dollar_volume_window: int = 20
    min_history_bars: int = 252
    secondary_min_dollar_volume: Decimal = Decimal("10000000")

    # Density floors (bind on the de-overlapped cohort)
    min_clusters: int = 7500
    min_contributing_years: int = 12
    min_year_share: float = 0.02
    max_year_share: float = 0.25

    # Power (Gate-1a measured sigma; CMP effect after ~50% publication decay)
    horizon_sessions: int = 60
    mds_bar: float = 0.0125
    excess_dispersion: float = 0.38
    power_z: float = 2.8

    # F0 integrity
    min_mapping_rate: float = 0.90
    max_unmapped_rate_ratio: float = 3.0
    min_year_weight_for_composition: float = 0.01

    # E1 bars (frozen now, evaluated only under a separate authorisation)
    future_min_clustered_t: float = 3.0
    future_trimmed_min_t: float = 2.0
    future_winsor_tail: float = 0.01
    future_primary_cost_bps: float = 25.0
    future_placebo_draws: int = 100


PROTOCOL = ProtocolConfig()


@dataclass(frozen=True)
class PurchaseCluster:
    """Two or more distinct insiders buying one issuer inside the trade window."""

    trading_symbol: str
    issuer_cik: str
    known_time: date
    first_transaction_date: date
    last_transaction_date: date
    distinct_insiders: int
    purchase_count: int
    gross_value: Decimal

    @property
    def year(self) -> int:
        return self.known_time.year


@dataclass(frozen=True)
class CfobGateResult:
    id: str
    passed: bool
    severity: str
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CfobGateReport:
    gates: tuple[CfobGateResult, ...]
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
class QualificationCounts:
    """Why rows dropped out. Every exclusion is counted, never silent."""

    total_rows: int = 0
    qualified: int = 0
    wrong_code: int = 0
    disposals: int = 0
    below_size_floor: int = 0
    stale: int = 0
    amendment_superseded: int = 0
    unparseable_value: int = 0
    late_filed: int = 0
    indirect_ownership: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def _gate(gate_id: str, *, passed: bool, severity: GateSeverity, reason: str) -> CfobGateResult:
    return CfobGateResult(id=gate_id, passed=passed, severity=str(severity), reason=reason)


# --- Qualification -----------------------------------------------------------


def dedupe_amendments(
    transactions: Iterable[InsiderTransaction],
) -> tuple[tuple[InsiderTransaction, ...], int]:
    """Collapse Form 4/A amendments onto the trade they restate.

    An amendment supersedes the original for the same (owner, issuer,
    transaction date, shares) trade. The *original* filing date is kept as
    known-time: the market learned of the trade when it was first filed, and a
    later correction does not un-publish it.
    """

    ordered = sorted(transactions, key=lambda t: (t.filing_date, t.accession_number))
    originals = [t for t in ordered if not t.is_amendment]
    amendments = [t for t in ordered if t.is_amendment]

    def key(txn: InsiderTransaction) -> tuple[str, str, date, str]:
        return (txn.owner_cik, txn.issuer_cik, txn.transaction_date, txn.transaction_code)

    by_key: dict[tuple[str, str, date, str], list[InsiderTransaction]] = defaultdict(list)
    for original in originals:
        by_key[key(original)].append(original)

    superseded = 0
    for amendment in amendments:
        matched = by_key.get(key(amendment))
        if not matched:
            # An amendment with no original in view is itself the only record
            # of the trade — keep it rather than discard a real purchase.
            by_key[key(amendment)] = [amendment]
            continue
        superseded += len(matched)
        by_key[key(amendment)] = [
            InsiderTransaction(
                accession_number=amendment.accession_number,
                issuer_cik=amendment.issuer_cik,
                trading_symbol=amendment.trading_symbol,
                owner_cik=amendment.owner_cik,
                # The market learned of the trade when it was first filed; a
                # later correction does not un-publish it.
                filing_date=min(m.filing_date for m in matched),
                transaction_date=amendment.transaction_date,
                transaction_code=amendment.transaction_code,
                acquired_disposed=amendment.acquired_disposed,
                shares=amendment.shares,
                price_per_share=amendment.price_per_share,
                direct_ownership=amendment.direct_ownership,
                document_type=amendment.document_type,
                original_submission_date=amendment.original_submission_date,
                late_filing=amendment.late_filing,
            )
        ]

    deduped = [txn for group in by_key.values() for txn in group]
    return tuple(deduped), superseded


def qualifying_purchases(
    transactions: Iterable[InsiderTransaction],
    *,
    config: ProtocolConfig = PROTOCOL,
) -> tuple[tuple[InsiderTransaction, ...], QualificationCounts]:
    """Filter to code-P non-derivative acquisitions clearing size and staleness.

    Code P is "open market *or private* purchase" and the tape carries no field
    separating the two, so private purchases are included; the off-market-price
    share is an F0 diagnostic rather than a filter. Direct and indirect
    ownership both qualify.
    """

    deduped, superseded = dedupe_amendments(transactions)
    kept: list[InsiderTransaction] = []
    wrong_code = disposals = below_size = stale = unparseable = late = indirect = 0

    for txn in deduped:
        if txn.transaction_code != config.transaction_code:
            wrong_code += 1
            continue
        if txn.acquired_disposed != "A":
            disposals += 1
            continue
        if txn.shares <= 0 or txn.price_per_share <= 0:
            unparseable += 1
            continue
        if txn.gross_value < config.min_gross_value:
            below_size += 1
            continue
        lag = (txn.filing_date - txn.transaction_date).days
        if lag < 0 or lag > config.staleness_cap_days:
            stale += 1
            continue
        if txn.late_filing:
            late += 1
        if not txn.direct_ownership:
            indirect += 1
        kept.append(txn)

    counts = QualificationCounts(
        total_rows=len(deduped) + superseded,
        qualified=len(kept),
        wrong_code=wrong_code,
        disposals=disposals,
        below_size_floor=below_size,
        stale=stale,
        amendment_superseded=superseded,
        unparseable_value=unparseable,
        late_filed=late,
        indirect_ownership=indirect,
    )
    return tuple(kept), counts


# --- Cluster construction ----------------------------------------------------


def build_clusters(
    purchases: Iterable[InsiderTransaction],
    *,
    config: ProtocolConfig = PROTOCOL,
    window_days: int | None = None,
) -> tuple[PurchaseCluster, ...]:
    """Group qualifying purchases into clusters on the *trade*-date window.

    A cluster needs ``min_distinct_insiders`` distinct owners whose transaction
    dates fall inside ``window_days``. Known-time is the latest filing date in
    the cluster: entry cannot precede the moment the whole cluster is public.
    """

    window = timedelta(days=window_days if window_days is not None else config.cluster_window_days)
    by_issuer: dict[tuple[str, str], list[InsiderTransaction]] = defaultdict(list)
    for purchase in purchases:
        by_issuer[(purchase.trading_symbol, purchase.issuer_cik)].append(purchase)

    clusters: list[PurchaseCluster] = []
    for (symbol, issuer_cik), issuer_purchases in by_issuer.items():
        ordered = sorted(issuer_purchases, key=lambda t: (t.transaction_date, t.owner_cik))
        start = 0
        while start < len(ordered):
            anchor = ordered[start].transaction_date
            member_end = start
            while (
                member_end + 1 < len(ordered)
                and ordered[member_end + 1].transaction_date - anchor <= window
            ):
                member_end += 1
            members = ordered[start : member_end + 1]
            owners = {m.owner_cik for m in members}
            if len(owners) >= config.min_distinct_insiders:
                clusters.append(
                    PurchaseCluster(
                        trading_symbol=symbol,
                        issuer_cik=issuer_cik,
                        known_time=max(m.filing_date for m in members),
                        first_transaction_date=members[0].transaction_date,
                        last_transaction_date=members[-1].transaction_date,
                        distinct_insiders=len(owners),
                        purchase_count=len(members),
                        gross_value=sum((m.gross_value for m in members), Decimal(0)),
                    )
                )
                start = member_end + 1
            else:
                start += 1

    return tuple(sorted(clusters, key=lambda c: (c.known_time, c.trading_symbol)))


def de_overlap(
    clusters: Sequence[PurchaseCluster],
    *,
    horizon_sessions: int | None = None,
    sessions_by_symbol: Mapping[str, Sequence[date]] | None = None,
    config: ProtocolConfig = PROTOCOL,
) -> tuple[PurchaseCluster, ...]:
    """First-wins: a symbol cannot re-enter until its horizon closes.

    Overlapping windows on one firm are not independent observations and would
    inflate the clustered t-statistic. Density floors bind on this cohort.

    Without a session calendar the horizon is approximated in calendar days
    (sessions * 7 / 5), which is deliberately conservative — it excludes at
    least as much as the true session window would.
    """

    horizon = horizon_sessions if horizon_sessions is not None else config.horizon_sessions
    kept: list[PurchaseCluster] = []
    blocked_until: dict[str, date] = {}

    for cluster in sorted(clusters, key=lambda c: (c.known_time, c.trading_symbol)):
        block = blocked_until.get(cluster.trading_symbol)
        if block is not None and cluster.known_time <= block:
            continue
        kept.append(cluster)
        sessions = sessions_by_symbol.get(cluster.trading_symbol) if sessions_by_symbol else None
        if sessions:
            future = [s for s in sessions if s > cluster.known_time]
            close = future[horizon - 1] if len(future) >= horizon else None
            blocked_until[cluster.trading_symbol] = close or date.max
        else:
            blocked_until[cluster.trading_symbol] = cluster.known_time + timedelta(
                days=round(horizon * 7 / 5)
            )

    return tuple(kept)


# --- Density statistics ------------------------------------------------------


def year_shares(clusters: Sequence[PurchaseCluster]) -> dict[int, float]:
    if not clusters:
        return {}
    counts: dict[int, int] = defaultdict(int)
    for cluster in clusters:
        counts[cluster.year] += 1
    total = len(clusters)
    return {year: count / total for year, count in sorted(counts.items())}


def min_detectable_size(*, n_events: int, config: ProtocolConfig = PROTOCOL) -> float:
    """Minimum detectable excess at the configured power, given measured sigma.

    Calibrated from Gate-1a: mean +1.89% at clustered t=5.3 on n=11,489 implies
    an effective (post-date-clustering) dispersion near 38% at h60.
    """

    if n_events <= 0:
        return float("inf")
    return config.power_z * config.excess_dispersion / sqrt(n_events)


def required_events(*, config: ProtocolConfig = PROTOCOL) -> int:
    """Event count implied by the MDS bar — how the density floor was derived."""

    return int((config.power_z * config.excess_dispersion / config.mds_bar) ** 2) + 1


# --- Stage D gates -----------------------------------------------------------


def evaluate_d1_volume(
    *, de_overlapped_clusters: int, config: ProtocolConfig = PROTOCOL
) -> CfobGateResult:
    passed = de_overlapped_clusters >= config.min_clusters
    mds = min_detectable_size(n_events=de_overlapped_clusters, config=config)
    return _gate(
        "D1-volume",
        passed=passed,
        severity=GateSeverity.HARD,
        reason=(
            f"de-overlapped clusters={de_overlapped_clusters} vs floor {config.min_clusters} "
            f"(MDS={mds:.4f} vs bar {config.mds_bar})"
        ),
    )


def evaluate_d2_year_spread(
    *, shares: Mapping[int, float], config: ProtocolConfig = PROTOCOL
) -> CfobGateResult:
    if not shares:
        return _gate(
            "D2-spread",
            passed=False,
            severity=GateSeverity.HARD,
            reason="no clusters — spread not measurable, fail closed",
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


def evaluate_d3_year_concentration(
    *, shares: Mapping[int, float], config: ProtocolConfig = PROTOCOL
) -> CfobGateResult:
    if not shares:
        return _gate(
            "D3-concentration",
            passed=False,
            severity=GateSeverity.HARD,
            reason="no clusters — concentration not measurable, fail closed",
        )
    worst_year, worst_share = max(shares.items(), key=lambda item: item[1])
    passed = worst_share <= config.max_year_share
    return _gate(
        "D3-concentration",
        passed=passed,
        severity=GateSeverity.HARD,
        reason=(
            f"max year share={worst_share:.4f} ({worst_year}) vs cap {config.max_year_share}"
        ),
    )


# --- Stage F0 gates ----------------------------------------------------------


def evaluate_f0_protocol(
    *, protocol_present: bool, trial_ledger_present: bool
) -> CfobGateResult:
    missing = [
        name
        for name, present in (("protocol", protocol_present), ("trial_ledger", trial_ledger_present))
        if not present
    ]
    return _gate(
        "F0-protocol",
        passed=not missing,
        severity=GateSeverity.HARD,
        reason="protocol freeze and trial ledger present" if not missing else f"missing: {', '.join(missing)}",
    )


def evaluate_f1_mapping_rate(
    *, mapped: int, total: int, config: ProtocolConfig = PROTOCOL
) -> CfobGateResult:
    if total <= 0:
        return _gate(
            "F1-mapping",
            passed=False,
            severity=GateSeverity.HARD,
            reason="no purchases to map — fail closed",
        )
    rate = mapped / total
    return _gate(
        "F1-mapping",
        passed=rate >= config.min_mapping_rate,
        severity=GateSeverity.HARD,
        reason=f"mapping rate={rate:.4f} vs floor {config.min_mapping_rate}",
    )


def evaluate_f2_unmapped_composition(
    *,
    unmapped_by_year: Mapping[int, int],
    total_by_year: Mapping[int, int],
    config: ProtocolConfig = PROTOCOL,
) -> CfobGateResult:
    """Composition matters more than rate: a 97% mapping rate whose every
    failure sits in 2008 is worse than 91% spread evenly.

    Measured as disproportion, not absolute share — each year's own unmapped
    *rate* is compared to the global rate, so a small unmapped set cannot fail
    merely for being small.
    """

    unmapped_total = sum(unmapped_by_year.values())
    grand_total = sum(total_by_year.values())
    if unmapped_total == 0:
        return _gate(
            "F2-unmapped-composition",
            passed=True,
            severity=GateSeverity.HARD,
            reason="no unmapped purchases",
        )
    if grand_total <= 0:
        return _gate(
            "F2-unmapped-composition",
            passed=False,
            severity=GateSeverity.HARD,
            reason="year totals not measured — fail closed",
        )

    global_rate = unmapped_total / grand_total
    worst_year: int | None = None
    worst_rate = 0.0
    for year, year_total in total_by_year.items():
        if year_total <= 0 or year_total / grand_total < config.min_year_weight_for_composition:
            continue
        rate = unmapped_by_year.get(year, 0) / year_total
        if rate > worst_rate:
            worst_year, worst_rate = year, rate

    ceiling = global_rate * config.max_unmapped_rate_ratio
    passed = worst_year is None or worst_rate <= ceiling
    return _gate(
        "F2-unmapped-composition",
        passed=passed,
        severity=GateSeverity.HARD,
        reason=(
            f"worst-year unmapped rate={worst_rate:.4f} ({worst_year}) vs "
            f"{config.max_unmapped_rate_ratio}x global {global_rate:.4f} = {ceiling:.4f}"
        ),
    )


def evaluate_f3_reconcile(*, reconciled: bool | None) -> CfobGateResult:
    if reconciled is None:
        return _gate(
            "F3-reconcile",
            passed=False,
            severity=GateSeverity.HARD,
            reason="parsed counts not reconciled against SEC aggregates — fail closed",
        )
    return _gate(
        "F3-reconcile",
        passed=reconciled,
        severity=GateSeverity.HARD,
        reason="parsed counts reconcile against SEC aggregates"
        if reconciled
        else "parsed counts disagree with SEC aggregates",
    )


# --- Reports -----------------------------------------------------------------


def _report(gates: Sequence[CfobGateResult], *, stage: str) -> CfobGateReport:
    hard_passed = all(g.passed for g in gates if g.severity == str(GateSeverity.HARD))
    verdict = str(Verdict.STAGE_PASS) if hard_passed else str(Verdict.KILL_LINE)
    return CfobGateReport(
        gates=tuple(gates),
        all_hard_gates_passed=hard_passed,
        capital_go=False,
        verdict=verdict,
    )


def evaluate_stage_d(
    *,
    de_overlapped_clusters: int,
    shares: Mapping[int, float],
    config: ProtocolConfig = PROTOCOL,
) -> CfobGateReport:
    """Density verdict. A fail is ``kill_line`` and re-seals Full-Stop."""

    gates = (
        evaluate_d1_volume(de_overlapped_clusters=de_overlapped_clusters, config=config),
        evaluate_d2_year_spread(shares=shares, config=config),
        evaluate_d3_year_concentration(shares=shares, config=config),
    )
    return _report(gates, stage="D")


def evaluate_stage_f0(
    *,
    protocol_present: bool,
    trial_ledger_present: bool,
    mapped: int,
    total: int,
    unmapped_by_year: Mapping[int, int],
    total_by_year: Mapping[int, int],
    reconciled: bool | None,
    config: ProtocolConfig = PROTOCOL,
) -> CfobGateReport:
    gates = (
        evaluate_f0_protocol(
            protocol_present=protocol_present, trial_ledger_present=trial_ledger_present
        ),
        evaluate_f1_mapping_rate(mapped=mapped, total=total, config=config),
        evaluate_f2_unmapped_composition(
            unmapped_by_year=unmapped_by_year, total_by_year=total_by_year, config=config
        ),
        evaluate_f3_reconcile(reconciled=reconciled),
    )
    return _report(gates, stage="F0")


def build_cfob_artifact(
    *,
    stage: str,
    report: CfobGateReport,
    counts: QualificationCounts,
    raw_clusters: int,
    de_overlapped_clusters: int,
    shares: Mapping[int, float],
    mode: str,
    notes: Mapping[str, object] | None = None,
    config: ProtocolConfig = PROTOCOL,
) -> dict:
    """Measurement artifact. ``capital_go`` is false by construction."""

    return {
        "stage": stage,
        "line": config.line,
        "experiment_id": config.experiment_id,
        "verdict": report.verdict,
        "capital_go": False,
        "implementability_eligible": False,
        "protocol": {
            "transaction_code": config.transaction_code,
            "min_gross_value": str(config.min_gross_value),
            "staleness_cap_days": config.staleness_cap_days,
            "cluster_window_days": config.cluster_window_days,
            "min_distinct_insiders": config.min_distinct_insiders,
            "min_price": str(config.min_price),
            "min_dollar_volume": str(config.min_dollar_volume),
            "min_clusters": config.min_clusters,
            "min_contributing_years": config.min_contributing_years,
            "min_year_share": config.min_year_share,
            "max_year_share": config.max_year_share,
            "mds_bar": config.mds_bar,
            "excess_dispersion": config.excess_dispersion,
            "horizon_sessions": config.horizon_sessions,
            "min_mapping_rate": config.min_mapping_rate,
            "known_time_axis": "filing_date_day_granular",
            "known_time_conservatism": (
                "SEC Insider Transactions Data Sets carry no acceptance timestamp; "
                "entry is the open of the first trading day strictly after filing_date"
            ),
            "entry_rule": "next_open_after_filing_date",
        },
        "counts": counts.to_dict(),
        "clusters": {
            "raw": raw_clusters,
            "de_overlapped": de_overlapped_clusters,
            "required_for_mds_bar": required_events(config=config),
            "mds_at_measured_n": min_detectable_size(
                n_events=de_overlapped_clusters, config=config
            ),
            "year_shares": {str(year): share for year, share in shares.items()},
        },
        "gates": report.to_dict()["gates"],
        "all_hard_gates_passed": report.all_hard_gates_passed,
        "mode": mode,
        "notes": dict(notes or {}),
    }
