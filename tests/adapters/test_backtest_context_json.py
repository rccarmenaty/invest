import json
from datetime import date
from pathlib import Path

import pytest

from invest.adapters.backtest_context_json import BacktestContextJsonReader
from invest.domain.market_context import (
    ContextReason,
    MarketContextIncompleteError,
    MarketContextInvalidError,
)


def _write_context(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _valid_payload() -> dict[str, object]:
    return {
        "schema_version": "market-context-v1",
        "symbols": [
            {
                "symbol": "ACME",
                "coverage": [{"start": "2024-01-01", "end": "2024-01-03"}],
                "eligibility": [{"start": "2024-01-01", "end": "2024-01-03", "eligible": True}],
                "blockers": [{"start": "2024-01-02", "end": "2024-01-02", "reason": "corporate-action"}],
            }
        ],
    }


def test_loads_strict_v1_market_context() -> None:
    context = BacktestContextJsonReader().load(Path("fixtures/backtest/market-context.json"))

    assert context.status("WIN", date(2024, 1, 23)).eligible is True
    assert context.status("WIN", date(2024, 1, 23)).reason is None


def test_rejects_unreadable_bytes_as_market_context_invalid(tmp_path: Path) -> None:
    context_path = tmp_path / "market-context.json"
    context_path.write_bytes(b"\xff")

    with pytest.raises(MarketContextInvalidError) as error:
        BacktestContextJsonReader().load(context_path)

    assert error.value.reason == "market-context-invalid"


def test_rejects_malformed_json_as_market_context_invalid(tmp_path: Path) -> None:
    context_path = tmp_path / "market-context.json"
    context_path.write_text("not-json", encoding="utf-8")

    with pytest.raises(MarketContextInvalidError) as error:
        BacktestContextJsonReader().load(context_path)

    assert error.value.reason == "market-context-invalid"


def test_rejects_unsupported_schema_version(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["schema_version"] = "market-context-v2"

    with pytest.raises(MarketContextInvalidError) as error:
        BacktestContextJsonReader().load(_write_context(tmp_path / "market-context.json", payload))

    assert error.value.reason == "market-context-invalid"


def test_rejects_overlapping_semantic_intervals(tmp_path: Path) -> None:
    payload = _valid_payload()
    symbol_payload = payload["symbols"][0]
    symbol_payload["blockers"] = [
        {"start": "2024-01-02", "end": "2024-01-02", "reason": "corporate-action"},
        {"start": "2024-01-02", "end": "2024-01-03", "reason": "earnings-context-missing"},
    ]

    with pytest.raises(MarketContextInvalidError) as error:
        BacktestContextJsonReader().load(_write_context(tmp_path / "market-context.json", payload))

    assert error.value.reason == "market-context-invalid"


def test_semantically_incomplete_context_surfaces_market_context_incomplete(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["symbols"][0]["eligibility"] = [
        {"start": "2024-01-01", "end": "2024-01-02", "eligible": True}
    ]

    context = BacktestContextJsonReader().load(_write_context(tmp_path / "market-context.json", payload))

    with pytest.raises(MarketContextIncompleteError) as error:
        context.require_complete((date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)), ("ACME",))

    assert error.value.reason == "market-context-incomplete"
    assert context.status("ACME", date(2024, 1, 2)).reason is ContextReason.CORPORATE_ACTION
