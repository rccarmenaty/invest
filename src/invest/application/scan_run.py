import hashlib

from invest.application.ports import Journal
from invest.contracts.events import AcceptedCandidate, EventBase, RejectedCandidate
from invest.domain.models import FixtureInputs, ScanDecision
from invest.domain.scanner import MomentumScanner


class ScanRun:
    def __init__(self, scanner: MomentumScanner, journal: Journal, rule_version: str) -> None:
        self._scanner = scanner
        self._journal = journal
        self._rule_version = rule_version

    def execute(self, inputs: FixtureInputs) -> list[EventBase]:
        for decision in self._scanner.scan(inputs.universe, inputs.bars):
            self._journal.append(self._to_event(decision, inputs.universe.fixture_version))
        return self._journal.events()

    def _to_event(self, decision: ScanDecision, fixture_version: str) -> EventBase:
        reason = decision.reason.value if decision.reason else ""
        event_type = "candidate.accepted.v1" if decision.accepted else "candidate.rejected.v1"
        event_id = hashlib.sha256(
            "|".join(("1", fixture_version, self._rule_version, decision.symbol, decision.decision_date.isoformat(), "accepted" if decision.accepted else "rejected", reason)).encode()
        ).hexdigest()
        common = dict(schema_version="1", event_type=event_type, event_id=event_id, symbol=decision.symbol, decision_date=decision.decision_date, fixture_version=fixture_version, rule_version=self._rule_version)
        if decision.accepted:
            return AcceptedCandidate(**common, decision="accepted")
        return RejectedCandidate(**common, decision="rejected", reason=reason)
