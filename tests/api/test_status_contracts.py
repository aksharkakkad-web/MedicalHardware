from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.app.contracts.status import (
    AwarenessTimelineResponse,
    CalibrationResponse,
    MonitoringStatusResponse,
    ResidentStatusResponse,
    SetupChangeRequest,
)


UTC_TIMESTAMP = datetime(2026, 8, 24, 21, 2, 11, tzinfo=timezone.utc)

MONITORING_PAYLOAD = {
    "schema_version": "1.0",
    "resident_id": "resident_demo_a",
    "room_id": "room_214",
    "observed_at": UTC_TIMESTAMP,
    "monitoring_state": "active",
    "presence_state": "resident_present",
    "baseline_learning_allowed": True,
    "resident_measurements_allowed": True,
    "reasons": [],
    "quality_policy_version": "synthetic_monitoring_quality_v1",
    "quality_policy_test_only": True,
}

CALIBRATION_PAYLOAD = {
    "schema_version": "1.0",
    "resident_id": "resident_demo_a",
    "version": 1,
    "recorded_at": UTC_TIMESTAMP,
    "setup_version": "setup_room_214_v1",
    "status": "established",
    "eligible_windows": 12,
    "excluded_windows": 2,
    "reason": "calibration_complete",
    "prior_setup_versions": [],
    "dimensions": [
        {
            "schema_version": "1.0",
            "dimension": "movement",
            "status": "established",
            "eligible_windows": 12,
            "excluded_windows": 2,
        }
    ],
    "setup_changes": [],
}

DEVICE_PAYLOAD = {
    "schema_version": "1.0",
    "device_id": "device_room_214",
    "display_label": "Room 214 monitor",
    "assignment": {
        "schema_version": "1.0",
        "location_id": "location_demo",
        "location_label": "Demo clinic",
        "room_id": "room_214",
        "room_label": "Room 214",
        "assigned_at": UTC_TIMESTAMP,
    },
    "health": {
        "schema_version": "1.0",
        "device_id": "device_room_214",
        "data_availability": "available",
        "state": "online",
        "observed_at": UTC_TIMESTAMP,
        "last_seen_at": UTC_TIMESTAMP,
        "sources": [],
        "limitations": [],
        "policy_version": "synthetic_device_health_v1",
        "policy_test_only": True,
    },
}


def test_status_contracts_expose_the_exact_frontend_fields() -> None:
    monitoring = MonitoringStatusResponse.model_validate(MONITORING_PAYLOAD)
    calibration = CalibrationResponse.model_validate(CALIBRATION_PAYLOAD)
    resident = ResidentStatusResponse.model_validate(
        {
            "schema_version": "1.0",
            "resident_id": "resident_demo_a",
            "room_id": "room_214",
            "data_availability": "available",
            "unavailable_reasons": [],
            "device_assignment_state": "assigned",
            "device": DEVICE_PAYLOAD,
            "monitoring": MONITORING_PAYLOAD,
            "calibration": CALIBRATION_PAYLOAD,
        }
    )
    awareness = AwarenessTimelineResponse.model_validate(
        {
            "schema_version": "1.0",
            "resident_id": "resident_demo_a",
            "items": [MONITORING_PAYLOAD],
        }
    )

    assert set(monitoring.model_dump()) == set(MONITORING_PAYLOAD)
    assert set(calibration.model_dump()) == set(CALIBRATION_PAYLOAD)
    assert resident.monitoring.resident_id == resident.resident_id
    assert awareness.items == [monitoring]
    assert calibration.dimensions[0].schema_version == "1.0"


@pytest.mark.parametrize(
    "invalid_payload",
    (
        {
            "reason": "device_moved",
            "affected_dimensions": ["movement"],
            "changed_at": UTC_TIMESTAMP,
            "expected_calibration_version": 1,
        },
        {
            "schema_version": "2.0",
            "reason": "device_moved",
            "affected_dimensions": ["movement"],
            "changed_at": UTC_TIMESTAMP,
            "expected_calibration_version": 1,
        },
        {
            "schema_version": "1.0",
            "reason": " ",
            "affected_dimensions": ["movement"],
            "changed_at": UTC_TIMESTAMP,
            "expected_calibration_version": 1,
        },
        {
            "schema_version": "1.0",
            "reason": "device_moved",
            "affected_dimensions": [],
            "changed_at": UTC_TIMESTAMP,
            "expected_calibration_version": 1,
        },
        {
            "schema_version": "1.0",
            "reason": "device_moved",
            "affected_dimensions": ["movement", "movement"],
            "changed_at": UTC_TIMESTAMP,
            "expected_calibration_version": 1,
        },
        {
            "schema_version": "1.0",
            "reason": "device_moved",
            "affected_dimensions": ["movement"],
            "changed_at": UTC_TIMESTAMP,
            "expected_calibration_version": -1,
        },
        {
            "schema_version": "1.0",
            "reason": "device_moved",
            "affected_dimensions": ["movement"],
            "changed_at": UTC_TIMESTAMP,
            "expected_calibration_version": 1,
            "surprise": True,
        },
    ),
)
def test_setup_change_rejects_unsafe_or_ambiguous_input(
    invalid_payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        SetupChangeRequest.model_validate(invalid_payload)


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
)
def test_status_contracts_reject_non_utc_timestamps(
    invalid_timestamp: datetime,
) -> None:
    with pytest.raises(ValidationError):
        MonitoringStatusResponse.model_validate(
            {**MONITORING_PAYLOAD, "observed_at": invalid_timestamp}
        )
    with pytest.raises(ValidationError):
        CalibrationResponse.model_validate(
            {**CALIBRATION_PAYLOAD, "recorded_at": invalid_timestamp}
        )
    with pytest.raises(ValidationError):
        SetupChangeRequest.model_validate(
            {
                "schema_version": "1.0",
                "reason": "device_moved",
                "affected_dimensions": ["movement"],
                "changed_at": invalid_timestamp,
                "expected_calibration_version": 1,
            }
        )


def test_nested_status_objects_require_known_schema_versions() -> None:
    invalid_dimension = {
        **CALIBRATION_PAYLOAD,
        "dimensions": [
            {
                **CALIBRATION_PAYLOAD["dimensions"][0],
                "schema_version": "2.0",
            }
        ],
    }
    with pytest.raises(ValidationError):
        CalibrationResponse.model_validate(invalid_dimension)

    with pytest.raises(ValidationError):
        ResidentStatusResponse.model_validate(
            {
                "schema_version": "1.0",
                "resident_id": "resident_demo_a",
                "room_id": "room_214",
                "data_availability": "available",
                "unavailable_reasons": [],
                "device_assignment_state": "assigned",
                "device": DEVICE_PAYLOAD,
                "monitoring": {**MONITORING_PAYLOAD, "unknown": True},
                "calibration": CALIBRATION_PAYLOAD,
            }
        )


@pytest.mark.parametrize(
    "device_fields",
    (
        {
            "device_assignment_state": "assigned",
            "device": None,
        },
        {
            "device_assignment_state": "assignment_unavailable",
            "device": DEVICE_PAYLOAD,
        },
        {
            "device_assignment_state": "assigned",
            "device": {
                **DEVICE_PAYLOAD,
                "assignment": {
                    **DEVICE_PAYLOAD["assignment"],
                    "room_id": "room_other",
                },
            },
        },
    ),
)
def test_resident_status_rejects_contradictory_device_composition(
    device_fields: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ResidentStatusResponse.model_validate(
            {
                "schema_version": "1.0",
                "resident_id": "resident_demo_a",
                "room_id": "room_214",
                "data_availability": "available",
                "unavailable_reasons": [],
                **device_fields,
                "monitoring": MONITORING_PAYLOAD,
                "calibration": CALIBRATION_PAYLOAD,
            }
        )
