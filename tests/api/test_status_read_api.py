from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.db.status_repositories import (
    CalibrationRepository,
    MonitoringStatusRepository,
    StoredCalibration,
    StoredMonitoringStatus,
)
from backend.app.domain.calibration import (
    BaselineStatus,
    CalibrationDimensionProgress,
    CalibrationProgress,
)
from backend.app.domain.monitoring import PresenceState, derive_monitoring_snapshot


ACCESS_HEADERS = {
    "X-Tenant-Id": "tenant_demo",
    "X-Actor-Id": "operator_1",
}
OBSERVED_AT = datetime(2026, 8, 24, 21, 0, tzinfo=timezone.utc)


def _seed_status_story(client: TestClient) -> None:
    with client.app.state.session_factory() as session:
        monitoring = MonitoringStatusRepository(session)
        for offset, presence in enumerate(
            (
                PresenceState.RESIDENT_PRESENT,
                PresenceState.RESIDENT_AWAY,
                PresenceState.RESIDENT_PRESENT,
            )
        ):
            monitoring.record(
                "tenant_demo",
                StoredMonitoringStatus(
                    resident_id="resident_demo_a",
                    room_id="room_214",
                    observed_at=OBSERVED_AT + timedelta(minutes=offset),
                    snapshot=derive_monitoring_snapshot(
                        assignment_valid=True,
                        device_healthy=True,
                        presence=presence,
                        signal_quality=0.9,
                    ),
                ),
            )
        CalibrationRepository(session).save(
            "tenant_demo",
            StoredCalibration(
                resident_id="resident_demo_a",
                version=1,
                recorded_at=OBSERVED_AT + timedelta(minutes=2),
                progress=CalibrationProgress(
                    setup_version="setup_room_214_v1",
                    status=BaselineStatus.ESTABLISHED,
                    eligible_windows=12,
                    excluded_windows=2,
                    reason="calibration_complete",
                    dimension_progress=(
                        CalibrationDimensionProgress(
                            dimension="movement",
                            status=BaselineStatus.ESTABLISHED,
                            eligible_windows=12,
                            excluded_windows=2,
                        ),
                        CalibrationDimensionProgress(
                            dimension="respiratory_rate",
                            status=BaselineStatus.ESTABLISHED,
                            eligible_windows=12,
                            excluded_windows=2,
                        ),
                    ),
                ),
            ),
            expected_version=0,
        )
        session.commit()


def test_resident_status_combines_latest_monitoring_and_calibration(
    api_client: TestClient,
) -> None:
    _seed_status_story(api_client)

    response = api_client.get(
        "/v1/residents/resident_demo_a/status",
        headers=ACCESS_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "resident_id": "resident_demo_a",
        "room_id": "room_214",
        "monitoring": {
            "schema_version": "1.0",
            "resident_id": "resident_demo_a",
            "room_id": "room_214",
            "observed_at": "2026-08-24T21:02:00Z",
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
            "recorded_at": "2026-08-24T21:02:00Z",
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


def test_away_is_chronological_awareness_not_a_warning_event(
    api_client: TestClient,
) -> None:
    _seed_status_story(api_client)

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
    ] == ["resident_present", "resident_away", "resident_present"]
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
    _seed_status_story(api_client)

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
    _seed_status_story(api_client)
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
