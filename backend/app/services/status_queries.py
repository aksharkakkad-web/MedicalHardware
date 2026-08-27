"""Product-facing resident monitoring, awareness, and calibration reads."""

from backend.app.contracts.status import (
    AwarenessTimelineResponse,
    CalibrationDimensionResponse,
    CalibrationResponse,
    MonitoringStatusResponse,
    ResidentStatusResponse,
    SetupChangeResponse,
)
from backend.app.db.repositories import ResidentRecord, ResidentRepository
from backend.app.db.status_repositories import (
    CalibrationRepository,
    MonitoringStatusRepository,
    StoredCalibration,
    StoredMonitoringStatus,
)
from backend.app.services.errors import NotFoundError
from backend.app.services.queries import AccessContext


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
    ) -> None:
        self._residents = residents
        self._monitoring = monitoring
        self._calibration = calibration

    def get_status(
        self,
        context: AccessContext,
        resident_id: str,
    ) -> ResidentStatusResponse:
        resident = self._resident(context, resident_id)
        monitoring = self._monitoring.latest(context.tenant_id, resident_id)
        calibration = self._calibration.current(context.tenant_id, resident_id)
        return ResidentStatusResponse(
            resident_id=resident.resident_id,
            room_id=resident.room_id,
            monitoring=monitoring_status_response(monitoring),
            calibration=calibration_response(calibration),
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
