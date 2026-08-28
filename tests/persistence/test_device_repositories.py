from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.device_mappers import StoredDeviceAssignment
from backend.app.db.device_repositories import (
    DeviceHealthRepository,
    DeviceRepository,
)
from backend.app.db.models import (
    DeviceHealthObservationRow,
    DeviceRoomAssignmentRow,
    DeviceRow,
    LocationRow,
    RoomRow,
    TenantRow,
)
from backend.app.db.session import create_engine_for_url
from backend.app.domain.device_health import (
    DeviceHealthObservation,
    DeviceHealthState,
    DeviceSourceHealth,
)
from backend.app.services.errors import NotFoundError


OBSERVED_AT = datetime(2026, 8, 25, 14, 0, tzinfo=timezone.utc)


@pytest.fixture
def session() -> Session:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def _seed_devices(session: Session) -> None:
    session.add_all(
        [
            TenantRow(tenant_id="tenant_demo"),
            TenantRow(tenant_id="tenant_other"),
        ]
    )
    session.flush()
    session.add_all(
        [
            LocationRow(
                location_id="location_demo",
                tenant_id="tenant_demo",
                label="Demo clinic",
            ),
            LocationRow(
                location_id="location_other",
                tenant_id="tenant_other",
                label="Other clinic",
            ),
            RoomRow(
                room_id="room_214",
                tenant_id="tenant_demo",
                label="Room 214",
            ),
            RoomRow(
                room_id="room_other",
                tenant_id="tenant_other",
                label="Other room",
            ),
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
            DeviceRow(
                device_id="device_other",
                tenant_id="tenant_other",
                display_label="Other monitor",
            ),
        ]
    )
    session.flush()
    session.add(
        DeviceRoomAssignmentRow(
            assignment_id="device_assign_room_214",
            tenant_id="tenant_demo",
            device_id="device_room_214",
            location_id="location_demo",
            room_id="room_214",
            status="active",
            effective_from=OBSERVED_AT - timedelta(days=1),
            effective_to=None,
        )
    )
    session.commit()


def _health(
    state: DeviceHealthState,
    observed_at: datetime,
) -> DeviceHealthObservation:
    return DeviceHealthObservation(
        device_id="device_room_214",
        state=state,
        observed_at=observed_at,
        last_seen_at=observed_at - timedelta(seconds=5),
        sources=(DeviceSourceHealth("radar", "online"),),
        limitations=(() if state is DeviceHealthState.ONLINE else ("delayed",)),
    )


def test_device_repository_lists_current_assignment_and_hides_other_tenants(
    session: Session,
) -> None:
    _seed_devices(session)
    repository = DeviceRepository(session)

    devices = repository.list("tenant_demo")

    assert [device.device_id for device in devices] == [
        "device_room_214",
        "device_unassigned",
    ]
    assert devices[0].assignment == StoredDeviceAssignment(
        assignment_id="device_assign_room_214",
        location_id="location_demo",
        location_label="Demo clinic",
        room_id="room_214",
        room_label="Room 214",
        effective_from=OBSERVED_AT - timedelta(days=1),
    )
    assert devices[1].assignment is None
    assert repository.find_for_room("tenant_demo", "room_214") == devices[0]
    assert repository.find("tenant_other", "device_room_214") is None
    with pytest.raises(NotFoundError):
        repository.get("tenant_other", "device_room_214")


def test_health_repository_preserves_append_only_history_and_latest_order(
    session: Session,
) -> None:
    _seed_devices(session)
    repository = DeviceHealthRepository(session)
    online = _health(DeviceHealthState.ONLINE, OBSERVED_AT)
    buffering = _health(
        DeviceHealthState.BUFFERING,
        OBSERVED_AT + timedelta(minutes=1),
    )
    repository.record("tenant_demo", online)
    repository.record("tenant_demo", buffering)
    session.commit()

    assert repository.timeline("tenant_demo", "device_room_214") == [
        online,
        buffering,
    ]
    assert repository.latest("tenant_demo", "device_room_214") == buffering
    assert repository.latest("tenant_other", "device_room_214") is None


def test_latest_health_uses_record_id_as_deterministic_time_tiebreaker(
    session: Session,
) -> None:
    _seed_devices(session)
    repository = DeviceHealthRepository(session)
    repository.record(
        "tenant_demo",
        _health(DeviceHealthState.BUFFERING, OBSERVED_AT),
    )
    repository.record(
        "tenant_demo",
        _health(DeviceHealthState.RETRYING, OBSERVED_AT),
    )
    session.commit()

    assert repository.latest("tenant_demo", "device_room_214").state is (
        DeviceHealthState.RETRYING
    )


@pytest.mark.parametrize(
    "malformed_sources",
    (
        "radar",
        [{"source": "radar", "state": "online"}],
        [
            {"source": "radar", "state": "online", "limitations": []},
            {"source": "radar", "state": "online", "limitations": []},
        ],
        [{"source": 42, "state": "online", "limitations": []}],
        [{"source": "radar", "state": "healthy", "limitations": []}],
        [{"source": "radar", "state": "online", "limitations": "none"}],
    ),
)
def test_health_repository_rejects_malformed_stored_source_json(
    session: Session,
    malformed_sources: object,
) -> None:
    _seed_devices(session)
    repository = DeviceHealthRepository(session)
    repository.record(
        "tenant_demo",
        _health(DeviceHealthState.ONLINE, OBSERVED_AT),
    )
    row = session.scalar(select(DeviceHealthObservationRow))
    assert row is not None
    row.sources = malformed_sources
    session.commit()

    with pytest.raises(ValueError):
        repository.latest("tenant_demo", "device_room_214")


def test_health_record_rejects_unknown_or_cross_tenant_device(
    session: Session,
) -> None:
    _seed_devices(session)
    repository = DeviceHealthRepository(session)
    observation = _health(DeviceHealthState.ONLINE, OBSERVED_AT)

    with pytest.raises(NotFoundError):
        repository.record("tenant_other", observation)
