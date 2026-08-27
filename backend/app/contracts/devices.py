"""Strict Product API contracts for device assignment and health reads."""

from enum import StrEnum

from pydantic import Field, StrictBool, field_validator, model_validator

from backend.app.contracts.common import ContractModel, UTCDateTime
from backend.app.domain.device_health import (
    DeviceHealthState,
    DeviceSourceHealthState,
)


class DeviceHealthDataAvailability(StrEnum):
    AVAILABLE = "available"
    NOT_YET_AVAILABLE = "not_yet_available"


class DeviceAssignmentState(StrEnum):
    ASSIGNED = "assigned"
    ASSIGNMENT_UNAVAILABLE = "assignment_unavailable"


class DeviceSourceHealthResponse(ContractModel):
    source: str
    state: DeviceSourceHealthState
    limitations: list[str]

    @field_validator("source")
    @classmethod
    def require_source(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("source must not be blank")
        return normalized

    @field_validator("limitations")
    @classmethod
    def require_source_limitations(cls, value: list[str]) -> list[str]:
        return _normalize_text_list(value, "limitations")


class DeviceHealthResponse(ContractModel):
    device_id: str
    data_availability: DeviceHealthDataAvailability
    state: DeviceHealthState | None
    observed_at: UTCDateTime | None
    last_seen_at: UTCDateTime | None
    sources: list[DeviceSourceHealthResponse]
    limitations: list[str]
    policy_version: str | None
    policy_test_only: StrictBool | None

    @field_validator("device_id")
    @classmethod
    def require_device_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("device_id must not be blank")
        return normalized

    @field_validator("limitations")
    @classmethod
    def require_limitations(cls, value: list[str]) -> list[str]:
        return _normalize_text_list(value, "limitations")

    @field_validator("sources")
    @classmethod
    def require_unique_sources(
        cls,
        value: list[DeviceSourceHealthResponse],
    ) -> list[DeviceSourceHealthResponse]:
        names = [source.source for source in value]
        if len(set(names)) != len(names):
            raise ValueError("sources must not contain duplicate source names")
        return value

    @model_validator(mode="after")
    def require_consistent_availability(self) -> "DeviceHealthResponse":
        if self.data_availability is DeviceHealthDataAvailability.AVAILABLE:
            required = (
                self.state,
                self.observed_at,
                self.policy_version,
                self.policy_test_only,
            )
            if any(value is None for value in required):
                raise ValueError("available health requires state, time, and policy")
            if self.last_seen_at is not None and self.last_seen_at > self.observed_at:
                raise ValueError("last_seen_at must not be after observed_at")
            if not self.policy_version.strip():
                raise ValueError("policy_version must not be blank")
            return self

        nullable_values = (
            self.state,
            self.observed_at,
            self.last_seen_at,
            self.policy_version,
            self.policy_test_only,
        )
        if any(value is not None for value in nullable_values):
            raise ValueError("unavailable health must not invent current values")
        if self.sources or self.limitations:
            raise ValueError("unavailable health must not invent source detail")
        return self


class DeviceAssignmentResponse(ContractModel):
    location_id: str
    location_label: str
    room_id: str
    room_label: str
    assigned_at: UTCDateTime

    @field_validator("location_id", "location_label", "room_id", "room_label")
    @classmethod
    def require_assignment_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("assignment fields must not be blank")
        return normalized


class DeviceListItemResponse(ContractModel):
    device_id: str
    display_label: str
    assignment: DeviceAssignmentResponse | None
    health: DeviceHealthResponse

    @field_validator("device_id", "display_label")
    @classmethod
    def require_device_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("device fields must not be blank")
        return normalized


class DeviceListResponse(ContractModel):
    items: list[DeviceListItemResponse] = Field(default_factory=list)


def _normalize_text_list(value: list[str], field: str) -> list[str]:
    normalized = [item.strip() for item in value]
    if any(not item for item in normalized):
        raise ValueError(f"{field} must contain nonblank values")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field} must not contain duplicates")
    return normalized


__all__ = [
    "DeviceAssignmentResponse",
    "DeviceAssignmentState",
    "DeviceHealthDataAvailability",
    "DeviceHealthResponse",
    "DeviceListItemResponse",
    "DeviceListResponse",
    "DeviceSourceHealthResponse",
]
