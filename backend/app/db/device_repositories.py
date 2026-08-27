"""Tenant-scoped repositories for devices, assignments, and health history."""

from datetime import datetime, timezone

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from backend.app.db.device_mappers import (
    StoredDevice,
    StoredDeviceAssignment,
    health_from_row,
    health_to_row,
)
from backend.app.db.models import (
    DeviceHealthObservationRow,
    DeviceRoomAssignmentRow,
    DeviceRow,
    LocationRow,
    RoomRow,
)
from backend.app.domain.device_health import DeviceHealthObservation
from backend.app.services.errors import NotFoundError


class DeviceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, tenant_id: str) -> list[StoredDevice]:
        statement = self._base_statement().where(DeviceRow.tenant_id == tenant_id)
        statement = statement.order_by(DeviceRow.device_id)
        return [self._stored(*row) for row in self._session.execute(statement)]

    def find(self, tenant_id: str, device_id: str) -> StoredDevice | None:
        row = self._session.execute(
            self._base_statement().where(
                DeviceRow.tenant_id == tenant_id,
                DeviceRow.device_id == device_id,
            )
        ).one_or_none()
        return None if row is None else self._stored(*row)

    def get(self, tenant_id: str, device_id: str) -> StoredDevice:
        stored = self.find(tenant_id, device_id)
        if stored is None:
            raise NotFoundError()
        return stored

    def find_for_room(self, tenant_id: str, room_id: str) -> StoredDevice | None:
        row = self._session.execute(
            self._base_statement().where(
                DeviceRow.tenant_id == tenant_id,
                DeviceRoomAssignmentRow.room_id == room_id,
            )
        ).one_or_none()
        return None if row is None else self._stored(*row)

    @staticmethod
    def _base_statement():
        return (
            select(
                DeviceRow,
                DeviceRoomAssignmentRow,
                LocationRow,
                RoomRow,
            )
            .outerjoin(
                DeviceRoomAssignmentRow,
                and_(
                    DeviceRoomAssignmentRow.device_id == DeviceRow.device_id,
                    DeviceRoomAssignmentRow.tenant_id == DeviceRow.tenant_id,
                    DeviceRoomAssignmentRow.status == "active",
                ),
            )
            .outerjoin(
                LocationRow,
                and_(
                    LocationRow.location_id == DeviceRoomAssignmentRow.location_id,
                    LocationRow.tenant_id == DeviceRoomAssignmentRow.tenant_id,
                ),
            )
            .outerjoin(
                RoomRow,
                and_(
                    RoomRow.room_id == DeviceRoomAssignmentRow.room_id,
                    RoomRow.tenant_id == DeviceRoomAssignmentRow.tenant_id,
                ),
            )
        )

    @staticmethod
    def _stored(
        device: DeviceRow,
        assignment: DeviceRoomAssignmentRow | None,
        location: LocationRow | None,
        room: RoomRow | None,
    ) -> StoredDevice:
        if assignment is None:
            stored_assignment = None
        else:
            if location is None or room is None:
                raise ValueError("active device assignment is incomplete")
            stored_assignment = StoredDeviceAssignment(
                assignment_id=assignment.assignment_id,
                location_id=location.location_id,
                location_label=location.label,
                room_id=room.room_id,
                room_label=room.label,
                effective_from=_utc(assignment.effective_from),
            )
        return StoredDevice(
            device_id=device.device_id,
            display_label=device.display_label,
            assignment=stored_assignment,
        )


class DeviceHealthRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        tenant_id: str,
        observation: DeviceHealthObservation,
    ) -> None:
        device_exists = self._session.scalar(
            select(DeviceRow.device_id).where(
                DeviceRow.tenant_id == tenant_id,
                DeviceRow.device_id == observation.device_id,
            )
        )
        if device_exists is None:
            raise NotFoundError()
        row = health_to_row(tenant_id, observation)
        self._session.add(row)
        self._session.flush((row,))

    def latest(
        self,
        tenant_id: str,
        device_id: str,
    ) -> DeviceHealthObservation | None:
        row = self._session.scalar(
            select(DeviceHealthObservationRow)
            .where(
                DeviceHealthObservationRow.tenant_id == tenant_id,
                DeviceHealthObservationRow.device_id == device_id,
            )
            .order_by(
                DeviceHealthObservationRow.observed_at.desc(),
                DeviceHealthObservationRow.device_health_observation_id.desc(),
            )
            .limit(1)
        )
        return None if row is None else health_from_row(row)

    def timeline(
        self,
        tenant_id: str,
        device_id: str,
    ) -> list[DeviceHealthObservation]:
        rows = self._session.scalars(
            select(DeviceHealthObservationRow)
            .where(
                DeviceHealthObservationRow.tenant_id == tenant_id,
                DeviceHealthObservationRow.device_id == device_id,
            )
            .order_by(
                DeviceHealthObservationRow.observed_at,
                DeviceHealthObservationRow.device_health_observation_id,
            )
        ).all()
        return [health_from_row(row) for row in rows]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = ["DeviceHealthRepository", "DeviceRepository"]
