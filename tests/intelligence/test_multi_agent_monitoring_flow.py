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
from tests.intelligence.test_policy_orchestration import (
    _activate,
    _baseline,
    _fall_sequence,
    _movement_frame,
    _process,
)


def _run(
    disposition: RecommendedDisposition | str,
    severity: Severity | str,
    *,
    state: AnalysisState | str = AnalysisState.ANALYZED,
    attribution_scope: AttributionScope | str = AttributionScope.RESIDENT,
    packet=None,
) -> AnalysisRun:
    packet = packet or _packet()
    evidence_ref = packet.evidence_refs[0]
    possibility = Possibility(
        possibility_id="possibility_routine",
        label="routine bathroom movement",
        confidence=ConfidenceBand.MEDIUM,
        supporting_evidence_refs=(evidence_ref,),
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
            evidence_refs=(evidence_ref,),
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
        input_fingerprint="test-input-fingerprint",
        attempt_number=1,
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
    run = _run(
        RecommendedDisposition.OBSERVE,
        Severity.WATCH,
        state=AnalysisState.ANALYSIS_PENDING,
    )
    decision = MultiAgentDispositionPolicy().decide(
        packet=_packet(),
        analysis_run=run,
    )

    assert decision.disposition is PolicyDisposition.OBSERVE
    assert decision.priority is None
    assert decision.confidence == "analysis_pending"
    assert decision.fallback_used
    assert decision.analysis_id == run.analysis_id


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

    def analyze(
        self,
        packet,
        resident_memory,
        relevant_context_entry_ids=(),
        *,
        tenant_id,
    ):
        self.calls += 1
        return _run(
            self.result.final_analysis.recommended_disposition,
            self.result.final_analysis.severity,
            state=self.result.state,
            attribution_scope=self.result.final_analysis.attribution_scope,
            packet=packet,
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


def test_confirmed_fall_like_pattern_is_analyzed_before_critical_event() -> None:
    from backend.app.intelligence.orchestration import MonitoringIntelligenceEngine

    orchestrator = _ScriptedOrchestrator(
        _run(RecommendedDisposition.CAREGIVER_EVENT, Severity.CRITICAL)
    )
    engine = MonitoringIntelligenceEngine(analysis_orchestrator=orchestrator)
    result = None

    for frame in _fall_sequence():
        result = _process(engine, frame, baseline=_baseline(feature_name="unused"))

    assert result is not None
    assert result.fall_assessment.urgent_triggered
    assert result.evidence is not None
    assert result.analysis is not None
    assert orchestrator.calls == 1
    assert result.event is not None
    assert result.event.priority is EventPriority.CRITICAL


def test_multi_person_period_stays_room_level_operational_awareness() -> None:
    from backend.app.intelligence.orchestration import MonitoringIntelligenceEngine

    orchestrator = _ScriptedOrchestrator(
        _run(
            RecommendedDisposition.AWARENESS,
            Severity.HIGH,
            attribution_scope=AttributionScope.ROOM,
        )
    )
    engine = MonitoringIntelligenceEngine(analysis_orchestrator=orchestrator)

    result = None
    for second in range(3):
        result = _process(
            engine,
            _movement_frame(second, 0.5),
            possible_multiple_people=True,
        )

    assert result is not None
    assert result.decision.disposition is PolicyDisposition.AWARENESS
    assert result.decision.room_level_only
    assert result.event is None
    assert orchestrator.calls == 1
