"""Validation for untrusted structured monitoring interpretations."""

from enum import StrEnum
from math import isfinite

from backend.app.ai.client import (
    ALLOWED_UNSUPPORTED_CONCLUSIONS,
    INTERPRETATION_SCHEMA_VERSION,
    ExplanationCategory,
    InterpretationAlternative,
    InterpretationRequest,
    InterpretationResult,
    InterpretationStatus,
    RecommendedDisposition,
    UncertaintyCategory,
    render_caregiver_wording,
    render_plain_english_summary,
)


class InterpretationValidationError(ValueError):
    def __init__(self, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


_ALLOWED_CATEGORIES_BY_SKILL = {
    "fall_like": {
        ExplanationCategory.UNKNOWN,
        ExplanationCategory.FALL_LIKE,
        ExplanationCategory.UNUSUAL_MOVEMENT,
    },
    "inactivity": {
        ExplanationCategory.UNKNOWN,
        ExplanationCategory.INACTIVITY,
    },
    "movement": {
        ExplanationCategory.UNKNOWN,
        ExplanationCategory.UNUSUAL_MOVEMENT,
        ExplanationCategory.ROUTINE_MOVEMENT,
    },
    "respiration": {
        ExplanationCategory.UNKNOWN,
        ExplanationCategory.RESPIRATORY_CHANGE,
    },
    "routine_change": {
        ExplanationCategory.UNKNOWN,
        ExplanationCategory.ROUTINE_CHANGE,
        ExplanationCategory.ROUTINE_MOVEMENT,
    },
    "monitoring_degraded": {
        ExplanationCategory.UNKNOWN,
        ExplanationCategory.MONITORING_DEGRADED,
    },
    "unknown_anomaly": {ExplanationCategory.UNKNOWN},
}


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


def _category(
    value: object,
    *,
    field: str,
    request: InterpretationRequest,
    reasons: list[str],
) -> ExplanationCategory | None:
    raw = _value(value)
    if not raw.strip():
        _append(reasons, f"blank_{field}")
        return None
    try:
        category = ExplanationCategory(raw)
    except ValueError:
        reason_field = "explanation" if field == "likely_explanation" else field
        _append(reasons, f"invalid_{reason_field}_category:{raw}")
        return None
    primary_skill = request.skill_bundle[1]
    allowed = set(_ALLOWED_CATEGORIES_BY_SKILL[primary_skill])
    if "multi_person" in request.skill_bundle:
        allowed.add(ExplanationCategory.MULTI_PERSON_AMBIGUITY)
    if category not in allowed:
        reason_field = "explanation" if field == "likely_explanation" else field
        _append(reasons, f"{reason_field}_category_not_allowed_for_skill:{raw}")
        return None
    return category


def _validate_exact_identifiers(
    *,
    actual: tuple[str, ...],
    expected: tuple[str, ...],
    singular: str,
    omission_prefix: str,
    reasons: list[str],
) -> None:
    actual_set = set(actual)
    expected_set = set(expected)
    for item in expected:
        if item not in actual_set:
            _append(reasons, f"{omission_prefix}:{item}")
    for item in actual:
        if item not in expected_set:
            _append(reasons, f"undeclared_{singular}:{item}")


def validate_interpretation(
    request: InterpretationRequest,
    result: InterpretationResult,
) -> InterpretationResult:
    """Return a fully supported result or reject it with deterministic reasons."""

    reasons: list[str] = []
    status = _value(result.status)
    valid_status = status in {item.value for item in InterpretationStatus}
    if not valid_status:
        _append(reasons, f"invalid_interpretation_status:{status}")
    disposition_value = _value(result.recommended_disposition)
    valid_disposition = disposition_value in {
        item.value for item in RecommendedDisposition
    }
    if not valid_disposition:
        _append(reasons, f"invalid_recommended_disposition:{disposition_value}")

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
        ("schema_version", result.schema_version, request.schema_version),
    )
    for field, actual, expected in provenance:
        if actual != expected:
            _append(reasons, f"provenance_mismatch:{field}")
    if request.schema_version != INTERPRETATION_SCHEMA_VERSION:
        _append(
            reasons,
            f"unsupported_request_schema_version:{request.schema_version}",
        )
    elif result.schema_version == request.schema_version and (
        result.schema_version != INTERPRETATION_SCHEMA_VERSION
    ):
        _append(
            reasons,
            f"unsupported_result_schema_version:{result.schema_version}",
        )

    likely_category = _category(
        result.likely_explanation,
        field="likely_explanation",
        request=request,
        reasons=reasons,
    )
    valid_alternatives: list[InterpretationAlternative] = []
    for expected_rank, alternative in enumerate(result.alternatives, start=1):
        if not isinstance(alternative, InterpretationAlternative):
            _append(reasons, f"invalid_alternative_structure:{expected_rank}")
            continue
        valid_alternatives.append(alternative)
        if alternative.rank != expected_rank:
            _append(reasons, f"invalid_alternative_rank:{alternative.rank}")
        if not _valid_confidence(alternative.confidence):
            _append(reasons, f"invalid_alternative_confidence:{alternative.rank}")
        raw_label = _value(alternative.label)
        if not raw_label.strip():
            _append(reasons, f"blank_alternative_label:{expected_rank}")
        else:
            category_reasons: list[str] = []
            alternative_category = _category(
                alternative.label,
                field="alternative",
                request=request,
                reasons=category_reasons,
            )
            for reason in category_reasons:
                if reason.startswith("invalid_alternative_category:"):
                    reason = (
                        f"invalid_alternative_category:{expected_rank}:"
                        f"{raw_label}"
                    )
                elif reason.startswith("alternative_category_not_allowed"):
                    reason = (
                        f"alternative_category_not_allowed_for_skill:"
                        f"{expected_rank}:{raw_label}"
                    )
                _append(reasons, reason)
            if alternative_category is None:
                continue

    available_refs = set(request.available_evidence_refs)
    references = (
        *result.supporting_evidence_refs,
        *result.contradicting_evidence_refs,
        *(
            reference
            for alternative in valid_alternatives
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

    uncertainty_value = _value(result.uncertainty)
    if not uncertainty_value.strip():
        _append(reasons, "blank_uncertainty")
    elif uncertainty_value not in {item.value for item in UncertaintyCategory}:
        _append(reasons, f"invalid_uncertainty_category:{uncertainty_value}")

    if not result.plain_english_summary.strip():
        _append(reasons, "blank_plain_english_summary")
    elif likely_category is not None and (
        result.plain_english_summary
        != render_plain_english_summary(likely_category)
    ):
        _append(reasons, "plain_english_summary_mismatch")

    if not result.caregiver_wording.strip():
        _append(reasons, "blank_caregiver_wording")
    elif likely_category is not None and valid_disposition and (
        result.caregiver_wording
        != render_caregiver_wording(
            likely_category,
            RecommendedDisposition(disposition_value),
        )
    ):
        _append(reasons, "caregiver_wording_mismatch")

    _validate_exact_identifiers(
        actual=result.addressed_contradictions,
        expected=request.contradictions,
        singular="contradiction",
        omission_prefix="contradiction_omitted",
        reasons=reasons,
    )
    _validate_exact_identifiers(
        actual=result.missing_information,
        expected=request.required_missing_information,
        singular="missing_information",
        omission_prefix="required_missing_information_omitted",
        reasons=reasons,
    )
    _validate_exact_identifiers(
        actual=result.limitations,
        expected=request.required_limitations,
        singular="limitation",
        omission_prefix="required_limitation_omitted",
        reasons=reasons,
    )

    unsupported_set = set(result.unsupported_conclusions)
    required_unsupported = set(request.required_unsupported_conclusions)
    for item in request.required_unsupported_conclusions:
        if item not in unsupported_set:
            _append(reasons, f"required_unsupported_conclusion_omitted:{item}")
    for item in result.unsupported_conclusions:
        if item not in ALLOWED_UNSUPPORTED_CONCLUSIONS:
            _append(reasons, f"unsupported_conclusion_not_allowed:{item}")
        elif item not in required_unsupported:
            _append(reasons, f"undeclared_unsupported_conclusion:{item}")

    if (
        request.urgent_deterministic_event
        and disposition_value != RecommendedDisposition.CAREGIVER_EVENT.value
        and valid_disposition
    ):
        _append(reasons, "urgent_deterministic_event_cannot_be_downgraded")

    if reasons:
        raise InterpretationValidationError(tuple(reasons))
    return result


__all__ = [
    "InterpretationValidationError",
    "validate_interpretation",
]
