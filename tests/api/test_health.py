from fastapi.testclient import TestClient

from backend.app.main import create_app


def test_health_is_versioned_and_reports_ready() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "status": "ready",
        "service": "product-api",
    }
