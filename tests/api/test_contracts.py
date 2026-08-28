from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from backend.app.contracts.events import (
    EventActionRequest,
    EventActionResponse,
    EventPriorityHistoryResponse,
    EventResponse,
)
from backend.app.contracts.feedback import MemoryEntryResponse, SubmitFeedbackRequest


UTC_TIMESTAMP = datetime(2026, 8, 24, 21, 2, 11, tzinfo=timezone.utc)
EVENT_PAYLOAD = {
    "event_id": "evt_contract_test",
    "episode_id": "episode_contract_test",
    "resident_id": "resident_contract_test",
    "room_id": "room_contract_test",
    "objective_family": "unknown_anomaly",
    "headline": "Contract test event",
    "priority": "watch",
    "status": "open",
    "created_at": UTC_TIMESTAMP,
    "last_signal_at": UTC_TIMESTAMP,
    "signal_count": 1,
    "related_event_ids": [],
    "recurrence_count": 1,
    "overdue_at": None,
    "overdue": False,
    "resolution_outcome": None,
    "action_history": [],
    "priority_history": [],
    "resident_memory_version": None,
    "resident_memory_entry_ids": [],
    "version": 1,
}
ACTIVE_MEMORY_ENTRY_PAYLOAD = {
    "entry_id": "memory_contract_test",
    "description": "assisted_movement",
    "source_kind": "feedback",
    "source_feedback_id": "fb_contract_test",
    "supersedes_entry_id": None,
    "status": "active",
    "created_by": "operator_1",
    "created_at": UTC_TIMESTAMP,
    "retired_by": None,
    "retired_at": None,
    "retirement_reason": None,
}
RETIRED_MEMORY_ENTRY_PAYLOAD = {
    **ACTIVE_MEMORY_ENTRY_PAYLOAD,
    "status": "retired",
    "retired_by": "operator_2",
    "retired_at": UTC_TIMESTAMP,
    "retirement_reason": "Routine ended",
}


@pytest.mark.parametrize(
    ("model_type", "valid_payload", "datetime_field"),
    (
        (
            EventActionResponse,
            {
                "action": "opened",
                "actor_id": "system:monitoring_event",
                "occurred_at": UTC_TIMESTAMP,
                "previous_status": "detected",
                "status": "open",
                "resolution_outcome": None,
            },
            "occurred_at",
        ),
        (
            EventPriorityHistoryResponse,
            {
                "previous_priority": None,
                "priority": "high",
                "actor_id": "system:monitoring_event",
                "changed_at": UTC_TIMESTAMP,
            },
            "changed_at",
        ),
        (
            EventResponse,
            EVENT_PAYLOAD,
            "created_at",
        ),
        (
            EventResponse,
            EVENT_PAYLOAD,
            "last_signal_at",
        ),
        (
            EventResponse,
            EVENT_PAYLOAD,
            "overdue_at",
        ),
        (
            MemoryEntryResponse,
            ACTIVE_MEMORY_ENTRY_PAYLOAD,
            "created_at",
        ),
        (
            MemoryEntryResponse,
            RETIRED_MEMORY_ENTRY_PAYLOAD,
            "retired_at",
        ),
    ),
)
@pytest.mark.parametrize(
    "invalid_timestamp",
    (
        datetime(2026, 8, 24, 21, 2, 11),
        datetime(
            2026,
            8,
            24,
            17,
            2,
            11,
            tzinfo=timezone(-timedelta(hours=4)),
        ),
    ),
    ids=("naive", "non_utc_offset"),
)
def test_public_datetime_contracts_reject_values_that_are_not_utc(
    model_type: type[BaseModel],
    valid_payload: dict[str, object],
    datetime_field: str,
    invalid_timestamp: datetime,
) -> None:
    payload = {**valid_payload, datetime_field: invalid_timestamp}

    with pytest.raises(ValidationError):
        model_type.model_validate(payload)


@pytest.mark.parametrize(
    ("model_type", "valid_payload", "datetime_field"),
    (
        (
            EventActionRequest,
            {"schema_version": "1.0", "occurred_at": UTC_TIMESTAMP},
            "occurred_at",
        ),
        (
            SubmitFeedbackRequest,
            {
                "schema_version": "1.0",
                "actual_event_label": "assisted_movement",
                "routine": True,
                "created_at": UTC_TIMESTAMP,
            },
            "created_at",
        ),
    ),
)
def test_public_command_contracts_require_version_and_utc(
    model_type: type[BaseModel],
    valid_payload: dict[str, object],
    datetime_field: str,
) -> None:
    model_type.model_validate(valid_payload)

    without_version = dict(valid_payload)
    without_version.pop("schema_version")
    with pytest.raises(ValidationError):
        model_type.model_validate(without_version)

    with pytest.raises(ValidationError):
        model_type.model_validate({**valid_payload, "schema_version": "2.0"})

    with pytest.raises(ValidationError):
        model_type.model_validate(
            {
                **valid_payload,
                datetime_field: datetime(
                    2026,
                    8,
                    24,
                    17,
                    2,
                    11,
                    tzinfo=timezone(-timedelta(hours=4)),
                ),
            }
        )


def test_every_read_operation_documents_versioned_method_not_allowed(
    api_client: TestClient,
) -> None:
    schema = api_client.get("/openapi.json").json()
    read_paths = (
        "/health",
        "/v1/residents",
        "/v1/residents/{resident_id}",
        "/v1/residents/{resident_id}/events",
        "/v1/residents/{resident_id}/memory",
        "/v1/residents/{resident_id}/status",
        "/v1/residents/{resident_id}/awareness",
        "/v1/residents/{resident_id}/calibration",
        "/v1/events/{event_id}",
        "/v1/devices",
        "/v1/devices/{device_id}/health",
    )

    for path in read_paths:
        responses = schema["paths"][path]["get"]["responses"]
        assert responses["405"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorEnvelope"
        }
