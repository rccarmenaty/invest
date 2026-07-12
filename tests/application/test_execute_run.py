from datetime import date, timedelta
from decimal import Decimal

from invest.adapters.journal_memory import MemoryJournal
from invest.application.execute_run import ExecuteRun
from invest.domain.models import AccountSnapshot, DailyBar, FixtureInputs, OrderIntent, Universe
from invest.domain.scanner import MomentumScanner


class FakeBroker:
    def __init__(self, snapshot: AccountSnapshot) -> None:
        self._snapshot = snapshot
        self.snapshot_calls = 0
        self.find_calls = 0
        self.submit_calls = 0

    def snapshot(self) -> AccountSnapshot:
        self.snapshot_calls += 1
        return self._snapshot

    def find_order(self, client_order_id: str) -> str | None:
        self.find_calls += 1
        return None

    def submit_bracket(self, intent: OrderIntent) -> str:
        self.submit_calls += 1
        return "broker-1"


def _accepted_bars(symbol: str) -> tuple[DailyBar, ...]:
    start = date(2026, 1, 1)
    history = tuple(
        DailyBar(
            symbol=symbol,
            date=start + timedelta(days=index),
            open=Decimal("10"),
            high=Decimal("10.40"),
            low=Decimal("9.60"),
            close=Decimal("10"),
            volume=100,
        )
        for index in range(20)
    )
    return (*history, DailyBar(symbol, start + timedelta(days=20), Decimal("10"), Decimal("11.50"), Decimal("10"), Decimal("11.40"), 250))


def _inputs(*symbols: str) -> FixtureInputs:
    return FixtureInputs(
        Universe("v1", symbols),
        tuple(bar for symbol in symbols for bar in _accepted_bars(symbol)),
    )


def _snapshot(**changes: object) -> AccountSnapshot:
    values = {
        "equity": Decimal("10000"),
        "last_equity": Decimal("10000"),
        "buying_power": Decimal("10000"),
        "open_position_count": 0,
        "deployed_value": Decimal("0"),
        "trading_blocked": False,
        "account_blocked": False,
    }
    values.update(changes)
    return AccountSnapshot(**values)


def test_execute_run_dry_run_rescans_sizes_and_never_mutates_broker() -> None:
    broker = FakeBroker(_snapshot())
    run = ExecuteRun(MomentumScanner(), MemoryJournal(), broker, rule_version="momentum-v1")

    events = run.execute(_inputs("ACME"))

    assert [event.event_type for event in events] == ["order.intent.v1"]
    assert events[0].symbol == "ACME"
    assert events[0].qty > 0
    assert broker.snapshot_calls == 1
    assert broker.find_calls == broker.submit_calls == 0


def test_execute_run_halt_emits_once_then_skips_every_candidate_and_completes() -> None:
    broker = FakeBroker(_snapshot(equity=Decimal("9700"), last_equity=Decimal("10000")))
    run = ExecuteRun(MomentumScanner(), MemoryJournal(), broker, rule_version="momentum-v1")

    events = run.execute(_inputs("ACME", "BETA"))

    assert [event.event_type for event in events] == [
        "execution.halted.v1",
        "execution.skipped.v1",
        "execution.skipped.v1",
    ]
    assert {event.reason for event in events} == {"kill-switch"}
    assert broker.snapshot_calls == 1
    assert broker.find_calls == broker.submit_calls == 0


def test_execute_run_halt_emits_once_with_zero_accepted_candidates() -> None:
    broker = FakeBroker(_snapshot(trading_blocked=True))
    run = ExecuteRun(MomentumScanner(), MemoryJournal(), broker, rule_version="momentum-v1")
    no_candidates = FixtureInputs(Universe("v1", ()), ())

    events = run.execute(no_candidates)

    assert [event.event_type for event in events] == ["execution.halted.v1"]
    assert events[0].reason == "broker-account-restricted"
    assert broker.snapshot_calls == 1
    assert broker.find_calls == broker.submit_calls == 0


def test_execute_run_continues_after_candidate_gate_failure_with_running_projection() -> None:
    broker = FakeBroker(_snapshot())
    run = ExecuteRun(MomentumScanner(), MemoryJournal(), broker, rule_version="momentum-v1")

    events = run.execute(_inputs("ACME", "BETA"))

    intents = [event for event in events if event.event_type == "order.intent.v1"]
    skips = [event for event in events if event.event_type == "execution.skipped.v1"]
    assert [event.symbol for event in intents] == ["ACME"]
    assert [(event.symbol, event.reason) for event in skips] == [
        ("BETA", "max-equity-deployed")
    ]
    assert broker.find_calls == broker.submit_calls == 0
