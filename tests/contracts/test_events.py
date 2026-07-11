from datetime import date

import pytest
from pydantic import ValidationError

from invest.contracts.events import AcceptedCandidate, FailedScan, RejectedCandidate


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
