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
    measurement_values: tuple[tuple[str, tuple[float, ...]], ...]
    contradictions: tuple[str, ...]
    required_missing_information: tuple[str, ...]
    required_limitations: tuple[str, ...]
    retrieved_context_refs: tuple[str, ...]
    request_fingerprint: str
    urgent_deterministic_event: bool
    schema_version: str = "1.0"

    def to_json(self) -> str:
        return self.payload_json


@dataclass(frozen=True)
class InterpretationAlternative:
    rank: int
    label: str
    confidence: float
    supporting_evidence_refs: tuple[str, ...]
    contradicting_evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class InterpretationResult:
    interpretation_id: str
    anomaly_id: str
    packet_revision: int
    status: InterpretationStatus | str
    likely_explanation: str
    confidence: float
    alternatives: tuple[InterpretationAlternative, ...]
    uncertainty: str
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
    schema_version: str = "1.0"


class LLMClient(Protocol):
    def interpret(self, request: InterpretationRequest) -> InterpretationResult:
        """Return one structured interpretation without controlling event state."""


class DeterministicFakeLLMClient:
    """Offline provider used for deterministic tests and replay."""

    def interpret(self, request: InterpretationRequest) -> InterpretationResult:
        digest = sha256(request.request_fingerprint.encode("utf-8")).hexdigest()[:20]
        return InterpretationResult(
            interpretation_id=f"fake_{digest}",
            anomaly_id=request.anomaly_id,
            packet_revision=request.packet_revision,
            status=InterpretationStatus.COMPLETE,
            likely_explanation="unknown",
            confidence=0.0,
            alternatives=(),
            uncertainty=(
                "The cause cannot be determined from the available structured evidence."
            ),
            plain_english_summary=(
                "The evidence shows an unusual change, but does not establish its cause."
            ),
            supporting_evidence_refs=request.available_evidence_refs,
            contradicting_evidence_refs=(),
            described_measurements=request.available_measurements,
            addressed_contradictions=request.contradictions,
            missing_information=request.required_missing_information,
            limitations=request.required_limitations,
            unsupported_conclusions=(
                "medical_cause_not_supported",
                "person_identity_not_supported",
            ),
            needs_more_observation=True,
            caregiver_wording=(
                "Review the objective evidence, missing information, and limitations."
            ),
            recommended_disposition=(
                RecommendedDisposition.CAREGIVER_EVENT
                if request.urgent_deterministic_event
                else RecommendedDisposition.OBSERVE
            ),
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
    "DeterministicFakeLLMClient",
    "InterpretationAlternative",
    "InterpretationRequest",
    "InterpretationResult",
    "InterpretationStatus",
    "LLMClient",
    "RecommendedDisposition",
]
