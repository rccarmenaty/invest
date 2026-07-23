"""Source-neutral I0 feasibility audit for SEC 8-K Item 2.02 filings.

This module deliberately has no network or price-data dependencies.  It turns typed
filing, listing, session, reconciliation, and pre-existing power-basis records into
an accession-level decision ledger and a fail-closed I0 verdict.  It cannot perform
F0 or E1 work and every result keeps capital and return measurement disabled.
"""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
from math import ceil, isfinite


@dataclass(frozen=True)
class I0Protocol:
    line: str = "sec-8k-2.02-timestamped-announcement-reaction-drift"
    stage: str = "i0"
    regime_start_year: int = 2004
    last_complete_year: int = 2025
    min_timestamp_rate: float = 0.99
    min_mapping_rate: float = 0.95
    max_year_unmapped_rate_ratio: float = 3.0
    min_year_weight_for_composition: float = 0.01
    min_prior_years: int = 2
    min_prior_events: int = 1_000
    min_usable_years: int = 10
    require_complete_quarter_forms: bool = True
    primary_clustered_t: float = 2.5
    power_z_beta: float = 0.841621
    power: float = 0.80
    target_effect: float = 0.01


PROTOCOL = I0Protocol()


@dataclass(frozen=True)
class UniverseFirstProtocol(I0Protocol):
    line: str = "sec-8k-uf-universe-first-pit-mapping"
    min_universe_cik_rate: float = 0.95


UNIVERSE_FIRST_PROTOCOL = UniverseFirstProtocol()
I0_INPUT_SECTION_NAMES = (
    "provenance",
    "filings",
    "listings",
    "sessions",
    "reconciliation",
    "power_basis",
)


class I0SealingError(ValueError):
    """An I0 manifest or artifact cannot be serialized and sealed deterministically."""


def canonical_i0_json(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as error:
        raise I0SealingError("I0 content is non-JSON or non-finite") from error


def digest_i0_json(value: object) -> str:
    return sha256(canonical_i0_json(value)).hexdigest()


def seal_i0_manifest(manifest: dict[str, object]) -> dict[str, object]:
    """Copy and hash every deterministic I0 input section without adapter coupling."""

    canonical_i0_json(manifest)
    try:
        copied = deepcopy(manifest)
    except (TypeError, ValueError, RuntimeError) as error:
        raise I0SealingError("I0 manifest cannot be copied for sealing") from error
    copied.pop("section_hashes", None)
    missing = [name for name in I0_INPUT_SECTION_NAMES if name not in copied]
    if missing:
        raise I0SealingError(f"cannot seal manifest; missing sections: {missing}")
    copied["section_hashes"] = {
        name: digest_i0_json(copied[name]) for name in I0_INPUT_SECTION_NAMES
    }
    return copied


@dataclass(frozen=True)
class FilingRecord:
    accession_number: str
    cik: str
    form: str
    filing_date: date
    acceptance_raw: str | None
    acceptance_at: datetime | None
    source_url: str
    content_sha256: str
    item_codes: tuple[str, ...]
    item_202_evidence: tuple[str, ...]
    source_occurrences: tuple[str, ...]
    as_filed_ticker: str | None = None
    item_202_conflicts: tuple[str, ...] = ()
    amendment_of: str | None = None
    parse_error: str | None = None

    @property
    def is_amendment(self) -> bool:
        return self.form.upper() == "8-K/A"


@dataclass(frozen=True)
class ListingRecord:
    symbol: str
    cik: str | None
    related_symbols: tuple[str, ...]
    first_date: date | None
    last_date: date | None
    us_primary_common: bool
    exchange: str | None = None

    def covers(self, as_of: date) -> bool:
        return not (
            (self.first_date is not None and as_of < self.first_date)
            or (self.last_date is not None and as_of > self.last_date)
        )


@dataclass(frozen=True)
class SessionRecord:
    session_date: date
    market_open: datetime


@dataclass(frozen=True)
class ReconciliationRecord:
    year: int
    quarter: int
    form: str
    expected: int
    fetched: int
    parsed: int
    failed: int
    excluded: int
    item_202: int | None = None


@dataclass(frozen=True)
class PowerBasis:
    basis_id: str
    created_at: datetime
    effective_sigma: float
    provenance: str


@dataclass(frozen=True)
class I0Result:
    line: str
    stage: str
    verdict: str
    status: str
    capital_go: bool
    returns_measured: bool
    counts: dict[str, int]
    folds: tuple[dict[str, int | bool], ...]
    power: dict[str, int | float | bool | str]
    gates: tuple[dict[str, str | bool], ...]
    decision_ledger: tuple[dict[str, object], ...]
    year_counts: dict[int, dict[str, int | float]]
    collisions: tuple[dict[str, object], ...]
    concentration: dict[str, object]
    universe_coverage: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "line": self.line,
            "stage": self.stage,
            "verdict": self.verdict,
            "status": self.status,
            "capital_go": False,
            "returns_measured": False,
            "f0_authorized": False,
            "e1_authorized": False,
            "counts": self.counts,
            "year_counts": {str(year): value for year, value in sorted(self.year_counts.items())},
            "folds": list(self.folds),
            "power": self.power,
            "gates": list(self.gates),
            "decision_ledger": list(self.decision_ledger),
            "collisions": list(self.collisions),
            "concentration": self.concentration,
        }
        if self.universe_coverage is not None:
            payload["universe_coverage"] = self.universe_coverage
        return payload


def normalize_cik(raw: str | None) -> str | None:
    if raw is None:
        return None
    digits = raw
    if not digits or any(character not in "0123456789" for character in digits):
        return None
    normalized = digits.lstrip("0")
    return normalized or None


def _gate(gate_id: str, passed: bool, reason: str, *, category: str) -> dict[str, str | bool]:
    return {"id": gate_id, "passed": passed, "category": category, "reason": reason}


def _valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value.lower())


def _map_listing(
    filing: FilingRecord,
    listings_by_cik: dict[str, list[ListingRecord]],
    *,
    as_of: date | None = None,
) -> tuple[ListingRecord | None, str]:
    cik = normalize_cik(filing.cik)
    if cik is None:
        return None, "filing_has_no_cik"
    mapping_date = as_of or filing.filing_date
    candidates = [row for row in listings_by_cik.get(cik, ()) if row.covers(mapping_date)]
    if not candidates:
        return None, "cik_or_window_absent"
    symbol = (filing.as_filed_ticker or "").strip().upper()
    exact = [row for row in candidates if row.symbol.strip().upper() == symbol]
    if len(exact) == 1:
        selected, reason = exact[0], "matched_exact_symbol"
    else:
        related = [
            row
            for row in candidates
            if symbol and symbol in {item.strip().upper() for item in row.related_symbols}
        ]
        if len(related) == 1:
            selected, reason = related[0], "matched_related_symbol"
        elif len(candidates) == 1:
            selected, reason = candidates[0], "matched_sole_covering_row"
        else:
            return None, "ambiguous_excluded"
    if not selected.us_primary_common:
        return None, "not_us_primary_common"
    return selected, reason


def _known_session(
    acceptance_at: datetime, sessions: Sequence[SessionRecord]
) -> SessionRecord | None:
    if acceptance_at.tzinfo is None:
        return None
    return next((session for session in sessions if session.market_open > acceptance_at), None)


def evaluate_i0(
    *,
    filings: Iterable[FilingRecord],
    listings: Sequence[ListingRecord],
    sessions: Sequence[SessionRecord],
    reconciliation: Sequence[ReconciliationRecord],
    power_basis: PowerBasis,
    protocol: I0Protocol = PROTOCOL,
    universe_first: bool = False,
) -> I0Result:
    """Evaluate I0 without inspecting or accepting any outcome-bearing values."""

    raw = tuple(filings)
    ordered_sessions = tuple(sorted(sessions, key=lambda row: row.market_open))
    universe_windows = tuple(listing for listing in listings if listing.us_primary_common)
    evaluated_listings = universe_windows if universe_first else tuple(listings)
    listings_by_cik: dict[str, list[ListingRecord]] = defaultdict(list)
    for listing in evaluated_listings:
        cik = normalize_cik(listing.cik)
        if cik is not None:
            listings_by_cik[cik].append(listing)
    universe_windows_with_cik = sum(
        normalize_cik(listing.cik) is not None for listing in universe_windows
    )
    universe_by_exchange: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for listing in universe_windows:
        exchange = (listing.exchange or "UNKNOWN").strip().upper() or "UNKNOWN"
        universe_by_exchange[exchange][0] += 1
        universe_by_exchange[exchange][1] += normalize_cik(listing.cik) is not None
    universe_by_year: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for year in range(protocol.regime_start_year, protocol.last_complete_year + 1):
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        for listing in universe_windows:
            if (
                listing.first_date is not None
                and listing.first_date > year_end
                or listing.last_date is not None
                and listing.last_date < year_start
            ):
                continue
            universe_by_year[year][0] += 1
            universe_by_year[year][1] += normalize_cik(listing.cik) is not None

    by_identity: dict[tuple[str, str], list[FilingRecord]] = defaultdict(list)
    by_accession: dict[str, list[FilingRecord]] = defaultdict(list)
    for filing in raw:
        normalized_cik = normalize_cik(filing.cik) or filing.cik.strip()
        by_identity[(filing.accession_number, normalized_cik)].append(filing)
        by_accession[filing.accession_number].append(filing)

    ledger_by_identity: dict[tuple[str, str], dict[str, object]] = {}
    eligible: list[tuple[FilingRecord, ListingRecord, SessionRecord, str]] = []
    duplicate_conflicts = 0
    item_filer_records = 0
    item_accessions: set[str] = set()
    valid_timestamps = 0
    mapped = 0
    mapping_total = 0
    mapping_by_year: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    unresolved_amendments = 0
    semantic_conflicts = 0
    known_session_missing = 0
    all_original_filer_records = 0
    out_of_universe_filer_records = 0
    unclassifiable_original_filings = 0
    all_original_by_year: dict[int, int] = defaultdict(int)
    out_of_universe_by_year: dict[int, int] = defaultdict(int)
    unclassifiable_by_year: dict[int, int] = defaultdict(int)

    for identity_key, occurrences in sorted(by_identity.items()):
        accession, normalized_cik = identity_key
        filing = sorted(occurrences, key=lambda row: (row.source_url, row.content_sha256))[0]
        observed_identities = {
            (row.form.upper(), row.filing_date, row.content_sha256) for row in occurrences
        }
        ledger: dict[str, object] = {
            "accession_number": accession,
            "cik": normalized_cik,
            "source_occurrences": sorted(
                {value for row in occurrences for value in row.source_occurrences}
            ),
            "form": filing.form.upper(),
        }
        ledger_by_identity[identity_key] = ledger
        if len(observed_identities) != 1:
            duplicate_conflicts += 1
            ledger.update(
                decision="duplicate_conflict",
                reasons=["accession-CIK identity/content differs"],
            )
            continue
        if filing.form.upper() not in {"8-K", "8-K/A"}:
            ledger.update(decision="excluded", reasons=["unsupported_form"])
            continue
        has_item = bool(filing.item_202_evidence) or "2.02" in filing.item_codes
        if filing.parse_error is not None:
            if has_item:
                item_filer_records += 1
                item_accessions.add(accession)
            ledger.update(decision="excluded", reasons=[filing.parse_error])
            continue
        if not _valid_sha256(filing.content_sha256):
            ledger.update(decision="excluded", reasons=["invalid_content_sha256"])
            continue
        if not has_item:
            ledger.update(decision="excluded", reasons=["not_item_2.02"])
            continue
        item_filer_records += 1
        item_accessions.add(accession)
        if filing.item_202_conflicts:
            semantic_conflicts += 1
            ledger.update(
                decision="excluded",
                reasons=["item_2.02_evidence_conflict", *filing.item_202_conflicts],
            )
            continue
        if filing.acceptance_at is None or filing.acceptance_at.tzinfo is None:
            ledger.update(decision="excluded", reasons=["missing_or_naive_acceptance_timestamp"])
            continue
        valid_timestamps += 1
        if filing.is_amendment:
            original_rows = by_accession.get(filing.amendment_of or "", ())
            link_supported = bool(original_rows) and any(
                row.form.upper() == "8-K" and normalize_cik(row.cik) == normalized_cik
                for row in original_rows
            )
            if filing.amendment_of and link_supported:
                ledger.update(
                    decision="amendment_linked_excluded",
                    reasons=["amendment_not_a_new_canonical_event"],
                    amendment_of=filing.amendment_of,
                )
            else:
                unresolved_amendments += 1
                ledger.update(
                    decision="amendment_unresolved_excluded",
                    reasons=["unresolved_amendment_link_not_guessed"],
                )
            continue

        all_original_filer_records += 1
        session: SessionRecord | None = None
        if universe_first:
            session = _known_session(filing.acceptance_at, ordered_sessions)
            classification_year = (
                session.session_date.year if session is not None else filing.filing_date.year
            )
            all_original_by_year[classification_year] += 1
            if session is None:
                known_session_missing += 1
                ledger.update(decision="excluded", reasons=["known_session_unavailable"])
                continue
            cik = normalize_cik(filing.cik)
            if cik is None:
                unclassifiable_original_filings += 1
                unclassifiable_by_year[classification_year] += 1
                ledger.update(decision="excluded", reasons=["unclassifiable_filing_cik"])
                continue
            if not any(
                listing.covers(session.session_date) for listing in listings_by_cik.get(cik, ())
            ):
                out_of_universe_filer_records += 1
                out_of_universe_by_year[classification_year] += 1
                ledger.update(decision="out_of_universe", reasons=["no_eligible_cik_window"])
                continue
        mapping_total += 1
        mapping_year = (
            session.session_date.year
            if universe_first and session is not None
            else filing.filing_date.year
        )
        mapping_by_year[mapping_year][1] += 1
        listing, mapping_reason = _map_listing(
            filing,
            listings_by_cik,
            as_of=session.session_date if session is not None else None,
        )
        if listing is None:
            ledger.update(decision="excluded", reasons=[mapping_reason])
            continue
        mapped += 1
        mapping_by_year[mapping_year][0] += 1
        if session is None:
            session = _known_session(filing.acceptance_at, ordered_sessions)
        if session is None:
            known_session_missing += 1
            ledger.update(decision="excluded", reasons=["known_session_unavailable"])
            continue
        eligible.append((filing, listing, session, mapping_reason))

    anchors: dict[tuple[str, date], list[tuple[FilingRecord, ListingRecord, str]]] = defaultdict(
        list
    )
    for filing, listing, session, mapping_reason in eligible:
        cik = normalize_cik(filing.cik)
        if cik is not None:
            anchors[(cik, session.session_date)].append((filing, listing, mapping_reason))

    collisions: list[dict[str, object]] = []
    year_counts: dict[int, dict[str, int | float]] = defaultdict(
        lambda: {
            "raw_accessions": 0,
            "item_202_filings": 0,
            "canonical_anchors": 0,
            "unique_issuers": 0,
            "mapped_original_filings": 0,
            "mapping_total": 0,
            "mapping_rate": 0.0,
        }
    )
    for row in reconciliation:
        year_counts[row.year]["raw_accessions"] += row.expected
    for accession, occurrences in by_accession.items():
        representative = occurrences[0]
        if any(bool(row.item_202_evidence) or "2.02" in row.item_codes for row in occurrences):
            year_counts[representative.filing_date.year]["item_202_filings"] += 1

    for (cik, session_date), members in sorted(anchors.items()):
        accessions = sorted(member[0].accession_number for member in members)
        symbols = sorted({member[1].symbol for member in members})
        year_counts[session_date.year]["canonical_anchors"] += 1
        if len(accessions) > 1:
            collisions.append(
                {
                    "cik": cik,
                    "known_session": session_date.isoformat(),
                    "accession_numbers": accessions,
                }
            )
        for filing, listing, mapping_reason in members:
            identity_key = (
                filing.accession_number,
                normalize_cik(filing.cik) or filing.cik.strip(),
            )
            ledger_by_identity[identity_key].update(
                decision="canonical_anchor",
                reasons=[mapping_reason],
                canonical_symbol=listing.symbol,
                known_session=session_date.isoformat(),
                contributing_accessions=accessions,
                collision=len(accessions) > 1,
                covering_symbols=symbols,
            )

    canonical_count = len(anchors)
    issuer_anchor_counts: dict[str, int] = defaultdict(int)
    session_anchor_counts: dict[date, int] = defaultdict(int)
    issuers_by_year: dict[int, set[str]] = defaultdict(set)
    for cik, session_date in anchors:
        issuer_anchor_counts[cik] += 1
        session_anchor_counts[session_date] += 1
        issuers_by_year[session_date.year].add(cik)
    years = set(year_counts) | set(mapping_by_year)
    if universe_first:
        years |= (
            set(all_original_by_year) | set(out_of_universe_by_year) | set(unclassifiable_by_year)
        )
    for year in years:
        year_mapped, year_total = mapping_by_year[year]
        year_counts[year]["unique_issuers"] = len(issuers_by_year[year])
        year_counts[year]["mapped_original_filings"] = year_mapped
        year_counts[year]["mapping_total"] = year_total
        year_counts[year]["mapping_rate"] = year_mapped / year_total if year_total else 0.0
        if universe_first:
            year_counts[year].update(
                all_original_filer_records=all_original_by_year[year],
                in_universe_candidates=year_total,
                out_of_universe_filer_records=out_of_universe_by_year[year],
                unclassifiable_original_filings=unclassifiable_by_year[year],
                ambiguous_in_universe_candidates=year_total - year_mapped,
            )
    max_issuer = max(issuer_anchor_counts.items(), key=lambda item: item[1], default=(None, 0))
    max_session = max(session_anchor_counts.items(), key=lambda item: item[1], default=(None, 0))
    timestamp_rate = valid_timestamps / item_filer_records if item_filer_records else 0.0
    mapping_rate = mapped / mapping_total if mapping_total else 0.0
    actual_item_by_quarter_form: dict[tuple[int, int, str], set[str]] = defaultdict(set)
    for accession, accession_records in by_accession.items():
        representative = accession_records[0]
        if not any(
            bool(row.item_202_evidence) or "2.02" in row.item_codes for row in accession_records
        ):
            continue
        key = (
            representative.filing_date.year,
            (representative.filing_date.month - 1) // 3 + 1,
            representative.form.upper(),
        )
        actual_item_by_quarter_form[key].add(accession)
    reconciliation_by_key = {
        (row.year, row.quarter, row.form.upper()): row for row in reconciliation
    }
    duplicate_reconciliation_rows = len(reconciliation_by_key) != len(reconciliation)
    required_reconciliation_keys: set[tuple[int, int, str]] = set(actual_item_by_quarter_form)
    if protocol.require_complete_quarter_forms:
        years = range(protocol.regime_start_year, protocol.last_complete_year + 1)
        required_reconciliation_keys = {
            (year, quarter, form)
            for year in years
            for quarter in (1, 2, 3, 4)
            for form in ("8-K", "8-K/A")
        }
    reconciliation_ok = (
        bool(reconciliation)
        and not duplicate_reconciliation_rows
        and set(reconciliation_by_key) == required_reconciliation_keys
        and all(
            row.form.upper() in {"8-K", "8-K/A"}
            and row.quarter in {1, 2, 3, 4}
            and row.expected == row.fetched == row.parsed
            and row.failed == 0
            and row.excluded == 0
            and (
                row.item_202 is None
                or row.item_202
                == len(actual_item_by_quarter_form[(row.year, row.quarter, row.form.upper())])
            )
            and (row.item_202 is None or 0 <= row.item_202 <= row.parsed)
            for row in reconciliation
        )
    )
    power_basis_ok = (
        bool(power_basis.basis_id.strip())
        and bool(power_basis.provenance.strip())
        and power_basis.created_at.tzinfo is not None
        and isfinite(power_basis.effective_sigma)
        and power_basis.effective_sigma > 0
    )

    composition_ok = True
    composition_reason = "no unmapped filings"
    unmapped = mapping_total - mapped
    if mapping_total and unmapped:
        global_rate = unmapped / mapping_total
        worst_year: int | None = None
        worst_rate = 0.0
        for year, (year_mapped, year_total) in sorted(mapping_by_year.items()):
            if year_total / mapping_total < protocol.min_year_weight_for_composition:
                continue
            rate = (year_total - year_mapped) / year_total
            if rate > worst_rate:
                worst_year, worst_rate = year, rate
        ceiling = global_rate * protocol.max_year_unmapped_rate_ratio
        composition_ok = worst_rate <= ceiling
        composition_reason = (
            f"worst_year={worst_year} unmapped_rate={worst_rate:.6f}; ceiling={ceiling:.6f}"
        )

    if universe_first:
        universe_coverage_rate = (
            universe_windows_with_cik / len(universe_windows) if universe_windows else 0.0
        )
        universe_floor = getattr(protocol, "min_universe_cik_rate", protocol.min_mapping_rate)
        mapping_gates = [
            _gate(
                "U1-universe-cik-coverage",
                bool(universe_windows) and universe_coverage_rate >= universe_floor,
                f"valid_cik={universe_windows_with_cik}/{len(universe_windows)}; "
                f"rate={universe_coverage_rate:.6f}",
                category="integrity",
            ),
            _gate(
                "U2-event-classification",
                unclassifiable_original_filings == 0,
                f"unclassifiable_original_filings={unclassifiable_original_filings}",
                category="integrity",
            ),
            _gate(
                "U3-in-universe-mapping",
                mapping_total > 0 and mapping_rate >= protocol.min_mapping_rate,
                f"mapped={mapped}/{mapping_total}; rate={mapping_rate:.6f}",
                category="integrity",
            ),
            _gate(
                "U4-mapping-composition",
                composition_ok,
                composition_reason,
                category="integrity",
            ),
        ]
    else:
        mapping_gates = [
            _gate(
                "I5-pit-mapping",
                mapping_total > 0 and mapping_rate >= protocol.min_mapping_rate,
                f"mapped={mapped}/{mapping_total}; rate={mapping_rate:.6f}",
                category="integrity",
            ),
            _gate(
                "I6-mapping-composition",
                composition_ok,
                composition_reason,
                category="integrity",
            ),
        ]

    gates = [
        _gate(
            "I1-reconciliation",
            reconciliation_ok,
            "all quarterly expected/fetched/parsed form counts agree"
            if reconciliation_ok
            else "missing or divergent quarterly reconciliation",
            category="integrity",
        ),
        _gate(
            "I2-accession-provenance",
            duplicate_conflicts == 0 and all(row.source_url.strip() for row in raw),
            f"duplicate_conflicts={duplicate_conflicts}",
            category="integrity",
        ),
        _gate(
            "I3-item-semantics",
            bool(item_accessions) and semantic_conflicts == 0,
            f"item_202_accessions={len(item_accessions)}; "
            f"filer_records={item_filer_records}; conflicts={semantic_conflicts}",
            category="integrity",
        ),
        _gate(
            "I4-acceptance-timestamps",
            item_filer_records > 0 and timestamp_rate >= protocol.min_timestamp_rate,
            f"valid={valid_timestamps}/{item_filer_records}; rate={timestamp_rate:.6f}",
            category="integrity",
        ),
        *mapping_gates,
        _gate(
            "I7-session-calendar",
            known_session_missing == 0,
            f"mapped filings without a strictly-later regular-session open={known_session_missing}",
            category="integrity",
        ),
        _gate(
            "I8-power-basis",
            power_basis_ok,
            "pre-existing count-only basis is present"
            if power_basis_ok
            else "power basis missing, invalid, or unprovenanced",
            category="integrity",
        ),
    ]

    canonical_by_year: dict[int, int] = {}
    for year, counts in year_counts.items():
        canonical_anchors = counts["canonical_anchors"]
        if not isinstance(canonical_anchors, int):
            raise RuntimeError("canonical anchor count must remain integral")
        canonical_by_year[year] = canonical_anchors
    folds: list[dict[str, int | bool]] = []
    event_years = sorted(
        year
        for year, count in canonical_by_year.items()
        if count > 0 and protocol.regime_start_year <= year <= protocol.last_complete_year
    )
    for year in event_years:
        prior_years = [prior for prior in event_years if prior < year]
        prior_count = sum(canonical_by_year[prior] for prior in prior_years)
        if len(prior_years) >= protocol.min_prior_years:
            folds.append(
                {
                    "year": year,
                    "prior_years": len(prior_years),
                    "prior_canonical_events": prior_count,
                    "usable": prior_count >= protocol.min_prior_events,
                }
            )
    usable_years = sum(1 for fold in folds if fold["usable"])
    protocol_canonical_count = sum(canonical_by_year[year] for year in event_years)
    required_events = (
        ceil(
            (
                (protocol.primary_clustered_t + protocol.power_z_beta)
                * power_basis.effective_sigma
                / protocol.target_effect
            )
            ** 2
        )
        if power_basis_ok
        and protocol.target_effect > 0
        and protocol.primary_clustered_t > 0
        and protocol.power_z_beta > 0
        else 0
    )
    power_ok = power_basis_ok and protocol_canonical_count >= required_events
    gates.extend(
        (
            _gate(
                "P1-usable-years",
                usable_years >= protocol.min_usable_years,
                f"usable_years={usable_years}; floor={protocol.min_usable_years}",
                category="power",
            ),
            _gate(
                "P2-count-upper-bound",
                power_ok,
                f"canonical={protocol_canonical_count}; required={required_events}; "
                "optimistic_upper_bound=true",
                category="power",
            ),
        )
    )

    integrity_failed = any(
        not bool(gate["passed"]) for gate in gates if gate["category"] == "integrity"
    )
    power_failed = any(not bool(gate["passed"]) for gate in gates if gate["category"] == "power")
    if integrity_failed:
        verdict, status = "kill_line", "i0_complete"
    elif power_failed:
        verdict, status = "underpowered_stop", "i0_complete"
    else:
        verdict, status = "i0_pass", "awaiting_f0_prd"

    return I0Result(
        line=protocol.line,
        stage=protocol.stage,
        verdict=verdict,
        status=status,
        capital_go=False,
        returns_measured=False,
        counts={
            **(
                {
                    "universe_listing_windows": len(universe_windows),
                    "universe_windows_with_cik": universe_windows_with_cik,
                    "all_original_filer_records": all_original_filer_records,
                    "in_universe_candidates": mapping_total,
                    "out_of_universe_filer_records": out_of_universe_filer_records,
                    "unclassifiable_original_filings": unclassifiable_original_filings,
                }
                if universe_first
                else {}
            ),
            "raw_rows": len(raw),
            "raw_accessions": sum(row.expected for row in reconciliation),
            "item_202_filings": len(item_accessions),
            "item_202_filer_records": item_filer_records,
            "duplicate_conflicts": duplicate_conflicts,
            "valid_acceptance_timestamps": valid_timestamps,
            "mapped_original_filings": mapped,
            "unresolved_amendments": unresolved_amendments,
            "canonical_anchors": canonical_count,
            "protocol_canonical_anchors": protocol_canonical_count,
            "unique_issuers": len(issuer_anchor_counts),
            "partial_year_anchors": sum(
                count
                for year, count in canonical_by_year.items()
                if year > protocol.last_complete_year
            ),
            "usable_years": usable_years,
        },
        folds=tuple(fold for fold in folds if fold["usable"]),
        power={
            "basis_id": power_basis.basis_id,
            "target_power": protocol.power,
            "target_effect": protocol.target_effect,
            "primary_clustered_t": protocol.primary_clustered_t,
            "power_z_beta": protocol.power_z_beta,
            "required_events": required_events,
            "observed_upper_bound_events": protocol_canonical_count,
            "passed": power_ok,
            "label": "optimistic_count_only_upper_bound_before_liquidity_or_horizon_deoverlap",
        },
        gates=tuple(gates),
        decision_ledger=tuple(ledger_by_identity[key] for key in sorted(ledger_by_identity)),
        year_counts=dict(sorted(year_counts.items())),
        collisions=tuple(collisions),
        concentration={
            "max_issuer": max_issuer[0],
            "max_issuer_anchors": max_issuer[1],
            "max_issuer_share": (max_issuer[1] / canonical_count if canonical_count else 0.0),
            "max_session": (
                max_session[0].isoformat() if isinstance(max_session[0], date) else None
            ),
            "max_session_anchors": max_session[1],
            "max_session_share": (max_session[1] / canonical_count if canonical_count else 0.0),
        },
        universe_coverage=(
            {
                "global": {
                    "windows": len(universe_windows),
                    "with_cik": universe_windows_with_cik,
                    "rate": (
                        universe_windows_with_cik / len(universe_windows)
                        if universe_windows
                        else 0.0
                    ),
                },
                "by_exchange": {
                    exchange: {
                        "windows": values[0],
                        "with_cik": values[1],
                        "rate": values[1] / values[0] if values[0] else 0.0,
                    }
                    for exchange, values in sorted(universe_by_exchange.items())
                },
                "by_year": {
                    str(year): {
                        "windows": values[0],
                        "with_cik": values[1],
                        "rate": values[1] / values[0] if values[0] else 0.0,
                    }
                    for year, values in sorted(universe_by_year.items())
                },
            }
            if universe_first
            else None
        ),
    )


def refuse_f0() -> None:
    raise PermissionError("F0 refused: issue #83 authorizes I0 only; a separate F0 PRD is required")


def refuse_e1() -> None:
    raise PermissionError(
        "E1 refused: issue #83 authorizes I0 only; separate F0 and E1 PRDs are required"
    )
