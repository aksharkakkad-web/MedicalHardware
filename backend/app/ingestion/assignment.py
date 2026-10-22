"""Fail-closed device, room, and resident assignment resolution."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.device_repositories import DeviceRepository
from backend.app.db.models import RoomResidentAssignmentRow
from backend.app.services.errors import ProductError


class AssignmentUnavailableError(ProductError):
    code = "assignment_unavailable"
    default_message = "Monitoring assignment is unavailable"

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class MonitoringAssignment:
    tenant_id: str
    device_id: str
    room_id: str
    resident_id: str
    device_assignment_id: str
    resident_assignment_id: str

    def __post_init__(self) -> None:
        for field in (
            "tenant_id",
            "device_id",
            "room_id",
            "resident_id",
            "device_assignment_id",
            "resident_assignment_id",
        ):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be nonblank")


def resolve_monitoring_assignment(
    session: Session,
    tenant_id: str,
    device_id: str,
    declared_room_id: str,
) -> MonitoringAssignment:
    """Resolve the only safe resident lane for one telemetry envelope."""
    device_assignments = DeviceRepository(session).active_room_assignments(
        tenant_id,
        device_id,
    )
    if not device_assignments:
        raise AssignmentUnavailableError("device_assignment_missing")
    if len(device_assignments) != 1:
        raise AssignmentUnavailableError("device_assignment_conflict")
    device_assignment = device_assignments[0]
    if device_assignment.room_id != declared_room_id:
        raise AssignmentUnavailableError("declared_room_mismatch")

    resident_assignments = tuple(
        session.scalars(
            select(RoomResidentAssignmentRow)
            .where(
                RoomResidentAssignmentRow.tenant_id == tenant_id,
                RoomResidentAssignmentRow.room_id == device_assignment.room_id,
                RoomResidentAssignmentRow.status == "active",
            )
            .order_by(RoomResidentAssignmentRow.assignment_id)
        ).all()
    )
    if not resident_assignments:
        raise AssignmentUnavailableError("resident_assignment_missing")
    if len(resident_assignments) != 1:
        raise AssignmentUnavailableError("resident_assignment_conflict")
    resident_assignment = resident_assignments[0]

    return MonitoringAssignment(
        tenant_id=tenant_id,
        device_id=device_id,
        room_id=device_assignment.room_id,
        resident_id=resident_assignment.resident_id,
        device_assignment_id=device_assignment.assignment_id,
        resident_assignment_id=resident_assignment.assignment_id,
    )


__all__ = [
    "AssignmentUnavailableError",
    "MonitoringAssignment",
    "resolve_monitoring_assignment",
]
