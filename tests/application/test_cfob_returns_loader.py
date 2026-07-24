"""SEP loader plumbing for the CFOB E1/E2 returns gates (ticket #89).

``_load_sep_year`` lives in the research driver, not the package, so it is loaded
by path. It must carry the adjusted opening price (open-to-open returns, ADR 0003
§1) and fail closed when the column is absent.
"""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

_DRIVER_PATH = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "real-continuous"
    / "reports"
    / "research_cfob.py"
)


def _load_driver():
    spec = importlib.util.spec_from_file_location("research_cfob_under_test", _DRIVER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_parquet(path: Path, columns: dict[str, list]) -> None:
    pq.write_table(pa.table(columns), path)


def test_loader_carries_open_close_volume_in_canonical_order(tmp_path, monkeypatch) -> None:
    driver = _load_driver()
    _write_parquet(
        tmp_path / "sep_2020.parquet",
        {
            "symbol": ["ACME", "ACME", "OTHER"],
            "date": [date(2020, 1, 2), date(2020, 1, 3), date(2020, 1, 2)],
            "open_adj": [10.0, 11.0, 99.0],
            "close_adj": [10.5, 11.5, 99.5],
            "volume": [1000.0, 1100.0, 2000.0],
        },
    )
    monkeypatch.setattr(driver, "SEP_DIR", tmp_path)

    out = driver._load_sep_year(2020, {"ACME"})

    assert set(out) == {"ACME"}  # only requested cluster symbols kept
    assert out["ACME"] == [
        (date(2020, 1, 2), 10.0, 10.5, 1000.0),
        (date(2020, 1, 3), 11.0, 11.5, 1100.0),
    ]


def test_loader_fails_closed_when_open_adj_is_absent(tmp_path, monkeypatch) -> None:
    driver = _load_driver()
    _write_parquet(
        tmp_path / "sep_2020.parquet",
        {
            "symbol": ["ACME"],
            "date": [date(2020, 1, 2)],
            "close_adj": [10.5],
            "volume": [1000.0],
        },
    )
    monkeypatch.setattr(driver, "SEP_DIR", tmp_path)

    with pytest.raises(SystemExit, match="open_adj"):
        driver._load_sep_year(2020, {"ACME"})


class _FakeReader:
    """Stands in for SharadarMarketDataReader.fetch_available — records the call and
    returns a fixed adjusted-bar panel spanning two calendar years."""

    def __init__(self, bars):
        self._bars = bars
        self.calls = []

    def fetch_available(self, symbols, start, end):
        self.calls.append((symbols, start, end))
        return list(self._bars)


def test_materialize_sep_panel_writes_per_year_parquets_the_loader_reads_back(
    tmp_path, monkeypatch
) -> None:
    """The materializer round-trips: DailyBars pulled from the reader land in
    sep_<year>.parquet with canonical columns, and _load_sep_year reads the exact
    (date, open_adj, close_adj, volume) tuples back — open maps to open_adj,
    close (=closeadj) maps to close_adj."""
    from decimal import Decimal

    from invest.domain.models import DailyBar

    driver = _load_driver()
    bars = [
        DailyBar("ACME", date(2019, 12, 31), Decimal("9"), Decimal("11"), Decimal("8"),
                 Decimal("10.5"), Decimal("1000")),
        DailyBar("ACME", date(2020, 1, 2), Decimal("11"), Decimal("13"), Decimal("10"),
                 Decimal("11.5"), Decimal("1100")),
        DailyBar("BETA", date(2020, 1, 2), Decimal("20"), Decimal("21"), Decimal("19"),
                 Decimal("20.5"), Decimal("500")),
    ]
    reader = _FakeReader(bars)

    written = driver.materialize_sep_panel(
        {"BETA", "ACME"}, date(2019, 1, 1), date(2020, 12, 31), tmp_path,
        reader=reader, verbose=False,
    )

    assert [p.name for p in written] == ["sep_2019.parquet", "sep_2020.parquet"]
    # Reader was asked for the sorted symbol tuple over the exact window.
    assert reader.calls == [(("ACME", "BETA"), date(2019, 1, 1), date(2020, 12, 31))]

    monkeypatch.setattr(driver, "SEP_DIR", tmp_path)
    y2019 = driver._load_sep_year(2019, {"ACME", "BETA"})
    y2020 = driver._load_sep_year(2020, {"ACME", "BETA"})

    assert y2019 == {"ACME": [(date(2019, 12, 31), 9.0, 10.5, 1000.0)]}
    assert y2020 == {
        "ACME": [(date(2020, 1, 2), 11.0, 11.5, 1100.0)],
        "BETA": [(date(2020, 1, 2), 20.0, 20.5, 500.0)],
    }
