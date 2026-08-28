from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.ai.client import (
    DeterministicFakeLLMClient,
    InterpretationStatus,
    RecommendedDisposition,
    render_caregiver_wording,
)
from backend.app.domain.events import EventPriority, EventStatus, EventStore
from backend.app.domain.feedback import ResidentMemory
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
        frame_id=f"frame_{second}",
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
    return AlignedFrame(
        frame_id=f"fall_frame_{second}",
        window_start=at,
        window_end=at + timedelta(seconds=1),
        sources_present=("radar", "thermal"),
        sources_missing=(),
        feature_evidence=evidence,
        agreements=(f"position_state:radar=thermal={position}",),
        contradictions=(),
    )


def _fall_sequence(start_second: int = 0) -> tuple[AlignedFrame, ...]:
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
        )
        for index, (height, velocity, position, movement) in enumerate(values)
    )


def _baseline(*, feature_name: str = "movement") -> BaselineSnapshot:
    return BaselineSnapshot(
        baseline_id="baseline_7",
        resident_id=RESIDENT_ID,
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


def _memory() -> ResidentMemory:
    return ResidentMemory(resident_id=RESIDENT_ID, version=1, entries=())


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
        disposition = RecommendedDisposition.CAREGIVER_EVENT
        return replace(
            result,
            recommended_disposition=disposition,
            caregiver_wording=render_caregiver_wording(
                result.likely_explanation,
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
):
    return engine.process_frame(
        frame,
        baseline=baseline or _baseline(),
        context_key="resident_global",
        anomaly_id=anomaly_id,
        resident_id=RESIDENT_ID,
        room_id=ROOM_ID,
        config_version="synthetic_config_v4",
        unknowns=("cause_of_behavior_change",),
        resident_memory=_memory(),
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


def test_routine_context_never_suppresses_urgent_fall_like_evidence() -> None:
    # Break caught: an away/routine context flag suppresses strong urgent physical evidence.
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
    assert result.event is not None
    assert result.decision.disposition is PolicyDisposition.CAREGIVER_EVENT
    assert "urgent_fall_like" in result.decision.reasons


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
    result = None

    for current in _fall_sequence():
        result = _process(
            engine,
            current,
            baseline=_baseline(feature_name="unused"),
            possible_multiple_people=True,
        )

    assert result is not None
    assert result.event is not None
    assert result.decision.room_level_only
    assert result.fall_assessment.room_level_only
    assert result.event.headline == "Room-level fall-like signal pattern"


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
