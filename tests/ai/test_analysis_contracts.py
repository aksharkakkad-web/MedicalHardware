from dataclasses import replace

import pytest

from backend.app.ai.analysis_contracts import (
    AnalysisRun,
    AnalysisStage,
    AnalysisState,
    AttributionScope,
    ConfidenceBand,
    FinalAnalysis,
    Possibility,
    RoutingPlan,
    Severity,
    SpecialistAssessment,
    SpecialistAssignment,
    StageRequest,
    StageResponse,
    StageStatus,
)
from backend.app.ai.client import RecommendedDisposition


def _possibility(
    possibility_id: str = "possibility_routine",
    *,
    evidence_refs: tuple[str, ...] = ("evidence://movement",),
) -> Possibility:
    return Possibility(
        possibility_id=possibility_id,
        label="routine movement",
        confidence=ConfidenceBand.MEDIUM,
        supporting_evidence_refs=evidence_refs,
        contradicting_evidence_refs=(),
        missing_information=("direct visual confirmation",),
        rationale="Movement could match a normal room activity.",
    )


def _final() -> FinalAnalysis:
    primary = _possibility()
    alternative = _possibility(
        "possibility_sensor_issue",
        evidence_refs=("evidence://quality",),
    )
    return FinalAnalysis(
        analysis_id="analysis_1",
        anomaly_id="anomaly_1",
        packet_revision=2,
        possibilities=(primary, alternative),
        severity=Severity.WATCH,
        recommended_disposition=RecommendedDisposition.OBSERVE,
        attribution_scope=AttributionScope.RESIDENT,
        caregiver_summary="Movement changed, but routine activity remains plausible.",
        next_step="Observe the room status and review if the pattern continues.",
        missing_information=("direct visual confirmation",),
        specialist_disagreements=(),
        evidence_refs=("evidence://movement", "evidence://quality"),
        considered_possibility_ids=(
            "possibility_routine",
            "possibility_sensor_issue",
        ),
        coverage_complete=True,
        model_id="test-provider",
        model_version="test-model-v1",
        skill_versions=("final_integrator_reviewer@1.0",),
    )


def test_contracts_normalize_enum_strings_and_preserve_multiple_possibilities() -> None:
    result = replace(
        _final(),
        severity="watch",
        recommended_disposition="observe",
    )

    assert result.severity is Severity.WATCH
    assert result.recommended_disposition is RecommendedDisposition.OBSERVE
    assert [item.possibility_id for item in result.possibilities] == [
        "possibility_routine",
        "possibility_sensor_issue",
    ]


@pytest.mark.parametrize(
    "replacement",
    (
        {"analysis_id": " "},
        {"anomaly_id": ""},
        {"packet_revision": 0},
        {"model_id": ""},
        {"skill_versions": ()},
    ),
)
def test_final_analysis_rejects_missing_identity_and_provenance(
    replacement: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        replace(_final(), **replacement)


def test_final_analysis_rejects_duplicate_possibilities() -> None:
    duplicated = _possibility()

    with pytest.raises(ValueError, match="possibility_id"):
        replace(_final(), possibilities=(duplicated, duplicated))


def test_final_analysis_rejects_evidence_not_used_by_any_possibility() -> None:
    with pytest.raises(ValueError, match="evidence_refs"):
        replace(_final(), evidence_refs=("evidence://invented",))


@pytest.mark.parametrize(
    ("severity", "disposition"),
    (
        (Severity.CRITICAL, RecommendedDisposition.OBSERVE),
        (Severity.OBSERVATION, RecommendedDisposition.CAREGIVER_EVENT),
        (Severity.HIGH, RecommendedDisposition.NO_ACTION),
    ),
)
def test_final_analysis_rejects_internally_inconsistent_action_and_severity(
    severity: Severity,
    disposition: RecommendedDisposition,
) -> None:
    with pytest.raises(ValueError, match="severity and recommended_disposition"):
        replace(
            _final(),
            severity=severity,
            recommended_disposition=disposition,
        )


def test_routing_plan_rejects_duplicate_specialists_and_unknown_possibilities() -> None:
    possibility = _possibility()
    assignment = SpecialistAssignment(
        specialist="routine_context",
        possibility_ids=(possibility.possibility_id,),
        reason="Routine context may explain the movement.",
    )

    with pytest.raises(ValueError, match="specialist"):
        RoutingPlan(
            routing_id="routing_1",
            anomaly_id="anomaly_1",
            packet_revision=2,
            possibilities=(possibility,),
            assignments=(assignment, assignment),
            missing_information=(),
            evidence_refs=("evidence://movement",),
            model_id="test-provider",
            model_version="test-model-v1",
            skill_version="recall_router@1.0",
        )

    with pytest.raises(ValueError, match="unknown possibility"):
        replace(
            assignment,
            possibility_ids=("possibility_not_routed",),
        ).validate_against((possibility,))


def test_specialist_assessment_rejects_wrong_or_duplicate_assigned_possibilities() -> None:
    possibility = _possibility()
    with pytest.raises(ValueError, match="assessed_possibility_ids"):
        SpecialistAssessment(
            assessment_id="assessment_1",
            specialist="routine_context",
            anomaly_id="anomaly_1",
            packet_revision=2,
            assessed_possibility_ids=(possibility.possibility_id, possibility.possibility_id),
            possibilities=(possibility,),
            severity=Severity.WATCH,
            recommended_disposition=RecommendedDisposition.OBSERVE,
            missing_information=(),
            contradictions=(),
            evidence_refs=("evidence://movement",),
            model_id="test-provider",
            model_version="test-model-v1",
            skill_version="routine_context@1.0",
        )


def test_stage_request_and_response_bind_the_same_stage_and_fingerprint() -> None:
    request = StageRequest(
        stage=AnalysisStage.RECALL,
        anomaly_id="anomaly_1",
        packet_revision=2,
        skill_names=("recall_router",),
        prompt="bounded prompt",
        payload_json='{"bounded":true}',
        response_schema={"type": "object"},
        request_fingerprint="fingerprint_1",
        model_tier="recall_tier",
    )
    response = StageResponse(
        stage="recall",
        status=StageStatus.COMPLETE,
        request_fingerprint="fingerprint_1",
        payload_json='{"result":true}',
        model_id="test-provider",
        model_version="test-model-v1",
        latency_ms=12,
        input_tokens=20,
        output_tokens=10,
    )

    response.validate_for(request)
    with pytest.raises(ValueError, match="request_fingerprint"):
        replace(response, request_fingerprint="wrong").validate_for(request)


def test_analysis_run_requires_final_result_only_in_analyzed_state() -> None:
    pending = AnalysisRun(
        analysis_id="analysis_1",
        anomaly_id="anomaly_1",
        packet_revision=2,
        state=AnalysisState.ANALYSIS_PENDING,
        routing_plan=None,
        specialist_assessments=(),
        unavailable_specialists=(),
        final_analysis=None,
        errors=("provider unavailable",),
        repair_count=0,
    )
    assert pending.final_analysis is None

    with pytest.raises(ValueError, match="final_analysis"):
        replace(pending, state=AnalysisState.ANALYZED)

    analyzed = replace(pending, state=AnalysisState.ANALYZED, final_analysis=_final())
    assert analyzed.final_analysis is not None
