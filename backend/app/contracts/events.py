from pydantic import AwareDatetime, BaseModel, ConfigDict

from backend.app.contracts.common import ContractModel, UTCDateTime
from backend.app.domain.events import (
    EventActionType,
    EventPriority,
    EventStatus,
    ResolutionOutcome,
)


class EventActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    occurred_at: AwareDatetime


class ResolveEventRequest(EventActionRequest):
    outcome: ResolutionOutcome


class EventActionResponse(ContractModel):
    action: EventActionType
    actor_id: str
    occurred_at: UTCDateTime
    previous_status: EventStatus
    status: EventStatus
    resolution_outcome: ResolutionOutcome | None


class EventPriorityHistoryResponse(ContractModel):
    previous_priority: EventPriority | None
    priority: EventPriority
    actor_id: str
    changed_at: UTCDateTime


class EventResponse(ContractModel):
    event_id: str
    episode_id: str
    resident_id: str
    room_id: str
    objective_family: str
    headline: str
    priority: EventPriority
    status: EventStatus
    created_at: UTCDateTime
    last_signal_at: UTCDateTime
    signal_count: int
    related_event_ids: list[str]
    recurrence_count: int
    overdue_at: UTCDateTime | None
    overdue: bool
    resolution_outcome: ResolutionOutcome | None
    action_history: list[EventActionResponse]
    priority_history: list[EventPriorityHistoryResponse]
    resident_memory_version: int | None
    resident_memory_entry_ids: list[str]
    version: int


class EventListResponse(ContractModel):
    items: list[EventResponse]
