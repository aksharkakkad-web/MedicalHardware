from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.db.models import (
    ResidentRow,
    RoomResidentAssignmentRow,
    RoomRow,
)


ACCESS_HEADERS = {
    "X-Tenant-Id": "tenant_demo",
    "X-Actor-Id": "operator_1",
}


def test_resident_status_combines_latest_monitoring_and_calibration(
    api_client: TestClient,
) -> None:
    response = api_client.get(
        "/v1/residents/resident_demo_a/status",
        headers=ACCESS_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "resident_id": "resident_demo_a",
        "room_id": "room_214",
        "data_availability": "available",
        "unavailable_reasons": [],
        "device_assignment_state": "assigned",
        "device": {
            "schema_version": "1.0",
            "device_id": "device_room_214",
            "display_label": "Room 214 monitor",
            "assignment": {
                "schema_version": "1.0",
                "location_id": "location_demo",
                "location_label": "Demo clinic",
                "room_id": "room_214",
                "room_label": "Room 214",
                "assigned_at": "2026-08-24T00:00:00Z",
            },
            "health": {
                "schema_version": "1.0",
                "device_id": "device_room_214",
                "data_availability": "available",
                "state": "online",
                "observed_at": "2026-08-24T20:59:00Z",
                "last_seen_at": "2026-08-24T20:59:00Z",
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
                        "state": "online",
                        "limitations": [],
                    },
                    {
                        "schema_version": "1.0",
                        "source": "wifi_csi",
                        "state": "online",
                        "limitations": [],
                    },
                ],
                "limitations": [],
                "policy_version": "synthetic_device_health_v1",
                "policy_test_only": True,
            },
        },
        "monitoring": {
            "schema_version": "1.0",
            "resident_id": "resident_demo_a",
            "room_id": "room_214",
            "observed_at": "2026-08-24T20:59:00Z",
            "monitoring_state": "active",
            "presence_state": "resident_present",
            "baseline_learning_allowed": True,
            "resident_measurements_allowed": True,
            "reasons": [],
            "quality_policy_version": "synthetic_monitoring_quality_v1",
            "quality_policy_test_only": True,
        },
        "calibration": {
            "schema_version": "1.0",
            "resident_id": "resident_demo_a",
            "version": 1,
            "recorded_at": "2026-08-24T21:00:00Z",
            "setup_version": "setup_room_214_v1",
            "status": "established",
            "eligible_windows": 12,
            "excluded_windows": 2,
            "reason": "calibration_complete",
            "prior_setup_versions": [],
            "dimensions": [
                {
                    "schema_version": "1.0",
                    "dimension": "movement",
                    "status": "established",
                    "eligible_windows": 12,
                    "excluded_windows": 2,
                },
                {
                    "schema_version": "1.0",
                    "dimension": "respiratory_rate",
                    "status": "established",
                    "eligible_windows": 12,
                    "excluded_windows": 2,
                },
            ],
            "setup_changes": [],
        },
    }


def test_existing_resident_without_status_history_is_explicitly_unavailable(
    api_client: TestClient,
) -> None:
    with api_client.app.state.session_factory() as session:
        session.add(
            RoomRow(
                room_id="room_new",
                tenant_id="tenant_demo",
                label="New room",
            )
        )
        session.add(
            ResidentRow(
                resident_id="resident_new",
                tenant_id="tenant_demo",
                display_label="New resident",
            )
        )
        session.flush()
        session.add(
            RoomResidentAssignmentRow(
                assignment_id="assign_room_new",
                tenant_id="tenant_demo",
                room_id="room_new",
                resident_id="resident_new",
                status="active",
                effective_from=datetime(2026, 8, 25, tzinfo=timezone.utc),
                effective_to=None,
            )
        )
        session.commit()

    response = api_client.get(
        "/v1/residents/resident_new/status",
        headers=ACCESS_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "resident_id": "resident_new",
        "room_id": "room_new",
        "data_availability": "not_yet_available",
        "unavailable_reasons": [
            "monitoring_not_yet_available",
            "calibration_not_yet_available",
            "device_assignment_unavailable",
        ],
        "device_assignment_state": "assignment_unavailable",
        "device": None,
        "monitoring": None,
        "calibration": None,
    }


def test_away_is_chronological_awareness_not_a_warning_event(
    api_client: TestClient,
) -> None:
    timeline = api_client.get(
        "/v1/residents/resident_demo_a/awareness",
        headers=ACCESS_HEADERS,
    )
    events = api_client.get(
        "/v1/residents/resident_demo_a/events",
        headers=ACCESS_HEADERS,
    )

    assert timeline.status_code == 200
    assert [
        item["presence_state"] for item in timeline.json()["items"]
    ] == [
        "resident_present",
        "resident_away",
        "resident_present",
        "possible_multi_person",
        "resident_present",
    ]
    away = timeline.json()["items"][1]
    assert away["monitoring_state"] == "paused"
    assert away["baseline_learning_allowed"] is False
    assert all(
        item["objective_family"] != "resident_away"
        for item in events.json()["items"]
    )


def test_calibration_read_matches_status_calibration(
    api_client: TestClient,
) -> None:
    status = api_client.get(
        "/v1/residents/resident_demo_a/status",
        headers=ACCESS_HEADERS,
    ).json()
    calibration = api_client.get(
        "/v1/residents/resident_demo_a/calibration",
        headers=ACCESS_HEADERS,
    )

    assert calibration.status_code == 200
    assert calibration.json() == status["calibration"]


def test_status_reads_hide_missing_and_cross_tenant_residents(
    api_client: TestClient,
) -> None:
    other_headers = {
        "X-Tenant-Id": "tenant_other",
        "X-Actor-Id": "operator_1",
    }
    paths = ("status", "awareness", "calibration")

    missing = [
        api_client.get(
            f"/v1/residents/resident_missing/{path}",
            headers=ACCESS_HEADERS,
        )
        for path in paths
    ]
    cross_tenant = [
        api_client.get(
            f"/v1/residents/resident_demo_a/{path}",
            headers=other_headers,
        )
        for path in paths
    ]

    assert [response.status_code for response in missing + cross_tenant] == [404] * 6
    assert {response.text for response in missing + cross_tenant} == {
        '{"schema_version":"1.0","error":{"code":"not_found",'
        '"message":"Resource not found","field":null}}'
    }


def test_status_read_openapi_and_method_errors_are_versioned(
    api_client: TestClient,
) -> None:
    paths = api_client.get("/openapi.json").json()["paths"]
    expected_models = {
        "/v1/residents/{resident_id}/status": "ResidentStatusResponse",
        "/v1/residents/{resident_id}/awareness": "AwarenessTimelineResponse",
        "/v1/residents/{resident_id}/calibration": "CalibrationResponse",
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

    unsupported = api_client.post(
        "/v1/residents/resident_demo_a/status",
        headers=ACCESS_HEADERS,
    )
    assert unsupported.status_code == 405
    assert unsupported.json()["error"]["code"] == "method_not_allowed"
