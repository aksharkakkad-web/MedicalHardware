import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.config import Settings
from backend.app.db.base import Base
from backend.app.db.models import (
    DeviceHealthObservationRow,
    EdgeTelemetryRow,
    TelemetryCaptureBatchRow,
)
from backend.app.db.seed import seed_synthetic_story
from backend.app.db.session import create_engine_for_url
from backend.app.main import create_app


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "edge_telemetry"
    / "mahin_capture_v1.json"
)
INGEST_KEY = "test-bench-ingest-key"
HEADERS = {"Authorization": f"Bearer {INGEST_KEY}"}


@pytest.fixture
def ingest_client(tmp_path) -> TestClient:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'ingestion-api.db'}"
    engine = create_engine_for_url(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_synthetic_story(session)
        session.commit()
    engine.dispose()

    app = create_app(
        Settings(
            app_env="test",
            database_url=database_url,
            ingest_bearer_key=INGEST_KEY,
            ingest_tenant_id="tenant_demo",
        )
    )
    with TestClient(app) as client:
        yield client


def _fixture() -> list[dict[str, object]]:
    return json.loads(FIXTURE.read_text())


def test_current_mahin_capture_is_accepted(ingest_client: TestClient) -> None:
    response = ingest_client.post(
        "/v1/ingest/telemetry",
        json=_fixture(),
        headers=HEADERS,
    )

    assert response.status_code == 202
    assert response.json() == {
        "schema_version": "1.0",
        "batch_id": response.json()["batch_id"],
        "accepted": 3,
        "duplicate_count": 0,
        "rejected": 0,
        "duplicate": False,
        "processing_state": "calibrating",
        "results": [
            {
                "schema_version": "1.0",
                "source": item["source"],
                "sequence": item["sequence"],
                "status": "accepted",
                "errors": [],
            }
            for item in _fixture()
        ],
    }


def test_exact_network_retry_is_idempotent(ingest_client: TestClient) -> None:
    first = ingest_client.post(
        "/v1/ingest/telemetry", json=_fixture(), headers=HEADERS
    )
    retry = _fixture()
    for envelope in retry:
        envelope["transport"]["retry_count"] = 2
    second = ingest_client.post(
        "/v1/ingest/telemetry", json=retry, headers=HEADERS
    )

    assert second.status_code == 202
    assert second.json()["batch_id"] == first.json()["batch_id"]
    assert second.json()["duplicate"] is True
    assert second.json()["accepted"] == 0
    assert second.json()["duplicate_count"] == 3

    with Session(ingest_client.app.state.engine) as session:
        assert session.scalar(select(func.count()).select_from(EdgeTelemetryRow)) == 3
        assert (
            session.scalar(select(func.count()).select_from(TelemetryCaptureBatchRow))
            == 1
        )


def test_changed_packet_identity_returns_conflict(ingest_client: TestClient) -> None:
    assert ingest_client.post(
        "/v1/ingest/telemetry", json=_fixture(), headers=HEADERS
    ).status_code == 202
    changed = _fixture()
    changed[0]["payload"]["heart_rate_bpm"] = 90.0

    response = ingest_client.post(
        "/v1/ingest/telemetry", json=changed, headers=HEADERS
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "concurrent_update"


@pytest.mark.parametrize("authorization", (None, "Bearer wrong-key", "Basic nope"))
def test_ingest_authentication_fails_without_leaking_secret(
    ingest_client: TestClient,
    authorization: str | None,
) -> None:
    headers = {} if authorization is None else {"Authorization": authorization}

    response = ingest_client.post(
        "/v1/ingest/telemetry", json=_fixture(), headers=headers
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert INGEST_KEY not in response.text


def test_ingest_is_unavailable_without_runtime_key(tmp_path) -> None:
    app = create_app(
        Settings(
            app_env="test",
            database_url=f"sqlite+pysqlite:///{tmp_path / 'no-key.db'}",
        )
    )
    with TestClient(app) as client:
        response = client.post("/v1/ingest/telemetry", json=_fixture())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


def test_configured_tenant_must_match_envelope(ingest_client: TestClient) -> None:
    capture = _fixture()
    for envelope in capture:
        envelope["tenant_id"] = "tenant_other"

    response = ingest_client.post(
        "/v1/ingest/telemetry", json=capture, headers=HEADERS
    )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "invalid_input",
        "message": "Telemetry tenant does not match the authenticated tenant",
        "field": "tenant_id",
    }


def test_post_commit_processor_sees_durable_capture(
    ingest_client: TestClient,
) -> None:
    observed: list[tuple[str, int]] = []

    def processor(batch_id: str) -> None:
        with Session(ingest_client.app.state.engine) as session:
            count = session.scalar(
                select(func.count())
                .select_from(TelemetryCaptureBatchRow)
                .where(TelemetryCaptureBatchRow.batch_id == batch_id)
            )
            observed.append((batch_id, int(count or 0)))

    ingest_client.app.state.telemetry_post_commit_processor = processor

    response = ingest_client.post(
        "/v1/ingest/telemetry", json=_fixture(), headers=HEADERS
    )

    assert response.status_code == 202
    assert observed == [(response.json()["batch_id"], 1)]


def test_heartbeat_records_health_once_across_retry(
    ingest_client: TestClient,
) -> None:
    with Session(ingest_client.app.state.engine) as session:
        before = int(
            session.scalar(
                select(func.count()).select_from(DeviceHealthObservationRow)
            )
            or 0
        )
    heartbeat = {
        "schema_version": "1.0",
        "device_id": "device_room_214",
        "sequence": 1,
        "device_monotonic_ms": None,
        "firmware_version": "bench-0.1.0",
        "buffered_packets": 4,
        "sources_seen": ["radar", "thermal"],
        "transport_status": "retrying",
    }

    first = ingest_client.post(
        "/v1/ingest/heartbeat", json=heartbeat, headers=HEADERS
    )
    second = ingest_client.post(
        "/v1/ingest/heartbeat", json=heartbeat, headers=HEADERS
    )

    assert first.status_code == 202
    assert first.json()["health_state"] == "buffering"
    assert first.json()["duplicate"] is False
    assert second.status_code == 202
    assert second.json()["duplicate"] is True
    with Session(ingest_client.app.state.engine) as session:
        after = int(
            session.scalar(
                select(func.count()).select_from(DeviceHealthObservationRow)
            )
            or 0
        )
        assert after == before + 1


def test_capture_limit_is_enforced_at_contract_boundary(
    ingest_client: TestClient,
) -> None:
    capture = []
    for number in range(9):
        item = deepcopy(_fixture()[0])
        item["source"] = "radar"
        item["sequence"] = number + 1
        capture.append(item)

    response = ingest_client.post(
        "/v1/ingest/telemetry", json=capture, headers=HEADERS
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"
