import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.ai import client as ai_client
from backend.app.ai.client import (
    DeterministicFakeLLMClient,
    InterpretationResult,
    InterpretationStatus,
    RecommendedDisposition,
)
from backend.app.ai.context import build_interpretation_request
from backend.app.ai.skills import load_skill, select_skill_bundle
from backend.app.ai.validation import (
    InterpretationValidationError,
    validate_interpretation,
)
from backend.app.domain.feedback import MemoryEntry, ResidentMemory
from backend.app.intelligence.anomaly import AnomalyState, FeatureDeviation
from backend.app.intelligence.evidence import EvidencePacket
from backend.app.intelligence.observations import QualityClass


_NOW = datetime(2026, 8, 28, 15, 0, tzinfo=timezone.utc)


def _deviation(feature_name: str = "movement") -> FeatureDeviation:
    return FeatureDeviation(
        feature_name=feature_name,
        source="radar",
        observation_id=f"observation_{feature_name}",
        value=4.25,
        unit="normalized",
        quality_class=QualityClass.GOOD,
        quality_reasons=(),
        baseline_median=1.0,
        baseline_mad=0.5,
        baseline_iqr=0.75,
        baseline_lower_quantile=0.5,
        baseline_upper_quantile=1.5,
        baseline_resolution_floor=0.1,
        baseline_context_key="resident_global",
        robust_z=6.5,
        direction="up",
        trajectory="sustained",
        persistence_frames=3,
    )


def _packet(
    feature_name: str = "movement",
    *,
    contradictions: tuple[str, ...] = (),
    overall_strength: float | None = 6.5,
    missing_initiating_features: tuple[str, ...] = (),
    evidence_limited: bool = False,
    limitations: tuple[str, ...] | None = None,
) -> EvidencePacket:
    changed_features = () if feature_name == "none" else (_deviation(feature_name),)
    return EvidencePacket(
        anomaly_id="anomaly_17",
        packet_revision=2,
        lifecycle_state=AnomalyState.ACTIVE,
        resident_id="resident_42",
        room_id="room_7",
        candidate_started_at=_NOW - timedelta(seconds=10),
        activated_at=_NOW - timedelta(seconds=5),
        current_time=_NOW,
        overall_strength=overall_strength,
        strength_scale="max_abs_robust_z",
        progression="sustained",
        changed_features=changed_features,
        agreements=("movement:radar=thermal=changed",),
        contradictions=contradictions,
        missing_modalities=("wifi_csi",),
        missing_initiating_features=missing_initiating_features,
        evidence_limited=evidence_limited,
        limitations=(
            limitations
            if limitations is not None
            else (("missing_initiating_evidence",) if evidence_limited else ())
        ),
        baseline_id="baseline_4",
        baseline_policy_version="baseline_v1",
        monitoring_setup_version="setup_v3",
        filter_version="filter_v2",
        config_version="anomaly_v4",
        feature_contract_version="features_v2",
        frame_id="frame_91",
        unknowns=("cause_of_behavior_change",),
        evidence_refs=tuple(
            f"evidence://anomaly_17/2/features/{item.feature_name}"
            for item in changed_features
        ),
    )


def _entry(
    entry_id: str,
    description: str,
    *,
    status: str = "active",
    effective_from: datetime | None = None,
    effective_until: datetime | None = None,
    context_kind: str = "routine",
) -> MemoryEntry:
    retired = status == "retired"
    return MemoryEntry(
        entry_id=entry_id,
        description=description,
        source_feedback_id=None,
        status=status,
        created_by="operator_1",
        created_at=_NOW - timedelta(days=30),
        retired_by="operator_2" if retired else None,
        retired_at=_NOW - timedelta(days=1) if retired else None,
        retirement_reason="no longer relevant" if retired else None,
        source_kind="operator",
        context_kind=context_kind,
        effective_from=effective_from,
        effective_until=effective_until,
    )


def _memory() -> ResidentMemory:
    return ResidentMemory(
        resident_id="resident_42",
        version=8,
        entries=(
            _entry("memory_current", "Usually walks in the room at this time."),
            _entry(
                "memory_expired",
                "An old temporary routine that is no longer relevant.",
                effective_until=_NOW - timedelta(seconds=1),
            ),
            _entry(
                "memory_future",
                "A future routine that has not started.",
                effective_from=_NOW + timedelta(days=1),
            ),
            _entry(
                "memory_retired",
                "A retired and unrelated resident note.",
                status="retired",
            ),
        ),
    )


def _request(*, urgent: bool = False, packet: EvidencePacket | None = None):
    return build_interpretation_request(
        packet or _packet(),
        _memory(),
        model_id="fake-monitoring-model",
        model_version="fake-v1",
        urgent_deterministic_event=urgent,
    )


def _valid_result(request) -> InterpretationResult:
    return InterpretationResult(
        interpretation_id="interpretation_1",
        anomaly_id=request.anomaly_id,
        packet_revision=request.packet_revision,
        status=InterpretationStatus.COMPLETE,
        likely_explanation="unusual_movement_pattern",
        confidence=0.4,
        alternatives=(
            ai_client.InterpretationAlternative(
                rank=1,
                label="routine_movement",
                confidence=0.2,
                supporting_evidence_refs=request.available_evidence_refs,
                contradicting_evidence_refs=(),
            ),
        ),
        uncertainty="The cause cannot be determined from the available evidence.",
        plain_english_summary="The available evidence shows a change, but not its cause.",
        supporting_evidence_refs=request.available_evidence_refs,
        contradicting_evidence_refs=(),
        described_measurements=request.available_measurements,
        addressed_contradictions=request.contradictions,
        missing_information=request.required_missing_information,
        limitations=request.required_limitations,
        unsupported_conclusions=("medical_cause",),
        needs_more_observation=True,
        caregiver_wording="Review the objective evidence and its limitations.",
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


def test_movement_evidence_selects_only_core_and_movement_skills() -> None:
    # Break caught: broad movement evidence is routed to an unrelated interpreter.
    bundle = select_skill_bundle(_packet("movement"))

    assert bundle.skill_names == ("core", "movement")


def test_ambiguous_presence_adds_multi_person_without_replacing_primary_skill() -> None:
    # Break caught: attribution ambiguity is ignored or becomes a second primary call.
    bundle = select_skill_bundle(
        _packet(
            "movement",
            contradictions=(
                "presence_state:radar=resident_present,thermal=possible_multi_person",
            ),
        )
    )

    assert bundle.skill_names == ("core", "movement", "multi_person")


def test_unclassified_evidence_uses_unknown_anomaly_skill() -> None:
    # Break caught: unfamiliar evidence is forced into a known semantic cause.
    bundle = select_skill_bundle(_packet("ambient_temperature"))

    assert bundle.skill_names == ("core", "unknown_anomaly")


def test_skill_loader_rejects_unregistered_names_and_path_traversal() -> None:
    # Break caught: a caller can load arbitrary files by supplying a path-like skill name.
    with pytest.raises(ValueError, match="unknown monitoring skill"):
        load_skill("../core")
    with pytest.raises(ValueError, match="unknown monitoring skill"):
        load_skill("not_registered")


def test_request_serialization_is_bounded_versioned_and_uses_relevant_memory() -> None:
    # Break caught: prompts leak raw/history data or lose replay-critical version metadata.
    request = _request(
        packet=_packet(
            "none",
            overall_strength=None,
            missing_initiating_features=("movement",),
            evidence_limited=True,
        )
    )
    payload = json.loads(request.to_json())
    serialized = request.to_json()

    assert payload["anomaly_evidence"]["overall_strength"] is None
    assert payload["anomaly_evidence"]["missing_initiating_features"] == [
        "movement"
    ]
    assert payload["resident_context"]["entries"] == []
    assert "memory_expired" not in serialized
    assert "memory_future" not in serialized
    assert "memory_retired" not in serialized
    assert "raw_sensor" not in serialized
    assert "display_name" not in serialized
    assert request.skill_bundle_version == "monitoring_skills_v1"
    assert request.retrieval_contract_version == "relevant_resident_context_v1"
    assert request.output_schema_version == "monitoring_interpretation_output_v1"
    assert request.prompt_version == "monitoring_interpreter_v1"
    assert request.model_version == "fake-v1"
    assert request.invocation_version == "monitoring_invocation_v1"


def test_fake_provider_is_deterministic_for_replay_and_performs_no_external_setup() -> None:
    # Break caught: replaying an identical request yields provider-dependent output.
    request = _request()
    client = DeterministicFakeLLMClient()

    first = client.interpret(request)
    second = DeterministicFakeLLMClient().interpret(request)

    assert first == second
    assert validate_interpretation(request, first) == first


def test_unknown_interpretation_is_valid() -> None:
    # Break caught: honest uncertainty is rejected in favor of fabricated classification.
    request = _request()
    result = replace(
        _valid_result(request),
        likely_explanation="unknown",
        confidence=0.0,
        alternatives=(),
    )

    assert validate_interpretation(request, result) == result


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    (
        (
            {"supporting_evidence_refs": ("evidence://invented/measurement",)},
            "invented_evidence_ref:evidence://invented/measurement",
        ),
        (
            {"described_measurements": ("movement", "respiratory_rate")},
            "unavailable_measurement_described:respiratory_rate",
        ),
        (
            {
                "likely_explanation": "diagnosed_stroke",
                "confidence": 1.0,
                "plain_english_summary": "The resident definitely had a stroke.",
            },
            "diagnostic_certainty_not_allowed",
        ),
        (
            {"addressed_contradictions": ()},
            "contradiction_omitted:position_state:radar=floor_like,thermal=upright_like",
        ),
        ({"status": "finished"}, "invalid_interpretation_status:finished"),
        (
            {"recommended_disposition": "emergency"},
            "invalid_recommended_disposition:emergency",
        ),
    ),
)
def test_validator_rejects_unsupported_structured_output_with_exact_reason(
    mutation: dict[str, object],
    expected_reason: str,
) -> None:
    # Break caught: unsupported provider output crosses the trusted boundary.
    packet = _packet(
        contradictions=(
            "position_state:radar=floor_like,thermal=upright_like",
        ),
        missing_initiating_features=("respiratory_rate",),
        evidence_limited=True,
    )
    request = _request(packet=packet)
    result = replace(_valid_result(request), **mutation)

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (expected_reason,)


def test_validator_rejects_attempt_to_downgrade_urgent_deterministic_event() -> None:
    # Break caught: provider advice suppresses an already-required urgent caregiver event.
    request = _request(urgent=True)
    result = replace(
        _valid_result(request),
        recommended_disposition=RecommendedDisposition.OBSERVE,
    )

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (
        "urgent_deterministic_event_cannot_be_downgraded",
    )


def test_complete_result_exposes_ranked_evidence_bound_analysis() -> None:
    # Break caught: provider output collapses alternatives and limitations into opaque prose.
    request = _request()
    result = _valid_result(request)

    assert result.alternatives == (
        ai_client.InterpretationAlternative(
            rank=1,
            label="routine_movement",
            confidence=0.2,
            supporting_evidence_refs=(
                "evidence://anomaly_17/2/features/movement",
            ),
            contradicting_evidence_refs=(),
        ),
    )
    assert result.supporting_evidence_refs == (
        "evidence://anomaly_17/2/features/movement",
    )
    assert result.contradicting_evidence_refs == ()
    assert result.missing_information == (
        "cause_of_behavior_change",
        "wifi_csi",
    )
    assert result.limitations == ()
    assert result.unsupported_conclusions == ("medical_cause",)
    assert result.needs_more_observation is True
    assert result.caregiver_wording == (
        "Review the objective evidence and its limitations."
    )
    assert validate_interpretation(request, result) == result


def test_context_retrieval_includes_relevant_typed_routine_and_denies_other_notes() -> None:
    # Break caught: every active note, including unrelated private prose, is sent upstream.
    memory = ResidentMemory(
        resident_id="resident_42",
        version=9,
        entries=(
            _entry(
                "movement_routine",
                "Usually walks through the room in the afternoon.",
            ),
            _entry(
                "private_routine",
                "Receives private family calls on Friday evenings.",
            ),
            _entry(
                "private_general",
                "Private medical and financial family note.",
                context_kind="general_context",
            ),
        ),
    )

    request = build_interpretation_request(
        _packet("movement"),
        memory,
        model_id="fake-monitoring-model",
        model_version="fake-v1",
    )
    payload = json.loads(request.to_json())

    assert payload["resident_context"]["entries"] == [
        {
            "context_kind": "routine",
            "context_ref": "resident-memory://resident_42/9/entries/movement_routine",
            "description": "Usually walks through the room in the afternoon.",
            "entry_id": "movement_routine",
            "flexibility_note": None,
            "local_time_end": None,
            "local_time_start": None,
            "recurrence_note": None,
        }
    ]
    assert "private_routine" not in request.to_json()
    assert "private_general" not in request.to_json()
    assert request.retrieved_context_refs == (
        "resident-memory://resident_42/9/entries/movement_routine",
    )


def test_unknown_anomaly_retrieval_denies_context_without_an_explicit_match_rule() -> None:
    # Break caught: unknown evidence becomes a pretext to forward arbitrary resident history.
    request = _request(packet=_packet("ambient_temperature"))

    assert json.loads(request.to_json())["resident_context"]["entries"] == []
    assert request.retrieved_context_refs == ()


@pytest.mark.parametrize(
    ("field", "forged", "expected_reason"),
    (
        ("anomaly_id", "forged_anomaly", "provenance_mismatch:anomaly_id"),
        ("packet_revision", 99, "provenance_mismatch:packet_revision"),
        ("model_id", "forged_model", "provenance_mismatch:model_id"),
        ("model_version", "forged_v9", "provenance_mismatch:model_version"),
        ("skill_bundle", ("core", "respiration"), "provenance_mismatch:skill_bundle"),
        (
            "skill_bundle_version",
            "forged_skills",
            "provenance_mismatch:skill_bundle_version",
        ),
        ("prompt_version", "forged_prompt", "provenance_mismatch:prompt_version"),
        (
            "invocation_version",
            "forged_invocation",
            "provenance_mismatch:invocation_version",
        ),
        (
            "retrieval_contract_version",
            "forged_retrieval",
            "provenance_mismatch:retrieval_contract_version",
        ),
        (
            "output_schema_version",
            "forged_output",
            "provenance_mismatch:output_schema_version",
        ),
        (
            "relevant_context_version",
            "forged_context",
            "provenance_mismatch:relevant_context_version",
        ),
        (
            "request_fingerprint",
            "0" * 64,
            "provenance_mismatch:request_fingerprint",
        ),
    ),
)
def test_validator_rejects_each_forged_provenance_field(
    field: str,
    forged: object,
    expected_reason: str,
) -> None:
    # Break caught: a result from another request/revision can be accepted for this one.
    request = _request()
    result = replace(_valid_result(request), **{field: forged})

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (expected_reason,)


def test_empty_claim_declarations_cannot_hide_invented_numeric_prose() -> None:
    # Break caught: empty reference/declaration lists are treated as proof prose is safe.
    request = _request()
    result = replace(
        _valid_result(request),
        supporting_evidence_refs=(),
        contradicting_evidence_refs=(),
        described_measurements=(),
        plain_english_summary="Heart rate was 120 bpm.",
    )

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (
        "unsupported_numeric_measurement_claim:heart_rate:120",
    )


@pytest.mark.parametrize(
    "surface",
    (
        "likely_explanation",
        "alternatives",
        "uncertainty",
        "plain_english_summary",
        "missing_information",
        "limitations",
        "unsupported_conclusions",
        "caregiver_wording",
    ),
)
def test_medical_conclusions_are_rejected_on_every_text_surface(
    surface: str,
) -> None:
    # Break caught: a medical conclusion bypasses checks through a secondary text field.
    request = _request()
    if surface == "alternatives":
        mutation = {
            "alternatives": (
                ai_client.InterpretationAlternative(
                    rank=1,
                    label="resident_had_a_stroke",
                    confidence=0.2,
                    supporting_evidence_refs=request.available_evidence_refs,
                    contradicting_evidence_refs=(),
                ),
            )
        }
    elif surface == "missing_information":
        mutation = {
            surface: (*request.required_missing_information, "The resident had a stroke.")
        }
    elif surface in ("limitations", "unsupported_conclusions"):
        mutation = {surface: ("The resident had a stroke.",)}
    else:
        mutation = {surface: "The resident had a stroke."}
    result = replace(_valid_result(request), **mutation)

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == ("direct_medical_conclusion:stroke",)


def test_blank_uncertainty_is_rejected() -> None:
    # Break caught: a provider can omit the required uncertainty statement.
    request = _request()
    result = replace(_valid_result(request), uncertainty="   ")

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == ("blank_uncertainty",)


def test_packet_and_attribution_limitations_cannot_be_omitted() -> None:
    # Break caught: calibration or resident-attribution constraints disappear in output.
    packet = _packet(
        contradictions=(
            "presence_state:radar=resident_present,thermal=possible_multi_person",
        ),
        evidence_limited=True,
        limitations=("calibration_incomplete",),
    )
    request = _request(packet=packet)
    assert request.required_limitations == (
        "calibration_incomplete",
        "resident_attribution_ambiguous",
    )
    result = replace(_valid_result(request), limitations=())

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (
        "required_limitation_omitted:calibration_incomplete",
        "required_limitation_omitted:resident_attribution_ambiguous",
    )


def test_alternative_confidence_rank_and_references_are_validated() -> None:
    # Break caught: an alternative can carry an unbounded score, wrong rank, or invented ref.
    request = _request()
    result = replace(
        _valid_result(request),
        alternatives=(
            ai_client.InterpretationAlternative(
                rank=2,
                label="routine_movement",
                confidence=1.5,
                supporting_evidence_refs=("evidence://invented/alternative",),
                contradicting_evidence_refs=(),
            ),
        ),
    )

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (
        "invalid_alternative_rank:2",
        "invalid_alternative_confidence:2",
        "invented_evidence_ref:evidence://invented/alternative",
    )


def test_caregiver_wording_cannot_describe_an_unavailable_measurement() -> None:
    # Break caught: caregiver-facing prose bypasses unavailable-measurement declarations.
    request = _request(
        packet=_packet(
            "movement",
            missing_initiating_features=("respiratory_rate",),
            evidence_limited=True,
        )
    )
    result = replace(
        _valid_result(request),
        caregiver_wording="Respiratory rate was 18 breaths per minute.",
    )

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (
        "unavailable_numeric_measurement_claim:respiratory_rate:18",
    )
