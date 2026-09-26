"""EdgeTelemetryEnvelope construction, per docs/DATA_CONTRACT.md section 4.

Sequence numbers are strictly increasing per (device, source) stream, as the
contract requires. `device_time` stays null until the node has real wall-clock
time; `device_monotonic_ms` comes from the shared esp_timer clock that all
three modalities timestamp against.
"""

from __future__ import annotations

import itertools
import uuid
from dataclasses import dataclass, field

SCHEMA_VERSION = "1.0"

SENSOR_MODELS = {
    "radar": "MR60BHA2",
    "thermal": "MLX90640",
    "wifi_csi": "ESP32-S3",
}


@dataclass
class EnvelopeBuilder:
    device_id: str
    tenant_id: str
    room_id: str
    _seq: dict = field(default_factory=dict)

    def next_sequence(self, source: str) -> int:
        if source not in self._seq:
            self._seq[source] = itertools.count(1)
        return next(self._seq[source])

    def build(self, source: str, payload_format: str, payload: dict,
              device_monotonic_ms: int | None,
              quality_reasons: list[str] | None = None,
              batch_id: str | None = None, retry_count: int = 0) -> dict:
        env = {
            "schema_version": SCHEMA_VERSION,
            "device_id": self.device_id,
            "tenant_id": self.tenant_id,
            "room_id": self.room_id,
            "source": source,
            "sensor_model": SENSOR_MODELS.get(source, "unknown"),
            "sequence": self.next_sequence(source),
            # Null until the node has synchronised wall time. The contract
            # explicitly allows this and says not to assume device clocks.
            "device_time": None,
            "device_monotonic_ms": device_monotonic_ms,
            "payload_format": payload_format,
            "payload": payload,
            "transport": {
                "batch_id": batch_id or uuid.uuid4().hex[:12],
                "retry_count": retry_count,
            },
        }
        # Not part of the frozen envelope, but the contract requires explicit
        # reasons for unavailable values, so carry them alongside.
        if quality_reasons:
            env["quality_reasons"] = quality_reasons
        return env

    def heartbeat(self, firmware_version: str, buffered: int,
                  sources_seen: list[str], status: str = "ok") -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "device_id": self.device_id,
            "sequence": self.next_sequence("_heartbeat"),
            "device_monotonic_ms": None,
            "firmware_version": firmware_version,
            "buffered_packets": buffered,
            "sources_seen": sources_seen,
            "transport_status": status,
        }
