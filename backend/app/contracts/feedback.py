from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator

from backend.app.contracts.common import ContractModel, UTCDateTime
from backend.app.domain.events import ResolutionOutcome
from backend.app.domain.feedback import normalize_event_label


class SubmitFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actual_event_label: str
    routine: bool
    created_at: AwareDatetime

    @field_validator("actual_event_label")
    @classmethod
    def normalize_actual_event_label(cls, value: str) -> str:
        return normalize_event_label(value)


class MemoryEntryResponse(ContractModel):
    entry_id: str
    description: str
    source_feedback_id: str
    status: Literal["active", "retired"]
    created_by: str
    created_at: UTCDateTime
    retired_by: str | None
    retired_at: UTCDateTime | None
    retirement_reason: str | None


class ResidentMemoryResponse(ContractModel):
    resident_id: str
    version: int
    entries: list[MemoryEntryResponse]


class FeedbackResponse(ContractModel):
    feedback_id: str
    event_id: str
    resident_id: str
    actor_id: str
    outcome: ResolutionOutcome
    actual_event_label: str
    routine: bool
    created_at: UTCDateTime


class LearningDecisionResponse(ContractModel):
    feedback: FeedbackResponse
    memory: ResidentMemoryResponse
    memory_updated: bool
    baseline_window_eligible: bool
    global_label_recorded: bool
