"""Versioned source translators for compact edge telemetry."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from backend.app.contracts.ingestion import EdgeTelemetryEnvelope
from backend.app.ingestion.assignment import MonitoringAssignment
from backend.app.intelligence import (
    FeaturePurpose,
    FeatureValue,
    NormalizedObservation,
    QualityClass,
)


_WINDOW_DURATION = timedelta(seconds=5)
_PROCESSOR_VERSIONS = {
    "radar": "radar_normalizer_v1",
    "thermal": "thermal_normalizer_v1",
    "wifi_csi": "wifi_csi_normalizer_v1",
}


def normalize_envelope(
    envelope: EdgeTelemetryEnvelope,
    assignment: MonitoringAssignment,
    received_at: datetime,
) -> NormalizedObservation:
    if (
        envelope.tenant_id,
        envelope.device_id,
        envelope.room_id,
    ) != (
        assignment.tenant_id,
        assignment.device_id,
        assignment.room_id,
    ):
        raise ValueError("assignment must match telemetry envelope")
    window_end = _utc(received_at)
    processor_version = _PROCESSOR_VERSIONS[envelope.source]

    if envelope.source == "radar":
        features = _normalize_radar(envelope)
    elif envelope.source == "thermal":
        features = _normalize_thermal(envelope)
    else:
        features = _normalize_wifi_csi(envelope)

    source_reasons = tuple(envelope.quality_reasons)
    if not features:
        unavailable_reasons = tuple(sorted(set(source_reasons + ("no_measurements",))))
        features = (
            FeatureValue(
                name="source_unavailable",
                value=None,
                unit="state",
                quality_class=QualityClass.UNUSABLE,
                quality_reasons=unavailable_reasons,
                purposes=(),
            ),
        )
        source_quality = QualityClass.UNUSABLE
        source_reasons = unavailable_reasons
    elif source_reasons or _low_signal(envelope):
        low_signal = _low_signal(envelope)
        if low_signal:
            source_reasons = tuple(sorted(set(source_reasons + ("low_signal_quality",))))
        source_quality = QualityClass.LIMITED
        if low_signal:
            features = tuple(
                replace(
                    feature,
                    quality_class=QualityClass.LIMITED,
                    quality_reasons=tuple(
                        sorted(
                            set((*feature.quality_reasons, "low_signal_quality"))
                        )
                    ),
                )
                for feature in features
            )
    else:
        source_quality = QualityClass.GOOD

    return NormalizedObservation(
        observation_id=_observation_id(envelope, processor_version),
        tenant_id=assignment.tenant_id,
        room_id=assignment.room_id,
        resident_id=assignment.resident_id,
        device_id=assignment.device_id,
        source=envelope.source,
        window_start=window_end - _WINDOW_DURATION,
        window_end=window_end,
        features=tuple(features),
        source_quality_class=source_quality,
        source_quality_reasons=source_reasons,
        processor_version=processor_version,
    )


def _normalize_radar(envelope: EdgeTelemetryEnvelope) -> tuple[FeatureValue, ...]:
    payload = envelope.payload
    return tuple(
        feature
        for feature in (
            _good(payload, "movement_score", "movement_energy", "normalized", FeaturePurpose.MOVEMENT),
            _good(payload, "respiration_rpm", "respiratory_rate", "rpm", FeaturePurpose.RESPIRATION),
            _good(payload, "heart_rate_bpm", "heart_rate", "bpm", FeaturePurpose.PHYSIOLOGY),
            _good(payload, "distance_m", "distance_from_sensor", "m", FeaturePurpose.POSTURE, FeaturePurpose.PRESENCE),
            _good(payload, "tracked_height_m", "tracked_height", "m", FeaturePurpose.POSTURE),
            _good(payload, "vertical_velocity_mps", "vertical_velocity", "m/s", FeaturePurpose.POSTURE),
            _good(payload, "position_state", "position_state", "categorical", FeaturePurpose.POSTURE),
            _diagnostic(payload, "signal_quality", "signal_health", "normalized"),
        )
        if feature is not None
    )


def _normalize_thermal(envelope: EdgeTelemetryEnvelope) -> tuple[FeatureValue, ...]:
    payload = envelope.payload
    position = payload.get("position_features", {})
    if not isinstance(position, dict):
        position = {}
    return tuple(
        feature
        for feature in (
            _good(payload, "person_detected", "person_detected", "boolean", FeaturePurpose.PRESENCE),
            _good(payload, "centroid_x", "horizontal_position", "normalized", FeaturePurpose.POSTURE),
            _good(payload, "centroid_y", "vertical_position", "normalized", FeaturePurpose.POSTURE),
            _good(position, "near_floor_score", "near_floor_score", "normalized", FeaturePurpose.POSTURE),
            _good(payload, "max_observed_temp_c", "max_observed_temperature", "C", FeaturePurpose.PHYSIOLOGY),
            _good(payload, "temperature_trend_c", "temperature_trend", "C", FeaturePurpose.PHYSIOLOGY),
            _good(payload, "tracked_height_m", "tracked_height", "m", FeaturePurpose.POSTURE),
            _good(payload, "vertical_velocity_mps", "vertical_velocity", "m/s", FeaturePurpose.POSTURE),
            _good(payload, "position_state", "position_state", "categorical", FeaturePurpose.POSTURE),
            _diagnostic(payload, "signal_quality", "signal_health", "normalized"),
        )
        if feature is not None
    )


def _normalize_wifi_csi(envelope: EdgeTelemetryEnvelope) -> tuple[FeatureValue, ...]:
    payload = envelope.payload
    return tuple(
        feature
        for feature in (
            _good(payload, "presence_score", "presence_score", "normalized", FeaturePurpose.PRESENCE),
            _good(payload, "movement_score", "movement_energy", "normalized", FeaturePurpose.MOVEMENT),
            _good(payload, "respiration_feature", "respiration_periodicity", "normalized", FeaturePurpose.RESPIRATION),
            _diagnostic(payload, "rf_disturbance_score", "rf_disturbance", "normalized"),
            _diagnostic(payload, "signal_quality", "signal_health", "normalized"),
        )
        if feature is not None
    )


def _good(
    payload: dict[str, object],
    input_name: str,
    output_name: str,
    unit: str,
    *purposes: FeaturePurpose,
) -> FeatureValue | None:
    if input_name not in payload:
        return None
    return FeatureValue(
        name=output_name,
        value=payload[input_name],
        unit=unit,
        quality_class=QualityClass.GOOD,
        quality_reasons=(),
        purposes=tuple(purposes),
    )


def _diagnostic(
    payload: dict[str, object],
    input_name: str,
    output_name: str,
    unit: str,
) -> FeatureValue | None:
    if input_name not in payload:
        return None
    return FeatureValue(
        name=output_name,
        value=payload[input_name],
        unit=unit,
        quality_class=QualityClass.LIMITED,
        quality_reasons=("diagnostic_only",),
        purposes=(),
    )


def _low_signal(envelope: EdgeTelemetryEnvelope) -> bool:
    value = envelope.payload.get("signal_quality")
    return isinstance(value, (float, int)) and not isinstance(value, bool) and value < 0.5


def _observation_id(envelope: EdgeTelemetryEnvelope, processor_version: str) -> str:
    identity = "\x1f".join(
        (
            envelope.tenant_id,
            envelope.device_id,
            envelope.source,
            envelope.stream_id,
            str(envelope.sequence),
            envelope.schema_version,
            processor_version,
        )
    )
    return "obs_" + sha256(identity.encode()).hexdigest()[:24]


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("received_at must be a timezone-aware datetime")
    return value.astimezone(timezone.utc)


__all__ = ["normalize_envelope"]
