"""Fail-closed SEC EDGAR source adapter for 8-K Item 2.02 I0.

The parser is fixture-friendly and the acquisition client is resumable.  Network
requests are restricted to SEC hosts, carry an identifying User-Agent, are paced,
and use bounded retry/backoff.  Cached response bodies are immutable content-hash
objects; every cache hit is re-hashed before use.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Callable, Protocol, cast
from urllib.parse import urlparse
from zipfile import BadZipFile, ZipFile
from zoneinfo import ZoneInfo

import httpx  # pyright: ignore[reportMissingImports]

from invest.application.sec8k_i0 import (
    FilingRecord,
    I0SealingError,
    canonical_i0_json,
    digest_i0_json,
    seal_i0_manifest,
)


SEC_HOSTS = frozenset({"www.sec.gov", "sec.gov", "data.sec.gov", "archives.sec.gov"})
_ACCESSION_RE = re.compile(r"(?P<accession>\d{10}-\d{2}-\d{6})")
_ITEM_RE = re.compile(r"\b(?:ITEM\s*)?(\d+\.\d{2})\b", re.IGNORECASE)


class SecEdgar8kError(RuntimeError):
    """SEC source bytes are missing, malformed, unsafe, or unverifiable."""


@dataclass(frozen=True)
class FullIndexRecord:
    year: int
    quarter: int
    cik: str
    company_name: str
    form: str
    filing_date: date
    filename: str
    accession_number: str

    @property
    def source_url(self) -> str:
        return f"https://www.sec.gov/Archives/{self.filename.lstrip('/')}"


def parse_full_index(text: str, *, year: int, quarter: int) -> tuple[FullIndexRecord, ...]:
    """Parse SEC ``master.idx`` and retain unique accession-CIK filer rows."""

    if quarter not in {1, 2, 3, 4}:
        raise SecEdgar8kError(f"invalid quarter: {quarter}")
    records: dict[tuple[str, str], FullIndexRecord] = {}
    header_seen = False
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if line == "CIK|Company Name|Form Type|Date Filed|Filename":
            header_seen = True
            continue
        if not header_seen or not line or "|" not in line:
            continue
        parts = line.split("|")
        if len(parts) != 5:
            raise SecEdgar8kError(f"malformed master.idx row {line_number}")
        cik, company, form, filed, filename = (part.strip() for part in parts)
        if not cik.isdigit():
            raise SecEdgar8kError(f"master.idx row {line_number} has invalid CIK")
        normalized_form = form.upper()
        if normalized_form not in {"8-K", "8-K/A"}:
            continue
        match = _ACCESSION_RE.search(filename)
        if match is None:
            raise SecEdgar8kError(f"8-K row {line_number} has no accession")
        try:
            filing_date = date.fromisoformat(filed)
        except ValueError as error:
            raise SecEdgar8kError(f"8-K row {line_number} has invalid filing date") from error
        accession = match.group("accession")
        record = FullIndexRecord(
            year=year,
            quarter=quarter,
            cik=cik,
            company_name=company,
            form=normalized_form,
            filing_date=filing_date,
            filename=filename,
            accession_number=accession,
        )
        key = (accession, cik.lstrip("0") or "0")
        previous = records.get(key)
        if previous is not None and (
            previous.form != record.form
            or previous.filing_date != record.filing_date
            or previous.filename != record.filename
        ):
            raise SecEdgar8kError(f"conflicting duplicate index accession-CIK: {accession}/{cik}")
        records[key] = record
    if not header_seen:
        raise SecEdgar8kError("master.idx header is missing")
    return tuple(records[key] for key in sorted(records))


def _header_value(text: str, label: str) -> str | None:
    match = re.search(rf"(?mi)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$", text)
    return match.group(1).strip() if match else None


def _parse_acceptance(raw: str) -> datetime:
    value = raw.strip()
    try:
        if re.fullmatch(r"\d{14}", value):
            local = datetime.strptime(value, "%Y%m%d%H%M%S").replace(
                tzinfo=ZoneInfo("America/New_York")
            )
        else:
            local = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if local.tzinfo is None:
                local = local.replace(tzinfo=ZoneInfo("America/New_York"))
        return local.astimezone(timezone.utc)
    except ValueError as error:
        raise SecEdgar8kError(f"malformed acceptance timestamp: {raw!r}") from error


def _filing_date(text: str) -> date:
    raw = _header_value(text, "FILED AS OF DATE")
    if raw is None:
        raise SecEdgar8kError("submission is missing FILED AS OF DATE")
    try:
        return datetime.strptime(raw, "%Y%m%d").date()
    except ValueError as error:
        raise SecEdgar8kError(f"malformed FILED AS OF DATE: {raw!r}") from error


def parse_submission(
    payload: bytes,
    *,
    source_url: str,
    source_occurrence: str,
    metadata_items: tuple[str, ...] | None = None,
    metadata_acceptance: str | None = None,
    metadata_ticker: str | None = None,
) -> FilingRecord:
    """Parse an original SEC complete-submission body into a typed filing record."""

    validate_sec_url(source_url)
    if not payload:
        raise SecEdgar8kError("empty submission")
    text = payload.decode("utf-8", errors="replace")
    if "<DOCUMENT>" not in text.upper() or "<SEC-HEADER>" not in text.upper():
        raise SecEdgar8kError("submission is missing SEC header or document content")
    accession = _header_value(text, "ACCESSION NUMBER")
    if accession is None:
        match = _ACCESSION_RE.search(source_url)
        accession = match.group("accession") if match else None
    if accession is None or _ACCESSION_RE.fullmatch(accession) is None:
        raise SecEdgar8kError("submission accession is missing or malformed")
    form = (_header_value(text, "CONFORMED SUBMISSION TYPE") or "").upper()
    if form not in {"8-K", "8-K/A"}:
        raise SecEdgar8kError(f"unsupported submission form: {form!r}")
    cik = _header_value(text, "CENTRAL INDEX KEY")
    if cik is None:
        path_match = re.search(r"/data/(\d+)/", urlparse(source_url).path)
        cik = path_match.group(1) if path_match else None
    if not cik:
        raise SecEdgar8kError("submission CIK is missing")
    if any(character not in "0123456789" for character in cik):
        raise SecEdgar8kError("submission CIK is malformed")

    header_acceptance = _header_value(text, "ACCEPTANCE-DATETIME")
    raw_acceptance = header_acceptance or metadata_acceptance
    if raw_acceptance is None:
        acceptance_at = None
    else:
        acceptance_at = _parse_acceptance(raw_acceptance)
    if (
        header_acceptance is not None
        and metadata_acceptance is not None
        and _parse_acceptance(header_acceptance) != _parse_acceptance(metadata_acceptance)
    ):
        raise SecEdgar8kError("SEC header and submissions acceptance timestamps conflict")

    header = text.split("</SEC-HEADER>", 1)[0]
    metadata_line = _header_value(header, "ITEM INFORMATION") or ""
    header_items_line = _header_value(header, "ITEMS") or ""
    supplied_items = tuple(metadata_items or ())
    item_codes = sorted(
        {
            match.group(1)
            for value in (metadata_line, header_items_line, *supplied_items)
            for match in _ITEM_RE.finditer(value)
        }
    )
    evidence: list[str] = []
    if (
        "2.02" in supplied_items
        or "2.02" in item_codes
        or "results of operations and financial condition" in metadata_line.lower()
    ):
        evidence.append("sec_item_metadata")
        if "2.02" not in item_codes:
            item_codes.append("2.02")
            item_codes.sort()
    if re.search(r"(?is)\bitem\s+2\.02\b", text):
        evidence.append("filing_body")
        if "2.02" not in item_codes:
            item_codes.append("2.02")
            item_codes.sort()

    conflicts: list[str] = []
    if supplied_items and "2.02" not in supplied_items and "filing_body" in evidence:
        conflicts.append("submissions_metadata_omits_body_item_2.02")
    original = _header_value(text, "ORIGINAL SUBMISSION ACCESSION NUMBER")
    ticker = metadata_ticker or _header_value(text, "TRADING SYMBOL")
    if ticker is None:
        xbrl_ticker = re.search(
            r"(?is)<(?:dei:TradingSymbol|"
            r"ix:nonNumeric\b[^>]*name=[\"']dei:TradingSymbol[\"'][^>]*)>"
            r"\s*([^<]+?)\s*</",
            text,
        )
        ticker = xbrl_ticker.group(1).strip() if xbrl_ticker else None
    return FilingRecord(
        accession_number=accession,
        cik=cik,
        form=form,
        filing_date=_filing_date(text),
        acceptance_raw=raw_acceptance,
        acceptance_at=acceptance_at,
        source_url=source_url,
        content_sha256=sha256(payload).hexdigest(),
        item_codes=tuple(item_codes),
        item_202_evidence=tuple(evidence),
        source_occurrences=(source_occurrence,),
        as_filed_ticker=ticker,
        item_202_conflicts=tuple(conflicts),
        amendment_of=original,
    )


@dataclass(frozen=True)
class SubmissionMetadataRecord:
    accession_number: str
    form: str
    filing_date: date
    acceptance: str | None
    items: tuple[str, ...]
    primary_document: str


def parse_submissions_metadata(payload: bytes) -> tuple[SubmissionMetadataRecord, ...]:
    """Read current or historical SEC submissions-metadata column arrays."""

    try:
        root = json.loads(payload)
        recent = root["filings"]["recent"] if "filings" in root else root
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise SecEdgar8kError("malformed SEC submissions metadata") from error
    required = ("accessionNumber", "form", "filingDate", "primaryDocument")
    if any(name not in recent or not isinstance(recent[name], list) for name in required):
        raise SecEdgar8kError("submissions metadata is missing required arrays")
    lengths = {len(recent[name]) for name in required}
    if len(lengths) != 1:
        raise SecEdgar8kError("submissions metadata arrays have different lengths")
    count = lengths.pop()
    acceptance_values = recent.get("acceptanceDateTime", [None] * count)
    item_values = recent.get("items", [""] * count)
    if len(acceptance_values) != count or len(item_values) != count:
        raise SecEdgar8kError("submissions metadata optional arrays have different lengths")
    records: list[SubmissionMetadataRecord] = []
    for index in range(count):
        form = str(recent["form"][index]).upper()
        if form not in {"8-K", "8-K/A"}:
            continue
        accession = str(recent["accessionNumber"][index])
        if _ACCESSION_RE.fullmatch(accession) is None:
            raise SecEdgar8kError("submissions metadata contains malformed accession")
        raw_items = str(item_values[index] or "")
        try:
            filing_date = date.fromisoformat(str(recent["filingDate"][index]))
        except ValueError as error:
            raise SecEdgar8kError("submissions metadata contains malformed filing date") from error
        records.append(
            SubmissionMetadataRecord(
                accession_number=accession,
                form=form,
                filing_date=filing_date,
                acceptance=(str(acceptance_values[index]) if acceptance_values[index] else None),
                items=tuple(sorted({match.group(1) for match in _ITEM_RE.finditer(raw_items)})),
                primary_document=str(recent["primaryDocument"][index]),
            )
        )
    return tuple(records)


def submissions_history_files(payload: bytes) -> tuple[tuple[str, date, date], ...]:
    """Return validated historical shard names and coverage from a CIK root file."""

    try:
        files = json.loads(payload).get("filings", {}).get("files", [])
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError) as error:
        raise SecEdgar8kError("malformed SEC submissions history listing") from error
    if not isinstance(files, list):
        raise SecEdgar8kError("SEC submissions history listing must be an array")
    result: list[tuple[str, date, date]] = []
    for item in files:
        if not isinstance(item, dict):
            raise SecEdgar8kError("SEC submissions history entry must be an object")
        name = item.get("name")
        if (
            not isinstance(name, str)
            or re.fullmatch(r"CIK\d{10}-submissions-\d{3}\.json", name) is None
        ):
            raise SecEdgar8kError("unsafe SEC submissions history filename")
        try:
            filing_from = date.fromisoformat(str(item["filingFrom"]))
            filing_to = date.fromisoformat(str(item["filingTo"]))
        except (KeyError, ValueError) as error:
            raise SecEdgar8kError("invalid SEC submissions history coverage") from error
        result.append((name, filing_from, filing_to))
    return tuple(sorted(result))


def validate_sec_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in SEC_HOSTS:
        raise SecEdgar8kError(f"SEC URL is outside the allowlist: {url!r}")
    if parsed.username is not None or parsed.password is not None:
        raise SecEdgar8kError("credentials are forbidden in SEC URLs")


class _Response(Protocol):
    status_code: int
    content: bytes


class _Client(Protocol):
    get: Callable[..., _Response]
    close: Callable[[], None]


class _HttpxClient:
    def __init__(self, timeout: float) -> None:
        self._client = httpx.Client(timeout=timeout, follow_redirects=False)

    def get(self, url: str, *, headers: dict[str, str]) -> _Response:
        try:
            response = self._client.get(url, headers=headers)
        except httpx.TransportError as error:
            raise OSError("SEC transport failure") from error
        return cast(_Response, response)

    def close(self) -> None:
        self._client.close()


class SecFairAccessClient:
    """Paced, bounded, content-addressed SEC downloader."""

    def __init__(
        self,
        *,
        cache_dir: Path,
        user_agent: str,
        client: object | None = None,
        min_interval_seconds: float = 0.11,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
        timeout_seconds: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not user_agent.strip() or "@" not in user_agent:
            raise SecEdgar8kError("SEC User-Agent must identify the application and contact email")
        if min_interval_seconds < 0 or max_retries < 0 or backoff_seconds < 0:
            raise SecEdgar8kError("SEC pacing/retry values must be non-negative")
        if client is not None and (
            not callable(getattr(client, "get", None))
            or not callable(getattr(client, "close", None))
        ):
            raise SecEdgar8kError("injected SEC client must provide get() and close()")
        self.cache_dir = cache_dir
        self.user_agent = user_agent
        self.client: _Client = (
            _HttpxClient(timeout_seconds) if client is None else cast(_Client, client)
        )
        self._owns_client = client is None
        self.min_interval_seconds = min_interval_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.sleep = sleep
        self.monotonic = monotonic
        self._last_request_at: float | None = None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> SecFairAccessClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _paths(self, url: str) -> tuple[Path, Path]:
        key = sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / "refs" / f"{key}.json", self.cache_dir / "objects"

    def _cached(self, url: str, expected_sha256: str | None) -> bytes | None:
        reference_path, object_dir = self._paths(url)
        if not reference_path.is_file():
            return None
        try:
            reference = json.loads(reference_path.read_text(encoding="utf-8"))
            digest = reference["sha256"]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
            return None
        if (
            reference.get("url") != url
            or not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
        ):
            return None
        try:
            payload = (object_dir / digest).read_bytes()
        except OSError:
            return None
        actual = sha256(payload).hexdigest()
        if actual != digest or (expected_sha256 is not None and actual != expected_sha256):
            return None
        return payload

    @staticmethod
    def _publish(path: Path, payload: bytes) -> None:
        with NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)

    def fetch(self, url: str, *, expected_sha256: str | None = None) -> bytes:
        validate_sec_url(url)
        cached = self._cached(url, expected_sha256)
        if cached is not None:
            return cached

        response: _Response | None = None
        for attempt in range(self.max_retries + 1):
            now = self.monotonic()
            if self._last_request_at is not None:
                wait = self.min_interval_seconds - (now - self._last_request_at)
                if wait > 0:
                    self.sleep(wait)
            try:
                current_response = self.client.get(
                    url,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept-Encoding": "gzip, deflate",
                    },
                )
                response = current_response
                self._last_request_at = self.monotonic()
            except OSError as error:
                if attempt >= self.max_retries:
                    raise SecEdgar8kError(
                        f"SEC request failed after {attempt + 1} attempts"
                    ) from error
                self.sleep(self.backoff_seconds * (2**attempt))
                continue
            if current_response.status_code not in {429, 500, 502, 503, 504}:
                break
            if attempt >= self.max_retries:
                raise SecEdgar8kError(
                    f"SEC transient status {current_response.status_code} "
                    f"after {attempt + 1} attempts"
                )
            self.sleep(self.backoff_seconds * (2**attempt))
        if response is None:
            raise SecEdgar8kError("SEC request produced no response")
        if response.status_code != 200:
            raise SecEdgar8kError(f"SEC request returned HTTP {response.status_code}")
        payload = response.content
        digest = sha256(payload).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise SecEdgar8kError("downloaded SEC content hash mismatch")

        reference_path, object_dir = self._paths(url)
        object_dir.mkdir(parents=True, exist_ok=True)
        reference_path.parent.mkdir(parents=True, exist_ok=True)
        object_path = object_dir / digest
        try:
            existing = object_path.read_bytes()
        except OSError:
            existing = None
        if existing is None or sha256(existing).hexdigest() != digest:
            self._publish(object_path, payload)
        reference = {"sha256": digest, "url": url}
        self._publish(
            reference_path,
            (json.dumps(reference, sort_keys=True, separators=(",", ":")) + "\n").encode(),
        )
        return payload


def filing_to_manifest_record(filing: FilingRecord) -> dict[str, object]:
    """Stable JSON representation shared by acquisition and the sealed CLI."""

    record = asdict(filing)
    record["filing_date"] = filing.filing_date.isoformat()
    record["acceptance_at"] = (
        filing.acceptance_at.isoformat().replace("+00:00", "Z")
        if filing.acceptance_at is not None
        else None
    )
    record["item_codes"] = list(filing.item_codes)
    record["item_202_evidence"] = list(filing.item_202_evidence)
    record["source_occurrences"] = list(filing.source_occurrences)
    record["item_202_conflicts"] = list(filing.item_202_conflicts)
    return record


_Bucket = tuple[int, int, str]
_Identity = tuple[str, str]
_BULK_ENTRY_RE = re.compile(r"CIK(?P<cik>\d{10})(?:-submissions-\d+)?\.json")


def _path_sha256(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
    except OSError as error:
        raise SecEdgar8kError(f"cannot read SEC bulk archive: {path}") from error
    return digest.hexdigest()


def _metadata_row_sha256(record: SubmissionMetadataRecord, cik: str) -> str:
    return sha256(
        canonical_i0_json(
            {
                "accession_number": record.accession_number,
                "cik": cik,
                "form": record.form,
                "filing_date": record.filing_date.isoformat(),
                "acceptance": record.acceptance,
                "items": list(record.items),
                "primary_document": record.primary_document,
            }
        )
    ).hexdigest()


def _merge_bulk_filing(
    filings: dict[_Identity, FilingRecord],
    filing: FilingRecord,
) -> None:
    identity = (filing.accession_number, normalize_digits(filing.cik))
    previous = filings.get(identity)
    if previous is None:
        filings[identity] = filing
        return
    previous_core = replace(previous, source_url="", source_occurrences=())
    filing_core = replace(filing, source_url="", source_occurrences=())
    if previous_core != filing_core:
        raise SecEdgar8kError(
            f"conflicting bulk metadata for accession-CIK: {identity[0]}/{identity[1]}"
        )
    filings[identity] = replace(
        previous,
        source_occurrences=tuple(
            sorted(set(previous.source_occurrences) | set(filing.source_occurrences))
        ),
    )


def _scan_bulk_submissions(
    *,
    submissions_zip: Path,
    quarters: set[tuple[int, int]],
) -> tuple[
    dict[_Identity, FilingRecord],
    dict[_Bucket, set[str]],
    dict[_Bucket, set[_Identity]],
    dict[_Bucket, set[str]],
]:
    filings: dict[_Identity, FilingRecord] = {}
    accessions_by_bucket: dict[_Bucket, set[str]] = defaultdict(set)
    identities_by_bucket: dict[_Bucket, set[_Identity]] = defaultdict(set)
    item_accessions_by_bucket: dict[_Bucket, set[str]] = defaultdict(set)
    try:
        with ZipFile(submissions_zip) as archive:
            for info in archive.infolist():
                match = _BULK_ENTRY_RE.fullmatch(info.filename)
                if match is None:
                    continue
                try:
                    payload = archive.read(info)
                except (BadZipFile, OSError, RuntimeError) as error:
                    raise SecEdgar8kError(
                        f"cannot read SEC bulk archive entry: {info.filename}"
                    ) from error
                cik = normalize_digits(match.group("cik"))
                for metadata in parse_submissions_metadata(payload):
                    quarter = (metadata.filing_date.month - 1) // 3 + 1
                    if (metadata.filing_date.year, quarter) not in quarters:
                        continue
                    bucket = (metadata.filing_date.year, quarter, metadata.form)
                    identity = (metadata.accession_number, cik)
                    accessions_by_bucket[bucket].add(metadata.accession_number)
                    identities_by_bucket[bucket].add(identity)
                    if "2.02" not in metadata.items:
                        continue
                    item_accessions_by_bucket[bucket].add(metadata.accession_number)
                    acceptance_at: datetime | None = None
                    parse_error: str | None = None
                    if metadata.acceptance is not None:
                        try:
                            acceptance_at = _parse_acceptance(metadata.acceptance)
                        except SecEdgar8kError as error:
                            parse_error = str(error)
                    source_occurrence = (
                        f"submissions.zip:{info.filename}:{metadata.accession_number}"
                    )
                    filing = FilingRecord(
                        accession_number=metadata.accession_number,
                        cik=cik,
                        form=metadata.form,
                        filing_date=metadata.filing_date,
                        acceptance_raw=metadata.acceptance,
                        acceptance_at=acceptance_at,
                        source_url=(
                            f"https://data.sec.gov/submissions/{info.filename}"
                            f"#{metadata.accession_number}"
                        ),
                        content_sha256=_metadata_row_sha256(metadata, cik),
                        item_codes=metadata.items,
                        item_202_evidence=("sec_item_metadata",),
                        source_occurrences=(source_occurrence,),
                        parse_error=parse_error,
                    )
                    _merge_bulk_filing(filings, filing)
    except BadZipFile as error:
        raise SecEdgar8kError("SEC bulk submissions archive is not a valid ZIP") from error
    return (
        filings,
        accessions_by_bucket,
        identities_by_bucket,
        item_accessions_by_bucket,
    )


def _scan_full_indexes(
    *,
    fetch: Callable[..., bytes],
    quarters: set[tuple[int, int]],
) -> tuple[dict[_Bucket, set[str]], dict[_Bucket, set[_Identity]]]:
    accessions_by_bucket: dict[_Bucket, set[str]] = defaultdict(set)
    identities_by_bucket: dict[_Bucket, set[_Identity]] = defaultdict(set)
    for year, quarter in sorted(quarters):
        url = f"https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.gz"
        payload = fetch(url, expected_sha256=None)
        if not isinstance(payload, bytes):
            raise SecEdgar8kError(f"compressed full index is not bytes: {year}Q{quarter}")
        try:
            text = gzip.decompress(payload).decode("latin-1")
        except (gzip.BadGzipFile, OSError, UnicodeDecodeError) as error:
            raise SecEdgar8kError(
                f"compressed full index is malformed: {year}Q{quarter}"
            ) from error
        for record in parse_full_index(text, year=year, quarter=quarter):
            bucket = (year, quarter, record.form)
            accessions_by_bucket[bucket].add(record.accession_number)
            identities_by_bucket[bucket].add(
                (record.accession_number, normalize_digits(record.cik))
            )
    return accessions_by_bucket, identities_by_bucket


def build_i0_manifest(
    *,
    client: object,
    quarters: tuple[tuple[int, int], ...],
    submissions_zip: Path,
    submissions_sha256: str,
    listings: tuple[dict[str, object], ...],
    sessions: tuple[dict[str, object], ...],
    power_basis: dict[str, object],
    generated_at: str,
    snapshot_id: str,
    sec_user_agent: str,
) -> dict[str, object]:
    """Build a sealed manifest from SEC bulk metadata plus compressed indexes."""

    quarter_set = set(quarters)
    if not quarter_set:
        raise SecEdgar8kError("at least one SEC quarter is required")
    fetch_value = getattr(client, "fetch", None)
    if not callable(fetch_value):
        raise SecEdgar8kError("acquisition client must provide fetch()")
    fetch = cast(Callable[..., bytes], fetch_value)
    if re.fullmatch(r"[0-9a-f]{64}", submissions_sha256) is None:
        raise SecEdgar8kError("bulk submissions SHA-256 is malformed")
    actual_submissions_sha256 = _path_sha256(submissions_zip)
    if actual_submissions_sha256 != submissions_sha256:
        raise SecEdgar8kError("bulk submissions archive hash mismatch")

    (
        filings_by_identity,
        bulk_accessions,
        bulk_identities,
        item_accessions,
    ) = _scan_bulk_submissions(submissions_zip=submissions_zip, quarters=quarter_set)
    index_accessions, index_identities = _scan_full_indexes(
        fetch=fetch,
        quarters=quarter_set,
    )

    counts: dict[_Bucket, dict[str, int]] = {}
    accepted_identities: set[_Identity] = set()
    for year, quarter in sorted(quarter_set):
        for form in ("8-K", "8-K/A"):
            bucket = (year, quarter, form)
            expected_accessions = index_accessions[bucket]
            observed_accessions = bulk_accessions[bucket]
            expected_identities = index_identities[bucket]
            observed_identities = bulk_identities[bucket]
            matching_accessions = expected_accessions & observed_accessions
            missing_identities = expected_identities - observed_identities
            extra_identities = observed_identities - expected_identities
            counts[bucket] = {
                "expected": len(expected_accessions),
                "fetched": len(matching_accessions),
                "parsed": len(matching_accessions),
                "item_202": len(item_accessions[bucket] & expected_accessions),
                "failed": len(expected_accessions - observed_accessions) + len(missing_identities),
                "excluded": len(observed_accessions - expected_accessions) + len(extra_identities),
            }
            accepted_identities.update(expected_identities & observed_identities)

    power_payload = power_basis.get("payload")
    if not isinstance(power_payload, dict):
        raise SecEdgar8kError("power basis payload must be an object")
    try:
        power_digest = digest_i0_json(power_payload)
    except I0SealingError as error:
        raise SecEdgar8kError("power basis payload cannot be sealed") from error
    if power_basis.get("sha256") != power_digest:
        raise SecEdgar8kError("pre-existing power basis hash is missing or stale")

    filings = [
        filing
        for identity, filing in filings_by_identity.items()
        if identity in accepted_identities
    ]
    manifest: dict[str, object] = {
        "schema_version": "sec8k-i0-manifest-v1",
        "generated_at": generated_at,
        "provenance": {
            "source": "SEC EDGAR bulk submissions metadata and compressed full indexes",
            "snapshot_id": (f"{snapshot_id};submissions_sha256={actual_submissions_sha256}"),
            "acquired_at": generated_at,
            "sec_user_agent": sec_user_agent,
        },
        "filings": [
            filing_to_manifest_record(filing)
            for filing in sorted(
                filings,
                key=lambda row: (row.accession_number, normalize_digits(row.cik)),
            )
        ],
        "listings": sorted(
            (dict(row) for row in listings),
            key=lambda row: (str(row.get("symbol", "")), str(row.get("cik", ""))),
        ),
        "sessions": sorted(
            (dict(row) for row in sessions), key=lambda row: str(row.get("market_open", ""))
        ),
        "reconciliation": [
            {"year": year, "quarter": quarter, "form": form, **values}
            for (year, quarter, form), values in sorted(counts.items())
        ],
        "power_basis": {"payload": power_payload, "sha256": power_digest},
    }
    try:
        return seal_i0_manifest(manifest)
    except I0SealingError as error:
        raise SecEdgar8kError("acquired bulk I0 manifest cannot be sealed") from error


def normalize_digits(value: str) -> str:
    normalized = "".join(character for character in value if character.isdigit()).lstrip("0")
    return normalized or "0"
