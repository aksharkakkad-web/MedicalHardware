from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.db.models import (
    AuditLogRow,
    CalibrationSnapshotRow,
    IdempotencyRecordRow,
    MonitoringSetupChangeRow,
)
from backend.app.db.status_repositories import CalibrationRepository
from tests.api.test_setup_change_api import PATH, _body, _headers, _seed_calibration


class FaultingCalibrationRepository(CalibrationRepository):
    def save(self, tenant_id, stored, expected_version):
        super().save(tenant_id, stored, expected_version)
        raise RuntimeError("synthetic setup persistence failure")


def test_setup_route_failure_rolls_back_history_audit_and_idempotency(
    api_client: TestClient,
) -> None:
    _seed_calibration(api_client)
    api_client.app.state.calibration_repository_factory = (
        FaultingCalibrationRepository
    )
    try:
        with TestClient(api_client.app, raise_server_exceptions=False) as safe_client:
            response = safe_client.post(
                PATH,
                headers=_headers("move-rollback"),
                json=_body(),
            )
    finally:
        del api_client.app.state.calibration_repository_factory

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    with api_client.app.state.session_factory() as session:
        assert session.scalar(
            select(func.count()).select_from(CalibrationSnapshotRow)
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(MonitoringSetupChangeRow)
        ) == 0
        assert session.scalar(select(func.count()).select_from(AuditLogRow)) == 0
        assert session.scalar(
            select(func.count()).select_from(IdempotencyRecordRow)
        ) == 0
