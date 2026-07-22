"""EVENTS-22 announcement-reaction drift F0 (GitHub issue #81).

This module may inspect event identities, dates, listing facts, price levels,
volumes, session counts, and pre-existing power inputs.  It must never accept
or calculate reaction values or forward returns.  E1 remains a separate,
human-authorised implementation boundary.
"""

from __future__ import annotations

from bisect import bisect_left
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
import json
from math import isfinite, sqrt
from typing import Any, Literal

F0Decision = Literal["included", "excluded"]
F0Verdict = Literal["kill_line", "underpowered_stop", "f0_pass"]
E1Status = Literal["blocked", "awaiting_human_approval"]
F0LedgerReason = Literal[
    "wrong_event_code",
    "unmapped_or_ambiguous",
    "known_date_outside_calendar",
    "insufficient_forward_sessions",
    "eligibility_unmeasured",
    "eligibility_conflict",
    "actions_or_delistings_incomplete",
    "below_price_floor",
    "below_dollar_volume_floor",
    "insufficient_prior_sessions",
    "issuer_horizon_overlap",
    "issuer_date_coalesced",
    "included",
]
F0GateId = Literal[
    "F0-semantics",
    "F0-known-time",
    "F0-PIT-map",
    "F0-duplicates",
    "F0-actions",
    "F0-reproducibility",
    "F0-seal",
    "F0-power",
]


@dataclass(frozen=True)
class ProtocolConfig:
    line: str = "events22-announcement-reaction-drift"
    experiment_id: str = "events22-f0"
    parent_prd: int = 81
    event_code: int = 22
    event_semantics: str = "Results of Operations / Item 2.02"
    known_time_policy: str = "second_open_date_only"
    initial_authorisation: str = "F0_only"
    capital_go: bool = False

    primary_entry: str = "D+2_open"
    secondary_entry: str = "D+1_open"
    primary_horizon_sessions: int = 60
    secondary_horizon_sessions: int = 60
    diagnostic_horizon_sessions: int = 20

    min_prior_years: int = 2
    min_prior_events: int = 1_000
    min_usable_years: int = 10

    min_price: float = 5.0
    dollar_volume_lookback_sessions: int = 20
    min_median_dollar_volume: float = 10_000_000.0
    min_prior_sessions: int = 252

    power_target_effect: float = 0.01
    power_target: float = 0.80
    primary_clustered_t: float = 2.5
    power_z_beta: float = 0.841621

    primary_cost_bps: float = 10.0
    stress_cost_bps: float = 25.0
    bootstrap_block_sessions: int = 63
    shifted_placebo_sessions: int = 20


PROTOCOL = ProtocolConfig()


@dataclass(frozen=True)
class EventRow:
    source_row_id: str
    ticker: str
    event_date: date
    event_code: int


@dataclass(frozen=True)
class ListingRecord:
    issuer_id: str
    ticker: str
    related_tickers: tuple[str, ...]
    listed_date: date
    delisted_date: date | None
    is_primary_common_stock: bool
    is_us_primary_listing: bool

    def covers(self, event_date: date) -> bool:
        return self.listed_date <= event_date and (
            self.delisted_date is None or event_date <= self.delisted_date
        )


@dataclass(frozen=True)
class EligibilityFact:
    ticker: str
    known_date: date
    price: float
    median_dollar_volume_20_session: float
    prior_valid_sessions: int
    actions_and_delistings_complete: bool = True


@dataclass(frozen=True)
class F0Evidence:
    semantics_verified: bool
    known_time_verified: bool
    pit_mapping_verified: bool
    duplicate_policy_verified: bool
    actions_and_delistings_verified: bool
    reproducibility_verified: bool
    return_fields_absent: bool
    semantics_source: str

    @classmethod
    def synthetic_pass(cls) -> F0Evidence:
        """Passing evidence for unit/smoke tests only; never a research claim."""

        return cls(
            semantics_verified=True,
            known_time_verified=True,
            pit_mapping_verified=True,
            duplicate_policy_verified=True,
            actions_and_delistings_verified=True,
            reproducibility_verified=True,
            return_fields_absent=True,
            semantics_source="synthetic-test-evidence",
        )


@dataclass(frozen=True)
class PowerBasis:
    source_name: str
    source_sha256: str
    cluster_adjusted_dispersion: float
    source_frozen_date: date
    outcome_inspection_not_before: date


@dataclass(frozen=True)
class F0Provenance:
    snapshot_id: str
    code_id: str


@dataclass(frozen=True)
class CanonicalEvent:
    issuer_id: str
    ticker: str
    known_date: date
    raw_row_ids: tuple[str, ...]


@dataclass(frozen=True)
class F0Counts:
    raw_code22: int
    mapped: int
    timing_eligible: int
    canonical: int
    eligible: int
    de_overlapped: int
    exclusions: Mapping[str, int]


@dataclass(frozen=True)
class F0YearCounts:
    raw: int
    canonical: int
    eligible: int
    de_overlapped: int


@dataclass(frozen=True)
class F0DensitySummary:
    mapping_success_rate: float
    duplicate_rows_coalesced: int
    coalesced_group_size_counts: Mapping[int, int]
    issuer_date_clusters: int
    post_first_wins_issuers: int
    post_first_wins_dates: int
    max_events_per_issuer: int
    max_events_per_date: int


@dataclass(frozen=True)
class F0LedgerEntry:
    source_row_id: str
    decision: F0Decision
    reason: F0LedgerReason
    issuer_id: str | None = None
    known_date: date | None = None


@dataclass(frozen=True)
class AnnualFold:
    year: int
    prior_years: int
    prior_events: int
    events: int
    usable: bool


@dataclass(frozen=True)
class PowerReport:
    q5_events: int
    basis_valid: bool
    detectable_effect_at_target_power: float
    target_effect: float
    target_power: float
    passed: bool
    reason: str


@dataclass(frozen=True)
class F0GateResult:
    id: F0GateId
    passed: bool
    reason: str


@dataclass(frozen=True)
class Events22F0Result:
    canonical_events: tuple[CanonicalEvent, ...]
    ledger: tuple[F0LedgerEntry, ...]
    counts: F0Counts
    counts_by_year: Mapping[int, F0YearCounts]
    density: F0DensitySummary
    folds: Mapping[int, AnnualFold]
    usable_years: tuple[int, ...]
    power: PowerReport
    gates: tuple[F0GateResult, ...]
    capital_go: bool
    returns_measured: bool
    e1_status: E1Status
    verdict: F0Verdict


def _listing_for_event(event: EventRow, listings: Sequence[ListingRecord]) -> ListingRecord | None:
    candidates = [
        listing
        for listing in listings
        if listing.covers(event.event_date)
        and listing.is_primary_common_stock
        and listing.is_us_primary_listing
        and (event.ticker == listing.ticker or event.ticker in listing.related_tickers)
    ]
    issuer_ids = {candidate.issuer_id for candidate in candidates}
    if len(issuer_ids) != 1:
        return None
    exact = [candidate for candidate in candidates if candidate.ticker == event.ticker]
    return sorted(exact or candidates, key=lambda candidate: candidate.ticker)[0]


def _normalized_session(event_date: date, sessions: Sequence[date]) -> tuple[int, date] | None:
    index = bisect_left(sessions, event_date)
    if index >= len(sessions):
        return None
    return index, sessions[index]


def compute_events22_input_hashes(
    *,
    events: Sequence[EventRow],
    listings: Sequence[ListingRecord],
    sessions: Sequence[date],
    eligibility: Sequence[EligibilityFact],
    evidence: F0Evidence,
    power_basis: PowerBasis | None,
) -> dict[str, str]:
    """Hash every sealed F0 input section from its canonical content."""

    sections = {
        "events": _artifact_value([asdict(item) for item in events]),
        "listings": _artifact_value([asdict(item) for item in listings]),
        "sessions": _artifact_value(list(sessions)),
        "eligibility": _artifact_value([asdict(item) for item in eligibility]),
        "evidence": _artifact_value(asdict(evidence)),
        "power_basis": _artifact_value(asdict(power_basis)) if power_basis else None,
    }
    return {
        name: sha256(_canonical_json({"value": value})).hexdigest()
        for name, value in sorted(sections.items())
    }


def run_events22_f0(
    *,
    events: Sequence[EventRow],
    listings: Sequence[ListingRecord],
    sessions: Sequence[date],
    eligibility: Sequence[EligibilityFact],
    evidence: F0Evidence,
    power_basis: PowerBasis | None,
    input_hashes: Mapping[str, str],
    config: ProtocolConfig = PROTOCOL,
) -> Events22F0Result:
    """Build the canonical F0 cohort without reading or calculating returns."""

    source_row_ids = [event.source_row_id for event in events]
    if len(source_row_ids) != len(set(source_row_ids)):
        raise ValueError("source_row_id values must be unique")
    input_hashes_valid = dict(input_hashes) == compute_events22_input_hashes(
        events=events,
        listings=listings,
        sessions=sessions,
        eligibility=eligibility,
        evidence=evidence,
        power_basis=power_basis,
    )
    ordered_sessions = tuple(sorted(set(sessions)))
    eligibility_keys = [(fact.ticker, fact.known_date) for fact in eligibility]
    if len(eligibility_keys) != len(set(eligibility_keys)):
        raise ValueError("eligibility facts must be unique by ticker and known_date")
    if any(
        not isfinite(fact.price)
        or fact.price <= 0
        or not isfinite(fact.median_dollar_volume_20_session)
        or fact.median_dollar_volume_20_session < 0
        or fact.prior_valid_sessions < 0
        for fact in eligibility
    ):
        raise ValueError("eligibility price, volume, and session values must be finite and valid")
    eligibility_by_key = {(fact.ticker, fact.known_date): fact for fact in eligibility}
    exclusions: Counter[str] = Counter()
    ledger: list[F0LedgerEntry] = []
    grouped: dict[tuple[str, date], list[tuple[EventRow, ListingRecord, int, date]]] = defaultdict(
        list
    )
    raw_code22 = 0
    mapped = 0
    raw_by_year: Counter[int] = Counter()

    for event in sorted(events, key=lambda row: (row.event_date, row.ticker, row.source_row_id)):
        if event.event_code != config.event_code:
            exclusions["wrong_event_code"] += 1
            ledger.append(F0LedgerEntry(event.source_row_id, "excluded", "wrong_event_code"))
            continue
        raw_code22 += 1
        raw_by_year[event.event_date.year] += 1
        listing = _listing_for_event(event, listings)
        if listing is None:
            exclusions["unmapped_or_ambiguous"] += 1
            ledger.append(F0LedgerEntry(event.source_row_id, "excluded", "unmapped_or_ambiguous"))
            continue
        mapped += 1
        normalized = _normalized_session(event.event_date, ordered_sessions)
        if normalized is None:
            exclusions["known_date_outside_calendar"] += 1
            ledger.append(
                F0LedgerEntry(
                    event.source_row_id,
                    "excluded",
                    "known_date_outside_calendar",
                    listing.issuer_id,
                )
            )
            continue
        session_index, session_date = normalized
        if session_index + 2 + config.primary_horizon_sessions >= len(ordered_sessions):
            exclusions["insufficient_forward_sessions"] += 1
            ledger.append(
                F0LedgerEntry(
                    event.source_row_id,
                    "excluded",
                    "insufficient_forward_sessions",
                    listing.issuer_id,
                    session_date,
                )
            )
            continue
        grouped[(listing.issuer_id, session_date)].append(
            (event, listing, session_index, session_date)
        )

    coalesced: list[tuple[CanonicalEvent, int]] = []
    for (issuer_id, known_date), members in sorted(grouped.items()):

        def exclude_group(reason: F0LedgerReason) -> None:
            exclusions[reason] += len(members)
            ledger.extend(
                F0LedgerEntry(
                    event.source_row_id,
                    "excluded",
                    reason,
                    issuer_id,
                    known_date,
                )
                for event, _, _, _ in members
            )

        tickers = sorted({listing.ticker for _, listing, _, _ in members})
        facts = [
            eligibility_by_key[(ticker, known_date)]
            for ticker in tickers
            if (ticker, known_date) in eligibility_by_key
        ]
        if not facts:
            exclude_group("eligibility_unmeasured")
            continue
        comparable = {
            (
                fact.price,
                fact.median_dollar_volume_20_session,
                fact.prior_valid_sessions,
                fact.actions_and_delistings_complete,
            )
            for fact in facts
        }
        if len(comparable) != 1:
            exclude_group("eligibility_conflict")
            continue
        fact = sorted(facts, key=lambda item: item.ticker)[0]
        if not fact.actions_and_delistings_complete:
            exclude_group("actions_or_delistings_incomplete")
            continue
        if fact.price < config.min_price:
            exclude_group("below_price_floor")
            continue
        if fact.median_dollar_volume_20_session < config.min_median_dollar_volume:
            exclude_group("below_dollar_volume_floor")
            continue
        if fact.prior_valid_sessions < config.min_prior_sessions:
            exclude_group("insufficient_prior_sessions")
            continue
        row_ids = tuple(sorted(event.source_row_id for event, _, _, _ in members))
        coalesced.append(
            (
                CanonicalEvent(
                    issuer_id=issuer_id,
                    ticker=fact.ticker,
                    known_date=known_date,
                    raw_row_ids=row_ids,
                ),
                members[0][2],
            )
        )

    kept: list[CanonicalEvent] = []
    blocked_until: dict[str, int] = {}
    for event, session_index in coalesced:
        if session_index < blocked_until.get(event.issuer_id, -1):
            exclusions["issuer_horizon_overlap"] += len(event.raw_row_ids)
            ledger.extend(
                F0LedgerEntry(
                    row_id,
                    "excluded",
                    "issuer_horizon_overlap",
                    event.issuer_id,
                    event.known_date,
                )
                for row_id in event.raw_row_ids
            )
            continue
        kept.append(event)
        included_reason = "issuer_date_coalesced" if len(event.raw_row_ids) > 1 else "included"
        ledger.extend(
            F0LedgerEntry(
                row_id,
                "included",
                included_reason,
                event.issuer_id,
                event.known_date,
            )
            for row_id in event.raw_row_ids
        )
        blocked_until[event.issuer_id] = session_index + 2 + config.primary_horizon_sessions

    event_counts_by_year = Counter(event.known_date.year for event in kept)
    canonical_by_year = Counter(known_date.year for _, known_date in grouped)
    eligible_by_year = Counter(event.known_date.year for event, _ in coalesced)
    folds: dict[int, AnnualFold] = {}
    for year in sorted(event_counts_by_year):
        prior_year_counts = {
            prior_year: count
            for prior_year, count in event_counts_by_year.items()
            if prior_year < year
        }
        prior_events = sum(prior_year_counts.values())
        folds[year] = AnnualFold(
            year=year,
            prior_years=len(prior_year_counts),
            prior_events=prior_events,
            events=event_counts_by_year[year],
            usable=(
                len(prior_year_counts) >= config.min_prior_years
                and prior_events >= config.min_prior_events
            ),
        )
    usable_years = tuple(year for year, fold in folds.items() if fold.usable)
    usable_years_passed = len(usable_years) >= config.min_usable_years
    q5_events = sum(folds[year].events // 5 for year in usable_years)
    basis_valid = bool(
        power_basis is not None
        and power_basis.source_name.strip()
        and len(power_basis.source_sha256) == 64
        and all(character in "0123456789abcdef" for character in power_basis.source_sha256.lower())
        and isfinite(power_basis.cluster_adjusted_dispersion)
        and power_basis.cluster_adjusted_dispersion > 0
        and power_basis.source_frozen_date < power_basis.outcome_inspection_not_before
    )
    detectable_effect = float("inf")
    if basis_valid and usable_years_passed and power_basis is not None and q5_events > 0:
        detectable_effect = (
            (config.primary_clustered_t + config.power_z_beta)
            * power_basis.cluster_adjusted_dispersion
            / sqrt(q5_events)
        )
    power_passed = (
        basis_valid and usable_years_passed and detectable_effect <= config.power_target_effect
    )
    if not basis_valid:
        power_reason = "no valid pre-existing variance/dependence basis — fail closed"
    elif not usable_years_passed:
        power_reason = (
            f"requires {config.min_usable_years} usable years; observed {len(usable_years)}"
        )
    elif q5_events == 0:
        power_reason = "no usable Q5 events under frozen annual cutoffs"
    else:
        power_reason = (
            f"80% power MDS={detectable_effect:.6f} vs "
            f"target={config.power_target_effect:.6f}; expected Q5 n={q5_events}"
        )
    power_report = PowerReport(
        q5_events=q5_events,
        basis_valid=basis_valid,
        detectable_effect_at_target_power=detectable_effect,
        target_effect=config.power_target_effect,
        target_power=config.power_target,
        passed=power_passed,
        reason=power_reason,
    )

    semantics_passed = evidence.semantics_verified and bool(evidence.semantics_source.strip())
    reproducibility_passed = evidence.reproducibility_verified and input_hashes_valid
    gates = (
        F0GateResult(
            "F0-semantics",
            semantics_passed,
            f"EVENTS code {config.event_code}: {config.event_semantics}; "
            f"source={evidence.semantics_source}",
        ),
        F0GateResult(
            "F0-known-time",
            evidence.known_time_verified,
            f"date-granular policy={config.known_time_policy}",
        ),
        F0GateResult(
            "F0-PIT-map",
            evidence.pit_mapping_verified,
            "point-in-time issuer/security mapping verified",
        ),
        F0GateResult(
            "F0-duplicates",
            evidence.duplicate_policy_verified,
            "issuer-date coalescing and first-wins de-overlap verified",
        ),
        F0GateResult(
            "F0-actions",
            evidence.actions_and_delistings_verified,
            "corporate-action and delisting coverage verified",
        ),
        F0GateResult(
            "F0-reproducibility",
            reproducibility_passed,
            "input/config provenance and SHA-256 hashes verified"
            if reproducibility_passed
            else "missing or invalid input/config provenance hash",
        ),
        F0GateResult(
            "F0-seal",
            evidence.return_fields_absent,
            "reaction and forward-return fields absent",
        ),
        F0GateResult("F0-power", power_passed, power_reason),
    )

    integrity = all(
        (
            semantics_passed,
            evidence.known_time_verified,
            evidence.pit_mapping_verified,
            evidence.duplicate_policy_verified,
            evidence.actions_and_delistings_verified,
            reproducibility_passed,
            evidence.return_fields_absent,
        )
    )
    if not integrity:
        verdict = "kill_line"
    elif not power_passed:
        verdict = "underpowered_stop"
    else:
        verdict = "f0_pass"

    years = sorted(
        set(raw_by_year)
        | set(canonical_by_year)
        | set(eligible_by_year)
        | set(event_counts_by_year)
    )
    counts_by_year = {
        year: F0YearCounts(
            raw=raw_by_year[year],
            canonical=canonical_by_year[year],
            eligible=eligible_by_year[year],
            de_overlapped=event_counts_by_year[year],
        )
        for year in years
    }
    issuer_density = Counter(event.issuer_id for event in kept)
    date_density = Counter(event.known_date for event in kept)
    group_size_counts = Counter(len(members) for members in grouped.values())

    return Events22F0Result(
        canonical_events=tuple(kept),
        ledger=tuple(sorted(ledger, key=lambda entry: entry.source_row_id)),
        counts=F0Counts(
            raw_code22=raw_code22,
            mapped=mapped,
            timing_eligible=sum(len(members) for members in grouped.values()),
            canonical=len(grouped),
            eligible=len(coalesced),
            de_overlapped=len(kept),
            exclusions=dict(sorted(exclusions.items())),
        ),
        counts_by_year=counts_by_year,
        density=F0DensitySummary(
            mapping_success_rate=mapped / raw_code22 if raw_code22 else 0.0,
            duplicate_rows_coalesced=(
                sum(len(members) for members in grouped.values()) - len(grouped)
            ),
            coalesced_group_size_counts=dict(sorted(group_size_counts.items())),
            issuer_date_clusters=len(grouped),
            post_first_wins_issuers=len(issuer_density),
            post_first_wins_dates=len(date_density),
            max_events_per_issuer=max(issuer_density.values(), default=0),
            max_events_per_date=max(date_density.values(), default=0),
        ),
        folds=folds,
        usable_years=usable_years,
        power=power_report,
        gates=gates,
        capital_go=False,
        returns_measured=False,
        e1_status="awaiting_human_approval" if verdict == "f0_pass" else "blocked",
        verdict=verdict,
    )


def refuse_events22_e1() -> None:
    """Make the F0-only implementation boundary executable and unambiguous."""

    raise PermissionError(
        "EVENTS-22 is F0-only; E1 needs a separate human approval and implementation"
    )


def _artifact_value(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and not isfinite(value):
        return None
    if isinstance(value, Mapping):
        return {str(key): _artifact_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_artifact_value(item) for item in value]
    return value


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def build_events22_f0_artifact(
    *,
    result: Events22F0Result,
    evidence: F0Evidence,
    input_hashes: Mapping[str, str],
    power_basis: PowerBasis | None,
    provenance: F0Provenance,
    config: ProtocolConfig = PROTOCOL,
) -> dict[str, Any]:
    """Serialize a deterministic, self-hashed F0 artifact with no outcome values."""

    protocol = _artifact_value(asdict(config))
    config_sha256 = sha256(_canonical_json(protocol)).hexdigest()
    artifact: dict[str, Any] = {
        "schema_version": "events22-f0-v1",
        "protocol": protocol,
        "config_sha256": config_sha256,
        "provenance": _artifact_value(asdict(provenance)),
        "input_sha256": dict(sorted(input_hashes.items())),
        "evidence": _artifact_value(asdict(evidence)),
        "power_basis": _artifact_value(asdict(power_basis)) if power_basis else None,
        "canonical_events": _artifact_value(asdict(result)["canonical_events"]),
        "ledger": _artifact_value(asdict(result)["ledger"]),
        "counts": _artifact_value(asdict(result.counts)),
        "counts_by_year": _artifact_value(asdict(result)["counts_by_year"]),
        "density": _artifact_value(asdict(result.density)),
        "annual_folds": _artifact_value(asdict(result)["folds"]),
        "usable_folds": {
            "count": len(result.usable_years),
            "first_year": min(result.usable_years, default=None),
            "last_year": max(result.usable_years, default=None),
            "years": list(result.usable_years),
        },
        "power": _artifact_value(asdict(result.power)),
        "gates": _artifact_value(asdict(result)["gates"]),
        "capital_go": False,
        "returns_measured": False,
        "e1_status": result.e1_status,
        "verdict": result.verdict,
    }
    artifact["artifact_sha256"] = sha256(_canonical_json(artifact)).hexdigest()
    return artifact
