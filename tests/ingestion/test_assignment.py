from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.device_repositories import DeviceRepository
from backend.app.db.models import (
    DeviceRoomAssignmentRow,
    DeviceRow,
    LocationRow,
    ResidentRow,
    RoomResidentAssignmentRow,
    RoomRow,
    TenantRow,
)
from backend.app.db.session import create_engine_for_url
from backend.app.ingestion.assignment import (
    AssignmentUnavailableError,
    MonitoringAssignment,
    resolve_monitoring_assignment,
)


NOW = datetime(2026, 9, 23, 16, 0, tzinfo=timezone.utc)


@pytest.fixture
def session() -> Session:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as active:
        _seed(active)
        yield active
    engine.dispose()


def _seed(session: Session) -> None:
    session.add_all(
        [TenantRow(tenant_id="tenant_demo"), TenantRow(tenant_id="tenant_other")]
    )
    session.flush()
    session.add_all(
        [
            LocationRow(
                location_id="location_demo",
                tenant_id="tenant_demo",
                label="Demo clinic",
            ),
            RoomRow(room_id="room_214", tenant_id="tenant_demo", label="Room 214"),
            RoomRow(room_id="room_spare", tenant_id="tenant_demo", label="Spare"),
            RoomRow(room_id="room_other", tenant_id="tenant_other", label="Other"),
            DeviceRow(
                device_id="device_room_214",
                tenant_id="tenant_demo",
                display_label="Room 214 monitor",
            ),
            DeviceRow(
                device_id="device_unassigned",
                tenant_id="tenant_demo",
                display_label="Spare monitor",
            ),
            ResidentRow(
                resident_id="resident_demo_a",
                tenant_id="tenant_demo",
                display_label="Resident A",
            ),
        ]
    )
    session.flush()
    session.add_all(
        [
            DeviceRoomAssignmentRow(
                assignment_id="device_assign_room_214",
                tenant_id="tenant_demo",
                device_id="device_room_214",
                location_id="location_demo",
                room_id="room_214",
                status="active",
                effective_from=NOW,
                effective_to=None,
            ),
            RoomResidentAssignmentRow(
                assignment_id="resident_assign_room_214",
                tenant_id="tenant_demo",
                room_id="room_214",
                resident_id="resident_demo_a",
                status="active",
                effective_from=NOW,
                effective_to=None,
            ),
        ]
    )
    session.commit()


def test_resident_comes_from_server_assignment(session: Session) -> None:
    assignment = resolve_monitoring_assignment(
        session,
        "tenant_demo",
        "device_room_214",
        "room_214",
    )

    assert assignment == MonitoringAssignment(
        tenant_id="tenant_demo",
        device_id="device_room_214",
        room_id="room_214",
        resident_id="resident_demo_a",
        device_assignment_id="device_assign_room_214",
        resident_assignment_id="resident_assign_room_214",
    )


@pytest.mark.parametrize(
    ("tenant_id", "device_id", "room_id", "reason"),
    (
        ("tenant_demo", "device_room_214", "room_spare", "declared_room_mismatch"),
        ("tenant_demo", "device_unassigned", "room_214", "device_assignment_missing"),
        ("tenant_demo", "missing_device", "room_214", "device_assignment_missing"),
        ("tenant_other", "device_room_214", "room_214", "device_assignment_missing"),
    ),
)
def test_invalid_device_assignment_blocks_resident_processing(
    session: Session,
    tenant_id: str,
    device_id: str,
    room_id: str,
    reason: str,
) -> None:
    with pytest.raises(AssignmentUnavailableError, match=reason):
        resolve_monitoring_assignment(session, tenant_id, device_id, room_id)


def test_missing_room_resident_assignment_blocks_processing(session: Session) -> None:
    assignment = session.get(RoomResidentAssignmentRow, "resident_assign_room_214")
    assert assignment is not None
    assignment.status = "inactive"
    assignment.effective_to = NOW
    session.commit()

    with pytest.raises(AssignmentUnavailableError, match="resident_assignment_missing"):
        resolve_monitoring_assignment(
            session,
            "tenant_demo",
            "device_room_214",
            "room_214",
        )


def test_conflicting_device_assignments_fail_closed(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assignment = session.get(DeviceRoomAssignmentRow, "device_assign_room_214")
    assert assignment is not None
    monkeypatch.setattr(
        DeviceRepository,
        "active_room_assignments",
        lambda *args: (assignment, assignment),
    )

    with pytest.raises(AssignmentUnavailableError, match="device_assignment_conflict"):
        resolve_monitoring_assignment(
            session,
            "tenant_demo",
            "device_room_214",
            "room_214",
        )
