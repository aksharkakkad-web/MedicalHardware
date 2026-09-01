"""Strict application boundary for AI-proposed resident-memory changes."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Mapping

from backend.app.domain._validation import require_nonblank_text
from backend.app.domain.feedback import MEMORY_CONTEXT_KINDS, MemoryContextKind


class MemoryUpdateAction(StrEnum):
    NO_CHANGE = "no_change"
    ADD_CANDIDATE = "add_candidate"
    REINFORCE = "reinforce"
    REVISE = "revise"
    RETIRE = "retire"


@dataclass(frozen=True)
class MemoryUpdateProposal:
    action: MemoryUpdateAction
    resident_id: str
    source_feedback_id: str
    evidence_refs: tuple[str, ...]
    confidence: float
    context_kind: MemoryContextKind
    description: str
    reason: str
    review_after_days: int
    schema_version: str = "1.0"


_FIELDS = {
    "action",
    "resident_id",
    "source_feedback_id",
    "evidence_refs",
    "confidence",
    "context_kind",
    "description",
    "reason",
    "review_after_days",
}


def parse_memory_update_proposal(
    payload: Mapping[str, object],
    *,
    expected_resident_id: str,
    source_feedback_id: str,
    allowed_evidence_refs: tuple[str, ...],
) -> MemoryUpdateProposal:
    """Validate model output without granting it authority to mutate memory."""

    if not isinstance(payload, Mapping):
        raise ValueError("memory proposal must be an object")
    unknown = set(payload) - _FIELDS
    missing = _FIELDS - set(payload)
    if unknown:
        raise ValueError(f"memory proposal contains unknown or protected fields: {sorted(unknown)}")
    if missing:
        raise ValueError(f"memory proposal is missing fields: {sorted(missing)}")
    expected_resident_id = require_nonblank_text(expected_resident_id, "expected_resident_id")
    source_feedback_id = require_nonblank_text(source_feedback_id, "source_feedback_id")
    if source_feedback_id.casefold().startswith("ack"):
        raise ValueError("memory proposals require explicit feedback, not acknowledgment")
    resident_id = require_nonblank_text(payload["resident_id"], "resident_id")
    if resident_id != expected_resident_id:
        raise ValueError("resident_id does not match the protected request identity")
    proposal_feedback_id = require_nonblank_text(
        payload["source_feedback_id"], "source_feedback_id"
    )
    if proposal_feedback_id != source_feedback_id:
        raise ValueError("source_feedback_id does not match explicit feedback")
    try:
        action = MemoryUpdateAction(payload["action"])
    except (TypeError, ValueError) as exc:
        raise ValueError("memory proposal action is invalid") from exc
    context_kind = payload["context_kind"]
    if context_kind not in MEMORY_CONTEXT_KINDS:
        raise ValueError("memory proposal context_kind is invalid")
    refs_value = payload["evidence_refs"]
    if not isinstance(refs_value, list) or not refs_value:
        raise ValueError("evidence_refs must be a non-empty list")
    evidence_refs = tuple(require_nonblank_text(ref, "evidence_ref") for ref in refs_value)
    if len(set(evidence_refs)) != len(evidence_refs):
        raise ValueError("evidence_refs must not contain duplicates")
    if not set(evidence_refs) <= set(allowed_evidence_refs):
        raise ValueError("memory proposal contains an unsupported evidence reference")
    confidence = payload["confidence"]
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise ValueError("confidence must be numeric")
    confidence = float(confidence)
    if not isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise ValueError("confidence must be between 0 and 1")
    review_after_days = payload["review_after_days"]
    if isinstance(review_after_days, bool) or not isinstance(review_after_days, int):
        raise ValueError("review_after_days must be an int")
    if not 1 <= review_after_days <= 365:
        raise ValueError("review_after_days must be between 1 and 365")
    return MemoryUpdateProposal(
        action=action,
        resident_id=resident_id,
        source_feedback_id=proposal_feedback_id,
        evidence_refs=evidence_refs,
        confidence=confidence,
        context_kind=context_kind,
        description=require_nonblank_text(payload["description"], "description"),
        reason=require_nonblank_text(payload["reason"], "reason"),
        review_after_days=review_after_days,
    )


__all__ = [
    "MemoryUpdateAction",
    "MemoryUpdateProposal",
    "parse_memory_update_proposal",
]
