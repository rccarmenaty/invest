"""Versioned event contracts emitted by scan runs."""

import hashlib
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from invest.domain.models import OrderIntent
from invest.domain.sizing import GateReason


class EventBase(BaseModel):
    """Fields shared by every deterministic scan event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"]
    event_type: str
    event_id: str
    symbol: str | None
    decision_date: date
    fixture_version: str
    rule_version: str
    decision: str


class AcceptedCandidate(EventBase):
    event_type: Literal["candidate.accepted.v1"]
    symbol: str
    decision: Literal["accepted"]


class RejectedCandidate(EventBase):
    event_type: Literal["candidate.rejected.v1"]
    symbol: str
    decision: Literal["rejected"]
    reason: str


class FailedScan(EventBase):
    event_type: Literal["scan.failed.v1"]
    decision: Literal["failed"]
    reason: str


class OrderIntentEvent(EventBase):
    event_type: Literal["order.intent.v1"]
    symbol: str
    decision: Literal["intent"]
    qty: int
    entry_price: str
    stop_price: str
    take_profit_price: str
    client_order_id: str

    @classmethod
    def from_intent(
        cls,
        intent: OrderIntent,
        *,
        fixture_version: str,
        rule_version: str,
    ) -> "OrderIntentEvent":
        event_id = hashlib.sha256(
            "|".join(
                (
                    "1",
                    "order.intent.v1",
                    fixture_version,
                    rule_version,
                    intent.symbol,
                    intent.decision_date.isoformat(),
                    str(intent.qty),
                    str(intent.stop),
                    str(intent.take_profit),
                )
            ).encode()
        ).hexdigest()
        return cls(
            schema_version="1",
            event_type="order.intent.v1",
            event_id=event_id,
            symbol=intent.symbol,
            decision_date=intent.decision_date,
            fixture_version=fixture_version,
            rule_version=rule_version,
            decision="intent",
            qty=intent.qty,
            entry_price=str(intent.entry),
            stop_price=str(intent.stop),
            take_profit_price=str(intent.take_profit),
            client_order_id=event_id,
        )


class ExecutionEventBase(BaseModel):
    """Fields shared by broker acknowledgement and execution outcome events."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"]
    event_type: str
    event_id: str
    symbol: str | None
    decision_date: date
    fixture_version: str
    rule_version: str
    decision: str


class OrderSubmitted(ExecutionEventBase):
    event_type: Literal["order.submitted.v1"]
    symbol: str
    decision: Literal["submitted"]
    intent_id: str
    broker_order_id: str

    @classmethod
    def from_ack(cls, *, intent_id: str, broker_order_id: str, **common: object) -> "OrderSubmitted":
        event_id = hashlib.sha256(f"{intent_id}|{broker_order_id}".encode()).hexdigest()
        return cls(
            schema_version="1",
            event_type="order.submitted.v1",
            event_id=event_id,
            decision="submitted",
            intent_id=intent_id,
            broker_order_id=broker_order_id,
            **common,
        )


class OrderRejected(ExecutionEventBase):
    event_type: Literal["order.rejected.v1"]
    symbol: str
    decision: Literal["rejected"]
    intent_id: str
    reason: str
    broker_order_id: str

    @classmethod
    def from_ack(
        cls,
        *,
        intent_id: str,
        reason: str,
        broker_order_id: str,
        **common: object,
    ) -> "OrderRejected":
        event_id = hashlib.sha256(f"{intent_id}|{reason}|{broker_order_id}".encode()).hexdigest()
        return cls(
            schema_version="1",
            event_type="order.rejected.v1",
            event_id=event_id,
            decision="rejected",
            intent_id=intent_id,
            reason=reason,
            broker_order_id=broker_order_id,
            **common,
        )


class ExecutionSkipped(ExecutionEventBase):
    event_type: Literal["execution.skipped.v1"]
    symbol: str
    decision: Literal["skipped"]
    intent_id: str | None
    reason: str

    @classmethod
    def from_reason(
        cls,
        *,
        intent_id_or_symbol: str,
        reason: GateReason | str,
        broker_order_id: str | None = None,
        **common: object,
    ) -> "ExecutionSkipped":
        reason_value = reason.value if isinstance(reason, GateReason) else reason
        id_parts = [intent_id_or_symbol, reason_value]
        if broker_order_id is not None:
            id_parts.append(broker_order_id)
        event_id = hashlib.sha256("|".join(id_parts).encode()).hexdigest()
        return cls(
            schema_version="1",
            event_type="execution.skipped.v1",
            event_id=event_id,
            decision="skipped",
            intent_id=intent_id_or_symbol if intent_id_or_symbol != common.get("symbol") else None,
            reason=reason_value,
            **common,
        )


class ExecutionHalted(ExecutionEventBase):
    event_type: Literal["execution.halted.v1"]
    symbol: None
    decision: Literal["halted"]
    reason: GateReason

    @classmethod
    def from_reason(
        cls,
        *,
        reason: GateReason,
        decision_date: date,
        fixture_version: str,
        rule_version: str,
    ) -> "ExecutionHalted":
        event_id = hashlib.sha256(f"execution.halted.v1|{fixture_version}|{reason.value}".encode()).hexdigest()
        return cls(
            schema_version="1",
            event_type="execution.halted.v1",
            event_id=event_id,
            symbol=None,
            decision_date=decision_date,
            fixture_version=fixture_version,
            rule_version=rule_version,
            decision="halted",
            reason=reason,
        )
