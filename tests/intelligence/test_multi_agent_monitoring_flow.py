from dataclasses import replace

from backend.app.ai.analysis_contracts import (
    AnalysisRun,
    AnalysisState,
    AttributionScope,
    ConfidenceBand,
    FinalAnalysis,
    Possibility,
    Severity,
)
from backend.app.ai.client import RecommendedDisposition
from backend.app.domain.events import EventPriority
from backend.app.intelligence.policy import (
    MultiAgentDispositionPolicy,
    PolicyDisposition,
)
from tests.ai.test_analysis_context import EVIDENCE_REF, _packet
from tests.intelligence.test_policy_orchestration import _activate, _process


def _run(
    disposition: RecommendedDisposition | str,
    severity: Severity | str,
    *,
    state: AnalysisState | str = AnalysisState.ANALYZED,
    attribution_scope: AttributionScope | str = AttributionScope.RESIDENT,
) -> AnalysisRun:
    packet = _packet()
    possibility = Possibility(
        possibility_id="possibility_routine",
        label="routine bathroom movement",
        confidence=ConfidenceBand.MEDIUM,
        supporting_evidence_refs=(EVIDENCE_REF,),
        contradicting_evidence_refs=(),
        missing_information=("direct staff confirmation",),
        rationale="The measured movement is compatible with ordinary room activity.",
    )
    final = None
    if AnalysisState(state) is AnalysisState.ANALYZED:
        final = FinalAnalysis(
            analysis_id="analysis_final_1",
            anomaly_id=packet.anomaly_id,
            packet_revision=packet.packet_revision,
            possibilities=(possibility,),
            severity=severity,
            recommended_disposition=disposition,
            attribution_scope=attribution_scope,
            caregiver_summary="Routine bathroom movement is plausible.",
            next_step="Observe and review if the pattern continues.",
            missing_information=("direct staff confirmation",),
            specialist_disagreements=(),
            evidence_refs=(EVIDENCE_REF,),
            considered_possibility_ids=(possibility.possibility_id,),
            coverage_complete=True,
            model_id="scripted-final",
            model_version="scripted-v1",
            skill_versions=("final-integrator-reviewer-v1",),
        )
    return AnalysisRun(
        analysis_id="analysis_final_1",
        anomaly_id=packet.anomaly_id,
        packet_revision=packet.packet_revision,
        state=state,
        routing_plan=None,
        specialist_assessments=(),
        unavailable_specialists=(),
        final_analysis=final,
        errors=("final_unavailable",) if final is None else (),
        repair_count=0,
    )


def test_trusted_observe_remains_observation_even_for_strong_anomaly() -> None:
    packet = _packet()
    decision = MultiAgentDispositionPolicy().decide(
        packet=packet,
        analysis_run=_run(RecommendedDisposition.OBSERVE, Severity.WATCH),
    )

    assert packet.overall_strength is not None and packet.overall_strength > 5
    assert decision.disposition is PolicyDisposition.OBSERVE
    assert decision.priority is None
    assert decision.reasons == ("trusted_final_analysis",)


def test_ai_unavailability_is_visible_pending_not_an_objective_severity_guess() -> None:
    decision = MultiAgentDispositionPolicy().decide(
        packet=_packet(),
        analysis_run=_run(
            RecommendedDisposition.OBSERVE,
            Severity.WATCH,
            state=AnalysisState.ANALYSIS_PENDING,
        ),
    )

    assert decision.disposition is PolicyDisposition.OBSERVE
    assert decision.priority is None
    assert decision.confidence == "analysis_pending"
    assert decision.fallback_used


def test_final_high_action_creates_high_priority_mapping() -> None:
    decision = MultiAgentDispositionPolicy().decide(
        packet=_packet(),
        analysis_run=_run(RecommendedDisposition.CAREGIVER_EVENT, Severity.HIGH),
    )

    assert decision.disposition is PolicyDisposition.CAREGIVER_EVENT
    assert decision.priority is EventPriority.HIGH


def test_final_critical_action_creates_critical_priority_mapping() -> None:
    decision = MultiAgentDispositionPolicy().decide(
        packet=_packet(),
        analysis_run=_run(
            RecommendedDisposition.CAREGIVER_EVENT,
            Severity.CRITICAL,
        ),
    )

    assert decision.disposition is PolicyDisposition.CAREGIVER_EVENT
    assert decision.priority is EventPriority.CRITICAL


def test_room_or_unknown_attribution_never_claims_resident_identity() -> None:
    decision = MultiAgentDispositionPolicy().decide(
        packet=_packet(),
        analysis_run=_run(
            RecommendedDisposition.AWARENESS,
            Severity.WATCH,
            attribution_scope=AttributionScope.ROOM,
        ),
    )

    assert decision.disposition is PolicyDisposition.AWARENESS
    assert decision.room_level_only


class _ScriptedOrchestrator:
    def __init__(self, result: AnalysisRun) -> None:
        self.result = result
        self.calls = 0

    def analyze(self, packet, resident_memory, relevant_context_entry_ids=()):
        self.calls += 1
        final = self.result.final_analysis
        if final is not None:
            final = replace(
                final,
                anomaly_id=packet.anomaly_id,
                packet_revision=packet.packet_revision,
            )
        return replace(
            self.result,
            anomaly_id=packet.anomaly_id,
            packet_revision=packet.packet_revision,
            final_analysis=final,
        )


def test_monitoring_engine_uses_final_action_to_create_exactly_one_event() -> None:
    from backend.app.intelligence.orchestration import MonitoringIntelligenceEngine

    orchestrator = _ScriptedOrchestrator(
        _run(RecommendedDisposition.CAREGIVER_EVENT, Severity.HIGH)
    )
    engine = MonitoringIntelligenceEngine(analysis_orchestrator=orchestrator)

    result = _activate(engine)
    replay = _process(engine, result.observation)

    assert result.analysis is not None
    assert result.interpretation is None
    assert result.event is not None
    assert result.event.priority is EventPriority.HIGH
    assert replay.event is not None
    assert replay.event.event_id == result.event.event_id
    assert replay.event.signal_count == 1
    assert orchestrator.calls == 1


def test_monitoring_engine_keeps_trusted_observe_out_of_caregiver_queue() -> None:
    from backend.app.intelligence.orchestration import MonitoringIntelligenceEngine

    orchestrator = _ScriptedOrchestrator(
        _run(RecommendedDisposition.OBSERVE, Severity.WATCH)
    )
    engine = MonitoringIntelligenceEngine(analysis_orchestrator=orchestrator)

    result = _activate(engine)

    assert result.analysis is not None
    assert result.decision.disposition is PolicyDisposition.OBSERVE
    assert result.event is None
