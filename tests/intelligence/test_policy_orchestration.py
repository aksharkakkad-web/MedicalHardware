from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.ai.client import (
    DeterministicFakeLLMClient,
    ExplanationCategory,
    InterpretationStatus,
    RecommendedDisposition,
    render_caregiver_wording,
    render_plain_english_summary,
)
from backend.app.domain.events import EventPriority, EventStatus, EventStore
from backend.app.domain.feedback import MemoryEntry, ResidentMemory
from backend.app.intelligence.anomaly import AnomalyState
from backend.app.intelligence.baseline import BaselineSnapshot, FeatureBaseline
from backend.app.intelligence.fusion import AlignedFrame, FeatureEvidence
from backend.app.intelligence.observations import (
    FeaturePurpose,
    FeatureValue,
    QualityClass,
)
from backend.app.intelligence.orchestration import MonitoringIntelligenceEngine
from backend.app.intelligence.policy import (
    EventAttentionPolicy,
    PolicyDisposition,
    SyntheticDispositionPolicy,
)


START = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
RESIDENT_ID = "resident_demo_a"
ROOM_ID = "room_214"
TENANT_ID = "tenant_demo"


def _feature(
    name: str,
    value: float | bool | str | None,
    unit: str,
    purpose: FeaturePurpose,
    *,
    source: str = "radar",
    second: int,
    quality: QualityClass = QualityClass.GOOD,
    reasons: tuple[str, ...] = (),
) -> FeatureEvidence:
    return FeatureEvidence(
        source=source,
        observation_id=f"observation_{source}_{second}_{name}",
        feature=FeatureValue(
            name=name,
            value=value,
            unit=unit,
            quality_class=quality,
            quality_reasons=reasons,
            purposes=(purpose,),
        ),
    )


def _movement_frame(
    second: int,
    value: float,
    *,
    device_moved: bool = False,
    frame_id: str | None = None,
    tenant_id: str = TENANT_ID,
    room_id: str = ROOM_ID,
    resident_id: str = RESIDENT_ID,
) -> AlignedFrame:
    evidence = (
        _feature(
            "movement",
            value,
            "normalized",
            FeaturePurpose.MOVEMENT,
            second=second,
        ),
    )
    if device_moved:
        evidence += (
            _feature(
                "device_moved",
                True,
                "boolean",
                FeaturePurpose.MOVEMENT,
                second=second,
            ),
        )
    at = START + timedelta(seconds=second)
    return AlignedFrame(
        frame_id=frame_id or f"frame_{second}",
        tenant_id=tenant_id,
        room_id=room_id,
        resident_id=resident_id,
        window_start=at,
        window_end=at + timedelta(seconds=1),
        sources_present=("radar",),
        sources_missing=(),
        feature_evidence=evidence,
        agreements=(),
        contradictions=(),
    )


def _fall_frame(
    second: int,
    *,
    height: float,
    velocity: float,
    position: str,
    movement: float,
    degradation: str | None = None,
    tenant_id: str = TENANT_ID,
    room_id: str = ROOM_ID,
    resident_id: str = RESIDENT_ID,
) -> AlignedFrame:
    at = START + timedelta(seconds=second)
    evidence = (
        _feature(
            "tracked_height",
            height,
            "m",
            FeaturePurpose.POSTURE,
            second=second,
        ),
        _feature(
            "vertical_velocity",
            velocity,
            "m/s",
            FeaturePurpose.MOVEMENT,
            second=second,
        ),
        _feature(
            "position_state",
            position,
            "categorical",
            FeaturePurpose.POSTURE,
            second=second,
        ),
        _feature(
            "movement_energy",
            movement,
            "normalized",
            FeaturePurpose.MOVEMENT,
            second=second,
        ),
        _feature(
            "position_state",
            position,
            "categorical",
            FeaturePurpose.POSTURE,
            source="thermal",
            second=second,
        ),
    )
    if degradation in {"device_moved", "environment_shift"}:
        evidence += (
            _feature(
                degradation,
                True,
                "boolean",
                FeaturePurpose.MOVEMENT,
                second=second,
            ),
        )
    elif degradation in {"frozen", "stale"}:
        evidence += (
            _feature(
                "signal_health",
                0.5,
                "normalized",
                FeaturePurpose.MOVEMENT,
                second=second,
                quality=QualityClass.LIMITED,
                reasons=(degradation,),
            ),
        )
    return AlignedFrame(
        frame_id=f"fall_frame_{second}",
        tenant_id=tenant_id,
        room_id=room_id,
        resident_id=resident_id,
        window_start=at,
        window_end=at + timedelta(seconds=1),
        sources_present=("radar", "thermal"),
        sources_missing=(),
        feature_evidence=evidence,
        agreements=(f"position_state:radar=thermal={position}",),
        contradictions=(),
    )


def _fall_sequence(
    start_second: int = 0,
    *,
    degradation: str | None = None,
) -> tuple[AlignedFrame, ...]:
    values = (
        (1.7, 0.0, "upright_like", 0.4),
        (0.8, -1.1, "floor_like", 0.5),
        (0.78, -0.1, "floor_like", 0.1),
        (0.78, 0.0, "floor_like", 0.08),
        (0.78, 0.0, "floor_like", 0.07),
    )
    return tuple(
        _fall_frame(
            start_second + index,
            height=height,
            velocity=velocity,
            position=position,
            movement=movement,
            degradation=degradation,
        )
        for index, (height, velocity, position, movement) in enumerate(values)
    )


def _baseline(
    *,
    feature_name: str = "movement",
    resident_id: str = RESIDENT_ID,
    baseline_id: str = "baseline_7",
) -> BaselineSnapshot:
    return BaselineSnapshot(
        baseline_id=baseline_id,
        resident_id=resident_id,
        monitoring_setup_version="setup_room_214_v3",
        features=(
            FeatureBaseline(
                feature_name=feature_name,
                purpose=FeaturePurpose.MOVEMENT,
                median=0.0,
                mad=0.0,
                iqr=0.0,
                lower_quantile=0.0,
                upper_quantile=0.0,
                resolution_floor=0.1,
                unit="normalized",
                eligible_sample_count=12,
                context_key="resident_global",
            ),
        ),
        policy_version="synthetic_baseline_v1",
    )


def _memory(
    resident_id: str = RESIDENT_ID,
    *,
    entries: tuple[MemoryEntry, ...] = (),
) -> ResidentMemory:
    return ResidentMemory(resident_id=resident_id, version=1, entries=entries)


class RecordingClient:
    def __init__(self, mode: str = "event") -> None:
        self.mode = mode
        self.calls = []

    def interpret(self, request):
        self.calls.append(request)
        if self.mode == "raise":
            raise RuntimeError("synthetic provider outage")
        result = DeterministicFakeLLMClient().interpret(request)
        if self.mode == "invalid":
            return replace(result, anomaly_id="forged_anomaly")
        if self.mode == "unavailable":
            return replace(result, status=InterpretationStatus.UNAVAILABLE)
        if self.mode == "unsupported_no_action":
            category = ExplanationCategory.ROUTINE_MOVEMENT
            disposition = RecommendedDisposition.NO_ACTION
            return replace(
                result,
                likely_explanation=category,
                supporting_evidence_refs=(),
                described_measurements=(),
                plain_english_summary=render_plain_english_summary(category),
                recommended_disposition=disposition,
                caregiver_wording=render_caregiver_wording(category, disposition),
            )
        disposition = RecommendedDisposition.CAREGIVER_EVENT
        category = (
            ExplanationCategory.ROUTINE_MOVEMENT
            if self.mode == "routine"
            else result.likely_explanation
        )
        return replace(
            result,
            likely_explanation=category,
            plain_english_summary=render_plain_english_summary(category),
            recommended_disposition=disposition,
            caregiver_wording=render_caregiver_wording(
                category,
                disposition,
            ),
        )


def _process(
    engine: MonitoringIntelligenceEngine,
    frame: AlignedFrame,
    *,
    anomaly_id: str = "anomaly_1",
    baseline: BaselineSnapshot | None = None,
    resident_away: bool = False,
    possible_multiple_people: bool = False,
    tenant_id: str = TENANT_ID,
    resident_id: str = RESIDENT_ID,
    room_id: str = ROOM_ID,
    resident_memory: ResidentMemory | None = None,
):
    return engine.process_frame(
        frame,
        baseline=baseline or _baseline(),
        context_key="resident_global",
        anomaly_id=anomaly_id,
        tenant_id=tenant_id,
        resident_id=resident_id,
        room_id=room_id,
        config_version="synthetic_config_v4",
        unknowns=("cause_of_behavior_change",),
        resident_memory=resident_memory or _memory(resident_id),
        resident_away=resident_away,
        possible_multiple_people=possible_multiple_people,
    )


def _activate(
    engine: MonitoringIntelligenceEngine,
    *,
    anomaly_id: str = "anomaly_1",
    start_second: int = 0,
    value: float = 0.5,
):
    result = None
    for second in range(start_second, start_second + 3):
        result = _process(
            engine,
            _movement_frame(second, value),
            anomaly_id=anomaly_id,
        )
    assert result is not None
    return result


def test_normal_frame_returns_no_action_without_ai_or_event() -> None:
    # Break caught: normal evidence is interpreted or promoted into caregiver work.
    client = RecordingClient()
    engine = MonitoringIntelligenceEngine(llm_client=client)

    result = _process(engine, _movement_frame(0, 0.0))

    assert result.observation.frame_id == "frame_0"
    assert result.baseline.baseline_id == "baseline_7"
    assert result.anomaly is not None
    assert result.anomaly.episode is None
    assert result.evidence is None
    assert result.interpretation is None
    assert result.decision.disposition is PolicyDisposition.NO_ACTION
    assert result.event is None
    assert client.calls == []


def test_away_context_does_not_create_resident_anomaly_or_caregiver_work() -> None:
    # Break caught: an ordinary bathroom/away interval becomes a resident alert.
    client = RecordingClient()
    engine = MonitoringIntelligenceEngine(llm_client=client)

    result = _process(
        engine,
        _movement_frame(0, 0.8),
        resident_away=True,
    )

    assert result.anomaly is None
    assert result.decision.disposition in {
        PolicyDisposition.NO_ACTION,
        PolicyDisposition.AWARENESS,
    }
    assert result.event is None
    assert client.calls == []


def test_sustained_nonurgent_anomaly_is_validated_before_policy_consumes_it() -> None:
    # Break caught: nonurgent policy decides without the one structured AI transaction.
    client = RecordingClient()
    engine = MonitoringIntelligenceEngine(llm_client=client)

    result = _activate(engine)

    assert len(client.calls) == 1
    assert result.interpretation is not None
    assert result.decision.interpretation_id == result.interpretation.interpretation_id
    assert result.decision.disposition is PolicyDisposition.CAREGIVER_EVENT
    assert result.event is not None


@pytest.mark.parametrize("mode", ("invalid", "unavailable", "raise"))
def test_untrusted_or_unavailable_ai_uses_objective_fallback(mode: str) -> None:
    # Break caught: provider failure either crashes monitoring or becomes trusted policy input.
    client = RecordingClient(mode)
    engine = MonitoringIntelligenceEngine(llm_client=client)

    result = _activate(engine)

    assert len(client.calls) == 1
    assert result.interpretation is None
    assert result.interpretation_error
    assert result.decision.fallback_used
    assert result.decision.disposition is PolicyDisposition.CAREGIVER_EVENT
    assert result.event is not None


def test_evidence_free_routine_no_action_uses_objective_fallback() -> None:
    # Break caught: unsupported routine/no-action output suppresses caregiver work.
    client = RecordingClient("unsupported_no_action")
    engine = MonitoringIntelligenceEngine(llm_client=client)

    result = _activate(engine)

    assert len(client.calls) == 1
    assert result.interpretation is None
    assert result.interpretation_error == (
        "non_unknown_explanation_requires_supporting_evidence",
    )
    assert result.decision.fallback_used
    assert result.decision.disposition is PolicyDisposition.CAREGIVER_EVENT
    assert result.event is not None


def test_provider_recovery_keeps_one_event_for_the_same_anomaly() -> None:
    # Break caught: fallback and later validated categories split one episode into two events.
    client = RecordingClient("raise")
    engine = MonitoringIntelligenceEngine(llm_client=client)
    fallback = _activate(engine)
    assert fallback.event is not None
    client.mode = "event"

    enriched = _process(engine, _movement_frame(3, 0.5))

    assert enriched.event is not None
    assert enriched.event.event_id == fallback.event.event_id
    assert enriched.event.signal_count == 2


def test_urgent_fall_like_evidence_creates_event_without_ai_result() -> None:
    # Break caught: the urgent short lane waits for or is cancelled by an LLM failure.
    client = RecordingClient("raise")
    engine = MonitoringIntelligenceEngine(llm_client=client)
    result = None

    for current in _fall_sequence():
        result = _process(engine, current, baseline=_baseline(feature_name="unused"))

    assert result is not None
    assert result.fall_assessment.urgent_triggered
    assert result.interpretation is None
    assert client.calls == []
    assert result.decision.disposition is PolicyDisposition.CAREGIVER_EVENT
    assert result.decision.priority is EventPriority.CRITICAL
    assert result.event is not None
    assert result.event.provisional_urgent


def test_away_context_blocks_apparent_fall_and_resets_confounded_sequence() -> None:
    # Break caught: an away-room sequence creates resident work or contaminates later frames.
    engine = MonitoringIntelligenceEngine(llm_client=RecordingClient("raise"))
    result = None

    for current in _fall_sequence():
        result = _process(
            engine,
            current,
            baseline=_baseline(feature_name="unused"),
            resident_away=True,
        )

    assert result is not None
    assert result.event is None
    assert result.decision.disposition is PolicyDisposition.NO_ACTION

    trustworthy = _process(
        engine,
        _fall_sequence(start_second=10)[-1],
        baseline=_baseline(feature_name="unused"),
    )
    assert not trustworthy.fall_assessment.urgent_triggered
    assert trustworthy.event is None


def test_duplicate_packet_processing_is_idempotent() -> None:
    # Break caught: replaying one packet increments the event signal count twice.
    engine = MonitoringIntelligenceEngine(llm_client=RecordingClient())
    result = _activate(engine)
    assert result.event is not None

    duplicate = _process(engine, _movement_frame(2, 0.5))

    assert duplicate.event is not None
    assert duplicate.event.event_id == result.event.event_id
    assert duplicate.event.signal_count == 1
    assert duplicate.event_bridge_idempotency_key == (
        "anomaly_1:1:synthetic_disposition_v1"
    )


def test_same_lane_frame_identity_rejects_conflicting_complete_inputs() -> None:
    # Break caught: a partial cache key silently returns stale work for changed evidence.
    engine = MonitoringIntelligenceEngine(llm_client=RecordingClient())
    original = _movement_frame(0, 0.0, frame_id="stable_frame")
    conflicting = _movement_frame(0, 0.8, frame_id="stable_frame")
    _process(engine, original)

    with pytest.raises(ValueError, match="processed frame identity conflict"):
        _process(engine, conflicting)


@pytest.mark.parametrize(
    ("passed_field", "passed_value"),
    (
        ("tenant_id", "tenant_other"),
        ("room_id", "room_other"),
        ("resident_id", "resident_other"),
    ),
)
def test_process_frame_rejects_passed_identity_that_does_not_match_frame(
    passed_field: str,
    passed_value: str,
) -> None:
    # Break caught: orchestration relabels a frame into a different assignment lane.
    engine = MonitoringIntelligenceEngine(llm_client=RecordingClient())
    identity = {passed_field: passed_value}

    with pytest.raises(ValueError, match="frame assignment identity must match"):
        _process(engine, _movement_frame(0, 0.0), **identity)


def test_exact_replay_rehydrates_current_event_without_reinvoking_ai() -> None:
    # Break caught: replay returns the cached OPEN snapshot after acknowledgment.
    client = RecordingClient()
    engine = MonitoringIntelligenceEngine(llm_client=client)
    opened = _activate(engine)
    assert opened.event is not None
    assert len(client.calls) == 1
    engine.acknowledge_event(
        opened.event.event_id,
        actor_id="operator_001",
        at=START + timedelta(seconds=4),
    )

    replayed = _process(engine, _movement_frame(2, 0.5))

    assert len(client.calls) == 1
    assert replayed.event is not None
    assert replayed.event.status is EventStatus.ACKNOWLEDGED
    assert replayed.decision.attention_suppressed


def test_continuing_acknowledged_evidence_updates_one_event_but_stays_quiet() -> None:
    # Break caught: acknowledgment either closes the anomaly or blocks evidence updates.
    engine = MonitoringIntelligenceEngine(llm_client=RecordingClient())
    opened = _activate(engine)
    assert opened.event is not None
    acknowledged = engine.acknowledge_event(
        opened.event.event_id,
        actor_id="operator_001",
        at=START + timedelta(seconds=4),
    )

    continued = _process(engine, _movement_frame(4, 0.5))

    assert continued.event is not None
    assert continued.event.event_id == opened.event.event_id
    assert continued.event.status is EventStatus.ACKNOWLEDGED
    assert continued.event.signal_count == 2
    assert continued.event.attention_suppressed_until == (
        START + timedelta(minutes=30, seconds=4)
    )
    assert continued.decision.attention_suppressed
    assert acknowledged.attention_suppressed_until == continued.event.attention_suppressed_until
    assert continued.anomaly is not None
    assert continued.anomaly.episode is not None
    assert continued.anomaly.episode.state is AnomalyState.ACTIVE


def test_material_priority_escalation_overrides_attention_cooldown() -> None:
    # Break caught: materially stronger evidence remains hidden by an old cooldown.
    engine = MonitoringIntelligenceEngine(llm_client=RecordingClient())
    opened = _activate(engine, value=0.5)
    assert opened.event is not None
    engine.acknowledge_event(
        opened.event.event_id,
        actor_id="operator_001",
        at=START + timedelta(seconds=4),
    )

    escalated = _process(engine, _movement_frame(4, 0.8))

    assert escalated.event is not None
    assert escalated.event.event_id == opened.event.event_id
    assert escalated.event.priority is EventPriority.CRITICAL
    assert escalated.event.attention_suppressed_until is None
    assert not escalated.decision.attention_suppressed


def test_anomaly_recovery_does_not_resolve_caregiver_event() -> None:
    # Break caught: numerical recovery silently resolves outstanding caregiver work.
    engine = MonitoringIntelligenceEngine(llm_client=RecordingClient())
    opened = _activate(engine)
    assert opened.event is not None

    result = None
    for second in (3, 4, 5):
        result = _process(engine, _movement_frame(second, 0.0))

    assert result is not None
    assert result.anomaly is not None
    assert result.anomaly.episode is not None
    assert result.anomaly.episode.state is AnomalyState.CLOSED
    assert result.decision.disposition is PolicyDisposition.NO_ACTION
    assert engine.event_store.get(opened.event.event_id).status is EventStatus.OPEN


def test_failed_persistence_candidate_closes_silently_before_later_episode() -> None:
    # Break caught: a short candidate emits a packet/event or blocks a later anomaly ID.
    client = RecordingClient()
    engine = MonitoringIntelligenceEngine(llm_client=client)
    started = _process(
        engine,
        _movement_frame(0, 0.5),
        anomaly_id="short_candidate",
    )
    retired = _process(
        engine,
        _movement_frame(1, 0.2),
        anomaly_id="short_candidate",
    )

    assert started.evidence is None
    assert retired.anomaly is not None and retired.anomaly.episode is not None
    assert retired.anomaly.episode.state is AnomalyState.CLOSED
    assert retired.evidence is None
    assert retired.interpretation is None
    assert retired.event is None
    assert client.calls == []

    later = None
    for second in (2, 3, 4):
        later = _process(
            engine,
            _movement_frame(second, 0.5),
            anomaly_id="later_anomaly",
        )
    assert later is not None and later.event is not None
    assert later.event.source_anomaly_id == "later_anomaly"


def test_post_recovery_anomaly_creates_linked_event() -> None:
    # Break caught: a distinct post-recovery episode reopens or mutates old history.
    engine = MonitoringIntelligenceEngine(llm_client=RecordingClient())
    first = _activate(engine, anomaly_id="anomaly_1")
    assert first.event is not None
    for second in (3, 4, 5):
        _process(engine, _movement_frame(second, 0.0), anomaly_id="anomaly_1")

    recurrence = _activate(
        engine,
        anomaly_id="anomaly_2",
        start_second=6,
        value=0.5,
    )

    assert recurrence.event is not None
    assert recurrence.event.event_id != first.event.event_id
    assert recurrence.event.related_event_ids == (first.event.event_id,)
    assert recurrence.event.recurrence_count == 2
    assert recurrence.event.source_anomaly_id == "anomaly_2"


def test_recurrence_lineage_survives_changed_objective_family() -> None:
    # Break caught: interpretation wording, rather than recurrence_of, controls event links.
    client = RecordingClient("raise")
    engine = MonitoringIntelligenceEngine(llm_client=client)
    first = _activate(engine, anomaly_id="anomaly_1")
    assert first.event is not None
    assert first.event.objective_family == "unknown_anomaly"
    for second in (3, 4, 5):
        _process(engine, _movement_frame(second, 0.0), anomaly_id="anomaly_1")
    client.mode = "routine"

    recurrence = _activate(
        engine,
        anomaly_id="anomaly_2",
        start_second=6,
        value=0.5,
    )

    assert recurrence.anomaly is not None
    assert recurrence.anomaly.episode is not None
    assert recurrence.anomaly.episode.recurrence_of == "anomaly_1"
    assert recurrence.event is not None
    assert recurrence.event.objective_family == "routine_movement"
    assert recurrence.event.related_event_ids == (first.event.event_id,)
    assert recurrence.event.recurrence_count == 2
    assert engine.event_store.get(first.event.event_id).status is EventStatus.OPEN


def test_monitoring_degradation_is_operational_awareness_only() -> None:
    # Break caught: device movement is mislabeled as a resident anomaly/event.
    client = RecordingClient()
    engine = MonitoringIntelligenceEngine(llm_client=client)

    result = _process(engine, _movement_frame(0, 0.8, device_moved=True))

    assert result.degradation.degraded
    assert not result.degradation.resident_anomaly
    assert result.anomaly is None
    assert result.decision.disposition is PolicyDisposition.AWARENESS
    assert result.event is None
    assert client.calls == []


def test_multi_person_urgent_result_is_room_level_without_resident_claim() -> None:
    # Break caught: ambiguous fall-like evidence is attributed to the assigned resident.
    engine = MonitoringIntelligenceEngine(llm_client=RecordingClient("raise"))
    memory = _memory(
        entries=(
            MemoryEntry(
                entry_id="private_routine",
                description="Private resident routine",
                source_feedback_id="feedback_001",
                status="active",
                created_by="operator_001",
                created_at=START - timedelta(days=1),
            ),
        ),
    )
    result = None

    for current in _fall_sequence():
        result = _process(
            engine,
            current,
            baseline=_baseline(feature_name="unused"),
            possible_multiple_people=True,
            resident_memory=memory,
        )

    assert result is not None
    assert result.event is not None
    assert result.decision.room_level_only
    assert result.fall_assessment.room_level_only
    assert result.event.headline == "Room-level fall-like signal pattern"
    assert result.event.room_level_only
    assert result.event.resident_id == RESIDENT_ID
    assert result.event.resident_memory_version is None
    assert result.event.resident_memory_entry_ids == ()


def test_nonurgent_multi_person_is_room_awareness_without_resident_anomaly() -> None:
    # Break caught: attribution ambiguity silently disappears as no action.
    engine = MonitoringIntelligenceEngine(llm_client=RecordingClient())

    result = _process(
        engine,
        _movement_frame(0, 0.8),
        possible_multiple_people=True,
    )

    assert result.anomaly is None
    assert result.event is None
    assert result.decision.disposition is PolicyDisposition.AWARENESS
    assert result.decision.room_level_only


def test_interleaved_resident_lanes_keep_anomaly_state_and_events_isolated() -> None:
    # Break caught: resident B's normal frame advances or rejects resident A's episode.
    client = RecordingClient()
    engine = MonitoringIntelligenceEngine(llm_client=client)
    result_a = None
    result_b = None
    for second in range(3):
        result_a = _process(
            engine,
            _movement_frame(
                second,
                0.5,
                resident_id="resident_a",
                room_id="room_a",
            ),
            resident_id="resident_a",
            room_id="room_a",
            anomaly_id="anomaly_a",
            baseline=_baseline(
                resident_id="resident_a",
                baseline_id="baseline_a",
            ),
        )
        result_b = _process(
            engine,
            _movement_frame(
                second,
                0.0,
                resident_id="resident_b",
                room_id="room_b",
            ),
            resident_id="resident_b",
            room_id="room_b",
            anomaly_id="anomaly_b",
            baseline=_baseline(
                resident_id="resident_b",
                baseline_id="baseline_b",
            ),
        )

    assert result_a is not None and result_a.event is not None
    assert result_a.event.resident_id == "resident_a"
    assert result_a.event.room_id == "room_a"
    assert result_b is not None and result_b.event is None
    assert result_b.anomaly is not None and result_b.anomaly.episode is None
    assert len(client.calls) == 1


def test_same_resident_and_room_are_isolated_across_tenants() -> None:
    # Break caught: same-named assignment lanes share anomaly, replay, or event state.
    client = RecordingClient()
    engine = MonitoringIntelligenceEngine(llm_client=client)
    results = {}
    for second in range(3):
        for tenant_id in ("tenant_a", "tenant_b"):
            results[tenant_id] = _process(
                engine,
                _movement_frame(second, 0.5, tenant_id=tenant_id),
                tenant_id=tenant_id,
                anomaly_id="same_anomaly_id",
            )

    event_a = results["tenant_a"].event
    event_b = results["tenant_b"].event
    assert event_a is not None and event_b is not None
    assert event_a.event_id != event_b.event_id
    assert event_a.signal_count == event_b.signal_count == 1
    assert len(client.calls) == 2


def test_interleaved_fall_lanes_do_not_cross_contaminate_or_misattribute() -> None:
    # Break caught: one global fall state combines alternating room evidence.
    engine = MonitoringIntelligenceEngine(llm_client=RecordingClient("raise"))
    sequence_a = _fall_sequence()
    sequence_b = _fall_sequence()
    result_a = None
    result_b = None
    for current_a, current_b in zip(sequence_a, sequence_b, strict=True):
        result_a = _process(
            engine,
            replace(current_a, resident_id="resident_a", room_id="room_a"),
            resident_id="resident_a",
            room_id="room_a",
            anomaly_id="fall_a",
            baseline=_baseline(
                feature_name="unused",
                resident_id="resident_a",
                baseline_id="baseline_a",
            ),
        )
        result_b = _process(
            engine,
            replace(current_b, resident_id="resident_b", room_id="room_b"),
            resident_id="resident_b",
            room_id="room_b",
            anomaly_id="fall_b",
            baseline=_baseline(
                feature_name="unused",
                resident_id="resident_b",
                baseline_id="baseline_b",
            ),
        )

    assert result_a is not None and result_a.event is not None
    assert result_b is not None and result_b.event is not None
    assert result_a.event.event_id != result_b.event.event_id
    assert (result_a.event.resident_id, result_a.event.room_id) == (
        "resident_a",
        "room_a",
    )
    assert (result_b.event.resident_id, result_b.event.room_id) == (
        "resident_b",
        "room_b",
    )


def test_distinct_urgent_frames_use_monotonic_provisional_bridge_revisions() -> None:
    # Break caught: every packetless urgent frame collapses onto the `revision=0` key.
    engine = MonitoringIntelligenceEngine(llm_client=RecordingClient("raise"))
    result = None
    sequence = _fall_sequence()
    for current in sequence:
        result = _process(engine, current, baseline=_baseline(feature_name="unused"))
    assert result is not None and result.event is not None
    first_key = result.event_bridge_idempotency_key

    continued_frame = _fall_frame(
        5,
        height=0.78,
        velocity=0.0,
        position="floor_like",
        movement=0.06,
    )
    continued = _process(
        engine,
        continued_frame,
        baseline=_baseline(feature_name="unused"),
    )
    replayed = _process(
        engine,
        continued_frame,
        baseline=_baseline(feature_name="unused"),
    )

    assert first_key == "anomaly_1:provisional-1:synthetic_disposition_v1"
    assert continued.event_bridge_idempotency_key == (
        "anomaly_1:provisional-2:synthetic_disposition_v1"
    )
    assert continued.event is not None
    assert continued.event.signal_count == 2
    assert continued.event.last_signal_at == START + timedelta(seconds=6)
    assert replayed.event is not None
    assert replayed.event.signal_count == 2


@pytest.mark.parametrize(
    "degradation",
    ("device_moved", "environment_shift", "frozen", "stale"),
)
def test_degradation_precedes_apparent_fall_and_resets_confounded_state(
    degradation: str,
) -> None:
    # Break caught: known-bad operational evidence creates a resident urgent event.
    engine = MonitoringIntelligenceEngine(llm_client=RecordingClient("raise"))
    result = None
    for current in _fall_sequence(degradation=degradation):
        result = _process(
            engine,
            current,
            baseline=_baseline(feature_name="unused"),
        )

    assert result is not None
    assert result.degradation.degraded
    assert result.decision.disposition is PolicyDisposition.AWARENESS
    assert result.event is None

    trustworthy = _process(
        engine,
        _fall_sequence(start_second=10)[-1],
        baseline=_baseline(feature_name="unused"),
    )
    assert not trustworthy.fall_assessment.urgent_triggered
    assert trustworthy.event is None


def test_task7_policies_are_versioned_synthetic_and_nonclinical() -> None:
    # Break caught: prototype disposition/cooldown values gain hidden authority.
    disposition = SyntheticDispositionPolicy()
    attention = EventAttentionPolicy()

    assert disposition.policy_version == "synthetic_disposition_v1"
    assert disposition.test_only
    assert not disposition.clinical_authority
    assert attention.policy_version == "synthetic_event_attention_v1"
    assert attention.test_only
    assert attention.acknowledged_cooldown == timedelta(minutes=30)


def test_custom_attention_duration_requires_distinct_policy_version() -> None:
    # Break caught: a changed cooldown reuses provenance from the canonical fixture policy.
    with pytest.raises(ValueError, match="distinct policy_version"):
        EventAttentionPolicy(acknowledged_cooldown=timedelta(minutes=5))

    custom = EventAttentionPolicy(
        acknowledged_cooldown=timedelta(minutes=5),
        policy_version="synthetic_event_attention_custom_v1",
    )
    assert custom.acknowledged_cooldown == timedelta(minutes=5)
