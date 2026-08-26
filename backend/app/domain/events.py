"""Episode-aware, in-memory event lifecycle for synthetic toy scenarios."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import uuid4


class EventStatus(StrEnum):
    DETECTED = "detected"
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    CHECKED = "checked"
    RESOLVED = "resolved"


class EventPriority(StrEnum):
    WATCH = "watch"
    HIGH = "high"
    CRITICAL = "critical"


class ResolutionOutcome(StrEnum):
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class MonitoringEvent:
    event_id: str
    episode_id: str
    resident_id: str
    room_id: str
    objective_family: str
    headline: str
    priority: EventPriority
    status: EventStatus
    created_at: datetime
    last_signal_at: datetime
    signal_count: int = 1
    related_event_ids: tuple[str, ...] = ()
    recurrence_count: int = 1
    overdue: bool = False
    resolution_outcome: ResolutionOutcome | None = None
    schema_version: str = "1.0"


class EventStore:
    """Groups related synthetic signals and enforces the caregiver lifecycle."""

    def __init__(self, quiet_gap: timedelta = timedelta(minutes=5)) -> None:
        if quiet_gap <= timedelta(0):
            raise ValueError("quiet_gap must be positive")
        self.quiet_gap = quiet_gap
        self._events: dict[str, MonitoringEvent] = {}

    def record_signal(
        self,
        *,
        resident_id: str,
        room_id: str,
        objective_family: str,
        headline: str,
        priority: EventPriority,
        observed_at: datetime,
    ) -> MonitoringEvent:
        active = self._latest_related(resident_id, room_id, objective_family)
        if active is not None:
            elapsed = observed_at - active.last_signal_at
            if elapsed < timedelta(0):
                raise ValueError("observed_at cannot precede the latest related signal")
        if (
            active is not None
            and active.status != EventStatus.RESOLVED
            and elapsed <= self.quiet_gap
        ):
            updated = replace(
                active,
                last_signal_at=observed_at,
                signal_count=active.signal_count + 1,
                priority=max(
                    active.priority,
                    priority,
                    key=lambda value: (
                        EventPriority.WATCH,
                        EventPriority.HIGH,
                        EventPriority.CRITICAL,
                    ).index(value),
                ),
            )
            self._events[updated.event_id] = updated
            return updated

        related = self._related_events(resident_id, room_id, objective_family)
        event_id = f"evt_{uuid4().hex}"
        event = MonitoringEvent(
            event_id=event_id,
            episode_id=f"episode_{uuid4().hex}",
            resident_id=resident_id,
            room_id=room_id,
            objective_family=objective_family,
            headline=headline,
            priority=priority,
            status=EventStatus.OPEN,
            created_at=observed_at,
            last_signal_at=observed_at,
            related_event_ids=tuple(item.event_id for item in related),
            recurrence_count=len(related) + 1,
        )
        self._events[event_id] = event
        return event

    def get(self, event_id: str) -> MonitoringEvent:
        try:
            return self._events[event_id]
        except KeyError as exc:
            raise KeyError(f"Unknown event: {event_id}") from exc

    def acknowledge(self, event_id: str) -> MonitoringEvent:
        return self._transition(event_id, EventStatus.OPEN, EventStatus.ACKNOWLEDGED)

    def check(self, event_id: str) -> MonitoringEvent:
        return self._transition(
            event_id,
            EventStatus.ACKNOWLEDGED,
            EventStatus.CHECKED,
        )

    def resolve(
        self,
        event_id: str,
        outcome: ResolutionOutcome,
    ) -> MonitoringEvent:
        outcome = ResolutionOutcome(outcome)
        event = self._transition(event_id, EventStatus.CHECKED, EventStatus.RESOLVED)
        resolved = replace(event, resolution_outcome=outcome)
        self._events[resolved.event_id] = resolved
        return resolved

    def mark_overdue(self, event_id: str, *, at: datetime) -> MonitoringEvent:
        event = self.get(event_id)
        if event.priority == EventPriority.WATCH:
            raise ValueError("watch events do not use overdue escalation")
        if event.status != EventStatus.OPEN:
            raise ValueError("only unacknowledged open events become overdue")
        if at <= event.created_at:
            raise ValueError("overdue time must follow event creation")
        overdue = replace(event, overdue=True)
        self._events[overdue.event_id] = overdue
        return overdue

    def _transition(
        self,
        event_id: str,
        expected: EventStatus,
        target: EventStatus,
    ) -> MonitoringEvent:
        event = self.get(event_id)
        if event.status != expected:
            raise ValueError(
                f"Cannot move event {event_id} from {event.status} to {target}"
            )
        transitioned = replace(event, status=target)
        self._events[transitioned.event_id] = transitioned
        return transitioned

    def _related_events(
        self,
        resident_id: str,
        room_id: str,
        objective_family: str,
    ) -> list[MonitoringEvent]:
        return sorted(
            (
                event
                for event in self._events.values()
                if event.resident_id == resident_id
                and event.room_id == room_id
                and event.objective_family == objective_family
            ),
            key=lambda event: event.created_at,
        )

    def _latest_related(
        self,
        resident_id: str,
        room_id: str,
        objective_family: str,
    ) -> MonitoringEvent | None:
        related = self._related_events(resident_id, room_id, objective_family)
        return related[-1] if related else None
