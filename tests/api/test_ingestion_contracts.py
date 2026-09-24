import json
from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.contracts.ingestion import (
    DeviceHeartbeatRequest,
    EdgeTelemetryEnvelope,
    TelemetryCaptureRequest,
)


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "edge_telemetry"
    / "mahin_capture_v1.json"
)


def _capture() -> list[dict[str, object]]:
    return json.loads(FIXTURE.read_text())


def _radar(**changes: object) -> dict[str, object]:
    envelope = deepcopy(_capture()[0])
    envelope.update(changes)
    return envelope


def test_current_mahin_capture_parses_without_rewrite() -> None:
    parsed = TelemetryCaptureRequest.model_validate_json(FIXTURE.read_text())

    assert [item.source for item in parsed.root] == [
        "radar",
        "thermal",
        "wifi_csi",
    ]
    assert all(item.stream_id == "legacy" for item in parsed.root)
    assert [item.transport.batch_id for item in parsed.root] == [
        "radar-batch-41",
        "thermal-batch-38",
        "csi-batch-52",
    ]
    assert parsed.root[1].quality_reasons == (
        "temperature trend needs more history",
    )


def test_single_envelope_is_normalized_to_one_capture() -> None:
    parsed = TelemetryCaptureRequest.model_validate(_radar())

    assert len(parsed.root) == 1
    assert parsed.root[0].source == "radar"


def test_null_measurement_is_rejected_but_omission_is_valid() -> None:
    payload = {"heart_rate_bpm": None}
    with pytest.raises(ValidationError, match="heart_rate_bpm"):
        EdgeTelemetryEnvelope.model_validate(_radar(payload=payload))

    parsed = EdgeTelemetryEnvelope.model_validate(_radar(payload={}))
    assert parsed.payload == {}


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        ({"payload_format": "mlx90640_edge_features_v1"}, "payload_format"),
        ({"sequence": 0}, "sequence"),
        ({"unknown": "value"}, "Extra inputs"),
        ({"payload": {"signal_quality": 1.01}}, "signal_quality"),
        ({"payload": {"distance_m": float("inf")}}, "distance_m"),
        ({"stream_id": ""}, "stream_id"),
    ),
)
def test_invalid_envelope_is_rejected(
    changes: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        EdgeTelemetryEnvelope.model_validate(_radar(**changes))


def test_capture_requires_one_device_room_tenant_and_unique_sources() -> None:
    mixed_device = _capture()
    mixed_device[1]["device_id"] = "device_other"
    with pytest.raises(ValidationError, match="one device"):
        TelemetryCaptureRequest.model_validate(mixed_device)

    mixed_room = _capture()
    mixed_room[1]["room_id"] = "room_other"
    with pytest.raises(ValidationError, match="one room"):
        TelemetryCaptureRequest.model_validate(mixed_room)

    mixed_tenant = _capture()
    mixed_tenant[1]["tenant_id"] = "tenant_other"
    with pytest.raises(ValidationError, match="one tenant"):
        TelemetryCaptureRequest.model_validate(mixed_tenant)

    duplicate_source = _capture()
    duplicate_source.append(deepcopy(duplicate_source[0]))
    duplicate_source[-1]["sequence"] = 42
    with pytest.raises(ValidationError, match="duplicate source"):
        TelemetryCaptureRequest.model_validate(duplicate_source)


def test_capture_size_is_bounded() -> None:
    oversized = [_radar(sequence=index + 1) for index in range(9)]
    with pytest.raises(ValidationError, match="at most 8"):
        TelemetryCaptureRequest.model_validate(oversized)


def test_stream_id_allows_explicit_device_boot_identity() -> None:
    parsed = EdgeTelemetryEnvelope.model_validate(
        _radar(stream_id="boot-01", device_monotonic_ms=1234)
    )

    assert parsed.stream_id == "boot-01"
    assert parsed.device_monotonic_ms == 1234


def test_current_hardware_heartbeat_parses() -> None:
    heartbeat = DeviceHeartbeatRequest.model_validate(
        {
            "schema_version": "1.0",
            "device_id": "device_room_214",
            "sequence": 9,
            "device_monotonic_ms": None,
            "firmware_version": "bench-0.1.0",
            "buffered_packets": 0,
            "sources_seen": ["radar", "thermal", "wifi_csi"],
            "transport_status": "ok",
        }
    )

    assert heartbeat.stream_id == "legacy"
    assert heartbeat.sources_seen == ("radar", "thermal", "wifi_csi")


def test_heartbeat_rejects_duplicate_or_unknown_sources() -> None:
    base = {
        "schema_version": "1.0",
        "device_id": "device_room_214",
        "sequence": 9,
        "device_monotonic_ms": None,
        "firmware_version": "bench-0.1.0",
        "buffered_packets": 0,
        "transport_status": "ok",
    }
    with pytest.raises(ValidationError, match="duplicate"):
        DeviceHeartbeatRequest.model_validate(
            {**base, "sources_seen": ["radar", "radar"]}
        )
    with pytest.raises(ValidationError, match="sources_seen"):
        DeviceHeartbeatRequest.model_validate(
            {**base, "sources_seen": ["camera"]}
        )
