"""Episode-aware, in-memory event lifecycle for synthetic toy scenarios."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar
from uuid import uuid4

from backend.app.domain._validation import (
    coerce_enum,
    require_aware_datetime,
    require_nonblank_text,
)
from backend.app.domain.monitoring import MonitoringSnapshot, MonitoringState

if TYPE_CHECKING:
    from backend.app.domain.feedback import ResidentMemory


SYSTEM_EVENT_ACTOR_ID = "system:monitoring_event"
SYSTEM_OVERDUE_ACTOR_ID = "system:overdue_policy"


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


class EventActionType(StrEnum):
    OPENED = "opened"
    ACKNOWLEDGED = "acknowledged"
    CHECKED = "checked"
    RESOLVED = "resolved"
    MARKED_OVERDUE = "marked_overdue"


@dataclass(frozen=True)
class EventAction:
    action: EventActionType
    actor_id: str
    occurred_at: datetime
    previous_status: EventStatus
    status: EventStatus
    resolution_outcome: ResolutionOutcome | None = None
    schema_version: str = "1.0"


@dataclass(frozen=True)
class EventPriorityHistoryEntry:
    previous_priority: EventPriority | None
    priority: EventPriority
    actor_id: str
    changed_at: datetime
    schema_version: str = "1.0"


@dataclass(frozen=True)
class SyntheticEventEpisodePolicy:
    """Versioned toy-only quiet-gap policy; not a production threshold."""

    TEST_ONLY: ClassVar[bool] = True
    quiet_gap: timedelta = timedelta(minutes=5)
    policy_version: str = "synthetic_event_episode_v1"
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if not isinstance(self.quiet_gap, timedelta):
            raise ValueError("quiet_gap must be a timedelta")
        if self.quiet_gap <= timedelta(0):
            raise ValueError("quiet_gap must be positive")
        object.__setattr__(
            self,
            "policy_version",
            require_nonblank_text(self.policy_version, "policy_version"),
        )

    @property
    def test_only(self) -> bool:
        return self.TEST_ONLY


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
    overdue_at: datetime | None = None
    resolution_outcome: ResolutionOutcome | None = None
    action_history: tuple[EventAction, ...] = ()
    priority_history: tuple[EventPriorityHistoryEntry, ...] = ()
    schema_version: str = "1.0"
    episode_policy_version: str = "synthetic_event_episode_v1"
    episode_policy_test_only: bool = True
    resident_memory_version: int | None = None
    resident_memory_entry_ids: tuple[str, ...] = ()

    @property
    def overdue(self) -> bool:
        """Compatibility view; the timestamp is the auditable source of truth."""
        return self.overdue_at is not None

    @property
    def latest_recorded_at(self) -> datetime:
        """Latest timestamp across signals, priority changes, and actions."""
        timestamps = [self.created_at, self.last_signal_at]
        timestamps.extend(action.occurred_at for action in self.action_history)
        timestamps.extend(
            change.changed_at for change in self.priority_history
        )
        if self.overdue_at is not None:
            timestamps.append(self.overdue_at)
        return max(timestamps)


class EventStore:
    """Groups related synthetic signals and enforces the caregiver lifecycle."""

    def __init__(
        self,
        quiet_gap: timedelta | None = None,
        *,
        policy: SyntheticEventEpisodePolicy | None = None,
    ) -> None:
        if quiet_gap is not None and policy is not None:
            raise ValueError("provide quiet_gap or policy, not both")
        if policy is None:
            policy = SyntheticEventEpisodePolicy(
                quiet_gap=(
                    timedelta(minutes=5)
                    if quiet_gap is None
                    else quiet_gap
                ),
            )
        elif not isinstance(policy, SyntheticEventEpisodePolicy):
            raise ValueError("policy must be a SyntheticEventEpisodePolicy")
        self.policy = policy
        self.quiet_gap = policy.quiet_gap
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
        actor_id: str = SYSTEM_EVENT_ACTOR_ID,
        monitoring_snapshot: MonitoringSnapshot | None = None,
        resident_memory: ResidentMemory | None = None,
    ) -> MonitoringEvent:
        resident_id = require_nonblank_text(resident_id, "resident_id")
        room_id = require_nonblank_text(room_id, "room_id")
        objective_family = require_nonblank_text(
            objective_family,
            "objective_family",
        )
        headline = require_nonblank_text(headline, "headline")
        priority = coerce_enum(priority, EventPriority, "priority")
        observed_at = require_aware_datetime(observed_at, "observed_at")
        actor_id = require_nonblank_text(actor_id, "actor_id")
        if monitoring_snapshot is not None:
            if not isinstance(monitoring_snapshot, MonitoringSnapshot):
                raise ValueError(
                    "monitoring_snapshot must be a MonitoringSnapshot"
                )
            if (
                monitoring_snapshot.state != MonitoringState.ACTIVE
                or not monitoring_snapshot.resident_measurements_allowed
            ):
                raise ValueError(
                    "resident-specific event creation requires active monitoring"
                )
        resident_memory_version, resident_memory_entry_ids = (
            self._memory_references(resident_id, resident_memory)
        )
        related = self._related_events(
            resident_id,
            room_id,
            objective_family,
        )
        active = related[-1] if related else None
        if active is not None:
            elapsed = observed_at - active.last_signal_at
            latest_related_history_at = max(
                event.latest_recorded_at for event in related
            )
            history_elapsed = observed_at - latest_related_history_at
            if elapsed < timedelta(0):
                raise ValueError("observed_at cannot precede the latest related signal")
            if history_elapsed < timedelta(0):
                raise ValueError("observed_at cannot precede related event history")
        if (
            active is not None
            and active.status != EventStatus.RESOLVED
            and elapsed <= self.quiet_gap
        ):
            priority_order = (
                EventPriority.WATCH,
                EventPriority.HIGH,
                EventPriority.CRITICAL,
            )
            effective_priority = max(
                active.priority,
                priority,
                key=priority_order.index,
            )
            priority_history = active.priority_history
            if effective_priority != active.priority:
                priority_history += (
                    EventPriorityHistoryEntry(
                        previous_priority=active.priority,
                        priority=effective_priority,
                        actor_id=actor_id,
                        changed_at=observed_at,
                    ),
                )
            updated = replace(
                active,
                last_signal_at=observed_at,
                signal_count=active.signal_count + 1,
                priority=effective_priority,
                priority_history=priority_history,
            )
            self._events[updated.event_id] = updated
            return updated

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
            action_history=(
                EventAction(
                    action=EventActionType.OPENED,
                    actor_id=actor_id,
                    occurred_at=observed_at,
                    previous_status=EventStatus.DETECTED,
                    status=EventStatus.OPEN,
                ),
            ),
            priority_history=(
                EventPriorityHistoryEntry(
                    previous_priority=None,
                    priority=priority,
                    actor_id=actor_id,
                    changed_at=observed_at,
                ),
            ),
            episode_policy_version=self.policy.policy_version,
            episode_policy_test_only=self.policy.test_only,
            resident_memory_version=resident_memory_version,
            resident_memory_entry_ids=resident_memory_entry_ids,
        )
        self._events[event_id] = event
        return event

    def get(self, event_id: str) -> MonitoringEvent:
        event_id = require_nonblank_text(event_id, "event_id")
        try:
            return self._events[event_id]
        except KeyError as exc:
            raise KeyError(f"Unknown event: {event_id}") from exc

    def acknowledge(
        self,
        event_id: str,
        *,
        actor_id: str,
        at: datetime,
    ) -> MonitoringEvent:
        return self._transition(
            event_id,
            EventStatus.OPEN,
            EventStatus.ACKNOWLEDGED,
            action=EventActionType.ACKNOWLEDGED,
            actor_id=actor_id,
            at=at,
        )

    def check(
        self,
        event_id: str,
        *,
        actor_id: str,
        at: datetime,
    ) -> MonitoringEvent:
        return self._transition(
            event_id,
            EventStatus.ACKNOWLEDGED,
            EventStatus.CHECKED,
            action=EventActionType.CHECKED,
            actor_id=actor_id,
            at=at,
        )

    def resolve(
        self,
        event_id: str,
        outcome: ResolutionOutcome,
        *,
        actor_id: str,
        at: datetime,
    ) -> MonitoringEvent:
        outcome = coerce_enum(outcome, ResolutionOutcome, "outcome")
        return self._transition(
            event_id,
            EventStatus.CHECKED,
            EventStatus.RESOLVED,
            action=EventActionType.RESOLVED,
            actor_id=actor_id,
            at=at,
            resolution_outcome=outcome,
        )

    def mark_overdue(
        self,
        event_id: str,
        *,
        at: datetime,
        actor_id: str = SYSTEM_OVERDUE_ACTOR_ID,
    ) -> MonitoringEvent:
        at = require_aware_datetime(at, "at")
        event = self.get(event_id)
        if event.priority == EventPriority.WATCH:
            raise ValueError("watch events do not use overdue escalation")
        if event.status != EventStatus.OPEN:
            raise ValueError("only unacknowledged open events become overdue")
        if event.overdue_at is not None:
            raise ValueError("event is already overdue")
        if at <= event.created_at:
            raise ValueError("overdue time must follow event creation")
        latest_recorded_at = max(
            event.last_signal_at,
            event.action_history[-1].occurred_at,
        )
        if at < latest_recorded_at:
            raise ValueError("overdue timestamp cannot precede event history")
        actor_id = require_nonblank_text(actor_id, "actor_id")
        overdue = replace(
            event,
            overdue_at=at,
            action_history=event.action_history
            + (
                EventAction(
                    action=EventActionType.MARKED_OVERDUE,
                    actor_id=actor_id,
                    occurred_at=at,
                    previous_status=event.status,
                    status=event.status,
                ),
            ),
        )
        self._events[overdue.event_id] = overdue
        return overdue

    def _transition(
        self,
        event_id: str,
        expected: EventStatus,
        target: EventStatus,
        *,
        action: EventActionType,
        actor_id: str,
        at: datetime,
        resolution_outcome: ResolutionOutcome | None = None,
    ) -> MonitoringEvent:
        actor_id = require_nonblank_text(actor_id, "actor_id")
        at = require_aware_datetime(at, "at")
        event = self.get(event_id)
        if event.status != expected:
            raise ValueError(
                f"Cannot move event {event_id} from {event.status} to {target}"
            )
        latest_recorded_at = max(
            event.last_signal_at,
            event.action_history[-1].occurred_at,
        )
        if at < latest_recorded_at:
            raise ValueError("action timestamp cannot precede event history")
        transitioned = replace(
            event,
            status=target,
            resolution_outcome=resolution_outcome,
            action_history=event.action_history
            + (
                EventAction(
                    action=action,
                    actor_id=actor_id,
                    occurred_at=at,
                    previous_status=expected,
                    status=target,
                    resolution_outcome=resolution_outcome,
                ),
            ),
        )
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

    @staticmethod
    def _memory_references(
        resident_id: str,
        resident_memory: ResidentMemory | None,
    ) -> tuple[int | None, tuple[str, ...]]:
        if resident_memory is None:
            return None, ()
        try:
            memory_resident_id = require_nonblank_text(
                resident_memory.resident_id,
                "resident_memory.resident_id",
            )
            version = resident_memory.version
            active_entries = resident_memory.active_entries
        except AttributeError as exc:
            raise ValueError("resident_memory must be a ResidentMemory") from exc
        if memory_resident_id != resident_id:
            raise ValueError("resident_memory must belong to the event resident")
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            raise ValueError("resident_memory.version must be a nonnegative integer")
        if not isinstance(active_entries, tuple):
            raise ValueError("resident_memory.active_entries must be a tuple")
        entry_ids = tuple(
            require_nonblank_text(entry.entry_id, "memory entry_id")
            for entry in active_entries
        )
        return version, entry_ids
