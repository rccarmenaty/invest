from pydantic import BaseModel


class MemoryJournal:
    """Idempotent, deterministically ordered journal for a single scan run."""

    def __init__(self) -> None:
        self._events: dict[str, BaseModel] = {}

    def append(self, event: BaseModel) -> None:
        self._events.setdefault(event.event_id, event)

    def events(self) -> list[BaseModel]:
        return sorted(
            self._events.values(),
            key=lambda event: (
                event.decision_date,
                event.symbol or "",
                event.event_type,
                getattr(event, "reason", ""),
            ),
        )
