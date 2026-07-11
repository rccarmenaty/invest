from datetime import date
from decimal import Decimal

from invest.adapters.journal_memory import MemoryJournal
from invest.application.scan_run import ScanRun
from invest.domain.models import DailyBar, FixtureInputs, Universe
from invest.domain.scanner import MomentumScanner


def _inputs() -> FixtureInputs:
    bars = tuple(
        DailyBar("ACME", date(2026, 6, day), Decimal("10"), Decimal("10.2"), Decimal("9.8"), Decimal("10"), 100)
        for day in range(1, 21)
    ) + (DailyBar("ACME", date(2026, 6, 21), Decimal("10"), Decimal("11.4"), Decimal("10"), Decimal("11.2"), 250),)
    return FixtureInputs(Universe("v1", ("ACME",)), bars)


def test_scan_run_maps_and_journals_deterministic_contracts() -> None:
    journal = MemoryJournal()
    run = ScanRun(MomentumScanner(), journal, rule_version="momentum-v1")

    first = run.execute(_inputs())
    second = run.execute(_inputs())

    assert first == second == journal.events()
    assert len(first) == 1
    assert first[0].event_type == "candidate.accepted.v1"
    assert first[0].event_id
