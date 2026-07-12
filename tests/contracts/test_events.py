import hashlib
from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from invest.contracts.events import AcceptedCandidate, FailedScan, RejectedCandidate
from invest.domain.models import OrderIntent
from invest.domain.sizing import GateReason


def test_accepted_candidate_requires_schema_version() -> None:
    with pytest.raises(ValidationError):
        AcceptedCandidate(
            event_type="candidate.accepted.v1",
            event_id="evt-1",
            symbol="ACME",
            decision_date=date(2026, 7, 10),
            fixture_version="v1",
            rule_version="momentum-v1",
            decision="accepted",
        )


@pytest.mark.parametrize(
    ("contract", "payload", "event_type", "decision"),
    [
        (
            AcceptedCandidate,
            {"symbol": "ACME"},
            "candidate.accepted.v1",
            "accepted",
        ),
        (
            RejectedCandidate,
            {"symbol": "BETA", "reason": "no-signal"},
            "candidate.rejected.v1",
            "rejected",
        ),
        (
            FailedScan,
            {"symbol": None, "reason": "fixture-invalid"},
            "scan.failed.v1",
            "failed",
        ),
    ],
)
def test_contracts_preserve_versioned_fields(contract, payload, event_type, decision) -> None:
    event = contract(
        schema_version="1",
        event_type=event_type,
        event_id="evt-123",
        decision_date=date(2026, 7, 10),
        fixture_version="v1",
        rule_version="momentum-v1",
        decision=decision,
        **payload,
    )

    assert event.model_dump(mode="json") == {
        "schema_version": "1",
        "event_type": event_type,
        "event_id": "evt-123",
        "symbol": payload["symbol"],
        "decision_date": "2026-07-10",
        "fixture_version": "v1",
        "rule_version": "momentum-v1",
        "decision": decision,
        **({"reason": payload["reason"]} if "reason" in payload else {}),
    }


def test_order_intent_event_is_reproducible_and_serializes_quantized_prices() -> None:
    from invest.contracts.events import OrderIntentEvent

    intent = OrderIntent(
        symbol="ACME",
        decision_date=date(2026, 7, 10),
        qty=12,
        entry=Decimal("11.20"),
        stop=Decimal("10.90"),
        take_profit=Decimal("11.80"),
    )

    first = OrderIntentEvent.from_intent(intent, fixture_version="v1", rule_version="momentum-v1")
    second = OrderIntentEvent.from_intent(intent, fixture_version="v1", rule_version="momentum-v1")
    expected_id = hashlib.sha256(
        b"1|order.intent.v1|v1|momentum-v1|ACME|2026-07-10|12|10.90|11.80"
    ).hexdigest()

    assert first == second
    assert first.event_id == first.client_order_id == expected_id
    assert (first.entry_price, first.stop_price, first.take_profit_price) == (
        "11.20",
        "10.90",
        "11.80",
    )


def test_execution_events_use_their_own_content_addressed_id_family() -> None:
    from invest.contracts.events import (
        EventBase,
        ExecutionEventBase,
        ExecutionHalted,
        ExecutionSkipped,
        OrderRejected,
        OrderSubmitted,
    )

    common = {
        "symbol": "ACME",
        "decision_date": date(2026, 7, 10),
        "fixture_version": "v1",
        "rule_version": "momentum-v1",
    }
    submitted = OrderSubmitted.from_ack(intent_id="intent-1", broker_order_id="broker-1", **common)
    rejected = OrderRejected.from_ack(
        intent_id="intent-1", reason="rejected", broker_order_id="broker-2", **common
    )
    skipped = ExecutionSkipped.from_reason(
        intent_id_or_symbol="intent-1", reason=GateReason.SIZING_INVALID, **common
    )
    halted = ExecutionHalted.from_reason(
        reason=GateReason.KILL_SWITCH,
        decision_date=common["decision_date"],
        fixture_version="v1",
        rule_version="momentum-v1",
    )

    assert not issubclass(ExecutionEventBase, EventBase)
    assert submitted.event_id == hashlib.sha256(b"intent-1|broker-1").hexdigest()
    assert rejected.event_id == hashlib.sha256(b"intent-1|rejected|broker-2").hexdigest()
    assert skipped.event_id == hashlib.sha256(b"intent-1|sizing-invalid").hexdigest()
    assert halted.event_id == hashlib.sha256(b"execution.halted.v1|v1|kill-switch").hexdigest()

    deterministic_intent_style = hashlib.sha256(
        b"1|order.intent.v1|v1|momentum-v1|ACME|2026-07-10|1|10.00|12.00"
    ).hexdigest()
    assert all(
        event.event_id != deterministic_intent_style
        for event in (submitted, rejected, skipped, halted)
    )
