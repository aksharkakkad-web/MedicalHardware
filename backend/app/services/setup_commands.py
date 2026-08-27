"""Atomic resident monitoring setup-change commands."""

from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.db.models import AuditLogRow
from backend.app.db.repositories import ResidentRepository
from backend.app.db.status_repositories import (
    CalibrationRepository,
    StoredCalibration,
)
from backend.app.domain.calibration import start_recalibration
from backend.app.services.errors import (
    ConcurrentUpdateError,
    InvalidTransitionError,
    NotFoundError,
)
from backend.app.services.queries import AccessContext


class SetupChangeCommandService:
    def __init__(
        self,
        session: Session,
        *,
        residents: ResidentRepository,
        calibration: CalibrationRepository,
    ) -> None:
        self._session = session
        self._residents = residents
        self._calibration = calibration

    def change_setup(
        self,
        context: AccessContext,
        resident_id: str,
        *,
        reason: str,
        affected_dimensions: tuple[str, ...],
        changed_at: datetime,
        expected_calibration_version: int,
    ) -> StoredCalibration:
        resident = self._residents.find(context.tenant_id, resident_id)
        if resident is None:
            raise NotFoundError()
        current = self._calibration.current(context.tenant_id, resident_id)
        if current.version != expected_calibration_version:
            raise ConcurrentUpdateError()
        if changed_at < current.recorded_at:
            raise InvalidTransitionError()
        next_version = current.version + 1
        try:
            progress = start_recalibration(
                current.progress,
                new_setup_version=f"setup_{resident.room_id}_v{next_version}",
                reason=reason,
                actor_id=context.actor_id,
                changed_at=changed_at,
                affected_dimensions=affected_dimensions,
            )
        except ValueError as error:
            raise InvalidTransitionError() from error

        saved = self._calibration.save(
            context.tenant_id,
            StoredCalibration(
                resident_id=resident_id,
                version=next_version,
                recorded_at=changed_at,
                progress=progress,
            ),
            expected_version=expected_calibration_version,
        )
        action = saved.progress.setup_change_history[-1]
        self._session.add(
            AuditLogRow(
                tenant_id=context.tenant_id,
                actor_id=context.actor_id,
                action="monitoring_setup.changed",
                target_type="resident_monitoring_setup",
                target_id=resident_id,
                occurred_at=changed_at,
                details={
                    "previous_setup_version": action.previous_setup_version,
                    "new_setup_version": action.new_setup_version,
                    "affected_dimensions": list(action.affected_dimensions),
                    "reason": action.reason,
                    "calibration_version": saved.version,
                },
            )
        )
        self._session.flush()
        return saved
