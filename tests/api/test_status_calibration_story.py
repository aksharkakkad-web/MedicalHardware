from pathlib import Path
import subprocess
import sys

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.db.seed import seed_synthetic_story
from backend.app.main import create_app


ACCESS_HEADERS = {
    "X-Tenant-Id": "tenant_demo",
    "X-Actor-Id": "operator_1",
}
SETUP_HEADERS = {**ACCESS_HEADERS, "Idempotency-Key": "story-device-move"}
SETUP_BODY = {
    "schema_version": "1.0",
    "reason": "device_moved",
    "affected_dimensions": ["movement"],
    "changed_at": "2026-08-24T22:00:00Z",
    "expected_calibration_version": 1,
}


def test_seeded_status_calibration_story_survives_restart(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'status-story.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    first_app = create_app(Settings(app_env="test", database_url=database_url))
    with first_app.state.session_factory() as session:
        seed_synthetic_story(session)
    with TestClient(first_app) as client:
        status = client.get(
            "/v1/residents/resident_demo_a/status",
            headers=ACCESS_HEADERS,
        )
        awareness = client.get(
            "/v1/residents/resident_demo_a/awareness",
            headers=ACCESS_HEADERS,
        )
        events = client.get(
            "/v1/residents/resident_demo_a/events",
            headers=ACCESS_HEADERS,
        )
        setup = client.post(
            "/v1/residents/resident_demo_a/setup-changes",
            headers=SETUP_HEADERS,
            json=SETUP_BODY,
        )

        assert status.status_code == setup.status_code == 200
        assert status.json()["monitoring"]["monitoring_state"] == "active"
        assert [item["presence_state"] for item in awareness.json()["items"]] == [
            "resident_present",
            "resident_away",
            "resident_present",
            "possible_multi_person",
            "resident_present",
        ]
        assert awareness.json()["items"][3]["monitoring_state"] == "limited"
        assert awareness.json()["items"][3]["baseline_learning_allowed"] is False
        assert all(
            item["objective_family"] != "resident_away"
            for item in events.json()["items"]
        )
        assert setup.json()["version"] == 2
        assert {
            item["dimension"]: item["status"]
            for item in setup.json()["dimensions"]
        } == {
            "movement": "calibrating",
            "respiratory_rate": "established",
        }
        original_setup = setup.json()

    second_app = create_app(Settings(app_env="test", database_url=database_url))
    with TestClient(second_app) as client:
        replay = client.post(
            "/v1/residents/resident_demo_a/setup-changes",
            headers=SETUP_HEADERS,
            json=SETUP_BODY,
        )
        calibration = client.get(
            "/v1/residents/resident_demo_a/calibration",
            headers=ACCESS_HEADERS,
        )
        awareness = client.get(
            "/v1/residents/resident_demo_a/awareness",
            headers=ACCESS_HEADERS,
        )

        assert replay.status_code == calibration.status_code == 200
        assert replay.json() == original_setup
        assert calibration.json() == original_setup
        assert len(calibration.json()["setup_changes"]) == 1
        assert len(awareness.json()["items"]) == 5


def test_founder_checkpoint_command_prints_plain_language_proof() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "backend.app.checkpoints.status_calibration"],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stdout.splitlines() == [
        "PASS resident active monitoring is available",
        "PASS resident away is awareness, not a warning",
        "PASS resident return resumes monitoring",
        "PASS possible multi-person state limits learning",
        "PASS setup change recalibrates only movement",
        "PASS status and calibration survive restart",
        "CHECKPOINT A READY",
    ]
