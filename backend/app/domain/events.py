"""The first product slice: a durable monitoring event and its lifecycle.

This in-memory store is deliberately small. It lets us agree on product
behavior before adding the database and HTTP API around the same rules.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum


class EventStatus(StrEnum):
    DETECTED = "detected"
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    CHECKED = "checked"
    RESOLVED = "resolved"


class ResolutionOutcome(StrEnum):
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    UNCERTAIN = "uncertain"


@dataclass
class MonitoringEvent:
    event_id: str
    resident_id: str
    room_id: str
    headline: str
    status: EventStatus = EventStatus.DETECTED
    resolution_outcome: ResolutionOutcome | None = None
    created_at: datetime | None = None
    schema_version: str = "1.0"


class EventStore:
    """Stores events and enforces the user-facing lifecycle."""

    _allowed_transitions = {
        EventStatus.DETECTED: EventStatus.OPEN,
        EventStatus.OPEN: EventStatus.ACKNOWLEDGED,
        EventStatus.ACKNOWLEDGED: EventStatus.CHECKED,
        EventStatus.CHECKED: EventStatus.RESOLVED,
    }

    def __init__(self) -> None:
        self._events: dict[str, MonitoringEvent] = {}

    def create_event(
        self,
        *,
        event_id: str,
        resident_id: str,
        room_id: str,
        headline: str,
    ) -> MonitoringEvent:
        if event_id in self._events:
            raise ValueError(f"Event already exists: {event_id}")
        event = MonitoringEvent(
            event_id=event_id,
            resident_id=resident_id,
            room_id=room_id,
            headline=headline,
            created_at=datetime.now(timezone.utc),
        )
        self._events[event_id] = event
        return event

    def get(self, event_id: str) -> MonitoringEvent:
        try:
            return self._events[event_id]
        except KeyError as exc:
            raise KeyError(f"Unknown event: {event_id}") from exc

    def open_event(self, event_id: str) -> MonitoringEvent:
        return self._transition(event_id, EventStatus.OPEN)

    def acknowledge(self, event_id: str) -> MonitoringEvent:
        return self._transition(event_id, EventStatus.ACKNOWLEDGED)

    def check(self, event_id: str) -> MonitoringEvent:
        return self._transition(event_id, EventStatus.CHECKED)

    def resolve(
        self, event_id: str, outcome: ResolutionOutcome
    ) -> MonitoringEvent:
        event = self._transition(event_id, EventStatus.RESOLVED)
        event.resolution_outcome = outcome
        return event

    def _transition(self, event_id: str, target: EventStatus) -> MonitoringEvent:
        event = self.get(event_id)
        expected = self._allowed_transitions.get(event.status)
        if expected != target:
            raise ValueError(
                f"Cannot move event {event_id} from {event.status} to {target}"
            )
        event.status = target
        return event
