"""Bounded, canonical context builders for multi-stage monitoring analysis."""

from dataclasses import asdict
from hashlib import sha256
import json

from backend.app.ai.analysis_contracts import (
    AnalysisStage,
    Possibility,
    RoutingPlan,
    SpecialistAssessment,
    SpecialistAssignment,
    StageRequest,
)
from backend.app.ai.analysis_skills import analysis_skill_registry, load_analysis_skill
from backend.app.ai.context import build_interpretation_request
from backend.app.domain.feedback import ResidentMemory
from backend.app.intelligence.evidence import EvidencePacket


_SPECIALISTS = tuple(
    name
    for name, skill in analysis_skill_registry().items()
    if skill.stage is AnalysisStage.SPECIALIST
)


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _case_payload(
    packet: EvidencePacket,
    resident_memory: ResidentMemory,
    relevant_context_entry_ids: tuple[str, ...],
) -> dict[str, object]:
    legacy = build_interpretation_request(
        packet,
        resident_memory,
        model_id="analysis_context_builder",
        model_version="multi_agent_v1",
        relevant_context_entry_ids=relevant_context_entry_ids,
    )
    payload = json.loads(legacy.payload_json)
    return {
        "anomaly_evidence": payload["anomaly_evidence"],
        "resident_context": payload["resident_context"],
    }


def _possibility_payload(item: Possibility) -> dict[str, object]:
    return {
        "possibility_id": item.possibility_id,
        "label": item.label,
        "confidence": item.confidence.value,
        "supporting_evidence_refs": list(item.supporting_evidence_refs),
        "contradicting_evidence_refs": list(item.contradicting_evidence_refs),
        "missing_information": list(item.missing_information),
        "rationale": item.rationale,
    }


def _assignment_payload(item: SpecialistAssignment) -> dict[str, object]:
    return {
        "specialist": item.specialist,
        "possibility_ids": list(item.possibility_ids),
        "reason": item.reason,
    }


def _assessment_payload(item: SpecialistAssessment) -> dict[str, object]:
    data = asdict(item)
    data["severity"] = item.severity.value
    data["recommended_disposition"] = item.recommended_disposition.value
    data["possibilities"] = [_possibility_payload(value) for value in item.possibilities]
    for field in (
        "assessed_possibility_ids",
        "missing_information",
        "contradictions",
        "evidence_refs",
    ):
        data[field] = list(getattr(item, field))
    return data


def _string_array() -> dict[str, object]:
    return {"type": "array", "items": {"type": "string"}}


def _possibility_schema() -> dict[str, object]:
    fields = {
        "possibility_id": {"type": "string"},
        "label": {"type": "string"},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "supporting_evidence_refs": _string_array(),
        "contradicting_evidence_refs": _string_array(),
        "missing_information": _string_array(),
        "rationale": {"type": "string"},
    }
    return {"type": "object", "required": list(fields), "properties": fields}


def recall_response_schema() -> dict[str, object]:
    fields = {
        "routing_id": {"type": "string"},
        "anomaly_id": {"type": "string"},
        "packet_revision": {"type": "integer", "minimum": 1},
        "possibilities": {"type": "array", "minItems": 1, "items": _possibility_schema()},
        "assignments": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["specialist", "possibility_ids", "reason"],
                "properties": {
                    "specialist": {"type": "string", "enum": list(_SPECIALISTS)},
                    "possibility_ids": _string_array(),
                    "reason": {"type": "string"},
                },
            },
        },
        "missing_information": _string_array(),
        "evidence_refs": _string_array(),
    }
    return {"type": "object", "required": list(fields), "properties": fields}


def specialist_response_schema() -> dict[str, object]:
    fields = {
        "assessment_id": {"type": "string"},
        "specialist": {"type": "string", "enum": list(_SPECIALISTS)},
        "anomaly_id": {"type": "string"},
        "packet_revision": {"type": "integer", "minimum": 1},
        "assessed_possibility_ids": _string_array(),
        "possibilities": {"type": "array", "minItems": 1, "items": _possibility_schema()},
        "severity": {"type": "string", "enum": ["observation", "watch", "high", "critical"]},
        "recommended_disposition": {"type": "string", "enum": ["no_action", "observe", "awareness", "caregiver_event"]},
        "missing_information": _string_array(),
        "contradictions": _string_array(),
        "evidence_refs": _string_array(),
    }
    return {"type": "object", "required": list(fields), "properties": fields}


def final_response_schema() -> dict[str, object]:
    fields = {
        "analysis_id": {"type": "string"},
        "anomaly_id": {"type": "string"},
        "packet_revision": {"type": "integer", "minimum": 1},
        "possibilities": {"type": "array", "minItems": 1, "items": _possibility_schema()},
        "severity": {"type": "string", "enum": ["observation", "watch", "high", "critical"]},
        "recommended_disposition": {"type": "string", "enum": ["no_action", "observe", "awareness", "caregiver_event"]},
        "attribution_scope": {"type": "string", "enum": ["resident", "room", "unknown"]},
        "caregiver_summary": {"type": "string"},
        "next_step": {"type": "string"},
        "missing_information": _string_array(),
        "specialist_disagreements": _string_array(),
        "evidence_refs": _string_array(),
        "considered_possibility_ids": _string_array(),
        "coverage_complete": {"type": "boolean"},
    }
    return {"type": "object", "required": list(fields), "properties": fields}


def _request(
    *,
    stage: AnalysisStage,
    packet: EvidencePacket,
    skill_names: tuple[str, ...],
    prompt: str,
    payload: dict[str, object],
    response_schema: dict[str, object],
    model_tier: str,
) -> StageRequest:
    payload_json = _canonical_json(payload)
    fingerprint = sha256(
        _canonical_json(
            {
                "anomaly_id": packet.anomaly_id,
                "model_tier": model_tier,
                "packet_revision": packet.packet_revision,
                "payload": payload,
                "prompt": prompt,
                "skills": list(skill_names),
                "stage": stage.value,
            }
        ).encode("utf-8")
    ).hexdigest()
    return StageRequest(
        stage=stage,
        anomaly_id=packet.anomaly_id,
        packet_revision=packet.packet_revision,
        skill_names=skill_names,
        prompt=prompt,
        payload_json=payload_json,
        response_schema=response_schema,
        request_fingerprint=fingerprint,
        model_tier=model_tier,
    )


def build_recall_request(
    packet: EvidencePacket,
    resident_memory: ResidentMemory,
    *,
    relevant_context_entry_ids: tuple[str, ...] = (),
    model_tier: str = "recall_tier",
) -> StageRequest:
    skill = load_analysis_skill("recall_router")
    payload = {
        "case": _case_payload(packet, resident_memory, relevant_context_entry_ids),
        "output_contract": {
            "allowed_evidence_refs": list(packet.evidence_refs),
            "allowed_specialists": list(_SPECIALISTS),
            "must_not_set_final_severity_or_action": True,
        },
        "versions": {"skill": f"{skill.name}@{skill.version}", "schema": "1.0"},
    }
    return _request(
        stage=AnalysisStage.RECALL,
        packet=packet,
        skill_names=(skill.name,),
        prompt=skill.instructions,
        payload=payload,
        response_schema=recall_response_schema(),
        model_tier=model_tier,
    )


def build_specialist_request(
    packet: EvidencePacket,
    resident_memory: ResidentMemory,
    plan: RoutingPlan,
    assignment: SpecialistAssignment,
    *,
    relevant_context_entry_ids: tuple[str, ...] = (),
    model_tier: str = "precision_tier",
) -> StageRequest:
    assignment.validate_against(plan.possibilities)
    skill = load_analysis_skill(assignment.specialist)
    routed = tuple(item for item in plan.possibilities if item.possibility_id in assignment.possibility_ids)
    payload = {
        "assignment": _assignment_payload(assignment),
        "case": _case_payload(packet, resident_memory, relevant_context_entry_ids),
        "output_contract": {
            "allowed_evidence_refs": list(packet.evidence_refs),
            "required_assessed_possibility_ids": list(assignment.possibility_ids),
        },
        "routing_possibilities": [_possibility_payload(item) for item in routed],
        "versions": {"skill": f"{skill.name}@{skill.version}", "schema": "1.0"},
    }
    return _request(
        stage=AnalysisStage.SPECIALIST,
        packet=packet,
        skill_names=(skill.name,),
        prompt=skill.instructions,
        payload=payload,
        response_schema=specialist_response_schema(),
        model_tier=model_tier,
    )


def build_final_request(
    packet: EvidencePacket,
    resident_memory: ResidentMemory,
    plan: RoutingPlan,
    assessments: tuple[SpecialistAssessment, ...],
    *,
    unavailable_specialists: tuple[str, ...],
    relevant_context_entry_ids: tuple[str, ...] = (),
    repair_errors: tuple[str, ...] = (),
    prior_result_json: str | None = None,
    model_tier: str = "final_tier",
) -> StageRequest:
    skill = load_analysis_skill("final_integrator_reviewer")
    payload = {
        "case": _case_payload(packet, resident_memory, relevant_context_entry_ids),
        "output_contract": {
            "allowed_evidence_refs": list(packet.evidence_refs),
            "required_considered_possibility_ids": [item.possibility_id for item in plan.possibilities],
            "required_specialists": [item.specialist for item in plan.assignments],
        },
        "routing_plan": {
            "routing_id": plan.routing_id,
            "possibilities": [_possibility_payload(item) for item in plan.possibilities],
            "assignments": [_assignment_payload(item) for item in plan.assignments],
            "missing_information": list(plan.missing_information),
        },
        "specialist_assessments": [_assessment_payload(item) for item in assessments],
        "unavailable_specialists": list(unavailable_specialists),
        "versions": {"skill": f"{skill.name}@{skill.version}", "schema": "1.0"},
    }
    stage = AnalysisStage.FINAL
    if repair_errors:
        stage = AnalysisStage.REPAIR
        payload["repair"] = {
            "errors": list(repair_errors),
            "prior_result_json": prior_result_json,
        }
    return _request(
        stage=stage,
        packet=packet,
        skill_names=(skill.name,),
        prompt=skill.instructions,
        payload=payload,
        response_schema=final_response_schema(),
        model_tier=model_tier,
    )


__all__ = [
    "build_final_request",
    "build_recall_request",
    "build_specialist_request",
    "final_response_schema",
    "recall_response_schema",
    "specialist_response_schema",
]
