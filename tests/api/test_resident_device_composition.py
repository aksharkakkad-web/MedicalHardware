from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from backend.app.db.device_repositories import DeviceHealthRepository
from backend.app.db.models import (
    DeviceHealthObservationRow,
    DeviceRoomAssignmentRow,
)
from backend.app.domain.device_health import (
    DeviceHealthObservation,
    DeviceHealthState,
    DeviceSourceHealth,
)


ACCESS_HEADERS = {
    "X-Tenant-Id": "tenant_demo",
    "X-Actor-Id": "operator_1",
}
OBSERVED_AT = datetime(2026, 8, 25, 15, 0, tzinfo=timezone.utc)


def _record_health(api_client: TestClient, state: DeviceHealthState) -> None:
    with api_client.app.state.session_factory() as session:
        DeviceHealthRepository(session).record(
            "tenant_demo",
            DeviceHealthObservation(
                device_id="device_room_214",
                state=state,
                observed_at=OBSERVED_AT,
                last_seen_at=OBSERVED_AT - timedelta(seconds=5),
                sources=(DeviceSourceHealth("radar", "online"),),
                limitations=(() if state is DeviceHealthState.ONLINE else ("delayed",)),
            ),
        )
        session.commit()


def test_online_device_is_composed_into_active_resident_status(
    api_client: TestClient,
) -> None:
    response = api_client.get(
        "/v1/residents/resident_demo_a/status",
        headers=ACCESS_HEADERS,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data_availability"] == "available"
    assert body["device_assignment_state"] == "assigned"
    assert body["device"]["device_id"] == "device_room_214"
    assert body["device"]["assignment"]["room_id"] == "room_214"
    assert body["device"]["health"]["state"] == "online"
    assert body["monitoring"]["monitoring_state"] == "active"


@pytest.mark.parametrize(
    "state",
    (
        DeviceHealthState.OFFLINE,
        DeviceHealthState.DEGRADED,
        DeviceHealthState.BUFFERING,
        DeviceHealthState.RETRYING,
    ),
)
def test_non_online_device_makes_current_monitoring_unavailable_not_history(
    api_client: TestClient,
    state: DeviceHealthState,
) -> None:
    events_before = api_client.get(
        "/v1/residents/resident_demo_a/events",
        headers=ACCESS_HEADERS,
    ).json()["items"]
    _record_health(api_client, state)

    status = api_client.get(
        "/v1/residents/resident_demo_a/status",
        headers=ACCESS_HEADERS,
    )
    awareness = api_client.get(
        "/v1/residents/resident_demo_a/awareness",
        headers=ACCESS_HEADERS,
    )
    events_after = api_client.get(
        "/v1/residents/resident_demo_a/events",
        headers=ACCESS_HEADERS,
    ).json()["items"]

    assert status.status_code == awareness.status_code == 200
    assert status.json()["device"]["health"]["state"] == state.value
    assert status.json()["monitoring"]["monitoring_state"] == "unavailable"
    assert status.json()["monitoring"]["baseline_learning_allowed"] is False
    assert status.json()["monitoring"]["resident_measurements_allowed"] is False
    assert "device_unhealthy" in status.json()["monitoring"]["reasons"]
    assert awareness.json()["items"][-1]["monitoring_state"] == "active"
    assert events_after == events_before


def test_online_recovery_restores_latest_valid_monitoring_view(
    api_client: TestClient,
) -> None:
    _record_health(api_client, DeviceHealthState.OFFLINE)
    with api_client.app.state.session_factory() as session:
        DeviceHealthRepository(session).record(
            "tenant_demo",
            DeviceHealthObservation(
                device_id="device_room_214",
                state=DeviceHealthState.ONLINE,
                observed_at=OBSERVED_AT + timedelta(minutes=1),
                last_seen_at=OBSERVED_AT + timedelta(minutes=1),
                sources=(DeviceSourceHealth("radar", "online"),),
                limitations=(),
            ),
        )
        session.commit()

    status = api_client.get(
        "/v1/residents/resident_demo_a/status",
        headers=ACCESS_HEADERS,
    ).json()

    assert status["device"]["health"]["state"] == "online"
    assert status["monitoring"]["monitoring_state"] == "active"
    assert status["monitoring"]["reasons"] == []


def test_missing_health_is_explicit_and_never_treated_as_online(
    api_client: TestClient,
) -> None:
    with api_client.app.state.session_factory() as session:
        session.execute(delete(DeviceHealthObservationRow))
        session.commit()

    status = api_client.get(
        "/v1/residents/resident_demo_a/status",
        headers=ACCESS_HEADERS,
    ).json()

    assert status["data_availability"] == "partial"
    assert "device_health_not_yet_available" in status["unavailable_reasons"]
    assert status["device"]["health"]["data_availability"] == "not_yet_available"
    assert status["monitoring"]["monitoring_state"] == "unavailable"
    assert "device_health_unavailable" in status["monitoring"]["reasons"]


def test_missing_device_assignment_is_explicit_and_never_guessed(
    api_client: TestClient,
) -> None:
    with api_client.app.state.session_factory() as session:
        assignment = session.scalar(
            select(DeviceRoomAssignmentRow).where(
                DeviceRoomAssignmentRow.device_id == "device_room_214"
            )
        )
        assert assignment is not None
        assignment.status = "inactive"
        assignment.effective_to = OBSERVED_AT
        session.commit()

    status = api_client.get(
        "/v1/residents/resident_demo_a/status",
        headers=ACCESS_HEADERS,
    ).json()

    assert status["data_availability"] == "partial"
    assert status["device_assignment_state"] == "assignment_unavailable"
    assert "device_assignment_unavailable" in status["unavailable_reasons"]
    assert status["device"] is None
    assert status["monitoring"]["monitoring_state"] == "unavailable"
    assert "assignment_invalid" in status["monitoring"]["reasons"]
