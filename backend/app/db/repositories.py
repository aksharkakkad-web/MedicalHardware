"""Tenant-scoped persistence adapters for product domain records."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, update
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
    EventPriorityHistoryRow,
    FeedbackRecordRow,
    MonitoringEventRow,
    ResidentMemoryEntryRow,
    ResidentMemorySnapshotRow,
    ResidentRow,
    RoomResidentAssignmentRow,
    RoomRow,
)
from backend.app.domain.events import MonitoringEvent
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


@dataclass(frozen=True)
class ResidentRecord:
    resident_id: str
    display_label: str
    room_id: str
    room_label: str
    assignment_status: str


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
        self._session.flush()
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
        return event_from_rows(event_row, actions, priorities)

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
