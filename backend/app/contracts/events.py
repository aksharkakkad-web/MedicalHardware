from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from backend.app.contracts.common import ContractModel, RequestContractModel, UTCDateTime
from backend.app.domain.events import (
    EventActionType,
    EventPriority,
    EventStatus,
    ResolutionOutcome,
)
from backend.app.ai.analysis_contracts import (
    AnalysisState,
    AttributionScope,
    ConfidenceBand,
    Severity,
)
from backend.app.ai.client import RecommendedDisposition


class ClinicEventStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    CHECKED = "checked"
    RESOLVED = "resolved"


class EventActionRequest(RequestContractModel):
    occurred_at: UTCDateTime


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


class AnalysisPossibilityResponse(ContractModel):
    possibility_id: str
    label: str
    confidence: ConfidenceBand
    supporting_evidence_refs: list[str]
    contradicting_evidence_refs: list[str]
    missing_information: list[str]


class EventAnalysisResponse(ContractModel):
    analysis_id: str
    packet_revision: int
    state: AnalysisState
    possibilities: list[AnalysisPossibilityResponse]
    severity: Severity | None
    recommended_disposition: RecommendedDisposition | None
    attribution_scope: AttributionScope | None
    caregiver_summary: str | None
    next_step: str | None
    missing_information: list[str]
    specialist_disagreements: list[str]
    evidence_refs: list[str]
    unavailable_specialists: list[str]
    errors: list[str]
    model_id: str | None
    model_version: str | None
    skill_versions: list[str]


class ResidentAnalysisResponse(ContractModel):
    anomaly_id: str
    resident_id: str
    room_id: str
    observed_at: UTCDateTime
    analysis: EventAnalysisResponse


class ResidentAnalysisListResponse(ContractModel):
    items: list[ResidentAnalysisResponse]


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
    analysis: EventAnalysisResponse | None = None
    version: int


class EventListResponse(ContractModel):
    items: list[EventResponse]


class ClinicEventQueueResponse(ContractModel):
    items: list[EventResponse] = Field(default_factory=list)
    total_items: int = Field(ge=0)
    next_cursor: str | None

    @field_validator("next_cursor")
    @classmethod
    def require_nonblank_cursor(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("next_cursor must not be blank")
        return normalized

    @model_validator(mode="after")
    def require_total_to_cover_page(self) -> "ClinicEventQueueResponse":
        if self.total_items < len(self.items):
            raise ValueError("total_items cannot be smaller than the page")
        return self
