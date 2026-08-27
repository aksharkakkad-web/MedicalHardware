from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy import func, select

from backend.app.db.models import (
    AuditLogRow,
    EventActionRow,
    IdempotencyRecordRow,
)


EVENT_ID = "evt_phase2_demo"
EVENT_PATH = f"/v1/events/{EVENT_ID}"
ACTION_TIME = "2026-08-24T21:03:00Z"


def _headers(
    key: str,
    *,
    tenant_id: str = "tenant_demo",
    actor_id: str = "operator_1",
) -> dict[str, str]:
    return {
        "X-Tenant-Id": tenant_id,
        "X-Actor-Id": actor_id,
        "Idempotency-Key": key,
    }


def _row_count(api_client: TestClient, row_type: type[object]) -> int:
    with api_client.app.state.session_factory() as session:
        return session.scalar(select(func.count()).select_from(row_type))


def test_complete_caregiver_lifecycle_is_persisted_and_auditable(
    api_client: TestClient,
) -> None:
    acknowledged = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=_headers("ack-1"),
        json={"occurred_at": ACTION_TIME},
    )
    checked = api_client.post(
        f"{EVENT_PATH}/checked",
        headers=_headers("check-1"),
        json={"occurred_at": "2026-08-24T21:04:00Z"},
    )
    resolved = api_client.post(
        f"{EVENT_PATH}/resolve",
        headers=_headers("resolve-1"),
        json={
            "occurred_at": "2026-08-24T21:05:00Z",
            "outcome": "false_positive",
        },
    )

    assert [response.status_code for response in (acknowledged, checked, resolved)] == [
        200,
        200,
        200,
    ]
    assert [response.json()["status"] for response in (acknowledged, checked, resolved)] == [
        "acknowledged",
        "checked",
        "resolved",
    ]
    assert resolved.json()["resolution_outcome"] == "false_positive"
    assert resolved.json()["version"] == 4
    assert [item["action"] for item in resolved.json()["action_history"]] == [
        "opened",
        "acknowledged",
        "checked",
        "resolved",
    ]
    assert [item["actor_id"] for item in resolved.json()["action_history"]] == [
        "system:monitoring_event",
        "operator_1",
        "operator_1",
        "operator_1",
    ]

    with api_client.app.state.session_factory() as session:
        audits = session.scalars(select(AuditLogRow).order_by(AuditLogRow.audit_id)).all()
        assert [audit.action for audit in audits] == [
            "event.acknowledged",
            "event.checked",
            "event.resolved",
        ]
        assert {audit.target_id for audit in audits} == {EVENT_ID}
        assert {audit.actor_id for audit in audits} == {"operator_1"}
        assert [audit.details["version"] for audit in audits] == [2, 3, 4]
        assert session.scalar(select(func.count()).select_from(EventActionRow)) == 4
        assert session.scalar(select(func.count()).select_from(IdempotencyRecordRow)) == 3


def test_same_idempotency_key_replays_original_response_once(
    api_client: TestClient,
) -> None:
    headers = _headers("ack-retry")

    first = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=headers,
        json={"occurred_at": ACTION_TIME},
    )
    second = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=headers,
        json={"occurred_at": ACTION_TIME},
    )

    assert second.status_code == first.status_code == 200
    assert second.json() == first.json()
    assert _row_count(api_client, EventActionRow) == 2
    assert _row_count(api_client, AuditLogRow) == 1
    assert _row_count(api_client, IdempotencyRecordRow) == 1


def test_changed_request_reusing_an_idempotency_key_is_rejected_without_effects(
    api_client: TestClient,
) -> None:
    headers = _headers("ack-conflict")
    first = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=headers,
        json={"occurred_at": ACTION_TIME},
    )

    conflict = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=headers,
        json={"occurred_at": "2026-08-24T21:04:00Z"},
    )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json() == {
        "schema_version": "1.0",
        "error": {
            "code": "idempotency_conflict",
            "message": "Idempotency key was already used for a different request",
            "field": None,
        },
    }
    assert _row_count(api_client, EventActionRow) == 2
    assert _row_count(api_client, AuditLogRow) == 1
    assert _row_count(api_client, IdempotencyRecordRow) == 1


def test_same_key_on_a_different_path_is_a_conflict(api_client: TestClient) -> None:
    headers = _headers("path-conflict")
    first = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=headers,
        json={"occurred_at": ACTION_TIME},
    )

    conflict = api_client.post(
        f"{EVENT_PATH}/checked",
        headers=headers,
        json={"occurred_at": ACTION_TIME},
    )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    assert _row_count(api_client, EventActionRow) == 2
    assert _row_count(api_client, AuditLogRow) == 1
    assert _row_count(api_client, IdempotencyRecordRow) == 1


def test_idempotency_keys_are_scoped_by_actor(api_client: TestClient) -> None:
    first = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=_headers("actor-scoped"),
        json={"occurred_at": ACTION_TIME},
    )

    second_actor = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=_headers("actor-scoped", actor_id="operator_2"),
        json={"occurred_at": ACTION_TIME},
    )

    assert first.status_code == 200
    assert second_actor.status_code == 409
    assert second_actor.json()["error"]["code"] == "invalid_transition"
    assert _row_count(api_client, EventActionRow) == 2
    assert _row_count(api_client, AuditLogRow) == 1
    assert _row_count(api_client, IdempotencyRecordRow) == 1


@pytest.mark.parametrize(
    ("headers", "missing_field"),
    (
        (
            {"X-Actor-Id": "operator_1", "Idempotency-Key": "ack-missing-tenant"},
            "X-Tenant-Id",
        ),
        (
            {"X-Tenant-Id": "tenant_demo", "Idempotency-Key": "ack-missing-actor"},
            "X-Actor-Id",
        ),
        (
            {"X-Tenant-Id": "tenant_demo", "X-Actor-Id": "operator_1"},
            "Idempotency-Key",
        ),
    ),
)
def test_mutations_require_all_access_and_idempotency_headers(
    api_client: TestClient,
    headers: dict[str, str],
    missing_field: str,
) -> None:
    response = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=headers,
        json={"occurred_at": ACTION_TIME},
    )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "invalid_input",
        "message": "Invalid request",
        "field": missing_field,
    }
    assert _row_count(api_client, EventActionRow) == 1
    assert _row_count(api_client, AuditLogRow) == 0
    assert _row_count(api_client, IdempotencyRecordRow) == 0


def test_blank_idempotency_key_is_invalid_input(api_client: TestClient) -> None:
    response = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=_headers("   "),
        json={"occurred_at": ACTION_TIME},
    )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "invalid_input",
        "message": "Invalid request",
        "field": "Idempotency-Key",
    }
    assert _row_count(api_client, IdempotencyRecordRow) == 0


@pytest.mark.parametrize(
    ("path", "body", "field"),
    (
        (
            f"{EVENT_PATH}/acknowledge",
            {"occurred_at": ACTION_TIME, "unexpected": True},
            "unexpected",
        ),
        (
            f"{EVENT_PATH}/acknowledge",
            {"occurred_at": "2026-08-24T21:03:00"},
            "occurred_at",
        ),
        (
            f"{EVENT_PATH}/resolve",
            {"occurred_at": ACTION_TIME, "outcome": "invented"},
            "outcome",
        ),
    ),
)
def test_action_requests_are_strict_and_timezone_aware(
    api_client: TestClient,
    path: str,
    body: dict[str, object],
    field: str,
) -> None:
    response = api_client.post(path, headers=_headers(f"invalid-{field}"), json=body)

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "invalid_input",
        "message": "Invalid request",
        "field": field,
    }
    assert _row_count(api_client, EventActionRow) == 1
    assert _row_count(api_client, AuditLogRow) == 0
    assert _row_count(api_client, IdempotencyRecordRow) == 0


def test_invalid_transition_rolls_back_every_caregiver_effect(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        f"{EVENT_PATH}/checked",
        headers=_headers("check-before-ack"),
        json={"occurred_at": ACTION_TIME},
    )

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "invalid_transition",
        "message": "The requested transition is not allowed",
        "field": None,
    }
    assert _row_count(api_client, EventActionRow) == 1
    assert _row_count(api_client, AuditLogRow) == 0
    assert _row_count(api_client, IdempotencyRecordRow) == 0


def test_failure_after_event_and_audit_flush_rolls_back_the_whole_action(
    api_client: TestClient,
) -> None:
    def fail_idempotency_insert(*_: object) -> None:
        raise RuntimeError("injected idempotency persistence failure")

    sqlalchemy_event.listen(
        IdempotencyRecordRow,
        "before_insert",
        fail_idempotency_insert,
    )
    try:
        safe_client = TestClient(api_client.app, raise_server_exceptions=False)
        response = safe_client.post(
            f"{EVENT_PATH}/acknowledge",
            headers=_headers("rollback-after-flush"),
            json={"occurred_at": ACTION_TIME},
        )
    finally:
        sqlalchemy_event.remove(
            IdempotencyRecordRow,
            "before_insert",
            fail_idempotency_insert,
        )

    assert response.status_code == 500
    assert response.json() == {
        "schema_version": "1.0",
        "error": {
            "code": "internal_error",
            "message": "Internal server error",
            "field": None,
        },
    }
    assert _row_count(api_client, EventActionRow) == 1
    assert _row_count(api_client, AuditLogRow) == 0
    assert _row_count(api_client, IdempotencyRecordRow) == 0


def test_action_timestamp_cannot_precede_event_history(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=_headers("ack-before-open"),
        json={"occurred_at": "2026-08-24T21:02:10Z"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_transition"
    assert _row_count(api_client, EventActionRow) == 1
    assert _row_count(api_client, AuditLogRow) == 0
    assert _row_count(api_client, IdempotencyRecordRow) == 0


def test_cross_tenant_mutation_is_tenant_safe_not_found(
    api_client: TestClient,
) -> None:
    success = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=_headers("tenant-scoped"),
        json={"occurred_at": ACTION_TIME},
    )
    missing = api_client.post(
        "/v1/events/evt_missing/acknowledge",
        headers=_headers("missing-event"),
        json={"occurred_at": ACTION_TIME},
    )
    cross_tenant = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=_headers("tenant-scoped", tenant_id="tenant_other"),
        json={"occurred_at": ACTION_TIME},
    )

    assert success.status_code == 200
    assert missing.status_code == cross_tenant.status_code == 404
    assert missing.json() == cross_tenant.json()
    assert _row_count(api_client, EventActionRow) == 2
    assert _row_count(api_client, AuditLogRow) == 1
    assert _row_count(api_client, IdempotencyRecordRow) == 1


def test_offset_request_timestamp_is_returned_as_utc(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=_headers("ack-offset"),
        json={"occurred_at": "2026-08-24T17:03:00-04:00"},
    )

    assert response.status_code == 200
    action = response.json()["action_history"][-1]
    assert action["occurred_at"] == "2026-08-24T21:03:00Z"
    parsed_timestamp = datetime.fromisoformat(
        action["occurred_at"].replace("Z", "+00:00")
    )
    assert parsed_timestamp.tzinfo is timezone.utc
