import json
from dataclasses import replace

import pytest

from backend.app.ai.analysis_context import (
    build_final_request,
    build_recall_request,
    build_specialist_request,
)
from backend.app.ai.analysis_contracts import AnalysisStage, AttributionScope, StageResponse, StageStatus
from backend.app.ai.analysis_validation import (
    AnalysisValidationError,
    validate_final_analysis,
    validate_routing_plan,
    validate_specialist_assessment,
)
from tests.ai.test_analysis_context import (
    EVIDENCE_REF,
    _assessment,
    _memory,
    _packet,
    _plan,
)


def _response(request, payload: dict[str, object]) -> StageResponse:
    return StageResponse(
        stage=request.stage,
        status=StageStatus.COMPLETE,
        request_fingerprint=request.request_fingerprint,
        payload_json=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        model_id="fake",
        model_version="fake-v1",
        latency_ms=5,
    )


def _possibility_payload() -> dict[str, object]:
    return {
        "possibility_id": "possibility_routine",
        "label": "routine movement",
        "confidence": "medium",
        "supporting_evidence_refs": [EVIDENCE_REF],
        "contradicting_evidence_refs": [],
        "missing_information": ["direct confirmation"],
        "rationale": "The movement may match normal activity.",
    }


def test_routing_validation_rejects_invented_evidence_and_unknown_specialist() -> None:
    request = build_recall_request(_packet(), _memory())
    payload = {
        "routing_id": "routing_1",
        "anomaly_id": "anomaly_1",
        "packet_revision": 2,
        "possibilities": [_possibility_payload()],
        "assignments": [{
            "specialist": "routine_context",
            "possibility_ids": ["possibility_routine"],
            "reason": "Routine context is relevant.",
        }],
        "missing_information": ["direct confirmation"],
        "evidence_refs": [EVIDENCE_REF],
    }
    assert validate_routing_plan(_packet(), request, _response(request, payload)).routing_id == "routing_1"

    invented = json.loads(json.dumps(payload))
    invented["possibilities"][0]["supporting_evidence_refs"] = ["evidence://invented"]
    invented["evidence_refs"] = ["evidence://invented"]
    with pytest.raises(AnalysisValidationError, match="evidence"):
        validate_routing_plan(_packet(), request, _response(request, invented))

    unknown = json.loads(json.dumps(payload))
    unknown["assignments"][0]["specialist"] = "imaginary_specialist"
    with pytest.raises(AnalysisValidationError, match="specialist"):
        validate_routing_plan(_packet(), request, _response(request, unknown))


def test_specialist_validation_requires_exact_assignment_coverage() -> None:
    plan = _plan()
    assignment = plan.assignments[0]
    request = build_specialist_request(_packet(), _memory(), plan, assignment)
    payload = {
        "assessment_id": "assessment_1",
        "specialist": "routine_context",
        "anomaly_id": "anomaly_1",
        "packet_revision": 2,
        "assessed_possibility_ids": ["possibility_routine"],
        "possibilities": [_possibility_payload()],
        "severity": "watch",
        "recommended_disposition": "observe",
        "missing_information": ["direct confirmation"],
        "contradictions": [],
        "evidence_refs": [EVIDENCE_REF],
    }
    assert validate_specialist_assessment(
        _packet(), assignment, request, _response(request, payload)
    ).specialist == "routine_context"

    payload["assessed_possibility_ids"] = ["possibility_other"]
    payload["possibilities"][0]["possibility_id"] = "possibility_other"
    with pytest.raises(AnalysisValidationError, match="assignment"):
        validate_specialist_assessment(
            _packet(), assignment, request, _response(request, payload)
        )


def test_final_validation_requires_complete_router_coverage_but_allows_observe_for_strong_anomaly() -> None:
    plan = _plan()
    request = build_final_request(_packet(), _memory(), plan, (_assessment(),), unavailable_specialists=())
    payload = {
        "analysis_id": "analysis_1",
        "anomaly_id": "anomaly_1",
        "packet_revision": 2,
        "possibilities": [_possibility_payload()],
        "severity": "watch",
        "recommended_disposition": "observe",
        "attribution_scope": "resident",
        "caregiver_summary": "Movement changed, with routine activity still plausible.",
        "next_step": "Observe and review if the pattern continues.",
        "missing_information": ["direct confirmation"],
        "specialist_disagreements": [],
        "evidence_refs": [EVIDENCE_REF],
        "considered_possibility_ids": ["possibility_routine"],
        "coverage_complete": True,
    }

    result = validate_final_analysis(_packet(), plan, request, _response(request, payload))
    assert result.recommended_disposition.value == "observe"

    payload["considered_possibility_ids"] = ["possibility_skipped"]
    with pytest.raises(AnalysisValidationError, match="coverage"):
        validate_final_analysis(_packet(), plan, request, _response(request, payload))


def test_final_validation_rejects_resident_attribution_during_multi_person_ambiguity() -> None:
    packet = _packet(limitations=("resident_attribution_ambiguous",))
    plan = _plan()
    request = build_final_request(packet, _memory(), plan, (_assessment(),), unavailable_specialists=())
    payload = {
        "analysis_id": "analysis_1",
        "anomaly_id": "anomaly_1",
        "packet_revision": 2,
        "possibilities": [_possibility_payload()],
        "severity": "watch",
        "recommended_disposition": "observe",
        "attribution_scope": AttributionScope.RESIDENT.value,
        "caregiver_summary": "Movement changed.",
        "next_step": "Review room context.",
        "missing_information": ["identity"],
        "specialist_disagreements": [],
        "evidence_refs": [EVIDENCE_REF],
        "considered_possibility_ids": ["possibility_routine"],
        "coverage_complete": True,
    }

    with pytest.raises(AnalysisValidationError, match="attribution"):
        validate_final_analysis(packet, plan, request, _response(request, payload))


def test_stage_response_must_match_request_before_payload_is_trusted() -> None:
    request = build_recall_request(_packet(), _memory())
    response = StageResponse(
        stage=AnalysisStage.RECALL,
        status=StageStatus.COMPLETE,
        request_fingerprint="wrong",
        payload_json="{}",
        model_id="fake",
        model_version="fake-v1",
        latency_ms=1,
    )
    with pytest.raises(AnalysisValidationError, match="fingerprint"):
        validate_routing_plan(_packet(), request, response)
