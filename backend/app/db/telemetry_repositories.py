"""Tenant-scoped durable telemetry, replay, and heartbeat repositories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.contracts.ingestion import (
    DeviceHeartbeatRequest,
    EdgeTelemetryEnvelope,
    TelemetryCaptureRequest,
)
from backend.app.db.models import (
    DeviceHeartbeatIdentityRow,
    EdgeTelemetryRow,
    FusedFrameRow,
    NormalizedObservationRow,
    TelemetryCaptureBatchRow,
)
from backend.app.db.telemetry_mappers import (
    canonical_json,
    capture_fingerprint,
    digest,
    envelope_from_row,
    envelope_to_row,
    frame_from_data,
    frame_to_data,
    observation_from_data,
    observation_to_data,
    packet_hash,
    utc,
)
from backend.app.intelligence.fusion import AlignedFrame
from backend.app.intelligence.observations import NormalizedObservation
from backend.app.services.errors import ConcurrentUpdateError, NotFoundError


_PROCESSING_STATES = frozenset(
    {"pending", "processing", "processed", "calibrating", "blocked", "failed"}
)


@dataclass(frozen=True)
class TelemetryPacketRecord:
    telemetry_id: str
    envelope: EdgeTelemetryEnvelope
    sequence_gap: int
    received_at: datetime

    @property
    def sequence(self) -> int:
        return self.envelope.sequence

    @property
    def stream_id(self) -> str:
        return self.envelope.stream_id


@dataclass(frozen=True)
class TelemetryBatchRecord:
    batch_id: str
    tenant_id: str
    device_id: str
    room_id: str
    request_fingerprint: str
    received_at: datetime
    processing_state: str
    processed_at: datetime | None
    processing_error: str | None
    packets: tuple[TelemetryPacketRecord, ...]
    duplicate: bool = False


@dataclass(frozen=True)
class HeartbeatRecord:
    tenant_id: str
    heartbeat: DeviceHeartbeatRequest
    received_at: datetime
    duplicate: bool = False


class TelemetryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_capture(
        self,
        capture: TelemetryCaptureRequest,
        *,
        received_at: datetime,
    ) -> TelemetryBatchRecord:
        if not isinstance(capture, TelemetryCaptureRequest):
            raise ValueError("capture must be a TelemetryCaptureRequest")
        received = utc(received_at)
        envelopes = tuple(capture.root)
        fingerprint = capture_fingerprint(envelopes)
        tenant_id = envelopes[0].tenant_id
        existing_batch = self._session.scalar(
            select(TelemetryCaptureBatchRow).where(
                TelemetryCaptureBatchRow.tenant_id == tenant_id,
                TelemetryCaptureBatchRow.request_fingerprint == fingerprint,
            )
        )
        if existing_batch is not None:
            return self._batch_record(existing_batch, duplicate=True)

        gaps: dict[str, int] = {}
        for envelope in envelopes:
            existing = self._packet_for_identity(envelope)
            if existing is not None:
                # A semantic exact retry would have matched the capture
                # fingerprint. Reusing one packet inside a different capture is
                # ambiguous and cannot safely create another fused frame.
                raise ConcurrentUpdateError(
                    "telemetry packet identity was reused by another capture"
                )
            latest = self._latest_sequence(envelope)
            if latest is not None and envelope.sequence <= latest:
                raise ConcurrentUpdateError("telemetry sequence is stale")
            gaps[envelope.source] = (
                0 if latest is None else max(0, envelope.sequence - latest - 1)
            )

        batch_id = "capture_" + sha256(fingerprint.encode()).hexdigest()[:24]
        batch_row = TelemetryCaptureBatchRow(
            tenant_id=tenant_id,
            batch_id=batch_id,
            device_id=envelopes[0].device_id,
            room_id=envelopes[0].room_id,
            request_fingerprint=fingerprint,
            received_at=received,
            processing_state="pending",
            processed_at=None,
            processing_error=None,
        )
        packet_rows = tuple(
            envelope_to_row(
                envelope,
                batch_id=batch_id,
                received_at=received,
                sequence_gap=gaps[envelope.source],
            )
            for envelope in envelopes
        )
        self._session.add(batch_row)
        # The rows intentionally have no ORM relationship; flush the parent
        # explicitly so SQLite and Postgres see the capture before its packets.
        self._session.flush((batch_row,))
        self._session.add_all(packet_rows)
        self._session.flush(packet_rows)
        return self._batch_record(batch_row)

    def get_batch(self, batch_id: str) -> TelemetryBatchRecord:
        row = self._session.scalar(
            select(TelemetryCaptureBatchRow).where(
                TelemetryCaptureBatchRow.batch_id == batch_id
            )
        )
        if row is None:
            raise NotFoundError()
        return self._batch_record(row)

    def pending_batches(self, *, limit: int) -> tuple[TelemetryBatchRecord, ...]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        rows = self._session.scalars(
            select(TelemetryCaptureBatchRow)
            .where(
                TelemetryCaptureBatchRow.processing_state.in_(("pending", "failed"))
            )
            .order_by(
                TelemetryCaptureBatchRow.received_at,
                TelemetryCaptureBatchRow.batch_id,
            )
            .limit(limit)
        ).all()
        return tuple(self._batch_record(row) for row in rows)

    def save_observation(
        self,
        batch_id: str,
        observation: NormalizedObservation,
    ) -> NormalizedObservation:
        batch = self._batch_row(batch_id)
        if observation.tenant_id != batch.tenant_id:
            raise ValueError("observation tenant must match capture batch")
        data = observation_to_data(observation)
        existing = self._session.get(
            NormalizedObservationRow,
            (batch.tenant_id, observation.observation_id),
        )
        if existing is not None:
            if existing.batch_id != batch_id or existing.observation != data:
                raise ConcurrentUpdateError()
            return observation_from_data(existing.observation)
        row = NormalizedObservationRow(
            tenant_id=batch.tenant_id,
            observation_id=observation.observation_id,
            batch_id=batch_id,
            observation=data,
        )
        self._session.add(row)
        self._session.flush((row,))
        return observation_from_data(row.observation)

    def observations_for_batch(
        self,
        batch_id: str,
    ) -> tuple[NormalizedObservation, ...]:
        batch = self._batch_row(batch_id)
        rows = self._session.scalars(
            select(NormalizedObservationRow)
            .where(
                NormalizedObservationRow.tenant_id == batch.tenant_id,
                NormalizedObservationRow.batch_id == batch_id,
            )
            .order_by(NormalizedObservationRow.observation_id)
        ).all()
        return tuple(observation_from_data(row.observation) for row in rows)

    def save_frame(self, batch_id: str, frame: AlignedFrame) -> AlignedFrame:
        batch = self._batch_row(batch_id)
        if frame.tenant_id != batch.tenant_id:
            raise ValueError("frame tenant must match capture batch")
        data = frame_to_data(frame)
        existing = self._session.get(
            FusedFrameRow,
            (batch.tenant_id, frame.frame_id),
        )
        if existing is not None:
            if existing.batch_id != batch_id or existing.frame != data:
                raise ConcurrentUpdateError()
            return frame_from_data(existing.frame)
        row = FusedFrameRow(
            tenant_id=batch.tenant_id,
            frame_id=frame.frame_id,
            batch_id=batch_id,
            frame=data,
        )
        self._session.add(row)
        self._session.flush((row,))
        return frame_from_data(row.frame)

    def frame_for_batch(self, batch_id: str) -> AlignedFrame | None:
        batch = self._batch_row(batch_id)
        row = self._session.scalar(
            select(FusedFrameRow).where(
                FusedFrameRow.tenant_id == batch.tenant_id,
                FusedFrameRow.batch_id == batch_id,
            )
        )
        return None if row is None else frame_from_data(row.frame)

    def mark_processed(
        self,
        batch_id: str,
        *,
        state: str,
        processed_at: datetime,
        error: str | None = None,
    ) -> TelemetryBatchRecord:
        if state not in _PROCESSING_STATES - {"pending"}:
            raise ValueError("invalid processing state")
        if error is not None:
            error = error.strip()
            if not error or len(error) > 500:
                raise ValueError("processing error must be 1 to 500 characters")
        row = self._batch_row(batch_id)
        row.processing_state = state
        row.processed_at = utc(processed_at)
        row.processing_error = error
        self._session.flush((row,))
        return self._batch_record(row)

    def _batch_row(self, batch_id: str) -> TelemetryCaptureBatchRow:
        row = self._session.scalar(
            select(TelemetryCaptureBatchRow).where(
                TelemetryCaptureBatchRow.batch_id == batch_id
            )
        )
        if row is None:
            raise NotFoundError()
        return row

    def _batch_record(
        self,
        row: TelemetryCaptureBatchRow,
        *,
        duplicate: bool = False,
    ) -> TelemetryBatchRecord:
        packets = self._session.scalars(
            select(EdgeTelemetryRow)
            .where(
                EdgeTelemetryRow.tenant_id == row.tenant_id,
                EdgeTelemetryRow.batch_id == row.batch_id,
            )
            .order_by(EdgeTelemetryRow.source)
        ).all()
        return TelemetryBatchRecord(
            batch_id=row.batch_id,
            tenant_id=row.tenant_id,
            device_id=row.device_id,
            room_id=row.room_id,
            request_fingerprint=row.request_fingerprint,
            received_at=utc(row.received_at),
            processing_state=row.processing_state,
            processed_at=(None if row.processed_at is None else utc(row.processed_at)),
            processing_error=row.processing_error,
            packets=tuple(
                TelemetryPacketRecord(
                    telemetry_id=packet.telemetry_id,
                    envelope=envelope_from_row(packet),
                    sequence_gap=packet.sequence_gap,
                    received_at=utc(packet.received_at),
                )
                for packet in packets
            ),
            duplicate=duplicate,
        )

    def _packet_for_identity(
        self,
        envelope: EdgeTelemetryEnvelope,
    ) -> EdgeTelemetryRow | None:
        return self._session.scalar(
            select(EdgeTelemetryRow).where(
                EdgeTelemetryRow.tenant_id == envelope.tenant_id,
                EdgeTelemetryRow.device_id == envelope.device_id,
                EdgeTelemetryRow.source == envelope.source,
                EdgeTelemetryRow.stream_id == envelope.stream_id,
                EdgeTelemetryRow.sequence == envelope.sequence,
                EdgeTelemetryRow.schema_version == envelope.schema_version,
            )
        )

    def _latest_sequence(self, envelope: EdgeTelemetryEnvelope) -> int | None:
        return self._session.scalar(
            select(func.max(EdgeTelemetryRow.sequence)).where(
                EdgeTelemetryRow.tenant_id == envelope.tenant_id,
                EdgeTelemetryRow.device_id == envelope.device_id,
                EdgeTelemetryRow.source == envelope.source,
                EdgeTelemetryRow.stream_id == envelope.stream_id,
                EdgeTelemetryRow.schema_version == envelope.schema_version,
            )
        )


class HeartbeatRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        tenant_id: str,
        heartbeat: DeviceHeartbeatRequest,
        *,
        received_at: datetime,
    ) -> HeartbeatRecord:
        data = heartbeat.model_dump(mode="json")
        fingerprint = digest(data)
        existing = self._session.scalar(
            select(DeviceHeartbeatIdentityRow).where(
                DeviceHeartbeatIdentityRow.tenant_id == tenant_id,
                DeviceHeartbeatIdentityRow.device_id == heartbeat.device_id,
                DeviceHeartbeatIdentityRow.stream_id == heartbeat.stream_id,
                DeviceHeartbeatIdentityRow.sequence == heartbeat.sequence,
            )
        )
        if existing is not None:
            if existing.payload_hash != fingerprint:
                raise ConcurrentUpdateError("heartbeat identity has different content")
            return HeartbeatRecord(
                tenant_id=tenant_id,
                heartbeat=DeviceHeartbeatRequest.model_validate(existing.payload),
                received_at=utc(existing.received_at),
                duplicate=True,
            )
        latest = self._session.scalar(
            select(func.max(DeviceHeartbeatIdentityRow.sequence)).where(
                DeviceHeartbeatIdentityRow.tenant_id == tenant_id,
                DeviceHeartbeatIdentityRow.device_id == heartbeat.device_id,
                DeviceHeartbeatIdentityRow.stream_id == heartbeat.stream_id,
            )
        )
        if latest is not None and heartbeat.sequence <= latest:
            raise ConcurrentUpdateError("heartbeat sequence is stale")
        row = DeviceHeartbeatIdentityRow(
            tenant_id=tenant_id,
            device_id=heartbeat.device_id,
            stream_id=heartbeat.stream_id,
            sequence=heartbeat.sequence,
            payload_hash=fingerprint,
            payload=data,
            received_at=utc(received_at),
        )
        self._session.add(row)
        self._session.flush((row,))
        return HeartbeatRecord(
            tenant_id=tenant_id,
            heartbeat=heartbeat,
            received_at=utc(received_at),
        )


__all__ = [
    "HeartbeatRecord",
    "HeartbeatRepository",
    "TelemetryBatchRecord",
    "TelemetryPacketRecord",
    "TelemetryRepository",
]
