import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.db.models import (
    AuditLogRow,
    FeedbackRecordRow,
    IdempotencyRecordRow,
    ResidentMemoryEntryRow,
    ResidentMemorySnapshotRow,
    TenantRow,
)


EVENT_ID = "evt_phase2_demo"
EVENT_PATH = f"/v1/events/{EVENT_ID}"
FEEDBACK_PATH = f"{EVENT_PATH}/feedback"
FEEDBACK_BODY = {
    "schema_version": "1.0",
    "actual_event_label": "Assisted movement",
    "routine": True,
    "created_at": "2026-08-24T21:06:00Z",
}


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


def _resolve_event(api_client: TestClient) -> None:
    actions = (
        (
            "acknowledge",
            "resolve-feedback-ack",
            {"schema_version": "1.0", "occurred_at": "2026-08-24T21:03:00Z"},
        ),
        (
            "checked",
            "resolve-feedback-check",
            {"schema_version": "1.0", "occurred_at": "2026-08-24T21:04:00Z"},
        ),
        (
            "resolve",
            "resolve-feedback-resolve",
            {
                "schema_version": "1.0",
                "occurred_at": "2026-08-24T21:05:00Z",
                "outcome": "false_positive",
            },
        ),
    )
    for action, key, body in actions:
        response = api_client.post(
            f"{EVENT_PATH}/{action}",
            headers=_headers(key),
            json=body,
        )
        assert response.status_code == 200


def _row_count(api_client: TestClient, row_type: type[object]) -> int:
    with api_client.app.state.session_factory() as session:
        return session.scalar(select(func.count()).select_from(row_type))


def _feedback_audit_count(api_client: TestClient) -> int:
    with api_client.app.state.session_factory() as session:
        return session.scalar(
            select(func.count())
            .select_from(AuditLogRow)
            .where(AuditLogRow.action == "feedback.submitted")
        )


def test_feedback_updates_memory_once_with_versioned_synthetic_output(
    api_client: TestClient,
) -> None:
    _resolve_event(api_client)

    response = api_client.post(
        FEEDBACK_PATH,
        headers=_headers("feedback-1"),
        json=FEEDBACK_BODY,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1.0"
    assert payload["memory_updated"] is True
    assert payload["baseline_window_eligible"] is True
    assert payload["global_label_recorded"] is True
    assert payload["feedback"] == {
        "schema_version": "1.0",
        "feedback_id": payload["feedback"]["feedback_id"],
        "event_id": EVENT_ID,
        "resident_id": "resident_demo_a",
        "actor_id": "operator_1",
        "outcome": "false_positive",
        "actual_event_label": "assisted_movement",
        "routine": True,
        "created_at": "2026-08-24T21:06:00Z",
    }
    assert payload["feedback"]["feedback_id"].startswith("fb_")
    assert payload["memory"]["schema_version"] == "1.0"
    assert payload["memory"]["resident_id"] == "resident_demo_a"
    assert payload["memory"]["version"] == 1
    assert len(payload["memory"]["entries"]) == 1
    entry = payload["memory"]["entries"][0]
    assert entry == {
        "schema_version": "1.0",
        "entry_id": entry["entry_id"],
        "description": "assisted_movement",
        "context_kind": "general_context",
        "effective_from": None,
        "effective_until": None,
        "local_time_start": None,
        "local_time_end": None,
        "recurrence_note": None,
        "flexibility_note": None,
        "source_kind": "feedback",
        "source_feedback_id": payload["feedback"]["feedback_id"],
        "supersedes_entry_id": None,
        "status": "active",
        "created_by": "operator_1",
        "created_at": "2026-08-24T21:06:00Z",
        "retired_by": None,
        "retired_at": None,
        "retirement_reason": None,
    }
    assert entry["entry_id"].startswith("memory_")

    assert _row_count(api_client, FeedbackRecordRow) == 1
    assert _row_count(api_client, ResidentMemorySnapshotRow) == 1
    assert _row_count(api_client, ResidentMemoryEntryRow) == 1
    assert _feedback_audit_count(api_client) == 1


def test_same_idempotency_key_replays_without_relearning(
    api_client: TestClient,
) -> None:
    _resolve_event(api_client)
    headers = _headers("feedback-retry")

    first = api_client.post(FEEDBACK_PATH, headers=headers, json=FEEDBACK_BODY)
    retry = api_client.post(FEEDBACK_PATH, headers=headers, json=FEEDBACK_BODY)

    assert first.status_code == retry.status_code == 200
    assert retry.json() == first.json()
    assert retry.json()["memory"]["version"] == 1
    assert retry.json()["memory_updated"] is True
    assert _row_count(api_client, FeedbackRecordRow) == 1
    assert _row_count(api_client, ResidentMemorySnapshotRow) == 1
    assert _row_count(api_client, ResidentMemoryEntryRow) == 1
    assert _feedback_audit_count(api_client) == 1


def test_changed_feedback_reusing_idempotency_key_is_rejected_without_effects(
    api_client: TestClient,
) -> None:
    _resolve_event(api_client)
    headers = _headers("feedback-conflict")
    first = api_client.post(FEEDBACK_PATH, headers=headers, json=FEEDBACK_BODY)

    conflict = api_client.post(
        FEEDBACK_PATH,
        headers=headers,
        json={**FEEDBACK_BODY, "routine": False},
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
    assert _row_count(api_client, FeedbackRecordRow) == 1
    assert _row_count(api_client, ResidentMemorySnapshotRow) == 1
    assert _row_count(api_client, ResidentMemoryEntryRow) == 1
    assert _feedback_audit_count(api_client) == 1


def test_conflicting_second_feedback_requires_explicit_correction(
    api_client: TestClient,
) -> None:
    _resolve_event(api_client)
    first = api_client.post(
        FEEDBACK_PATH,
        headers=_headers("feedback-first"),
        json=FEEDBACK_BODY,
    )

    conflict = api_client.post(
        FEEDBACK_PATH,
        headers=_headers("feedback-second"),
        json={**FEEDBACK_BODY, "actual_event_label": "Unexplained movement"},
    )

    assert first.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "invalid_transition"
    assert _row_count(api_client, FeedbackRecordRow) == 1
    assert _row_count(api_client, ResidentMemorySnapshotRow) == 1
    assert _row_count(api_client, ResidentMemoryEntryRow) == 1
    assert _feedback_audit_count(api_client) == 1


def test_unresolved_event_rejects_feedback_without_persisting_effects(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        FEEDBACK_PATH,
        headers=_headers("feedback-unresolved"),
        json=FEEDBACK_BODY,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_transition"
    assert _row_count(api_client, FeedbackRecordRow) == 0
    assert _row_count(api_client, ResidentMemorySnapshotRow) == 0
    assert _row_count(api_client, ResidentMemoryEntryRow) == 0
    assert _feedback_audit_count(api_client) == 0
    assert _row_count(api_client, IdempotencyRecordRow) == 0


def test_cross_tenant_feedback_is_tenant_safe_not_found(
    api_client: TestClient,
) -> None:
    _resolve_event(api_client)
    same_tenant = api_client.post(
        FEEDBACK_PATH,
        headers=_headers("feedback-same-tenant"),
        json=FEEDBACK_BODY,
    )
    with api_client.app.state.session_factory() as session:
        session.add(TenantRow(tenant_id="tenant_other"))
        session.commit()

    response = api_client.post(
        FEEDBACK_PATH,
        headers=_headers("feedback-cross-tenant", tenant_id="tenant_other"),
        json=FEEDBACK_BODY,
    )

    assert same_tenant.status_code == 200
    assert response.status_code == 404
    assert EVENT_ID not in response.text
    assert _row_count(api_client, FeedbackRecordRow) == 1
    assert _row_count(api_client, ResidentMemorySnapshotRow) == 1
    assert _feedback_audit_count(api_client) == 1
    with api_client.app.state.session_factory() as session:
        assert session.scalar(
            select(func.count())
            .select_from(IdempotencyRecordRow)
            .where(IdempotencyRecordRow.tenant_id == "tenant_other")
        ) == 0


def test_feedback_before_newer_admin_memory_is_rejected_without_reordering_history(
    api_client: TestClient,
) -> None:
    memory = api_client.post(
        "/v1/residents/resident_demo_a/memory/entries",
        headers=_headers("feedback-chronology-memory"),
        json={
            "schema_version": "1.0",
            "expected_version": 0,
            "description": "Newer staff-entered routine",
            "changed_at": "2026-08-25T15:10:00Z",
        },
    )
    assert memory.status_code == 200
    _resolve_event(api_client)

    response = api_client.post(
        FEEDBACK_PATH,
        headers=_headers("feedback-before-admin-memory"),
        json=FEEDBACK_BODY,
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_transition"
    assert _row_count(api_client, FeedbackRecordRow) == 0
    assert _row_count(api_client, ResidentMemorySnapshotRow) == 1
    current = api_client.get(
        "/v1/residents/resident_demo_a/memory",
        headers={
            "X-Tenant-Id": "tenant_demo",
            "X-Actor-Id": "operator_1",
        },
    )
    assert current.status_code == 200
    assert current.json() == memory.json()


@pytest.mark.parametrize(
    ("created_at", "expected_code", "expected_field"),
    (
        ("2026-08-24T21:06:00", "invalid_input", "created_at"),
        ("2026-08-24T21:02:00Z", "invalid_transition", None),
    ),
)
def test_invalid_feedback_times_fail_without_persisting_effects(
    api_client: TestClient,
    created_at: str,
    expected_code: str,
    expected_field: str | None,
) -> None:
    _resolve_event(api_client)

    response = api_client.post(
        FEEDBACK_PATH,
        headers=_headers(f"feedback-invalid-time-{expected_code}"),
        json={**FEEDBACK_BODY, "created_at": created_at},
    )

    assert response.status_code in {409, 422}
    assert response.json()["error"]["code"] == expected_code
    assert response.json()["error"]["field"] == expected_field
    assert _row_count(api_client, FeedbackRecordRow) == 0
    assert _row_count(api_client, ResidentMemorySnapshotRow) == 0
    assert _feedback_audit_count(api_client) == 0
    assert _row_count(api_client, IdempotencyRecordRow) == 3


def test_offset_feedback_time_is_rejected(
    api_client: TestClient,
) -> None:
    _resolve_event(api_client)

    response = api_client.post(
        FEEDBACK_PATH,
        headers=_headers("feedback-offset-time"),
        json={**FEEDBACK_BODY, "created_at": "2026-08-24T17:06:00-04:00"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["field"] == "created_at"
    assert _row_count(api_client, FeedbackRecordRow) == 0
    assert _row_count(api_client, ResidentMemorySnapshotRow) == 0
    assert _feedback_audit_count(api_client) == 0


@pytest.mark.parametrize("actual_event_label", ("", "   ", "--- !!!"))
def test_malformed_feedback_label_is_invalid_input_without_effects(
    api_client: TestClient,
    actual_event_label: str,
) -> None:
    _resolve_event(api_client)

    response = api_client.post(
        FEEDBACK_PATH,
        headers=_headers(f"malformed-label-{actual_event_label!r}"),
        json={**FEEDBACK_BODY, "actual_event_label": actual_event_label},
    )

    assert response.status_code == 422
    assert response.json() == {
        "schema_version": "1.0",
        "error": {
            "code": "invalid_input",
            "message": "Invalid request",
            "field": "actual_event_label",
        },
    }
    assert _row_count(api_client, FeedbackRecordRow) == 0
    assert _row_count(api_client, ResidentMemorySnapshotRow) == 0
    assert _row_count(api_client, ResidentMemoryEntryRow) == 0
    assert _feedback_audit_count(api_client) == 0
    assert _row_count(api_client, IdempotencyRecordRow) == 3


def test_equivalent_normalized_labels_share_idempotency_fingerprint(
    api_client: TestClient,
) -> None:
    _resolve_event(api_client)
    headers = _headers("normalized-label-replay")

    first = api_client.post(
        FEEDBACK_PATH,
        headers=headers,
        json={**FEEDBACK_BODY, "actual_event_label": "Assisted movement"},
    )
    replay = api_client.post(
        FEEDBACK_PATH,
        headers=headers,
        json={**FEEDBACK_BODY, "actual_event_label": "assisted_movement"},
    )

    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json()
    assert _row_count(api_client, FeedbackRecordRow) == 1
    assert _row_count(api_client, ResidentMemorySnapshotRow) == 1
    assert _row_count(api_client, ResidentMemoryEntryRow) == 1
    assert _feedback_audit_count(api_client) == 1
