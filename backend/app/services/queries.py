from dataclasses import dataclass

from backend.app.contracts.events import (
    EventActionResponse,
    EventListResponse,
    EventPriorityHistoryResponse,
    EventResponse,
)
from backend.app.contracts.feedback import MemoryEntryResponse, ResidentMemoryResponse
from backend.app.contracts.residents import ResidentListResponse, ResidentSummary
from backend.app.db.mappers import StoredEvent
from backend.app.db.repositories import (
    EventRepository,
    FeedbackRepository,
    ResidentRecord,
    ResidentRepository,
)
from backend.app.domain.feedback import ResidentMemory
from backend.app.services.errors import NotFoundError


@dataclass(frozen=True)
class AccessContext:
    tenant_id: str
    actor_id: str


class ProductQueryService:
    def __init__(
        self,
        residents: ResidentRepository,
        events: EventRepository,
        feedback: FeedbackRepository,
    ) -> None:
        self._residents = residents
        self._events = events
        self._feedback = feedback

    def list_residents(self, context: AccessContext) -> ResidentListResponse:
        return ResidentListResponse(
            items=[
                self._resident_response(record)
                for record in self._residents.list(context.tenant_id)
            ]
        )

    def get_resident(
        self,
        context: AccessContext,
        resident_id: str,
    ) -> ResidentSummary:
        record = self._residents.find(context.tenant_id, resident_id)
        if record is None:
            raise NotFoundError()
        return self._resident_response(record)

    def list_resident_events(
        self,
        context: AccessContext,
        resident_id: str,
    ) -> EventListResponse:
        self.get_resident(context, resident_id)
        return EventListResponse(
            items=[
                self._event_response(stored)
                for stored in self._events.list_for_resident(
                    context.tenant_id,
                    resident_id,
                )
            ]
        )

    def get_event(
        self,
        context: AccessContext,
        event_id: str,
    ) -> EventResponse:
        return self._event_response(
            self._events.get(context.tenant_id, event_id)
        )

    def get_resident_memory(
        self,
        context: AccessContext,
        resident_id: str,
    ) -> ResidentMemoryResponse:
        self.get_resident(context, resident_id)
        return self._memory_response(
            self._feedback.current_memory(context.tenant_id, resident_id)
        )

    @staticmethod
    def _resident_response(record: ResidentRecord) -> ResidentSummary:
        return ResidentSummary.model_validate(record, from_attributes=True)

    @staticmethod
    def _event_response(stored: StoredEvent) -> EventResponse:
        event = stored.event
        return EventResponse(
            event_id=event.event_id,
            episode_id=event.episode_id,
            resident_id=event.resident_id,
            room_id=event.room_id,
            objective_family=event.objective_family,
            headline=event.headline,
            priority=event.priority,
            status=event.status,
            created_at=event.created_at,
            last_signal_at=event.last_signal_at,
            signal_count=event.signal_count,
            related_event_ids=list(event.related_event_ids),
            recurrence_count=event.recurrence_count,
            overdue_at=event.overdue_at,
            overdue=event.overdue,
            resolution_outcome=event.resolution_outcome,
            action_history=[
                EventActionResponse(
                    action=action.action,
                    actor_id=action.actor_id,
                    occurred_at=action.occurred_at,
                    previous_status=action.previous_status,
                    status=action.status,
                    resolution_outcome=action.resolution_outcome,
                )
                for action in event.action_history
            ],
            priority_history=[
                EventPriorityHistoryResponse(
                    previous_priority=item.previous_priority,
                    priority=item.priority,
                    actor_id=item.actor_id,
                    changed_at=item.changed_at,
                )
                for item in event.priority_history
            ],
            resident_memory_version=event.resident_memory_version,
            resident_memory_entry_ids=list(event.resident_memory_entry_ids),
            version=stored.version,
        )

    @staticmethod
    def _memory_response(memory: ResidentMemory) -> ResidentMemoryResponse:
        return ResidentMemoryResponse(
            resident_id=memory.resident_id,
            version=memory.version,
            entries=[
                MemoryEntryResponse(
                    entry_id=entry.entry_id,
                    description=entry.description,
                    source_feedback_id=entry.source_feedback_id,
                    status=entry.status,
                    created_by=entry.created_by,
                    created_at=entry.created_at,
                    retired_by=entry.retired_by,
                    retired_at=entry.retired_at,
                    retirement_reason=entry.retirement_reason,
                )
                for entry in memory.entries
            ],
        )
