"""Validation for untrusted structured monitoring interpretations."""

from enum import StrEnum
from math import isclose, isfinite
import re

from backend.app.ai.client import (
    InterpretationAlternative,
    InterpretationRequest,
    InterpretationResult,
    InterpretationStatus,
    RecommendedDisposition,
)


class InterpretationValidationError(ValueError):
    def __init__(self, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


_CERTAINTY = re.compile(
    r"diagnos|\bdefinite(?:ly)?\b|\bcertain(?:ly)?\b|\bconfirmed\b|\bconclusive\b",
    re.IGNORECASE,
)
_MEDICAL_CONCLUSIONS = {
    "stroke": re.compile(r"\bstroke\b", re.IGNORECASE),
    "seizure": re.compile(r"\bseizure\b", re.IGNORECASE),
    "heart_attack": re.compile(
        r"\b(?:heart attack|myocardial infarction)\b",
        re.IGNORECASE,
    ),
}
_MEASUREMENT_ALIASES = {
    "heart_rate": r"\bheart[\s_-]*rate\b",
    "respiratory_rate": r"\brespirat(?:ory|ion)[\s_-]*rate\b",
    "oxygen_saturation": r"\b(?:oxygen[\s_-]*saturation|spo2)\b",
    "blood_pressure": r"\bblood[\s_-]*pressure\b",
    "temperature": r"\btemperature\b",
    "movement": r"\bmovement\b",
}
_NUMBER = re.compile(r"(?<![A-Za-z0-9_.])-?\d+(?:\.\d+)?")


def _value(value: object) -> str:
    return value.value if isinstance(value, StrEnum) else str(value)


def _append(reasons: list[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _valid_confidence(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


def _text_surfaces(result: InterpretationResult) -> tuple[str, ...]:
    return (
        result.likely_explanation,
        *(alternative.label for alternative in result.alternatives),
        result.uncertainty,
        result.plain_english_summary,
        *result.missing_information,
        *result.limitations,
        *result.unsupported_conclusions,
        result.caregiver_wording,
    )


def _measurement_patterns(
    request: InterpretationRequest,
) -> dict[str, re.Pattern[str]]:
    names = {
        *_MEASUREMENT_ALIASES,
        *request.available_measurements,
        *request.unavailable_measurements,
    }
    patterns: dict[str, re.Pattern[str]] = {}
    for name in sorted(names):
        expression = _MEASUREMENT_ALIASES.get(name)
        if expression is None:
            parts = tuple(filter(None, re.split(r"[_\s-]+", name)))
            expression = r"\b" + r"[\s_-]*".join(map(re.escape, parts)) + r"\b"
        patterns[name] = re.compile(expression, re.IGNORECASE)
    return patterns


def _validate_text_measurements(
    request: InterpretationRequest,
    surfaces: tuple[str, ...],
    reasons: list[str],
) -> None:
    available = dict(request.measurement_values)
    unavailable = set(request.unavailable_measurements)
    patterns = _measurement_patterns(request)
    for surface in surfaces:
        numbers = tuple(float(match.group()) for match in _NUMBER.finditer(surface))
        if not numbers:
            continue
        for name, pattern in patterns.items():
            if not pattern.search(surface):
                continue
            for number in numbers:
                rendered = format(number, "g")
                if name in unavailable:
                    _append(
                        reasons,
                        f"unavailable_numeric_measurement_claim:{name}:{rendered}",
                    )
                elif name not in available or not any(
                    isclose(number, allowed, rel_tol=0.0, abs_tol=1e-9)
                    for allowed in available[name]
                ):
                    _append(
                        reasons,
                        f"unsupported_numeric_measurement_claim:{name}:{rendered}",
                    )


def validate_interpretation(
    request: InterpretationRequest,
    result: InterpretationResult,
) -> InterpretationResult:
    """Return a fully supported result or reject it with deterministic reasons."""

    reasons: list[str] = []
    status = _value(result.status)
    if status not in {item.value for item in InterpretationStatus}:
        _append(reasons, f"invalid_interpretation_status:{status}")
    disposition = _value(result.recommended_disposition)
    if disposition not in {item.value for item in RecommendedDisposition}:
        _append(reasons, f"invalid_recommended_disposition:{disposition}")

    provenance = (
        ("anomaly_id", result.anomaly_id, request.anomaly_id),
        ("packet_revision", result.packet_revision, request.packet_revision),
        ("model_id", result.model_id, request.model_id),
        ("model_version", result.model_version, request.model_version),
        ("skill_bundle", result.skill_bundle, request.skill_bundle),
        (
            "skill_bundle_version",
            result.skill_bundle_version,
            request.skill_bundle_version,
        ),
        ("prompt_version", result.prompt_version, request.prompt_version),
        (
            "invocation_version",
            result.invocation_version,
            request.invocation_version,
        ),
        (
            "retrieval_contract_version",
            result.retrieval_contract_version,
            request.retrieval_contract_version,
        ),
        (
            "output_schema_version",
            result.output_schema_version,
            request.output_schema_version,
        ),
        (
            "relevant_context_version",
            result.relevant_context_version,
            request.relevant_context_version,
        ),
        (
            "request_fingerprint",
            result.request_fingerprint,
            request.request_fingerprint,
        ),
    )
    for field, actual, expected in provenance:
        if actual != expected:
            _append(reasons, f"provenance_mismatch:{field}")

    for expected_rank, alternative in enumerate(result.alternatives, start=1):
        if not isinstance(alternative, InterpretationAlternative):
            _append(reasons, f"invalid_alternative_structure:{expected_rank}")
            continue
        if alternative.rank != expected_rank:
            _append(reasons, f"invalid_alternative_rank:{alternative.rank}")
        if not _valid_confidence(alternative.confidence):
            _append(reasons, f"invalid_alternative_confidence:{alternative.rank}")

    available_refs = set(request.available_evidence_refs)
    references = (
        *result.supporting_evidence_refs,
        *result.contradicting_evidence_refs,
        *(
            reference
            for alternative in result.alternatives
            if isinstance(alternative, InterpretationAlternative)
            for reference in (
                *alternative.supporting_evidence_refs,
                *alternative.contradicting_evidence_refs,
            )
        ),
    )
    for reference in references:
        if reference not in available_refs:
            _append(reasons, f"invented_evidence_ref:{reference}")

    available_measurements = set(request.available_measurements)
    unavailable_measurements = set(request.unavailable_measurements)
    for measurement in result.described_measurements:
        if measurement in unavailable_measurements:
            _append(reasons, f"unavailable_measurement_described:{measurement}")
        elif measurement not in available_measurements:
            _append(reasons, f"unsupported_measurement_description:{measurement}")

    if not _valid_confidence(result.confidence):
        _append(reasons, "invalid_interpretation_confidence")
    if not isinstance(result.needs_more_observation, bool):
        _append(reasons, "invalid_needs_more_observation")
    if not result.uncertainty.strip():
        _append(reasons, "blank_uncertainty")
    if not result.caregiver_wording.strip():
        _append(reasons, "blank_caregiver_wording")

    surfaces = _text_surfaces(result)
    normalized_text = re.sub(r"[_-]+", " ", " ".join(surfaces))
    if _CERTAINTY.search(normalized_text):
        _append(reasons, "diagnostic_certainty_not_allowed")
    else:
        for label, pattern in _MEDICAL_CONCLUSIONS.items():
            if pattern.search(normalized_text):
                _append(reasons, f"direct_medical_conclusion:{label}")
                break
    _validate_text_measurements(request, surfaces, reasons)

    addressed = set(result.addressed_contradictions)
    for contradiction in request.contradictions:
        if contradiction not in addressed:
            _append(reasons, f"contradiction_omitted:{contradiction}")
    stated_missing = set(result.missing_information)
    for missing in request.required_missing_information:
        if missing not in stated_missing:
            _append(reasons, f"required_missing_information_omitted:{missing}")
    stated_limitations = set(result.limitations)
    for limitation in request.required_limitations:
        if limitation not in stated_limitations:
            _append(reasons, f"required_limitation_omitted:{limitation}")

    if (
        request.urgent_deterministic_event
        and disposition != RecommendedDisposition.CAREGIVER_EVENT.value
        and disposition in {item.value for item in RecommendedDisposition}
    ):
        _append(reasons, "urgent_deterministic_event_cannot_be_downgraded")

    if reasons:
        raise InterpretationValidationError(tuple(reasons))
    return result


__all__ = [
    "InterpretationValidationError",
    "validate_interpretation",
]
