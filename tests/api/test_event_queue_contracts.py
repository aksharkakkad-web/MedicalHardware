from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.app.contracts.events import (
    ClinicEventQueueResponse,
    ClinicEventStatus,
    EventResponse,
)


def _event() -> EventResponse:
    at = datetime(2026, 8, 24, 21, 2, 11, tzinfo=timezone.utc)
    return EventResponse(
        event_id="evt_contract",
        episode_id="episode_contract",
        resident_id="resident_demo_a",
        room_id="room_214",
        objective_family="unusual_movement",
        headline="Unusual movement detected",
        priority="high",
        status="open",
        created_at=at,
        last_signal_at=at,
        signal_count=1,
        related_event_ids=[],
        recurrence_count=1,
        overdue_at=None,
        overdue=False,
        resolution_outcome=None,
        action_history=[],
        priority_history=[],
        resident_memory_version=None,
        resident_memory_entry_ids=[],
        version=1,
    )


def test_clinic_queue_response_is_versioned_and_reuses_event_contract() -> None:
    response = ClinicEventQueueResponse(
        items=[_event()],
        total_items=2,
        next_cursor="opaque-next-page",
    )

    assert response.model_dump(mode="json") == {
        "schema_version": "1.0",
        "items": [_event().model_dump(mode="json")],
        "total_items": 2,
        "next_cursor": "opaque-next-page",
    }


def test_clinic_queue_response_rejects_impossible_totals_and_blank_cursor() -> None:
    invalid_values = (
        {"items": [], "total_items": -1, "next_cursor": None},
        {"items": [_event()], "total_items": 0, "next_cursor": None},
        {"items": [], "total_items": 0, "next_cursor": "   "},
    )

    for values in invalid_values:
        with pytest.raises(ValidationError):
            ClinicEventQueueResponse(**values)


def test_clinic_event_status_excludes_internal_detected_state() -> None:
    assert {status.value for status in ClinicEventStatus} == {
        "open",
        "acknowledged",
        "checked",
        "resolved",
    }

