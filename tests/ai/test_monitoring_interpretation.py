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


def _request(
    *,
    urgent: bool = False,
    packet: EvidencePacket | None = None,
    memory: ResidentMemory | None = None,
    relevant_context_entry_ids: tuple[str, ...] = (),
):
    return build_interpretation_request(
        packet or _packet(),
        memory or _memory(),
        model_id="fake-monitoring-model",
        model_version="fake-v1",
        urgent_deterministic_event=urgent,
        relevant_context_entry_ids=relevant_context_entry_ids,
    )


def _valid_result(request) -> InterpretationResult:
    return InterpretationResult(
        interpretation_id="interpretation_1",
        anomaly_id=request.anomaly_id,
        packet_revision=request.packet_revision,
        status=InterpretationStatus.COMPLETE,
        likely_explanation=ai_client.ExplanationCategory.UNUSUAL_MOVEMENT,
        confidence=0.4,
        alternatives=(
            ai_client.InterpretationAlternative(
                rank=1,
                label=ai_client.ExplanationCategory.ROUTINE_MOVEMENT,
                confidence=0.2,
                supporting_evidence_refs=request.available_evidence_refs,
                contradicting_evidence_refs=(),
            ),
        ),
        uncertainty=ai_client.UncertaintyCategory.CAUSE_NOT_ESTABLISHED,
        plain_english_summary="The evidence supports an unusual movement pattern.",
        supporting_evidence_refs=request.available_evidence_refs,
        contradicting_evidence_refs=(),
        described_measurements=request.available_measurements,
        addressed_contradictions=request.contradictions,
        missing_information=request.required_missing_information,
        limitations=request.required_limitations,
        unsupported_conclusions=request.required_unsupported_conclusions,
        needs_more_observation=True,
        caregiver_wording=(
            "For the unusual movement pattern, observe and review the objective "
            "evidence and declared limitations."
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
        likely_explanation=ai_client.ExplanationCategory.UNKNOWN,
        confidence=0.0,
        alternatives=(),
        plain_english_summary=(
            "The evidence is unusual, but it does not support a specific explanation."
        ),
        caregiver_wording=(
            "For the unclassified anomaly, observe and review the objective evidence "
            "and declared limitations."
        ),
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


@pytest.mark.parametrize(
    ("category", "disposition", "expected_reason"),
    (
        (
            ai_client.ExplanationCategory.ROUTINE_MOVEMENT,
            RecommendedDisposition.NO_ACTION,
            "non_unknown_explanation_requires_supporting_evidence",
        ),
        (
            ai_client.ExplanationCategory.UNKNOWN,
            RecommendedDisposition.OBSERVE,
            "action_recommendation_requires_supporting_evidence",
        ),
    ),
)
def test_factual_explanation_and_action_require_supporting_evidence(
    category: ai_client.ExplanationCategory,
    disposition: RecommendedDisposition,
    expected_reason: str,
) -> None:
    # Break caught: an evidence-free explanation or action crosses the trust boundary.
    request = _request()
    result = replace(
        _valid_result(request),
        likely_explanation=category,
        alternatives=(),
        supporting_evidence_refs=(),
        described_measurements=(),
        plain_english_summary=ai_client.render_plain_english_summary(category),
        recommended_disposition=disposition,
        caregiver_wording=ai_client.render_caregiver_wording(
            category,
            disposition,
        ),
    )

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (expected_reason,)


def test_non_unknown_alternative_requires_its_own_supporting_evidence() -> None:
    # Break caught: a ranked factual alternative borrows unrelated top-level evidence.
    request = _request()
    result = replace(
        _valid_result(request),
        alternatives=(
            ai_client.InterpretationAlternative(
                rank=1,
                label=ai_client.ExplanationCategory.ROUTINE_MOVEMENT,
                confidence=0.2,
                supporting_evidence_refs=(),
                contradicting_evidence_refs=(),
            ),
        ),
    )

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (
        "non_unknown_alternative_requires_supporting_evidence:1",
    )


def test_complete_result_exposes_ranked_evidence_bound_analysis() -> None:
    # Break caught: provider output collapses alternatives and limitations into opaque prose.
    request = _request()
    result = _valid_result(request)

    assert result.alternatives == (
        ai_client.InterpretationAlternative(
            rank=1,
            label=ai_client.ExplanationCategory.ROUTINE_MOVEMENT,
            confidence=0.2,
            supporting_evidence_refs=(
                "evidence://anomaly_17/2/features/movement",
            ),
            contradicting_evidence_refs=(),
        ),
    )
    assert result.likely_explanation == ai_client.ExplanationCategory.UNUSUAL_MOVEMENT
    assert result.uncertainty == ai_client.UncertaintyCategory.CAUSE_NOT_ESTABLISHED
    assert result.supporting_evidence_refs == (
        "evidence://anomaly_17/2/features/movement",
    )
    assert result.contradicting_evidence_refs == ()
    assert result.missing_information == (
        "cause_of_behavior_change",
        "wifi_csi",
    )
    assert result.limitations == ()
    assert result.unsupported_conclusions == (
        "causal_explanation",
        "medical_diagnosis",
        "unobserved_measurement",
    )
    assert result.needs_more_observation is True
    assert result.caregiver_wording == (
        "For the unusual movement pattern, observe and review the objective evidence "
        "and declared limitations."
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
        relevant_context_entry_ids=("movement_routine",),
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


def test_context_retrieval_defaults_to_no_resident_entries() -> None:
    # Break caught: evidence category guesses which private resident notes to forward.
    request = _request(packet=_packet("ambient_temperature"))

    assert json.loads(request.to_json())["resident_context"]["entries"] == []
    assert request.retrieved_context_refs == ()


def test_retirement_account_balance_note_never_leaks_without_explicit_selection() -> None:
    # Break caught: the word "balance" leaks an unrelated financial note into fall context.
    memory = ResidentMemory(
        resident_id="resident_42",
        version=10,
        entries=(
            _entry(
                "retirement_balance",
                "Retirement account balance is 120 thousand dollars.",
            ),
        ),
    )

    request = _request(packet=_packet("height_drop"), memory=memory)

    assert json.loads(request.to_json())["resident_context"]["entries"] == []
    assert "retirement" not in request.to_json().casefold()


def test_explicit_context_ids_are_deduplicated_stably_ordered_and_fingerprinted() -> None:
    # Break caught: duplicate/order variance changes context or escapes the request fingerprint.
    memory = ResidentMemory(
        resident_id="resident_42",
        version=11,
        entries=(
            _entry("routine_b", "Second explicitly selected routine."),
            _entry("routine_a", "First explicitly selected routine."),
        ),
    )

    selected = _request(
        memory=memory,
        relevant_context_entry_ids=("routine_b", "routine_a", "routine_b"),
    )
    no_context = _request(memory=memory)

    assert tuple(
        item["entry_id"]
        for item in json.loads(selected.to_json())["resident_context"]["entries"]
    ) == ("routine_a", "routine_b")
    assert selected.retrieved_context_refs == (
        "resident-memory://resident_42/11/entries/routine_a",
        "resident-memory://resident_42/11/entries/routine_b",
    )
    assert selected.request_fingerprint != no_context.request_fingerprint


@pytest.mark.parametrize(
    ("entry_id", "expected_reason"),
    (
        ("missing", "requested context entry is unknown: missing"),
        (
            "memory_retired",
            "requested context entry is not active/effective: memory_retired",
        ),
        (
            "memory_expired",
            "requested context entry is not active/effective: memory_expired",
        ),
        (
            "memory_future",
            "requested context entry is not active/effective: memory_future",
        ),
        (
            "memory_general",
            "requested context entry uses disallowed context kind: memory_general",
        ),
    ),
)
def test_explicit_context_rejects_invalid_entry_ids(
    entry_id: str,
    expected_reason: str,
) -> None:
    # Break caught: a caller mistake silently forwards or ignores an invalid private note.
    base = _memory()
    memory = replace(
        base,
        entries=(
            *base.entries,
            _entry(
                "memory_general",
                "Private general note.",
                context_kind="general_context",
            ),
        ),
    )

    with pytest.raises(ValueError) as exc_info:
        _request(memory=memory, relevant_context_entry_ids=(entry_id,))

    assert str(exc_info.value) == expected_reason


def test_explicit_context_selection_is_bounded() -> None:
    # Break caught: a caller can turn explicit selection into an unbounded memory dump.
    memory = ResidentMemory(
        resident_id="resident_42",
        version=12,
        entries=tuple(
            _entry(f"routine_{index:02d}", f"Selected routine {index}.")
            for index in range(21)
        ),
    )

    with pytest.raises(ValueError) as exc_info:
        _request(
            memory=memory,
            relevant_context_entry_ids=tuple(
                f"routine_{index:02d}" for index in range(21)
            ),
        )

    assert str(exc_info.value) == "relevant_context_entry_ids exceeds 20 entries"


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
        ("schema_version", "999", "provenance_mismatch:schema_version"),
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


def test_provider_cannot_override_deterministic_summary_with_pulse_claim() -> None:
    # Break caught: arbitrary provider prose crosses into caregiver-facing output.
    request = _request()
    result = replace(
        _valid_result(request),
        contradicting_evidence_refs=(),
        described_measurements=(),
        plain_english_summary="Pulse was 120 bpm.",
    )

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == ("plain_english_summary_mismatch",)


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
                label=ai_client.ExplanationCategory.ROUTINE_MOVEMENT,
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


def test_provider_cannot_override_deterministic_caregiver_wording() -> None:
    # Break caught: arbitrary provider prose crosses into caregiver guidance.
    request = _request(
        packet=_packet(
            "movement",
            missing_initiating_features=("respiratory_rate",),
            evidence_limited=True,
        )
    )
    result = replace(
        _valid_result(request),
        caregiver_wording="Pulse was 120 bpm.",
    )

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == ("caregiver_wording_mismatch",)


def test_malformed_alternative_is_rejected_without_dereferencing_it() -> None:
    # Break caught: malformed untrusted alternatives crash validation with AttributeError.
    request = _request()
    result = replace(_valid_result(request), alternatives=("not-structured",))

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == ("invalid_alternative_structure:1",)


@pytest.mark.parametrize("surface", ("likely", "alternative"))
def test_pneumonia_is_rejected_as_an_uncontrolled_category(surface: str) -> None:
    # Break caught: arbitrary diagnostic prose enters through an open-ended category label.
    request = _request()
    if surface == "likely":
        result = replace(_valid_result(request), likely_explanation="pneumonia")
        expected = "invalid_explanation_category:pneumonia"
    else:
        result = replace(
            _valid_result(request),
            alternatives=(
                ai_client.InterpretationAlternative(
                    rank=1,
                    label="pneumonia",
                    confidence=0.2,
                    supporting_evidence_refs=request.available_evidence_refs,
                    contradicting_evidence_refs=(),
                ),
            ),
        )
        expected = "invalid_alternative_category:1:pneumonia"

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (expected,)


def test_hidden_text_in_addressed_contradictions_is_rejected_as_undeclared() -> None:
    # Break caught: an exact-reference field becomes an arbitrary hidden-text channel.
    request = _request()
    result = replace(
        _valid_result(request),
        addressed_contradictions=("resident_had_pneumonia",),
    )

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (
        "undeclared_contradiction:resident_had_pneumonia",
    )


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    (
        ({"likely_explanation": ""}, "blank_likely_explanation"),
        ({"plain_english_summary": "   "}, "blank_plain_english_summary"),
        ({"caregiver_wording": ""}, "blank_caregiver_wording"),
        ({"uncertainty": "free prose"}, "invalid_uncertainty_category:free prose"),
    ),
)
def test_required_controlled_fields_reject_blank_or_free_prose(
    mutation: dict[str, object],
    expected_reason: str,
) -> None:
    # Break caught: a required semantic/template field is blank or arbitrary provider prose.
    request = _request()
    result = replace(_valid_result(request), **mutation)

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (expected_reason,)


def test_blank_alternative_label_is_rejected() -> None:
    # Break caught: a ranked alternative can exist without a controlled explanation.
    request = _request()
    result = replace(
        _valid_result(request),
        alternatives=(
            ai_client.InterpretationAlternative(
                rank=1,
                label="   ",
                confidence=0.2,
                supporting_evidence_refs=request.available_evidence_refs,
                contradicting_evidence_refs=(),
            ),
        ),
    )

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == ("blank_alternative_label:1",)


@pytest.mark.parametrize(
    ("field", "extra", "expected_reason"),
    (
        (
            "missing_information",
            "private_extra",
            "undeclared_missing_information:private_extra",
        ),
        ("limitations", "private_extra", "undeclared_limitation:private_extra"),
        (
            "unsupported_conclusions",
            "pneumonia",
            "unsupported_conclusion_not_allowed:pneumonia",
        ),
        (
            "unsupported_conclusions",
            "person_identity",
            "undeclared_unsupported_conclusion:person_identity",
        ),
    ),
)
def test_declared_identifier_fields_reject_extras(
    field: str,
    extra: str,
    expected_reason: str,
) -> None:
    # Break caught: declared-identifier tuples become arbitrary provider text channels.
    request = _request()
    current = getattr(_valid_result(request), field)
    result = replace(_valid_result(request), **{field: (*current, extra)})

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (expected_reason,)


@pytest.mark.parametrize(
    ("field", "expected_reason"),
    (
        (
            "missing_information",
            "required_missing_information_omitted:cause_of_behavior_change",
        ),
        (
            "unsupported_conclusions",
            "required_unsupported_conclusion_omitted:causal_explanation",
        ),
    ),
)
def test_declared_identifier_fields_reject_omissions(
    field: str,
    expected_reason: str,
) -> None:
    # Break caught: required unknown/unsupported declarations disappear from output.
    request = _request()
    current = getattr(_valid_result(request), field)
    result = replace(_valid_result(request), **{field: current[1:]})

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (expected_reason,)


def test_context_snapshot_rejects_active_and_retired_duplicate_entry_ids() -> None:
    # Break caught: a retired duplicate overwrites an active entry during authorization.
    memory = ResidentMemory(
        resident_id="resident_42",
        version=13,
        entries=(
            _entry("duplicate_routine", "Active movement routine."),
            _entry(
                "duplicate_routine",
                "Retired private replacement.",
                status="retired",
            ),
        ),
    )

    with pytest.raises(ValueError) as exc_info:
        _request(
            memory=memory,
            relevant_context_entry_ids=("duplicate_routine",),
        )

    assert str(exc_info.value) == (
        "resident memory contains duplicate entry_id: duplicate_routine"
    )


@pytest.mark.parametrize(
    ("field", "malformed", "expected_reason"),
    (
        ("alternatives", None, "invalid_alternatives_shape"),
        (
            "supporting_evidence_refs",
            None,
            "invalid_supporting_evidence_refs_shape",
        ),
        (
            "contradicting_evidence_refs",
            None,
            "invalid_contradicting_evidence_refs_shape",
        ),
        (
            "described_measurements",
            None,
            "invalid_described_measurements_shape",
        ),
        (
            "addressed_contradictions",
            None,
            "invalid_addressed_contradictions_shape",
        ),
        (
            "missing_information",
            None,
            "invalid_missing_information_shape",
        ),
        ("limitations", None, "invalid_limitations_shape"),
        (
            "unsupported_conclusions",
            None,
            "invalid_unsupported_conclusions_shape",
        ),
        ("skill_bundle", None, "invalid_skill_bundle_shape"),
    ),
)
def test_untrusted_result_container_shapes_are_rejected_deterministically(
    field: str,
    malformed: object,
    expected_reason: str,
) -> None:
    # Break caught: None or a non-tuple reaches iteration, unpacking, or set().
    request = _request()
    result = replace(_valid_result(request), **{field: malformed})

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (expected_reason,)


@pytest.mark.parametrize(
    ("field", "malformed", "expected_reason"),
    (
        ("interpretation_id", None, "invalid_interpretation_id_type"),
        ("plain_english_summary", None, "invalid_plain_english_summary_type"),
        ("caregiver_wording", None, "invalid_caregiver_wording_type"),
        ("likely_explanation", None, "invalid_likely_explanation_type"),
        ("uncertainty", None, "invalid_uncertainty_type"),
        ("status", None, "invalid_interpretation_status_type"),
        (
            "recommended_disposition",
            None,
            "invalid_recommended_disposition_type",
        ),
        ("confidence", "high", "invalid_interpretation_confidence"),
        ("needs_more_observation", None, "invalid_needs_more_observation"),
        ("model_id", None, "invalid_model_id_type"),
    ),
)
def test_untrusted_result_scalar_shapes_are_rejected_deterministically(
    field: str,
    malformed: object,
    expected_reason: str,
) -> None:
    # Break caught: a malformed scalar reaches strip(), enum conversion, or provenance use.
    request = _request()
    result = replace(_valid_result(request), **{field: malformed})

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (expected_reason,)


@pytest.mark.parametrize(
    ("field", "expected_reason"),
    (
        (
            "supporting_evidence_refs",
            "invalid_alternative_supporting_evidence_refs_shape:1",
        ),
        (
            "contradicting_evidence_refs",
            "invalid_alternative_contradicting_evidence_refs_shape:1",
        ),
    ),
)
def test_nested_alternative_reference_shapes_are_rejected_deterministically(
    field: str,
    expected_reason: str,
) -> None:
    # Break caught: malformed nested references are unpacked after the outer type check.
    request = _request()
    alternative = replace(
        _valid_result(request).alternatives[0],
        **{field: None},
    )
    result = replace(_valid_result(request), alternatives=(alternative,))

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (expected_reason,)


def test_blank_interpretation_id_is_rejected() -> None:
    # Break caught: an accepted interpretation cannot be durably identified.
    request = _request()

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(
            request,
            replace(_valid_result(request), interpretation_id="   "),
        )

    assert exc_info.value.reasons == ("blank_interpretation_id",)


@pytest.mark.parametrize(
    ("field", "malformed", "expected_reason"),
    (
        (
            "addressed_contradictions",
            (None,),
            "invalid_addressed_contradictions_item:1",
        ),
        (
            "missing_information",
            ("cause_of_behavior_change", "   "),
            "blank_missing_information_item:2",
        ),
        (
            "limitations",
            (7,),
            "invalid_limitations_item:1",
        ),
        (
            "unsupported_conclusions",
            ("causal_explanation", "medical_diagnosis", ""),
            "blank_unsupported_conclusions_item:3",
        ),
        (
            "supporting_evidence_refs",
            (None,),
            "invalid_supporting_evidence_refs_item:1",
        ),
        (
            "described_measurements",
            ("   ",),
            "blank_described_measurements_item:1",
        ),
    ),
)
def test_declared_tuples_require_nonblank_string_items(
    field: str,
    malformed: tuple[object, ...],
    expected_reason: str,
) -> None:
    # Break caught: an identifier tuple carries a non-string or hidden blank item.
    request = _request()
    result = replace(_valid_result(request), **{field: malformed})

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (expected_reason,)


@pytest.mark.parametrize(
    ("field", "request_kwargs", "expected_reason"),
    (
        (
            "addressed_contradictions",
            {"packet": _packet(contradictions=("sensor_conflict",))},
            "duplicate_addressed_contradiction:sensor_conflict",
        ),
        (
            "missing_information",
            {},
            "duplicate_missing_information:cause_of_behavior_change",
        ),
        (
            "limitations",
            {"packet": _packet(limitations=("calibration_incomplete",))},
            "duplicate_limitation:calibration_incomplete",
        ),
        (
            "unsupported_conclusions",
            {},
            "duplicate_unsupported_conclusion:causal_explanation",
        ),
        (
            "supporting_evidence_refs",
            {},
            "duplicate_supporting_evidence_ref:evidence://anomaly_17/2/features/movement",
        ),
        (
            "contradicting_evidence_refs",
            {},
            "duplicate_contradicting_evidence_ref:evidence://anomaly_17/2/features/movement",
        ),
        (
            "described_measurements",
            {},
            "duplicate_described_measurement:movement",
        ),
    ),
)
def test_semantic_declaration_tuples_reject_duplicates(
    field: str,
    request_kwargs: dict[str, object],
    expected_reason: str,
) -> None:
    # Break caught: set-based comparison silently normalizes duplicate declarations.
    request = _request(**request_kwargs)
    valid = _valid_result(request)
    current = getattr(valid, field)
    if not current:
        current = request.available_evidence_refs
    result = replace(valid, **{field: (*current, current[0])})

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (expected_reason,)


@pytest.mark.parametrize(
    ("field", "expected_reason"),
    (
        (
            "supporting_evidence_refs",
            "duplicate_alternative_supporting_evidence_ref:1:"
            "evidence://anomaly_17/2/features/movement",
        ),
        (
            "contradicting_evidence_refs",
            "duplicate_alternative_contradicting_evidence_ref:1:"
            "evidence://anomaly_17/2/features/movement",
        ),
    ),
)
def test_alternative_reference_tuples_reject_duplicates(
    field: str,
    expected_reason: str,
) -> None:
    # Break caught: duplicate evidence citations inflate a ranked alternative.
    request = _request()
    refs = (*request.available_evidence_refs, *request.available_evidence_refs)
    alternative = replace(
        _valid_result(request).alternatives[0],
        **{field: refs},
    )
    result = replace(_valid_result(request), alternatives=(alternative,))

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == (expected_reason,)


def test_huge_integer_top_level_confidence_is_rejected_without_overflow() -> None:
    # Break caught: float conversion overflows before the trust boundary can reject JSON int.
    request = _request()
    result = replace(_valid_result(request), confidence=10**400)

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == ("invalid_interpretation_confidence",)


def test_huge_integer_alternative_confidence_is_rejected_without_overflow() -> None:
    # Break caught: a huge alternative score escapes as raw OverflowError.
    request = _request()
    alternative = replace(
        _valid_result(request).alternatives[0],
        confidence=10**400,
    )
    result = replace(_valid_result(request), alternatives=(alternative,))

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == ("invalid_alternative_confidence:1",)


@pytest.mark.parametrize("confidence", (0, 1, 0.0, 0.5, 1.0))
def test_finite_in_range_integer_and_float_confidence_is_accepted(
    confidence: int | float,
) -> None:
    # Break caught: overflow hardening accidentally narrows valid bounded numeric scores.
    request = _request()
    result = replace(_valid_result(request), confidence=confidence)

    assert validate_interpretation(request, result) is result


@pytest.mark.parametrize(
    "confidence",
    (False, True, -1, 2, -0.1, 1.1, float("nan"), float("inf"), -float("inf")),
)
def test_bool_out_of_range_and_nonfinite_confidence_is_rejected(
    confidence: object,
) -> None:
    # Break caught: the confidence helper admits bools, out-of-range values, NaN, or infinity.
    request = _request()
    result = replace(_valid_result(request), confidence=confidence)

    with pytest.raises(InterpretationValidationError) as exc_info:
        validate_interpretation(request, result)

    assert exc_info.value.reasons == ("invalid_interpretation_confidence",)
