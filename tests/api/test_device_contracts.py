from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.app.contracts.devices import (
    DeviceAssignmentResponse,
    DeviceHealthResponse,
    DeviceListItemResponse,
    DeviceListResponse,
)


OBSERVED_AT = datetime(2026, 8, 25, 14, 0, tzinfo=timezone.utc)


HEALTH_PAYLOAD = {
    "schema_version": "1.0",
    "device_id": "device_room_214",
    "data_availability": "available",
    "state": "degraded",
    "observed_at": OBSERVED_AT,
    "last_seen_at": OBSERVED_AT - timedelta(seconds=5),
    "sources": [
        {
            "schema_version": "1.0",
            "source": "thermal",
            "state": "degraded",
            "limitations": ["reduced_frame_rate"],
        }
    ],
    "limitations": ["thermal_detail_reduced"],
    "policy_version": "synthetic_device_health_v1",
    "policy_test_only": True,
}


def test_device_contracts_expose_exact_frontend_fields() -> None:
    assignment = DeviceAssignmentResponse.model_validate(
        {
            "schema_version": "1.0",
            "location_id": "location_demo",
            "location_label": "Demo clinic",
            "room_id": "room_214",
            "room_label": "Room 214",
            "assigned_at": OBSERVED_AT,
        }
    )
    health = DeviceHealthResponse.model_validate(HEALTH_PAYLOAD)
    item = DeviceListItemResponse.model_validate(
        {
            "schema_version": "1.0",
            "device_id": "device_room_214",
            "display_label": "Room 214 monitor",
            "assignment": assignment.model_dump(),
            "health": HEALTH_PAYLOAD,
        }
    )
    response = DeviceListResponse(items=[item])

    assert set(health.model_dump()) == set(HEALTH_PAYLOAD)
    assert item.assignment == assignment
    assert response.items == [item]
    assert response.schema_version == "1.0"


def test_known_device_without_health_is_explicitly_not_yet_available() -> None:
    health = DeviceHealthResponse.model_validate(
        {
            "schema_version": "1.0",
            "device_id": "device_new",
            "data_availability": "not_yet_available",
            "state": None,
            "observed_at": None,
            "last_seen_at": None,
            "sources": [],
            "limitations": [],
            "policy_version": None,
            "policy_test_only": None,
        }
    )

    assert health.state is None
    assert health.data_availability == "not_yet_available"


@pytest.mark.parametrize(
    "payload",
    (
        {**HEALTH_PAYLOAD, "schema_version": "2.0"},
        {**HEALTH_PAYLOAD, "surprise": True},
        {**HEALTH_PAYLOAD, "observed_at": datetime(2026, 8, 25, 14, 0)},
        {
            **HEALTH_PAYLOAD,
            "observed_at": datetime(
                2026,
                8,
                25,
                10,
                0,
                tzinfo=timezone(-timedelta(hours=4)),
            ),
        },
        {**HEALTH_PAYLOAD, "policy_test_only": 1},
        {**HEALTH_PAYLOAD, "state": "healthy"},
        {
            **HEALTH_PAYLOAD,
            "data_availability": "not_yet_available",
        },
        {
            "schema_version": "1.0",
            "device_id": "device_new",
            "data_availability": "not_yet_available",
            "state": "offline",
            "observed_at": None,
            "last_seen_at": None,
            "sources": [],
            "limitations": [],
            "policy_version": None,
            "policy_test_only": None,
        },
    ),
)
def test_device_health_contract_rejects_unsafe_or_contradictory_data(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        DeviceHealthResponse.model_validate(payload)
