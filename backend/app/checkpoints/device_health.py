"""Prove the Checkpoint B device assignment and health product story."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.config import Settings
from backend.app.db.device_repositories import DeviceHealthRepository
from backend.app.db.models import (
    DeviceHealthObservationRow,
    DeviceRoomAssignmentRow,
)
from backend.app.db.seed import DEVICE_ID, seed_synthetic_story
from backend.app.domain.device_health import (
    DeviceHealthObservation,
    DeviceHealthState,
    DeviceSourceHealth,
)
from backend.app.main import create_app


ACCESS_HEADERS = {
    "X-Tenant-Id": "tenant_demo",
    "X-Actor-Id": "operator_1",
}


def _require(condition: bool) -> None:
    if not condition:
        raise RuntimeError("checkpoint condition failed")


def _observation(
    state: DeviceHealthState,
    observed_at: datetime,
    *,
    limitations: tuple[str, ...] = (),
    wifi_state: str = "online",
    wifi_limitations: tuple[str, ...] = (),
) -> DeviceHealthObservation:
    return DeviceHealthObservation(
        device_id=DEVICE_ID,
        state=state,
        observed_at=observed_at,
        last_seen_at=observed_at - timedelta(seconds=5),
        sources=(
            DeviceSourceHealth("radar", "online"),
            DeviceSourceHealth("thermal", "online"),
            DeviceSourceHealth(
                "wifi_csi",
                wifi_state,
                wifi_limitations,
            ),
        ),
        limitations=limitations,
    )


def run_checkpoint() -> list[str]:
    project_root = Path(__file__).resolve().parents[3]
    with TemporaryDirectory() as temporary_directory:
        database_url = (
            "sqlite+pysqlite:///"
            f"{Path(temporary_directory) / 'checkpoint-b.db'}"
        )
        config = Config(str(project_root / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(config, "head")

        first_app = create_app(Settings(app_env="test", database_url=database_url))
        with first_app.state.session_factory() as session:
            seed_synthetic_story(session)

        buffering_at = datetime(2026, 8, 24, 21, 10, tzinfo=timezone.utc)
        offline_at = buffering_at + timedelta(minutes=1)
        recovery_at = buffering_at + timedelta(minutes=2)

        with TestClient(first_app) as client:
            devices = client.get("/v1/devices", headers=ACCESS_HEADERS)
            status = client.get(
                "/v1/residents/resident_demo_a/status",
                headers=ACCESS_HEADERS,
            )
            _require(devices.status_code == status.status_code == 200)
            device = devices.json()["items"][0]
            _require(device["assignment"]["room_id"] == "room_214")
            _require(device["health"]["state"] == "online")
            _require(status.json()["monitoring"]["monitoring_state"] == "active")

            with first_app.state.session_factory() as session:
                health = DeviceHealthRepository(session)
                health.record(
                    "tenant_demo",
                    _observation(
                        DeviceHealthState.BUFFERING,
                        buffering_at,
                        limitations=("upload_delayed",),
                        wifi_state="degraded",
                        wifi_limitations=("packets_buffered",),
                    ),
                )
                session.commit()
            buffering = client.get(
                f"/v1/devices/{DEVICE_ID}/health",
                headers=ACCESS_HEADERS,
            )
            buffering_status = client.get(
                "/v1/residents/resident_demo_a/status",
                headers=ACCESS_HEADERS,
            )
            _require(buffering.json()["state"] == "buffering")
            _require(
                buffering_status.json()["monitoring"]["monitoring_state"]
                == "unavailable"
            )
            _require("upload_delayed" in buffering.json()["limitations"])
            _require(
                buffering.json()["sources"][2]["limitations"]
                == ["packets_buffered"]
            )

            with first_app.state.session_factory() as session:
                health = DeviceHealthRepository(session)
                health.record(
                    "tenant_demo",
                    _observation(
                        DeviceHealthState.OFFLINE,
                        offline_at,
                        limitations=("device_not_reporting",),
                        wifi_state="offline",
                        wifi_limitations=("no_recent_packets",),
                    ),
                )
                session.commit()
            offline = client.get(
                f"/v1/devices/{DEVICE_ID}/health",
                headers=ACCESS_HEADERS,
            )
            offline_status = client.get(
                "/v1/residents/resident_demo_a/status",
                headers=ACCESS_HEADERS,
            )
            _require(offline.json()["state"] == "offline")
            _require(
                offline_status.json()["monitoring"]["monitoring_state"]
                == "unavailable"
            )

            with first_app.state.session_factory() as session:
                DeviceHealthRepository(session).record(
                    "tenant_demo",
                    _observation(DeviceHealthState.ONLINE, recovery_at),
                )
                session.commit()
            recovered = client.get(
                "/v1/residents/resident_demo_a/status",
                headers=ACCESS_HEADERS,
            )
            _require(recovered.json()["device"]["health"]["state"] == "online")
            _require(recovered.json()["monitoring"]["monitoring_state"] == "active")

        second_app = create_app(Settings(app_env="test", database_url=database_url))
        with TestClient(second_app) as client:
            devices = client.get("/v1/devices", headers=ACCESS_HEADERS)
            status = client.get(
                "/v1/residents/resident_demo_a/status",
                headers=ACCESS_HEADERS,
            )
            _require(devices.json()["items"][0]["assignment"]["room_id"] == "room_214")
            _require(devices.json()["items"][0]["health"]["state"] == "online")
            _require(status.json()["monitoring"]["monitoring_state"] == "active")
            with second_app.state.session_factory() as session:
                _require(
                    session.scalar(
                        select(func.count()).select_from(DeviceRoomAssignmentRow)
                    )
                    == 1
                )
                _require(
                    session.scalar(
                        select(func.count()).select_from(DeviceHealthObservationRow)
                    )
                    == 4
                )

    return [
        "PASS device is assigned to the resident room",
        "PASS online device allows current monitoring",
        "PASS buffering and offline states stop current monitoring",
        "PASS source limitations remain visible",
        "PASS online recovery restores current monitoring",
        "PASS assignment and health history survive restart",
        "CHECKPOINT B READY",
    ]


def main() -> int:
    try:
        lines = run_checkpoint()
    except Exception:
        print("FAIL checkpoint B story did not complete")
        return 1
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
