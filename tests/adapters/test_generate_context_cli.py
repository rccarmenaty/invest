"""CLI tests for invest-generate-context."""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from invest.domain.models import DailyBar


def _bar(symbol: str, day: date) -> DailyBar:
    close = Decimal("10")
    return DailyBar(symbol, day, close, close + Decimal("0.5"), close - Decimal("0.5"), close, 1_000_000)


def _eligible_inputs():
    from invest.application.generate_market_context import GeneratorInputs, NormalizedListing

    start = date(2024, 1, 2)
    sessions = (start, start + timedelta(days=1), start + timedelta(days=2))
    listing_start = start - timedelta(days=2)
    return GeneratorInputs(
        sessions=sessions,
        listings=(
            NormalizedListing("ACME", listing_start, start + timedelta(days=365), True),
        ),
        bars=tuple(_bar("ACME", listing_start + timedelta(days=i)) for i in range(5)),
        actions=(),
    )


def _install_fake_source(monkeypatch, inputs=None, error: Exception | None = None):
    from invest.adapters import generate_context_cli as cli

    payload = inputs if inputs is not None else _eligible_inputs()

    class _FakeSource:
        def __init__(self, **_kwargs) -> None:
            pass

        def load(self, start, end, config):
            if error is not None:
                raise error
            return payload

    monkeypatch.setattr(cli, "SharadarContextSource", _FakeSource)
    return cli


def _args(out: Path, *extra: str) -> list[str]:
    return [
        "--start", "2024-01-02", "--end", "2024-01-04", "--out", str(out),
        "--price-floor", "1", "--dollar-volume-floor", "1",
        "--dollar-volume-window", "2", "--min-observed-bars", "3", *extra,
    ]


def _assert_fail(result: int, out: Path, capsys, reason: str) -> None:
    captured = capsys.readouterr()
    assert result == 2
    assert captured.err == ""
    assert captured.out.count("\n") == 1
    assert json.loads(captured.out) == {"reason": reason}
    assert not out.exists() if reason != "output-exists" else out.exists()


def test_success_writes_context_silent_exit_zero(tmp_path, capsys, monkeypatch) -> None:
    cli = _install_fake_source(monkeypatch)
    out = tmp_path / "context.json"
    result = cli.main(_args(out))
    captured = capsys.readouterr()
    assert result == 0
    assert captured.out == ""
    assert captured.err == ""
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "market-context-v2"
    assert payload["generation_span"] == {"start": "2024-01-02", "end": "2024-01-04"}
    assert payload["symbols"][0]["symbol"] == "ACME"


def test_bars_out_writes_deterministic_pair_with_pre_span_warmup(
    tmp_path, capsys, monkeypatch
) -> None:
    from invest.adapters.fixtures_json import JsonFixtureReader

    cli = _install_fake_source(monkeypatch)
    first_context = tmp_path / "first-context.json"
    second_context = tmp_path / "second-context.json"
    first_bars = tmp_path / "first-bars"
    second_bars = tmp_path / "second-bars"

    first_result = cli.main(_args(first_context, "--bars-out", str(first_bars)))
    second_result = cli.main(_args(second_context, "--bars-out", str(second_bars)))

    captured = capsys.readouterr()
    assert first_result == second_result == 0
    assert captured.out == ""
    assert first_context.read_bytes() == second_context.read_bytes()
    assert (first_bars / "universe.json").read_bytes() == (
        second_bars / "universe.json"
    ).read_bytes()
    assert (first_bars / "bars.json").read_bytes() == (second_bars / "bars.json").read_bytes()
    inputs = JsonFixtureReader().load(first_bars / "universe.json", first_bars / "bars.json")
    context_payload = json.loads(first_context.read_text(encoding="utf-8"))
    assert min(bar.date for bar in inputs.bars) == date(2023, 12, 31)
    assert context_payload["generation_span"]["start"] == "2024-01-02"


def test_bars_write_failure_leaves_no_orphan_context(tmp_path, capsys, monkeypatch) -> None:
    """A failed --bars-out write must not leave an unpaired context file behind."""
    cli = _install_fake_source(monkeypatch)
    out = tmp_path / "context.json"
    bars_out = tmp_path / "bars"
    bars_out.mkdir()  # pre-existing bars path → BarsFixtureExistsError

    result = cli.main(_args(out, "--bars-out", str(bars_out)))

    captured = capsys.readouterr()
    assert result == 2
    assert captured.err == ""
    assert json.loads(captured.out) == {"reason": "bars-out-exists"}
    assert not out.exists()

    # Retry with the same context path and a fresh bars path must succeed.
    retry_bars = tmp_path / "bars-retry"
    assert cli.main(_args(out, "--bars-out", str(retry_bars))) == 0
    assert out.is_file()
    assert (retry_bars / "bars.json").is_file()


def test_bars_storage_failure_leaves_no_orphan_context(tmp_path, capsys, monkeypatch) -> None:
    """Storage-level bars failures must also keep the pair invariant."""
    from invest.adapters import generate_context_cli as cli_module
    from invest.adapters.bars_fixture_json import BarsFixtureStorageError

    cli = _install_fake_source(monkeypatch)
    out = tmp_path / "context.json"
    bars_out = tmp_path / "bars"

    class _FailingWriter:
        def write(self, inputs, path):
            raise BarsFixtureStorageError("disk full")

    monkeypatch.setattr(cli_module, "BarsFixtureWriter", _FailingWriter)

    result = cli.main(_args(out, "--bars-out", str(bars_out)))

    captured = capsys.readouterr()
    assert result == 2
    assert json.loads(captured.out) == {"reason": "storage-failure"}
    assert not out.exists()
    assert not bars_out.exists()


@pytest.mark.parametrize(
    ("argv_extra", "reason"),
    [
        (["--start", "2024-01-04", "--end", "2024-01-02"], "invalid-arguments"),
        (["--price-floor", "0"], "invalid-arguments"),
        (["--dollar-volume-floor", "NaN"], "invalid-arguments"),
        (["--dollar-volume-window", "20", "--min-observed-bars", "10"], "invalid-arguments"),
    ],
)
def test_invalid_screen_and_date_args(tmp_path, capsys, monkeypatch, argv_extra, reason) -> None:
    cli = _install_fake_source(monkeypatch)
    out = tmp_path / "context.json"
    # For date-order case replace start/end entirely.
    if "--start" in argv_extra:
        argv = [*argv_extra, "--out", str(out),
                "--price-floor", "1", "--dollar-volume-floor", "1",
                "--dollar-volume-window", "2", "--min-observed-bars", "3"]
    else:
        argv = _args(out, *argv_extra)
    _assert_fail(cli.main(argv), out, capsys, reason)


def test_existing_output_refused(tmp_path, capsys, monkeypatch) -> None:
    cli = _install_fake_source(monkeypatch)
    out = tmp_path / "context.json"
    out.write_text('{"preexisting":true}\n', encoding="utf-8")
    before = out.read_text(encoding="utf-8")
    result = cli.main(_args(out))
    captured = capsys.readouterr()
    assert result == 2
    assert captured.err == ""
    assert json.loads(captured.out) == {"reason": "output-exists"}
    assert out.read_text(encoding="utf-8") == before


def test_missing_parent_is_invalid_arguments(tmp_path, capsys, monkeypatch) -> None:
    cli = _install_fake_source(monkeypatch)
    out = tmp_path / "missing" / "context.json"
    _assert_fail(cli.main(_args(out)), out, capsys, "invalid-arguments")


def test_reference_data_incomplete_one_line(tmp_path, capsys, monkeypatch) -> None:
    from invest.application.generate_market_context import ReferenceDataIncompleteError

    cli = _install_fake_source(monkeypatch, error=ReferenceDataIncompleteError("orphan"))
    out = tmp_path / "context.json"
    _assert_fail(cli.main(_args(out)), out, capsys, "reference-data-incomplete")


def test_reader_error_reason_stable(tmp_path, capsys, monkeypatch) -> None:
    from invest.adapters.alpaca_market_data import MarketDataFetchError

    cli = _install_fake_source(
        monkeypatch, error=MarketDataFetchError("malformed-response", "blank cursor")
    )
    out = tmp_path / "context.json"
    result = cli.main(_args(out))
    captured = capsys.readouterr()
    assert result == 2
    assert captured.err == ""
    assert list(json.loads(captured.out).keys()) == ["reason"]
    assert json.loads(captured.out) == {"reason": "malformed-response"}
    assert not out.exists()


def test_no_replay_broker_scanner_imports_or_calls(tmp_path, monkeypatch) -> None:
    import ast
    from invest.adapters import generate_context_cli as cli

    tree = ast.parse(Path(cli.__file__).read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    for banned in (
        "BacktestRun", "AlpacaBroker", "ExecuteRun", "ScanRun",
        "backtest_main", "execute_main", "main",
    ):
        # `main` is this CLI's own entry; skip self-reference check via modules.
        if banned == "main":
            continue
        assert banned not in names
    assert "invest.application.backtest_run" not in modules
    assert "invest.adapters.alpaca_broker" not in modules
    assert "invest.application.execute_run" not in modules
    assert "invest.application.scan_run" not in modules

    _install_fake_source(monkeypatch)
    out = tmp_path / "context.json"
    assert cli.main(_args(out)) == 0
    assert out.is_file()


def test_core_defaults_and_no_banned_flags() -> None:
    from invest.adapters.generate_context_cli import _parser
    from invest.domain.liquidity_screen import ScreenConfig

    core = ScreenConfig.core_defaults()
    defaults = _parser().parse_args(
        ["--start", "2024-01-02", "--end", "2024-01-04", "--out", "x.json"]
    )
    assert defaults.price_floor == core.price_floor
    assert defaults.dollar_volume_floor == core.dollar_volume_floor
    assert defaults.dollar_volume_window == core.dollar_volume_window
    assert defaults.min_observed_bars == core.min_observed_bars
    dests = {a.dest for a in _parser()._actions}
    for banned in (
        "source", "replay", "universe", "overwrite", "aum", "adv_fraction",
        "impact", "bars", "market_context", "strategy", "execute",
    ):
        assert banned not in dests
    assert "bars_out" in dests
