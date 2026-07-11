from datetime import date

from invest.adapters.journal_memory import MemoryJournal
from invest.contracts.events import AcceptedCandidate, RejectedCandidate


def test_journal_stores_unique_events_in_deterministic_order() -> None:
    journal = MemoryJournal()
    later = AcceptedCandidate(schema_version="1", event_type="candidate.accepted.v1", event_id="b", symbol="ZZZ", decision_date=date(2026, 7, 11), fixture_version="v1", rule_version="momentum-v1", decision="accepted")
    earlier = RejectedCandidate(schema_version="1", event_type="candidate.rejected.v1", event_id="a", symbol="AAA", decision_date=date(2026, 7, 10), fixture_version="v1", rule_version="momentum-v1", decision="rejected", reason="no-signal")

    journal.append(later)
    journal.append(earlier)
    journal.append(later)

    assert journal.events() == [earlier, later]
