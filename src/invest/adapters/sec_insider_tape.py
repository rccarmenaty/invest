"""SEC Insider Transactions Data Sets reader (Forms 3/4/5, 2006-).

Fail-closed adapter over the quarterly tab-delimited archives published at
sec.gov. A truncated archive, a missing required column, or an unparseable
numeric raises rather than yielding a short panel that would silently
understate event density and make a sparse tape look like a real null.

The tape carries ``FILING_DATE`` at day granularity only — there is no
acceptance timestamp — so ``filing_date`` is the sole knowledge-time axis.
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from invest.domain.models import InsiderTransaction

SUBMISSION_COLUMNS = frozenset(
    {"ACCESSION_NUMBER", "FILING_DATE", "DOCUMENT_TYPE", "ISSUERCIK", "ISSUERTRADINGSYMBOL"}
)
NONDERIV_COLUMNS = frozenset(
    {
        "ACCESSION_NUMBER",
        "TRANS_DATE",
        "TRANS_CODE",
        "TRANS_SHARES",
        "TRANS_PRICEPERSHARE",
        "TRANS_ACQUIRED_DISP_CD",
        "DIRECT_INDIRECT_OWNERSHIP",
    }
)
REPORTINGOWNER_COLUMNS = frozenset({"ACCESSION_NUMBER", "RPTOWNERCIK"})


class InsiderTapeError(RuntimeError):
    """Raised when the tape cannot be read exactly as published."""


def parse_form_index_form4(lines) -> tuple[int, frozenset[str]]:
    """Count Form 4 / 4/A rows in an EDGAR quarterly ``form.idx``.

    The index lists each filing once per (form, filer) appearance, so raw line
    counts run ~2× the submission count. Integrity comparisons bind on the
    *unique accession numbers* (second element); the raw 4/4A line count is
    returned first as a diagnostic.
    """

    started = False
    form4_lines = 0
    accessions: set[str] = set()
    for line in lines:
        if not started:
            if line.startswith("---"):
                started = True
            continue
        if line[:12].strip() not in {"4", "4/A"}:
            continue
        form4_lines += 1
        parts = line.split()
        if not parts:
            continue
        filename = parts[-1]
        if filename.endswith(".txt"):
            accessions.add(filename.rsplit("/", 1)[-1][:-4])
    return form4_lines, frozenset(accessions)


def _parse_date(raw: str, *, field: str) -> date:
    text = (raw or "").strip()
    if not text:
        raise InsiderTapeError(f"{field} is empty")
    for fmt in ("%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise InsiderTapeError(f"{field} is not a recognised date: {text!r}")


def _parse_decimal(raw: str) -> Decimal | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        raise InsiderTapeError(f"unparseable numeric: {text!r}") from None


def _read_table(archive: zipfile.ZipFile, name: str, required: frozenset[str]) -> list[dict]:
    if name not in archive.namelist():
        raise InsiderTapeError(f"archive is missing {name}")
    with archive.open(name) as handle:
        text = io.TextIOWrapper(handle, encoding="utf-8", errors="strict")
        reader = csv.DictReader(text, delimiter="\t")
        header = set(reader.fieldnames or [])
        missing = required - header
        if missing:
            raise InsiderTapeError(f"{name} is missing required columns: {sorted(missing)}")
        return list(reader)


@dataclass(frozen=True)
class SecInsiderTapeReader:
    """Reads one cached quarterly archive into typed transactions.

    Archives are expected on disk (see the research driver for the polite,
    resumable download); this adapter never reaches the network.
    """

    cache_dir: Path

    def archive_path(self, year: int, quarter: int) -> Path:
        return self.cache_dir / f"{year}q{quarter}_form345.zip"

    def load_quarter(self, year: int, quarter: int) -> tuple[InsiderTransaction, ...]:
        path = self.archive_path(year, quarter)
        if not path.is_file():
            raise InsiderTapeError(f"missing quarterly archive: {path}")
        try:
            archive = zipfile.ZipFile(path)
        except zipfile.BadZipFile as exc:
            raise InsiderTapeError(f"corrupt archive: {path}") from exc
        with archive:
            if archive.testzip() is not None:
                raise InsiderTapeError(f"truncated archive: {path}")
            submissions = _read_table(archive, "SUBMISSION.tsv", SUBMISSION_COLUMNS)
            transactions = _read_table(archive, "NONDERIV_TRANS.tsv", NONDERIV_COLUMNS)
            owners = _read_table(archive, "REPORTINGOWNER.tsv", REPORTINGOWNER_COLUMNS)

        submission_by_accession = {
            row["ACCESSION_NUMBER"]: row for row in submissions if row.get("ACCESSION_NUMBER")
        }
        owner_by_accession: dict[str, str] = {}
        for row in owners:
            accession = row.get("ACCESSION_NUMBER")
            if accession and accession not in owner_by_accession:
                owner_by_accession[accession] = (row.get("RPTOWNERCIK") or "").strip()

        parsed: list[InsiderTransaction] = []
        for row in transactions:
            accession = (row.get("ACCESSION_NUMBER") or "").strip()
            submission = submission_by_accession.get(accession)
            if submission is None:
                # A transaction with no submission row cannot be dated or
                # attributed; the tape is not internally consistent.
                raise InsiderTapeError(f"transaction references unknown submission: {accession!r}")
            symbol = (submission.get("ISSUERTRADINGSYMBOL") or "").strip().upper()
            owner_cik = owner_by_accession.get(accession, "")
            shares = _parse_decimal(row.get("TRANS_SHARES", ""))
            price = _parse_decimal(row.get("TRANS_PRICEPERSHARE", ""))
            if shares is None or price is None:
                # Footnoted-only amounts are common and legitimate; they cannot
                # clear a dollar floor, so they are dropped rather than guessed.
                continue
            original_raw = (submission.get("DATE_OF_ORIG_SUB") or "").strip()
            parsed.append(
                InsiderTransaction(
                    accession_number=accession,
                    issuer_cik=(submission.get("ISSUERCIK") or "").strip(),
                    trading_symbol=symbol,
                    owner_cik=owner_cik,
                    filing_date=_parse_date(submission.get("FILING_DATE", ""), field="FILING_DATE"),
                    transaction_date=_parse_date(row.get("TRANS_DATE", ""), field="TRANS_DATE"),
                    transaction_code=(row.get("TRANS_CODE") or "").strip().upper(),
                    acquired_disposed=(row.get("TRANS_ACQUIRED_DISP_CD") or "").strip().upper(),
                    shares=shares,
                    price_per_share=price,
                    direct_ownership=(row.get("DIRECT_INDIRECT_OWNERSHIP") or "").strip().upper()
                    == "D",
                    document_type=(submission.get("DOCUMENT_TYPE") or "").strip(),
                    original_submission_date=(
                        _parse_date(original_raw, field="DATE_OF_ORIG_SUB") if original_raw else None
                    ),
                    late_filing=(row.get("TRANS_TIMELINESS") or "").strip().upper() == "L",
                    source_table="NONDERIV_TRANS",
                )
            )
        return tuple(parsed)
