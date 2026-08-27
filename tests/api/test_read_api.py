from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app.api.dependencies import query_service
from backend.app.db.repositories import FeedbackRepository
from backend.app.domain.events import ResolutionOutcome
from backend.app.domain.feedback import (
    FeedbackRecord,
    LearningDecision,
    MemoryEntry,
    ResidentMemory,
)


ACCESS_HEADERS = {
    "X-Tenant-Id": "tenant_demo",
    "X-Actor-Id": "operator_1",
}


def test_list_residents_is_tenant_scoped(api_client: TestClient) -> None:
    response = api_client.get("/v1/residents", headers=ACCESS_HEADERS)

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "items": [
            {
                "schema_version": "1.0",
                "resident_id": "resident_demo_a",
                "display_label": "Resident A",
                "room_id": "room_214",
                "room_label": "Room 214",
                "assignment_status": "active",
            }
        ],
    }


def test_get_resident_returns_the_versioned_assignment(api_client: TestClient) -> None:
    response = api_client.get(
        "/v1/residents/resident_demo_a",
        headers=ACCESS_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "resident_id": "resident_demo_a",
        "display_label": "Resident A",
        "room_id": "room_214",
        "room_label": "Room 214",
        "assignment_status": "active",
    }


def test_list_resident_events_returns_complete_versioned_history(
    api_client: TestClient,
) -> None:
    response = api_client.get(
        "/v1/residents/resident_demo_a/events",
        headers=ACCESS_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "items": [
            {
                "schema_version": "1.0",
                "event_id": "evt_phase2_demo",
                "episode_id": "episode_phase2_demo",
                "resident_id": "resident_demo_a",
                "room_id": "room_214",
                "objective_family": "unusual_movement",
                "headline": "Unusual movement detected",
                "priority": "high",
                "status": "open",
                "created_at": "2026-08-24T21:02:11Z",
                "last_signal_at": "2026-08-24T21:02:11Z",
                "signal_count": 1,
                "related_event_ids": [],
                "recurrence_count": 1,
                "overdue_at": None,
                "overdue": False,
                "resolution_outcome": None,
                "action_history": [
                    {
                        "schema_version": "1.0",
                        "action": "opened",
                        "actor_id": "system:monitoring_event",
                        "occurred_at": "2026-08-24T21:02:11Z",
                        "previous_status": "detected",
                        "status": "open",
                        "resolution_outcome": None,
                    }
                ],
                "priority_history": [
                    {
                        "schema_version": "1.0",
                        "previous_priority": None,
                        "priority": "high",
                        "actor_id": "system:monitoring_event",
                        "changed_at": "2026-08-24T21:02:11Z",
                    }
                ],
                "resident_memory_version": None,
                "resident_memory_entry_ids": [],
                "version": 1,
            }
        ],
    }


def test_get_event_matches_the_resident_event_contract(api_client: TestClient) -> None:
    listed = api_client.get(
        "/v1/residents/resident_demo_a/events",
        headers=ACCESS_HEADERS,
    ).json()["items"][0]

    response = api_client.get(
        "/v1/events/evt_phase2_demo",
        headers=ACCESS_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == listed


def test_get_resident_memory_returns_versioned_empty_memory(
    api_client: TestClient,
) -> None:
    response = api_client.get(
        "/v1/residents/resident_demo_a/memory",
        headers=ACCESS_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "resident_id": "resident_demo_a",
        "version": 0,
        "entries": [],
    }


def test_get_resident_memory_maps_nested_entries_to_public_contracts(
    api_client: TestClient,
) -> None:
    created_at = datetime(2026, 8, 24, 21, 7, tzinfo=timezone.utc)
    feedback = FeedbackRecord(
        feedback_id="fb_read_contract",
        event_id="evt_phase2_demo",
        resident_id="resident_demo_a",
        actor_id="operator_1",
        outcome=ResolutionOutcome.FALSE_POSITIVE,
        actual_event_label="assisted_movement",
        routine=True,
        created_at=created_at,
    )
    memory = ResidentMemory(
        resident_id="resident_demo_a",
        version=1,
        entries=(
            MemoryEntry(
                entry_id="memory_read_contract",
                description="assisted_movement",
                source_feedback_id=feedback.feedback_id,
                status="active",
                created_by="operator_1",
                created_at=created_at,
            ),
        ),
    )
    with api_client.app.state.session_factory() as session:
        FeedbackRepository(session).save_decision(
            "tenant_demo",
            LearningDecision(feedback, memory, True, True, True),
        )
        session.commit()

    response = api_client.get(
        "/v1/residents/resident_demo_a/memory",
        headers=ACCESS_HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "resident_id": "resident_demo_a",
        "version": 1,
        "entries": [
            {
                "schema_version": "1.0",
                "entry_id": "memory_read_contract",
                "description": "assisted_movement",
                "source_feedback_id": "fb_read_contract",
                "status": "active",
                "created_by": "operator_1",
                "created_at": "2026-08-24T21:07:00Z",
                "retired_by": None,
                "retired_at": None,
                "retirement_reason": None,
            }
        ],
    }


def test_cross_tenant_resources_use_the_same_not_found_response(
    api_client: TestClient,
) -> None:
    other_tenant_headers = {
        "X-Tenant-Id": "tenant_other",
        "X-Actor-Id": "operator_1",
    }
    paths = (
        "/v1/residents/resident_demo_a",
        "/v1/residents/resident_demo_a/events",
        "/v1/residents/resident_demo_a/memory",
        "/v1/events/evt_phase2_demo",
    )

    responses = [
        api_client.get(path, headers=other_tenant_headers)
        for path in paths
    ]

    assert [response.status_code for response in responses] == [404] * len(paths)
    assert {response.text for response in responses} == {
        '{"error":{"schema_version":"1.0","code":"not_found",'
        '"message":"Resource not found","field":null}}'
    }


def test_missing_and_cross_tenant_event_are_indistinguishable(
    api_client: TestClient,
) -> None:
    missing = api_client.get("/v1/events/evt_missing", headers=ACCESS_HEADERS)
    cross_tenant = api_client.get(
        "/v1/events/evt_phase2_demo",
        headers={
            "X-Tenant-Id": "tenant_other",
            "X-Actor-Id": "operator_1",
        },
    )

    assert missing.status_code == cross_tenant.status_code == 404
    assert missing.json() == cross_tenant.json()


def test_openapi_documents_versioned_success_and_not_found_contracts(
    api_client: TestClient,
) -> None:
    paths = api_client.get("/openapi.json").json()["paths"]

    assert paths["/v1/residents"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"].endswith("/ResidentListResponse")
    for path in (
        "/v1/residents/{resident_id}",
        "/v1/residents/{resident_id}/events",
        "/v1/residents/{resident_id}/memory",
        "/v1/events/{event_id}",
    ):
        assert paths[path]["get"]["responses"]["404"]["content"][
            "application/json"
        ]["schema"]["$ref"].endswith("/ErrorEnvelope")


def test_missing_access_header_uses_the_versioned_error_contract(
    api_client: TestClient,
) -> None:
    response = api_client.get(
        "/v1/residents",
        headers={"X-Tenant-Id": "tenant_demo"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "schema_version": "1.0",
            "code": "invalid_input",
            "message": "Invalid request",
            "field": "X-Actor-Id",
        }
    }


def test_blank_access_header_uses_the_versioned_error_contract(
    api_client: TestClient,
) -> None:
    response = api_client.get(
        "/v1/residents",
        headers={"X-Tenant-Id": "  ", "X-Actor-Id": "operator_1"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "schema_version": "1.0",
            "code": "invalid_input",
            "message": "Invalid request",
            "field": "X-Tenant-Id",
        }
    }


def test_unexpected_errors_return_a_versioned_generic_response(
    api_client: TestClient,
) -> None:
    def fail_without_exposing_details() -> None:
        raise RuntimeError("private database connection details")

    api_client.app.dependency_overrides[query_service] = fail_without_exposing_details
    try:
        safe_client = TestClient(api_client.app, raise_server_exceptions=False)
        response = safe_client.get("/v1/residents", headers=ACCESS_HEADERS)
    finally:
        api_client.app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "schema_version": "1.0",
            "code": "internal_error",
            "message": "Internal server error",
            "field": None,
        }
    }
    assert "private database" not in response.text
