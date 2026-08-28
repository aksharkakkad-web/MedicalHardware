from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from httpx import Response
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from backend.app.config import Settings
from backend.app.db.models import (
    AuditLogRow,
    CalibrationSnapshotRow,
    EventActionRow,
    EventPriorityHistoryRow,
    FeedbackRecordRow,
    IdempotencyRecordRow,
    MonitoringStatusSnapshotRow,
    ResidentMemoryEntryRow,
    ResidentMemorySnapshotRow,
    RoomResidentAssignmentRow,
    DeviceHealthObservationRow,
    DeviceRoomAssignmentRow,
    DeviceRow,
    LocationRow,
    RoomRow,
    TenantRow,
)
from backend.app.db.device_repositories import (
    DeviceHealthRepository,
    DeviceRepository,
)
from backend.app.domain.device_health import (
    DeviceHealthObservation,
    DeviceHealthState,
    DeviceSourceHealth,
)
from backend.app.db.seed import seed_synthetic_story
from backend.app.main import create_app


ACCESS_HEADERS = {
    "X-Tenant-Id": "tenant_demo",
    "X-Actor-Id": "operator_1",
}
EVENT_PATH = "/v1/events/evt_phase2_demo"


def _post(
    client: TestClient,
    suffix: str,
    key: str,
    body: dict[str, object],
) -> Response:
    return client.post(
        f"{EVENT_PATH}/{suffix}",
        headers={**ACCESS_HEADERS, "Idempotency-Key": key},
        json={"schema_version": "1.0", **body},
    )


def test_application_shutdown_disposes_its_process_engine(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'engine-lifecycle.db'}"
    app = create_app(Settings(app_env="test", database_url=database_url))
    process_pool = app.state.engine.pool

    with TestClient(app):
        pass

    assert app.state.engine.pool is not process_pool


def test_device_assignment_and_health_history_survive_restart(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'device-restart.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    observed_at = datetime(2026, 8, 25, 14, 0, tzinfo=timezone.utc)

    first_app = create_app(Settings(app_env="test", database_url=database_url))
    with first_app.state.session_factory() as session:
        session.add(TenantRow(tenant_id="tenant_device_restart"))
        session.flush()
        session.add_all(
            [
                LocationRow(
                    location_id="location_restart",
                    tenant_id="tenant_device_restart",
                    label="Restart clinic",
                ),
                RoomRow(
                    room_id="room_restart",
                    tenant_id="tenant_device_restart",
                    label="Restart room",
                ),
                DeviceRow(
                    device_id="device_restart",
                    tenant_id="tenant_device_restart",
                    display_label="Restart monitor",
                ),
            ]
        )
        session.flush()
        session.add(
            DeviceRoomAssignmentRow(
                assignment_id="assignment_restart",
                tenant_id="tenant_device_restart",
                device_id="device_restart",
                location_id="location_restart",
                room_id="room_restart",
                status="active",
                effective_from=observed_at - timedelta(days=1),
                effective_to=None,
            )
        )
        health = DeviceHealthRepository(session)
        for offset, state in enumerate(
            (DeviceHealthState.ONLINE, DeviceHealthState.BUFFERING)
        ):
            health.record(
                "tenant_device_restart",
                DeviceHealthObservation(
                    device_id="device_restart",
                    state=state,
                    observed_at=observed_at + timedelta(minutes=offset),
                    last_seen_at=observed_at,
                    sources=(DeviceSourceHealth("radar", "online"),),
                    limitations=(() if offset == 0 else ("upload_delayed",)),
                ),
            )
        session.commit()
    first_app.state.engine.dispose()

    second_app = create_app(Settings(app_env="test", database_url=database_url))
    with second_app.state.session_factory() as session:
        device = DeviceRepository(session).get(
            "tenant_device_restart",
            "device_restart",
        )
        health = DeviceHealthRepository(session)

        assert device.assignment is not None
        assert device.assignment.room_id == "room_restart"
        assert [item.state for item in health.timeline(
            "tenant_device_restart",
            "device_restart",
        )] == [DeviceHealthState.ONLINE, DeviceHealthState.BUFFERING]
        assert session.scalar(
            select(func.count()).select_from(DeviceRoomAssignmentRow)
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(DeviceHealthObservationRow)
        ) == 2
    second_app.state.engine.dispose()


def test_assignment_event_feedback_memory_audit_and_retries_are_durable(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'restart.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    first_app = create_app(Settings(app_env="test", database_url=database_url))
    with first_app.state.session_factory() as session:
        seed_synthetic_story(session)
    with TestClient(first_app) as first_client:
        acknowledge = _post(
            first_client,
            "acknowledge",
            "restart-ack",
            {"occurred_at": "2026-08-24T21:03:00Z"},
        )
        assert acknowledge.status_code == 200
        assert _post(
            first_client,
            "checked",
            "restart-check",
            {"occurred_at": "2026-08-24T21:04:00Z"},
        ).status_code == 200
        assert _post(
            first_client,
            "resolve",
            "restart-resolve",
            {
                "occurred_at": "2026-08-24T21:05:00Z",
                "outcome": "false_positive",
            },
        ).status_code == 200
        feedback = _post(
            first_client,
            "feedback",
            "restart-feedback",
            {
                "actual_event_label": "assisted_movement",
                "routine": True,
                "created_at": "2026-08-24T21:06:00Z",
            },
        )
        assert feedback.status_code == 200
        original_acknowledgement = acknowledge.json()
        original_feedback = feedback.json()
    first_app.state.engine.dispose()

    second_app = create_app(Settings(app_env="test", database_url=database_url))
    with TestClient(second_app) as second_client:
        replayed_acknowledgement = _post(
            second_client,
            "acknowledge",
            "restart-ack",
            {"occurred_at": "2026-08-24T21:03:00Z"},
        )
        replayed_feedback = _post(
            second_client,
            "feedback",
            "restart-feedback",
            {
                "actual_event_label": "assisted_movement",
                "routine": True,
                "created_at": "2026-08-24T21:06:00Z",
            },
        )
        memory = second_client.get(
            "/v1/residents/resident_demo_a/memory",
            headers=ACCESS_HEADERS,
        )
        status = second_client.get(
            "/v1/residents/resident_demo_a/status",
            headers=ACCESS_HEADERS,
        )
        awareness = second_client.get(
            "/v1/residents/resident_demo_a/awareness",
            headers=ACCESS_HEADERS,
        )

        assert replayed_acknowledgement.status_code == 200
        assert replayed_acknowledgement.json() == original_acknowledgement
        assert replayed_feedback.status_code == 200
        assert replayed_feedback.json() == original_feedback
        assert memory.json()["version"] == 1
        assert len(memory.json()["entries"]) == 1
        assert status.status_code == awareness.status_code == 200
        assert status.json()["monitoring"]["monitoring_state"] == "active"
        assert len(awareness.json()["items"]) == 5

        with second_app.state.session_factory() as session:
            assignment = session.scalar(
                select(RoomResidentAssignmentRow).where(
                    RoomResidentAssignmentRow.tenant_id == "tenant_demo",
                    RoomResidentAssignmentRow.room_id == "room_214",
                )
            )
            assert assignment is not None
            assert assignment.resident_id == "resident_demo_a"
            assert assignment.status == "active"
            assert session.scalar(
                select(func.count()).select_from(EventActionRow)
            ) == 4
            assert session.scalar(
                select(func.count()).select_from(EventPriorityHistoryRow)
            ) == 1
            assert session.scalar(
                select(func.count()).select_from(FeedbackRecordRow)
            ) == 1
            assert session.scalar(
                select(func.count()).select_from(ResidentMemorySnapshotRow)
            ) == 1
            assert session.scalar(
                select(func.count()).select_from(ResidentMemoryEntryRow)
            ) == 1
            assert session.scalar(
                select(func.count()).select_from(AuditLogRow)
            ) == 4
            assert session.scalar(
                select(func.count()).select_from(IdempotencyRecordRow)
            ) == 4
            assert session.scalar(
                select(func.count()).select_from(MonitoringStatusSnapshotRow)
            ) == 5
            assert session.scalar(
                select(func.count()).select_from(CalibrationSnapshotRow)
            ) == 1
    second_app.state.engine.dispose()
