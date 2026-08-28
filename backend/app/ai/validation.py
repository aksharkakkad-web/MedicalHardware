"""Validation for untrusted structured monitoring interpretations."""

from math import isfinite
import re
from enum import StrEnum

from backend.app.ai.client import (
    InterpretationRequest,
    InterpretationResult,
    InterpretationStatus,
    RecommendedDisposition,
)


class InterpretationValidationError(ValueError):
    def __init__(self, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


_DIAGNOSTIC_CERTAINTY = re.compile(
    r"diagnos|\bdefinite(?:ly)?\b|\bcertain(?:ly)?\b|\bconfirmed[_ -](?:stroke|seizure|heart attack)",
    re.IGNORECASE,
)


def _value(value: object) -> str:
    return value.value if isinstance(value, StrEnum) else str(value)


def validate_interpretation(
    request: InterpretationRequest,
    result: InterpretationResult,
) -> InterpretationResult:
    """Return a supported result or reject it with deterministic reasons."""

    reasons: list[str] = []
    status = _value(result.status)
    if status not in {item.value for item in InterpretationStatus}:
        reasons.append(f"invalid_interpretation_status:{status}")
    disposition = _value(result.recommended_disposition)
    if disposition not in {item.value for item in RecommendedDisposition}:
        reasons.append(f"invalid_recommended_disposition:{disposition}")

    if result.anomaly_id != request.anomaly_id:
        reasons.append("anomaly_id_mismatch")
    if result.packet_revision != request.packet_revision:
        reasons.append("packet_revision_mismatch")

    available_refs = set(request.available_evidence_refs)
    for reference in result.evidence_refs:
        if reference not in available_refs:
            reasons.append(f"invented_evidence_ref:{reference}")

    available_measurements = set(request.available_measurements)
    unavailable_measurements = set(request.unavailable_measurements)
    for measurement in result.described_measurements:
        if measurement in unavailable_measurements:
            reasons.append(f"unavailable_measurement_described:{measurement}")
        elif measurement not in available_measurements:
            reasons.append(f"unsupported_measurement_description:{measurement}")

    text_claims = " ".join(
        (
            result.likely_explanation,
            *result.alternatives,
            result.uncertainty,
            result.plain_english_summary,
        )
    )
    if _DIAGNOSTIC_CERTAINTY.search(text_claims):
        reasons.append("diagnostic_certainty_not_allowed")

    addressed = set(result.addressed_contradictions)
    for contradiction in request.contradictions:
        if contradiction not in addressed:
            reasons.append(f"contradiction_omitted:{contradiction}")

    if (
        request.urgent_deterministic_event
        and disposition != RecommendedDisposition.CAREGIVER_EVENT.value
        and disposition in {item.value for item in RecommendedDisposition}
    ):
        reasons.append("urgent_deterministic_event_cannot_be_downgraded")

    if isinstance(result.confidence, bool) or not isinstance(
        result.confidence, (int, float)
    ) or not isfinite(float(result.confidence)) or not 0.0 <= result.confidence <= 1.0:
        reasons.append("invalid_interpretation_confidence")

    if reasons:
        raise InterpretationValidationError(tuple(reasons))
    return result


__all__ = [
    "InterpretationValidationError",
    "validate_interpretation",
]
