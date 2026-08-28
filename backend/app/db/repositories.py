"""Tenant-scoped persistence adapters for product domain records."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db.mappers import (
    StoredEvent,
    event_from_rows,
    event_to_rows,
    feedback_from_row,
    feedback_to_row,
    memory_from_rows,
    memory_to_rows,
)
from backend.app.db.models import (
    EventActionRow,
    EventBridgeRecordRow,
    EventPriorityHistoryRow,
    FeedbackRecordRow,
    MonitoringEventRow,
    ResidentMemoryEntryRow,
    ResidentMemorySnapshotRow,
    ResidentRow,
    RoomResidentAssignmentRow,
    RoomRow,
)
from backend.app.domain.events import EventPriority, EventStatus, MonitoringEvent
from backend.app.domain.feedback import LearningDecision, ResidentMemory
from backend.app.services.errors import ConcurrentUpdateError, NotFoundError


def _is_feedback_event_conflict(error: IntegrityError) -> bool:
    constraint_name = getattr(
        getattr(error.orig, "diag", None),
        "constraint_name",
        None,
    )
    if constraint_name == "feedback_records_tenant_id_event_id_key":
        return True
    return (
        "unique constraint failed: feedback_records.tenant_id, "
        "feedback_records.event_id"
    ) in str(error.orig).casefold()


def _same_bridge_row(
    left: EventBridgeRecordRow,
    right: EventBridgeRecordRow,
) -> bool:
    for column in EventBridgeRecordRow.__table__.columns:
        if column.name == "event_bridge_record_id":
            continue
        left_value = getattr(left, column.name)
        right_value = getattr(right, column.name)
        if isinstance(left_value, datetime) and isinstance(right_value, datetime):
            if left_value.tzinfo is None:
                left_value = left_value.replace(tzinfo=timezone.utc)
            if right_value.tzinfo is None:
                right_value = right_value.replace(tzinfo=timezone.utc)
            left_value = left_value.astimezone(timezone.utc)
            right_value = right_value.astimezone(timezone.utc)
        if left_value != right_value:
            return False
    return True


@dataclass(frozen=True)
class ResidentRecord:
    resident_id: str
    display_label: str
    room_id: str
    room_label: str
    assignment_status: str


@dataclass(frozen=True)
class EventQueuePosition:
    resolved: bool
    priority: EventPriority
    overdue: bool
    last_signal_at: datetime
    created_at: datetime
    event_id: str


@dataclass(frozen=True)
class EventQueuePage:
    items: tuple[StoredEvent, ...]
    next_position: EventQueuePosition | None
    total_items: int


class ResidentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, tenant_id: str) -> list[ResidentRecord]:
        statement = (
            select(ResidentRow, RoomResidentAssignmentRow, RoomRow)
            .join(
                RoomResidentAssignmentRow,
                RoomResidentAssignmentRow.resident_id == ResidentRow.resident_id,
            )
            .join(RoomRow, RoomRow.room_id == RoomResidentAssignmentRow.room_id)
            .where(
                ResidentRow.tenant_id == tenant_id,
                RoomResidentAssignmentRow.tenant_id == tenant_id,
                RoomRow.tenant_id == tenant_id,
                RoomResidentAssignmentRow.status == "active",
            )
            .order_by(ResidentRow.resident_id)
        )
        return [self._to_record(*rows) for rows in self._session.execute(statement)]

    def find(self, tenant_id: str, resident_id: str) -> ResidentRecord | None:
        statement = (
            select(ResidentRow, RoomResidentAssignmentRow, RoomRow)
            .join(
                RoomResidentAssignmentRow,
                RoomResidentAssignmentRow.resident_id == ResidentRow.resident_id,
            )
            .join(RoomRow, RoomRow.room_id == RoomResidentAssignmentRow.room_id)
            .where(
                ResidentRow.resident_id == resident_id,
                ResidentRow.tenant_id == tenant_id,
                RoomResidentAssignmentRow.tenant_id == tenant_id,
                RoomRow.tenant_id == tenant_id,
                RoomResidentAssignmentRow.status == "active",
            )
        )
        rows = self._session.execute(statement).one_or_none()
        return None if rows is None else self._to_record(*rows)

    @staticmethod
    def _to_record(
        resident: ResidentRow,
        assignment: RoomResidentAssignmentRow,
        room: RoomRow,
    ) -> ResidentRecord:
        return ResidentRecord(
            resident_id=resident.resident_id,
            display_label=resident.display_label,
            room_id=room.room_id,
            room_label=room.label,
            assignment_status=assignment.status,
        )


class EventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_resident(
        self,
        tenant_id: str,
        resident_id: str,
    ) -> list[StoredEvent]:
        statement = (
            select(MonitoringEventRow)
            .where(
                MonitoringEventRow.tenant_id == tenant_id,
                MonitoringEventRow.resident_id == resident_id,
            )
            .order_by(MonitoringEventRow.created_at.desc())
        )
        return [
            self._hydrate(tenant_id, row)
            for row in self._session.scalars(statement)
        ]

    def list_for_tenant(
        self,
        tenant_id: str,
        *,
        statuses: Sequence[EventStatus] = (),
        priorities: Sequence[EventPriority] = (),
        resident_id: str | None = None,
        room_id: str | None = None,
        limit: int,
        after: EventQueuePosition | None = None,
    ) -> EventQueuePage:
        filters = [MonitoringEventRow.tenant_id == tenant_id]
        if statuses:
            filters.append(
                MonitoringEventRow.status.in_(status.value for status in statuses)
            )
        if priorities:
            filters.append(
                MonitoringEventRow.priority.in_(
                    priority.value for priority in priorities
                )
            )
        if resident_id is not None:
            filters.append(MonitoringEventRow.resident_id == resident_id)
        if room_id is not None:
            filters.append(MonitoringEventRow.room_id == room_id)

        total_items = int(
            self._session.scalar(
                select(func.count())
                .select_from(MonitoringEventRow)
                .where(*filters)
            )
            or 0
        )
        resolved_rank = case(
            (MonitoringEventRow.status == EventStatus.RESOLVED.value, 1),
            else_=0,
        )
        priority_rank = case(
            (MonitoringEventRow.priority == EventPriority.CRITICAL.value, 0),
            (MonitoringEventRow.priority == EventPriority.HIGH.value, 1),
            else_=2,
        )
        overdue_rank = case(
            (MonitoringEventRow.overdue_at.is_not(None), 0),
            else_=1,
        )

        page_filters = list(filters)
        if after is not None:
            after_resolved = int(after.resolved)
            after_priority = {
                EventPriority.CRITICAL: 0,
                EventPriority.HIGH: 1,
                EventPriority.WATCH: 2,
            }[after.priority]
            after_overdue = 0 if after.overdue else 1
            page_filters.append(
                or_(
                    resolved_rank > after_resolved,
                    and_(
                        resolved_rank == after_resolved,
                        priority_rank > after_priority,
                    ),
                    and_(
                        resolved_rank == after_resolved,
                        priority_rank == after_priority,
                        overdue_rank > after_overdue,
                    ),
                    and_(
                        resolved_rank == after_resolved,
                        priority_rank == after_priority,
                        overdue_rank == after_overdue,
                        MonitoringEventRow.last_signal_at
                        < after.last_signal_at,
                    ),
                    and_(
                        resolved_rank == after_resolved,
                        priority_rank == after_priority,
                        overdue_rank == after_overdue,
                        MonitoringEventRow.last_signal_at
                        == after.last_signal_at,
                        MonitoringEventRow.created_at < after.created_at,
                    ),
                    and_(
                        resolved_rank == after_resolved,
                        priority_rank == after_priority,
                        overdue_rank == after_overdue,
                        MonitoringEventRow.last_signal_at
                        == after.last_signal_at,
                        MonitoringEventRow.created_at == after.created_at,
                        MonitoringEventRow.event_id > after.event_id,
                    ),
                )
            )

        rows = self._session.scalars(
            select(MonitoringEventRow)
            .where(*page_filters)
            .order_by(
                resolved_rank,
                priority_rank,
                overdue_rank,
                MonitoringEventRow.last_signal_at.desc(),
                MonitoringEventRow.created_at.desc(),
                MonitoringEventRow.event_id,
            )
            .limit(limit + 1)
        ).all()
        has_more = len(rows) > limit
        page_rows = rows[:limit]
        items = self._hydrate_many(tenant_id, page_rows)
        next_position = (
            self._queue_position(page_rows[-1]) if has_more else None
        )
        return EventQueuePage(
            items=items,
            next_position=next_position,
            total_items=total_items,
        )

    def find(self, tenant_id: str, event_id: str) -> StoredEvent | None:
        event_row = self._session.scalar(
            select(MonitoringEventRow).where(
                MonitoringEventRow.tenant_id == tenant_id,
                MonitoringEventRow.event_id == event_id,
            )
        )
        return None if event_row is None else self._hydrate(tenant_id, event_row)

    def get(self, tenant_id: str, event_id: str) -> StoredEvent:
        stored = self.find(tenant_id, event_id)
        if stored is None:
            raise NotFoundError()
        return stored

    def save(
        self,
        tenant_id: str,
        event: MonitoringEvent,
        expected_version: int,
    ) -> StoredEvent:
        bundle = event_to_rows(tenant_id, event, expected_version + 1)
        try:
            with self._session.begin_nested():
                existing_bridges = {
                    row.idempotency_key: row
                    for row in self._session.scalars(
                        select(EventBridgeRecordRow).where(
                            EventBridgeRecordRow.tenant_id == tenant_id,
                            EventBridgeRecordRow.idempotency_key.in_(
                                bridge.idempotency_key for bridge in bundle.bridges
                            ),
                        )
                    )
                }
                for bridge in bundle.bridges:
                    existing_bridge = existing_bridges.get(bridge.idempotency_key)
                    if existing_bridge is not None and not _same_bridge_row(
                        existing_bridge,
                        bridge,
                    ):
                        raise ConcurrentUpdateError()

                if expected_version == 0:
                    existing_event = self._session.scalar(
                        select(MonitoringEventRow).where(
                            MonitoringEventRow.event_id == event.event_id,
                            MonitoringEventRow.tenant_id == tenant_id,
                        )
                    )
                    if existing_event is not None:
                        raise ConcurrentUpdateError()
                    self._session.add(bundle.event)
                    self._session.flush()
                    action_sequence = priority_sequence = 0
                else:
                    values = {
                        column.name: getattr(bundle.event, column.name)
                        for column in MonitoringEventRow.__table__.columns
                        if column.name not in {"event_id", "tenant_id", "version"}
                    }
                    values["version"] = expected_version + 1
                    result = self._session.execute(
                        update(MonitoringEventRow)
                        .where(
                            MonitoringEventRow.event_id == event.event_id,
                            MonitoringEventRow.tenant_id == tenant_id,
                            MonitoringEventRow.version == expected_version,
                        )
                        .values(**values)
                    )
                    if result.rowcount == 0:
                        raise ConcurrentUpdateError()
                    action_sequence = self._latest_sequence(
                        EventActionRow,
                        EventActionRow.sequence,
                        tenant_id,
                        event.event_id,
                    )
                    priority_sequence = self._latest_sequence(
                        EventPriorityHistoryRow,
                        EventPriorityHistoryRow.sequence,
                        tenant_id,
                        event.event_id,
                    )
                self._session.add_all(
                    row for row in bundle.actions if row.sequence > action_sequence
                )
                self._session.add_all(
                    row for row in bundle.priorities if row.sequence > priority_sequence
                )
                self._session.add_all(
                    bridge
                    for bridge in bundle.bridges
                    if bridge.idempotency_key not in existing_bridges
                )
                self._session.flush()
        except IntegrityError as exc:
            raise ConcurrentUpdateError() from exc
        return self.get(tenant_id, event.event_id)

    def _hydrate(
        self,
        tenant_id: str,
        event_row: MonitoringEventRow,
    ) -> StoredEvent:
        actions = self._session.scalars(
            select(EventActionRow)
            .where(
                EventActionRow.tenant_id == tenant_id,
                EventActionRow.event_id == event_row.event_id,
            )
            .order_by(EventActionRow.sequence)
        ).all()
        priorities = self._session.scalars(
            select(EventPriorityHistoryRow)
            .where(
                EventPriorityHistoryRow.tenant_id == tenant_id,
                EventPriorityHistoryRow.event_id == event_row.event_id,
            )
            .order_by(EventPriorityHistoryRow.sequence)
        ).all()
        bridges = self._session.scalars(
            select(EventBridgeRecordRow)
            .where(
                EventBridgeRecordRow.tenant_id == tenant_id,
                EventBridgeRecordRow.event_id == event_row.event_id,
            )
            .order_by(EventBridgeRecordRow.event_bridge_record_id)
        ).all()
        return event_from_rows(event_row, actions, priorities, bridges)

    def _hydrate_many(
        self,
        tenant_id: str,
        event_rows: Sequence[MonitoringEventRow],
    ) -> tuple[StoredEvent, ...]:
        if not event_rows:
            return ()
        event_ids = [row.event_id for row in event_rows]
        actions = self._session.scalars(
            select(EventActionRow)
            .where(
                EventActionRow.tenant_id == tenant_id,
                EventActionRow.event_id.in_(event_ids),
            )
            .order_by(EventActionRow.event_id, EventActionRow.sequence)
        ).all()
        priorities = self._session.scalars(
            select(EventPriorityHistoryRow)
            .where(
                EventPriorityHistoryRow.tenant_id == tenant_id,
                EventPriorityHistoryRow.event_id.in_(event_ids),
            )
            .order_by(
                EventPriorityHistoryRow.event_id,
                EventPriorityHistoryRow.sequence,
            )
        ).all()
        bridges = self._session.scalars(
            select(EventBridgeRecordRow)
            .where(
                EventBridgeRecordRow.tenant_id == tenant_id,
                EventBridgeRecordRow.event_id.in_(event_ids),
            )
            .order_by(
                EventBridgeRecordRow.event_id,
                EventBridgeRecordRow.event_bridge_record_id,
            )
        ).all()
        actions_by_event: dict[str, list[EventActionRow]] = {
            event_id: [] for event_id in event_ids
        }
        priorities_by_event: dict[str, list[EventPriorityHistoryRow]] = {
            event_id: [] for event_id in event_ids
        }
        bridges_by_event: dict[str, list[EventBridgeRecordRow]] = {
            event_id: [] for event_id in event_ids
        }
        for action in actions:
            actions_by_event[action.event_id].append(action)
        for priority in priorities:
            priorities_by_event[priority.event_id].append(priority)
        for bridge in bridges:
            bridges_by_event[bridge.event_id].append(bridge)
        return tuple(
            event_from_rows(
                event_row,
                actions_by_event[event_row.event_id],
                priorities_by_event[event_row.event_id],
                bridges_by_event[event_row.event_id],
            )
            for event_row in event_rows
        )

    @staticmethod
    def _queue_position(event_row: MonitoringEventRow) -> EventQueuePosition:
        def utc(value: datetime) -> datetime:
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)

        return EventQueuePosition(
            resolved=event_row.status == EventStatus.RESOLVED.value,
            priority=EventPriority(event_row.priority),
            overdue=event_row.overdue_at is not None,
            last_signal_at=utc(event_row.last_signal_at),
            created_at=utc(event_row.created_at),
            event_id=event_row.event_id,
        )

    def _latest_sequence(
        self,
        row_type: type[EventActionRow] | type[EventPriorityHistoryRow],
        sequence_column: object,
        tenant_id: str,
        event_id: str,
    ) -> int:
        return self._session.scalar(
            select(func.coalesce(func.max(sequence_column), 0)).where(
                row_type.tenant_id == tenant_id,
                row_type.event_id == event_id,
            )
        )


class FeedbackRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_event(
        self,
        tenant_id: str,
        event_id: str,
    ) -> LearningDecision | None:
        row = self._session.scalar(
            select(FeedbackRecordRow).where(
                FeedbackRecordRow.tenant_id == tenant_id,
                FeedbackRecordRow.event_id == event_id,
            )
        )
        if row is None:
            return None
        memory = self.current_memory(tenant_id, row.resident_id)
        return feedback_from_row(row, memory)

    def current_memory(
        self,
        tenant_id: str,
        resident_id: str,
    ) -> ResidentMemory:
        snapshot = self._session.scalar(
            select(ResidentMemorySnapshotRow)
            .where(
                ResidentMemorySnapshotRow.tenant_id == tenant_id,
                ResidentMemorySnapshotRow.resident_id == resident_id,
            )
            .order_by(ResidentMemorySnapshotRow.version.desc())
            .limit(1)
        )
        if snapshot is None:
            return ResidentMemory(resident_id, 0, ())
        entries = self._session.scalars(
            select(ResidentMemoryEntryRow)
            .where(
                ResidentMemoryEntryRow.tenant_id == tenant_id,
                ResidentMemoryEntryRow.resident_id == resident_id,
                ResidentMemoryEntryRow.memory_version == snapshot.version,
            )
            .order_by(ResidentMemoryEntryRow.memory_entry_row_id)
        ).all()
        return memory_from_rows(snapshot, entries)

    def memory_timeline(
        self,
        tenant_id: str,
        resident_id: str,
    ) -> list[ResidentMemory]:
        snapshots = self._session.scalars(
            select(ResidentMemorySnapshotRow)
            .where(
                ResidentMemorySnapshotRow.tenant_id == tenant_id,
                ResidentMemorySnapshotRow.resident_id == resident_id,
            )
            .order_by(ResidentMemorySnapshotRow.version)
        ).all()
        history: list[ResidentMemory] = []
        for snapshot in snapshots:
            entries = self._session.scalars(
                select(ResidentMemoryEntryRow)
                .where(
                    ResidentMemoryEntryRow.tenant_id == tenant_id,
                    ResidentMemoryEntryRow.resident_id == resident_id,
                    ResidentMemoryEntryRow.memory_version == snapshot.version,
                )
                .order_by(ResidentMemoryEntryRow.memory_entry_row_id)
            ).all()
            history.append(memory_from_rows(snapshot, entries))
        return history

    def save_memory(
        self,
        tenant_id: str,
        memory: ResidentMemory,
        *,
        expected_version: int,
        changed_at: datetime,
    ) -> ResidentMemory:
        resident_exists = self._session.scalar(
            select(ResidentRow.resident_id).where(
                ResidentRow.tenant_id == tenant_id,
                ResidentRow.resident_id == memory.resident_id,
            )
        )
        if resident_exists is None:
            raise NotFoundError()
        current = self.current_memory(tenant_id, memory.resident_id)
        if (
            current.version != expected_version
            or memory.version != expected_version + 1
        ):
            raise ConcurrentUpdateError()

        bundle = memory_to_rows(tenant_id, memory, changed_at)
        self._session.add(bundle.snapshot)
        try:
            self._session.flush((bundle.snapshot,))
        except IntegrityError as error:
            raise ConcurrentUpdateError() from error
        self._session.add_all(bundle.entries)
        self._session.flush()
        return self.current_memory(tenant_id, memory.resident_id)

    def save_decision(
        self,
        tenant_id: str,
        decision: LearningDecision,
    ) -> None:
        existing_snapshot = self._session.scalar(
            select(ResidentMemorySnapshotRow).where(
                ResidentMemorySnapshotRow.tenant_id == tenant_id,
                ResidentMemorySnapshotRow.resident_id == decision.memory.resident_id,
                ResidentMemorySnapshotRow.version == decision.memory.version,
            )
        )
        if existing_snapshot is not None and decision.memory_updated:
            raise ConcurrentUpdateError()

        feedback_row = feedback_to_row(tenant_id, decision)
        self._session.add(feedback_row)
        try:
            self._session.flush((feedback_row,))
        except IntegrityError as error:
            if _is_feedback_event_conflict(error):
                raise ConcurrentUpdateError() from error
            raise
        if existing_snapshot is None:
            bundle = memory_to_rows(
                tenant_id,
                decision.memory,
                decision.feedback.created_at,
            )
            self._session.add(bundle.snapshot)
            # Flush the snapshot alone so only its optimistic version collision
            # is translated; entry integrity failures remain internal errors.
            try:
                self._session.flush((bundle.snapshot,))
            except IntegrityError as error:
                raise ConcurrentUpdateError() from error
            self._session.add_all(bundle.entries)
        self._session.flush()
