"""Provider-neutral structured interpretation request and response types."""

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Protocol


class InterpretationStatus(StrEnum):
    PENDING = "pending"
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"


class RecommendedDisposition(StrEnum):
    NO_ACTION = "no_action"
    OBSERVE = "observe"
    AWARENESS = "awareness"
    CAREGIVER_EVENT = "caregiver_event"


class ExplanationCategory(StrEnum):
    UNKNOWN = "unknown"
    UNUSUAL_MOVEMENT = "unusual_movement"
    ROUTINE_MOVEMENT = "routine_movement"
    FALL_LIKE = "fall_like"
    INACTIVITY = "inactivity"
    RESPIRATORY_CHANGE = "respiratory_change"
    ROUTINE_CHANGE = "routine_change"
    MONITORING_DEGRADED = "monitoring_degraded"
    MULTI_PERSON_AMBIGUITY = "multi_person_ambiguity"


class UncertaintyCategory(StrEnum):
    CAUSE_NOT_ESTABLISHED = "cause_not_established"
    EVIDENCE_LIMITED = "evidence_limited"
    ATTRIBUTION_AMBIGUOUS = "attribution_ambiguous"


INTERPRETATION_SCHEMA_VERSION = "1.0"
ALLOWED_UNSUPPORTED_CONCLUSIONS = (
    "causal_explanation",
    "medical_diagnosis",
    "person_identity",
    "unobserved_measurement",
)
_CATEGORY_PHRASES = {
    ExplanationCategory.UNKNOWN: "unclassified anomaly",
    ExplanationCategory.UNUSUAL_MOVEMENT: "unusual movement pattern",
    ExplanationCategory.ROUTINE_MOVEMENT: "routine movement pattern",
    ExplanationCategory.FALL_LIKE: "fall-like signal pattern",
    ExplanationCategory.INACTIVITY: "inactivity pattern",
    ExplanationCategory.RESPIRATORY_CHANGE: "respiratory signal change",
    ExplanationCategory.ROUTINE_CHANGE: "routine-change pattern",
    ExplanationCategory.MONITORING_DEGRADED: "monitoring-degraded state",
    ExplanationCategory.MULTI_PERSON_AMBIGUITY: "multi-person ambiguity",
}
_SUMMARY_TEMPLATES = {
    ExplanationCategory.UNKNOWN: (
        "The evidence is unusual, but it does not support a specific explanation."
    ),
    ExplanationCategory.UNUSUAL_MOVEMENT: (
        "The evidence supports an unusual movement pattern."
    ),
    ExplanationCategory.ROUTINE_MOVEMENT: (
        "The evidence supports a possible routine movement pattern."
    ),
    ExplanationCategory.FALL_LIKE: (
        "The evidence supports a possible fall-like signal pattern."
    ),
    ExplanationCategory.INACTIVITY: "The evidence supports an inactivity pattern.",
    ExplanationCategory.RESPIRATORY_CHANGE: (
        "The evidence supports a respiratory signal change."
    ),
    ExplanationCategory.ROUTINE_CHANGE: (
        "The evidence supports a possible routine-change pattern."
    ),
    ExplanationCategory.MONITORING_DEGRADED: (
        "The evidence indicates that monitoring is degraded."
    ),
    ExplanationCategory.MULTI_PERSON_AMBIGUITY: (
        "The evidence indicates ambiguous resident attribution."
    ),
}


def render_plain_english_summary(category: ExplanationCategory) -> str:
    return _SUMMARY_TEMPLATES[ExplanationCategory(category)]


def render_caregiver_wording(
    category: ExplanationCategory,
    disposition: RecommendedDisposition,
) -> str:
    phrase = _CATEGORY_PHRASES[ExplanationCategory(category)]
    action = {
        RecommendedDisposition.NO_ACTION: (
            "no caregiver action is recommended from this interpretation"
        ),
        RecommendedDisposition.OBSERVE: (
            "observe and review the objective evidence and declared limitations"
        ),
        RecommendedDisposition.AWARENESS: (
            "share awareness and review the objective evidence and declared limitations"
        ),
        RecommendedDisposition.CAREGIVER_EVENT: (
            "create or preserve caregiver work and review the objective evidence and "
            "declared limitations"
        ),
    }[RecommendedDisposition(disposition)]
    return f"For the {phrase}, {action}."


@dataclass(frozen=True)
class InterpretationRequest:
    anomaly_id: str
    packet_revision: int
    prompt: str
    skill_bundle: tuple[str, ...]
    prompt_version: str
    skill_bundle_version: str
    retrieval_contract_version: str
    output_schema_version: str
    model_id: str
    model_version: str
    invocation_version: str
    relevant_context_version: str
    payload_json: str
    available_evidence_refs: tuple[str, ...]
    available_measurements: tuple[str, ...]
    unavailable_measurements: tuple[str, ...]
    contradictions: tuple[str, ...]
    required_missing_information: tuple[str, ...]
    required_limitations: tuple[str, ...]
    required_unsupported_conclusions: tuple[str, ...]
    retrieved_context_refs: tuple[str, ...]
    request_fingerprint: str
    urgent_deterministic_event: bool
    schema_version: str = INTERPRETATION_SCHEMA_VERSION

    def to_json(self) -> str:
        return self.payload_json


@dataclass(frozen=True)
class InterpretationAlternative:
    rank: int
    label: ExplanationCategory | str
    confidence: float
    supporting_evidence_refs: tuple[str, ...]
    contradicting_evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class InterpretationResult:
    interpretation_id: str
    anomaly_id: str
    packet_revision: int
    status: InterpretationStatus | str
    likely_explanation: ExplanationCategory | str
    confidence: float
    alternatives: tuple[InterpretationAlternative, ...]
    uncertainty: UncertaintyCategory | str
    plain_english_summary: str
    supporting_evidence_refs: tuple[str, ...]
    contradicting_evidence_refs: tuple[str, ...]
    described_measurements: tuple[str, ...]
    addressed_contradictions: tuple[str, ...]
    missing_information: tuple[str, ...]
    limitations: tuple[str, ...]
    unsupported_conclusions: tuple[str, ...]
    needs_more_observation: bool
    caregiver_wording: str
    recommended_disposition: RecommendedDisposition | str
    model_id: str
    model_version: str
    skill_bundle: tuple[str, ...]
    skill_bundle_version: str
    prompt_version: str
    invocation_version: str
    retrieval_contract_version: str
    output_schema_version: str
    relevant_context_version: str
    request_fingerprint: str
    schema_version: str = INTERPRETATION_SCHEMA_VERSION


class LLMClient(Protocol):
    def interpret(self, request: InterpretationRequest) -> InterpretationResult:
        """Return one structured interpretation without controlling event state."""


class DeterministicFakeLLMClient:
    """Offline provider used for deterministic tests and replay."""

    def interpret(self, request: InterpretationRequest) -> InterpretationResult:
        digest = sha256(request.request_fingerprint.encode("utf-8")).hexdigest()[:20]
        category = {
            "fall_like": ExplanationCategory.FALL_LIKE,
            "inactivity": ExplanationCategory.INACTIVITY,
            "movement": ExplanationCategory.UNUSUAL_MOVEMENT,
            "respiration": ExplanationCategory.RESPIRATORY_CHANGE,
            "routine_change": ExplanationCategory.ROUTINE_CHANGE,
            "monitoring_degraded": ExplanationCategory.MONITORING_DEGRADED,
            "unknown_anomaly": ExplanationCategory.UNKNOWN,
        }[request.skill_bundle[1]]
        disposition = (
            RecommendedDisposition.CAREGIVER_EVENT
            if request.urgent_deterministic_event
            else RecommendedDisposition.OBSERVE
        )
        if "resident_attribution_ambiguous" in request.required_limitations:
            uncertainty = UncertaintyCategory.ATTRIBUTION_AMBIGUOUS
        elif request.required_limitations or request.required_missing_information:
            uncertainty = UncertaintyCategory.EVIDENCE_LIMITED
        else:
            uncertainty = UncertaintyCategory.CAUSE_NOT_ESTABLISHED
        return InterpretationResult(
            interpretation_id=f"fake_{digest}",
            anomaly_id=request.anomaly_id,
            packet_revision=request.packet_revision,
            status=InterpretationStatus.COMPLETE,
            likely_explanation=category,
            confidence=0.0,
            alternatives=(),
            uncertainty=uncertainty,
            plain_english_summary=render_plain_english_summary(category),
            supporting_evidence_refs=request.available_evidence_refs,
            contradicting_evidence_refs=(),
            described_measurements=request.available_measurements,
            addressed_contradictions=request.contradictions,
            missing_information=request.required_missing_information,
            limitations=request.required_limitations,
            unsupported_conclusions=request.required_unsupported_conclusions,
            needs_more_observation=True,
            caregiver_wording=render_caregiver_wording(category, disposition),
            recommended_disposition=disposition,
            model_id=request.model_id,
            model_version=request.model_version,
            skill_bundle=request.skill_bundle,
            skill_bundle_version=request.skill_bundle_version,
            prompt_version=request.prompt_version,
            invocation_version=request.invocation_version,
            retrieval_contract_version=request.retrieval_contract_version,
            output_schema_version=request.output_schema_version,
            relevant_context_version=request.relevant_context_version,
            request_fingerprint=request.request_fingerprint,
        )


__all__ = [
    "ALLOWED_UNSUPPORTED_CONCLUSIONS",
    "DeterministicFakeLLMClient",
    "ExplanationCategory",
    "INTERPRETATION_SCHEMA_VERSION",
    "InterpretationAlternative",
    "InterpretationRequest",
    "InterpretationResult",
    "InterpretationStatus",
    "LLMClient",
    "RecommendedDisposition",
    "UncertaintyCategory",
    "render_caregiver_wording",
    "render_plain_english_summary",
]
