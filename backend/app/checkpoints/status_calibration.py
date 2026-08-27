"""Prove the Checkpoint A resident status story through the real Product API."""

from pathlib import Path
from tempfile import TemporaryDirectory

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.config import Settings
from backend.app.db.seed import seed_synthetic_story
from backend.app.db.models import (
    AuditLogRow,
    CalibrationSnapshotRow,
    IdempotencyRecordRow,
    MonitoringSetupChangeRow,
)
from backend.app.main import create_app


ACCESS_HEADERS = {
    "X-Tenant-Id": "tenant_demo",
    "X-Actor-Id": "operator_1",
}
SETUP_HEADERS = {**ACCESS_HEADERS, "Idempotency-Key": "checkpoint-a-device-move"}
SETUP_BODY = {
    "schema_version": "1.0",
    "reason": "device_moved",
    "affected_dimensions": ["movement"],
    "changed_at": "2026-08-24T22:00:00Z",
    "expected_calibration_version": 1,
}


def _require(condition: bool) -> None:
    if not condition:
        raise RuntimeError("checkpoint condition failed")


def run_checkpoint() -> list[str]:
    project_root = Path(__file__).resolve().parents[3]
    with TemporaryDirectory() as temporary_directory:
        database_url = (
            "sqlite+pysqlite:///"
            f"{Path(temporary_directory) / 'checkpoint-a.db'}"
        )
        config = Config(str(project_root / "alembic.ini"))
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

            _require(status.status_code == 200)
            _require(setup.status_code == 200)
            status_body = status.json()
            awareness_items = awareness.json()["items"]
            event_items = events.json()["items"]
            setup_body = setup.json()
            _require(status_body["monitoring"]["monitoring_state"] == "active")
            _require(
                [item["presence_state"] for item in awareness_items]
                == [
                    "resident_present",
                    "resident_away",
                    "resident_present",
                    "possible_multi_person",
                    "resident_present",
                ]
            )
            _require(
                all(
                    item["objective_family"] != "resident_away"
                    for item in event_items
                )
            )
            _require(awareness_items[2]["monitoring_state"] == "active")
            _require(awareness_items[3]["monitoring_state"] == "limited")
            _require(awareness_items[3]["baseline_learning_allowed"] is False)
            _require(
                {
                    item["dimension"]: item["status"]
                    for item in setup_body["dimensions"]
                }
                == {
                    "movement": "calibrating",
                    "respiratory_rate": "established",
                }
            )

        second_app = create_app(Settings(app_env="test", database_url=database_url))
        with TestClient(second_app) as client:
            calibration = client.get(
                "/v1/residents/resident_demo_a/calibration",
                headers=ACCESS_HEADERS,
            )
            awareness = client.get(
                "/v1/residents/resident_demo_a/awareness",
                headers=ACCESS_HEADERS,
            )
            replay = client.post(
                "/v1/residents/resident_demo_a/setup-changes",
                headers=SETUP_HEADERS,
                json=SETUP_BODY,
            )
            _require(calibration.status_code == replay.status_code == 200)
            _require(calibration.json() == replay.json() == setup_body)
            _require(len(calibration.json()["setup_changes"]) == 1)
            _require(len(awareness.json()["items"]) == 5)
            with second_app.state.session_factory() as session:
                _require(
                    session.scalar(
                        select(func.count()).select_from(CalibrationSnapshotRow)
                    )
                    == 2
                )
                _require(
                    session.scalar(
                        select(func.count()).select_from(MonitoringSetupChangeRow)
                    )
                    == 1
                )
                _require(
                    session.scalar(select(func.count()).select_from(AuditLogRow))
                    == 1
                )
                _require(
                    session.scalar(
                        select(func.count()).select_from(IdempotencyRecordRow)
                    )
                    == 1
                )

    return [
        "PASS resident active monitoring is available",
        "PASS resident away is awareness, not a warning",
        "PASS resident return resumes monitoring",
        "PASS possible multi-person state limits learning",
        "PASS setup change recalibrates only movement",
        "PASS status and calibration survive restart",
        "CHECKPOINT A READY",
    ]


def main() -> int:
    try:
        lines = run_checkpoint()
    except Exception:
        print("FAIL checkpoint A story did not complete")
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
