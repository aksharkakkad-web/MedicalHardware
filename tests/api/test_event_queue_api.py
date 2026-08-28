from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.app.db.mappers import event_to_rows
from backend.app.domain.events import (
    EventPriority,
    EventStatus,
    MonitoringEvent,
    ResolutionOutcome,
)


ACCESS_HEADERS = {
    "X-Tenant-Id": "tenant_demo",
    "X-Actor-Id": "operator_1",
}


def _seed_queue_events(api_client: TestClient) -> None:
    base = datetime(2026, 8, 24, 22, 0, tzinfo=timezone.utc)
    events = (
        MonitoringEvent(
            event_id="evt_queue_critical",
            episode_id="episode_queue_critical",
            resident_id="resident_demo_a",
            room_id="room_214",
            objective_family="unknown_anomaly",
            headline="Critical queue event",
            priority=EventPriority.CRITICAL,
            status=EventStatus.OPEN,
            created_at=base,
            last_signal_at=base,
        ),
        MonitoringEvent(
            event_id="evt_queue_watch",
            episode_id="episode_queue_watch",
            resident_id="resident_demo_a",
            room_id="room_214",
            objective_family="repetitive_movement",
            headline="Watch queue event",
            priority=EventPriority.WATCH,
            status=EventStatus.ACKNOWLEDGED,
            created_at=base + timedelta(minutes=1),
            last_signal_at=base + timedelta(minutes=1),
        ),
        MonitoringEvent(
            event_id="evt_queue_resolved",
            episode_id="episode_queue_resolved",
            resident_id="resident_demo_a",
            room_id="room_214",
            objective_family="position_transition",
            headline="Resolved queue history",
            priority=EventPriority.CRITICAL,
            status=EventStatus.RESOLVED,
            created_at=base + timedelta(minutes=2),
            last_signal_at=base + timedelta(minutes=2),
            resolution_outcome=ResolutionOutcome.CONFIRMED,
        ),
    )
    with api_client.app.state.session_factory() as session:
        for event in events:
            bundle = event_to_rows("tenant_demo", event, version=1)
            session.add(bundle.event)
            session.flush()
            session.add_all(bundle.actions)
            session.add_all(bundle.priorities)
        session.commit()


def test_default_clinic_queue_returns_active_work_in_attention_order(
    api_client: TestClient,
) -> None:
    _seed_queue_events(api_client)

    response = api_client.get("/v1/events", headers=ACCESS_HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "1.0"
    assert body["total_items"] == 3
    assert body["next_cursor"] is None
    assert [item["event_id"] for item in body["items"]] == [
        "evt_queue_critical",
        "evt_phase2_demo",
        "evt_queue_watch",
    ]
    assert all(item["status"] != "resolved" for item in body["items"])


def test_clinic_queue_filters_categories_and_keeps_resolved_history(
    api_client: TestClient,
) -> None:
    _seed_queue_events(api_client)

    response = api_client.get(
        "/v1/events",
        params=[
            ("status", "open"),
            ("status", "resolved"),
            ("priority", "critical"),
            ("resident_id", "resident_demo_a"),
            ("room_id", "room_214"),
        ],
        headers=ACCESS_HEADERS,
    )

    assert response.status_code == 200
    assert [item["event_id"] for item in response.json()["items"]] == [
        "evt_queue_critical",
        "evt_queue_resolved",
    ]


def test_clinic_queue_cursor_traversal_has_no_duplicates_and_binds_filters(
    api_client: TestClient,
) -> None:
    _seed_queue_events(api_client)

    first = api_client.get(
        "/v1/events",
        params={"limit": 2},
        headers=ACCESS_HEADERS,
    )
    cursor = first.json()["next_cursor"]
    second = api_client.get(
        "/v1/events",
        params={"limit": 2, "cursor": cursor},
        headers=ACCESS_HEADERS,
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["total_items"] == second.json()["total_items"] == 3
    ids = [item["event_id"] for item in first.json()["items"]]
    ids += [item["event_id"] for item in second.json()["items"]]
    assert ids == [
        "evt_queue_critical",
        "evt_phase2_demo",
        "evt_queue_watch",
    ]
    assert second.json()["next_cursor"] is None

    mismatch = api_client.get(
        "/v1/events",
        params={"priority": "critical", "cursor": cursor},
        headers=ACCESS_HEADERS,
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["field"] == "cursor"


def test_clinic_queue_masks_cross_tenant_filter_ids_with_empty_pages(
    api_client: TestClient,
) -> None:
    for field in ("resident_id", "room_id"):
        response = api_client.get(
            "/v1/events",
            params={field: "other_tenant_identifier"},
            headers=ACCESS_HEADERS,
        )
        assert response.status_code == 200
        assert response.json() == {
            "schema_version": "1.0",
            "items": [],
            "total_items": 0,
            "next_cursor": None,
        }


def test_delivery_preferences_never_hide_high_or_critical_queue_events(
    api_client: TestClient,
) -> None:
    preferences = api_client.put(
        "/v1/residents/resident_demo_a/notification-preferences",
        headers={**ACCESS_HEADERS, "Idempotency-Key": "queue-visibility-prefs"},
        json={
            "schema_version": "1.0",
            "expected_version": 0,
            "event_delivery": {
                "watch": False,
                "high": False,
                "critical": False,
            },
            "awareness_delivery": {
                "away": False,
                "return": False,
                "limited": False,
                "unavailable": False,
            },
            "changed_at": "2026-08-25T15:00:00Z",
        },
    )
    assert preferences.status_code == 200

    queue = api_client.get("/v1/events", headers=ACCESS_HEADERS)

    assert queue.status_code == 200
    assert [item["event_id"] for item in queue.json()["items"]] == [
        "evt_phase2_demo"
    ]
    assert queue.json()["items"][0]["priority"] == "high"


def test_clinic_queue_rejects_internal_status_limits_and_blank_filters(
    api_client: TestClient,
) -> None:
    cases = (
        ({"status": "detected"}, "status"),
        ({"limit": 0}, "limit"),
        ({"limit": 101}, "limit"),
        ({"resident_id": "   "}, "resident_id"),
        ({"cursor": "not-a-valid-cursor"}, "cursor"),
    )
    for params, field in cases:
        response = api_client.get(
            "/v1/events",
            params=params,
            headers=ACCESS_HEADERS,
        )
        assert response.status_code == 422
        assert response.json()["error"]["field"] == field


def test_resolving_event_removes_it_from_active_queue_but_preserves_history(
    api_client: TestClient,
) -> None:
    actions = (
        ("acknowledge", "2026-08-24T21:03:00Z", None),
        ("checked", "2026-08-24T21:04:00Z", None),
        ("resolve", "2026-08-24T21:05:00Z", "confirmed"),
    )
    for index, (action, occurred_at, outcome) in enumerate(actions):
        body = {"schema_version": "1.0", "occurred_at": occurred_at}
        if outcome is not None:
            body["outcome"] = outcome
        response = api_client.post(
            f"/v1/events/evt_phase2_demo/{action}",
            headers={**ACCESS_HEADERS, "Idempotency-Key": f"queue-action-{index}"},
            json=body,
        )
        assert response.status_code == 200

    active = api_client.get("/v1/events", headers=ACCESS_HEADERS)
    history = api_client.get(
        "/v1/events",
        params={"status": "resolved"},
        headers=ACCESS_HEADERS,
    )

    assert active.json()["items"] == []
    assert [item["event_id"] for item in history.json()["items"]] == [
        "evt_phase2_demo"
    ]


def test_clinic_queue_openapi_freezes_operation_parameters_and_errors(
    api_client: TestClient,
) -> None:
    operation = api_client.get("/openapi.json").json()["paths"]["/v1/events"][
        "get"
    ]

    assert operation["operationId"] == "listClinicEvents"
    assert {parameter["name"] for parameter in operation["parameters"]} == {
        "status",
        "priority",
        "resident_id",
        "room_id",
        "limit",
        "cursor",
        "X-Tenant-Id",
        "X-Actor-Id",
    }
    assert operation["responses"]["200"]["content"]["application/json"][
        "schema"
    ]["$ref"].endswith("/ClinicEventQueueResponse")
    for status_code in ("404", "405", "422", "500"):
        assert operation["responses"][status_code]["content"]["application/json"][
            "schema"
        ]["$ref"].endswith("/ErrorEnvelope")
