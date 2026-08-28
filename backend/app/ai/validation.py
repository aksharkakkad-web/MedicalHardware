"""Validation for untrusted structured monitoring interpretations."""

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


def _append(reasons: list[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _valid_confidence(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return 0 <= value <= 1
    if isinstance(value, float):
        return isfinite(value) and 0.0 <= value <= 1.0
    return False


def _required_text(
    value: object,
    *,
    field: str,
    reasons: list[str],
) -> str | None:
    if not isinstance(value, str):
        _append(reasons, f"invalid_{field}_type")
        return None
    if not value.strip():
        _append(reasons, f"blank_{field}")
        return None
    return value


def _text_tuple(
    value: object,
    *,
    field: str,
    reasons: list[str],
    duplicate_singular: str | None = None,
    shape_suffix: str = "",
) -> tuple[str, ...] | None:
    if not isinstance(value, tuple):
        _append(reasons, f"invalid_{field}_shape{shape_suffix}")
        return None

    valid = True
    seen: set[str] = set()
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str):
            _append(reasons, f"invalid_{field}_item:{index}{shape_suffix}")
            valid = False
            continue
        if not item.strip():
            _append(reasons, f"blank_{field}_item:{index}{shape_suffix}")
            valid = False
            continue
        if item in seen and duplicate_singular is not None:
            _append(reasons, f"duplicate_{duplicate_singular}:{item}")
        seen.add(item)
    return value if valid else None


def _enum_value(
    value: object,
    *,
    field: str,
    allowed: frozenset[str],
    reasons: list[str],
) -> str | None:
    raw = _required_text(value, field=field, reasons=reasons)
    if raw is None:
        return None
    if raw not in allowed:
        _append(reasons, f"invalid_{field}:{raw}")
        return None
    return raw


def _category(
    value: object,
    *,
    field: str,
    request: InterpretationRequest,
    reasons: list[str],
    rank: int | None = None,
) -> ExplanationCategory | None:
    if rank is not None and not isinstance(value, str):
        _append(reasons, f"invalid_alternative_label_type:{rank}")
        return None
    if rank is not None and isinstance(value, str) and not value.strip():
        _append(reasons, f"blank_alternative_label:{rank}")
        return None
    raw = _required_text(value, field=field, reasons=reasons)
    if raw is None:
        return None
    try:
        category = ExplanationCategory(raw)
    except ValueError:
        if field == "likely_explanation":
            _append(reasons, f"invalid_explanation_category:{raw}")
        elif rank is not None:
            _append(reasons, f"invalid_alternative_category:{rank}:{raw}")
        else:
            _append(reasons, f"invalid_{field}_category:{raw}")
        return None

    primary_skill = request.skill_bundle[1]
    allowed = set(_ALLOWED_CATEGORIES_BY_SKILL[primary_skill])
    if "multi_person" in request.skill_bundle:
        allowed.add(ExplanationCategory.MULTI_PERSON_AMBIGUITY)
    if category not in allowed:
        if field == "likely_explanation":
            _append(reasons, f"explanation_category_not_allowed_for_skill:{raw}")
        elif rank is not None:
            _append(
                reasons,
                f"alternative_category_not_allowed_for_skill:{rank}:{raw}",
            )
        else:
            _append(reasons, f"{field}_category_not_allowed_for_skill:{raw}")
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


def _validate_string_provenance(
    *,
    field: str,
    actual: object,
    expected: str,
    reasons: list[str],
) -> str | None:
    value = _required_text(actual, field=field, reasons=reasons)
    if value is not None and value != expected:
        _append(reasons, f"provenance_mismatch:{field}")
    return value


def validate_interpretation(
    request: InterpretationRequest,
    result: InterpretationResult,
) -> InterpretationResult:
    """Return a fully supported result or reject it with deterministic reasons."""

    if not isinstance(result, InterpretationResult):
        raise InterpretationValidationError(("invalid_interpretation_result_structure",))

    reasons: list[str] = []
    _required_text(
        result.interpretation_id,
        field="interpretation_id",
        reasons=reasons,
    )

    _enum_value(
        result.status,
        field="interpretation_status",
        allowed=frozenset(item.value for item in InterpretationStatus),
        reasons=reasons,
    )
    disposition_value = _enum_value(
        result.recommended_disposition,
        field="recommended_disposition",
        allowed=frozenset(item.value for item in RecommendedDisposition),
        reasons=reasons,
    )

    _validate_string_provenance(
        field="anomaly_id",
        actual=result.anomaly_id,
        expected=request.anomaly_id,
        reasons=reasons,
    )
    if isinstance(result.packet_revision, bool) or not isinstance(
        result.packet_revision, int
    ):
        _append(reasons, "invalid_packet_revision_type")
    elif result.packet_revision != request.packet_revision:
        _append(reasons, "provenance_mismatch:packet_revision")

    for field, actual, expected in (
        ("model_id", result.model_id, request.model_id),
        ("model_version", result.model_version, request.model_version),
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
    ):
        _validate_string_provenance(
            field=field,
            actual=actual,
            expected=expected,
            reasons=reasons,
        )

    skill_bundle = _text_tuple(
        result.skill_bundle,
        field="skill_bundle",
        reasons=reasons,
        duplicate_singular="skill",
    )
    if skill_bundle is not None and skill_bundle != request.skill_bundle:
        _append(reasons, "provenance_mismatch:skill_bundle")

    if request.schema_version != INTERPRETATION_SCHEMA_VERSION:
        _append(
            reasons,
            f"unsupported_request_schema_version:{request.schema_version}",
        )
    elif (
        isinstance(result.schema_version, str)
        and result.schema_version == request.schema_version
        and result.schema_version != INTERPRETATION_SCHEMA_VERSION
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

    alternative_refs: list[tuple[str, ...]] = []
    if not isinstance(result.alternatives, tuple):
        _append(reasons, "invalid_alternatives_shape")
    else:
        for expected_rank, alternative in enumerate(result.alternatives, start=1):
            if not isinstance(alternative, InterpretationAlternative):
                _append(reasons, f"invalid_alternative_structure:{expected_rank}")
                continue
            if isinstance(alternative.rank, bool) or not isinstance(
                alternative.rank, int
            ):
                _append(reasons, f"invalid_alternative_rank:{expected_rank}")
            elif alternative.rank != expected_rank:
                _append(reasons, f"invalid_alternative_rank:{alternative.rank}")
            if not _valid_confidence(alternative.confidence):
                confidence_rank = (
                    alternative.rank
                    if not isinstance(alternative.rank, bool)
                    and isinstance(alternative.rank, int)
                    else expected_rank
                )
                _append(
                    reasons,
                    f"invalid_alternative_confidence:{confidence_rank}",
                )
            _category(
                alternative.label,
                field="alternative_label",
                request=request,
                reasons=reasons,
                rank=expected_rank,
            )
            supporting = _text_tuple(
                alternative.supporting_evidence_refs,
                field="alternative_supporting_evidence_refs",
                reasons=reasons,
                duplicate_singular=(
                    f"alternative_supporting_evidence_ref:{expected_rank}"
                ),
                shape_suffix=f":{expected_rank}",
            )
            contradicting = _text_tuple(
                alternative.contradicting_evidence_refs,
                field="alternative_contradicting_evidence_refs",
                reasons=reasons,
                duplicate_singular=(
                    f"alternative_contradicting_evidence_ref:{expected_rank}"
                ),
                shape_suffix=f":{expected_rank}",
            )
            if supporting is not None:
                alternative_refs.append(supporting)
            if contradicting is not None:
                alternative_refs.append(contradicting)

    supporting_refs = _text_tuple(
        result.supporting_evidence_refs,
        field="supporting_evidence_refs",
        reasons=reasons,
        duplicate_singular="supporting_evidence_ref",
    )
    contradicting_refs = _text_tuple(
        result.contradicting_evidence_refs,
        field="contradicting_evidence_refs",
        reasons=reasons,
        duplicate_singular="contradicting_evidence_ref",
    )
    available_refs = set(request.available_evidence_refs)
    for refs in (supporting_refs, contradicting_refs, *alternative_refs):
        if refs is None:
            continue
        for reference in refs:
            if reference not in available_refs:
                _append(reasons, f"invented_evidence_ref:{reference}")

    described_measurements = _text_tuple(
        result.described_measurements,
        field="described_measurements",
        reasons=reasons,
        duplicate_singular="described_measurement",
    )
    if described_measurements is not None:
        available_measurements = set(request.available_measurements)
        unavailable_measurements = set(request.unavailable_measurements)
        for measurement in described_measurements:
            if measurement in unavailable_measurements:
                _append(
                    reasons,
                    f"unavailable_measurement_described:{measurement}",
                )
            elif measurement not in available_measurements:
                _append(
                    reasons,
                    f"unsupported_measurement_description:{measurement}",
                )

    if not _valid_confidence(result.confidence):
        _append(reasons, "invalid_interpretation_confidence")
    if not isinstance(result.needs_more_observation, bool):
        _append(reasons, "invalid_needs_more_observation")

    uncertainty = _required_text(
        result.uncertainty,
        field="uncertainty",
        reasons=reasons,
    )
    if uncertainty is not None and uncertainty not in {
        item.value for item in UncertaintyCategory
    }:
        _append(reasons, f"invalid_uncertainty_category:{uncertainty}")

    summary = _required_text(
        result.plain_english_summary,
        field="plain_english_summary",
        reasons=reasons,
    )
    if summary is not None and likely_category is not None and (
        summary != render_plain_english_summary(likely_category)
    ):
        _append(reasons, "plain_english_summary_mismatch")

    caregiver_wording = _required_text(
        result.caregiver_wording,
        field="caregiver_wording",
        reasons=reasons,
    )
    if (
        caregiver_wording is not None
        and likely_category is not None
        and disposition_value is not None
        and caregiver_wording
        != render_caregiver_wording(
            likely_category,
            RecommendedDisposition(disposition_value),
        )
    ):
        _append(reasons, "caregiver_wording_mismatch")

    addressed_contradictions = _text_tuple(
        result.addressed_contradictions,
        field="addressed_contradictions",
        reasons=reasons,
        duplicate_singular="addressed_contradiction",
    )
    missing_information = _text_tuple(
        result.missing_information,
        field="missing_information",
        reasons=reasons,
        duplicate_singular="missing_information",
    )
    limitations = _text_tuple(
        result.limitations,
        field="limitations",
        reasons=reasons,
        duplicate_singular="limitation",
    )
    unsupported_conclusions = _text_tuple(
        result.unsupported_conclusions,
        field="unsupported_conclusions",
        reasons=reasons,
        duplicate_singular="unsupported_conclusion",
    )

    if addressed_contradictions is not None:
        _validate_exact_identifiers(
            actual=addressed_contradictions,
            expected=request.contradictions,
            singular="contradiction",
            omission_prefix="contradiction_omitted",
            reasons=reasons,
        )
    if missing_information is not None:
        _validate_exact_identifiers(
            actual=missing_information,
            expected=request.required_missing_information,
            singular="missing_information",
            omission_prefix="required_missing_information_omitted",
            reasons=reasons,
        )
    if limitations is not None:
        _validate_exact_identifiers(
            actual=limitations,
            expected=request.required_limitations,
            singular="limitation",
            omission_prefix="required_limitation_omitted",
            reasons=reasons,
        )
    if unsupported_conclusions is not None:
        required_unsupported = set(request.required_unsupported_conclusions)
        unsupported_set = set(unsupported_conclusions)
        for item in request.required_unsupported_conclusions:
            if item not in unsupported_set:
                _append(
                    reasons,
                    f"required_unsupported_conclusion_omitted:{item}",
                )
        for item in unsupported_conclusions:
            if item not in ALLOWED_UNSUPPORTED_CONCLUSIONS:
                _append(reasons, f"unsupported_conclusion_not_allowed:{item}")
            elif item not in required_unsupported:
                _append(reasons, f"undeclared_unsupported_conclusion:{item}")

    if (
        request.urgent_deterministic_event
        and disposition_value is not None
        and disposition_value != RecommendedDisposition.CAREGIVER_EVENT.value
    ):
        _append(reasons, "urgent_deterministic_event_cannot_be_downgraded")

    if reasons:
        raise InterpretationValidationError(tuple(reasons))
    return result


__all__ = [
    "InterpretationValidationError",
    "validate_interpretation",
]
