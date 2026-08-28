from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.ai.client import (
    DeterministicFakeLLMClient,
)
from backend.app.ai.validation import InterpretationValidationError
from backend.app.ai.context import build_interpretation_request
from backend.app.db.base import Base
from backend.app.db.intelligence_mappers import (
    DispositionRecord,
    anomaly_from_row,
    anomaly_to_row,
    canonical_json,
    disposition_from_row,
    disposition_to_row,
    event_bridge_from_row,
    event_bridge_to_row,
    interpretation_from_row,
    interpretation_to_row,
)
from backend.app.db.intelligence_repositories import IntelligenceRepository
from backend.app.db.models import (
    AnomalyRevisionRow,
    BaselineDimensionRow,
    BaselineSnapshotRow,
    DispositionDecisionRow,
    EventBridgeRecordRow,
    LLMInterpretationRow,
    MonitoringEventRow,
    ResidentRow,
    RoomRow,
    TenantRow,
)
from backend.app.db.repositories import EventRepository, FeedbackRepository
from backend.app.db.seed import seed_synthetic_story
from backend.app.db.session import create_engine_for_url
from backend.app.domain.events import (
    BridgeEvidenceKind,
    EventBridgeRecord,
    EventPriority,
    EventStore,
)
from backend.app.domain.feedback import MemoryEntry, ResidentMemory
from backend.app.intelligence.anomaly import (
    AnomalyEpisode,
    AnomalyState,
    AnomalyUpdate,
    FeatureDeviation,
)
from backend.app.intelligence.baseline import BaselineSnapshot, FeatureBaseline
from backend.app.intelligence.evidence import EvidencePacket, build_evidence_packet
from backend.app.intelligence.observations import FeaturePurpose, QualityClass
from backend.app.intelligence.policy import (
    DispositionDecision,
    PolicyDisposition,
)
from backend.app.intelligence.orchestration import MonitoringIntelligenceEngine
from backend.app.services.errors import ConcurrentUpdateError
from tests.intelligence.test_policy_orchestration import (
    _baseline as _fall_baseline,
    _fall_sequence,
    _process as _process_fall_frame,
)


AT = datetime(2026, 8, 28, 16, 0, tzinfo=timezone.utc)


@pytest.fixture
def session() -> Session:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        seed_synthetic_story(database_session)
        yield database_session
    engine.dispose()


def _baseline(
    baseline_id: str = "baseline_intelligence_1",
    *,
    median: float = 0.2,
) -> BaselineSnapshot:
    return BaselineSnapshot(
        baseline_id=baseline_id,
        resident_id="resident_demo_a",
        monitoring_setup_version="setup_room_214_v3",
        features=(
            FeatureBaseline(
                feature_name="movement",
                purpose=FeaturePurpose.MOVEMENT,
                median=median,
                mad=0.1,
                iqr=0.2,
                lower_quantile=0.05,
                upper_quantile=0.4,
                resolution_floor=0.01,
                unit="normalized",
                eligible_sample_count=18,
                context_key="resident_global",
            ),
        ),
        policy_version="synthetic_baseline_v1",
        prior_baseline_id="baseline_intelligence_0",
        adoption_candidate_id="candidate_new_normal_1",
        adoption_context_entry_id="memory_expected_change_1",
    )


def _anomaly_revision(
    baseline: BaselineSnapshot,
    revision: int = 1,
) -> tuple[AnomalyUpdate, EvidencePacket]:
    episode = AnomalyEpisode(
        anomaly_id="anomaly_intelligence_1",
        state=AnomalyState.ACTIVE,
        candidate_started_at=AT,
        current_time=AT + timedelta(seconds=revision + 2),
        activation_count=3,
        recovery_count=0,
        consecutive_missing_frames=0,
        related_frame_count=revision + 2,
        packet_revision=revision,
        initiating_features=("movement",),
        policy_version="synthetic_anomaly_v1",
        last_frame_id=f"frame_{revision}",
        activated_at=AT + timedelta(seconds=2),
    )
    update = AnomalyUpdate(
        episode=episode,
        deviations=(
            FeatureDeviation(
                feature_name="movement",
                source="radar",
                observation_id=f"observation_{revision}",
                value=0.8 + revision / 100,
                unit="normalized",
                quality_class=QualityClass.GOOD,
                quality_reasons=(),
                baseline_median=0.2,
                baseline_mad=0.1,
                baseline_iqr=0.2,
                baseline_lower_quantile=0.05,
                baseline_upper_quantile=0.4,
                baseline_resolution_floor=0.01,
                baseline_context_key="resident_global",
                robust_z=6.0 + revision / 10,
                direction="up",
                trajectory="sustained",
                persistence_frames=revision + 2,
            ),
        ),
        resident_id="resident_demo_a",
        room_id="room_214",
        frame_id=f"frame_{revision}",
        window_start=episode.current_time - timedelta(seconds=1),
        window_end=episode.current_time,
        agreements=("movement:radar=thermal",),
        contradictions=(),
        missing_sources=("csi",),
        missing_initiating_features=(),
        feature_contract_version="normalized_features_v1",
        baseline_id=baseline.baseline_id,
        baseline_policy_version=baseline.policy_version,
        monitoring_setup_version=baseline.monitoring_setup_version,
        context_key="resident_global",
        filter_version="synthetic_anomaly_v1",
        config_version="synthetic_config_v1",
        unknowns=("cause_of_behavior_change",),
        evidence_limited=False,
        limitations=("csi_unavailable",),
    )
    return update, build_evidence_packet(update)


def _interpretation(
    packet: EvidencePacket,
    memory: ResidentMemory | None = None,
    selected_entry_ids: tuple[str, ...] = (),
):
    request = build_interpretation_request(
        packet,
        memory or ResidentMemory(packet.resident_id, 0, ()),
        model_id="fake_provider",
        model_version="fake_model_v2",
        relevant_context_entry_ids=selected_entry_ids,
    )
    return request, DeterministicFakeLLMClient().interpret(request)


def _store_baseline_and_anomaly(
    repository: IntelligenceRepository,
) -> tuple[BaselineSnapshot, AnomalyUpdate, EvidencePacket]:
    baseline = _baseline()
    repository.save_baseline("tenant_demo", baseline, AT)
    update, packet = _anomaly_revision(baseline)
    repository.save_anomaly_revision("tenant_demo", update, packet)
    return baseline, update, packet


def _persist_packet_event(
    session: Session,
    packet: EvidencePacket,
    decision: DispositionDecision,
    *,
    observed_at: datetime | None = None,
) -> object:
    observed_at = observed_at or packet.current_time
    event = EventStore().record_signal(
        resident_id=packet.resident_id,
        room_id=packet.room_id,
        objective_family=decision.objective_family,
        headline=decision.headline,
        priority=decision.priority,
        observed_at=observed_at,
        source_anomaly_id=packet.anomaly_id,
        evidence_revision=packet.packet_revision,
        bridge_idempotency_key=(
            f"{packet.anomaly_id}:{packet.packet_revision}:{decision.policy_version}"
        ),
        provisional_urgent=decision.provisional_urgent,
        evidence_kind=BridgeEvidenceKind.PACKET,
        room_level_only=decision.room_level_only,
    )
    EventRepository(session).save("tenant_demo", event, expected_version=0)
    return event


def test_baseline_round_trip_latest_tenant_scope_and_immutable_identity(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    first = _baseline()
    second = replace(
        _baseline("baseline_intelligence_2", median=0.25),
        prior_baseline_id=first.baseline_id,
    )

    assert repository.save_baseline("tenant_demo", first, AT) == first
    assert repository.save_baseline("tenant_demo", first, AT) == first
    repository.save_baseline("tenant_demo", second, AT + timedelta(minutes=1))

    assert repository.latest_baseline("tenant_demo", "resident_demo_a") == second
    assert repository.latest_baseline("tenant_other", "resident_demo_a") is None
    with pytest.raises(ConcurrentUpdateError):
        repository.save_baseline(
            "tenant_demo",
            replace(first, policy_version="synthetic_baseline_v2"),
            AT,
        )


def test_baseline_hydration_rejects_shadow_column_tampering(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    baseline = _baseline()
    repository.save_baseline("tenant_demo", baseline, AT)
    row = session.get(
        BaselineSnapshotRow,
        ("tenant_demo", baseline.baseline_id),
    )
    assert row is not None
    row.policy_version = "tampered_policy"
    session.commit()
    session.expire_all()

    with pytest.raises(ConcurrentUpdateError):
        repository.latest_baseline("tenant_demo", baseline.resident_id)


def test_baseline_hydration_rejects_deleted_dimension(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    baseline = _baseline()
    repository.save_baseline("tenant_demo", baseline, AT)
    dimension = session.scalar(select(BaselineDimensionRow))
    session.delete(dimension)
    session.flush()

    with pytest.raises(ConcurrentUpdateError, match="manifest"):
        repository.latest_baseline("tenant_demo", baseline.resident_id)


def test_baseline_hydration_rejects_noncanonical_whitespace(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    baseline = _baseline()
    repository.save_baseline("tenant_demo", baseline, AT)
    row = session.get(
        BaselineSnapshotRow,
        ("tenant_demo", baseline.baseline_id),
    )
    row.payload_json = f" {row.payload_json}"
    session.flush()

    with pytest.raises(ConcurrentUpdateError, match="manifest|canonical"):
        repository.latest_baseline("tenant_demo", baseline.resident_id)


def test_baseline_hydration_rejects_extra_dimension_payload_key(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    baseline = _baseline()
    repository.save_baseline("tenant_demo", baseline, AT)
    dimension = session.scalar(select(BaselineDimensionRow))
    payload = json.loads(dimension.payload_json)
    payload["feature"]["unexpected"] = "tampered"
    dimension.payload_json = canonical_json(payload)
    session.flush()

    with pytest.raises(ConcurrentUpdateError, match="manifest|canonical"):
        repository.latest_baseline("tenant_demo", baseline.resident_id)
    with pytest.raises(ConcurrentUpdateError):
        repository.save_baseline("tenant_demo", baseline, AT)


def test_intelligence_logical_ids_are_independent_per_tenant(
    session: Session,
) -> None:
    session.add(TenantRow(tenant_id="tenant_other"))
    session.flush()
    session.add_all(
        (
            ResidentRow(
                resident_id="resident_other",
                tenant_id="tenant_other",
                display_label="Resident Other",
            ),
            RoomRow(
                room_id="room_other",
                tenant_id="tenant_other",
                label="Room Other",
            ),
        )
    )
    session.flush()
    repository = IntelligenceRepository(session)
    first_baseline = _baseline()
    other_baseline = replace(first_baseline, resident_id="resident_other")

    repository.save_baseline("tenant_demo", first_baseline, AT)
    repository.save_baseline("tenant_other", other_baseline, AT)

    first_update, first_packet = _anomaly_revision(first_baseline)
    other_update = replace(
        first_update,
        resident_id="resident_other",
        room_id="room_other",
    )
    other_packet = build_evidence_packet(other_update)
    repository.save_anomaly_revision("tenant_demo", first_update, first_packet)
    repository.save_anomaly_revision("tenant_other", other_update, other_packet)
    first_request, first_result = _interpretation(first_packet)
    other_request, other_result = _interpretation(other_packet)
    other_result = replace(
        other_result,
        interpretation_id=first_result.interpretation_id,
    )
    assert first_result.interpretation_id == other_result.interpretation_id
    repository.save_interpretation(
        "tenant_demo", first_request, first_result, first_packet.current_time
    )
    repository.save_interpretation(
        "tenant_other", other_request, other_result, other_packet.current_time
    )

    decision = DispositionDecision(
        disposition=PolicyDisposition.OBSERVE,
        priority=None,
        confidence="interpreted",
        objective_family="unusual_movement",
        headline="Observe",
        reasons=("validated_interpretation",),
        policy_version="synthetic_disposition_v1",
        fallback_used=False,
        room_level_only=False,
        interpretation_id=first_result.interpretation_id,
    )
    first_disposition = DispositionRecord(
        disposition_id="disposition_shared",
        resident_id="resident_demo_a",
        room_id="room_214",
        anomaly_id=first_packet.anomaly_id,
        evidence_kind=BridgeEvidenceKind.PACKET,
        evidence_revision=1,
        packet_revision=1,
        decided_at=first_packet.current_time,
        decision=decision,
        interpretation_id=first_result.interpretation_id,
    )
    other_disposition = replace(
        first_disposition,
        resident_id="resident_other",
        room_id="room_other",
        decided_at=other_packet.current_time,
    )
    repository.save_disposition("tenant_demo", first_disposition)
    repository.save_disposition("tenant_other", other_disposition)

    assert repository.latest_baseline(
        "tenant_demo", "resident_demo_a"
    ) == first_baseline
    assert repository.latest_baseline(
        "tenant_other", "resident_other"
    ) == other_baseline
    assert repository.find_interpretation(
        "tenant_demo", first_result.interpretation_id
    ).result == first_result
    assert repository.find_interpretation(
        "tenant_other", other_result.interpretation_id
    ).result == other_result
    assert repository.find_disposition(
        "tenant_demo", "disposition_shared"
    ) == first_disposition
    assert repository.find_disposition(
        "tenant_other", "disposition_shared"
    ) == other_disposition


def test_baseline_insert_race_reconciles_without_poisoning_session(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = IntelligenceRepository(session)
    baseline = _baseline()
    repository.save_baseline("tenant_demo", baseline, AT)
    session.commit()
    session.expunge_all()
    real_get = session.get
    baseline_get_count = 0

    def stale_get(entity, identity, *args, **kwargs):
        nonlocal baseline_get_count
        if entity is BaselineSnapshotRow:
            baseline_get_count += 1
            if baseline_get_count in {1, 3}:
                return None
        return real_get(entity, identity, *args, **kwargs)

    monkeypatch.setattr(session, "get", stale_get)

    assert repository.save_baseline("tenant_demo", baseline, AT) == baseline
    session.expunge_all()
    with pytest.raises(ConcurrentUpdateError):
        repository.save_baseline(
            "tenant_demo",
            replace(baseline, policy_version="policy_changed"),
            AT,
        )
    session.commit()
    assert repository.latest_baseline(
        "tenant_demo", baseline.resident_id
    ) == baseline


def test_canonical_json_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValueError):
        canonical_json({"not_a_number": float("nan")})


def test_anomaly_hydration_rejects_noncanonical_json() -> None:
    update, packet = _anomaly_revision(_baseline())
    row = anomaly_to_row("tenant_demo", update, packet)
    row.update_json = f" {row.update_json}"

    with pytest.raises(ConcurrentUpdateError, match="canonical"):
        anomaly_from_row(row)


def test_interpretation_hydration_rejects_extra_json_key() -> None:
    _, packet = _anomaly_revision(_baseline())
    request, result = _interpretation(packet)
    row = interpretation_to_row("tenant_demo", request, result, AT)
    payload = json.loads(row.result_json)
    payload["unexpected"] = True
    row.result_json = canonical_json(payload)

    with pytest.raises(ConcurrentUpdateError, match="canonical"):
        interpretation_from_row(row)


def test_disposition_hydration_rejects_extra_json_key() -> None:
    record = DispositionRecord(
        disposition_id="disposition_strict_json",
        resident_id="resident_demo_a",
        room_id="room_214",
        anomaly_id="anomaly_intelligence_1",
        evidence_kind=BridgeEvidenceKind.PACKET,
        evidence_revision=1,
        packet_revision=1,
        decided_at=AT,
        decision=DispositionDecision(
            disposition=PolicyDisposition.OBSERVE,
            priority=None,
            confidence="objective_only",
            objective_family="unknown_anomaly",
            headline="Observe",
            reasons=("objective_fallback",),
            policy_version="synthetic_disposition_v1",
            fallback_used=True,
            room_level_only=False,
        ),
    )
    row = disposition_to_row("tenant_demo", record)
    payload = json.loads(row.payload_json)
    payload["unexpected"] = True
    row.payload_json = canonical_json(payload)

    with pytest.raises(ConcurrentUpdateError, match="canonical"):
        disposition_from_row(row)


def test_bridge_hydration_rejects_noncanonical_json() -> None:
    bridge = EventBridgeRecord(
        idempotency_key="strict-bridge",
        resident_id="resident_demo_a",
        room_id="room_214",
        source_anomaly_id="anomaly_intelligence_1",
        evidence_revision=1,
        evidence_kind=BridgeEvidenceKind.PACKET,
        objective_family="unknown_anomaly",
        headline="Observe",
        priority=EventPriority.WATCH,
        provisional_urgent=False,
        room_level_only=False,
        observed_at=AT,
        actor_id="system:monitoring_event",
    )
    row = event_bridge_to_row("tenant_demo", "event_strict", bridge)
    row.payload_json = f"{row.payload_json}\n"

    with pytest.raises(ConcurrentUpdateError, match="canonical"):
        event_bridge_from_row(row)


def test_anomaly_revisions_append_and_changed_duplicate_conflicts(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    baseline = _baseline()
    repository.save_baseline("tenant_demo", baseline, AT)
    update_1, packet_1 = _anomaly_revision(baseline, 1)
    update_2, packet_2 = _anomaly_revision(baseline, 2)

    first = repository.save_anomaly_revision("tenant_demo", update_1, packet_1)
    assert repository.save_anomaly_revision(
        "tenant_demo", update_1, packet_1
    ) == first
    second = repository.save_anomaly_revision("tenant_demo", update_2, packet_2)

    row = session.scalar(
        select(AnomalyRevisionRow).where(
            AnomalyRevisionRow.tenant_id == "tenant_demo",
            AnomalyRevisionRow.anomaly_id == "anomaly_intelligence_1",
            AnomalyRevisionRow.packet_revision == 2,
        )
    )
    assert row is not None
    assert row.packet_json == json.dumps(
        json.loads(row.packet_json),
        sort_keys=True,
        separators=(",", ":"),
    )

    assert repository.latest_anomaly(
        "tenant_demo", "anomaly_intelligence_1"
    ) == second
    assert repository.latest_anomaly(
        "tenant_other", "anomaly_intelligence_1"
    ) is None
    changed_update = replace(update_1, limitations=("changed_payload",))
    with pytest.raises(ConcurrentUpdateError):
        repository.save_anomaly_revision(
            "tenant_demo",
            changed_update,
            build_evidence_packet(changed_update),
        )


@pytest.mark.parametrize(
    ("changed_packet", "field"),
    (
        (lambda packet: replace(packet, resident_id="resident_other"), "resident_id"),
        (lambda packet: replace(packet, frame_id="frame_other"), "frame_id"),
        (
            lambda packet: replace(
                packet,
                changed_features=(
                    replace(packet.changed_features[0], robust_z=9.9),
                ),
            ),
            "changed_features",
        ),
        (
            lambda packet: replace(packet, filter_version="filter_other"),
            "filter_version",
        ),
    ),
)
def test_anomaly_mapper_rejects_cross_artifact_provenance_mismatch(
    changed_packet,
    field: str,
) -> None:
    baseline = _baseline()
    update, packet = _anomaly_revision(baseline)

    with pytest.raises(ValueError, match=field):
        anomaly_to_row("tenant_demo", update, changed_packet(packet))


def test_interpretation_mapper_rejects_unvalidated_provenance() -> None:
    _, packet = _anomaly_revision(_baseline())
    request, result = _interpretation(packet)

    with pytest.raises(
        InterpretationValidationError,
        match="provenance_mismatch:prompt_version",
    ):
        interpretation_to_row(
            "tenant_demo",
            request,
            replace(result, prompt_version="prompt_other"),
            AT,
        )


def test_interpretation_repository_rejects_self_consistent_fabricated_packet(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    _, _, packet = _store_baseline_and_anomaly(repository)
    request, _ = _interpretation(packet)
    payload = json.loads(request.payload_json)
    payload["anomaly_evidence"]["frame_id"] = "fabricated_frame"
    fingerprint_payload = dict(payload)
    fingerprint_payload.pop("request_fingerprint")
    material = {
        "model_id": request.model_id,
        "model_version": request.model_version,
        "payload": fingerprint_payload,
        "prompt": request.prompt,
        "skill_bundle": list(request.skill_bundle),
    }
    fingerprint = sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload["request_fingerprint"] = fingerprint
    fabricated_request = replace(
        request,
        payload_json=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        request_fingerprint=fingerprint,
    )
    fabricated_result = DeterministicFakeLLMClient().interpret(
        fabricated_request
    )

    with pytest.raises(ValueError, match="stored evidence packet"):
        repository.save_interpretation(
            "tenant_demo",
            fabricated_request,
            fabricated_result,
            AT + timedelta(seconds=1),
        )


def test_interpretation_repository_rejects_noncanonical_embedded_request(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    _, _, packet = _store_baseline_and_anomaly(repository)
    request, _ = _interpretation(packet)
    noncanonical = replace(request, payload_json=f"{request.payload_json} ")
    result = DeterministicFakeLLMClient().interpret(noncanonical)

    with pytest.raises(ValueError, match="canonical"):
        repository.save_interpretation(
            "tenant_demo",
            noncanonical,
            result,
            packet.current_time,
        )


def test_interpretation_hydration_rejects_malformed_embedded_context_shape() -> None:
    _, packet = _anomaly_revision(_baseline())
    request, result = _interpretation(packet)
    row = interpretation_to_row("tenant_demo", request, result, packet.current_time)
    envelope = json.loads(row.request_json)
    embedded = json.loads(envelope["request"]["payload_json"])
    embedded["resident_context"] = []
    envelope["request"]["payload_json"] = canonical_json(embedded)
    row.request_json = canonical_json(envelope)

    with pytest.raises((ValueError, ConcurrentUpdateError)) as exc_info:
        interpretation_from_row(row)
    assert not isinstance(exc_info.value, AttributeError)


def test_interpretation_hydration_rejects_wrong_nested_evidence_type() -> None:
    _, packet = _anomaly_revision(_baseline())
    request, result = _interpretation(packet)
    row = interpretation_to_row("tenant_demo", request, result, packet.current_time)
    envelope = json.loads(row.request_json)
    embedded = json.loads(envelope["request"]["payload_json"])
    embedded["anomaly_evidence"]["changed_features"][0]["robust_z"] = {
        "invalid": True
    }
    envelope["request"]["payload_json"] = canonical_json(embedded)
    row.request_json = canonical_json(envelope)

    with pytest.raises(ValueError, match="changed features"):
        interpretation_from_row(row)


def test_interpretation_hydration_rejects_oversized_nested_integer() -> None:
    # Break caught: isfinite converts an arbitrary-size JSON integer and overflows.
    _, packet = _anomaly_revision(_baseline())
    request, result = _interpretation(packet)
    row = interpretation_to_row("tenant_demo", request, result, packet.current_time)
    envelope = json.loads(row.request_json)
    embedded = json.loads(envelope["request"]["payload_json"])
    embedded["anomaly_evidence"]["changed_features"][0]["robust_z"] = 10**1000
    envelope["request"]["payload_json"] = canonical_json(embedded)
    row.request_json = canonical_json(envelope)

    with pytest.raises((ValueError, ConcurrentUpdateError)) as exc_info:
        interpretation_from_row(row)
    assert not isinstance(exc_info.value, OverflowError)


def test_interpretation_hydration_rejects_empty_outer_skill_bundle() -> None:
    # Break caught: Task 6 indexes an empty persisted skill bundle.
    _, packet = _anomaly_revision(_baseline())
    request, result = _interpretation(packet)
    row = interpretation_to_row("tenant_demo", request, result, packet.current_time)
    envelope = json.loads(row.request_json)
    envelope["request"]["skill_bundle"] = []
    row.request_json = canonical_json(envelope)

    with pytest.raises((ValueError, ConcurrentUpdateError)) as exc_info:
        interpretation_from_row(row)
    assert not isinstance(exc_info.value, IndexError)


def test_interpretation_write_mapping_rejects_empty_outer_skill_bundle() -> None:
    # Break caught: write mapping reaches Task 6 before request shape validation.
    _, packet = _anomaly_revision(_baseline())
    request, result = _interpretation(packet)

    with pytest.raises(ValueError) as exc_info:
        interpretation_to_row(
            "tenant_demo",
            replace(request, skill_bundle=()),
            result,
            packet.current_time,
        )
    assert not isinstance(exc_info.value, IndexError)


def test_interpretation_hydration_rejects_non_list_outer_tuple_field() -> None:
    # Break caught: tuple(None) raises raw TypeError before request validation.
    _, packet = _anomaly_revision(_baseline())
    request, result = _interpretation(packet)
    row = interpretation_to_row("tenant_demo", request, result, packet.current_time)
    envelope = json.loads(row.request_json)
    envelope["request"]["available_evidence_refs"] = None
    row.request_json = canonical_json(envelope)

    with pytest.raises((ValueError, ConcurrentUpdateError)) as exc_info:
        interpretation_from_row(row)
    assert not isinstance(exc_info.value, TypeError)


def test_interpretation_hydration_rejects_missing_request_envelope() -> None:
    # Break caught: a missing outer request object escapes as raw KeyError.
    _, packet = _anomaly_revision(_baseline())
    request, result = _interpretation(packet)
    row = interpretation_to_row("tenant_demo", request, result, packet.current_time)
    envelope = json.loads(row.request_json)
    del envelope["request"]
    row.request_json = canonical_json(envelope)

    with pytest.raises((ValueError, ConcurrentUpdateError)) as exc_info:
        interpretation_from_row(row)
    assert not isinstance(exc_info.value, KeyError)


def test_interpretation_hydration_rejects_recursive_embedded_json() -> None:
    # Break caught: deeply nested persisted JSON escapes as raw RecursionError.
    _, packet = _anomaly_revision(_baseline())
    request, result = _interpretation(packet)
    row = interpretation_to_row("tenant_demo", request, result, packet.current_time)
    envelope = json.loads(row.request_json)
    embedded = json.loads(envelope["request"]["payload_json"])
    scalar = canonical_json(
        embedded["anomaly_evidence"]["changed_features"][0]["value"]
    )
    envelope["request"]["payload_json"] = envelope["request"][
        "payload_json"
    ].replace(
        f'"value":{scalar}',
        '"value":' + "[" * 150_000 + "0" + "]" * 150_000,
        1,
    )
    row.request_json = canonical_json(envelope)

    with pytest.raises((ValueError, ConcurrentUpdateError)) as exc_info:
        interpretation_from_row(row)
    assert not isinstance(exc_info.value, RecursionError)


def test_interpretation_hydration_rejects_recursive_outer_request_json() -> None:
    # Break caught: outer persisted JSON parsing escapes as raw RecursionError.
    _, packet = _anomaly_revision(_baseline())
    request, result = _interpretation(packet)
    row = interpretation_to_row("tenant_demo", request, result, packet.current_time)
    envelope = json.loads(row.request_json)
    refs = canonical_json(envelope["request"]["available_evidence_refs"])
    row.request_json = row.request_json.replace(
        f'"available_evidence_refs":{refs}',
        '"available_evidence_refs":' + "[" * 150_000 + "0" + "]" * 150_000,
        1,
    )

    with pytest.raises((ValueError, ConcurrentUpdateError)) as exc_info:
        interpretation_from_row(row)
    assert not isinstance(exc_info.value, RecursionError)


def test_interpretation_repository_rejects_fabricated_stored_context(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    _, _, packet = _store_baseline_and_anomaly(repository)
    memory = ResidentMemory(
        resident_id=packet.resident_id,
        version=1,
        entries=(
            MemoryEntry(
                entry_id="routine_evening",
                description="Usually reads in the evening",
                source_kind="operator",
                source_feedback_id=None,
                status="active",
                created_by="operator_1",
                created_at=packet.current_time - timedelta(days=1),
                context_kind="routine",
                local_time_start="18:00",
                local_time_end="22:00",
            ),
        ),
    )
    FeedbackRepository(session).save_memory(
        "tenant_demo",
        memory,
        expected_version=0,
        changed_at=packet.current_time - timedelta(days=1),
    )
    request, _ = _interpretation(packet, memory, ("routine_evening",))
    payload = json.loads(request.payload_json)
    payload["resident_context"]["entries"][0]["description"] = "Fabricated"
    fingerprint_payload = dict(payload)
    fingerprint_payload.pop("request_fingerprint")
    material = {
        "model_id": request.model_id,
        "model_version": request.model_version,
        "payload": fingerprint_payload,
        "prompt": request.prompt,
        "skill_bundle": list(request.skill_bundle),
    }
    fingerprint = sha256(canonical_json(material).encode()).hexdigest()
    payload["request_fingerprint"] = fingerprint
    fabricated = replace(
        request,
        payload_json=canonical_json(payload),
        request_fingerprint=fingerprint,
    )
    result = DeterministicFakeLLMClient().interpret(fabricated)

    with pytest.raises(ValueError, match="resident memory"):
        repository.save_interpretation(
            "tenant_demo",
            fabricated,
            result,
            packet.current_time,
        )


def test_interpretation_find_revalidates_stored_packet_chain(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    _, _, packet = _store_baseline_and_anomaly(repository)
    request, result = _interpretation(packet)
    repository.save_interpretation(
        "tenant_demo", request, result, packet.current_time
    )
    anomaly = session.scalar(select(AnomalyRevisionRow))
    anomaly.packet_json = f" {anomaly.packet_json}"
    session.flush()

    with pytest.raises(ConcurrentUpdateError):
        repository.find_interpretation("tenant_demo", result.interpretation_id)


def test_interpretation_rejects_creation_before_packet_time(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    _, _, packet = _store_baseline_and_anomaly(repository)
    request, result = _interpretation(packet)

    with pytest.raises(ValueError, match="precede"):
        repository.save_interpretation(
            "tenant_demo",
            request,
            result,
            packet.current_time - timedelta(days=30),
        )


def test_disposition_record_rejects_mismatched_or_invalid_identity() -> None:
    decision = DispositionDecision(
        disposition=PolicyDisposition.OBSERVE,
        priority=None,
        confidence="objective_only",
        objective_family="unknown_anomaly",
        headline="Observe",
        reasons=("objective_fallback",),
        policy_version="synthetic_disposition_v1",
        fallback_used=True,
        room_level_only=False,
        interpretation_id="interpretation_expected",
    )

    with pytest.raises(ValueError, match="interpretation_id"):
        DispositionRecord(
            disposition_id="disposition_invalid",
            resident_id="resident_demo_a",
            room_id="room_214",
            anomaly_id="anomaly_intelligence_1",
            evidence_kind=BridgeEvidenceKind.PACKET,
            evidence_revision=1,
            packet_revision=1,
            decided_at=AT,
            decision=decision,
            interpretation_id="interpretation_other",
        )
    with pytest.raises(ValueError, match="disposition_id"):
        DispositionRecord(
            disposition_id=" ",
            resident_id="resident_demo_a",
            room_id="room_214",
            anomaly_id="anomaly_intelligence_1",
            evidence_kind=BridgeEvidenceKind.PACKET,
            evidence_revision=1,
            packet_revision=1,
            decided_at=AT,
            decision=replace(decision, interpretation_id=None),
        )


def test_interpretation_and_disposition_preserve_complete_provenance(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    _, _, packet = _store_baseline_and_anomaly(repository)
    request, result = _interpretation(packet)

    stored_interpretation = repository.save_interpretation(
        "tenant_demo", request, result, AT + timedelta(seconds=5)
    )
    decision = DispositionDecision(
        disposition=PolicyDisposition.CAREGIVER_EVENT,
        priority=EventPriority.HIGH,
        confidence="interpreted",
        objective_family="unusual_movement",
        headline="Unusual movement pattern",
        reasons=("validated_interpretation",),
        policy_version="synthetic_disposition_v1",
        fallback_used=False,
        room_level_only=False,
        interpretation_id=result.interpretation_id,
    )
    event = _persist_packet_event(session, packet, decision)
    disposition = DispositionRecord(
        disposition_id="disposition_intelligence_1",
        resident_id="resident_demo_a",
        room_id="room_214",
        anomaly_id=packet.anomaly_id,
        evidence_kind=BridgeEvidenceKind.PACKET,
        evidence_revision=packet.packet_revision,
        packet_revision=packet.packet_revision,
        decided_at=AT + timedelta(seconds=6),
        decision=decision,
        interpretation_id=result.interpretation_id,
        event_id=event.event_id,
    )

    assert repository.find_interpretation(
        "tenant_demo", result.interpretation_id
    ) == stored_interpretation
    assert repository.save_interpretation(
        "tenant_demo", request, result, AT + timedelta(seconds=5)
    ) == stored_interpretation
    assert stored_interpretation.request == request
    assert stored_interpretation.result == result
    assert repository.find_interpretation(
        "tenant_other", result.interpretation_id
    ) is None
    assert repository.save_disposition("tenant_demo", disposition) == disposition
    assert repository.save_disposition("tenant_demo", disposition) == disposition
    assert repository.find_disposition(
        "tenant_demo", disposition.disposition_id
    ) == disposition
    with pytest.raises(ConcurrentUpdateError):
        repository.save_disposition(
            "tenant_demo",
            replace(disposition, event_id=None),
        )
    with pytest.raises(InterpretationValidationError):
        repository.save_interpretation(
            "tenant_demo",
            request,
            replace(result, model_version="changed_model_version"),
            AT + timedelta(seconds=5),
        )


def test_disposition_rejects_cross_lane_linked_artifacts(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    _, _, packet = _store_baseline_and_anomaly(repository)
    request, result = _interpretation(packet)
    repository.save_interpretation(
        "tenant_demo",
        request,
        result,
        packet.current_time,
    )
    decision = DispositionDecision(
        disposition=PolicyDisposition.OBSERVE,
        priority=None,
        confidence="interpreted",
        objective_family="unusual_movement",
        headline="Observe",
        reasons=("validated_interpretation",),
        policy_version="synthetic_disposition_v1",
        fallback_used=False,
        room_level_only=False,
        interpretation_id=result.interpretation_id,
    )
    record = DispositionRecord(
        disposition_id="disposition_wrong_lane",
        resident_id="resident_demo_b",
        room_id="room_214",
        anomaly_id=packet.anomaly_id,
        evidence_kind=BridgeEvidenceKind.PACKET,
        evidence_revision=packet.packet_revision,
        packet_revision=packet.packet_revision,
        decided_at=packet.current_time,
        decision=decision,
        interpretation_id=result.interpretation_id,
    )

    with pytest.raises(ValueError, match="lane"):
        repository.save_disposition("tenant_demo", record)


def test_packet_disposition_rejects_unrelated_same_lane_event(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    _, _, packet = _store_baseline_and_anomaly(repository)
    decision = DispositionDecision(
        disposition=PolicyDisposition.CAREGIVER_EVENT,
        priority=EventPriority.HIGH,
        confidence="objective_only",
        objective_family="unusual_movement",
        headline="Unusual movement",
        reasons=("objective_fallback",),
        policy_version="synthetic_disposition_v1",
        fallback_used=True,
        room_level_only=False,
    )
    _persist_packet_event(session, packet, decision)
    record = DispositionRecord(
        disposition_id="disposition_unrelated_event",
        resident_id=packet.resident_id,
        room_id=packet.room_id,
        anomaly_id=packet.anomaly_id,
        evidence_kind=BridgeEvidenceKind.PACKET,
        evidence_revision=packet.packet_revision,
        packet_revision=packet.packet_revision,
        decided_at=packet.current_time,
        decision=decision,
        event_id="evt_phase2_demo",
    )

    with pytest.raises(ValueError, match="bridge"):
        repository.save_disposition("tenant_demo", record)


def test_packet_disposition_rejects_decision_before_evidence(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    _, _, packet = _store_baseline_and_anomaly(repository)
    decision = DispositionDecision(
        disposition=PolicyDisposition.CAREGIVER_EVENT,
        priority=EventPriority.HIGH,
        confidence="objective_only",
        objective_family="unusual_movement",
        headline="Unusual movement",
        reasons=("objective_fallback",),
        policy_version="synthetic_disposition_v1",
        fallback_used=True,
        room_level_only=False,
    )
    event = _persist_packet_event(session, packet, decision)
    record = DispositionRecord(
        disposition_id="disposition_before_evidence",
        resident_id=packet.resident_id,
        room_id=packet.room_id,
        anomaly_id=packet.anomaly_id,
        evidence_kind=BridgeEvidenceKind.PACKET,
        evidence_revision=packet.packet_revision,
        packet_revision=packet.packet_revision,
        decided_at=packet.current_time - timedelta(days=30),
        decision=decision,
        event_id=event.event_id,
    )

    with pytest.raises(ValueError, match="precede"):
        repository.save_disposition("tenant_demo", record)


def test_packet_disposition_rejects_bridge_from_unrelated_policy(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    _, _, packet = _store_baseline_and_anomaly(repository)
    wrong_policy_decision = DispositionDecision(
        disposition=PolicyDisposition.CAREGIVER_EVENT,
        priority=EventPriority.HIGH,
        confidence="objective_only",
        objective_family="unusual_movement",
        headline="Unusual movement",
        reasons=("objective_fallback",),
        policy_version="unrelated_policy",
        fallback_used=True,
        room_level_only=False,
    )
    event = _persist_packet_event(session, packet, wrong_policy_decision)
    record = DispositionRecord(
        disposition_id="disposition_exact_policy_bridge",
        resident_id=packet.resident_id,
        room_id=packet.room_id,
        anomaly_id=packet.anomaly_id,
        evidence_kind=BridgeEvidenceKind.PACKET,
        evidence_revision=packet.packet_revision,
        packet_revision=packet.packet_revision,
        decided_at=packet.current_time,
        decision=replace(
            wrong_policy_decision,
            policy_version="synthetic_disposition_v1",
        ),
        event_id=event.event_id,
    )

    with pytest.raises(ValueError, match="bridge"):
        repository.save_disposition("tenant_demo", record)


def test_packet_disposition_rejects_bridge_before_packet_time(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    _, _, packet = _store_baseline_and_anomaly(repository)
    decision = DispositionDecision(
        disposition=PolicyDisposition.CAREGIVER_EVENT,
        priority=EventPriority.HIGH,
        confidence="objective_only",
        objective_family="unusual_movement",
        headline="Unusual movement",
        reasons=("objective_fallback",),
        policy_version="synthetic_disposition_v1",
        fallback_used=True,
        room_level_only=False,
    )
    event = _persist_packet_event(
        session,
        packet,
        decision,
        observed_at=packet.current_time - timedelta(days=20),
    )
    record = DispositionRecord(
        disposition_id="disposition_early_bridge",
        resident_id=packet.resident_id,
        room_id=packet.room_id,
        anomaly_id=packet.anomaly_id,
        evidence_kind=BridgeEvidenceKind.PACKET,
        evidence_revision=packet.packet_revision,
        packet_revision=packet.packet_revision,
        decided_at=packet.current_time,
        decision=decision,
        event_id=event.event_id,
    )

    with pytest.raises(ValueError, match="precede packet"):
        repository.save_disposition("tenant_demo", record)


def test_disposition_read_and_duplicate_revalidate_deleted_bridge(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    _, _, packet = _store_baseline_and_anomaly(repository)
    decision = DispositionDecision(
        disposition=PolicyDisposition.CAREGIVER_EVENT,
        priority=EventPriority.HIGH,
        confidence="objective_only",
        objective_family="unusual_movement",
        headline="Unusual movement",
        reasons=("objective_fallback",),
        policy_version="synthetic_disposition_v1",
        fallback_used=True,
        room_level_only=False,
    )
    event = _persist_packet_event(session, packet, decision)
    record = DispositionRecord(
        disposition_id="disposition_deleted_bridge",
        resident_id=packet.resident_id,
        room_id=packet.room_id,
        anomaly_id=packet.anomaly_id,
        evidence_kind=BridgeEvidenceKind.PACKET,
        evidence_revision=packet.packet_revision,
        packet_revision=packet.packet_revision,
        decided_at=packet.current_time,
        decision=decision,
        event_id=event.event_id,
    )
    repository.save_disposition("tenant_demo", record)
    bridge = session.scalar(
        select(EventBridgeRecordRow).where(
            EventBridgeRecordRow.event_id == event.event_id
        )
    )
    session.delete(bridge)
    session.flush()

    with pytest.raises(ValueError, match="bridge"):
        repository.save_disposition("tenant_demo", record)
    with pytest.raises(ValueError, match="bridge"):
        repository.find_disposition("tenant_demo", record.disposition_id)


def test_disposition_find_revalidates_event_bridge_ledger(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    _, _, packet = _store_baseline_and_anomaly(repository)
    decision = DispositionDecision(
        disposition=PolicyDisposition.CAREGIVER_EVENT,
        priority=EventPriority.HIGH,
        confidence="objective_only",
        objective_family="unusual_movement",
        headline="Unusual movement",
        reasons=("objective_fallback",),
        policy_version="synthetic_disposition_v1",
        fallback_used=True,
        room_level_only=False,
    )
    event = _persist_packet_event(session, packet, decision)
    record = DispositionRecord(
        disposition_id="disposition_tampered_event_ledger",
        resident_id=packet.resident_id,
        room_id=packet.room_id,
        anomaly_id=packet.anomaly_id,
        evidence_kind=BridgeEvidenceKind.PACKET,
        evidence_revision=packet.packet_revision,
        packet_revision=packet.packet_revision,
        decided_at=packet.current_time,
        decision=decision,
        event_id=event.event_id,
    )
    repository.save_disposition("tenant_demo", record)
    event_row = session.get(MonitoringEventRow, event.event_id)
    event_row.bridge_idempotency_keys = []
    session.flush()

    with pytest.raises(ValueError, match="bridge"):
        repository.find_disposition("tenant_demo", record.disposition_id)


def test_disposition_find_revalidates_all_event_bridge_times(
    session: Session,
) -> None:
    repository = IntelligenceRepository(session)
    _, _, packet = _store_baseline_and_anomaly(repository)
    decision = DispositionDecision(
        disposition=PolicyDisposition.CAREGIVER_EVENT,
        priority=EventPriority.HIGH,
        confidence="objective_only",
        objective_family="unusual_movement",
        headline="Unusual movement",
        reasons=("objective_fallback",),
        policy_version="synthetic_disposition_v1",
        fallback_used=True,
        room_level_only=False,
    )
    event = _persist_packet_event(session, packet, decision)
    later_bridge = replace(
        event.bridge_records[0],
        idempotency_key="anomaly_later:1:other_policy",
        source_anomaly_id="anomaly_later",
        observed_at=packet.current_time + timedelta(seconds=30),
    )
    later_event = replace(
        event,
        last_signal_at=later_bridge.observed_at,
        signal_count=2,
        source_anomaly_id=later_bridge.source_anomaly_id,
        bridge_idempotency_keys=(
            *event.bridge_idempotency_keys,
            later_bridge.idempotency_key,
        ),
        bridge_records=(*event.bridge_records, later_bridge),
    )
    EventRepository(session).save(
        "tenant_demo",
        later_event,
        expected_version=1,
    )
    record = DispositionRecord(
        disposition_id="disposition_event_bridge_time_ledger",
        resident_id=packet.resident_id,
        room_id=packet.room_id,
        anomaly_id=packet.anomaly_id,
        evidence_kind=BridgeEvidenceKind.PACKET,
        evidence_revision=packet.packet_revision,
        packet_revision=packet.packet_revision,
        decided_at=packet.current_time,
        decision=decision,
        event_id=event.event_id,
    )
    repository.save_disposition("tenant_demo", record)
    event_row = session.get(MonitoringEventRow, event.event_id)
    event_row.last_signal_at = packet.current_time
    session.flush()

    with pytest.raises(ValueError, match="signal history"):
        repository.find_disposition("tenant_demo", record.disposition_id)


def test_provisional_urgent_disposition_persists_without_packet(
    session: Session,
) -> None:
    engine = MonitoringIntelligenceEngine()
    result = None
    for frame in _fall_sequence():
        result = _process_fall_frame(
            engine,
            frame,
            baseline=_fall_baseline(feature_name="unused"),
        )
    assert result is not None
    assert result.evidence is None
    assert result.event is not None
    bridge = result.event.bridge_records[-1]
    EventRepository(session).save(
        "tenant_demo",
        result.event,
        expected_version=0,
    )
    record = DispositionRecord(
        disposition_id="disposition_provisional_fall",
        resident_id=result.event.resident_id,
        room_id=result.event.room_id,
        anomaly_id=bridge.source_anomaly_id,
        evidence_kind=BridgeEvidenceKind.PROVISIONAL,
        evidence_revision=bridge.evidence_revision,
        packet_revision=None,
        decided_at=bridge.observed_at,
        decision=result.decision,
        event_id=result.event.event_id,
    )

    assert IntelligenceRepository(session).save_disposition(
        "tenant_demo", record
    ) == record
    assert session.scalar(select(AnomalyRevisionRow)) is None


@pytest.mark.parametrize(
    ("row_type", "timestamp_field"),
    (
        (LLMInterpretationRow, "created_at"),
        (DispositionDecisionRow, "decided_at"),
    ),
)
def test_hydration_rejects_timestamp_shadow_tampering(
    session: Session,
    row_type,
    timestamp_field: str,
) -> None:
    repository = IntelligenceRepository(session)
    _, _, packet = _store_baseline_and_anomaly(repository)
    request, result = _interpretation(packet)
    repository.save_interpretation(
        "tenant_demo",
        request,
        result,
        packet.current_time,
    )
    disposition = DispositionRecord(
        disposition_id="disposition_timestamp_tamper",
        resident_id=packet.resident_id,
        room_id=packet.room_id,
        anomaly_id=packet.anomaly_id,
        evidence_kind=BridgeEvidenceKind.PACKET,
        evidence_revision=packet.packet_revision,
        packet_revision=packet.packet_revision,
        decided_at=packet.current_time,
        decision=DispositionDecision(
            disposition=PolicyDisposition.OBSERVE,
            priority=None,
            confidence="interpreted",
            objective_family="unusual_movement",
            headline="Observe",
            reasons=("validated_interpretation",),
            policy_version="synthetic_disposition_v1",
            fallback_used=False,
            room_level_only=False,
            interpretation_id=result.interpretation_id,
        ),
        interpretation_id=result.interpretation_id,
    )
    repository.save_disposition("tenant_demo", disposition)
    row = session.scalar(select(row_type))
    setattr(row, timestamp_field, packet.current_time + timedelta(days=1))
    session.flush()

    with pytest.raises(ConcurrentUpdateError):
        if row_type is LLMInterpretationRow:
            repository.find_interpretation("tenant_demo", result.interpretation_id)
        else:
            repository.find_disposition("tenant_demo", disposition.disposition_id)


def test_event_metadata_and_bridge_payload_rehydrate_event_store(
    session: Session,
) -> None:
    story = seed_synthetic_story(session)
    event_repository = EventRepository(session)
    stored = event_repository.get(story.tenant_id, story.event_id)
    bridge = EventBridgeRecord(
        idempotency_key="anomaly_intelligence_1:1:synthetic_disposition_v1",
        resident_id=story.resident_id,
        room_id=story.room_id,
        source_anomaly_id="anomaly_intelligence_1",
        evidence_revision=1,
        evidence_kind=BridgeEvidenceKind.PACKET,
        objective_family="unusual_movement",
        headline="Unusual movement pattern",
        priority=EventPriority.HIGH,
        provisional_urgent=True,
        room_level_only=False,
        observed_at=AT,
        actor_id="system:monitoring_event",
        related_event_ids=("evt_prior",),
    )
    event = replace(
        stored.event,
        source_anomaly_id=bridge.source_anomaly_id,
        latest_evidence_revision=bridge.evidence_revision,
        latest_provisional_evidence_revision=2,
        attention_suppressed_until=AT + timedelta(minutes=30),
        provisional_urgent=True,
        room_level_only=False,
        bridge_idempotency_keys=(bridge.idempotency_key,),
        bridge_records=(bridge,),
    )
    event_repository.save(
        story.tenant_id,
        event,
        expected_version=stored.version,
    )

    hydrated = event_repository.get(story.tenant_id, story.event_id).event
    assert hydrated == event
    assert IntelligenceRepository(session).find_event_bridge(
        story.tenant_id, bridge.idempotency_key
    ).record == bridge
    assert IntelligenceRepository(session).find_event_bridge(
        "tenant_other", bridge.idempotency_key
    ) is None

    restarted_store = EventStore(initial_events=(hydrated,))
    assert restarted_store.record_signal(
        resident_id=bridge.resident_id,
        room_id=bridge.room_id,
        objective_family=bridge.objective_family,
        headline=bridge.headline,
        priority=bridge.priority,
        observed_at=bridge.observed_at,
        actor_id=bridge.actor_id,
        source_anomaly_id=bridge.source_anomaly_id,
        evidence_revision=bridge.evidence_revision,
        bridge_idempotency_key=bridge.idempotency_key,
        provisional_urgent=bridge.provisional_urgent,
        evidence_kind=bridge.evidence_kind,
        room_level_only=bridge.room_level_only,
        related_event_ids=bridge.related_event_ids,
    ) == hydrated
    with pytest.raises(ValueError, match="bridge idempotency conflict"):
        restarted_store.record_signal(
            resident_id=bridge.resident_id,
            room_id=bridge.room_id,
            objective_family=bridge.objective_family,
            headline="Changed payload",
            priority=bridge.priority,
            observed_at=bridge.observed_at,
            actor_id=bridge.actor_id,
            source_anomaly_id=bridge.source_anomaly_id,
            evidence_revision=bridge.evidence_revision,
            bridge_idempotency_key=bridge.idempotency_key,
            provisional_urgent=bridge.provisional_urgent,
            evidence_kind=bridge.evidence_kind,
            room_level_only=bridge.room_level_only,
            related_event_ids=bridge.related_event_ids,
        )


def test_event_bridge_conflict_rolls_back_parent_and_children(
    session: Session,
) -> None:
    story = seed_synthetic_story(session)
    repository = EventRepository(session)
    original = repository.get(story.tenant_id, story.event_id)
    bridge = EventBridgeRecord(
        idempotency_key="anomaly_atomic:1:policy_v1",
        resident_id=story.resident_id,
        room_id=story.room_id,
        source_anomaly_id="anomaly_atomic",
        evidence_revision=1,
        evidence_kind=BridgeEvidenceKind.PACKET,
        objective_family="unusual_movement",
        headline="Original bridge payload",
        priority=EventPriority.HIGH,
        provisional_urgent=False,
        room_level_only=False,
        observed_at=AT,
        actor_id="system:monitoring_event",
    )
    stored = repository.save(
        story.tenant_id,
        replace(
            original.event,
            source_anomaly_id=bridge.source_anomaly_id,
            latest_evidence_revision=1,
            bridge_idempotency_keys=(bridge.idempotency_key,),
            bridge_records=(bridge,),
        ),
        expected_version=original.version,
    )
    session.commit()

    conflicting = replace(
        stored.event,
        headline="Mutated parent headline",
        signal_count=stored.event.signal_count + 1,
        bridge_records=(replace(bridge, headline="Changed bridge payload"),),
    )
    with pytest.raises(ConcurrentUpdateError):
        repository.save(
            story.tenant_id,
            conflicting,
            expected_version=stored.version,
        )
    session.commit()
    session.expire_all()

    recovered = repository.get(story.tenant_id, story.event_id)
    assert recovered == stored


def test_event_bridge_hydration_rejects_shadow_column_tampering(
    session: Session,
) -> None:
    story = seed_synthetic_story(session)
    events = EventRepository(session)
    original = events.get(story.tenant_id, story.event_id)
    bridge = EventBridgeRecord(
        idempotency_key="anomaly_shadow:1:policy_v1",
        resident_id=story.resident_id,
        room_id=story.room_id,
        source_anomaly_id="anomaly_shadow",
        evidence_revision=1,
        evidence_kind=BridgeEvidenceKind.PACKET,
        objective_family="unknown_anomaly",
        headline="Shadow binding",
        priority=EventPriority.HIGH,
        provisional_urgent=False,
        room_level_only=False,
        observed_at=AT,
        actor_id="system:monitoring_event",
    )
    events.save(
        story.tenant_id,
        replace(
            original.event,
            source_anomaly_id=bridge.source_anomaly_id,
            latest_evidence_revision=1,
            bridge_idempotency_keys=(bridge.idempotency_key,),
            bridge_records=(bridge,),
        ),
        expected_version=original.version,
    )
    row = session.scalar(
        select(EventBridgeRecordRow).where(
            EventBridgeRecordRow.tenant_id == story.tenant_id,
            EventBridgeRecordRow.idempotency_key == bridge.idempotency_key,
        )
    )
    assert row is not None
    row.priority = EventPriority.CRITICAL.value
    session.commit()
    session.expire_all()

    with pytest.raises(ConcurrentUpdateError):
        IntelligenceRepository(session).find_event_bridge(
            story.tenant_id,
            bridge.idempotency_key,
        )
