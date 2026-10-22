"""Durable capture-to-intelligence processing and replay coordination."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy.orm import Session

from backend.app.db.intelligence_repositories import IntelligenceRepository
from backend.app.db.repositories import FeedbackRepository
from backend.app.db.status_repositories import MonitoringStatusRepository
from backend.app.db.telemetry_repositories import (
    TelemetryBatchRecord,
    TelemetryRepository,
)
from backend.app.domain.monitoring import MonitoringState, PresenceState
from backend.app.ingestion.assignment import (
    AssignmentUnavailableError,
    resolve_monitoring_assignment,
)
from backend.app.ingestion.normalizers import normalize_envelope
from backend.app.intelligence import AlignedFrame, align_observations
from backend.app.intelligence.anomaly import AnomalyState
from backend.app.intelligence.orchestration import (
    IntelligenceResult,
    MonitoringIntelligenceEngine,
)
from backend.app.services.monitoring_processing import PersistentMonitoringService


_EXPECTED_SOURCES = ("radar", "thermal", "wifi_csi")
_TERMINAL_STATES = frozenset({"processed", "calibrating", "blocked"})


@dataclass(frozen=True)
class TelemetryProcessingOutcome:
    batch: TelemetryBatchRecord
    frame: AlignedFrame | None
    intelligence: IntelligenceResult | None

    @property
    def processing_state(self) -> str:
        return self.batch.processing_state


class TelemetryProcessingCoordinator:
    def __init__(
        self,
        session: Session,
        engine: MonitoringIntelligenceEngine,
    ) -> None:
        self._session = session
        self._engine = engine
        self._telemetry = TelemetryRepository(session)
        self._intelligence = IntelligenceRepository(session)
        self._status = MonitoringStatusRepository(session)
        self._feedback = FeedbackRepository(session)

    def process_batch(self, batch_id: str) -> TelemetryProcessingOutcome:
        batch = self._telemetry.get_batch(batch_id)
        existing_frame = self._telemetry.frame_for_batch(batch_id)
        if batch.processing_state in _TERMINAL_STATES:
            return TelemetryProcessingOutcome(batch, existing_frame, None)

        try:
            assignment = resolve_monitoring_assignment(
                self._session,
                batch.tenant_id,
                batch.device_id,
                batch.room_id,
            )
        except AssignmentUnavailableError as exc:
            return self._finish_without_intelligence(
                batch_id,
                state="blocked",
                error=exc.reason,
            )

        try:
            observations = tuple(
                normalize_envelope(
                    packet.envelope,
                    assignment,
                    packet.received_at,
                )
                for packet in batch.packets
            )
            for observation in observations:
                self._telemetry.save_observation(batch_id, observation)
            frame = align_observations(
                observations,
                frame_id=_frame_id(batch_id),
                window_start=min(item.window_start for item in observations),
                window_end=max(item.window_end for item in observations),
                expected_sources=_EXPECTED_SOURCES,
            )
            self._telemetry.save_frame(batch_id, frame)

            baseline = self._intelligence.latest_baseline(
                batch.tenant_id,
                assignment.resident_id,
            )
            if baseline is None:
                stored = self._telemetry.mark_processed(
                    batch_id,
                    state="calibrating",
                    processed_at=_now(),
                    error="numerical_baseline_unavailable",
                )
                self._session.commit()
                return TelemetryProcessingOutcome(stored, frame, None)

            status = self._status.find_latest(
                batch.tenant_id,
                assignment.resident_id,
            )
            if (
                status is None
                or status.room_id != assignment.room_id
                or status.snapshot.state is MonitoringState.UNAVAILABLE
                or status.snapshot.presence is PresenceState.UNKNOWN
            ):
                self._session.rollback()
                return self._finish_without_intelligence(
                    batch_id,
                    state="blocked",
                    error="monitoring_status_unavailable",
                )

            memory = self._feedback.current_memory(
                batch.tenant_id,
                assignment.resident_id,
            )
            relevant_context_ids = tuple(
                entry.entry_id
                for entry in memory.relevant_entries(frame.window_end)
            )
            anomaly_id = self._anomaly_id(batch, assignment.resident_id, frame)
            unknowns = tuple(
                dict.fromkeys(
                    (
                        "real-world cause is not directly observed",
                        *(f"missing source: {source}" for source in frame.sources_missing),
                    )
                )
            )
            result = PersistentMonitoringService(
                self._session,
                self._engine,
            ).process_frame(
                frame,
                baseline=baseline,
                context_key="resident_global",
                anomaly_id=anomaly_id,
                tenant_id=batch.tenant_id,
                resident_id=assignment.resident_id,
                room_id=assignment.room_id,
                config_version="telemetry_pipeline_v1",
                unknowns=unknowns,
                resident_memory=memory,
                resident_away=(
                    status.snapshot.presence is PresenceState.RESIDENT_AWAY
                ),
                possible_multiple_people=(
                    status.snapshot.presence
                    is PresenceState.POSSIBLE_MULTI_PERSON
                ),
                relevant_context_entry_ids=relevant_context_ids,
            )
            stored = self._telemetry.mark_processed(
                batch_id,
                state="processed",
                processed_at=_now(),
            )
            self._session.commit()
            return TelemetryProcessingOutcome(stored, frame, result)
        except Exception:
            self._session.rollback()
            return self._finish_without_intelligence(
                batch_id,
                state="failed",
                error="telemetry_processing_failed",
            )

    def drain_pending(self, *, limit: int) -> tuple[TelemetryProcessingOutcome, ...]:
        pending = self._telemetry.pending_batches(limit=limit)
        return tuple(self.process_batch(batch.batch_id) for batch in pending)

    def _anomaly_id(
        self,
        batch: TelemetryBatchRecord,
        resident_id: str,
        frame: AlignedFrame,
    ) -> str:
        latest = self._intelligence.latest_anomaly_for_lane(
            batch.tenant_id,
            resident_id,
            batch.room_id,
        )
        if latest is None or latest.update.episode is None:
            generation = "initial"
        elif latest.update.episode.state is not AnomalyState.CLOSED:
            return latest.update.episode.anomaly_id
        else:
            generation = latest.update.episode.anomaly_id + ":next"
        identity = ":".join(
            (
                batch.tenant_id,
                batch.room_id,
                resident_id,
                generation,
            )
        )
        return "anomaly_" + sha256(identity.encode()).hexdigest()[:24]

    def _finish_without_intelligence(
        self,
        batch_id: str,
        *,
        state: str,
        error: str,
    ) -> TelemetryProcessingOutcome:
        stored = self._telemetry.mark_processed(
            batch_id,
            state=state,
            processed_at=_now(),
            error=error,
        )
        self._session.commit()
        return TelemetryProcessingOutcome(
            stored,
            self._telemetry.frame_for_batch(batch_id),
            None,
        )


def _frame_id(batch_id: str) -> str:
    return "frame_" + sha256(f"{batch_id}:fusion_v1".encode()).hexdigest()[:24]


def _now() -> datetime:
    return datetime.now(timezone.utc)


__all__ = ["TelemetryProcessingCoordinator", "TelemetryProcessingOutcome"]
