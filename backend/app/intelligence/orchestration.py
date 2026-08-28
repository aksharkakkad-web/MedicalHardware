"""One-frame orchestration across monitoring intelligence and caregiver events."""

from dataclasses import dataclass, replace
from datetime import datetime

from backend.app.ai.client import (
    InterpretationResult,
    InterpretationStatus,
    LLMClient,
)
from backend.app.ai.context import build_interpretation_request
from backend.app.ai.validation import (
    InterpretationValidationError,
    validate_interpretation,
)
from backend.app.domain.events import EventStatus, EventStore, MonitoringEvent
from backend.app.domain.feedback import ResidentMemory
from backend.app.intelligence.anomaly import (
    AnomalyEpisode,
    AnomalyState,
    AnomalyUpdate,
    SyntheticAnomalyPolicy,
    advance_episode,
)
from backend.app.intelligence.baseline import BaselineSnapshot
from backend.app.intelligence.degradation import (
    DegradationAssessment,
    assess_monitoring_degradation,
)
from backend.app.intelligence.evidence import EvidencePacket, build_evidence_packet
from backend.app.intelligence.fall_detection import (
    FallLikeAssessment,
    SyntheticFallPolicy,
    advance_fall_like,
)
from backend.app.intelligence.fusion import AlignedFrame
from backend.app.intelligence.policy import (
    DispositionDecision,
    EventAttentionPolicy,
    PolicyDisposition,
    SyntheticDispositionPolicy,
)


@dataclass(frozen=True)
class IntelligenceResult:
    observation: AlignedFrame
    baseline: BaselineSnapshot
    anomaly: AnomalyUpdate | None
    evidence: EvidencePacket | None
    interpretation: InterpretationResult | None
    interpretation_error: tuple[str, ...]
    decision: DispositionDecision
    event: MonitoringEvent | None
    event_bridge_idempotency_key: str | None
    fall_assessment: FallLikeAssessment
    degradation: DegradationAssessment
    schema_version: str = "1.0"


class MonitoringIntelligenceEngine:
    """Stateful V1 lane over injected normalized frames; persistence is Task 8."""

    def __init__(
        self,
        *,
        event_store: EventStore | None = None,
        llm_client: LLMClient | None = None,
        disposition_policy: SyntheticDispositionPolicy | None = None,
        attention_policy: EventAttentionPolicy | None = None,
        anomaly_policy: SyntheticAnomalyPolicy | None = None,
        fall_policy: SyntheticFallPolicy | None = None,
        model_id: str = "deterministic-fake-monitoring",
        model_version: str = "fake-v1",
    ) -> None:
        self.event_store = event_store or EventStore()
        self.llm_client = llm_client
        self.disposition_policy = disposition_policy or SyntheticDispositionPolicy()
        self.attention_policy = attention_policy or EventAttentionPolicy()
        self.anomaly_policy = anomaly_policy or SyntheticAnomalyPolicy()
        self.fall_policy = fall_policy or SyntheticFallPolicy()
        self.model_id = model_id
        self.model_version = model_version
        self._episode: AnomalyEpisode | None = None
        self._fall_assessment: FallLikeAssessment | None = None
        self._results: dict[tuple[object, ...], IntelligenceResult] = {}
        self._event_ids_by_anomaly: dict[str, str] = {}

    def process_frame(
        self,
        frame: AlignedFrame,
        *,
        baseline: BaselineSnapshot,
        context_key: str,
        anomaly_id: str,
        resident_id: str,
        room_id: str,
        config_version: str,
        unknowns: tuple[str, ...],
        resident_memory: ResidentMemory | None = None,
        resident_away: bool = False,
        possible_multiple_people: bool = False,
        relevant_context_entry_ids: tuple[str, ...] = (),
    ) -> IntelligenceResult:
        cache_key = (
            frame.frame_id,
            baseline.baseline_id,
            anomaly_id,
            resident_id,
            room_id,
            resident_away,
            possible_multiple_people,
            self.disposition_policy.policy_version,
        )
        cached = self._results.get(cache_key)
        if cached is not None:
            return cached

        degradation = assess_monitoring_degradation(frame)
        fall_assessment = advance_fall_like(
            self._fall_assessment,
            frame,
            policy=self.fall_policy,
            possible_multiple_people=possible_multiple_people,
        )
        self._fall_assessment = fall_assessment

        anomaly: AnomalyUpdate | None = None
        if fall_assessment.urgent_triggered or (
            not degradation.degraded
            and not resident_away
            and not possible_multiple_people
        ):
            anomaly = advance_episode(
                self._episode,
                frame=frame,
                baseline=baseline,
                context_key=context_key,
                anomaly_id=anomaly_id,
                resident_id=resident_id,
                room_id=room_id,
                config_version=config_version,
                unknowns=unknowns,
                policy=self.anomaly_policy,
            )
            self._episode = anomaly.episode

        evidence = self._packet(anomaly)
        interpretation = None
        interpretation_error: tuple[str, ...] = ()
        if (
            evidence is not None
            and evidence.lifecycle_state != AnomalyState.CLOSED
            and not fall_assessment.urgent_triggered
        ):
            interpretation, interpretation_error = self._interpret(
                evidence,
                resident_memory,
                relevant_context_entry_ids,
            )

        decision = self.disposition_policy.decide(
            packet=evidence,
            interpretation=interpretation,
            interpretation_failed=bool(interpretation_error),
            fall_assessment=fall_assessment,
            degradation=degradation,
            resident_away=resident_away,
            possible_multiple_people=possible_multiple_people,
        )

        event = self._existing_event(anomaly_id)
        bridge_key = None
        if decision.disposition == PolicyDisposition.CAREGIVER_EVENT:
            revision = evidence.packet_revision if evidence is not None else 0
            bridge_key = ":".join(
                (
                    anomaly_id,
                    str(revision),
                    self.disposition_policy.policy_version,
                )
            )
            if decision.priority is None:
                raise RuntimeError("caregiver-event decisions require priority")
            event = self.event_store.record_signal(
                resident_id=resident_id,
                room_id=room_id,
                objective_family=decision.objective_family,
                headline=decision.headline,
                priority=decision.priority,
                observed_at=frame.window_end,
                resident_memory=resident_memory,
                source_anomaly_id=anomaly_id,
                evidence_revision=revision,
                bridge_idempotency_key=bridge_key,
                provisional_urgent=decision.provisional_urgent,
            )
            self._event_ids_by_anomaly[anomaly_id] = event.event_id

        attention_suppressed = bool(
            event is not None
            and event.status in (EventStatus.ACKNOWLEDGED, EventStatus.CHECKED)
            and event.attention_suppressed_until is not None
            and frame.window_end < event.attention_suppressed_until
        )
        decision = replace(
            decision,
            attention_suppressed=attention_suppressed,
        )
        result = IntelligenceResult(
            observation=frame,
            baseline=baseline,
            anomaly=anomaly,
            evidence=evidence,
            interpretation=interpretation,
            interpretation_error=interpretation_error,
            decision=decision,
            event=event,
            event_bridge_idempotency_key=bridge_key,
            fall_assessment=fall_assessment,
            degradation=degradation,
        )
        self._results[cache_key] = result
        return result

    def acknowledge_event(
        self,
        event_id: str,
        *,
        actor_id: str,
        at: datetime,
    ) -> MonitoringEvent:
        event = self.event_store.get(event_id)
        suppressed_until = self.attention_policy.suppression_until(
            event.priority,
            at,
        )
        return self.event_store.acknowledge(
            event_id,
            actor_id=actor_id,
            at=at,
            attention_suppressed_until=suppressed_until,
        )

    def _interpret(
        self,
        packet: EvidencePacket,
        resident_memory: ResidentMemory | None,
        relevant_context_entry_ids: tuple[str, ...],
    ) -> tuple[InterpretationResult | None, tuple[str, ...]]:
        if self.llm_client is None:
            return None, ("llm_unavailable",)
        if resident_memory is None:
            return None, ("resident_memory_unavailable",)
        try:
            request = build_interpretation_request(
                packet,
                resident_memory,
                model_id=self.model_id,
                model_version=self.model_version,
                relevant_context_entry_ids=relevant_context_entry_ids,
            )
            result = self.llm_client.interpret(request)
            validated = validate_interpretation(request, result)
            if validated.status != InterpretationStatus.COMPLETE:
                return None, (f"interpretation_status:{validated.status}",)
            return validated, ()
        except InterpretationValidationError as exc:
            return None, exc.reasons
        except Exception as exc:
            return None, (f"interpretation_unavailable:{type(exc).__name__}",)

    @staticmethod
    def _packet(anomaly: AnomalyUpdate | None) -> EvidencePacket | None:
        if anomaly is None or anomaly.episode is None:
            return None
        if anomaly.episode.state == AnomalyState.CANDIDATE:
            return None
        return build_evidence_packet(anomaly)

    def _existing_event(self, anomaly_id: str) -> MonitoringEvent | None:
        event_id = self._event_ids_by_anomaly.get(anomaly_id)
        return self.event_store.get(event_id) if event_id is not None else None


__all__ = ["IntelligenceResult", "MonitoringIntelligenceEngine"]
