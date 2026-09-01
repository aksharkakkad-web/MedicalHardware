"""One-frame orchestration across monitoring intelligence and caregiver events."""

from dataclasses import dataclass, replace
from datetime import datetime

from backend.app.ai.analysis_contracts import AnalysisRun, AnalysisState
from backend.app.ai.analysis_orchestration import MultiAgentAnalysisOrchestrator
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
from backend.app.domain.events import (
    BridgeEvidenceKind,
    EventStatus,
    EventStore,
    MonitoringEvent,
)
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
from backend.app.intelligence.evidence import (
    EvidencePacket,
    build_evidence_packet,
    build_fall_evidence_packet,
)
from backend.app.intelligence.fall_detection import (
    FallLikeAssessment,
    SyntheticFallPolicy,
    advance_fall_like,
)
from backend.app.intelligence.fusion import AlignedFrame
from backend.app.intelligence.policy import (
    DispositionDecision,
    EventAttentionPolicy,
    MultiAgentDispositionPolicy,
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
    analysis: AnalysisRun | None
    analysis_error: tuple[str, ...]
    decision: DispositionDecision
    event: MonitoringEvent | None
    event_bridge_idempotency_key: str | None
    fall_assessment: FallLikeAssessment
    degradation: DegradationAssessment
    schema_version: str = "1.0"


LaneKey = tuple[str, str, str]


@dataclass(frozen=True)
class _ProcessBinding:
    frame: AlignedFrame
    baseline: BaselineSnapshot
    context_key: str
    anomaly_id: str
    tenant_id: str
    resident_id: str
    room_id: str
    config_version: str
    unknowns: tuple[str, ...]
    resident_memory: ResidentMemory | None
    resident_away: bool
    possible_multiple_people: bool
    relevant_context_entry_ids: tuple[str, ...]
    disposition_policy: SyntheticDispositionPolicy
    analysis_policy: MultiAgentDispositionPolicy
    attention_policy: EventAttentionPolicy
    anomaly_policy: SyntheticAnomalyPolicy
    fall_policy: SyntheticFallPolicy
    event_policy_version: str
    model_id: str
    model_version: str
    llm_boundary: str
    analysis_boundary: str


@dataclass(frozen=True)
class _ProcessedFrame:
    binding: _ProcessBinding
    result: IntelligenceResult
    lane: LaneKey
    anomaly_id: str


class MonitoringIntelligenceEngine:
    """Stateful V1 lane over injected normalized frames; persistence is Task 8."""

    def __init__(
        self,
        *,
        event_store: EventStore | None = None,
        llm_client: LLMClient | None = None,
        analysis_orchestrator: MultiAgentAnalysisOrchestrator | None = None,
        disposition_policy: SyntheticDispositionPolicy | None = None,
        analysis_policy: MultiAgentDispositionPolicy | None = None,
        attention_policy: EventAttentionPolicy | None = None,
        anomaly_policy: SyntheticAnomalyPolicy | None = None,
        fall_policy: SyntheticFallPolicy | None = None,
        model_id: str = "deterministic-fake-monitoring",
        model_version: str = "fake-v1",
    ) -> None:
        self.event_store = event_store or EventStore()
        self._event_stores: dict[str, EventStore] = {}
        self.llm_client = llm_client
        self.analysis_orchestrator = analysis_orchestrator
        self.disposition_policy = disposition_policy or SyntheticDispositionPolicy()
        self.analysis_policy = analysis_policy or MultiAgentDispositionPolicy()
        self.attention_policy = attention_policy or EventAttentionPolicy()
        self.anomaly_policy = anomaly_policy or SyntheticAnomalyPolicy()
        self.fall_policy = fall_policy or SyntheticFallPolicy()
        self.model_id = model_id
        self.model_version = model_version
        self._episodes: dict[LaneKey, AnomalyEpisode] = {}
        self._fall_assessments: dict[LaneKey, FallLikeAssessment] = {}
        self._processed_frames: dict[
            tuple[LaneKey, str],
            _ProcessedFrame,
        ] = {}
        self._urgent_revisions: dict[tuple[LaneKey, str], int] = {}
        self._fall_packet_revisions: dict[tuple[LaneKey, str], int] = {}
        self._event_ids_by_anomaly: dict[tuple[LaneKey, str], str] = {}

    def process_frame(
        self,
        frame: AlignedFrame,
        *,
        baseline: BaselineSnapshot,
        context_key: str,
        anomaly_id: str,
        tenant_id: str,
        resident_id: str,
        room_id: str,
        config_version: str,
        unknowns: tuple[str, ...],
        resident_memory: ResidentMemory | None = None,
        resident_away: bool = False,
        possible_multiple_people: bool = False,
        relevant_context_entry_ids: tuple[str, ...] = (),
    ) -> IntelligenceResult:
        identity = (tenant_id, room_id, resident_id)
        if identity != (frame.tenant_id, frame.room_id, frame.resident_id):
            raise ValueError(
                "frame assignment identity must match passed tenant_id, room_id, "
                "and resident_id"
            )
        lane = identity
        event_store = self._event_store_for(tenant_id)
        binding = _ProcessBinding(
            frame=frame,
            baseline=baseline,
            context_key=context_key,
            anomaly_id=anomaly_id,
            tenant_id=tenant_id,
            resident_id=resident_id,
            room_id=room_id,
            config_version=config_version,
            unknowns=unknowns,
            resident_memory=resident_memory,
            resident_away=resident_away,
            possible_multiple_people=possible_multiple_people,
            relevant_context_entry_ids=relevant_context_entry_ids,
            disposition_policy=self.disposition_policy,
            analysis_policy=self.analysis_policy,
            attention_policy=self.attention_policy,
            anomaly_policy=self.anomaly_policy,
            fall_policy=self.fall_policy,
            event_policy_version=event_store.policy.policy_version,
            model_id=self.model_id,
            model_version=self.model_version,
            llm_boundary=(
                "unavailable"
                if self.llm_client is None
                else (
                    f"{type(self.llm_client).__module__}."
                    f"{type(self.llm_client).__qualname__}"
                )
            ),
            analysis_boundary=(
                "unavailable"
                if self.analysis_orchestrator is None
                else (
                    f"{type(self.analysis_orchestrator).__module__}."
                    f"{type(self.analysis_orchestrator).__qualname__}"
                )
            ),
        )
        cache_key = (lane, frame.frame_id)
        cached = self._processed_frames.get(cache_key)
        if cached is not None:
            if cached.binding != binding:
                raise ValueError(
                    "processed frame identity conflict: lane/frame reused with "
                    "different inputs or versions"
                )
            return self._replay(cached)

        degradation = assess_monitoring_degradation(frame)
        confounded = degradation.degraded or resident_away
        if confounded:
            fall_assessment = advance_fall_like(
                None,
                frame,
                policy=self.fall_policy,
                possible_multiple_people=possible_multiple_people,
            )
            self._fall_assessments.pop(lane, None)
        else:
            fall_assessment = advance_fall_like(
                self._fall_assessments.get(lane),
                frame,
                policy=self.fall_policy,
                possible_multiple_people=possible_multiple_people,
            )
            self._fall_assessments[lane] = fall_assessment

        anomaly: AnomalyUpdate | None = None
        if (
            not degradation.degraded
            and not resident_away
            and (
                not possible_multiple_people
                or self.analysis_orchestrator is not None
            )
        ):
            anomaly = advance_episode(
                self._episodes.get(lane),
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
            if anomaly.episode is not None:
                self._episodes[lane] = anomaly.episode

        evidence = self._packet(anomaly)
        if evidence is not None and possible_multiple_people:
            evidence = replace(
                evidence,
                evidence_limited=True,
                limitations=tuple(
                    dict.fromkeys(
                        (*evidence.limitations, "resident_attribution_ambiguous")
                    )
                ),
                unknowns=tuple(
                    dict.fromkeys(
                        (*evidence.unknowns, "which person produced the measured change")
                    )
                ),
            )
        if (
            evidence is None
            and fall_assessment.urgent_triggered
            and self.analysis_orchestrator is not None
        ):
            fall_key = (lane, anomaly_id)
            fall_revision = self._fall_packet_revisions.get(fall_key, 0) + 1
            evidence = build_fall_evidence_packet(
                fall_assessment,
                frame=frame,
                baseline=baseline,
                anomaly_id=anomaly_id,
                packet_revision=fall_revision,
                config_version=config_version,
                unknowns=unknowns,
            )
            self._fall_packet_revisions[fall_key] = fall_revision
        interpretation = None
        interpretation_error: tuple[str, ...] = ()
        analysis = None
        analysis_error: tuple[str, ...] = ()
        if (
            evidence is not None
            and evidence.lifecycle_state != AnomalyState.CLOSED
        ):
            if self.analysis_orchestrator is not None:
                if resident_memory is None:
                    analysis_error = ("resident_memory_unavailable",)
                else:
                    try:
                        analysis = self.analysis_orchestrator.analyze(
                            evidence,
                            resident_memory,
                            relevant_context_entry_ids,
                            tenant_id=tenant_id,
                        )
                    except Exception as exc:
                        analysis_error = (
                            f"analysis_unavailable:{type(exc).__name__}",
                        )
            elif not fall_assessment.urgent_triggered:
                interpretation, interpretation_error = self._interpret(
                    evidence,
                    resident_memory,
                    relevant_context_entry_ids,
                )

        if self.analysis_orchestrator is not None and (
            degradation.degraded
            or resident_away
        ):
            decision = self.disposition_policy.decide(
                packet=None,
                interpretation=None,
                interpretation_failed=False,
                fall_assessment=fall_assessment,
                degradation=degradation,
                resident_away=resident_away,
                possible_multiple_people=possible_multiple_people,
            )
        elif self.analysis_orchestrator is not None:
            decision = self.analysis_policy.decide(
                packet=evidence,
                analysis_run=analysis,
            )
            if analysis_error and decision.confidence == "analysis_pending":
                decision = replace(
                    decision,
                    reasons=tuple(
                        dict.fromkeys((*decision.reasons, *analysis_error))
                    ),
                )
            if fall_assessment.urgent_triggered and (
                analysis is None or analysis.state is not AnalysisState.ANALYZED
            ):
                # An unavailable model may delay interpretation, but it must
                # not erase an already-confirmed deterministic urgent signal.
                urgent_fallback = self.disposition_policy.decide(
                    packet=evidence,
                    interpretation=None,
                    interpretation_failed=True,
                    fall_assessment=fall_assessment,
                    degradation=degradation,
                    resident_away=resident_away,
                    possible_multiple_people=possible_multiple_people,
                )
                decision = replace(
                    urgent_fallback,
                    analysis_id=None if analysis is None else analysis.analysis_id,
                    reasons=tuple(
                        dict.fromkeys(
                            (
                                *urgent_fallback.reasons,
                                "analysis_pending_did_not_suppress_urgent_signal",
                                *analysis_error,
                            )
                        )
                    ),
                    fallback_used=True,
                )
        else:
            decision = self.disposition_policy.decide(
                packet=evidence,
                interpretation=interpretation,
                interpretation_failed=bool(interpretation_error),
                fall_assessment=fall_assessment,
                degradation=degradation,
                resident_away=resident_away,
                possible_multiple_people=possible_multiple_people,
            )

        event = self._existing_event(lane, anomaly_id)
        bridge_key = None
        if decision.disposition == PolicyDisposition.CAREGIVER_EVENT:
            if evidence is not None:
                revision = evidence.packet_revision
                evidence_kind = BridgeEvidenceKind.PACKET
                revision_component = str(revision)
            else:
                urgent_key = (lane, anomaly_id)
                revision = self._urgent_revisions.get(urgent_key, 0) + 1
                evidence_kind = BridgeEvidenceKind.PROVISIONAL
                revision_component = f"provisional-{revision}"
            bridge_key = ":".join(
                (
                    anomaly_id,
                    revision_component,
                    decision.policy_version,
                )
            )
            if decision.priority is None:
                raise RuntimeError("caregiver-event decisions require priority")
            related_event_ids = self._recurrence_event_ids(lane, anomaly)
            event = event_store.record_signal(
                resident_id=resident_id,
                room_id=room_id,
                objective_family=decision.objective_family,
                headline=decision.headline,
                priority=decision.priority,
                observed_at=frame.window_end,
                resident_memory=(
                    None if decision.room_level_only else resident_memory
                ),
                source_anomaly_id=anomaly_id,
                evidence_revision=revision,
                bridge_idempotency_key=bridge_key,
                provisional_urgent=decision.provisional_urgent,
                evidence_kind=evidence_kind,
                room_level_only=decision.room_level_only,
                related_event_ids=related_event_ids,
            )
            if evidence_kind == BridgeEvidenceKind.PROVISIONAL:
                self._urgent_revisions[(lane, anomaly_id)] = revision
            self._event_ids_by_anomaly[(lane, anomaly_id)] = event.event_id

        decision = self._with_attention(decision, event, frame.window_end)
        result = IntelligenceResult(
            observation=frame,
            baseline=baseline,
            anomaly=anomaly,
            evidence=evidence,
            interpretation=interpretation,
            interpretation_error=interpretation_error,
            analysis=analysis,
            analysis_error=analysis_error,
            decision=decision,
            event=event,
            event_bridge_idempotency_key=bridge_key,
            fall_assessment=fall_assessment,
            degradation=degradation,
        )
        self._processed_frames[cache_key] = _ProcessedFrame(
            binding=binding,
            result=result,
            lane=lane,
            anomaly_id=anomaly_id,
        )
        return result

    def acknowledge_event(
        self,
        event_id: str,
        *,
        actor_id: str,
        at: datetime,
    ) -> MonitoringEvent:
        event_store = self._store_containing_event(event_id)
        event = event_store.get(event_id)
        suppressed_until = self.attention_policy.suppression_until(
            event.priority,
            at,
        )
        return event_store.acknowledge(
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
        if (
            anomaly.episode.state == AnomalyState.CANDIDATE
            or anomaly.episode.activated_at is None
        ):
            return None
        return build_evidence_packet(anomaly)

    def _event_store_for(self, tenant_id: str) -> EventStore:
        store = self._event_stores.get(tenant_id)
        if store is not None:
            return store
        store = (
            self.event_store
            if not self._event_stores
            else EventStore(policy=self.event_store.policy)
        )
        self._event_stores[tenant_id] = store
        return store

    def _store_containing_event(self, event_id: str) -> EventStore:
        stores = tuple(dict.fromkeys((self.event_store, *self._event_stores.values())))
        for store in stores:
            try:
                store.get(event_id)
            except KeyError:
                continue
            return store
        raise KeyError(f"Unknown event: {event_id}")

    def _existing_event(
        self,
        lane: LaneKey,
        anomaly_id: str,
    ) -> MonitoringEvent | None:
        event_id = self._event_ids_by_anomaly.get((lane, anomaly_id))
        return (
            self._event_store_for(lane[0]).get(event_id)
            if event_id is not None
            else None
        )

    def _recurrence_event_ids(
        self,
        lane: LaneKey,
        anomaly: AnomalyUpdate | None,
    ) -> tuple[str, ...]:
        if (
            anomaly is None
            or anomaly.episode is None
            or anomaly.episode.recurrence_of is None
        ):
            return ()
        prior_event_id = self._event_ids_by_anomaly.get(
            (lane, anomaly.episode.recurrence_of)
        )
        return (prior_event_id,) if prior_event_id is not None else ()

    def _replay(self, cached: _ProcessedFrame) -> IntelligenceResult:
        event = self._existing_event(cached.lane, cached.anomaly_id)
        decision = self._with_attention(
            cached.result.decision,
            event,
            cached.result.observation.window_end,
        )
        return replace(cached.result, event=event, decision=decision)

    @staticmethod
    def _with_attention(
        decision: DispositionDecision,
        event: MonitoringEvent | None,
        observed_at: datetime,
    ) -> DispositionDecision:
        attention_suppressed = bool(
            event is not None
            and event.status in (EventStatus.ACKNOWLEDGED, EventStatus.CHECKED)
            and event.attention_suppressed_until is not None
            and observed_at < event.attention_suppressed_until
        )
        return replace(
            decision,
            attention_suppressed=attention_suppressed,
        )


__all__ = ["IntelligenceResult", "MonitoringIntelligenceEngine"]
