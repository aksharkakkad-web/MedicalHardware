from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import func, select

from backend.app.config import Settings
from backend.app.db.models import (
    AuditLogRow,
    EventActionRow,
    FeedbackRecordRow,
    IdempotencyRecordRow,
    ResidentMemoryEntryRow,
    ResidentMemorySnapshotRow,
    RoomResidentAssignmentRow,
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
        json=body,
    )


def test_application_shutdown_disposes_its_process_engine(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'engine-lifecycle.db'}"
    app = create_app(Settings(app_env="test", database_url=database_url))
    process_pool = app.state.engine.pool

    with TestClient(app):
        pass

    assert app.state.engine.pool is not process_pool


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

        assert replayed_acknowledgement.status_code == 200
        assert replayed_acknowledgement.json() == original_acknowledgement
        assert replayed_feedback.status_code == 200
        assert replayed_feedback.json() == original_feedback
        assert memory.json()["version"] == 1
        assert len(memory.json()["entries"]) == 1

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
    second_app.state.engine.dispose()
