from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from backend.app.contracts.common import (
    ContractModel,
    RequestContractModel,
    UTCDateTime,
)
from backend.app.contracts.devices import (
    DeviceAssignmentState,
    DeviceListItemResponse,
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


class ResidentStatusDataAvailability(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    NOT_YET_AVAILABLE = "not_yet_available"


class ResidentStatusUnavailableReason(StrEnum):
    MONITORING_NOT_YET_AVAILABLE = "monitoring_not_yet_available"
    CALIBRATION_NOT_YET_AVAILABLE = "calibration_not_yet_available"
    DEVICE_ASSIGNMENT_UNAVAILABLE = "device_assignment_unavailable"
    DEVICE_HEALTH_NOT_YET_AVAILABLE = "device_health_not_yet_available"


class ResidentStatusResponse(ContractModel):
    resident_id: str
    room_id: str
    data_availability: ResidentStatusDataAvailability
    unavailable_reasons: list[ResidentStatusUnavailableReason]
    device_assignment_state: DeviceAssignmentState
    device: DeviceListItemResponse | None
    monitoring: MonitoringStatusResponse | None
    calibration: CalibrationResponse | None

    @field_validator("unavailable_reasons")
    @classmethod
    def require_unique_unavailable_reasons(
        cls,
        value: list[ResidentStatusUnavailableReason],
    ) -> list[ResidentStatusUnavailableReason]:
        if len(set(value)) != len(value):
            raise ValueError("unavailable_reasons must not contain duplicates")
        return value

    @model_validator(mode="after")
    def require_consistent_device_assignment(self) -> "ResidentStatusResponse":
        if self.device_assignment_state is DeviceAssignmentState.ASSIGNED:
            if self.device is None or self.device.assignment is None:
                raise ValueError("assigned resident status requires device assignment")
            if self.device.assignment.room_id != self.room_id:
                raise ValueError("device assignment must match resident room")
            if self.device.health.device_id != self.device.device_id:
                raise ValueError("device health identity must match device")
            return self
        if self.device is not None:
            raise ValueError("unavailable device assignment must not invent a device")
        return self


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
