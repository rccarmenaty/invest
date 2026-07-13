import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from invest.adapters import cli
from invest.domain.models import AccountSnapshot, BrokerAck


def _accepted_fixture(tmp_path: Path, symbol: str | tuple[str, ...] = "ACME") -> tuple[Path, Path]:
    """A universe/bars pair that produces one accepted momentum candidate."""
    start = date(2026, 1, 1)
    symbols = (symbol,) if isinstance(symbol, str) else symbol
    bars = [
        {
            "symbol": item,
            "date": (start + timedelta(days=index)).isoformat(),
            "open": 10,
            "high": 10.40,
            "low": 9.60,
            "close": 10,
            "volume": 100,
        }
        for item in symbols
        for index in range(20)
    ]
    bars.extend(
        {
            "symbol": item,
            "date": (start + timedelta(days=20)).isoformat(),
            "open": 10,
            "high": 11.50,
            "low": 10,
            "close": 11.40,
            "volume": 250,
        }
        for item in symbols
    )
    universe_path = tmp_path / "universe.json"
    bars_path = tmp_path / "bars.json"
    universe_path.write_text(
        json.dumps({"fixture_version": "v1", "symbols": list(symbols)}), encoding="utf-8"
    )
    bars_path.write_text(json.dumps({"fixture_version": "v1", "bars": bars}), encoding="utf-8")
    return universe_path, bars_path


def _snapshot(**changes: object) -> AccountSnapshot:
    values: dict[str, object] = {
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


def _fake_broker_factory(
    *,
    snapshot: AccountSnapshot | None = None,
    snapshot_error: Exception | None = None,
    ack: BrokerAck | None = None,
    created: list,
):
    class FakeBroker:
        def __init__(self) -> None:
            self.find_calls = 0
            self.submit_calls = 0
            created.append(self)

        def snapshot(self) -> AccountSnapshot:
            if snapshot_error is not None:
                raise snapshot_error
            assert snapshot is not None
            return snapshot

        def find_order(self, client_order_id: str) -> str | None:
            self.find_calls += 1
            return None

        def submit_bracket(self, intent, client_order_id: str) -> BrokerAck:
            self.submit_calls += 1
            assert ack is not None
            return ack

    return FakeBroker


def test_execute_dry_run_default_prints_intents_and_makes_zero_broker_mutation_calls(
    tmp_path, monkeypatch, capsys
) -> None:
    universe, bars = _accepted_fixture(tmp_path)
    created: list = []
    monkeypatch.setattr(
        cli, "AlpacaBroker", _fake_broker_factory(snapshot=_snapshot(), created=created)
    )

    result = cli.execute_main(
        ["--universe", str(universe), "--bars", str(bars), "--format", "json"]
    )

    captured = capsys.readouterr()
    assert result == 0
    payload = json.loads(captured.out)
    assert any(event["event_type"] == "order.intent.v1" for event in payload)
    assert created[0].find_calls == 0
    assert created[0].submit_calls == 0
    assert captured.err == ""


def test_execute_flag_submits_and_journals_broker_ack(tmp_path, monkeypatch, capsys) -> None:
    universe, bars = _accepted_fixture(tmp_path)
    created: list = []
    monkeypatch.setattr(
        cli,
        "AlpacaBroker",
        _fake_broker_factory(
            snapshot=_snapshot(),
            ack=BrokerAck(broker_order_id="broker-1", status="submitted"),
            created=created,
        ),
    )

    result = cli.execute_main(
        ["--universe", str(universe), "--bars", str(bars), "--format", "json", "--execute"]
    )

    captured = capsys.readouterr()
    assert result == 0
    payload = json.loads(captured.out)
    assert any(event["event_type"] == "order.submitted.v1" for event in payload)
    assert created[0].submit_calls == 1


def test_execute_infra_failure_prints_exactly_one_record_and_exits_two(
    tmp_path, monkeypatch, capsys
) -> None:
    from invest.adapters.alpaca_broker import BrokerFetchError

    universe, bars = _accepted_fixture(tmp_path)
    created: list = []
    monkeypatch.setattr(
        cli,
        "AlpacaBroker",
        _fake_broker_factory(snapshot_error=BrokerFetchError("auth-failure"), created=created),
    )

    result = cli.execute_main(
        ["--universe", str(universe), "--bars", str(bars), "--format", "json"]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert json.loads(captured.out) == {"reason": "auth-failure"}
    assert captured.out.count("\n") == 1
    assert captured.err == ""


def test_execute_invalid_fixture_fails_before_broker_is_constructed(
    tmp_path, monkeypatch, capsys
) -> None:
    universe = tmp_path / "universe.json"
    universe.write_text('{"fixture_version":"v1","symbols":["ACME"]}', encoding="utf-8")
    bars = tmp_path / "bars.json"
    bars.write_text("not-json", encoding="utf-8")

    def _fail_if_constructed(*args, **kwargs):
        raise AssertionError("broker must not be constructed before fixtures validate")

    monkeypatch.setattr(cli, "AlpacaBroker", _fail_if_constructed)

    result = cli.execute_main(
        ["--universe", str(universe), "--bars", str(bars), "--format", "json"]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert json.loads(captured.out) == {"reason": "fixture-invalid"}
    assert captured.out.count("\n") == 1
    assert captured.err == ""


def test_execute_all_halted_business_outcome_exits_zero_with_full_event_list(
    tmp_path, monkeypatch, capsys
) -> None:
    universe, bars = _accepted_fixture(tmp_path)
    created: list = []
    monkeypatch.setattr(
        cli,
        "AlpacaBroker",
        _fake_broker_factory(snapshot=_snapshot(trading_blocked=True), created=created),
    )

    result = cli.execute_main(
        ["--universe", str(universe), "--bars", str(bars), "--format", "json"]
    )

    captured = capsys.readouterr()
    assert result == 0
    payload = json.loads(captured.out)
    assert [event["event_type"] for event in payload] == [
        "execution.halted.v1",
        "execution.skipped.v1",
    ]
    assert created[0].submit_calls == 0


def test_execute_rejected_business_outcome_exits_zero(tmp_path, monkeypatch, capsys) -> None:
    universe, bars = _accepted_fixture(tmp_path)
    created: list = []
    monkeypatch.setattr(
        cli,
        "AlpacaBroker",
        _fake_broker_factory(
            snapshot=_snapshot(),
            ack=BrokerAck(broker_order_id=None, status="rejected", reason="invalid order"),
            created=created,
        ),
    )

    result = cli.execute_main(
        ["--universe", str(universe), "--bars", str(bars), "--format", "json", "--execute"]
    )

    captured = capsys.readouterr()
    assert result == 0
    payload = json.loads(captured.out)
    assert any(event["event_type"] == "order.rejected.v1" for event in payload)


def test_execute_mid_run_infra_failure_prints_full_journal_and_exits_two(
    tmp_path, monkeypatch, capsys
) -> None:
    from invest.adapters.alpaca_broker import BrokerFetchError

    universe, bars = _accepted_fixture(tmp_path, ("ACME", "BETA", "CHARLIE"))

    class FailingBroker:
        def __init__(self) -> None:
            self.calls = 0

        def snapshot(self) -> AccountSnapshot:
            return _snapshot(
                equity=Decimal("100000"),
                buying_power=Decimal("100000"),
                deployed_value=Decimal("-30000"),
            )

        def submit_bracket(self, intent, client_order_id: str) -> BrokerAck:
            self.calls += 1
            if self.calls == 2:
                raise BrokerFetchError("submission-uncertain")
            return BrokerAck(broker_order_id=f"broker-{self.calls}", status="submitted")

    monkeypatch.setattr(cli, "AlpacaBroker", FailingBroker)

    result = cli.execute_main(
        ["--universe", str(universe), "--bars", str(bars), "--format", "json", "--execute"]
    )

    payload = json.loads(capsys.readouterr().out)
    assert result == 2
    assert any(event["event_type"] == "order.submitted.v1" and event["symbol"] == "ACME" for event in payload)
    skips = [(event["symbol"], event["reason"]) for event in payload if event["event_type"] == "execution.skipped.v1"]
    assert skips == [("BETA", "submission-uncertain"), ("CHARLIE", "submission-uncertain")]


def test_execute_parser_does_not_accept_market_context_argument() -> None:
    options = {action.dest for action in cli._execute_parser()._actions}

    assert "market_context" not in options
