"""Transactional persistence boundary for one monitoring-engine result."""

from hashlib import sha256

from sqlalchemy.orm import Session

from backend.app.db.intelligence_mappers import DispositionRecord
from backend.app.db.intelligence_repositories import IntelligenceRepository
from backend.app.db.repositories import EventRepository
from backend.app.domain.events import BridgeEvidenceKind
from backend.app.intelligence.orchestration import (
    IntelligenceResult,
    MonitoringIntelligenceEngine,
)
from backend.app.intelligence.evidence import build_evidence_packet
from backend.app.services.errors import ConcurrentUpdateError


class PersistentMonitoringService:
    """Run the intelligence lane and append its exact evidence-bound outputs."""

    def __init__(self, session: Session, engine: MonitoringIntelligenceEngine) -> None:
        self._session = session
        self._engine = engine
        self._intelligence = IntelligenceRepository(session)
        self._events = EventRepository(session)

    def process_frame(self, *args, **kwargs) -> IntelligenceResult:
        if (
            self._engine.analysis_orchestrator is not None
            and kwargs.get("resident_memory") is None
        ):
            raise ValueError(
                "resident_memory is required for persistent multi-agent analysis"
            )
        tenant_hint = kwargs.get("tenant_id")
        resident_hint = kwargs.get("resident_id")
        baseline_hint = kwargs.get("baseline")
        anomaly_hint = kwargs.get("anomaly_id")
        current_baseline = None
        if (
            isinstance(tenant_hint, str)
            and isinstance(resident_hint, str)
            and baseline_hint is not None
        ):
            current_baseline = self._intelligence.latest_baseline(
                tenant_hint,
                resident_hint,
            )
            if (
                current_baseline is not None
                and current_baseline.baseline_id == baseline_hint.baseline_id
                and current_baseline != baseline_hint
            ):
                # A baseline ID is immutable lineage. Reject a collision before
                # the stateful engine consumes the new frame.
                raise ConcurrentUpdateError(
                    "baseline identity has different contents"
                )
        if (
            isinstance(tenant_hint, str)
            and isinstance(anomaly_hint, str)
            and self._engine.analysis_orchestrator is not None
        ):
            checkpoints = self._intelligence.analysis_checkpoints_for_anomaly(
                tenant_hint, anomaly_hint
            )
            for checkpoint in checkpoints:
                self._engine.analysis_orchestrator.restore_checkpoint(checkpoint)
        result = self._engine.process_frame(*args, **kwargs)
        tenant_id = result.observation.tenant_id
        if current_baseline is None or current_baseline.baseline_id != result.baseline.baseline_id:
            self._intelligence.save_baseline(
                tenant_id,
                result.baseline,
                result.observation.window_end,
            )
        if (
            result.anomaly is not None
            and result.evidence is not None
            and result.evidence.strength_scale != "fall_like_state_machine"
        ):
            self._intelligence.save_anomaly_revision(
                tenant_id,
                result.anomaly,
                build_evidence_packet(result.anomaly),
            )
        if result.analysis is not None and result.evidence is not None:
            self._intelligence.save_analysis_run(
                tenant_id,
                result.analysis,
                result.evidence.current_time,
                packet=result.evidence,
            )
        if result.event is not None:
            stored = self._events.find(tenant_id, result.event.event_id)
            if stored is None:
                self._events.save(tenant_id, result.event, expected_version=0)
            elif stored.event != result.event:
                self._events.save(
                    tenant_id,
                    result.event,
                    expected_version=stored.version,
                )
        if result.evidence is not None and result.analysis is not None:
            identity = ":".join(
                (
                    tenant_id,
                    result.evidence.anomaly_id,
                    str(result.evidence.packet_revision),
                    result.decision.policy_version,
                    result.analysis.analysis_id,
                )
            )
            disposition_id = "disposition_" + sha256(
                identity.encode("utf-8")
            ).hexdigest()[:20]
            self._intelligence.save_disposition(
                tenant_id,
                DispositionRecord(
                    disposition_id=disposition_id,
                    resident_id=result.evidence.resident_id,
                    room_id=result.evidence.room_id,
                    anomaly_id=result.evidence.anomaly_id,
                    evidence_kind=BridgeEvidenceKind.PACKET,
                    evidence_revision=result.evidence.packet_revision,
                    packet_revision=result.evidence.packet_revision,
                    decided_at=result.evidence.current_time,
                    decision=result.decision,
                    interpretation_id=None,
                    analysis_id=result.decision.analysis_id,
                    event_id=None if result.event is None else result.event.event_id,
                ),
            )
        return result


__all__ = ["PersistentMonitoringService"]
