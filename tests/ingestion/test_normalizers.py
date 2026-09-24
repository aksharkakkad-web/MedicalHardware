import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.app.contracts.ingestion import EdgeTelemetryEnvelope
from backend.app.ingestion.assignment import MonitoringAssignment
from backend.app.ingestion.normalizers import normalize_envelope
from backend.app.intelligence import FeaturePurpose, QualityClass


NOW = datetime(2026, 9, 23, 16, 0, tzinfo=timezone.utc)
FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "edge_telemetry"
    / "mahin_capture_v1.json"
)
ASSIGNMENT = MonitoringAssignment(
    tenant_id="tenant_demo",
    device_id="device_room_214",
    room_id="room_214",
    resident_id="resident_demo_a",
    device_assignment_id="device_assign_room_214",
    resident_assignment_id="resident_assign_room_214",
)


def _raw(source: str) -> dict[str, object]:
    return next(
        deepcopy(item)
        for item in json.loads(FIXTURE.read_text())
        if item["source"] == source
    )


def _envelope(source: str, **changes: object) -> EdgeTelemetryEnvelope:
    raw = _raw(source)
    raw.update(changes)
    return EdgeTelemetryEnvelope.model_validate(raw)


def _features(observation) -> dict[str, object]:
    return {item.name: item for item in observation.features}


def test_radar_maps_current_and_future_neutral_features() -> None:
    raw = _raw("radar")
    raw["payload"].update(
        {
            "movement_score": 0.2,
            "tracked_height_m": 1.6,
            "vertical_velocity_mps": -0.4,
            "position_state": "upright_like",
        }
    )

    observation = normalize_envelope(
        EdgeTelemetryEnvelope.model_validate(raw), ASSIGNMENT, NOW
    )
    features = _features(observation)

    assert features["respiratory_rate"].unit == "rpm"
    assert features["respiratory_rate"].purposes == (FeaturePurpose.RESPIRATION,)
    assert features["heart_rate"].purposes == (FeaturePurpose.PHYSIOLOGY,)
    assert features["movement_energy"].value == 0.2
    assert features["distance_from_sensor"].purposes == (
        FeaturePurpose.POSTURE,
        FeaturePurpose.PRESENCE,
    )
    assert features["tracked_height"].unit == "m"
    assert features["vertical_velocity"].unit == "m/s"
    assert features["position_state"].value == "upright_like"


def test_missing_vital_is_not_invented() -> None:
    raw = _raw("radar")
    del raw["payload"]["heart_rate_bpm"]

    observation = normalize_envelope(
        EdgeTelemetryEnvelope.model_validate(raw), ASSIGNMENT, NOW
    )

    assert "heart_rate" not in _features(observation)


def test_thermal_maps_presence_position_and_temperature_without_guessing() -> None:
    observation = normalize_envelope(_envelope("thermal"), ASSIGNMENT, NOW)
    features = _features(observation)

    assert features["person_detected"].value is True
    assert features["vertical_position"].value == 0.41
    assert features["near_floor_score"].value == 0.08
    assert features["max_observed_temperature"].unit == "C"
    assert "temperature_trend" not in features
    assert observation.source_quality_class is QualityClass.LIMITED
    assert observation.source_quality_reasons == (
        "temperature trend needs more history",
    )
    assert features["person_detected"].quality_class is QualityClass.GOOD


def test_wifi_csi_maps_present_evidence_and_diagnostics() -> None:
    observation = normalize_envelope(_envelope("wifi_csi"), ASSIGNMENT, NOW)
    features = _features(observation)

    assert features["presence_score"].purposes == (FeaturePurpose.PRESENCE,)
    assert features["movement_energy"].purposes == (FeaturePurpose.MOVEMENT,)
    assert features["respiration_periodicity"].purposes == (
        FeaturePurpose.RESPIRATION,
    )
    assert features["rf_disturbance"].quality_class is QualityClass.LIMITED
    assert features["signal_health"].quality_class is QualityClass.LIMITED


def test_empty_payload_becomes_unusable_instead_of_fabricated_zero() -> None:
    observation = normalize_envelope(
        _envelope("radar", payload={}), ASSIGNMENT, NOW
    )

    assert observation.source_quality_class is QualityClass.UNUSABLE
    assert len(observation.features) == 1
    assert observation.features[0].name == "source_unavailable"
    assert observation.features[0].value is None
    assert observation.features[0].quality_class is QualityClass.UNUSABLE


def test_observation_identity_and_capture_window_are_deterministic() -> None:
    first = normalize_envelope(_envelope("radar"), ASSIGNMENT, NOW)
    second = normalize_envelope(_envelope("radar"), ASSIGNMENT, NOW)
    later = normalize_envelope(
        _envelope("radar", sequence=42), ASSIGNMENT, NOW
    )

    assert first.observation_id == second.observation_id
    assert first.observation_id != later.observation_id
    assert first.window_start == NOW - timedelta(seconds=5)
    assert first.window_end == NOW


def test_assignment_identity_must_match_envelope() -> None:
    mismatched = MonitoringAssignment(
        tenant_id="tenant_demo",
        device_id="device_room_214",
        room_id="room_other",
        resident_id="resident_other",
        device_assignment_id="device_assignment_other",
        resident_assignment_id="resident_assignment_other",
    )

    with pytest.raises(ValueError, match="assignment must match telemetry envelope"):
        normalize_envelope(_envelope("radar"), mismatched, NOW)

