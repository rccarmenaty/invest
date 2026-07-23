"""Public behavior for the source-neutral SEC 8-K Item 2.02 I0 evaluator."""

from __future__ import annotations

from datetime import date, datetime, timezone

from invest.application.sec8k_i0 import (
    FilingRecord,
    I0Protocol,
    ListingRecord,
    PowerBasis,
    ReconciliationRecord,
    SessionRecord,
    UniverseFirstProtocol,
    evaluate_i0,
)


def _assert_false(value: object) -> None:
    assert isinstance(value, bool)
    assert not value


def test_clean_source_builds_prior_only_folds_and_stops_awaiting_a_separate_f0_prd() -> None:
    filings = []
    sessions = []
    for year in (2020, 2021, 2022):
        for ordinal, day in enumerate((10, 11), start=1):
            accession = f"0000000001-{year % 100:02d}-{ordinal:06d}"
            filings.append(
                FilingRecord(
                    accession_number=accession,
                    cik="0000000001",
                    form="8-K",
                    filing_date=date(year, 1, day),
                    acceptance_raw=f"{year}0109{120000 + ordinal:06d}",
                    acceptance_at=datetime(year, 1, day - 1, 17, tzinfo=timezone.utc),
                    source_url=f"https://www.sec.gov/Archives/edgar/data/1/{accession}.txt",
                    content_sha256=(f"{year}{ordinal}".encode().hex() + "0" * 64)[:64],
                    item_codes=("2.02",),
                    item_202_evidence=("sec_metadata",),
                    source_occurrences=(f"{year}Q1/full-index",),
                    as_filed_ticker="ACME",
                )
            )
            sessions.append(
                SessionRecord(
                    session_date=date(year, 1, day),
                    market_open=datetime(year, 1, day, 14, 30, tzinfo=timezone.utc),
                )
            )

    result = evaluate_i0(
        filings=filings,
        listings=(
            ListingRecord(
                symbol="ACME",
                cik="1",
                related_symbols=(),
                first_date=date(2019, 1, 1),
                last_date=None,
                us_primary_common=True,
            ),
        ),
        sessions=sessions,
        reconciliation=(
            ReconciliationRecord(
                year=2020,
                quarter=1,
                form="8-K",
                expected=2,
                fetched=2,
                parsed=2,
                failed=0,
                excluded=0,
            ),
            ReconciliationRecord(2021, 1, "8-K", 2, 2, 2, 0, 0),
            ReconciliationRecord(2022, 1, "8-K", 2, 2, 2, 0, 0),
        ),
        power_basis=PowerBasis(
            basis_id="pre-sec8k-basis",
            created_at=datetime(2019, 1, 1, tzinfo=timezone.utc),
            effective_sigma=0.001,
            provenance="Frozen before SEC-8K outcome inspection",
        ),
        protocol=I0Protocol(
            line="custom-sec8k-line",
            stage="custom-i0-stage",
            min_usable_years=1,
            min_prior_years=2,
            min_prior_events=4,
            require_complete_quarter_forms=False,
            power=0.80,
            target_effect=0.01,
        ),
    )

    assert result.verdict == "i0_pass"
    assert result.status == "awaiting_f0_prd"
    serialized = result.to_dict()
    assert serialized["line"] == "custom-sec8k-line"
    assert serialized["stage"] == "custom-i0-stage"
    _assert_false(result.capital_go)
    _assert_false(result.returns_measured)
    assert result.counts["canonical_anchors"] == 6
    expected_folds = (
        {"year": 2022, "prior_years": 2, "prior_canonical_events": 4, "usable": True},
    )
    assert result.folds == expected_folds
    assert len(result.decision_ledger) == 6
    assert all(row["decision"] == "canonical_anchor" for row in result.decision_ledger)

    underpowered = evaluate_i0(
        filings=filings,
        listings=(ListingRecord("ACME", "1", (), date(2019, 1, 1), None, True),),
        sessions=sessions,
        reconciliation=(
            ReconciliationRecord(2020, 1, "8-K", 2, 2, 2, 0, 0),
            ReconciliationRecord(2021, 1, "8-K", 2, 2, 2, 0, 0),
            ReconciliationRecord(2022, 1, "8-K", 2, 2, 2, 0, 0),
        ),
        power_basis=PowerBasis(
            "pre-sec8k-basis",
            datetime(2019, 1, 1, tzinfo=timezone.utc),
            0.01,
            "Frozen before SEC-8K outcome inspection",
        ),
        protocol=I0Protocol(
            min_usable_years=1,
            min_prior_years=2,
            min_prior_events=4,
            require_complete_quarter_forms=False,
            target_effect=0.000001,
        ),
    )
    assert underpowered.verdict == "underpowered_stop"

    integrity_and_power_fail = evaluate_i0(
        filings=filings,
        listings=(ListingRecord("ACME", "1", (), date(2019, 1, 1), None, True),),
        sessions=sessions,
        reconciliation=(ReconciliationRecord(2020, 1, "8-K", 6, 5, 5, 1, 0),),
        power_basis=PowerBasis(
            "pre-sec8k-basis",
            datetime(2019, 1, 1, tzinfo=timezone.utc),
            0.01,
            "Frozen before SEC-8K outcome inspection",
        ),
        protocol=I0Protocol(
            min_usable_years=1,
            min_prior_years=2,
            min_prior_events=4,
            require_complete_quarter_forms=False,
            target_effect=0.000001,
        ),
    )
    assert integrity_and_power_fail.verdict == "kill_line"


def test_mapping_ladder_amendments_and_same_session_collisions_remain_auditable() -> None:
    accepted = datetime(2024, 3, 8, 22, tzinfo=timezone.utc)

    def filing(
        accession: str,
        cik: str,
        ticker: str,
        *,
        form: str = "8-K",
        amendment_of: str | None = None,
    ) -> FilingRecord:
        return FilingRecord(
            accession_number=accession,
            cik=cik,
            form=form,
            filing_date=date(2024, 3, 8),
            acceptance_raw="20240308170000",
            acceptance_at=accepted,
            source_url=f"https://www.sec.gov/Archives/{accession}.txt",
            content_sha256=(accession.encode().hex() + "0" * 64)[:64],
            item_codes=("2.02", "9.01"),
            item_202_evidence=("filing_body",),
            source_occurrences=("2024Q1/master.idx",),
            as_filed_ticker=ticker,
            amendment_of=amendment_of,
        )

    records = (
        filing("0000000001-24-000001", "0001", "ACME"),
        filing("0000000001-24-000002", "0001", "ACME"),
        filing(
            "0000000001-24-000003",
            "0001",
            "ACME",
            form="8-K/A",
            amendment_of="0000000001-24-000001",
        ),
        filing("0000000002-24-000001", "0002", "OLD"),
        filing("0000000003-24-000001", "0003", "UNKNOWN"),
    )
    result = evaluate_i0(
        filings=records,
        listings=(
            ListingRecord("ACME", "1", (), date(2020, 1, 1), None, True),
            ListingRecord("NEW", "2", ("OLD",), date(2020, 1, 1), None, True),
            ListingRecord("CLASSA", "3", (), date(2020, 1, 1), None, True),
            ListingRecord("CLASSB", "3", (), date(2020, 1, 1), None, True),
        ),
        sessions=(
            SessionRecord(
                date(2024, 3, 11),
                datetime(2024, 3, 11, 13, 30, tzinfo=timezone.utc),
            ),
        ),
        reconciliation=(
            ReconciliationRecord(2024, 1, "8-K", 4, 4, 4, 0, 0),
            ReconciliationRecord(2024, 1, "8-K/A", 1, 1, 1, 0, 0),
        ),
        power_basis=PowerBasis(
            "preexisting",
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            0.001,
            "frozen before outcomes",
        ),
        protocol=I0Protocol(
            min_mapping_rate=0.70,
            min_usable_years=0,
            min_prior_events=0,
            require_complete_quarter_forms=False,
        ),
    )

    assert result.verdict == "i0_pass"
    assert result.counts["canonical_anchors"] == 2
    assert result.counts["unresolved_amendments"] == 0
    assert result.year_counts[2024]["mapping_total"] == 4
    assert result.year_counts[2024]["mapped_original_filings"] == 3
    assert result.year_counts[2024]["mapping_rate"] == 0.75
    assert result.year_counts[2024]["unique_issuers"] == 2
    assert result.collisions[0]["accession_numbers"] == [
        "0000000001-24-000001",
        "0000000001-24-000002",
    ]
    ledger = {row["accession_number"]: row for row in result.decision_ledger}
    assert ledger["0000000001-24-000003"]["decision"] == "amendment_linked_excluded"
    assert ledger["0000000002-24-000001"]["reasons"] == ["matched_related_symbol"]
    assert ledger["0000000003-24-000001"]["reasons"] == ["ambiguous_excluded"]


def test_complete_reconciliation_rejects_a_self_consistent_truncated_period() -> None:
    accession = "0000000001-25-000001"
    reconciliation = tuple(
        ReconciliationRecord(
            2025,
            quarter,
            form,
            1 if quarter == 1 and form == "8-K" else 0,
            1 if quarter == 1 and form == "8-K" else 0,
            1 if quarter == 1 and form == "8-K" else 0,
            0,
            0,
        )
        for quarter in (1, 2, 3, 4)
        for form in ("8-K", "8-K/A")
    )
    result = evaluate_i0(
        filings=(
            FilingRecord(
                accession_number=accession,
                cik="1",
                form="8-K",
                filing_date=date(2025, 1, 2),
                acceptance_raw="20250101170000",
                acceptance_at=datetime(2025, 1, 1, 22, tzinfo=timezone.utc),
                source_url=f"https://www.sec.gov/Archives/{accession}.txt",
                content_sha256=(accession.encode().hex() + "0" * 64)[:64],
                item_codes=("2.02",),
                item_202_evidence=("filing_body",),
                source_occurrences=("2025Q1/master.idx",),
                as_filed_ticker="ACME",
            ),
        ),
        listings=(ListingRecord("ACME", "1", (), date(2020, 1, 1), None, True),),
        sessions=(
            SessionRecord(
                date(2025, 1, 2),
                datetime(2025, 1, 2, 14, 30, tzinfo=timezone.utc),
            ),
        ),
        reconciliation=reconciliation,
        power_basis=PowerBasis(
            "preexisting",
            datetime(2020, 1, 1, tzinfo=timezone.utc),
            0.001,
            "frozen before outcomes",
        ),
        protocol=I0Protocol(min_usable_years=0, min_prior_events=0),
    )

    assert result.verdict == "kill_line"
    reconcile_gate = next(gate for gate in result.gates if gate["id"] == "I1-reconciliation")
    _assert_false(reconcile_gate["passed"])


def test_power_upper_bound_excludes_filings_outside_the_frozen_protocol_years() -> None:
    filings = []
    sessions = []
    reconciliation = []
    for year in (2003, 2004, 2026):
        accession = f"0000000001-{year % 100:02d}-000001"
        filings.append(
            FilingRecord(
                accession_number=accession,
                cik="1",
                form="8-K",
                filing_date=date(year, 1, 2),
                acceptance_raw=f"{year}0101170000",
                acceptance_at=datetime(year, 1, 1, 22, tzinfo=timezone.utc),
                source_url=f"https://www.sec.gov/Archives/{accession}.txt",
                content_sha256=(accession.encode().hex() + "0" * 64)[:64],
                item_codes=("2.02",),
                item_202_evidence=("filing_body",),
                source_occurrences=(f"{year}Q1/master.idx",),
                as_filed_ticker="ACME",
            )
        )
        sessions.append(
            SessionRecord(
                date(year, 1, 2),
                datetime(year, 1, 2, 14, 30, tzinfo=timezone.utc),
            )
        )
        reconciliation.append(ReconciliationRecord(year, 1, "8-K", 1, 1, 1, 0, 0))

    result = evaluate_i0(
        filings=filings,
        listings=(ListingRecord("ACME", "1", (), date(2000, 1, 1), None, True),),
        sessions=sessions,
        reconciliation=reconciliation,
        power_basis=PowerBasis(
            "preexisting",
            datetime(2000, 1, 1, tzinfo=timezone.utc),
            0.014,
            "frozen before outcomes",
        ),
        protocol=I0Protocol(
            regime_start_year=2004,
            last_complete_year=2025,
            min_usable_years=0,
            min_prior_events=0,
            require_complete_quarter_forms=False,
        ),
    )

    assert result.verdict == "underpowered_stop"
    assert result.power["observed_upper_bound_events"] == 1
    assert result.power["required_events"] == 22


def test_universe_first_mapping_composition_uses_the_strictly_later_known_session_year() -> None:
    filing = FilingRecord(
        accession_number="0000000001-05-000001",
        cik="1",
        form="8-K",
        filing_date=date(2005, 12, 31),
        acceptance_raw="20051231220000",
        acceptance_at=datetime(2005, 12, 31, 22, 0, tzinfo=timezone.utc),
        source_url="https://www.sec.gov/Archives/edgar/data/1/0000000001-05-000001.txt",
        content_sha256="a" * 64,
        item_codes=("2.02",),
        item_202_evidence=("sec_item_metadata",),
        source_occurrences=("2005Q4/master.idx",),
        as_filed_ticker="ACME",
    )
    result = evaluate_i0(
        filings=(filing,),
        listings=(
            ListingRecord(
                "ACME",
                "1",
                (),
                date(2000, 1, 1),
                None,
                True,
                exchange="XNYS",
            ),
        ),
        sessions=(
            SessionRecord(
                session_date=date(2006, 1, 2),
                market_open=datetime(2006, 1, 2, 14, 30, tzinfo=timezone.utc),
            ),
        ),
        reconciliation=(
            ReconciliationRecord(
                year=2005,
                quarter=4,
                form="8-K",
                expected=1,
                fetched=1,
                parsed=1,
                item_202=1,
                failed=0,
                excluded=0,
            ),
        ),
        power_basis=PowerBasis(
            basis_id="pre-source-count-only",
            created_at=datetime(2004, 1, 1, tzinfo=timezone.utc),
            effective_sigma=0.001,
            provenance="Frozen before SEC outcome inspection",
        ),
        protocol=UniverseFirstProtocol(
            regime_start_year=2005,
            last_complete_year=2006,
            min_prior_years=0,
            min_prior_events=0,
            min_usable_years=0,
            require_complete_quarter_forms=False,
        ),
        universe_first=True,
    )

    assert result.year_counts[2005]["mapping_total"] == 0
    assert result.year_counts[2006]["mapping_total"] == 1
    assert result.year_counts[2006]["mapped_original_filings"] == 1


def test_joint_filer_accession_maps_each_cik_without_duplicate_conflict() -> None:
    accession = "0000000001-24-000001"
    acceptance = datetime(2024, 3, 8, 22, tzinfo=timezone.utc)
    filings = tuple(
        FilingRecord(
            accession_number=accession,
            cik=cik,
            form="8-K",
            filing_date=date(2024, 3, 8),
            acceptance_raw="2024-03-08T22:00:00Z",
            acceptance_at=acceptance,
            source_url=(
                "https://data.sec.gov/submissions/submissions.zip"
                f"#CIK{cik.zfill(10)}.json:{accession}"
            ),
            content_sha256=(cik.encode().hex() + "0" * 64)[:64],
            item_codes=("2.02",),
            item_202_evidence=("sec_item_metadata",),
            source_occurrences=(f"CIK{cik.zfill(10)}.json:0",),
        )
        for cik in ("1", "2")
    )
    result = evaluate_i0(
        filings=filings,
        listings=(
            ListingRecord("ACME", "1", (), date(2020, 1, 1), None, True),
            ListingRecord("OTHER", "2", (), date(2020, 1, 1), None, True),
        ),
        sessions=(
            SessionRecord(
                session_date=date(2024, 3, 11),
                market_open=datetime(2024, 3, 11, 13, 30, tzinfo=timezone.utc),
            ),
        ),
        reconciliation=(
            ReconciliationRecord(
                year=2024,
                quarter=1,
                form="8-K",
                expected=1,
                fetched=1,
                parsed=1,
                failed=0,
                excluded=0,
                item_202=1,
            ),
        ),
        power_basis=PowerBasis(
            "preexisting",
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            0.001,
            "frozen",
        ),
        protocol=I0Protocol(
            min_usable_years=0,
            min_prior_years=0,
            min_prior_events=0,
            require_complete_quarter_forms=False,
        ),
    )

    assert result.verdict == "i0_pass"
    assert result.counts["raw_accessions"] == 1
    assert result.counts["item_202_filer_records"] == 2
    assert result.counts["canonical_anchors"] == 2
    assert result.counts["duplicate_conflicts"] == 0
    assert len(result.decision_ledger) == 2
    assert {row["cik"] for row in result.decision_ledger} == {"1", "2"}
    assert result.power["primary_clustered_t"] == 2.5
    assert result.power["power_z_beta"] == 0.841621


def test_item_202_parse_errors_remain_in_the_acceptance_timestamp_denominator() -> None:
    def filing(accession: str, *, parse_error: str | None = None) -> FilingRecord:
        return FilingRecord(
            accession_number=accession,
            cik="1",
            form="8-K",
            filing_date=date(2024, 3, 8),
            acceptance_raw="20240308170000" if parse_error is None else None,
            acceptance_at=(
                datetime(2024, 3, 8, 22, tzinfo=timezone.utc) if parse_error is None else None
            ),
            source_url=f"https://www.sec.gov/Archives/{accession}.txt",
            content_sha256="a" * 64,
            item_codes=("2.02",),
            item_202_evidence=("sec_item_metadata",),
            source_occurrences=("2024Q1/master.idx",),
            as_filed_ticker="ACME",
            parse_error=parse_error,
        )

    result = evaluate_i0(
        filings=(
            filing("0000000001-24-000001"),
            filing("0000000001-24-000002", parse_error="malformed acceptance timestamp"),
        ),
        listings=(ListingRecord("ACME", "1", (), date(2020, 1, 1), None, True),),
        sessions=(
            SessionRecord(
                date(2024, 3, 11),
                datetime(2024, 3, 11, 13, 30, tzinfo=timezone.utc),
            ),
        ),
        reconciliation=(ReconciliationRecord(2024, 1, "8-K", 2, 2, 2, 0, 0, 2),),
        power_basis=PowerBasis(
            "preexisting",
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            0.001,
            "frozen",
        ),
        protocol=I0Protocol(
            min_timestamp_rate=0.75,
            min_usable_years=0,
            min_prior_years=0,
            min_prior_events=0,
            require_complete_quarter_forms=False,
        ),
    )

    timestamp_gate = next(gate for gate in result.gates if gate["id"] == "I4-acceptance-timestamps")
    assert timestamp_gate["reason"] == "valid=1/2; rate=0.500000"
    assert result.verdict == "kill_line"


def test_embedded_digit_ciks_fail_closed_in_filing_first_and_universe_first_mapping() -> None:
    filing = FilingRecord(
        accession_number="0000000001-24-000001",
        cik="issuer CIK 1",
        form="8-K",
        filing_date=date(2024, 3, 8),
        acceptance_raw="20240308170000",
        acceptance_at=datetime(2024, 3, 8, 22, tzinfo=timezone.utc),
        source_url="https://www.sec.gov/Archives/0000000001-24-000001.txt",
        content_sha256="a" * 64,
        item_codes=("2.02",),
        item_202_evidence=("sec_item_metadata",),
        source_occurrences=("2024Q1/master.idx",),
        as_filed_ticker="ACME",
    )
    common = {
        "filings": (filing,),
        "listings": (ListingRecord("ACME", "1", (), date(2020, 1, 1), None, True),),
        "sessions": (
            SessionRecord(
                date(2024, 3, 11),
                datetime(2024, 3, 11, 13, 30, tzinfo=timezone.utc),
            ),
        ),
        "reconciliation": (ReconciliationRecord(2024, 1, "8-K", 1, 1, 1, 0, 0, 1),),
        "power_basis": PowerBasis(
            "preexisting",
            datetime(2023, 1, 1, tzinfo=timezone.utc),
            0.001,
            "frozen",
        ),
    }

    filing_first = evaluate_i0(
        **common,
        protocol=I0Protocol(
            min_usable_years=0,
            min_prior_years=0,
            min_prior_events=0,
            require_complete_quarter_forms=False,
        ),
    )
    universe_first = evaluate_i0(
        **common,
        protocol=UniverseFirstProtocol(
            min_usable_years=0,
            min_prior_years=0,
            min_prior_events=0,
            require_complete_quarter_forms=False,
        ),
        universe_first=True,
    )

    assert filing_first.verdict == "kill_line"
    assert filing_first.counts["mapped_original_filings"] == 0
    assert universe_first.verdict == "kill_line"
    assert universe_first.counts["unclassifiable_original_filings"] == 1
