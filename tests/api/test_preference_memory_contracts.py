from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.app.contracts.feedback import (
    AddMemoryEntryRequest,
    CorrectMemoryEntryRequest,
    MemoryEntryResponse,
    RetireMemoryEntryRequest,
)
from backend.app.contracts.preferences import (
    AwarenessDeliveryPreferences,
    EventDeliveryPreferences,
    ResidentNotificationPreferencesResponse,
    UpdateNotificationPreferencesRequest,
)


UTC_TIMESTAMP = datetime(2026, 8, 25, 15, 0, tzinfo=timezone.utc)
EVENT_DELIVERY = {"watch": False, "high": True, "critical": True}
AWARENESS_DELIVERY = {
    "away": True,
    "return": True,
    "limited": False,
    "unavailable": True,
}


def test_preference_update_contract_is_strict_and_versioned() -> None:
    request = UpdateNotificationPreferencesRequest.model_validate(
        {
            "schema_version": "1.0",
            "expected_version": 0,
            "event_delivery": EVENT_DELIVERY,
            "awareness_delivery": AWARENESS_DELIVERY,
            "changed_at": UTC_TIMESTAMP,
        }
    )

    assert request.expected_version == 0
    assert request.event_delivery.watch is False
    assert request.awareness_delivery.return_ is True

    invalid_payloads = (
        {"expected_version": -1},
        {"expected_version": True},
        {"event_delivery": {**EVENT_DELIVERY, "watch": 1}},
        {"awareness_delivery": {**AWARENESS_DELIVERY, "away": "yes"}},
        {"changed_at": "2026-08-25T11:00:00-04:00"},
    )
    valid = {
        "schema_version": "1.0",
        "expected_version": 0,
        "event_delivery": EVENT_DELIVERY,
        "awareness_delivery": AWARENESS_DELIVERY,
        "changed_at": UTC_TIMESTAMP,
    }
    for change in invalid_payloads:
        with pytest.raises(ValidationError):
            UpdateNotificationPreferencesRequest.model_validate(
                {**valid, **change}
            )


def test_delivery_contracts_forbid_missing_or_extra_choices() -> None:
    EventDeliveryPreferences.model_validate(EVENT_DELIVERY)
    AwarenessDeliveryPreferences.model_validate(AWARENESS_DELIVERY)

    with pytest.raises(ValidationError):
        EventDeliveryPreferences.model_validate(
            {"watch": True, "high": True}
        )
    with pytest.raises(ValidationError):
        AwarenessDeliveryPreferences.model_validate(
            {**AWARENESS_DELIVERY, "visitor": True}
        )


def test_preference_response_requires_honest_available_shape() -> None:
    available = ResidentNotificationPreferencesResponse.model_validate(
        {
            "resident_id": "resident_demo_a",
            "data_availability": "available",
            "version": 1,
            "event_delivery": EVENT_DELIVERY,
            "awareness_delivery": AWARENESS_DELIVERY,
            "high_critical_dashboard_visibility": "always_visible",
            "changed_by": "operator_1",
            "changed_at": UTC_TIMESTAMP,
        }
    )
    assert available.version == 1

    with pytest.raises(ValidationError):
        ResidentNotificationPreferencesResponse.model_validate(
            {
                **available.model_dump(),
                "data_availability": "not_yet_available",
            }
        )


def test_preference_response_requires_honest_missing_shape() -> None:
    missing = ResidentNotificationPreferencesResponse.model_validate(
        {
            "resident_id": "resident_new",
            "data_availability": "not_yet_available",
            "version": None,
            "event_delivery": None,
            "awareness_delivery": None,
            "high_critical_dashboard_visibility": "always_visible",
            "changed_by": None,
            "changed_at": None,
        }
    )
    assert missing.version is None

    with pytest.raises(ValidationError):
        ResidentNotificationPreferencesResponse.model_validate(
            {
                **missing.model_dump(),
                "event_delivery": EVENT_DELIVERY,
            }
        )


@pytest.mark.parametrize(
    ("model_type", "body"),
    (
        (
            AddMemoryEntryRequest,
            {
                "description": "Assisted standing is common before breakfast.",
            },
        ),
        (
            CorrectMemoryEntryRequest,
            {
                "description": "Assisted standing is common after breakfast.",
                "reason": "The routine time was entered incorrectly.",
            },
        ),
        (
            RetireMemoryEntryRequest,
            {"reason": "This routine is no longer current."},
        ),
    ),
)
def test_memory_admin_requests_require_version_nonblank_text_and_utc(
    model_type: type,
    body: dict[str, object],
) -> None:
    valid = {
        "schema_version": "1.0",
        "expected_version": 2,
        "changed_at": UTC_TIMESTAMP,
        **body,
    }
    model_type.model_validate(valid)

    with pytest.raises(ValidationError):
        model_type.model_validate({**valid, "expected_version": True})
    with pytest.raises(ValidationError):
        model_type.model_validate({**valid, "expected_version": -1})
    with pytest.raises(ValidationError):
        model_type.model_validate({**valid, "changed_at": "2026-08-25T15:00:00"})

    text_field = "description" if "description" in body else "reason"
    with pytest.raises(ValidationError):
        model_type.model_validate({**valid, text_field: "   "})


def test_memory_entry_contract_requires_consistent_provenance() -> None:
    feedback_entry = {
        "entry_id": "memory_feedback",
        "description": "assisted_movement",
        "source_kind": "feedback",
        "source_feedback_id": "fb_001",
        "supersedes_entry_id": None,
        "status": "active",
        "created_by": "operator_1",
        "created_at": UTC_TIMESTAMP,
        "retired_by": None,
        "retired_at": None,
        "retirement_reason": None,
    }
    MemoryEntryResponse.model_validate(feedback_entry)

    operator_entry = {
        **feedback_entry,
        "entry_id": "memory_operator",
        "source_kind": "operator",
        "source_feedback_id": None,
    }
    MemoryEntryResponse.model_validate(operator_entry)

    with pytest.raises(ValidationError):
        MemoryEntryResponse.model_validate(
            {**feedback_entry, "source_feedback_id": None}
        )
    with pytest.raises(ValidationError):
        MemoryEntryResponse.model_validate(
            {**operator_entry, "source_feedback_id": "fb_impossible"}
        )


def test_memory_entry_contract_requires_consistent_retirement_metadata() -> None:
    active = {
        "entry_id": "memory_operator",
        "description": "Morning routine",
        "source_kind": "operator",
        "source_feedback_id": None,
        "supersedes_entry_id": None,
        "status": "active",
        "created_by": "operator_1",
        "created_at": UTC_TIMESTAMP,
        "retired_by": None,
        "retired_at": None,
        "retirement_reason": None,
    }
    MemoryEntryResponse.model_validate(active)

    with pytest.raises(ValidationError):
        MemoryEntryResponse.model_validate(
            {**active, "retired_by": "operator_2"}
        )

    retired = {
        **active,
        "status": "retired",
        "retired_by": "operator_2",
        "retired_at": UTC_TIMESTAMP,
        "retirement_reason": "No longer current",
    }
    MemoryEntryResponse.model_validate(retired)

    with pytest.raises(ValidationError):
        MemoryEntryResponse.model_validate(
            {**retired, "retirement_reason": None}
        )
