from invest.contracts.events import EventBase


class MemoryJournal:
    """Idempotent, deterministically ordered journal for a single scan run."""

    def __init__(self) -> None:
        self._events: dict[str, EventBase] = {}

    def append(self, event: EventBase) -> None:
        self._events.setdefault(event.event_id, event)

    def events(self) -> list[EventBase]:
        return sorted(
            self._events.values(),
            key=lambda event: (
                event.decision_date,
                event.symbol or "",
                event.event_type,
                getattr(event, "reason", ""),
            ),
        )
