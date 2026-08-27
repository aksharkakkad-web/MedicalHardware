from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.db.models import (
    AuditLogRow,
    CalibrationSnapshotRow,
    IdempotencyRecordRow,
    MonitoringSetupChangeRow,
)
from backend.app.db.status_repositories import CalibrationRepository, StoredCalibration
from backend.app.domain.calibration import (
    BaselineStatus,
    CalibrationDimensionProgress,
    CalibrationProgress,
)


PATH = "/v1/residents/resident_demo_a/setup-changes"


def _headers(key: str, tenant_id: str = "tenant_demo") -> dict[str, str]:
    return {
        "X-Tenant-Id": tenant_id,
        "X-Actor-Id": "operator_1",
        "Idempotency-Key": key,
    }


def _body(**changes: object) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "reason": "device_moved",
        "affected_dimensions": ["movement"],
        "changed_at": "2026-08-24T22:00:00Z",
        "expected_calibration_version": 1,
        **changes,
    }


def _seed_calibration(client: TestClient) -> None:
    with client.app.state.session_factory() as session:
        CalibrationRepository(session).save(
            "tenant_demo",
            StoredCalibration(
                resident_id="resident_demo_a",
                version=1,
                recorded_at=datetime(2026, 8, 24, 21, 0, tzinfo=timezone.utc),
                progress=CalibrationProgress(
                    setup_version="setup_room_214_v1",
                    status=BaselineStatus.ESTABLISHED,
                    eligible_windows=12,
                    excluded_windows=2,
                    reason="calibration_complete",
                    dimension_progress=(
                        CalibrationDimensionProgress(
                            "movement",
                            BaselineStatus.ESTABLISHED,
                            12,
                            2,
                        ),
                        CalibrationDimensionProgress(
                            "respiratory_rate",
                            BaselineStatus.ESTABLISHED,
                            12,
                            2,
                        ),
                    ),
                ),
            ),
            expected_version=0,
        )
        session.commit()


def _count(client: TestClient, row_type: type[object]) -> int:
    with client.app.state.session_factory() as session:
        return session.scalar(select(func.count()).select_from(row_type))


def test_setup_change_resets_only_selected_dimension_and_audits(
    api_client: TestClient,
) -> None:
    _seed_calibration(api_client)

    response = api_client.post(PATH, headers=_headers("move-1"), json=_body())

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == 2
    assert payload["setup_version"] == "setup_room_214_v2"
    assert payload["status"] == "partial"
    assert payload["prior_setup_versions"] == ["setup_room_214_v1"]
    dimensions = {item["dimension"]: item for item in payload["dimensions"]}
    assert dimensions["movement"] == {
        "schema_version": "1.0",
        "dimension": "movement",
        "status": "calibrating",
        "eligible_windows": 0,
        "excluded_windows": 0,
    }
    assert dimensions["respiratory_rate"]["status"] == "established"
    assert payload["setup_changes"] == [
        {
            "schema_version": "1.0",
            "previous_setup_version": "setup_room_214_v1",
            "new_setup_version": "setup_room_214_v2",
            "affected_dimensions": ["movement"],
            "reason": "device_moved",
            "actor_id": "operator_1",
            "changed_at": "2026-08-24T22:00:00Z",
        }
    ]
    with api_client.app.state.session_factory() as session:
        audit = session.scalar(select(AuditLogRow))
        assert audit is not None
        assert audit.action == "monitoring_setup.changed"
        assert audit.target_id == "resident_demo_a"
        assert audit.details["calibration_version"] == 2


def test_setup_change_replay_returns_one_durable_effect(
    api_client: TestClient,
) -> None:
    _seed_calibration(api_client)
    headers = _headers("move-retry")

    first = api_client.post(PATH, headers=headers, json=_body())
    replay = api_client.post(PATH, headers=headers, json=_body())

    assert replay.status_code == first.status_code == 200
    assert replay.json() == first.json()
    assert _count(api_client, CalibrationSnapshotRow) == 2
    assert _count(api_client, MonitoringSetupChangeRow) == 1
    assert _count(api_client, AuditLogRow) == 1
    assert _count(api_client, IdempotencyRecordRow) == 1


def test_setup_change_conflicts_do_not_create_more_history(
    api_client: TestClient,
) -> None:
    _seed_calibration(api_client)
    success = api_client.post(
        PATH,
        headers=_headers("move-success"),
        json=_body(),
    )
    stale = api_client.post(
        PATH,
        headers=_headers("move-stale"),
        json=_body(changed_at="2026-08-24T22:01:00Z"),
    )
    reused_key = api_client.post(
        PATH,
        headers=_headers("move-success"),
        json=_body(reason="different_reason"),
    )
    stale_with_unknown_dimension = api_client.post(
        PATH,
        headers=_headers("move-stale-unknown"),
        json=_body(
            changed_at="2026-08-24T22:02:00Z",
            affected_dimensions=["invented_dimension"],
        ),
    )

    assert success.status_code == 200
    assert stale.status_code == reused_key.status_code == 409
    assert stale.json()["error"]["code"] == "concurrent_update"
    assert stale_with_unknown_dimension.json()["error"]["code"] == (
        "concurrent_update"
    )
    assert reused_key.json()["error"]["code"] == "idempotency_conflict"
    assert _count(api_client, CalibrationSnapshotRow) == 2
    assert _count(api_client, MonitoringSetupChangeRow) == 1
    assert _count(api_client, AuditLogRow) == 1


def test_setup_change_validates_input_and_tenant_scope(
    api_client: TestClient,
) -> None:
    _seed_calibration(api_client)

    unknown_dimension = api_client.post(
        PATH,
        headers=_headers("unknown-dimension"),
        json=_body(affected_dimensions=["invented_dimension"]),
    )
    missing_key = api_client.post(PATH, headers=_headers("unused") | {"Idempotency-Key": ""}, json=_body())
    cross_tenant = api_client.post(
        PATH,
        headers=_headers("cross-tenant", tenant_id="tenant_other"),
        json=_body(),
    )

    assert unknown_dimension.status_code == 409
    assert unknown_dimension.json()["error"]["code"] == "invalid_transition"
    assert missing_key.status_code == 422
    assert cross_tenant.status_code == 404
    assert _count(api_client, CalibrationSnapshotRow) == 1
    assert _count(api_client, MonitoringSetupChangeRow) == 0
    assert _count(api_client, AuditLogRow) == 0
