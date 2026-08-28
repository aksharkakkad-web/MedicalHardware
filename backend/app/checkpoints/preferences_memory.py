"""Prove the Checkpoint C resident-controls product story."""

from pathlib import Path
from tempfile import TemporaryDirectory

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.config import Settings
from backend.app.db.models import (
    AuditLogRow,
    IdempotencyRecordRow,
    ResidentMemoryEntryRow,
    ResidentMemorySnapshotRow,
    ResidentNotificationPreferenceVersionRow,
)
from backend.app.db.seed import seed_synthetic_story
from backend.app.main import create_app


ACCESS_HEADERS = {
    "X-Tenant-Id": "tenant_demo",
    "X-Actor-Id": "operator_1",
}
RESIDENT_PATH = "/v1/residents/resident_demo_a"
PREFERENCE_PATH = f"{RESIDENT_PATH}/notification-preferences"
MEMORY_PATH = f"{RESIDENT_PATH}/memory"
PREFERENCE_HEADERS = {
    **ACCESS_HEADERS,
    "Idempotency-Key": "checkpoint-c-preferences",
}
PREFERENCE_BODY = {
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
}


def _require(condition: bool) -> None:
    if not condition:
        raise RuntimeError("checkpoint condition failed")


def run_checkpoint() -> list[str]:
    project_root = Path(__file__).resolve().parents[3]
    with TemporaryDirectory() as temporary_directory:
        database_url = (
            "sqlite+pysqlite:///"
            f"{Path(temporary_directory) / 'checkpoint-c.db'}"
        )
        config = Config(str(project_root / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(config, "head")

        first_app = create_app(Settings(app_env="test", database_url=database_url))
        with first_app.state.session_factory() as session:
            seed_synthetic_story(session)

        with TestClient(first_app) as client:
            missing = client.get(PREFERENCE_PATH, headers=ACCESS_HEADERS)
            _require(missing.status_code == 200)
            _require(missing.json()["data_availability"] == "not_yet_available")

            preferences = client.put(
                PREFERENCE_PATH,
                headers=PREFERENCE_HEADERS,
                json=PREFERENCE_BODY,
            )
            events = client.get(
                f"{RESIDENT_PATH}/events",
                headers=ACCESS_HEADERS,
            )
            _require(preferences.status_code == events.status_code == 200)
            _require(
                preferences.json()["high_critical_dashboard_visibility"]
                == "always_visible"
            )
            _require(preferences.json()["event_delivery"]["high"] is False)
            _require(
                any(
                    event["priority"] == "high"
                    for event in events.json()["items"]
                )
            )

            added = client.post(
                f"{MEMORY_PATH}/entries",
                headers={
                    **ACCESS_HEADERS,
                    "Idempotency-Key": "checkpoint-c-memory-add",
                },
                json={
                    "schema_version": "1.0",
                    "expected_version": 0,
                    "description": "Assisted standing is common before breakfast.",
                    "changed_at": "2026-08-25T15:10:00Z",
                },
            )
            _require(added.status_code == 200)
            original = added.json()["entries"][0]
            _require(original["source_kind"] == "operator")
            _require(original["source_feedback_id"] is None)

            corrected = client.post(
                f"{MEMORY_PATH}/entries/{original['entry_id']}/correct",
                headers={
                    **ACCESS_HEADERS,
                    "Idempotency-Key": "checkpoint-c-memory-correct",
                },
                json={
                    "schema_version": "1.0",
                    "expected_version": 1,
                    "description": "Assisted standing is common after breakfast.",
                    "reason": "The routine time was entered incorrectly.",
                    "changed_at": "2026-08-25T15:20:00Z",
                },
            )
            _require(corrected.status_code == 200)
            corrected_body = corrected.json()
            replacement = corrected_body["entries"][-1]
            _require(corrected_body["entries"][0]["status"] == "retired")
            _require(replacement["supersedes_entry_id"] == original["entry_id"])

            retired = client.post(
                f"{MEMORY_PATH}/entries/{replacement['entry_id']}/retire",
                headers={
                    **ACCESS_HEADERS,
                    "Idempotency-Key": "checkpoint-c-memory-retire",
                },
                json={
                    "schema_version": "1.0",
                    "expected_version": 2,
                    "reason": "This routine is no longer current.",
                    "changed_at": "2026-08-25T15:30:00Z",
                },
            )
            _require(retired.status_code == 200)
            retired_body = retired.json()
            _require(retired_body["version"] == 3)
            _require(
                all(entry["status"] == "retired" for entry in retired_body["entries"])
            )

        second_app = create_app(Settings(app_env="test", database_url=database_url))
        with TestClient(second_app) as client:
            preferences = client.get(PREFERENCE_PATH, headers=ACCESS_HEADERS)
            memory = client.get(MEMORY_PATH, headers=ACCESS_HEADERS)
            replay = client.put(
                PREFERENCE_PATH,
                headers=PREFERENCE_HEADERS,
                json=PREFERENCE_BODY,
            )
            _require(preferences.status_code == memory.status_code == replay.status_code == 200)
            _require(preferences.json() == replay.json())
            _require(memory.json() == retired_body)
            with second_app.state.session_factory() as session:
                _require(
                    session.scalar(
                        select(func.count()).select_from(
                            ResidentNotificationPreferenceVersionRow
                        )
                    )
                    == 1
                )
                _require(
                    session.scalar(
                        select(func.count()).select_from(ResidentMemorySnapshotRow)
                    )
                    == 3
                )
                _require(
                    session.scalar(
                        select(func.count()).select_from(ResidentMemoryEntryRow)
                    )
                    == 5
                )
                _require(
                    session.scalar(select(func.count()).select_from(AuditLogRow))
                    == 4
                )
                _require(
                    session.scalar(
                        select(func.count()).select_from(IdempotencyRecordRow)
                    )
                    == 4
                )

    return [
        "PASS unconfigured preferences are shown honestly",
        "PASS delivery choices never hide high or critical dashboard events",
        "PASS staff can add resident context with honest provenance",
        "PASS correction preserves and links the superseded context",
        "PASS retirement preserves all resident-memory history",
        "PASS preferences and resident memory survive restart",
        "CHECKPOINT C READY",
    ]


def main() -> int:
    try:
        lines = run_checkpoint()
    except Exception:
        print("FAIL checkpoint C story did not complete")
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
