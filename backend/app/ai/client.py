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
    contradictions: tuple[str, ...]
    urgent_deterministic_event: bool
    schema_version: str = "1.0"

    def to_json(self) -> str:
        return self.payload_json


@dataclass(frozen=True)
class InterpretationResult:
    interpretation_id: str
    anomaly_id: str
    packet_revision: int
    status: InterpretationStatus | str
    likely_explanation: str
    confidence: float
    alternatives: tuple[str, ...]
    uncertainty: str
    plain_english_summary: str
    evidence_refs: tuple[str, ...]
    described_measurements: tuple[str, ...]
    addressed_contradictions: tuple[str, ...]
    recommended_disposition: RecommendedDisposition | str
    model_id: str
    model_version: str
    skill_bundle_version: str
    prompt_version: str
    invocation_version: str
    schema_version: str = "1.0"


class LLMClient(Protocol):
    def interpret(self, request: InterpretationRequest) -> InterpretationResult:
        """Return one structured interpretation without controlling event state."""


class DeterministicFakeLLMClient:
    """Offline provider used for deterministic tests and replay."""

    def interpret(self, request: InterpretationRequest) -> InterpretationResult:
        digest = sha256(request.to_json().encode("utf-8")).hexdigest()[:20]
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
            evidence_refs=request.available_evidence_refs,
            described_measurements=request.available_measurements,
            addressed_contradictions=request.contradictions,
            recommended_disposition=(
                RecommendedDisposition.CAREGIVER_EVENT
                if request.urgent_deterministic_event
                else RecommendedDisposition.OBSERVE
            ),
            model_id=request.model_id,
            model_version=request.model_version,
            skill_bundle_version=request.skill_bundle_version,
            prompt_version=request.prompt_version,
            invocation_version=request.invocation_version,
        )


__all__ = [
    "DeterministicFakeLLMClient",
    "InterpretationRequest",
    "InterpretationResult",
    "InterpretationStatus",
    "LLMClient",
    "RecommendedDisposition",
]
