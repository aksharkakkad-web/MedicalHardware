"""Transactional device-ingestion application service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.contracts.ingestion import (
    DeviceHeartbeatRequest,
    EdgeTelemetryEnvelope,
    HeartbeatIngestResponse,
    TelemetryCaptureRequest,
    TelemetryIngestItemResponse,
    TelemetryIngestResponse,
)
from backend.app.db.device_repositories import (
    DeviceHealthRepository,
    DeviceRepository,
)
from backend.app.db.models import RoomRow
from backend.app.db.telemetry_repositories import (
    HeartbeatRepository,
    TelemetryRepository,
)
from backend.app.domain.device_health import (
    DeviceHealthObservation,
    DeviceHealthState,
    DeviceSourceHealth,
    DeviceSourceHealthState,
)
from backend.app.ingestion.assignment import (
    AssignmentUnavailableError,
    resolve_monitoring_assignment,
)
from backend.app.services.errors import InvalidInputError, NotFoundError


PostCommitProcessor = Callable[[str], None]
Clock = Callable[[], datetime]
_EXPECTED_SOURCES = ("radar", "thermal", "wifi_csi")


class TelemetryIngestionService:
    def __init__(
        self,
        session: Session,
        *,
        post_commit_processor: PostCommitProcessor | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._session = session
        self._telemetry = TelemetryRepository(session)
        self._heartbeats = HeartbeatRepository(session)
        self._devices = DeviceRepository(session)
        self._health = DeviceHealthRepository(session)
        self._post_commit_processor = post_commit_processor
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def ingest_capture(
        self,
        tenant_id: str,
        capture: TelemetryCaptureRequest,
    ) -> TelemetryIngestResponse:
        if any(item.tenant_id != tenant_id for item in capture.root):
            raise InvalidInputError(
                "Telemetry tenant does not match the authenticated tenant",
                field="tenant_id",
            )
        first = capture.root[0]
        if self._devices.find(tenant_id, first.device_id) is None:
            raise NotFoundError()
        room = self._session.get(RoomRow, first.room_id)
        if room is None or room.tenant_id != tenant_id:
            raise NotFoundError()
        now = self._clock()
        try:
            batch = self._telemetry.save_capture(capture, received_at=now)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        if not batch.duplicate and self._post_commit_processor is not None:
            try:
                self._post_commit_processor(batch.batch_id)
            except Exception:
                self._session.rollback()
                self._telemetry.mark_processed(
                    batch.batch_id,
                    state="failed",
                    processed_at=self._clock(),
                    error="post_commit_processing_failed",
                )
                self._session.commit()

        status = "duplicate" if batch.duplicate else "accepted"
        item_count = len(batch.packets)
        return TelemetryIngestResponse(
            batch_id=batch.batch_id,
            accepted=0 if batch.duplicate else item_count,
            duplicate_count=item_count if batch.duplicate else 0,
            rejected=0,
            duplicate=batch.duplicate,
            processing_state=batch.processing_state,
            results=tuple(
                TelemetryIngestItemResponse(
                    source=packet.envelope.source,
                    sequence=packet.envelope.sequence,
                    status=status,
                )
                for packet in batch.packets
            ),
        )

    def ingest_heartbeat(
        self,
        tenant_id: str,
        heartbeat: DeviceHeartbeatRequest,
    ) -> HeartbeatIngestResponse:
        device = self._devices.find(tenant_id, heartbeat.device_id)
        if device is None:
            raise NotFoundError()
        now = self._clock()
        try:
            stored = self._heartbeats.record(
                tenant_id,
                heartbeat,
                received_at=now,
            )
            state = self._heartbeat_state(tenant_id, heartbeat)
            if not stored.duplicate:
                seen = set(heartbeat.sources_seen)
                sources = tuple(
                    DeviceSourceHealth(
                        source=source,
                        state=(
                            DeviceSourceHealthState.ONLINE
                            if source in seen
                            else DeviceSourceHealthState.UNAVAILABLE
                        ),
                        limitations=(
                            () if source in seen else ("not_seen_in_heartbeat",)
                        ),
                    )
                    for source in _EXPECTED_SOURCES
                )
                limitations = tuple(
                    reason
                    for reason, applies in (
                        ("buffered_packets", heartbeat.buffered_packets > 0),
                        (
                            "transport_not_ok",
                            heartbeat.transport_status.casefold()
                            not in {"ok", "online", "connected"},
                        ),
                        (
                            "assignment_unavailable",
                            state is DeviceHealthState.ASSIGNMENT_UNAVAILABLE,
                        ),
                        (
                            "expected_source_missing",
                            not set(_EXPECTED_SOURCES) <= seen,
                        ),
                    )
                    if applies
                )
                self._health.record(
                    tenant_id,
                    DeviceHealthObservation(
                        device_id=heartbeat.device_id,
                        state=state,
                        observed_at=now,
                        last_seen_at=now,
                        sources=sources,
                        limitations=limitations,
                    ),
                )
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

        return HeartbeatIngestResponse(
            device_id=heartbeat.device_id,
            sequence=heartbeat.sequence,
            duplicate=stored.duplicate,
            health_state=state.value,
        )

    def _heartbeat_state(
        self,
        tenant_id: str,
        heartbeat: DeviceHeartbeatRequest,
    ) -> DeviceHealthState:
        device_assignments = self._devices.active_room_assignments(
            tenant_id,
            heartbeat.device_id,
        )
        if len(device_assignments) != 1:
            return DeviceHealthState.ASSIGNMENT_UNAVAILABLE
        try:
            resolve_monitoring_assignment(
                self._session,
                tenant_id,
                heartbeat.device_id,
                device_assignments[0].room_id,
            )
        except AssignmentUnavailableError:
            return DeviceHealthState.ASSIGNMENT_UNAVAILABLE
        if heartbeat.buffered_packets > 0:
            return DeviceHealthState.BUFFERING
        transport = heartbeat.transport_status.casefold()
        if transport in {"retry", "retrying", "backoff"}:
            return DeviceHealthState.RETRYING
        if transport not in {"ok", "online", "connected"}:
            return DeviceHealthState.DEGRADED
        if not set(_EXPECTED_SOURCES) <= set(heartbeat.sources_seen):
            return DeviceHealthState.DEGRADED
        return DeviceHealthState.ONLINE


__all__ = ["TelemetryIngestionService"]
