from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock, get_ident

import pytest
from fastapi.testclient import TestClient
from httpx import Response
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


def _action_body(
    occurred_at: str = ACTION_TIME,
    **extra: object,
) -> dict[str, object]:
    return {"schema_version": "1.0", "occurred_at": occurred_at, **extra}


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


def _race_same_idempotency_key(
    api_client: TestClient,
    *,
    first_body: dict[str, object],
    second_body: dict[str, object],
) -> tuple[Response, Response]:
    owner_inserted = Event()
    contender_reached_idempotency = Event()
    release_owner = Event()
    state_lock = Lock()
    state: dict[str, int | None] = {"owner_thread_id": None}

    def before_cursor_execute(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        if "idempotency_records" not in statement.lower():
            return
        with state_lock:
            owner_thread_id = state["owner_thread_id"]
        if (
            owner_inserted.is_set()
            and get_ident() != owner_thread_id
            and statement.lstrip().lower().startswith(
                "insert into idempotency_records"
            )
        ):
            contender_reached_idempotency.set()

    def after_cursor_execute(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        normalized_statement = statement.lstrip().lower()
        with state_lock:
            owner_thread_id = state["owner_thread_id"]
        if (
            owner_inserted.is_set()
            and get_ident() != owner_thread_id
            and normalized_statement.startswith("select")
            and "idempotency_records" in normalized_statement
        ):
            contender_reached_idempotency.set()
            return
        if not normalized_statement.startswith("insert into idempotency_records"):
            return
        with state_lock:
            if state["owner_thread_id"] is not None:
                return
            state["owner_thread_id"] = get_ident()
        owner_inserted.set()
        if not release_owner.wait(timeout=5):
            raise RuntimeError("timed out while coordinating idempotency race")

    engine = api_client.app.state.engine
    sqlalchemy_event.listen(engine, "before_cursor_execute", before_cursor_execute)
    sqlalchemy_event.listen(engine, "after_cursor_execute", after_cursor_execute)

    def post(body: dict[str, object]) -> Response:
        with TestClient(api_client.app) as client:
            return client.post(
                f"{EVENT_PATH}/acknowledge",
                headers=_headers("concurrent-key"),
                json=body,
            )

    executor = ThreadPoolExecutor(max_workers=2)
    try:
        first_future = executor.submit(post, first_body)
        owner_ready = owner_inserted.wait(timeout=5)
        second_future = executor.submit(post, second_body)
        contender_ready = contender_reached_idempotency.wait(timeout=5)
        release_owner.set()
        first = first_future.result(timeout=10)
        second = second_future.result(timeout=10)
    finally:
        release_owner.set()
        executor.shutdown(wait=True)
        sqlalchemy_event.remove(
            engine,
            "before_cursor_execute",
            before_cursor_execute,
        )
        sqlalchemy_event.remove(
            engine,
            "after_cursor_execute",
            after_cursor_execute,
        )

    assert owner_ready, "the first request never reached its idempotency insert"
    assert contender_ready, "the contender never reached idempotency handling"
    return first, second


def test_complete_caregiver_lifecycle_is_persisted_and_auditable(
    api_client: TestClient,
) -> None:
    acknowledged = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=_headers("ack-1"),
        json=_action_body(),
    )
    checked = api_client.post(
        f"{EVENT_PATH}/checked",
        headers=_headers("check-1"),
        json=_action_body("2026-08-24T21:04:00Z"),
    )
    resolved = api_client.post(
        f"{EVENT_PATH}/resolve",
        headers=_headers("resolve-1"),
        json=_action_body(
            "2026-08-24T21:05:00Z",
            outcome="false_positive",
        ),
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
        json=_action_body(),
    )
    second = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=headers,
        json=_action_body(),
    )

    assert second.status_code == first.status_code == 200
    assert second.json() == first.json()
    assert _row_count(api_client, EventActionRow) == 2
    assert _row_count(api_client, AuditLogRow) == 1
    assert _row_count(api_client, IdempotencyRecordRow) == 1


def test_concurrent_same_key_and_request_replays_one_success(
    api_client: TestClient,
) -> None:
    first, replay = _race_same_idempotency_key(
        api_client,
        first_body=_action_body(),
        second_body=_action_body(),
    )

    assert first.status_code == replay.status_code == 200
    assert first.json() == replay.json()
    assert _row_count(api_client, EventActionRow) == 2
    assert _row_count(api_client, AuditLogRow) == 1
    assert _row_count(api_client, IdempotencyRecordRow) == 1


def test_concurrent_same_key_and_different_request_returns_canonical_conflict(
    api_client: TestClient,
) -> None:
    first, conflict = _race_same_idempotency_key(
        api_client,
        first_body=_action_body(),
        second_body=_action_body("2026-08-24T21:04:00Z"),
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


def test_changed_request_reusing_an_idempotency_key_is_rejected_without_effects(
    api_client: TestClient,
) -> None:
    headers = _headers("ack-conflict")
    first = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=headers,
        json=_action_body(),
    )

    conflict = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=headers,
        json=_action_body("2026-08-24T21:04:00Z"),
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
        json=_action_body(),
    )

    conflict = api_client.post(
        f"{EVENT_PATH}/checked",
        headers=headers,
        json=_action_body(),
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
        json=_action_body(),
    )

    second_actor = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=_headers("actor-scoped", actor_id="operator_2"),
        json=_action_body(),
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
        json=_action_body(),
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
        json=_action_body(),
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
            _action_body(unexpected=True),
            "unexpected",
        ),
        (
            f"{EVENT_PATH}/acknowledge",
            _action_body("2026-08-24T21:03:00"),
            "occurred_at",
        ),
        (
            f"{EVENT_PATH}/resolve",
            _action_body(outcome="invented"),
            "outcome",
        ),
        (
            f"{EVENT_PATH}/acknowledge",
            {"occurred_at": ACTION_TIME},
            "schema_version",
        ),
        (
            f"{EVENT_PATH}/acknowledge",
            _action_body(schema_version="2.0"),
            "schema_version",
        ),
    ),
)
def test_action_requests_are_strict_versioned_and_utc(
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
        json=_action_body(),
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
    def fail_idempotency_response_update(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        if statement.lstrip().lower().startswith(
            "update idempotency_records"
        ):
            raise RuntimeError("injected idempotency persistence failure")

    engine = api_client.app.state.engine
    sqlalchemy_event.listen(
        engine,
        "before_cursor_execute",
        fail_idempotency_response_update,
    )
    try:
        safe_client = TestClient(api_client.app, raise_server_exceptions=False)
        response = safe_client.post(
            f"{EVENT_PATH}/acknowledge",
            headers=_headers("rollback-after-flush"),
            json=_action_body(),
        )
    finally:
        sqlalchemy_event.remove(
            engine,
            "before_cursor_execute",
            fail_idempotency_response_update,
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
        json=_action_body("2026-08-24T21:02:10Z"),
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
        json=_action_body(),
    )
    missing = api_client.post(
        "/v1/events/evt_missing/acknowledge",
        headers=_headers("missing-event"),
        json=_action_body(),
    )
    cross_tenant = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=_headers("tenant-scoped", tenant_id="tenant_other"),
        json=_action_body(),
    )

    assert success.status_code == 200
    assert missing.status_code == cross_tenant.status_code == 404
    assert missing.json() == cross_tenant.json()
    assert _row_count(api_client, EventActionRow) == 2
    assert _row_count(api_client, AuditLogRow) == 1
    assert _row_count(api_client, IdempotencyRecordRow) == 1


def test_offset_request_timestamp_is_rejected(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        f"{EVENT_PATH}/acknowledge",
        headers=_headers("ack-offset"),
        json=_action_body("2026-08-24T17:03:00-04:00"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["field"] == "occurred_at"
    assert _row_count(api_client, EventActionRow) == 1
