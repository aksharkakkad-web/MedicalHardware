"""Canonical mappings for replayable telemetry intelligence records."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json

from backend.app.contracts.ingestion import EdgeTelemetryEnvelope
from backend.app.db.models import EdgeTelemetryRow
from backend.app.intelligence.fusion import (
    AlignedFrame,
    FeatureEvidence,
)
from backend.app.intelligence.observations import (
    FeaturePurpose,
    FeatureValue,
    NormalizedObservation,
    QualityClass,
)


def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=True,
    )


def digest(value: object) -> str:
    return sha256(canonical_json(value).encode()).hexdigest()


def envelope_semantic_data(envelope: EdgeTelemetryEnvelope) -> dict[str, object]:
    """Return immutable packet content; transport retry metadata is not identity."""

    data = envelope.model_dump(mode="json")
    data.pop("transport", None)
    return data


def packet_hash(envelope: EdgeTelemetryEnvelope) -> str:
    return digest(envelope_semantic_data(envelope))


def packet_id(envelope: EdgeTelemetryEnvelope) -> str:
    identity = (
        envelope.tenant_id,
        envelope.device_id,
        envelope.source,
        envelope.stream_id,
        envelope.sequence,
        envelope.schema_version,
    )
    return "telemetry_" + sha256(repr(identity).encode()).hexdigest()[:24]


def capture_fingerprint(envelopes: tuple[EdgeTelemetryEnvelope, ...]) -> str:
    return digest(
        sorted(
            (envelope_semantic_data(item) for item in envelopes),
            key=lambda item: str(item["source"]),
        )
    )


def envelope_to_row(
    envelope: EdgeTelemetryEnvelope,
    *,
    batch_id: str,
    received_at: datetime,
    sequence_gap: int,
) -> EdgeTelemetryRow:
    return EdgeTelemetryRow(
        telemetry_id=packet_id(envelope),
        tenant_id=envelope.tenant_id,
        batch_id=batch_id,
        device_id=envelope.device_id,
        room_id=envelope.room_id,
        source=envelope.source,
        sensor_model=envelope.sensor_model,
        stream_id=envelope.stream_id,
        sequence=envelope.sequence,
        sequence_gap=sequence_gap,
        schema_version=envelope.schema_version,
        device_time=envelope.device_time,
        device_monotonic_ms=envelope.device_monotonic_ms,
        payload_format=envelope.payload_format,
        payload=envelope.payload,
        quality_reasons=list(envelope.quality_reasons),
        transport=envelope.transport.model_dump(mode="json"),
        payload_hash=packet_hash(envelope),
        received_at=utc(received_at),
    )


def envelope_from_row(row: EdgeTelemetryRow) -> EdgeTelemetryEnvelope:
    return EdgeTelemetryEnvelope.model_validate(
        {
            "schema_version": row.schema_version,
            "device_id": row.device_id,
            "tenant_id": row.tenant_id,
            "room_id": row.room_id,
            "source": row.source,
            "sensor_model": row.sensor_model,
            "stream_id": row.stream_id,
            "sequence": row.sequence,
            "device_time": (
                None if row.device_time is None else utc(row.device_time)
            ),
            "device_monotonic_ms": row.device_monotonic_ms,
            "payload_format": row.payload_format,
            "payload": row.payload,
            "quality_reasons": row.quality_reasons,
            "transport": row.transport,
        }
    )


def _feature_data(feature: FeatureValue) -> dict[str, object]:
    return {
        "name": feature.name,
        "value": feature.value,
        "unit": feature.unit,
        "quality_class": feature.quality_class.value,
        "quality_reasons": list(feature.quality_reasons),
        "purposes": [item.value for item in feature.purposes],
        "schema_version": feature.schema_version,
    }


def _feature_from_data(data: dict[str, object]) -> FeatureValue:
    return FeatureValue(
        name=str(data["name"]),
        value=data["value"],
        unit=str(data["unit"]),
        quality_class=QualityClass(str(data["quality_class"])),
        quality_reasons=tuple(str(item) for item in data["quality_reasons"]),
        purposes=tuple(FeaturePurpose(str(item)) for item in data["purposes"]),
        schema_version=str(data["schema_version"]),
    )


def observation_to_data(observation: NormalizedObservation) -> dict[str, object]:
    return {
        "observation_id": observation.observation_id,
        "tenant_id": observation.tenant_id,
        "room_id": observation.room_id,
        "resident_id": observation.resident_id,
        "device_id": observation.device_id,
        "source": observation.source,
        "window_start": observation.window_start.isoformat(),
        "window_end": observation.window_end.isoformat(),
        "features": [_feature_data(item) for item in observation.features],
        "source_quality_class": observation.source_quality_class.value,
        "source_quality_reasons": list(observation.source_quality_reasons),
        "processor_version": observation.processor_version,
        "schema_version": observation.schema_version,
    }


def observation_from_data(data: dict[str, object]) -> NormalizedObservation:
    features = data["features"]
    if not isinstance(features, list):
        raise ValueError("stored observation features must be a list")
    return NormalizedObservation(
        observation_id=str(data["observation_id"]),
        tenant_id=str(data["tenant_id"]),
        room_id=str(data["room_id"]),
        resident_id=str(data["resident_id"]),
        device_id=str(data["device_id"]),
        source=str(data["source"]),
        window_start=datetime.fromisoformat(str(data["window_start"])),
        window_end=datetime.fromisoformat(str(data["window_end"])),
        features=tuple(_feature_from_data(item) for item in features),
        source_quality_class=QualityClass(str(data["source_quality_class"])),
        source_quality_reasons=tuple(
            str(item) for item in data["source_quality_reasons"]
        ),
        processor_version=str(data["processor_version"]),
        schema_version=str(data["schema_version"]),
    )


def frame_to_data(frame: AlignedFrame) -> dict[str, object]:
    return {
        "frame_id": frame.frame_id,
        "tenant_id": frame.tenant_id,
        "room_id": frame.room_id,
        "resident_id": frame.resident_id,
        "window_start": frame.window_start.isoformat(),
        "window_end": frame.window_end.isoformat(),
        "sources_present": list(frame.sources_present),
        "sources_missing": list(frame.sources_missing),
        "feature_evidence": [
            {
                "source": item.source,
                "observation_id": item.observation_id,
                "feature": _feature_data(item.feature),
            }
            for item in frame.feature_evidence
        ],
        "agreements": list(frame.agreements),
        "contradictions": list(frame.contradictions),
        "schema_version": frame.schema_version,
    }


def frame_from_data(data: dict[str, object]) -> AlignedFrame:
    evidence = data["feature_evidence"]
    if not isinstance(evidence, list):
        raise ValueError("stored frame evidence must be a list")
    return AlignedFrame(
        frame_id=str(data["frame_id"]),
        tenant_id=str(data["tenant_id"]),
        room_id=str(data["room_id"]),
        resident_id=str(data["resident_id"]),
        window_start=datetime.fromisoformat(str(data["window_start"])),
        window_end=datetime.fromisoformat(str(data["window_end"])),
        sources_present=tuple(str(item) for item in data["sources_present"]),
        sources_missing=tuple(str(item) for item in data["sources_missing"]),
        feature_evidence=tuple(
            FeatureEvidence(
                source=str(item["source"]),
                observation_id=str(item["observation_id"]),
                feature=_feature_from_data(item["feature"]),
            )
            for item in evidence
        ),
        agreements=tuple(str(item) for item in data["agreements"]),
        contradictions=tuple(str(item) for item in data["contradictions"]),
        schema_version=str(data["schema_version"]),
    )


__all__ = [
    "canonical_json",
    "capture_fingerprint",
    "digest",
    "envelope_from_row",
    "envelope_to_row",
    "frame_from_data",
    "frame_to_data",
    "observation_from_data",
    "observation_to_data",
    "packet_hash",
    "packet_id",
    "utc",
]
