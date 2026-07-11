import json
from pathlib import Path

from invest.adapters.cli import main


def test_cli_success_prints_only_event_list(capsys) -> None:
    result = main(["--universe", "fixtures/v1/universe.json", "--bars", "fixtures/v1/bars.json", "--format", "json"])
    captured = capsys.readouterr()
    assert result == 0
    payload = json.loads(captured.out)
    assert isinstance(payload, list)
    assert payload[0]["event_type"] == "candidate.rejected.v1"
    assert captured.err == ""


def test_cli_failure_prints_one_failed_record_without_partial_output(tmp_path: Path, capsys) -> None:
    malformed = tmp_path / "bars.json"
    malformed.write_text("not-json", encoding="utf-8")
    result = main(["--universe", "fixtures/v1/universe.json", "--bars", str(malformed), "--format", "json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result != 0
    assert payload["event_type"] == "scan.failed.v1"
    assert payload["reason"] == "fixture-invalid"
    assert captured.out.count("scan.failed.v1") == 1
    assert captured.err == ""
