from typing import Annotated, Literal

from pydantic import Field, StrictInt, field_validator, model_validator

from backend.app.contracts.common import ContractModel, RequestContractModel, UTCDateTime
from backend.app.domain._validation import require_nonblank_text
from backend.app.domain.events import ResolutionOutcome
from backend.app.domain.feedback import (
    MemoryContextKind,
    normalize_event_label,
    validate_memory_context,
)


ExpectedVersion = Annotated[StrictInt, Field(ge=0)]


class SubmitFeedbackRequest(RequestContractModel):
    actual_event_label: str
    routine: bool
    created_at: UTCDateTime

    @field_validator("actual_event_label")
    @classmethod
    def normalize_actual_event_label(cls, value: str) -> str:
        return normalize_event_label(value)


class MemoryEntryResponse(ContractModel):
    entry_id: str
    description: str
    source_kind: Literal["feedback", "operator"] = "feedback"
    source_feedback_id: str | None
    supersedes_entry_id: str | None = None
    status: Literal["active", "retired"]
    created_by: str
    created_at: UTCDateTime
    retired_by: str | None
    retired_at: UTCDateTime | None
    retirement_reason: str | None
    context_kind: MemoryContextKind = "general_context"
    effective_from: UTCDateTime | None = None
    effective_until: UTCDateTime | None = None
    local_time_start: str | None = None
    local_time_end: str | None = None
    recurrence_note: str | None = None
    flexibility_note: str | None = None

    @model_validator(mode="after")
    def require_consistent_provenance_and_retirement(self) -> "MemoryEntryResponse":
        validate_memory_context(
            context_kind=self.context_kind,
            effective_from=self.effective_from,
            effective_until=self.effective_until,
            local_time_start=self.local_time_start,
            local_time_end=self.local_time_end,
        )
        if self.source_kind == "feedback" and self.source_feedback_id is None:
            raise ValueError("feedback memory requires source_feedback_id")
        if self.source_kind == "operator" and self.source_feedback_id is not None:
            raise ValueError("operator memory cannot claim a feedback source")
        retirement_values = (
            self.retired_by,
            self.retired_at,
            self.retirement_reason,
        )
        if self.status == "active" and any(value is not None for value in retirement_values):
            raise ValueError("active memory cannot contain retirement metadata")
        if self.status == "retired" and any(value is None for value in retirement_values):
            raise ValueError("retired memory requires complete retirement metadata")
        return self


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


class AddMemoryEntryRequest(RequestContractModel):
    expected_version: ExpectedVersion
    description: str
    changed_at: UTCDateTime
    context_kind: MemoryContextKind = "general_context"
    effective_from: UTCDateTime | None = None
    effective_until: UTCDateTime | None = None
    local_time_start: str | None = None
    local_time_end: str | None = None
    recurrence_note: str | None = None
    flexibility_note: str | None = None

    @field_validator("description")
    @classmethod
    def require_description(cls, value: str) -> str:
        return require_nonblank_text(value, "description")

    @model_validator(mode="after")
    def require_valid_context(self) -> "AddMemoryEntryRequest":
        validate_memory_context(
            context_kind=self.context_kind,
            effective_from=self.effective_from,
            effective_until=self.effective_until,
            local_time_start=self.local_time_start,
            local_time_end=self.local_time_end,
        )
        return self


class CorrectMemoryEntryRequest(RequestContractModel):
    expected_version: ExpectedVersion
    description: str
    reason: str
    changed_at: UTCDateTime
    context_kind: MemoryContextKind = "general_context"
    effective_from: UTCDateTime | None = None
    effective_until: UTCDateTime | None = None
    local_time_start: str | None = None
    local_time_end: str | None = None
    recurrence_note: str | None = None
    flexibility_note: str | None = None

    @field_validator("description", "reason")
    @classmethod
    def require_text(cls, value: str, info: object) -> str:
        return require_nonblank_text(value, info.field_name)

    @model_validator(mode="after")
    def require_valid_context(self) -> "CorrectMemoryEntryRequest":
        validate_memory_context(
            context_kind=self.context_kind,
            effective_from=self.effective_from,
            effective_until=self.effective_until,
            local_time_start=self.local_time_start,
            local_time_end=self.local_time_end,
        )
        return self


class RetireMemoryEntryRequest(RequestContractModel):
    expected_version: ExpectedVersion
    reason: str
    changed_at: UTCDateTime

    @field_validator("reason")
    @classmethod
    def require_reason(cls, value: str) -> str:
        return require_nonblank_text(value, "reason")
