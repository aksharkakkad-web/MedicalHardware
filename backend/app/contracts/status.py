from pydantic import Field, field_validator

from backend.app.contracts.common import (
    ContractModel,
    RequestContractModel,
    UTCDateTime,
)
from backend.app.domain.calibration import BaselineStatus
from backend.app.domain.monitoring import (
    MonitoringReason,
    MonitoringState,
    PresenceState,
)


class CalibrationDimensionResponse(ContractModel):
    dimension: str
    status: BaselineStatus
    eligible_windows: int = Field(ge=0)
    excluded_windows: int = Field(ge=0)


class SetupChangeResponse(ContractModel):
    previous_setup_version: str
    new_setup_version: str
    affected_dimensions: list[str]
    reason: str
    actor_id: str
    changed_at: UTCDateTime


class CalibrationResponse(ContractModel):
    resident_id: str
    version: int = Field(ge=0)
    recorded_at: UTCDateTime
    setup_version: str
    status: BaselineStatus
    eligible_windows: int = Field(ge=0)
    excluded_windows: int = Field(ge=0)
    reason: str
    prior_setup_versions: list[str]
    dimensions: list[CalibrationDimensionResponse]
    setup_changes: list[SetupChangeResponse]


class MonitoringStatusResponse(ContractModel):
    resident_id: str
    room_id: str
    observed_at: UTCDateTime
    monitoring_state: MonitoringState
    presence_state: PresenceState
    baseline_learning_allowed: bool
    resident_measurements_allowed: bool
    reasons: list[MonitoringReason]
    quality_policy_version: str
    quality_policy_test_only: bool


class ResidentStatusResponse(ContractModel):
    resident_id: str
    room_id: str
    monitoring: MonitoringStatusResponse
    calibration: CalibrationResponse


class AwarenessTimelineResponse(ContractModel):
    resident_id: str
    items: list[MonitoringStatusResponse]


class SetupChangeRequest(RequestContractModel):
    reason: str
    affected_dimensions: list[str]
    changed_at: UTCDateTime
    expected_calibration_version: int = Field(ge=0)

    @field_validator("reason")
    @classmethod
    def require_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason must not be blank")
        return normalized

    @field_validator("affected_dimensions")
    @classmethod
    def require_known_dimensions(cls, value: list[str]) -> list[str]:
        normalized = [dimension.strip() for dimension in value]
        if not normalized or any(not dimension for dimension in normalized):
            raise ValueError("affected_dimensions must contain nonblank values")
        if len(set(normalized)) != len(normalized):
            raise ValueError("affected_dimensions must not contain duplicates")
        return normalized
