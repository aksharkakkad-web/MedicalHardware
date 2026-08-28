"""Product-facing tenant-safe device assignment and health reads."""

from backend.app.contracts.devices import (
    DeviceAssignmentResponse,
    DeviceHealthDataAvailability,
    DeviceHealthResponse,
    DeviceListItemResponse,
    DeviceListResponse,
    DeviceSourceHealthResponse,
)
from backend.app.db.device_mappers import StoredDevice
from backend.app.db.device_repositories import (
    DeviceHealthRepository,
    DeviceRepository,
)
from backend.app.domain.device_health import DeviceHealthObservation
from backend.app.services.queries import AccessContext


def device_health_response(
    device_id: str,
    observation: DeviceHealthObservation | None,
) -> DeviceHealthResponse:
    if observation is None:
        return DeviceHealthResponse(
            device_id=device_id,
            data_availability=DeviceHealthDataAvailability.NOT_YET_AVAILABLE,
            state=None,
            observed_at=None,
            last_seen_at=None,
            sources=[],
            limitations=[],
            policy_version=None,
            policy_test_only=None,
        )
    return DeviceHealthResponse(
        device_id=device_id,
        data_availability=DeviceHealthDataAvailability.AVAILABLE,
        state=observation.state,
        observed_at=observation.observed_at,
        last_seen_at=observation.last_seen_at,
        sources=[
            DeviceSourceHealthResponse(
                source=source.source,
                state=source.state,
                limitations=list(source.limitations),
            )
            for source in observation.sources
        ],
        limitations=list(observation.limitations),
        policy_version=observation.policy_version,
        policy_test_only=observation.policy_test_only,
    )


def device_list_item_response(
    stored: StoredDevice,
    observation: DeviceHealthObservation | None,
) -> DeviceListItemResponse:
    assignment = stored.assignment
    return DeviceListItemResponse(
        device_id=stored.device_id,
        display_label=stored.display_label,
        assignment=(
            None
            if assignment is None
            else DeviceAssignmentResponse(
                location_id=assignment.location_id,
                location_label=assignment.location_label,
                room_id=assignment.room_id,
                room_label=assignment.room_label,
                assigned_at=assignment.effective_from,
            )
        ),
        health=device_health_response(stored.device_id, observation),
    )


class ProductDeviceQueryService:
    def __init__(
        self,
        devices: DeviceRepository,
        health: DeviceHealthRepository,
    ) -> None:
        self._devices = devices
        self._health = health

    def list_devices(self, context: AccessContext) -> DeviceListResponse:
        return DeviceListResponse(
            items=[
                device_list_item_response(
                    stored,
                    self._health.latest(context.tenant_id, stored.device_id),
                )
                for stored in self._devices.list(context.tenant_id)
            ]
        )

    def get_health(
        self,
        context: AccessContext,
        device_id: str,
    ) -> DeviceHealthResponse:
        device = self._devices.get(context.tenant_id, device_id)
        return device_health_response(
            device.device_id,
            self._health.latest(context.tenant_id, device.device_id),
        )


__all__ = [
    "ProductDeviceQueryService",
    "device_health_response",
    "device_list_item_response",
]
