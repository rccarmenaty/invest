"""Versioned event contracts emitted by scan runs."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


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
