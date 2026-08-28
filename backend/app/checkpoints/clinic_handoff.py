"""Prove the complete Checkpoint D clinic Product API handoff story."""

from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.db.mappers import event_to_rows
from backend.app.db.models import (
    ResidentRow,
    RoomResidentAssignmentRow,
    RoomRow,
)
from backend.app.db.seed import seed_synthetic_story
from backend.app.domain.events import EventPriority, EventStatus, MonitoringEvent
from backend.app.main import create_app


ACCESS_HEADERS = {
    "X-Tenant-Id": "tenant_demo",
    "X-Actor-Id": "operator_1",
}
RESIDENT_ID = "resident_demo_a"
SECOND_RESIDENT_ID = "resident_demo_b"
RESIDENT_PATH = f"/v1/residents/{RESIDENT_ID}"
EVENT_ID = "evt_phase2_demo"
EVENT_PATH = f"/v1/events/{EVENT_ID}"


def _require(condition: bool) -> None:
    if not condition:
        raise RuntimeError("checkpoint condition failed")


def _seed_queue_events(app) -> None:
    base = datetime(2026, 8, 24, 22, 0, tzinfo=timezone.utc)
    events = (
        MonitoringEvent(
            event_id="evt_handoff_critical",
            episode_id="episode_handoff_critical",
            resident_id=SECOND_RESIDENT_ID,
            room_id="room_302",
            objective_family="unknown_anomaly",
            headline="Critical synthetic attention",
            priority=EventPriority.CRITICAL,
            status=EventStatus.OPEN,
            created_at=base,
            last_signal_at=base,
        ),
        MonitoringEvent(
            event_id="evt_handoff_watch",
            episode_id="episode_handoff_watch",
            resident_id=RESIDENT_ID,
            room_id="room_214",
            objective_family="repetitive_movement",
            headline="Watch synthetic attention",
            priority=EventPriority.WATCH,
            status=EventStatus.ACKNOWLEDGED,
            created_at=base + timedelta(minutes=1),
            last_signal_at=base + timedelta(minutes=1),
        ),
    )
    with app.state.session_factory() as session:
        for event in events:
            bundle = event_to_rows("tenant_demo", event, version=1)
            session.add(bundle.event)
            session.flush()
            session.add_all(bundle.actions)
            session.add_all(bundle.priorities)
        session.commit()


def _seed_second_resident(app) -> None:
    with app.state.session_factory() as session:
        session.add(
            RoomRow(
                room_id="room_302",
                tenant_id="tenant_demo",
                label="Room 302",
            )
        )
        session.add(
            ResidentRow(
                resident_id=SECOND_RESIDENT_ID,
                tenant_id="tenant_demo",
                display_label="Resident B",
            )
        )
        session.flush()
        session.add(
            RoomResidentAssignmentRow(
                assignment_id="assign_room_302_b",
                tenant_id="tenant_demo",
                room_id="room_302",
                resident_id=SECOND_RESIDENT_ID,
                status="active",
                effective_from=datetime(2026, 8, 24, tzinfo=timezone.utc),
                effective_to=None,
            )
        )
        session.commit()


def _event_action(
    client: TestClient,
    action: str,
    occurred_at: str,
    index: int,
    *,
    outcome: str | None = None,
):
    body = {"schema_version": "1.0", "occurred_at": occurred_at}
    if outcome is not None:
        body["outcome"] = outcome
    return client.post(
        f"{EVENT_PATH}/{action}",
        headers={
            **ACCESS_HEADERS,
            "Idempotency-Key": f"checkpoint-d-event-{index}",
        },
        json=body,
    )


def run_checkpoint() -> list[str]:
    project_root = Path(__file__).resolve().parents[3]
    with TemporaryDirectory() as temporary_directory:
        database_url = (
            "sqlite+pysqlite:///"
            f"{Path(temporary_directory) / 'checkpoint-d.db'}"
        )
        config = Config(str(project_root / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(config, "head")

        first_app = create_app(Settings(app_env="test", database_url=database_url))
        with first_app.state.session_factory() as session:
            seed_synthetic_story(session)
        _seed_second_resident(first_app)
        _seed_queue_events(first_app)

        with TestClient(first_app) as client:
            residents = client.get("/v1/residents", headers=ACCESS_HEADERS)
            status = client.get(f"{RESIDENT_PATH}/status", headers=ACCESS_HEADERS)
            second_status = client.get(
                f"/v1/residents/{SECOND_RESIDENT_ID}/status",
                headers=ACCESS_HEADERS,
            )
            devices = client.get("/v1/devices", headers=ACCESS_HEADERS)
            _require(
                residents.status_code
                == status.status_code
                == second_status.status_code
                == devices.status_code
                == 200
            )
            _require(len(residents.json()["items"]) == 2)
            _require(residents.json()["items"][0]["room_id"] == "room_214")
            _require(status.json()["monitoring"]["monitoring_state"] == "active")
            _require(status.json()["device"]["health"]["state"] == "online")
            _require(second_status.json()["data_availability"] == "not_yet_available")
            _require(
                second_status.json()["device_assignment_state"]
                == "assignment_unavailable"
            )

            first_page = client.get(
                "/v1/events",
                params={"limit": 2},
                headers=ACCESS_HEADERS,
            )
            _require(first_page.status_code == 200)
            _require(first_page.json()["total_items"] == 3)
            _require(
                [item["event_id"] for item in first_page.json()["items"]]
                == ["evt_handoff_critical", EVENT_ID]
            )
            second_page = client.get(
                "/v1/events",
                params={
                    "limit": 2,
                    "cursor": first_page.json()["next_cursor"],
                },
                headers=ACCESS_HEADERS,
            )
            _require(
                [item["event_id"] for item in second_page.json()["items"]]
                == ["evt_handoff_watch"]
            )
            complete_queue = (
                first_page.json()["items"] + second_page.json()["items"]
            )
            attention_counts = Counter(
                item["resident_id"] for item in complete_queue
            )
            _require(attention_counts == {RESIDENT_ID: 2, SECOND_RESIDENT_ID: 1})
            _require(complete_queue[0]["resident_id"] == SECOND_RESIDENT_ID)
            _require(complete_queue[0]["headline"] == "Critical synthetic attention")

            actions = (
                _event_action(client, "acknowledge", "2026-08-24T21:03:00Z", 1),
                _event_action(client, "checked", "2026-08-24T21:04:00Z", 2),
                _event_action(
                    client,
                    "resolve",
                    "2026-08-24T21:05:00Z",
                    3,
                    outcome="false_positive",
                ),
            )
            _require(all(response.status_code == 200 for response in actions))
            active = client.get("/v1/events", headers=ACCESS_HEADERS)
            resolved = client.get(
                "/v1/events",
                params={"status": "resolved"},
                headers=ACCESS_HEADERS,
            )
            _require(active.json()["total_items"] == 2)
            _require(
                [item["event_id"] for item in resolved.json()["items"]]
                == [EVENT_ID]
            )

            feedback = client.post(
                f"{EVENT_PATH}/feedback",
                headers={
                    **ACCESS_HEADERS,
                    "Idempotency-Key": "checkpoint-d-feedback",
                },
                json={
                    "schema_version": "1.0",
                    "actual_event_label": "assisted_movement",
                    "routine": True,
                    "created_at": "2026-08-24T21:06:00Z",
                },
            )
            _require(feedback.status_code == 200)
            _require(feedback.json()["memory_updated"] is True)

            preferences = client.put(
                f"{RESIDENT_PATH}/notification-preferences",
                headers={
                    **ACCESS_HEADERS,
                    "Idempotency-Key": "checkpoint-d-preferences",
                },
                json={
                    "schema_version": "1.0",
                    "expected_version": 0,
                    "event_delivery": {
                        "watch": False,
                        "high": False,
                        "critical": False,
                    },
                    "awareness_delivery": {
                        "away": True,
                        "return": True,
                        "limited": False,
                        "unavailable": True,
                    },
                    "changed_at": "2026-08-25T15:00:00Z",
                },
            )
            urgent = client.get(
                "/v1/events",
                params={"priority": "critical"},
                headers=ACCESS_HEADERS,
            )
            _require(preferences.status_code == urgent.status_code == 200)
            _require(preferences.json()["event_delivery"]["critical"] is False)
            _require(urgent.json()["items"][0]["event_id"] == "evt_handoff_critical")

            memory = client.post(
                f"{RESIDENT_PATH}/memory/entries",
                headers={
                    **ACCESS_HEADERS,
                    "Idempotency-Key": "checkpoint-d-memory",
                },
                json={
                    "schema_version": "1.0",
                    "expected_version": 1,
                    "description": "Morning movement is commonly assisted.",
                    "changed_at": "2026-08-25T15:10:00Z",
                },
            )
            _require(memory.status_code == 200)
            _require(memory.json()["version"] == 2)
            _require(
                {entry["source_kind"] for entry in memory.json()["entries"]}
                == {"feedback", "operator"}
            )

            awareness = client.get(
                f"{RESIDENT_PATH}/awareness",
                headers=ACCESS_HEADERS,
            )
            calibration = client.post(
                f"{RESIDENT_PATH}/setup-changes",
                headers={
                    **ACCESS_HEADERS,
                    "Idempotency-Key": "checkpoint-d-setup",
                },
                json={
                    "schema_version": "1.0",
                    "reason": "Synthetic monitor position changed.",
                    "affected_dimensions": ["movement"],
                    "changed_at": "2026-08-25T15:20:00Z",
                    "expected_calibration_version": 1,
                },
            )
            _require(awareness.status_code == calibration.status_code == 200)
            _require(len(awareness.json()["items"]) == 5)
            _require(calibration.json()["version"] == 2)
            _require(calibration.json()["dimensions"][0]["status"] == "calibrating")

            committed_openapi = json.loads(
                (project_root / "docs/openapi/product-api-v1.json").read_text(
                    encoding="utf-8"
                )
            )
            _require(client.get("/openapi.json").json() == committed_openapi)

        second_app = create_app(Settings(app_env="test", database_url=database_url))
        with TestClient(second_app) as client:
            durable_reads = {
                "residents": client.get("/v1/residents", headers=ACCESS_HEADERS),
                "status": client.get(f"{RESIDENT_PATH}/status", headers=ACCESS_HEADERS),
                "second_status": client.get(
                    f"/v1/residents/{SECOND_RESIDENT_ID}/status",
                    headers=ACCESS_HEADERS,
                ),
                "events": client.get("/v1/events", headers=ACCESS_HEADERS),
                "history": client.get(
                    "/v1/events",
                    params={"status": "resolved"},
                    headers=ACCESS_HEADERS,
                ),
                "devices": client.get("/v1/devices", headers=ACCESS_HEADERS),
                "awareness": client.get(
                    f"{RESIDENT_PATH}/awareness",
                    headers=ACCESS_HEADERS,
                ),
                "calibration": client.get(
                    f"{RESIDENT_PATH}/calibration",
                    headers=ACCESS_HEADERS,
                ),
                "preferences": client.get(
                    f"{RESIDENT_PATH}/notification-preferences",
                    headers=ACCESS_HEADERS,
                ),
                "memory": client.get(
                    f"{RESIDENT_PATH}/memory",
                    headers=ACCESS_HEADERS,
                ),
            }
            _require(all(response.status_code == 200 for response in durable_reads.values()))
            _require(len(durable_reads["residents"].json()["items"]) == 2)
            _require(
                durable_reads["second_status"].json()["data_availability"]
                == "not_yet_available"
            )
            _require(durable_reads["events"].json()["total_items"] == 2)
            durable_counts = Counter(
                item["resident_id"]
                for item in durable_reads["events"].json()["items"]
            )
            _require(durable_counts == {RESIDENT_ID: 1, SECOND_RESIDENT_ID: 1})
            _require(durable_reads["history"].json()["items"][0]["event_id"] == EVENT_ID)
            _require(durable_reads["calibration"].json()["version"] == 2)
            _require(durable_reads["preferences"].json()["version"] == 1)
            _require(durable_reads["memory"].json()["version"] == 2)

    return [
        "PASS clinic overview composes residents, monitoring, and device state",
        "PASS multiple rooms keep resident attention correctly separated",
        "PASS active events filter and page in caregiver attention order",
        "PASS lifecycle moves resolved events into preserved history",
        "PASS delivery preferences never hide urgent dashboard events",
        "PASS feedback and staff edits preserve resident context",
        "PASS awareness and selective calibration history stay available",
        "PASS generated OpenAPI represents the real Product API",
        "PASS the complete clinic API story survives restart",
        "CHECKPOINT D READY",
    ]


def main() -> int:
    try:
        lines = run_checkpoint()
    except Exception:
        print("FAIL checkpoint D clinic handoff did not complete")
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
