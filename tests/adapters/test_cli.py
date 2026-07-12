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


def test_cli_emits_accepted_event_for_momentum_candidate(capsys) -> None:
    result = main(["--universe", "fixtures/v1/universe.json", "--bars", "fixtures/v1/bars.json", "--format", "json"])
    captured = capsys.readouterr()
    assert result == 0
    payload = json.loads(captured.out)
    events_by_symbol = {event["symbol"]: event for event in payload}
    accepted = events_by_symbol["MOMO"]
    assert accepted["event_type"] == "candidate.accepted.v1"
    assert accepted["decision"] == "accepted"
    assert "reason" not in accepted
    assert events_by_symbol["ACME"]["event_type"] == "candidate.rejected.v1"


def test_cli_rejects_real_fixture_with_unknown_symbol_before_scanning(tmp_path: Path, capsys) -> None:
    universe = tmp_path / "universe.json"
    universe.write_text('{"fixture_version": "v1", "symbols": ["ACME"]}', encoding="utf-8")
    bars = tmp_path / "bars.json"
    bars.write_text(
        json.dumps(
            {
                "fixture_version": "v1",
                "bars": [
                    {"symbol": "ACME", "date": "2026-07-10", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 1000},
                    {"symbol": "GHOST", "date": "2026-07-10", "open": 10, "high": 12, "low": 9, "close": 11, "volume": 1000},
                ],
            }
        ),
        encoding="utf-8",
    )
    result = main(["--universe", str(universe), "--bars", str(bars), "--format", "json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result != 0
    assert payload["event_type"] == "scan.failed.v1"
    assert payload["reason"] == "fixture-symbol-missing"
    assert captured.out.count("scan.failed.v1") == 1
    assert captured.err == ""


def test_cli_maps_unsupported_input_to_single_failed_record(monkeypatch, capsys) -> None:
    from invest.adapters import cli
    from invest.adapters.fixtures_json import JsonFixtureReader

    original_load = JsonFixtureReader.load

    def load_with_alien_symbol(self, universe_path, bars_path):
        inputs = original_load(self, universe_path, bars_path)
        alien = tuple(
            bar.__class__(**{**bar.__dict__, "symbol": "ALIEN"}) for bar in inputs.bars[:1]
        )
        return inputs.__class__(universe=inputs.universe, bars=(*inputs.bars, *alien))

    monkeypatch.setattr(cli.JsonFixtureReader, "load", load_with_alien_symbol)
    result = cli.main(
        ["--universe", "fixtures/v1/universe.json", "--bars", "fixtures/v1/bars.json", "--format", "json"]
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result != 0
    assert payload["event_type"] == "scan.failed.v1"
    assert payload["reason"] == "unsupported-input"
    assert captured.out.count("scan.failed.v1") == 1
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
