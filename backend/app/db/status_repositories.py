"""Tenant-scoped append-only status and calibration repositories."""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db.models import (
    CalibrationSnapshotRow,
    MonitoringSetupChangeRow,
    MonitoringStatusSnapshotRow,
)
from backend.app.db.status_mappers import (
    StoredCalibration,
    StoredMonitoringStatus,
    calibration_from_rows,
    calibration_to_row,
    latest_setup_change_to_row,
    monitoring_from_row,
    monitoring_to_row,
)
from backend.app.services.errors import ConcurrentUpdateError, NotFoundError


def _is_calibration_version_conflict(error: IntegrityError) -> bool:
    constraint_name = getattr(
        getattr(error.orig, "diag", None),
        "constraint_name",
        None,
    )
    if constraint_name in {
        "calibration_snapshots_tenant_id_resident_id_version_key",
        "monitoring_setup_changes_tenant_id_resident_id_calibration_version_key",
    }:
        return True
    message = str(error.orig).casefold()
    return (
        "unique constraint failed: calibration_snapshots.tenant_id, "
        "calibration_snapshots.resident_id, calibration_snapshots.version"
    ) in message or (
        "unique constraint failed: monitoring_setup_changes.tenant_id, "
        "monitoring_setup_changes.resident_id, "
        "monitoring_setup_changes.calibration_version"
    ) in message


class MonitoringStatusRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(self, tenant_id: str, stored: StoredMonitoringStatus) -> None:
        row = monitoring_to_row(tenant_id, stored)
        self._session.add(row)
        self._session.flush((row,))

    def latest(self, tenant_id: str, resident_id: str) -> StoredMonitoringStatus:
        row = self._session.scalar(
            select(MonitoringStatusSnapshotRow)
            .where(
                MonitoringStatusSnapshotRow.tenant_id == tenant_id,
                MonitoringStatusSnapshotRow.resident_id == resident_id,
            )
            .order_by(
                MonitoringStatusSnapshotRow.observed_at.desc(),
                MonitoringStatusSnapshotRow.monitoring_status_id.desc(),
            )
            .limit(1)
        )
        if row is None:
            raise NotFoundError()
        return monitoring_from_row(row)

    def timeline(
        self,
        tenant_id: str,
        resident_id: str,
    ) -> list[StoredMonitoringStatus]:
        rows = self._session.scalars(
            select(MonitoringStatusSnapshotRow)
            .where(
                MonitoringStatusSnapshotRow.tenant_id == tenant_id,
                MonitoringStatusSnapshotRow.resident_id == resident_id,
            )
            .order_by(
                MonitoringStatusSnapshotRow.observed_at,
                MonitoringStatusSnapshotRow.monitoring_status_id,
            )
        ).all()
        return [monitoring_from_row(row) for row in rows]


class CalibrationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def current(self, tenant_id: str, resident_id: str) -> StoredCalibration:
        row = self._session.scalar(
            select(CalibrationSnapshotRow)
            .where(
                CalibrationSnapshotRow.tenant_id == tenant_id,
                CalibrationSnapshotRow.resident_id == resident_id,
            )
            .order_by(CalibrationSnapshotRow.version.desc())
            .limit(1)
        )
        if row is None:
            raise NotFoundError()
        setup_rows = self._session.scalars(
            select(MonitoringSetupChangeRow)
            .where(
                MonitoringSetupChangeRow.tenant_id == tenant_id,
                MonitoringSetupChangeRow.resident_id == resident_id,
                MonitoringSetupChangeRow.calibration_version <= row.version,
            )
            .order_by(MonitoringSetupChangeRow.calibration_version)
        ).all()
        return calibration_from_rows(row, setup_rows)

    def save(
        self,
        tenant_id: str,
        stored: StoredCalibration,
        expected_version: int,
    ) -> StoredCalibration:
        current_version = self._session.scalar(
            select(CalibrationSnapshotRow.version)
            .where(
                CalibrationSnapshotRow.tenant_id == tenant_id,
                CalibrationSnapshotRow.resident_id == stored.resident_id,
            )
            .order_by(CalibrationSnapshotRow.version.desc())
            .limit(1)
        )
        actual_version = 0 if current_version is None else current_version
        if actual_version != expected_version or stored.version != expected_version + 1:
            raise ConcurrentUpdateError()

        existing_setup_count = self._session.scalar(
            select(func.count())
            .select_from(MonitoringSetupChangeRow)
            .where(
                MonitoringSetupChangeRow.tenant_id == tenant_id,
                MonitoringSetupChangeRow.resident_id == stored.resident_id,
            )
        )
        history_count = len(stored.progress.setup_change_history)
        if history_count not in {existing_setup_count, existing_setup_count + 1}:
            raise ConcurrentUpdateError()

        calibration_row = calibration_to_row(tenant_id, stored)
        setup_row = (
            latest_setup_change_to_row(tenant_id, stored)
            if history_count == existing_setup_count + 1
            else None
        )
        self._session.add(calibration_row)
        if setup_row is not None:
            self._session.add(setup_row)
        try:
            self._session.flush()
        except IntegrityError as error:
            if _is_calibration_version_conflict(error):
                raise ConcurrentUpdateError() from error
            raise
        return self.current(tenant_id, stored.resident_id)


__all__ = [
    "CalibrationRepository",
    "MonitoringStatusRepository",
    "StoredCalibration",
    "StoredMonitoringStatus",
]
