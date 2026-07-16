import json
import os
from datetime import date
from pathlib import Path

import pytest

from invest.adapters.backtest_context_json import BacktestContextJsonReader
from invest.domain.market_context import (
    BlockerWindow,
    ContextReason,
    CoverageWindow,
    EligibilityWindow,
    MarketContext,
    MarketContextIncompleteError,
    MarketContextInvalidError,
    SymbolContext,
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


def test_rejects_integer_eligibility_as_market_context_invalid(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["symbols"][0]["eligibility"][0]["eligible"] = 1

    with pytest.raises(MarketContextInvalidError) as error:
        BacktestContextJsonReader().load(_write_context(tmp_path / "market-context.json", payload))

    assert error.value.reason == "market-context-invalid"


def test_rejects_numeric_date_as_market_context_invalid(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["symbols"][0]["coverage"][0]["start"] = 1_704_067_200

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


def _sample_context() -> MarketContext:
    return MarketContext(
        {
            "BETA": SymbolContext(
                coverage=(CoverageWindow(date(2024, 1, 1), date(2024, 1, 3)),),
                eligibility=(
                    EligibilityWindow(date(2024, 1, 1), date(2024, 1, 3), eligible=True),
                ),
                blockers=(),
            ),
            "ACME": SymbolContext(
                coverage=(CoverageWindow(date(2024, 1, 1), date(2024, 1, 3)),),
                eligibility=(
                    EligibilityWindow(date(2024, 1, 1), date(2024, 1, 1), eligible=True),
                    EligibilityWindow(date(2024, 1, 2), date(2024, 1, 2), eligible=False),
                    EligibilityWindow(date(2024, 1, 3), date(2024, 1, 3), eligible=True),
                ),
                blockers=(
                    BlockerWindow(
                        date(2024, 1, 1),
                        date(2024, 1, 1),
                        reason=ContextReason.CORPORATE_ACTION,
                    ),
                ),
            ),
        }
    )


def test_writer_emits_canonical_compact_json_with_trailing_newline(tmp_path: Path) -> None:
    from invest.adapters.backtest_context_json import BacktestContextJsonWriter

    out = tmp_path / "market-context.json"
    written = BacktestContextJsonWriter().write(_sample_context(), out)

    assert written == out
    raw = out.read_bytes()
    assert raw.endswith(b"\n")
    assert b" " not in raw.rstrip(b"\n")  # compact separators
    # Deterministic symbol order (ACME before BETA).
    text = raw.decode("utf-8")
    assert text.index('"symbol":"ACME"') < text.index('"symbol":"BETA"')
    payload = json.loads(text)
    assert payload["schema_version"] == "market-context-v1"
    assert [item["symbol"] for item in payload["symbols"]] == ["ACME", "BETA"]


def test_writer_round_trips_through_reader(tmp_path: Path) -> None:
    from invest.adapters.backtest_context_json import BacktestContextJsonWriter

    out = tmp_path / "market-context.json"
    original = _sample_context()
    BacktestContextJsonWriter().write(original, out)
    loaded = BacktestContextJsonReader().load(out)

    assert loaded.status("ACME", date(2024, 1, 1)).reason is ContextReason.CORPORATE_ACTION
    assert loaded.status("ACME", date(2024, 1, 2)).eligible is False
    assert loaded.status("BETA", date(2024, 1, 3)).eligible is True
    assert set(loaded.by_symbol) == set(original.by_symbol)


def test_writer_refuses_existing_target(tmp_path: Path) -> None:
    from invest.adapters.backtest_context_json import (
        BacktestContextJsonWriter,
        ContextOutputExistsError,
    )

    out = tmp_path / "market-context.json"
    out.write_text("existing", encoding="utf-8")

    with pytest.raises(ContextOutputExistsError) as error:
        BacktestContextJsonWriter().write(_sample_context(), out)

    assert error.value.reason == "output-exists"
    assert out.read_text(encoding="utf-8") == "existing"


def test_writer_cleans_temp_file_after_success(tmp_path: Path) -> None:
    from invest.adapters.backtest_context_json import BacktestContextJsonWriter

    out = tmp_path / "market-context.json"
    BacktestContextJsonWriter().write(_sample_context(), out)

    leftovers = [path for path in tmp_path.iterdir() if path != out]
    assert leftovers == []
    assert out.is_file()


def test_writer_cleans_temp_and_writes_nothing_on_invalid_empty_context(tmp_path: Path) -> None:
    from invest.adapters.backtest_context_json import BacktestContextJsonWriter

    out = tmp_path / "market-context.json"
    with pytest.raises(MarketContextInvalidError) as error:
        BacktestContextJsonWriter().write(MarketContext({}), out)

    assert error.value.reason == "market-context-invalid"
    assert list(tmp_path.iterdir()) == []


def test_writer_is_atomic_no_replace_under_race(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If the target appears after the existence check, publication must not replace it."""
    from invest.adapters import backtest_context_json as module
    from invest.adapters.backtest_context_json import (
        BacktestContextJsonWriter,
        ContextOutputExistsError,
    )

    out = tmp_path / "market-context.json"
    original_link = os.link

    def sneaky_link(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        Path(dst).write_text("racer", encoding="utf-8")
        return original_link(src, dst)

    monkeypatch.setattr(module.os, "link", sneaky_link)

    with pytest.raises((ContextOutputExistsError, FileExistsError, OSError)):
        BacktestContextJsonWriter().write(_sample_context(), out)

    # Existing racer content must not be replaced with generated JSON.
    if out.exists():
        assert out.read_text(encoding="utf-8") == "racer"
    # No temp leftovers.
    assert all(path == out or not path.name.startswith(".") for path in tmp_path.iterdir()) or True
    temps = [path for path in tmp_path.iterdir() if path.suffix == ".tmp" or ".tmp." in path.name]
    assert temps == []


def test_writer_is_deterministic_for_identical_context(tmp_path: Path) -> None:
    from invest.adapters.backtest_context_json import BacktestContextJsonWriter

    first = tmp_path / "a.json"
    second = tmp_path / "b.json"
    context = _sample_context()
    BacktestContextJsonWriter().write(context, first)
    BacktestContextJsonWriter().write(context, second)
    assert first.read_bytes() == second.read_bytes()
