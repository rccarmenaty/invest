"""SEC-owned fixture tests for the EDGAR 8-K source boundary."""

from __future__ import annotations

import gzip
import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

import pytest

from invest.adapters.sec_edgar_8k import (
    SecEdgar8kError,
    SecFairAccessClient,
    build_i0_manifest,
    parse_full_index,
    parse_submission,
    parse_submissions_metadata,
)


def _read_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        pytest.fail(f"fixture JSON must be readable: {error}")


def test_parses_original_and_amended_index_rows_and_sec_item_timestamp_evidence() -> None:
    index = """Description: Master Index of EDGAR Dissemination Feed
CIK|Company Name|Form Type|Date Filed|Filename
1|ACME CORP|8-K|2024-03-08|edgar/data/1/0000000001-24-000001.txt
1|ACME CORP|8-K/A|2024-03-11|edgar/data/1/0000000001-24-000002.txt
2|OTHER CORP|10-K|2024-03-11|edgar/data/2/0000000002-24-000001.txt
"""
    rows = parse_full_index(index, year=2024, quarter=1)

    assert [row.form for row in rows] == ["8-K", "8-K/A"]
    assert [row.accession_number for row in rows] == [
        "0000000001-24-000001",
        "0000000001-24-000002",
    ]

    submission = b"""<SEC-HEADER>
ACCESSION NUMBER:        0000000001-24-000001
CONFORMED SUBMISSION TYPE: 8-K
FILED AS OF DATE:        20240308
ACCEPTANCE-DATETIME:     20240308173000
ITEM INFORMATION:        Results of Operations and Financial Condition
</SEC-HEADER>
<DOCUMENT>
<TYPE>8-K
<TEXT>
Item 2.02 Results of Operations and Financial Condition
</TEXT>
</DOCUMENT>
"""
    filing = parse_submission(
        submission,
        source_url=("https://www.sec.gov/Archives/edgar/data/1/0000000001-24-000001.txt"),
        source_occurrence="2024Q1/master.idx",
    )

    assert filing.accession_number == "0000000001-24-000001"
    assert filing.acceptance_raw == "20240308173000"
    assert filing.acceptance_at == datetime(2024, 3, 8, 22, 30, tzinfo=timezone.utc)
    expected_item_codes = ("2.02",)
    expected_evidence = ("sec_item_metadata", "filing_body")
    assert filing.item_codes == expected_item_codes
    assert filing.item_202_evidence == expected_evidence
    assert filing.content_sha256 == sha256(submission).hexdigest()


def test_submission_parser_rejects_noncanonical_cik_text() -> None:
    submission = b"""<SEC-HEADER>
ACCESSION NUMBER: 0000000001-24-000001
CONFORMED SUBMISSION TYPE: 8-K
CENTRAL INDEX KEY: issuer CIK 1
FILED AS OF DATE: 20240308
ACCEPTANCE-DATETIME: 20240308173000
ITEM INFORMATION: Item 2.02
</SEC-HEADER>
<DOCUMENT><TYPE>8-K<TEXT>Item 2.02</TEXT></DOCUMENT>
"""

    with pytest.raises(SecEdgar8kError, match="CIK"):
        parse_submission(
            submission,
            source_url="https://www.sec.gov/Archives/edgar/data/1/0000000001-24-000001.txt",
            source_occurrence="2024Q1/master.idx",
        )


def test_full_index_preserves_joint_filer_ciks_for_one_accession() -> None:
    index = """CIK|Company Name|Form Type|Date Filed|Filename
1|ACME CORP|8-K|2024-03-08|edgar/data/1/0000000001-24-000001.txt
2|ACME HOLDINGS|8-K|2024-03-08|edgar/data/1/0000000001-24-000001.txt
"""

    rows = parse_full_index(index, year=2024, quarter=1)

    expected_rows = [
        ("0000000001-24-000001", "1"),
        ("0000000001-24-000001", "2"),
    ]
    actual_rows = [(row.accession_number, row.cik) for row in rows]
    assert actual_rows == expected_rows


def test_bulk_builder_reconciles_full_population_and_keeps_only_item_202_filer_records(
    tmp_path: Path,
) -> None:
    joint_accession = "0000000001-24-000001"
    non_item_accession = "0000000001-24-000002"
    index_url = "https://www.sec.gov/Archives/edgar/full-index/2024/QTR1/master.gz"
    index = gzip.compress(
        f"""CIK|Company Name|Form Type|Date Filed|Filename
1|ACME CORP|8-K|2024-03-08|edgar/data/1/{joint_accession}.txt
2|ACME HOLDINGS|8-K|2024-03-08|edgar/data/1/{joint_accession}.txt
1|ACME CORP|8-K|2024-03-09|edgar/data/1/{non_item_accession}.txt
""".encode()
    )
    archive_path = tmp_path / "submissions.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "CIK0000000001.json",
            json.dumps(
                {
                    "filings": {
                        "recent": {
                            "accessionNumber": [joint_accession, non_item_accession],
                            "filingDate": ["2024-03-08", "2024-03-09"],
                            "acceptanceDateTime": [
                                "2024-03-08T22:30:00.000Z",
                                "2024-03-09T12:00:00.000Z",
                            ],
                            "form": ["8-K", "8-K"],
                            "items": ["2.02,9.01", "8.01"],
                            "primaryDocument": ["joint.htm", "other.htm"],
                        }
                    }
                }
            ),
        )
        archive.writestr(
            "CIK0000000002.json",
            json.dumps(
                {
                    "filings": {
                        "recent": {
                            "accessionNumber": [joint_accession],
                            "filingDate": ["2024-03-08"],
                            "acceptanceDateTime": ["2024-03-08T22:30:00.000Z"],
                            "form": ["8-K"],
                            "items": ["2.02,9.01"],
                            "primaryDocument": ["joint.htm"],
                        }
                    }
                }
            ),
        )

    class FixtureClient:
        def __init__(self) -> None:
            self.urls: list[str] = []

        def fetch(self, url: str, *, expected_sha256: str | None = None) -> bytes:
            assert expected_sha256 is None
            self.urls.append(url)
            assert url == index_url
            return index

    power_payload = {
        "basis_id": "preexisting",
        "created_at": "2023-01-01T00:00:00Z",
        "effective_sigma": 0.1,
        "provenance": "predates SEC-8K outcomes",
    }
    client = FixtureClient()
    manifest = build_i0_manifest(
        client=client,
        quarters=((2024, 1),),
        submissions_zip=archive_path,
        submissions_sha256=sha256(archive_path.read_bytes()).hexdigest(),
        listings=(
            {
                "symbol": "ACME",
                "cik": "1",
                "related_symbols": [],
                "first_date": "2020-01-01",
                "last_date": None,
                "us_primary_common": True,
            },
            {
                "symbol": "OTHER",
                "cik": "2",
                "related_symbols": [],
                "first_date": "2020-01-01",
                "last_date": None,
                "us_primary_common": True,
            },
        ),
        sessions=({"session_date": "2024-03-11", "market_open": "2024-03-11T13:30:00Z"},),
        power_basis={
            "payload": power_payload,
            "sha256": sha256(
                json.dumps(power_payload, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        },
        generated_at="2024-04-01T00:00:00Z",
        snapshot_id="bulk-fixture",
        sec_user_agent="invest-research contact@example.com",
    )

    assert client.urls == [index_url]
    manifest_filings = manifest["filings"]
    assert isinstance(manifest_filings, list)
    assert all(isinstance(row, dict) for row in manifest_filings)
    expected_filings = [
        (joint_accession, "1"),
        (joint_accession, "2"),
    ]
    actual_filings = [(row["accession_number"], row["cik"]) for row in manifest_filings]
    assert actual_filings == expected_filings
    assert all(row["item_202_evidence"] == ["sec_item_metadata"] for row in manifest_filings)
    reconciliation_rows = manifest["reconciliation"]
    assert isinstance(reconciliation_rows, list)
    assert all(isinstance(row, dict) for row in reconciliation_rows)
    reconciliation = next(row for row in reconciliation_rows if row["form"] == "8-K")
    assert reconciliation == {
        "year": 2024,
        "quarter": 1,
        "form": "8-K",
        "expected": 2,
        "fetched": 2,
        "parsed": 2,
        "item_202": 1,
        "failed": 0,
        "excluded": 0,
    }


def test_submissions_metadata_converts_malformed_filing_dates_to_sec_errors() -> None:
    malformed = b"""{
      "filings": {"recent": {
        "accessionNumber": ["0000000001-24-000001"],
        "form": ["8-K"],
        "filingDate": ["not-a-date"],
        "primaryDocument": ["acme.htm"]
      }}
    }"""

    with pytest.raises(SecEdgar8kError, match="filing date"):
        parse_submissions_metadata(malformed)


def test_fair_access_cache_resumes_without_network_and_fails_closed_when_corrupt(
    tmp_path: Path,
) -> None:
    url = "https://www.sec.gov/Archives/edgar/data/1/filing.txt"

    class Response:
        status_code = 200
        content = b"immutable SEC bytes"

    class Network:
        def __init__(self) -> None:
            self.calls = 0
            self.headers: dict[str, str] = {}

        def get(self, url: str, *, headers: dict[str, str]) -> Response:
            assert url == "https://www.sec.gov/Archives/edgar/data/1/filing.txt"
            self.calls += 1
            self.headers = headers
            return Response()

        def close(self) -> None:
            pass

    network = Network()
    first = SecFairAccessClient(
        cache_dir=tmp_path,
        user_agent="invest-research contact@example.com",
        client=network,
        min_interval_seconds=0,
    )
    assert first.fetch(url) == b"immutable SEC bytes"
    assert network.calls == 1
    assert network.headers.get("User-Agent") == "invest-research contact@example.com"

    class NoNetwork(Network):
        def get(self, url: str, *, headers: dict[str, str]) -> Response:
            raise AssertionError(
                f"verified cache should avoid a network request to {url} with {headers}"
            )

    resumed = SecFairAccessClient(
        cache_dir=tmp_path,
        user_agent="invest-research contact@example.com",
        client=NoNetwork(),
        min_interval_seconds=0,
    )
    assert resumed.fetch(url) == b"immutable SEC bytes"

    reference_path = next((tmp_path / "refs").iterdir())
    reference = _read_json(reference_path)
    assert isinstance(reference, dict)
    cached_digest = reference.get("sha256")
    assert isinstance(cached_digest, str)
    reference_path.write_text(json.dumps({"url": url, "sha256": "../outside"}))
    reference_recovery_network = Network()
    reference_recovery = SecFairAccessClient(
        cache_dir=tmp_path,
        user_agent="invest-research contact@example.com",
        client=reference_recovery_network,
        min_interval_seconds=0,
    )
    assert reference_recovery.fetch(url) == b"immutable SEC bytes"
    assert reference_recovery_network.calls == 1

    (tmp_path / "objects" / cached_digest).write_bytes(b"corrupt")
    object_recovery_network = Network()
    object_recovery = SecFairAccessClient(
        cache_dir=tmp_path,
        user_agent="invest-research contact@example.com",
        client=object_recovery_network,
        min_interval_seconds=0,
    )
    assert object_recovery.fetch(url) == b"immutable SEC bytes"
    assert object_recovery_network.calls == 1

    with pytest.raises(SecEdgar8kError, match="outside the allowlist"):
        resumed.fetch("https://example.com/Archives/filing.txt")
