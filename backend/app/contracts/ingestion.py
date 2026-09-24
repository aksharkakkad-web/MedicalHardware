"""Versioned compact edge-telemetry ingestion contracts."""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    StringConstraints,
    field_validator,
    model_validator,
)

from backend.app.contracts.common import ContractModel, UTCDateTime


NonblankText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]
ReasonText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]
Score = Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
PositiveFloat = Annotated[float, Field(gt=0.0, allow_inf_nan=False)]
NonnegativeFloat = Annotated[float, Field(ge=0.0, allow_inf_nan=False)]
PositiveSequence = Annotated[int, Field(gt=0, strict=True)]
NonnegativeInteger = Annotated[int, Field(ge=0, strict=True)]

TelemetrySource = Literal["radar", "thermal", "wifi_csi"]
PayloadFormat = Literal[
    "radar_edge_features_v1",
    "mlx90640_edge_features_v1",
    "esp32_csi_edge_v1",
    "simulated_radar_edge_v1",
]

_SOURCE_FORMATS: dict[str, frozenset[str]] = {
    "radar": frozenset(
        {"radar_edge_features_v1", "simulated_radar_edge_v1"}
    ),
    "thermal": frozenset({"mlx90640_edge_features_v1"}),
    "wifi_csi": frozenset({"esp32_csi_edge_v1"}),
}
_MAX_CAPTURE_ITEMS = 8
_MAX_PAYLOAD_BYTES = 32_768


class _PayloadModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class RadarPayload(_PayloadModel):
    heart_rate_bpm: PositiveFloat | None = None
    respiration_rpm: PositiveFloat | None = None
    distance_m: NonnegativeFloat | None = None
    movement_score: Score | None = None
    signal_quality: Score | None = None
    tracked_height_m: NonnegativeFloat | None = None
    vertical_velocity_mps: FiniteFloat | None = None
    position_state: Literal["upright_like", "floor_like", "unknown"] | None = None


class ThermalPositionFeatures(_PayloadModel):
    near_floor_score: Score | None = None


class ThermalPayload(_PayloadModel):
    person_detected: bool | None = None
    centroid_x: Score | None = None
    centroid_y: Score | None = None
    temperature_trend_c: FiniteFloat | None = None
    max_observed_temp_c: FiniteFloat | None = None
    position_features: ThermalPositionFeatures | None = None
    signal_quality: Score | None = None
    tracked_height_m: NonnegativeFloat | None = None
    vertical_velocity_mps: FiniteFloat | None = None
    position_state: Literal["upright_like", "floor_like", "unknown"] | None = None


class WifiCsiPayload(_PayloadModel):
    presence_score: Score | None = None
    movement_score: Score | None = None
    rf_disturbance_score: Score | None = None
    respiration_feature: Score | None = None
    signal_quality: Score | None = None


class TelemetryTransport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    batch_id: NonblankText
    retry_count: NonnegativeInteger = 0


class EdgeTelemetryEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1.0"]
    device_id: NonblankText
    tenant_id: NonblankText
    room_id: NonblankText
    source: TelemetrySource
    sensor_model: NonblankText
    stream_id: NonblankText = "legacy"
    sequence: PositiveSequence
    device_time: UTCDateTime | None
    device_monotonic_ms: NonnegativeInteger | None
    payload_format: PayloadFormat
    payload: dict[str, Any]
    quality_reasons: tuple[ReasonText, ...] = ()
    transport: TelemetryTransport

    @field_validator("quality_reasons", mode="before")
    @classmethod
    def _quality_reasons_to_tuple(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("quality_reasons")
    @classmethod
    def _unique_quality_reasons(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("quality_reasons must not contain duplicates")
        return value

    @model_validator(mode="after")
    def _validate_source_payload(self) -> "EdgeTelemetryEnvelope":
        if self.payload_format not in _SOURCE_FORMATS[self.source]:
            raise ValueError(
                f"payload_format {self.payload_format!r} is invalid for source "
                f"{self.source!r}"
            )
        if len(json.dumps(self.payload, separators=(",", ":")).encode()) > _MAX_PAYLOAD_BYTES:
            raise ValueError("payload exceeds 32768 bytes")
        null_fields = tuple(
            sorted(field for field, value in self.payload.items() if value is None)
        )
        if null_fields:
            raise ValueError(
                "payload measurement fields must be omitted instead of null: "
                + ", ".join(null_fields)
            )
        model_type: type[_PayloadModel]
        if self.source == "radar":
            model_type = RadarPayload
        elif self.source == "thermal":
            model_type = ThermalPayload
        else:
            model_type = WifiCsiPayload
        parsed = model_type.model_validate(self.payload)
        normalized = parsed.model_dump(exclude_none=True, mode="python")
        self.payload.clear()
        self.payload.update(normalized)
        return self


class TelemetryCaptureRequest(RootModel[list[EdgeTelemetryEnvelope]]):
    @model_validator(mode="before")
    @classmethod
    def _wrap_one_envelope(cls, value: object) -> object:
        if isinstance(value, dict):
            return [value]
        return value

    @model_validator(mode="after")
    def _validate_capture(self) -> "TelemetryCaptureRequest":
        if not self.root:
            raise ValueError("capture must contain at least one envelope")
        if len(self.root) > _MAX_CAPTURE_ITEMS:
            raise ValueError("capture must contain at most 8 envelopes")
        tenants = {item.tenant_id for item in self.root}
        devices = {item.device_id for item in self.root}
        rooms = {item.room_id for item in self.root}
        sources = tuple(item.source for item in self.root)
        if len(tenants) != 1:
            raise ValueError("capture must belong to one tenant")
        if len(devices) != 1:
            raise ValueError("capture must belong to one device")
        if len(rooms) != 1:
            raise ValueError("capture must belong to one room")
        if len(set(sources)) != len(sources):
            raise ValueError("capture must not contain a duplicate source")
        return self


class DeviceHeartbeatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1.0"]
    device_id: NonblankText
    stream_id: NonblankText = "legacy"
    sequence: PositiveSequence
    device_monotonic_ms: NonnegativeInteger | None
    firmware_version: NonblankText
    buffered_packets: NonnegativeInteger
    sources_seen: tuple[TelemetrySource, ...]
    transport_status: NonblankText

    @field_validator("sources_seen", mode="before")
    @classmethod
    def _sources_to_tuple(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("sources_seen")
    @classmethod
    def _unique_sources(
        cls,
        value: tuple[TelemetrySource, ...],
    ) -> tuple[TelemetrySource, ...]:
        if len(set(value)) != len(value):
            raise ValueError("sources_seen must not contain duplicate sources")
        return value


class TelemetryIngestItemResponse(ContractModel):
    source: TelemetrySource
    sequence: int
    status: Literal["accepted", "duplicate", "rejected"]
    errors: tuple[str, ...] = ()


class TelemetryIngestResponse(ContractModel):
    batch_id: str
    accepted: int
    duplicate_count: int
    rejected: int
    duplicate: bool
    processing_state: Literal[
        "pending",
        "processing",
        "processed",
        "calibrating",
        "blocked",
        "failed",
    ]
    results: tuple[TelemetryIngestItemResponse, ...]


class HeartbeatIngestResponse(ContractModel):
    device_id: str
    sequence: int
    duplicate: bool
    health_state: Literal[
        "online",
        "offline",
        "degraded",
        "buffering",
        "retrying",
        "assignment_unavailable",
    ]


__all__ = [
    "DeviceHeartbeatRequest",
    "EdgeTelemetryEnvelope",
    "HeartbeatIngestResponse",
    "PayloadFormat",
    "TelemetryCaptureRequest",
    "TelemetryIngestItemResponse",
    "TelemetryIngestResponse",
    "TelemetrySource",
    "TelemetryTransport",
]
