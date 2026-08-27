from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

from backend.app.config import Settings
from backend.app.db.seed import seed_synthetic_story
from backend.app.main import create_app


ACCESS_HEADERS = {
    "X-Tenant-Id": "tenant_demo",
    "X-Actor-Id": "operator_1",
}
EVENT_PATH = "/v1/events/evt_phase2_demo"


def _migrate(database_url: str) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")


@contextmanager
def _product_client(
    database_url: str,
    *,
    seed: bool,
) -> Iterator[tuple[TestClient, FastAPI]]:
    _migrate(database_url)
    app = create_app(Settings(app_env="test", database_url=database_url))
    if seed:
        with app.state.session_factory() as session:
            seed_synthetic_story(session)

    try:
        with TestClient(app) as client:
            yield client, app
    finally:
        app.state.engine.dispose()


def _post_action(
    client: TestClient,
    action: str,
    key: str,
    occurred_at: str,
) -> Response:
    return client.post(
        f"{EVENT_PATH}/{action}",
        headers={**ACCESS_HEADERS, "Idempotency-Key": key},
        json={"occurred_at": occurred_at},
    )


def _resolve_event(client: TestClient, key: str) -> Response:
    return client.post(
        f"{EVENT_PATH}/resolve",
        headers={**ACCESS_HEADERS, "Idempotency-Key": key},
        json={
            "occurred_at": "2026-08-24T21:05:00Z",
            "outcome": "false_positive",
        },
    )


def _submit_feedback(client: TestClient, key: str) -> Response:
    return client.post(
        f"{EVENT_PATH}/feedback",
        headers={**ACCESS_HEADERS, "Idempotency-Key": key},
        json={
            "actual_event_label": "assisted_movement",
            "routine": True,
            "created_at": "2026-08-24T21:06:00Z",
        },
    )


def test_complete_synthetic_caregiver_story_survives_application_restart(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'product-story.db'}"

    with _product_client(database_url, seed=True) as (first_client, first_app):
        resident = first_client.get(
            "/v1/residents/resident_demo_a",
            headers=ACCESS_HEADERS,
        )
        opened = first_client.get(EVENT_PATH, headers=ACCESS_HEADERS)
        acknowledged = _post_action(
            first_client,
            "acknowledge",
            "ack-final",
            "2026-08-24T21:03:00Z",
        )
        checked = _post_action(
            first_client,
            "checked",
            "check-final",
            "2026-08-24T21:04:00Z",
        )
        resolved = _resolve_event(first_client, "resolve-final")
        feedback = _submit_feedback(first_client, "feedback-final")
        memory = first_client.get(
            "/v1/residents/resident_demo_a/memory",
            headers=ACCESS_HEADERS,
        )
        first_engine = first_app.state.engine

        assert resident.status_code == 200
        assert resident.json() == {
            "schema_version": "1.0",
            "resident_id": "resident_demo_a",
            "display_label": "Resident A",
            "room_id": "room_214",
            "room_label": "Room 214",
            "assignment_status": "active",
        }
        assert opened.status_code == 200
        assert opened.json()["status"] == "open"
        assert acknowledged.status_code == checked.status_code == 200
        assert acknowledged.json()["status"] == "acknowledged"
        assert checked.json()["status"] == "checked"
        assert resolved.status_code == 200
        assert resolved.json()["status"] == "resolved"
        assert resolved.json()["resolution_outcome"] == "false_positive"
        assert feedback.status_code == 200
        assert feedback.json()["feedback"]["actual_event_label"] == (
            "assisted_movement"
        )
        assert feedback.json()["memory_updated"] is True
        assert memory.status_code == 200
        assert memory.json()["version"] == 1
        assert memory.json()["entries"][0]["description"] == "assisted_movement"

    with _product_client(database_url, seed=False) as (second_client, second_app):
        recovered_resident = second_client.get(
            "/v1/residents/resident_demo_a",
            headers=ACCESS_HEADERS,
        )
        recovered_event = second_client.get(EVENT_PATH, headers=ACCESS_HEADERS)
        recovered_memory = second_client.get(
            "/v1/residents/resident_demo_a/memory",
            headers=ACCESS_HEADERS,
        )

        assert second_app.state.engine is not first_engine
        assert recovered_resident.json()["room_id"] == "room_214"
        assert recovered_resident.json()["assignment_status"] == "active"
        assert recovered_event.json()["status"] == "resolved"
        assert [
            item["action"] for item in recovered_event.json()["action_history"]
        ] == ["opened", "acknowledged", "checked", "resolved"]
        assert recovered_event.json()["resolution_outcome"] == "false_positive"
        assert recovered_memory.json()["version"] == 1
        assert recovered_memory.json()["entries"][0]["description"] == (
            "assisted_movement"
        )

        invalid_transition = _post_action(
            second_client,
            "acknowledge",
            "ack-after-resolution",
            "2026-08-24T21:07:00Z",
        )
        replay = _post_action(
            second_client,
            "acknowledge",
            "ack-final",
            "2026-08-24T21:03:00Z",
        )
        conflict = _post_action(
            second_client,
            "acknowledge",
            "ack-final",
            "2026-08-24T21:03:01Z",
        )
        hidden_from_other_tenant = second_client.get(
            EVENT_PATH,
            headers={
                "X-Tenant-Id": "tenant_other",
                "X-Actor-Id": "operator_other",
            },
        )

        assert invalid_transition.status_code == 409
        assert invalid_transition.json()["error"]["code"] == "invalid_transition"
        assert replay.status_code == 200
        assert replay.json()["status"] == "acknowledged"
        assert len(replay.json()["action_history"]) == 2
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "idempotency_conflict"
        assert hidden_from_other_tenant.status_code == 404
        assert hidden_from_other_tenant.json() == {
            "schema_version": "1.0",
            "error": {
                "code": "not_found",
                "message": "Resource not found",
                "field": None,
            },
        }
