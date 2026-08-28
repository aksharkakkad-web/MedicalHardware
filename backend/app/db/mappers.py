"""Explicit mappings between immutable domain records and SQLAlchemy rows."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from backend.app.db.models import (
    EventActionRow,
    EventPriorityHistoryRow,
    FeedbackRecordRow,
    MonitoringEventRow,
    ResidentMemoryEntryRow,
    ResidentMemorySnapshotRow,
)
from backend.app.domain.events import (
    EventAction,
    EventActionType,
    EventPriority,
    EventPriorityHistoryEntry,
    EventStatus,
    MonitoringEvent,
    ResolutionOutcome,
)
from backend.app.domain.feedback import (
    FeedbackRecord,
    LearningDecision,
    MemoryEntry,
    ResidentMemory,
)


@dataclass(frozen=True)
class EventRowBundle:
    event: MonitoringEventRow
    actions: tuple[EventActionRow, ...]
    priorities: tuple[EventPriorityHistoryRow, ...]


@dataclass(frozen=True)
class MemoryRowBundle:
    snapshot: ResidentMemorySnapshotRow
    entries: tuple[ResidentMemoryEntryRow, ...]


@dataclass(frozen=True)
class StoredEvent:
    event: MonitoringEvent
    version: int


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def event_to_rows(
    tenant_id: str,
    event: MonitoringEvent,
    version: int,
) -> EventRowBundle:
    event_row = MonitoringEventRow(
        event_id=event.event_id,
        tenant_id=tenant_id,
        episode_id=event.episode_id,
        resident_id=event.resident_id,
        room_id=event.room_id,
        objective_family=event.objective_family,
        headline=event.headline,
        priority=event.priority.value,
        status=event.status.value,
        created_at=_utc(event.created_at),
        last_signal_at=_utc(event.last_signal_at),
        signal_count=event.signal_count,
        related_event_ids=list(event.related_event_ids),
        recurrence_count=event.recurrence_count,
        overdue_at=_utc(event.overdue_at),
        resolution_outcome=(
            None
            if event.resolution_outcome is None
            else event.resolution_outcome.value
        ),
        episode_policy_version=event.episode_policy_version,
        episode_policy_test_only=event.episode_policy_test_only,
        resident_memory_version=event.resident_memory_version,
        resident_memory_entry_ids=list(event.resident_memory_entry_ids),
        version=version,
    )
    action_rows = tuple(
        EventActionRow(
            tenant_id=tenant_id,
            event_id=event.event_id,
            sequence=sequence,
            action=action.action.value,
            actor_id=action.actor_id,
            occurred_at=_utc(action.occurred_at),
            previous_status=action.previous_status.value,
            status=action.status.value,
            resolution_outcome=(
                None
                if action.resolution_outcome is None
                else action.resolution_outcome.value
            ),
        )
        for sequence, action in enumerate(event.action_history, start=1)
    )
    priority_rows = tuple(
        EventPriorityHistoryRow(
            tenant_id=tenant_id,
            event_id=event.event_id,
            sequence=sequence,
            previous_priority=(
                None
                if item.previous_priority is None
                else item.previous_priority.value
            ),
            priority=item.priority.value,
            actor_id=item.actor_id,
            changed_at=_utc(item.changed_at),
        )
        for sequence, item in enumerate(event.priority_history, start=1)
    )
    return EventRowBundle(event_row, action_rows, priority_rows)


def event_from_rows(
    event_row: MonitoringEventRow,
    action_rows: Iterable[EventActionRow],
    priority_rows: Iterable[EventPriorityHistoryRow],
) -> StoredEvent:
    actions = tuple(
        EventAction(
            action=EventActionType(row.action),
            actor_id=row.actor_id,
            occurred_at=_utc(row.occurred_at),
            previous_status=EventStatus(row.previous_status),
            status=EventStatus(row.status),
            resolution_outcome=(
                None
                if row.resolution_outcome is None
                else ResolutionOutcome(row.resolution_outcome)
            ),
        )
        for row in sorted(action_rows, key=lambda item: item.sequence)
    )
    priorities = tuple(
        EventPriorityHistoryEntry(
            previous_priority=(
                None
                if row.previous_priority is None
                else EventPriority(row.previous_priority)
            ),
            priority=EventPriority(row.priority),
            actor_id=row.actor_id,
            changed_at=_utc(row.changed_at),
        )
        for row in sorted(priority_rows, key=lambda item: item.sequence)
    )
    event = MonitoringEvent(
        event_id=event_row.event_id,
        episode_id=event_row.episode_id,
        resident_id=event_row.resident_id,
        room_id=event_row.room_id,
        objective_family=event_row.objective_family,
        headline=event_row.headline,
        priority=EventPriority(event_row.priority),
        status=EventStatus(event_row.status),
        created_at=_utc(event_row.created_at),
        last_signal_at=_utc(event_row.last_signal_at),
        signal_count=event_row.signal_count,
        related_event_ids=tuple(event_row.related_event_ids),
        recurrence_count=event_row.recurrence_count,
        overdue_at=_utc(event_row.overdue_at),
        resolution_outcome=(
            None
            if event_row.resolution_outcome is None
            else ResolutionOutcome(event_row.resolution_outcome)
        ),
        action_history=actions,
        priority_history=priorities,
        episode_policy_version=event_row.episode_policy_version,
        episode_policy_test_only=event_row.episode_policy_test_only,
        resident_memory_version=event_row.resident_memory_version,
        resident_memory_entry_ids=tuple(event_row.resident_memory_entry_ids),
    )
    return StoredEvent(event, event_row.version)


def memory_to_rows(
    tenant_id: str,
    memory: ResidentMemory,
    created_at: datetime,
) -> MemoryRowBundle:
    snapshot = ResidentMemorySnapshotRow(
        tenant_id=tenant_id,
        resident_id=memory.resident_id,
        version=memory.version,
        created_at=_utc(created_at),
    )
    entries = tuple(
        ResidentMemoryEntryRow(
            entry_id=entry.entry_id,
            tenant_id=tenant_id,
            resident_id=memory.resident_id,
            memory_version=memory.version,
            description=entry.description,
            source_kind=entry.source_kind,
            source_feedback_id=entry.source_feedback_id,
            supersedes_entry_id=entry.supersedes_entry_id,
            status=entry.status,
            created_by=entry.created_by,
            created_at=_utc(entry.created_at),
            retired_by=entry.retired_by,
            retired_at=_utc(entry.retired_at),
            retirement_reason=entry.retirement_reason,
        )
        for entry in memory.entries
    )
    return MemoryRowBundle(snapshot, entries)


def memory_from_rows(
    snapshot_row: ResidentMemorySnapshotRow,
    entry_rows: Iterable[ResidentMemoryEntryRow],
) -> ResidentMemory:
    entries = tuple(
        MemoryEntry(
            entry_id=row.entry_id,
            description=row.description,
            source_kind=row.source_kind,
            source_feedback_id=row.source_feedback_id,
            supersedes_entry_id=row.supersedes_entry_id,
            status=row.status,
            created_by=row.created_by,
            created_at=_utc(row.created_at),
            retired_by=row.retired_by,
            retired_at=_utc(row.retired_at),
            retirement_reason=row.retirement_reason,
        )
        for row in sorted(entry_rows, key=lambda item: item.memory_entry_row_id or 0)
    )
    return ResidentMemory(snapshot_row.resident_id, snapshot_row.version, entries)


def feedback_to_row(
    tenant_id: str,
    decision: LearningDecision,
) -> FeedbackRecordRow:
    feedback = decision.feedback
    return FeedbackRecordRow(
        feedback_id=feedback.feedback_id,
        tenant_id=tenant_id,
        event_id=feedback.event_id,
        resident_id=feedback.resident_id,
        actor_id=feedback.actor_id,
        outcome=feedback.outcome.value,
        actual_event_label=feedback.actual_event_label,
        routine=feedback.routine,
        created_at=_utc(feedback.created_at),
        memory_updated=decision.memory_updated,
        baseline_window_eligible=decision.baseline_window_eligible,
        global_label_recorded=decision.global_label_recorded,
    )


def feedback_from_row(
    row: FeedbackRecordRow,
    memory: ResidentMemory,
) -> LearningDecision:
    feedback = FeedbackRecord(
        feedback_id=row.feedback_id,
        event_id=row.event_id,
        resident_id=row.resident_id,
        actor_id=row.actor_id,
        outcome=ResolutionOutcome(row.outcome),
        actual_event_label=row.actual_event_label,
        routine=row.routine,
        created_at=_utc(row.created_at),
    )
    return LearningDecision(
        feedback=feedback,
        memory=memory,
        memory_updated=row.memory_updated,
        baseline_window_eligible=row.baseline_window_eligible,
        global_label_recorded=row.global_label_recorded,
    )
