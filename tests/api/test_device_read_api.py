from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.db.device_repositories import DeviceHealthRepository
from backend.app.db.models import (
    DeviceRoomAssignmentRow,
    DeviceRow,
    LocationRow,
    RoomRow,
    TenantRow,
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
OBSERVED_AT = datetime(2026, 8, 25, 14, 0, tzinfo=timezone.utc)


def _seed_device_reads(api_client: TestClient) -> None:
    with api_client.app.state.session_factory() as session:
        session.add(
            LocationRow(
                location_id="location_demo",
                tenant_id="tenant_demo",
                label="Demo clinic",
            )
        )
        session.add_all(
            [
                DeviceRow(
                    device_id="device_room_214",
                    tenant_id="tenant_demo",
                    display_label="Room 214 monitor",
                ),
                DeviceRow(
                    device_id="device_spare",
                    tenant_id="tenant_demo",
                    display_label="Spare monitor",
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
        DeviceHealthRepository(session).record(
            "tenant_demo",
            DeviceHealthObservation(
                device_id="device_room_214",
                state=DeviceHealthState.DEGRADED,
                observed_at=OBSERVED_AT,
                last_seen_at=OBSERVED_AT - timedelta(seconds=5),
                sources=(
                    DeviceSourceHealth("radar", "online"),
                    DeviceSourceHealth(
                        "thermal",
                        "degraded",
                        ("reduced_frame_rate",),
                    ),
                ),
                limitations=("thermal_detail_reduced",),
            ),
        )
        session.add(TenantRow(tenant_id="tenant_other"))
        session.flush()
        session.add_all(
            [
                LocationRow(
                    location_id="location_other",
                    tenant_id="tenant_other",
                    label="Other clinic",
                ),
                RoomRow(
                    room_id="room_other",
                    tenant_id="tenant_other",
                    label="Other room",
                ),
                DeviceRow(
                    device_id="device_other",
                    tenant_id="tenant_other",
                    display_label="Other monitor",
                ),
            ]
        )
        session.commit()


def test_device_list_returns_current_assignment_and_honest_health(
    api_client: TestClient,
) -> None:
    _seed_device_reads(api_client)

    response = api_client.get("/v1/devices", headers=ACCESS_HEADERS)

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "items": [
            {
                "schema_version": "1.0",
                "device_id": "device_room_214",
                "display_label": "Room 214 monitor",
                "assignment": {
                    "schema_version": "1.0",
                    "location_id": "location_demo",
                    "location_label": "Demo clinic",
                    "room_id": "room_214",
                    "room_label": "Room 214",
                    "assigned_at": "2026-08-24T14:00:00Z",
                },
                "health": {
                    "schema_version": "1.0",
                    "device_id": "device_room_214",
                    "data_availability": "available",
                    "state": "degraded",
                    "observed_at": "2026-08-25T14:00:00Z",
                    "last_seen_at": "2026-08-25T13:59:55Z",
                    "sources": [
                        {
                            "schema_version": "1.0",
                            "source": "radar",
                            "state": "online",
                            "limitations": [],
                        },
                        {
                            "schema_version": "1.0",
                            "source": "thermal",
                            "state": "degraded",
                            "limitations": ["reduced_frame_rate"],
                        },
                    ],
                    "limitations": ["thermal_detail_reduced"],
                    "policy_version": "synthetic_device_health_v1",
                    "policy_test_only": True,
                },
            },
            {
                "schema_version": "1.0",
                "device_id": "device_spare",
                "display_label": "Spare monitor",
                "assignment": None,
                "health": {
                    "schema_version": "1.0",
                    "device_id": "device_spare",
                    "data_availability": "not_yet_available",
                    "state": None,
                    "observed_at": None,
                    "last_seen_at": None,
                    "sources": [],
                    "limitations": [],
                    "policy_version": None,
                    "policy_test_only": None,
                },
            },
        ],
    }


def test_device_health_detail_matches_list_and_known_empty_is_200(
    api_client: TestClient,
) -> None:
    _seed_device_reads(api_client)

    device_list = api_client.get("/v1/devices", headers=ACCESS_HEADERS).json()
    detail = api_client.get(
        "/v1/devices/device_room_214/health",
        headers=ACCESS_HEADERS,
    )
    empty = api_client.get(
        "/v1/devices/device_spare/health",
        headers=ACCESS_HEADERS,
    )

    assert detail.status_code == empty.status_code == 200
    assert detail.json() == device_list["items"][0]["health"]
    assert empty.json()["data_availability"] == "not_yet_available"
    assert empty.json()["state"] is None


def test_device_reads_hide_missing_and_cross_tenant_devices(
    api_client: TestClient,
) -> None:
    _seed_device_reads(api_client)
    paths = (
        "/v1/devices/device_missing/health",
        "/v1/devices/device_other/health",
    )

    responses = [
        api_client.get(path, headers=ACCESS_HEADERS)
        for path in paths
    ]

    assert [response.status_code for response in responses] == [404, 404]
    assert {response.json()["error"]["code"] for response in responses} == {
        "not_found"
    }


def test_device_read_openapi_and_method_errors_are_versioned(
    api_client: TestClient,
) -> None:
    paths = api_client.get("/openapi.json").json()["paths"]
    expected_models = {
        "/v1/devices": "DeviceListResponse",
        "/v1/devices/{device_id}/health": "DeviceHealthResponse",
    }

    for path, model in expected_models.items():
        responses = paths[path]["get"]["responses"]
        assert responses["200"]["content"]["application/json"]["schema"][
            "$ref"
        ].endswith(f"/{model}")
        assert responses["404"]["content"]["application/json"]["schema"][
            "$ref"
        ].endswith("/ErrorEnvelope")
        assert responses["405"]["content"]["application/json"]["schema"][
            "$ref"
        ].endswith("/ErrorEnvelope")

    unsupported = api_client.post("/v1/devices", headers=ACCESS_HEADERS)
    assert unsupported.status_code == 405
    assert unsupported.json()["error"]["code"] == "method_not_allowed"
