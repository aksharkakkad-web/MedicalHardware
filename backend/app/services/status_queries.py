"""Product-facing resident monitoring, awareness, and calibration reads."""

from backend.app.contracts.status import (
    AwarenessTimelineResponse,
    CalibrationDimensionResponse,
    CalibrationResponse,
    MonitoringStatusResponse,
    ResidentStatusDataAvailability,
    ResidentStatusResponse,
    ResidentStatusUnavailableReason,
    SetupChangeResponse,
)
from backend.app.contracts.devices import DeviceAssignmentState
from backend.app.db.device_repositories import (
    DeviceHealthRepository,
    DeviceRepository,
)
from backend.app.db.repositories import ResidentRecord, ResidentRepository
from backend.app.db.status_repositories import (
    CalibrationRepository,
    MonitoringStatusRepository,
    StoredCalibration,
    StoredMonitoringStatus,
)
from backend.app.services.errors import NotFoundError
from backend.app.services.device_queries import device_list_item_response
from backend.app.services.queries import AccessContext
from backend.app.domain.device_health import DeviceHealthState
from backend.app.domain.monitoring import MonitoringReason, MonitoringState


def monitoring_status_response(
    stored: StoredMonitoringStatus,
) -> MonitoringStatusResponse:
    snapshot = stored.snapshot
    return MonitoringStatusResponse(
        resident_id=stored.resident_id,
        room_id=stored.room_id,
        observed_at=stored.observed_at,
        monitoring_state=snapshot.state,
        presence_state=snapshot.presence,
        baseline_learning_allowed=snapshot.baseline_learning_allowed,
        resident_measurements_allowed=snapshot.resident_measurements_allowed,
        reasons=list(snapshot.reasons),
        quality_policy_version=snapshot.quality_policy_version,
        quality_policy_test_only=snapshot.quality_policy_test_only,
    )


def calibration_response(stored: StoredCalibration) -> CalibrationResponse:
    progress = stored.progress
    return CalibrationResponse(
        resident_id=stored.resident_id,
        version=stored.version,
        recorded_at=stored.recorded_at,
        setup_version=progress.setup_version,
        status=progress.status,
        eligible_windows=progress.eligible_windows,
        excluded_windows=progress.excluded_windows,
        reason=progress.reason,
        prior_setup_versions=list(progress.prior_setup_versions),
        dimensions=[
            CalibrationDimensionResponse(
                dimension=dimension.dimension,
                status=dimension.status,
                eligible_windows=dimension.eligible_windows,
                excluded_windows=dimension.excluded_windows,
            )
            for dimension in progress.dimension_progress
        ],
        setup_changes=[
            SetupChangeResponse(
                previous_setup_version=change.previous_setup_version,
                new_setup_version=change.new_setup_version,
                affected_dimensions=list(change.affected_dimensions),
                reason=change.reason,
                actor_id=change.actor_id,
                changed_at=change.changed_at,
            )
            for change in progress.setup_change_history
        ],
    )


class ProductStatusQueryService:
    def __init__(
        self,
        residents: ResidentRepository,
        monitoring: MonitoringStatusRepository,
        calibration: CalibrationRepository,
        devices: DeviceRepository,
        device_health: DeviceHealthRepository,
    ) -> None:
        self._residents = residents
        self._monitoring = monitoring
        self._calibration = calibration
        self._devices = devices
        self._device_health = device_health

    def get_status(
        self,
        context: AccessContext,
        resident_id: str,
    ) -> ResidentStatusResponse:
        resident = self._resident(context, resident_id)
        monitoring = self._monitoring.find_latest(context.tenant_id, resident_id)
        calibration = self._calibration.find_current(
            context.tenant_id,
            resident_id,
        )
        device = self._devices.find_for_room(context.tenant_id, resident.room_id)
        device_observation = (
            None
            if device is None
            else self._device_health.latest(context.tenant_id, device.device_id)
        )
        unavailable_reasons: list[ResidentStatusUnavailableReason] = []
        if monitoring is None:
            unavailable_reasons.append(
                ResidentStatusUnavailableReason.MONITORING_NOT_YET_AVAILABLE
            )
        if calibration is None:
            unavailable_reasons.append(
                ResidentStatusUnavailableReason.CALIBRATION_NOT_YET_AVAILABLE
            )
        if device is None:
            unavailable_reasons.append(
                ResidentStatusUnavailableReason.DEVICE_ASSIGNMENT_UNAVAILABLE
            )
            device_assignment_state = DeviceAssignmentState.ASSIGNMENT_UNAVAILABLE
            device_response = None
            operational_reason = MonitoringReason.ASSIGNMENT_INVALID
        else:
            device_assignment_state = DeviceAssignmentState.ASSIGNED
            device_response = device_list_item_response(
                device,
                device_observation,
            )
            if device_observation is None:
                unavailable_reasons.append(
                    ResidentStatusUnavailableReason.DEVICE_HEALTH_NOT_YET_AVAILABLE
                )
                operational_reason = MonitoringReason.DEVICE_HEALTH_UNAVAILABLE
            elif device_observation.state is DeviceHealthState.ONLINE:
                operational_reason = None
            elif (
                device_observation.state
                is DeviceHealthState.ASSIGNMENT_UNAVAILABLE
            ):
                operational_reason = MonitoringReason.ASSIGNMENT_INVALID
            else:
                operational_reason = MonitoringReason.DEVICE_UNHEALTHY

        if monitoring is None and calibration is None:
            availability = ResidentStatusDataAvailability.NOT_YET_AVAILABLE
        elif unavailable_reasons:
            availability = ResidentStatusDataAvailability.PARTIAL
        else:
            availability = ResidentStatusDataAvailability.AVAILABLE

        monitoring_response = (
            None
            if monitoring is None
            else monitoring_status_response(monitoring)
        )
        if monitoring_response is not None and operational_reason is not None:
            reasons = list(monitoring_response.reasons)
            if operational_reason not in reasons:
                reasons.append(operational_reason)
            monitoring_response = monitoring_response.model_copy(
                update={
                    "monitoring_state": MonitoringState.UNAVAILABLE,
                    "baseline_learning_allowed": False,
                    "resident_measurements_allowed": False,
                    "reasons": reasons,
                }
            )
        return ResidentStatusResponse(
            resident_id=resident.resident_id,
            room_id=resident.room_id,
            data_availability=availability,
            unavailable_reasons=unavailable_reasons,
            device_assignment_state=device_assignment_state,
            device=device_response,
            monitoring=monitoring_response,
            calibration=(
                None if calibration is None else calibration_response(calibration)
            ),
        )

    def get_awareness(
        self,
        context: AccessContext,
        resident_id: str,
    ) -> AwarenessTimelineResponse:
        self._resident(context, resident_id)
        return AwarenessTimelineResponse(
            resident_id=resident_id,
            items=[
                monitoring_status_response(stored)
                for stored in self._monitoring.timeline(
                    context.tenant_id,
                    resident_id,
                )
            ],
        )

    def get_calibration(
        self,
        context: AccessContext,
        resident_id: str,
    ) -> CalibrationResponse:
        self._resident(context, resident_id)
        return calibration_response(
            self._calibration.current(context.tenant_id, resident_id)
        )

    def _resident(
        self,
        context: AccessContext,
        resident_id: str,
    ) -> ResidentRecord:
        resident = self._residents.find(context.tenant_id, resident_id)
        if resident is None:
            raise NotFoundError()
        return resident
