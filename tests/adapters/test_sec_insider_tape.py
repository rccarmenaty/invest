"""Contract tests for the SEC insider tape seam.

Small archives are built in-test rather than checked in as binaries, so the
exact bytes under test are visible in the test source. No network.
"""

from __future__ import annotations

import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from invest.adapters.sec_insider_tape import InsiderTapeError, SecInsiderTapeReader

SUBMISSION = (
    "ACCESSION_NUMBER\tFILING_DATE\tDOCUMENT_TYPE\tISSUERCIK\tISSUERTRADINGSYMBOL\tDATE_OF_ORIG_SUB\n"
    "0001-24-000001\t05-MAR-2024\t4\t0000320193\taapl\t\n"
    "0001-24-000002\t07-MAR-2024\t4/A\t0000320193\tAAPL\t05-MAR-2024\n"
)
NONDERIV = (
    "ACCESSION_NUMBER\tTRANS_DATE\tTRANS_CODE\tTRANS_SHARES\tTRANS_PRICEPERSHARE\t"
    "TRANS_ACQUIRED_DISP_CD\tDIRECT_INDIRECT_OWNERSHIP\tTRANS_TIMELINESS\n"
    "0001-24-000001\t04-MAR-2024\tP\t1000\t150.25\tA\tD\t\n"
    "0001-24-000002\t04-MAR-2024\tP\t1000\t150.25\tA\tD\tL\n"
)
REPORTINGOWNER = (
    "ACCESSION_NUMBER\tRPTOWNERCIK\n"
    "0001-24-000001\t0001111111\n"
    "0001-24-000002\t0001111111\n"
)


def _write_archive(path: Path, *, tables: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in tables.items():
            archive.writestr(name, body)


def _valid_tables() -> dict[str, str]:
    return {
        "SUBMISSION.tsv": SUBMISSION,
        "NONDERIV_TRANS.tsv": NONDERIV,
        "REPORTINGOWNER.tsv": REPORTINGOWNER,
    }


def test_reads_typed_transactions_from_a_well_formed_archive(tmp_path: Path) -> None:
    reader = SecInsiderTapeReader(cache_dir=tmp_path)
    _write_archive(reader.archive_path(2024, 1), tables=_valid_tables())

    transactions = reader.load_quarter(2024, 1)

    assert len(transactions) == 2
    first = transactions[0]
    assert first.trading_symbol == "AAPL"  # as-filed lowercase is normalised
    assert first.filing_date == date(2024, 3, 5)
    assert first.transaction_date == date(2024, 3, 4)
    assert first.transaction_code == "P"
    assert first.shares == Decimal("1000")
    assert first.price_per_share == Decimal("150.25")
    assert first.gross_value == Decimal("150250.00")
    assert first.direct_ownership is True
    assert first.is_amendment is False


def test_identifies_amendments_and_their_original_submission(tmp_path: Path) -> None:
    reader = SecInsiderTapeReader(cache_dir=tmp_path)
    _write_archive(reader.archive_path(2024, 1), tables=_valid_tables())

    amendment = reader.load_quarter(2024, 1)[1]

    assert amendment.is_amendment is True
    assert amendment.original_submission_date == date(2024, 3, 5)
    assert amendment.late_filing is True


def test_missing_archive_fails_closed(tmp_path: Path) -> None:
    reader = SecInsiderTapeReader(cache_dir=tmp_path)

    with pytest.raises(InsiderTapeError, match="missing quarterly archive"):
        reader.load_quarter(2024, 1)


def test_corrupt_archive_fails_closed(tmp_path: Path) -> None:
    reader = SecInsiderTapeReader(cache_dir=tmp_path)
    reader.archive_path(2024, 1).write_bytes(b"not a zip file")

    with pytest.raises(InsiderTapeError, match="corrupt archive"):
        reader.load_quarter(2024, 1)


def test_missing_table_fails_closed(tmp_path: Path) -> None:
    reader = SecInsiderTapeReader(cache_dir=tmp_path)
    tables = _valid_tables()
    del tables["NONDERIV_TRANS.tsv"]
    _write_archive(reader.archive_path(2024, 1), tables=tables)

    with pytest.raises(InsiderTapeError, match="missing NONDERIV_TRANS.tsv"):
        reader.load_quarter(2024, 1)


def test_missing_required_column_fails_closed(tmp_path: Path) -> None:
    reader = SecInsiderTapeReader(cache_dir=tmp_path)
    tables = _valid_tables()
    tables["NONDERIV_TRANS.tsv"] = (
        "ACCESSION_NUMBER\tTRANS_DATE\tTRANS_SHARES\tTRANS_PRICEPERSHARE\t"
        "TRANS_ACQUIRED_DISP_CD\tDIRECT_INDIRECT_OWNERSHIP\n"
        "0001-24-000001\t04-MAR-2024\t1000\t150.25\tA\tD\n"
    )
    _write_archive(reader.archive_path(2024, 1), tables=tables)

    with pytest.raises(InsiderTapeError, match="TRANS_CODE"):
        reader.load_quarter(2024, 1)


def test_transaction_without_its_submission_fails_closed(tmp_path: Path) -> None:
    reader = SecInsiderTapeReader(cache_dir=tmp_path)
    tables = _valid_tables()
    tables["NONDERIV_TRANS.tsv"] = NONDERIV + (
        "0001-24-000099\t04-MAR-2024\tP\t500\t10.00\tA\tD\t\n"
    )
    _write_archive(reader.archive_path(2024, 1), tables=tables)

    with pytest.raises(InsiderTapeError, match="unknown submission"):
        reader.load_quarter(2024, 1)


def test_unparseable_date_fails_closed(tmp_path: Path) -> None:
    reader = SecInsiderTapeReader(cache_dir=tmp_path)
    tables = _valid_tables()
    tables["SUBMISSION.tsv"] = SUBMISSION.replace("05-MAR-2024\t4\t", "not-a-date\t4\t")
    _write_archive(reader.archive_path(2024, 1), tables=tables)

    with pytest.raises(InsiderTapeError, match="FILING_DATE"):
        reader.load_quarter(2024, 1)


def test_footnoted_amounts_are_dropped_not_guessed(tmp_path: Path) -> None:
    reader = SecInsiderTapeReader(cache_dir=tmp_path)
    tables = _valid_tables()
    tables["NONDERIV_TRANS.tsv"] = (
        "ACCESSION_NUMBER\tTRANS_DATE\tTRANS_CODE\tTRANS_SHARES\tTRANS_PRICEPERSHARE\t"
        "TRANS_ACQUIRED_DISP_CD\tDIRECT_INDIRECT_OWNERSHIP\tTRANS_TIMELINESS\n"
        "0001-24-000001\t04-MAR-2024\tP\t\t\tA\tD\t\n"
    )
    _write_archive(reader.archive_path(2024, 1), tables=tables)

    assert reader.load_quarter(2024, 1) == ()
