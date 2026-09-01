"""Strict parsing and evidence grounding for staged AI results."""

import json

from backend.app.ai.analysis_contracts import (
    AttributionScope,
    FinalAnalysis,
    Possibility,
    RoutingPlan,
    SpecialistAssessment,
    SpecialistAssignment,
    StageRequest,
    StageResponse,
    StageStatus,
)
from backend.app.ai.analysis_skills import analysis_skill_registry
from backend.app.intelligence.evidence import EvidencePacket


class AnalysisValidationError(ValueError):
    def __init__(self, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


def _payload(request: StageRequest, response: StageResponse) -> dict[str, object]:
    try:
        response.validate_for(request)
    except ValueError as exc:
        raise AnalysisValidationError((str(exc),)) from None
    if response.status != StageStatus.COMPLETE or response.payload_json is None:
        raise AnalysisValidationError((f"stage_status:{response.status.value}",))
    try:
        value = json.loads(response.payload_json)
    except (TypeError, ValueError):
        raise AnalysisValidationError(("invalid_json",)) from None
    if not isinstance(value, dict):
        raise AnalysisValidationError(("response_must_be_object",))
    return value


def _tuple(payload: dict[str, object], field: str) -> tuple[str, ...]:
    value = payload[field]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise TypeError(field)
    return tuple(value)


def _possibility(payload: object) -> Possibility:
    if not isinstance(payload, dict):
        raise TypeError("possibility")
    return Possibility(
        possibility_id=payload["possibility_id"],
        label=payload["label"],
        confidence=payload["confidence"],
        supporting_evidence_refs=_tuple(payload, "supporting_evidence_refs"),
        contradicting_evidence_refs=_tuple(payload, "contradicting_evidence_refs"),
        missing_information=_tuple(payload, "missing_information"),
        rationale=payload["rationale"],
    )


def _ground(packet: EvidencePacket, refs: tuple[str, ...]) -> None:
    if not set(refs) <= set(packet.evidence_refs):
        raise AnalysisValidationError(("unsupported_evidence_reference",))


def validate_routing_plan(
    packet: EvidencePacket,
    request: StageRequest,
    response: StageResponse,
) -> RoutingPlan:
    value = _payload(request, response)
    try:
        possibilities = tuple(_possibility(item) for item in value["possibilities"])
        assignments = tuple(
            SpecialistAssignment(
                specialist=item["specialist"],
                possibility_ids=_tuple(item, "possibility_ids"),
                reason=item["reason"],
            )
            for item in value["assignments"]
        )
        known_specialists = analysis_skill_registry()
        if any(item.specialist not in known_specialists or known_specialists[item.specialist].stage.value != "specialist" for item in assignments):
            raise AnalysisValidationError(("unknown_specialist",))
        result = RoutingPlan(
            routing_id=value["routing_id"],
            anomaly_id=value["anomaly_id"],
            packet_revision=value["packet_revision"],
            possibilities=possibilities,
            assignments=assignments,
            missing_information=_tuple(value, "missing_information"),
            evidence_refs=_tuple(value, "evidence_refs"),
            model_id=response.model_id,
            model_version=response.model_version,
            skill_version="recall_router@1.0",
        )
    except AnalysisValidationError:
        raise
    except (KeyError, TypeError, ValueError):
        raise AnalysisValidationError(("invalid_routing_plan",)) from None
    if result.anomaly_id != packet.anomaly_id or result.packet_revision != packet.packet_revision:
        raise AnalysisValidationError(("routing_identity_mismatch",))
    for possibility in result.possibilities:
        _ground(packet, possibility.evidence_refs)
    _ground(packet, result.evidence_refs)
    return result


def validate_specialist_assessment(
    packet: EvidencePacket,
    assignment: SpecialistAssignment,
    request: StageRequest,
    response: StageResponse,
) -> SpecialistAssessment:
    value = _payload(request, response)
    try:
        result = SpecialistAssessment(
            assessment_id=value["assessment_id"],
            specialist=value["specialist"],
            anomaly_id=value["anomaly_id"],
            packet_revision=value["packet_revision"],
            assessed_possibility_ids=_tuple(value, "assessed_possibility_ids"),
            possibilities=tuple(_possibility(item) for item in value["possibilities"]),
            severity=value["severity"],
            recommended_disposition=value["recommended_disposition"],
            missing_information=_tuple(value, "missing_information"),
            contradictions=_tuple(value, "contradictions"),
            evidence_refs=_tuple(value, "evidence_refs"),
            model_id=response.model_id,
            model_version=response.model_version,
            skill_version=f"{assignment.specialist}@1.0",
        )
    except (KeyError, TypeError, ValueError):
        raise AnalysisValidationError(("invalid_specialist_assessment",)) from None
    if result.anomaly_id != packet.anomaly_id or result.packet_revision != packet.packet_revision:
        raise AnalysisValidationError(("specialist_identity_mismatch",))
    if result.specialist != assignment.specialist or result.assessed_possibility_ids != assignment.possibility_ids:
        raise AnalysisValidationError(("specialist_assignment_mismatch",))
    for possibility in result.possibilities:
        _ground(packet, possibility.evidence_refs)
    _ground(packet, result.evidence_refs)
    return result


def validate_final_analysis(
    packet: EvidencePacket,
    plan: RoutingPlan,
    request: StageRequest,
    response: StageResponse,
) -> FinalAnalysis:
    value = _payload(request, response)
    try:
        result = FinalAnalysis(
            analysis_id=value["analysis_id"],
            anomaly_id=value["anomaly_id"],
            packet_revision=value["packet_revision"],
            possibilities=tuple(_possibility(item) for item in value["possibilities"]),
            severity=value["severity"],
            recommended_disposition=value["recommended_disposition"],
            attribution_scope=value["attribution_scope"],
            caregiver_summary=value["caregiver_summary"],
            next_step=value["next_step"],
            missing_information=_tuple(value, "missing_information"),
            specialist_disagreements=_tuple(value, "specialist_disagreements"),
            evidence_refs=_tuple(value, "evidence_refs"),
            considered_possibility_ids=_tuple(value, "considered_possibility_ids"),
            coverage_complete=value["coverage_complete"],
            model_id=response.model_id,
            model_version=response.model_version,
            skill_versions=("final_integrator_reviewer@1.0",),
        )
    except (KeyError, TypeError, ValueError):
        raise AnalysisValidationError(("invalid_final_analysis",)) from None
    if result.anomaly_id != packet.anomaly_id or result.packet_revision != packet.packet_revision:
        raise AnalysisValidationError(("final_identity_mismatch",))
    required = {item.possibility_id for item in plan.possibilities}
    if not result.coverage_complete or set(result.considered_possibility_ids) != required:
        raise AnalysisValidationError(("incomplete_possibility_coverage",))
    if "resident_attribution_ambiguous" in packet.limitations and result.attribution_scope is AttributionScope.RESIDENT:
        raise AnalysisValidationError(("unsupported_resident_attribution",))
    for possibility in result.possibilities:
        _ground(packet, possibility.evidence_refs)
    _ground(packet, result.evidence_refs)
    return result


__all__ = [
    "AnalysisValidationError",
    "validate_final_analysis",
    "validate_routing_plan",
    "validate_specialist_assessment",
]
