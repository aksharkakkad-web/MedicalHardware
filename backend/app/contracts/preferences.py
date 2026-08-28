from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    model_validator,
)

from backend.app.contracts.common import ContractModel, RequestContractModel, UTCDateTime


ExpectedVersion = Annotated[StrictInt, Field(ge=0)]


class EventDeliveryPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    watch: StrictBool
    high: StrictBool
    critical: StrictBool


class AwarenessDeliveryPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    away: StrictBool
    return_: StrictBool = Field(alias="return")
    limited: StrictBool
    unavailable: StrictBool


class ResidentNotificationPreferencesResponse(ContractModel):
    resident_id: str
    data_availability: Literal["available", "not_yet_available"]
    version: int | None
    event_delivery: EventDeliveryPreferences | None
    awareness_delivery: AwarenessDeliveryPreferences | None
    high_critical_dashboard_visibility: Literal["always_visible"] = "always_visible"
    changed_by: str | None
    changed_at: UTCDateTime | None

    @model_validator(mode="after")
    def require_honest_availability_shape(
        self,
    ) -> "ResidentNotificationPreferencesResponse":
        saved_values = (
            self.version,
            self.event_delivery,
            self.awareness_delivery,
            self.changed_by,
            self.changed_at,
        )
        if self.data_availability == "available":
            if any(value is None for value in saved_values):
                raise ValueError("available preferences require saved values")
            if self.version is not None and self.version < 1:
                raise ValueError("available preference version must be positive")
        elif any(value is not None for value in saved_values):
            raise ValueError("missing preferences cannot contain saved values")
        return self


class UpdateNotificationPreferencesRequest(RequestContractModel):
    expected_version: ExpectedVersion
    event_delivery: EventDeliveryPreferences
    awareness_delivery: AwarenessDeliveryPreferences
    changed_at: UTCDateTime
