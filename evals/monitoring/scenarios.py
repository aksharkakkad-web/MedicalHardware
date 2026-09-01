"""Stable, visibly synthetic Phase 5 scenario fixtures and component execution."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

from backend.app.ai.client import (
    DeterministicFakeLLMClient,
    InterpretationRequest,
    InterpretationResult,
    InterpretationStatus,
    LLMClient,
    RecommendedDisposition,
    render_caregiver_wording,
)
from backend.app.domain.calibration import (
    BaselineStatus,
    CalibrationDimensionProgress,
    CalibrationProgress,
    start_recalibration,
)
from backend.app.db.base import Base
from backend.app.db.intelligence_mappers import DispositionRecord
from backend.app.db.intelligence_repositories import IntelligenceRepository
from backend.app.db.repositories import EventRepository
from backend.app.db.seed import seed_synthetic_story
from backend.app.db.session import create_engine_for_url, create_session_factory
from backend.app.domain.events import BridgeEvidenceKind, EventStatus, EventStore
from backend.app.domain.feedback import MemoryEntry, ResidentMemory
from backend.app.domain.monitoring import (
    MonitoringSnapshot,
    MonitoringState,
    PresenceState,
    derive_monitoring_snapshot,
)
from backend.app.intelligence.anomaly import AnomalyState
from backend.app.intelligence.baseline import (
    BaselinePolicy,
    BaselineSnapshot,
    NewNormalCandidate,
    advance_new_normal,
    build_feature_baseline,
    window_is_learning_eligible,
)
from backend.app.intelligence.fall_detection import FallLikeState
from backend.app.intelligence.fusion import AlignedFrame, align_observations
from backend.app.intelligence.observations import (
    FeaturePurpose,
    FeatureValue,
    NormalizedObservation,
    QualityClass,
)
from backend.app.intelligence.orchestration import (
    IntelligenceResult,
    MonitoringIntelligenceEngine,
)


SUITE_START = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
TENANT_ID = "tenant_demo"
RESIDENT_ID = "resident_demo_a"
ROOM_ID = "room_214"
DEVICE_ID = "device_synthetic_combo"
SETUP_VERSION = "setup_synthetic_v1"
CONTEXT_KEY = "resident_global"
CONFIG_VERSION = "synthetic_monitoring_config_v1"

REQUIRED_SCENARIO_IDS = (
    "normal_variation",
    "random_bathroom_away",
    "sleep_reading_stillness",
    "flexible_routine",
    "temporary_change",
    "visitor_multi_person",
    "sustained_movement_change",
    "repetitive_movement",
    "inactivity",
    "fall_like",
    "fall_like_confounder",
    "respiration_quality_limited",
    "unknown_anomaly",
    "missing_signal",
    "stale_signal",
    "frozen_signal",
    "contradictory_sensors",
    "setup_change",
    "preentered_new_behavior",
    "post_event_new_behavior",
    "continuing_acknowledged_anomaly",
    "recurrence_after_recovery",
    "llm_unavailable",
    "llm_invalid_output",
)


@dataclass(frozen=True)
class ScenarioDefinition:
    scenario_id: str
    intent: str
    expected_class: str
    meaningful_expected: bool = False
    packet_expected: bool = False
    caregiver_event_expected: bool = False
    quiet_resident_work_required: bool = False
    declared_exposure_units: float = 1.0
    expected_event_duration_seconds: float | None = None
    fixture_shortcut: str | None = None


@dataclass(frozen=True)
class ScenarioExecution:
    scenario_id: str
    record: dict[str, Any]
    interpretation_requests: tuple[InterpretationRequest, ...]
    interpretation_results: tuple[InterpretationResult, ...]
    provider_errors: tuple[str, ...]


SCENARIOS = (
    ScenarioDefinition("normal_variation", "ordinary movement around the personal baseline", "ordinary", quiet_resident_work_required=True),
    ScenarioDefinition("random_bathroom_away", "ordinary bathroom/away interval", "routine", quiet_resident_work_required=True),
    ScenarioDefinition("sleep_reading_stillness", "ordinary stillness while present", "ordinary", quiet_resident_work_required=True),
    ScenarioDefinition("flexible_routine", "flexible routine context without an exact schedule", "routine", quiet_resident_work_required=True),
    ScenarioDefinition("temporary_change", "time-bounded semantic context", "routine", quiet_resident_work_required=True),
    ScenarioDefinition("visitor_multi_person", "ambiguous room occupancy", "operational", quiet_resident_work_required=True),
    ScenarioDefinition("sustained_movement_change", "persistent movement deviation", "meaningful", True, True, True),
    ScenarioDefinition("repetitive_movement", "persistent repetitive movement evidence", "meaningful", True, True, True),
    ScenarioDefinition("inactivity", "persistent inactivity evidence", "meaningful", True, True, True),
    ScenarioDefinition("fall_like", "urgent corroborated fall-like transition", "urgent", True, False, True),
    ScenarioDefinition("fall_like_confounder", "controlled descent confounder", "ordinary", quiet_resident_work_required=True),
    ScenarioDefinition("respiration_quality_limited", "respiration change with limited quality", "operational", quiet_resident_work_required=True),
    ScenarioDefinition("unknown_anomaly", "persistent feature deviation without a forced semantic cause", "meaningful", True, True, True),
    ScenarioDefinition("missing_signal", "explicitly unavailable normalized evidence", "operational", quiet_resident_work_required=True),
    ScenarioDefinition("stale_signal", "stale source evidence", "operational", quiet_resident_work_required=True),
    ScenarioDefinition("frozen_signal", "frozen source evidence", "operational", quiet_resident_work_required=True),
    ScenarioDefinition("contradictory_sensors", "contradictory posture evidence", "operational", quiet_resident_work_required=True),
    ScenarioDefinition("setup_change", "device movement starts selective recalibration", "operational", quiet_resident_work_required=True),
    ScenarioDefinition("preentered_new_behavior", "expected behavior is semantic before numerical adoption", "learning", quiet_resident_work_required=True, fixture_shortcut="starts from the approved Task 3 expected-new-behavior candidate boundary"),
    ScenarioDefinition("post_event_new_behavior", "clean post-feedback windows adopt a new numerical normal", "learning", quiet_resident_work_required=True, fixture_shortcut="starts from the approved Task 3 post-event feedback-to-adoption boundary"),
    ScenarioDefinition("continuing_acknowledged_anomaly", "continuing evidence after caregiver acknowledgment", "lifecycle", packet_expected=True, caregiver_event_expected=True, expected_event_duration_seconds=2.0),
    ScenarioDefinition("recurrence_after_recovery", "closed anomaly followed by a linked recurrence", "lifecycle", packet_expected=True, caregiver_event_expected=True),
    ScenarioDefinition("llm_unavailable", "provider returns unavailable and objective policy continues", "meaningful", True, True, True),
    ScenarioDefinition("llm_invalid_output", "provider returns provenance-invalid output and is rejected", "meaningful", True, True, True),
)


class ScenarioLLMClient:
    """Deterministic fake-provider modes; no API or live model is used."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.requests: list[object] = []
        self.raw_results: list[object] = []

    def interpret(self, request):
        self.requests.append(request)
        result = DeterministicFakeLLMClient().interpret(request)
        if self.mode in {"caregiver_event", "invalid", "unavailable"}:
            disposition = RecommendedDisposition.CAREGIVER_EVENT
            result = replace(
                result,
                recommended_disposition=disposition,
                caregiver_wording=render_caregiver_wording(
                    result.likely_explanation,
                    disposition,
                ),
            )
        if self.mode == "invalid":
            result = replace(
                result,
                anomaly_id="forged_synthetic_anomaly",
                packet_revision=result.packet_revision + 1,
            )
        elif self.mode == "unavailable":
            result = replace(result, status=InterpretationStatus.UNAVAILABLE)
        self.raw_results.append(result)
        return result


class RecordingLLMClient:
    """Capture an injected provider exchange without changing its result."""

    def __init__(self, client: LLMClient) -> None:
        self.client = client
        self.requests: list[InterpretationRequest] = []
        self.raw_results: list[InterpretationResult] = []
        self.errors: list[str] = []

    def interpret(self, request: InterpretationRequest) -> InterpretationResult:
        self.requests.append(request)
        try:
            result = self.client.interpret(request)
        except Exception as exc:
            self.errors.append(f"{type(exc).__name__}: {exc}")
            raise
        self.raw_results.append(result)
        return result


FrameTransform = Callable[[tuple[AlignedFrame, ...]], tuple[AlignedFrame, ...]]


FeatureSpec = tuple[
    str,
    float | int | bool | str | None,
    str,
    FeaturePurpose,
    QualityClass,
    tuple[str, ...],
]


def scenario_definitions() -> tuple[ScenarioDefinition, ...]:
    return SCENARIOS


def _feature(
    name: str,
    value: float | int | bool | str | None,
    unit: str,
    purpose: FeaturePurpose,
    quality: QualityClass = QualityClass.GOOD,
    reasons: tuple[str, ...] = (),
) -> FeatureSpec:
    return name, value, unit, purpose, quality, reasons


def _frame(
    scenario_id: str,
    start: datetime,
    second: int,
    source_features: dict[str, tuple[FeatureSpec, ...]],
    *,
    expected_sources: tuple[str, ...] = ("radar", "thermal", "csi"),
) -> AlignedFrame:
    window_start = start + timedelta(seconds=second)
    window_end = window_start + timedelta(seconds=1)
    observations = tuple(
        NormalizedObservation(
            observation_id=f"{scenario_id}_{second:02d}_{source}",
            tenant_id=TENANT_ID,
            room_id=ROOM_ID,
            resident_id=RESIDENT_ID,
            device_id=DEVICE_ID,
            source=source,
            window_start=window_start,
            window_end=window_end,
            features=tuple(
                FeatureValue(
                    name=name,
                    value=value,
                    unit=unit,
                    quality_class=quality,
                    quality_reasons=reasons,
                    purposes=(purpose,),
                )
                for name, value, unit, purpose, quality, reasons in features
            ),
            source_quality_class=(
                QualityClass.UNUSABLE
                if all(item[4] == QualityClass.UNUSABLE for item in features)
                else QualityClass.LIMITED
                if any(item[4] == QualityClass.LIMITED for item in features)
                else QualityClass.GOOD
            ),
            source_quality_reasons=tuple(
                sorted({reason for item in features for reason in item[5]})
            ),
            processor_version="synthetic_normalizer_v1",
        )
        for source, features in sorted(source_features.items())
    )
    return align_observations(
        observations,
        frame_id=f"{scenario_id}_frame_{second:02d}",
        window_start=window_start,
        window_end=window_end,
        expected_sources=expected_sources,
    )


def _numeric_frame(
    scenario_id: str,
    start: datetime,
    second: int,
    value: float | None,
    *,
    feature_name: str = "movement_energy",
    unit: str = "normalized",
    purpose: FeaturePurpose = FeaturePurpose.MOVEMENT,
    quality: QualityClass = QualityClass.GOOD,
    reasons: tuple[str, ...] = (),
    extras: tuple[FeatureSpec, ...] = (),
) -> AlignedFrame:
    return _frame(
        scenario_id,
        start,
        second,
        {"radar": (_feature(feature_name, value, unit, purpose, quality, reasons), *extras)},
    )


def _fall_frame(
    scenario_id: str,
    start: datetime,
    second: int,
    *,
    height: float,
    velocity: float,
    position: str,
    movement: float,
    thermal_position: str | None = None,
) -> AlignedFrame:
    thermal = position if thermal_position is None else thermal_position
    return _frame(
        scenario_id,
        start,
        second,
        {
            "radar": (
                _feature("tracked_height", height, "m", FeaturePurpose.POSTURE),
                _feature("vertical_velocity", velocity, "m/s", FeaturePurpose.MOVEMENT),
                _feature("position_state", position, "categorical", FeaturePurpose.POSTURE),
                _feature("movement_energy", movement, "normalized", FeaturePurpose.MOVEMENT),
            ),
            "thermal": (
                _feature("position_state", thermal, "categorical", FeaturePurpose.POSTURE),
            ),
        },
    )


def _fall_sequence(scenario_id: str, start: datetime) -> tuple[AlignedFrame, ...]:
    values = (
        (1.7, 0.0, "upright_like", 0.4),
        (0.8, -1.1, "floor_like", 0.5),
        (0.78, -0.1, "floor_like", 0.1),
        (0.78, 0.0, "floor_like", 0.08),
        (0.78, 0.0, "floor_like", 0.07),
    )
    return tuple(
        _fall_frame(
            scenario_id,
            start,
            second,
            height=height,
            velocity=velocity,
            position=position,
            movement=movement,
        )
        for second, (height, velocity, position, movement) in enumerate(values)
    )


def _active_monitoring() -> MonitoringSnapshot:
    return derive_monitoring_snapshot(
        assignment_valid=True,
        device_healthy=True,
        presence=PresenceState.RESIDENT_PRESENT,
        signal_quality=1.0,
    )


def _baseline(
    scenario_id: str,
    start: datetime,
    *,
    feature_name: str = "movement_energy",
    unit: str = "normalized",
    purpose: FeaturePurpose = FeaturePurpose.MOVEMENT,
    samples: tuple[float, ...] = (0.0, 0.0, 0.0, 0.0, 0.0),
) -> BaselineSnapshot:
    training_frames = tuple(
        _numeric_frame(
            f"{scenario_id}_baseline",
            start - timedelta(days=1),
            index,
            value,
            feature_name=feature_name,
            unit=unit,
            purpose=purpose,
        )
        for index, value in enumerate(samples)
    )
    guards = tuple(
        window_is_learning_eligible(
            frame,
            monitoring_snapshot=_active_monitoring(),
            resident_id=RESIDENT_ID,
            setup_version=SETUP_VERSION,
            purpose=purpose,
        )
        for frame in training_frames
    )
    feature = build_feature_baseline(
        guards,
        resident_id=RESIDENT_ID,
        setup_version=SETUP_VERSION,
        feature_name=feature_name,
        purpose=purpose,
        context_key=CONTEXT_KEY,
        resolution_floor=0.1,
        policy=BaselinePolicy(),
    )
    return BaselineSnapshot(
        baseline_id=f"{scenario_id}_baseline_v1",
        resident_id=RESIDENT_ID,
        monitoring_setup_version=SETUP_VERSION,
        features=(feature,),
        policy_version=BaselinePolicy().policy_version,
    )


def _memory(
    *,
    entry_id: str | None = None,
    context_kind: str = "routine",
    start: datetime,
    effective_until: datetime | None = None,
) -> ResidentMemory:
    entries = ()
    if entry_id is not None:
        entries = (
            MemoryEntry(
                entry_id=entry_id,
                description=f"Synthetic {context_kind.replace('_', ' ')} context",
                source_feedback_id=None,
                status="active",
                created_by="operator_synthetic",
                created_at=start - timedelta(days=1),
                source_kind="operator",
                context_kind=context_kind,
                effective_from=start - timedelta(hours=1),
                effective_until=effective_until,
                flexibility_note="Synthetic fixture; timing is intentionally flexible",
            ),
        )
    return ResidentMemory(
        resident_id=RESIDENT_ID,
        version=1 if entries else 0,
        entries=entries,
    )


def _engine(
    mode: str | None,
    llm_client: LLMClient | None = None,
) -> tuple[
    MonitoringIntelligenceEngine,
    ScenarioLLMClient | RecordingLLMClient | None,
]:
    client: ScenarioLLMClient | RecordingLLMClient | None
    if llm_client is not None:
        client = RecordingLLMClient(llm_client)
    else:
        client = None if mode is None else ScenarioLLMClient(mode)
    return MonitoringIntelligenceEngine(llm_client=client), client


def _process(
    engine: MonitoringIntelligenceEngine,
    frame: AlignedFrame,
    *,
    baseline: BaselineSnapshot,
    anomaly_id: str,
    memory: ResidentMemory,
    resident_away: bool = False,
    possible_multiple_people: bool = False,
    relevant_context_entry_ids: tuple[str, ...] = (),
) -> IntelligenceResult:
    return engine.process_frame(
        frame,
        baseline=baseline,
        context_key=CONTEXT_KEY,
        anomaly_id=anomaly_id,
        tenant_id=TENANT_ID,
        resident_id=RESIDENT_ID,
        room_id=ROOM_ID,
        config_version=CONFIG_VERSION,
        unknowns=("synthetic_cause_not_established",),
        resident_memory=memory,
        resident_away=resident_away,
        possible_multiple_people=possible_multiple_people,
        relevant_context_entry_ids=relevant_context_entry_ids,
    )


def _learning_record(
    frame: AlignedFrame,
    result: IntelligenceResult,
    monitoring: MonitoringSnapshot,
    *,
    purpose: FeaturePurpose = FeaturePurpose.MOVEMENT,
    setup_change: bool = False,
) -> tuple[object, bool]:
    state = result.anomaly.episode.state if result.anomaly and result.anomaly.episode else None
    fall_in_progress = result.fall_assessment.state not in {
        FallLikeState.STABLE,
        FallLikeState.RECOVERED,
    }
    unsafe = bool(
        not monitoring.baseline_learning_allowed
        or result.degradation.degraded
        or frame.contradictions
        or state is not None
        or fall_in_progress
        or setup_change
        or any(
            item.feature.quality_class != QualityClass.GOOD
            for item in frame.feature_evidence
            if purpose in item.feature.purposes
        )
    )
    guard = window_is_learning_eligible(
        frame,
        monitoring_snapshot=monitoring,
        resident_id=RESIDENT_ID,
        setup_version=SETUP_VERSION,
        purpose=purpose,
        active_candidate=state == AnomalyState.CANDIDATE or fall_in_progress,
        unresolved_anomaly=state in {AnomalyState.ACTIVE, AnomalyState.RECOVERING},
        setup_change=setup_change,
        recovery_freeze=state == AnomalyState.CLOSED,
    )
    return guard, unsafe


def _finalize(
    definition: ScenarioDefinition,
    start: datetime,
    results: list[IntelligenceResult],
    learning_records: list[tuple[object, bool]],
    client: ScenarioLLMClient | RecordingLLMClient | None,
    monitoring_state: MonitoringState,
    *,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    episodes = {
        result.anomaly.episode.anomaly_id: result.anomaly.episode
        for result in results
        if result.anomaly is not None and result.anomaly.episode is not None
    }
    packets = {
        (result.evidence.anomaly_id, result.evidence.packet_revision): result.evidence
        for result in results
        if result.evidence is not None
    }
    events = {
        result.event.event_id: result.event
        for result in results
        if result.event is not None
    }
    event_groups: dict[str, set[str]] = {}
    for event in events.values():
        event_groups.setdefault(event.source_anomaly_id or "legacy", set()).add(event.event_id)
    duplicate_events = sum(max(0, len(ids) - 1) for ids in event_groups.values())
    interpretations = [result.interpretation for result in results if result.interpretation]
    errors = [reason for result in results for reason in result.interpretation_error]
    attempted_results = [
        result
        for result in results
        if result.interpretation is not None or result.interpretation_error
    ]
    unavailable_results = [
        result
        for result in attempted_results
        if result.interpretation is None
        and any(
            "unavailable" in reason
            or "interpretation_status:unavailable" in reason
            for reason in result.interpretation_error
        )
    ]
    rejected_results = [
        result
        for result in attempted_results
        if result.interpretation is None and result not in unavailable_results
    ]
    rejected_reference_count = sum(
        len(getattr(raw_result, "supporting_evidence_refs", ()))
        for attempted_result, raw_result in zip(
            attempted_results,
            (client.raw_results if client else ()),
            strict=False,
        )
        if attempted_result in rejected_results
    )
    event_values = tuple(events.values())
    resident_specific_events = tuple(event for event in event_values if not event.room_level_only)
    first_episode = min(
        (episode.candidate_started_at for episode in episodes.values()),
        default=None,
    )
    first_packet = min((packet.current_time for packet in packets.values()), default=None)
    first_event = min((event.created_at for event in event_values), default=None)
    actual_event_duration = (
        max(
            (event.last_signal_at - event.created_at).total_seconds()
            for event in event_values
        )
        if event_values
        else None
    )
    final_episode = next(
        (
            result.anomaly.episode
            for result in reversed(results)
            if result.anomaly is not None and result.anomaly.episode is not None
        ),
        None,
    )
    final_event = next((result.event for result in reversed(results) if result.event), None)
    guard_values = [guard for guard, _unsafe in learning_records]
    contaminated = sum(
        int(bool(getattr(guard, "eligible")) and unsafe)
        for guard, unsafe in learning_records
    )
    duration_seconds = (
        (results[-1].observation.window_end - results[0].observation.window_start).total_seconds()
        if results
        else 0.0
    )
    record: dict[str, Any] = {
        "scenario_id": definition.scenario_id,
        "intent": definition.intent,
        "expected_class": definition.expected_class,
        "meaningful_expected": definition.meaningful_expected,
        "packet_expected": definition.packet_expected,
        "caregiver_event_expected": definition.caregiver_event_expected,
        "quiet_resident_work_required": definition.quiet_resident_work_required,
        "declared_exposure_units": definition.declared_exposure_units,
        "component_trace": [
            "normalized_observation",
            "quality_learning_guard",
            "robust_baseline",
            "monitoring_intelligence_engine",
        ],
        "monitoring_state": monitoring_state.value,
        "monitoring_duration_seconds": duration_seconds,
        "candidate_count": len(episodes),
        "packet_count": len(packets),
        "caregiver_event_count": len(events),
        "resident_specific_event_count": len(resident_specific_events),
        "event_signal_groups": len(event_groups),
        "duplicate_event_count": duplicate_events,
        "candidate_latency_seconds": (
            (first_episode - start).total_seconds() if first_episode else None
        ),
        "packet_latency_seconds": (
            (first_packet - start).total_seconds() if first_packet else None
        ),
        "event_latency_seconds": (
            (first_event - start).total_seconds() if first_event else None
        ),
        "expected_event_duration_seconds": definition.expected_event_duration_seconds,
        "actual_event_duration_seconds": actual_event_duration,
        "interpretation": {
            "attempted": len(client.requests) if client else 0,
            "valid": len(interpretations),
            "rejected": len(rejected_results),
            "unavailable": len(unavailable_results),
        },
        "ai_diagnostics": {
            "validation_reason_count": len(errors),
            "validated_evidence_reference_count": sum(
                len(item.supporting_evidence_refs) for item in interpretations
            ),
            "rejected_result_evidence_reference_count": rejected_reference_count,
            "explicit_unsupported_conclusion_count": sum(
                len(item.unsupported_conclusions) for item in interpretations
            ),
        },
        "fallback_used": any(result.decision.fallback_used for result in results),
        "urgent_triggered": any(result.fall_assessment.urgent_triggered for result in results),
        "provisional_urgent_event": any(event.provisional_urgent for event in event_values),
        "room_level_event_count": sum(int(event.room_level_only) for event in event_values),
        "attention_suppressed": any(result.decision.attention_suppressed for result in results),
        "anomaly_final_state": final_episode.state.value if final_episode else None,
        "closed_anomaly_count": sum(
            int(episode.state == AnomalyState.CLOSED)
            for episode in episodes.values()
        ),
        "event_status": final_event.status.value if final_event else None,
        "resolved_event_count": sum(
            int(event.status == EventStatus.RESOLVED)
            for event in event_values
        ),
        "recurrence_linked": any(bool(event.related_event_ids) for event in event_values),
        "evaluated_learning_windows": len(guard_values),
        "eligible_learning_windows": sum(int(guard.eligible) for guard in guard_values),
        "contaminated_learning_windows": contaminated,
        "semantic_context_active": False,
        "numerical_baseline_changed": False,
        "clean_adoption_windows": 0,
        "fixture_shortcut": definition.fixture_shortcut,
    }
    if extras:
        record.update(extras)
    return record


def _monitoring_for(scenario_id: str) -> MonitoringSnapshot:
    if scenario_id == "random_bathroom_away":
        return derive_monitoring_snapshot(assignment_valid=True, device_healthy=True, presence=PresenceState.RESIDENT_AWAY, signal_quality=1.0)
    if scenario_id == "visitor_multi_person":
        return derive_monitoring_snapshot(assignment_valid=True, device_healthy=True, presence=PresenceState.POSSIBLE_MULTI_PERSON, signal_quality=1.0)
    if scenario_id in {"missing_signal", "respiration_quality_limited", "contradictory_sensors"}:
        return derive_monitoring_snapshot(assignment_valid=True, device_healthy=True, presence=PresenceState.RESIDENT_PRESENT, signal_quality=0.4)
    if scenario_id in {"stale_signal", "frozen_signal", "setup_change"}:
        return derive_monitoring_snapshot(assignment_valid=True, device_healthy=False, presence=PresenceState.RESIDENT_PRESENT, signal_quality=0.0)
    return _active_monitoring()


def _run_frames(
    definition: ScenarioDefinition,
    start: datetime,
    frames: tuple[AlignedFrame, ...],
    *,
    baseline: BaselineSnapshot,
    provider_mode: str | None,
    anomaly_ids: tuple[str, ...] | None = None,
    memory: ResidentMemory | None = None,
    resident_away: bool = False,
    possible_multiple_people: bool = False,
    setup_change: bool = False,
    purpose: FeaturePurpose = FeaturePurpose.MOVEMENT,
    relevant_context_entry_ids: tuple[str, ...] = (),
    llm_client: LLMClient | None = None,
    frame_transform: FrameTransform | None = None,
) -> tuple[
    MonitoringIntelligenceEngine,
    list[IntelligenceResult],
    list[tuple[object, bool]],
    ScenarioLLMClient | RecordingLLMClient | None,
]:
    engine, client = _engine(provider_mode, llm_client)
    if frame_transform is not None:
        frames = frame_transform(frames)
        if not isinstance(frames, tuple) or not frames:
            raise ValueError("frame_transform must return a non-empty tuple")
    memory = memory or _memory(start=start)
    monitoring = _monitoring_for(definition.scenario_id)
    results: list[IntelligenceResult] = []
    learning: list[tuple[object, bool]] = []
    if anomaly_ids is not None and len(anomaly_ids) != len(frames):
        raise ValueError("anomaly_ids must match the transformed frame count")
    ids = anomaly_ids or tuple(f"{definition.scenario_id}_anomaly_1" for _ in frames)
    for frame, anomaly_id in zip(frames, ids, strict=True):
        result = _process(
            engine,
            frame,
            baseline=baseline,
            anomaly_id=anomaly_id,
            memory=memory,
            resident_away=resident_away,
            possible_multiple_people=possible_multiple_people,
            relevant_context_entry_ids=relevant_context_entry_ids,
        )
        results.append(result)
        learning.append(
            _learning_record(
                frame,
                result,
                monitoring,
                purpose=purpose,
                setup_change=setup_change,
            )
        )
    return engine, results, learning, client


def _simple_scenario(
    definition: ScenarioDefinition,
    start: datetime,
    *,
    llm_client: LLMClient | None = None,
    frame_transform: FrameTransform | None = None,
) -> dict[str, Any]:
    scenario_id = definition.scenario_id
    monitoring = _monitoring_for(scenario_id)
    feature_name = "movement_energy"
    purpose = FeaturePurpose.MOVEMENT
    unit = "normalized"
    provider_mode: str | None = None
    values: tuple[float | None, ...] = (0.0,)
    quality = QualityClass.GOOD
    reasons: tuple[str, ...] = ()
    memory = _memory(start=start)
    extras: tuple[FeatureSpec, ...] = ()
    resident_away = False
    possible_multi = False
    setup_change = False

    if scenario_id == "random_bathroom_away":
        values = (0.8,)
        resident_away = True
    elif scenario_id == "sleep_reading_stillness":
        values = (0.01,)
    elif scenario_id == "flexible_routine":
        values = (0.2,)
        memory = _memory(entry_id="flexible_routine_entry", context_kind="routine", start=start)
    elif scenario_id == "temporary_change":
        values = (0.2,)
        memory = _memory(entry_id="temporary_change_entry", context_kind="temporary_change", start=start, effective_until=start + timedelta(hours=2))
    elif scenario_id == "visitor_multi_person":
        values = (0.8,)
        possible_multi = True
    elif scenario_id == "sustained_movement_change":
        values = (0.5, 0.5, 0.5)
        provider_mode = "caregiver_event"
        memory = _memory(
            entry_id="sustained_movement_context",
            context_kind="habit",
            start=start,
        )
    elif scenario_id == "repetitive_movement":
        feature_name = "repetitive_movement_score"
        values = (0.6, 0.6, 0.6)
        provider_mode = "caregiver_event"
    elif scenario_id == "inactivity":
        feature_name = "inactivity_seconds"
        unit = "synthetic_scaled_seconds"
        values = (0.5, 0.5, 0.5)
        provider_mode = "caregiver_event"
    elif scenario_id == "respiration_quality_limited":
        feature_name = "respiratory_rate"
        unit = "synthetic_breaths_per_min"
        purpose = FeaturePurpose.RESPIRATION
        values = (20.0,)
        quality = QualityClass.LIMITED
        reasons = ("respiration_quality_limited",)
    elif scenario_id == "unknown_anomaly":
        feature_name = "thermal_foreground_area"
        values = (0.5, 0.5, 0.5)
        provider_mode = "caregiver_event"
    elif scenario_id == "missing_signal":
        values = (None,)
        quality = QualityClass.UNUSABLE
        reasons = ("missing",)
    elif scenario_id in {"stale_signal", "frozen_signal"}:
        values = (0.5,)
        quality = QualityClass.LIMITED
        reasons = (("stale",) if scenario_id == "stale_signal" else ("frozen",))
    elif scenario_id == "setup_change":
        values = (0.5,)
        setup_change = True
        extras = (_feature("device_moved", True, "boolean", FeaturePurpose.MOVEMENT),)
    elif scenario_id == "llm_unavailable":
        values = (0.5, 0.5, 0.5)
        provider_mode = "unavailable"
    elif scenario_id == "llm_invalid_output":
        values = (0.5, 0.5, 0.5)
        provider_mode = "invalid"

    baseline_samples = (0.0, 0.0, 0.0, 0.0, 0.0)
    baseline = _baseline(
        scenario_id,
        start,
        feature_name=feature_name,
        unit=unit,
        purpose=purpose,
        samples=baseline_samples,
    )
    frames = tuple(
        _numeric_frame(
            scenario_id,
            start,
            second,
            value,
            feature_name=feature_name,
            unit=unit,
            purpose=purpose,
            quality=quality,
            reasons=reasons,
            extras=extras,
        )
        for second, value in enumerate(values)
    )
    _engine_value, results, learning, client = _run_frames(
        definition,
        start,
        frames,
        baseline=baseline,
        provider_mode=provider_mode,
        memory=memory,
        resident_away=resident_away,
        possible_multiple_people=possible_multi,
        setup_change=setup_change,
        purpose=purpose,
        relevant_context_entry_ids=(
            ("sustained_movement_context",)
            if scenario_id == "sustained_movement_change"
            else ()
        ),
        llm_client=llm_client,
        frame_transform=frame_transform,
    )
    extra_values: dict[str, Any] = {}
    if scenario_id in {"flexible_routine", "temporary_change"}:
        extra_values["semantic_context_active"] = bool(memory.relevant_entries(start))
    if scenario_id == "setup_change":
        progress = CalibrationProgress(
            setup_version=SETUP_VERSION,
            status=BaselineStatus.ESTABLISHED,
            eligible_windows=10,
            excluded_windows=0,
            reason="synthetic_initial_setup",
            dimension_progress=(
                CalibrationDimensionProgress("movement_energy", BaselineStatus.ESTABLISHED, 10, 0),
                CalibrationDimensionProgress("respiratory_rate", BaselineStatus.ESTABLISHED, 10, 0),
            ),
        )
        recalibrated = start_recalibration(
            progress,
            new_setup_version="setup_synthetic_v2",
            reason="synthetic_device_moved",
            actor_id="operator_synthetic",
            changed_at=start,
            affected_dimensions=("movement_energy",),
        )
        extra_values["setup_version_changed"] = recalibrated.setup_version != progress.setup_version
        extra_values["affected_dimensions"] = list(recalibrated.setup_change_history[-1].affected_dimensions)
    if scenario_id == "sustained_movement_change":
        if client is None or not client.requests:
            raise RuntimeError("synthetic selected-context scenario did not invoke AI")
        request = client.requests[-1]
        raw_result = client.raw_results[-1] if client.raw_results else None
        extra_values["context_provenance"] = {
            "explicit_selection": True,
            "selected_entry_ids": ["sustained_movement_context"],
            "retrieved_context_refs": list(request.retrieved_context_refs),
            "result_request_fingerprint_matches": (
                raw_result is not None
                and raw_result.request_fingerprint == request.request_fingerprint
            ),
        }
    return _finalize(definition, start, results, learning, client, monitoring.state, extras=extra_values)


def _fall_scenario(
    definition: ScenarioDefinition,
    start: datetime,
    *,
    llm_client: LLMClient | None = None,
    frame_transform: FrameTransform | None = None,
) -> dict[str, Any]:
    baseline = _baseline(definition.scenario_id, start, feature_name="unused_feature")
    frames = _fall_sequence(definition.scenario_id, start)
    _engine_value, results, learning, client = _run_frames(
        definition,
        start,
        frames,
        baseline=baseline,
        provider_mode=None,
        llm_client=llm_client,
        frame_transform=frame_transform,
    )
    return _finalize(definition, start, results, learning, client, MonitoringState.ACTIVE)


def _fall_confounder(
    definition: ScenarioDefinition,
    start: datetime,
    *,
    llm_client: LLMClient | None = None,
    frame_transform: FrameTransform | None = None,
) -> dict[str, Any]:
    baseline = _baseline(definition.scenario_id, start, feature_name="unused_feature")
    values = (
        (1.7, 0.0, "upright_like", 0.4),
        (1.2, -0.3, "seated_like", 0.35),
        (0.9, -0.3, "kneeling_like", 0.3),
    )
    frames = tuple(
        _fall_frame(
            definition.scenario_id,
            start,
            second,
            height=height,
            velocity=velocity,
            position=position,
            movement=movement,
        )
        for second, (height, velocity, position, movement) in enumerate(values)
    )
    _engine_value, results, learning, client = _run_frames(
        definition,
        start,
        frames,
        baseline=baseline,
        provider_mode=None,
        llm_client=llm_client,
        frame_transform=frame_transform,
    )
    return _finalize(definition, start, results, learning, client, MonitoringState.ACTIVE)


def _contradictory(
    definition: ScenarioDefinition,
    start: datetime,
    *,
    llm_client: LLMClient | None = None,
    frame_transform: FrameTransform | None = None,
) -> dict[str, Any]:
    baseline = _baseline(definition.scenario_id, start, feature_name="unused_feature")
    frame = _fall_frame(
        definition.scenario_id,
        start,
        0,
        height=1.0,
        velocity=0.0,
        position="floor_like",
        movement=0.4,
        thermal_position="upright_like",
    )
    _engine_value, results, learning, client = _run_frames(
        definition,
        start,
        (frame,),
        baseline=baseline,
        provider_mode=None,
        llm_client=llm_client,
        frame_transform=frame_transform,
    )
    return _finalize(definition, start, results, learning, client, MonitoringState.LIMITED)


def _expected_behavior(start: datetime) -> tuple[MemoryEntry, ResidentMemory]:
    memory = _memory(entry_id="expected_new_behavior_entry", context_kind="expected_new_behavior", start=start)
    return memory.entries[0], memory


def _adoption_scenario(
    definition: ScenarioDefinition,
    start: datetime,
    *,
    values: tuple[float, ...],
    llm_client: LLMClient | None = None,
    frame_transform: FrameTransform | None = None,
) -> dict[str, Any]:
    baseline = _baseline(definition.scenario_id, start)
    expected_behavior, memory = _expected_behavior(start)
    frames = tuple(
        _numeric_frame(definition.scenario_id, start, second, value)
        for second, value in enumerate(values)
    )
    _engine_value, results, learning, client = _run_frames(
        definition,
        start,
        frames,
        baseline=baseline,
        provider_mode=None,
        memory=memory,
        llm_client=llm_client,
        frame_transform=frame_transform,
    )
    candidate = NewNormalCandidate(
        candidate_id=f"{definition.scenario_id}_candidate",
        resident_id=RESIDENT_ID,
        feature_name="movement_energy",
        unit="normalized",
        purpose=FeaturePurpose.MOVEMENT,
        context_key=CONTEXT_KEY,
        semantic_context_entry_id=expected_behavior.entry_id,
        setup_version=SETUP_VERSION,
    )
    calibration = CalibrationProgress(
        setup_version=SETUP_VERSION,
        status=BaselineStatus.ESTABLISHED,
        eligible_windows=20,
        excluded_windows=0,
        reason="synthetic_established",
    )
    published = None
    for guard, _unsafe in learning:
        candidate, published = advance_new_normal(
            candidate,
            baseline=baseline,
            expected_behavior=expected_behavior,
            learning_guard=guard,
            calibration_progress=calibration,
            new_baseline_id=f"{definition.scenario_id}_baseline_v2",
            policy=BaselinePolicy(),
        )
    return _finalize(
        definition,
        start,
        results,
        learning,
        client,
        MonitoringState.ACTIVE,
        extras={
            "semantic_context_active": bool(memory.relevant_entries(start)),
            "numerical_baseline_changed": published is not None,
            "clean_adoption_windows": candidate.clean_windows,
        },
    )


def _acknowledgment_scenario(
    definition: ScenarioDefinition,
    start: datetime,
    *,
    llm_client: LLMClient | None = None,
    frame_transform: FrameTransform | None = None,
) -> dict[str, Any]:
    baseline = _baseline(definition.scenario_id, start)
    frames = tuple(_numeric_frame(definition.scenario_id, start, second, 0.5) for second in range(3))
    engine, results, learning, client = _run_frames(
        definition,
        start,
        frames,
        baseline=baseline,
        provider_mode="caregiver_event",
        llm_client=llm_client,
        frame_transform=frame_transform,
    )
    opened = results[-1].event
    if opened is None:
        raise RuntimeError("synthetic acknowledgment scenario did not open an event")
    engine.acknowledge_event(
        opened.event_id,
        actor_id="operator_synthetic",
        at=results[-1].observation.window_end + timedelta(seconds=1),
    )
    continuation = _numeric_frame(definition.scenario_id, start, 4, 0.5)
    if frame_transform is not None:
        continuation = frame_transform((continuation,))[0]
    continued = _process(engine, continuation, baseline=baseline, anomaly_id=f"{definition.scenario_id}_anomaly_1", memory=_memory(start=start))
    results.append(continued)
    learning.append(_learning_record(continuation, continued, _active_monitoring()))
    return _finalize(definition, start, results, learning, client, MonitoringState.ACTIVE)


def _recurrence_scenario(
    definition: ScenarioDefinition,
    start: datetime,
    *,
    llm_client: LLMClient | None = None,
    frame_transform: FrameTransform | None = None,
) -> dict[str, Any]:
    baseline = _baseline(definition.scenario_id, start)
    frames = tuple(
        _numeric_frame(definition.scenario_id, start, second, value)
        for second, value in enumerate((0.5, 0.5, 0.5, 0.0, 0.0, 0.0, 0.5, 0.5, 0.5))
    )
    anomaly_ids = tuple(
        f"{definition.scenario_id}_anomaly_{1 if second < 6 else 2}"
        for second in range(9)
    )
    _engine_value, results, learning, client = _run_frames(
        definition,
        start,
        frames,
        baseline=baseline,
        provider_mode="caregiver_event",
        anomaly_ids=anomaly_ids,
        llm_client=llm_client,
        frame_transform=frame_transform,
    )
    return _finalize(definition, start, results, learning, client, MonitoringState.ACTIVE)


def run_repository_restart_story() -> dict[str, bool]:
    """Persist and rehydrate one real anomaly-to-event chain across engine reopen."""

    definition = next(
        item for item in SCENARIOS if item.scenario_id == "repetitive_movement"
    )
    start = SUITE_START + timedelta(hours=4)
    baseline = _baseline(
        "repository_restart",
        start,
        feature_name="repetitive_movement_score",
    )
    frames = tuple(
        _numeric_frame(
            "repository_restart",
            start,
            second,
            0.6,
            feature_name="repetitive_movement_score",
        )
        for second in range(3)
    )
    _engine_value, results, _learning, client = _run_frames(
        definition,
        start,
        frames,
        baseline=baseline,
        provider_mode="caregiver_event",
        anomaly_ids=tuple("repository_restart_anomaly" for _ in frames),
    )
    final = results[-1]
    if (
        final.anomaly is None
        or final.evidence is None
        or final.interpretation is None
        or final.event is None
        or client is None
        or not client.requests
    ):
        raise RuntimeError("repository restart fixture did not produce a full chain")
    request = client.requests[-1]
    packet = final.evidence
    event = final.event
    bridge = event.bridge_records[-1]
    disposition = DispositionRecord(
        disposition_id="repository_restart_disposition",
        resident_id=RESIDENT_ID,
        room_id=ROOM_ID,
        anomaly_id=packet.anomaly_id,
        evidence_kind=BridgeEvidenceKind.PACKET,
        evidence_revision=packet.packet_revision,
        packet_revision=packet.packet_revision,
        decided_at=packet.current_time,
        decision=final.decision,
        interpretation_id=final.interpretation.interpretation_id,
        event_id=event.event_id,
    )

    with TemporaryDirectory(prefix="phase5-restart-") as temporary_directory:
        database_path = Path(temporary_directory) / "monitoring.sqlite3"
        database_url = f"sqlite+pysqlite:///{database_path}"
        first_engine = create_engine_for_url(database_url)
        Base.metadata.create_all(first_engine)
        first_session_factory = create_session_factory(first_engine)
        with first_session_factory() as session:
            seed_synthetic_story(session)
            repository = IntelligenceRepository(session)
            repository.save_baseline(TENANT_ID, baseline, start)
            repository.save_anomaly_revision(TENANT_ID, final.anomaly, packet)
            repository.save_interpretation(
                TENANT_ID,
                request,
                final.interpretation,
                packet.current_time,
            )
            EventRepository(session).save(TENANT_ID, event, expected_version=0)
            repository.save_disposition(TENANT_ID, disposition)
            session.commit()
        first_engine.dispose()

        second_engine = create_engine_for_url(database_url)
        second_session_factory = create_session_factory(second_engine)
        with second_session_factory() as session:
            repository = IntelligenceRepository(session)
            hydrated_anomaly = repository.latest_anomaly(
                TENANT_ID,
                packet.anomaly_id,
            )
            hydrated_interpretation = repository.find_interpretation(
                TENANT_ID,
                final.interpretation.interpretation_id,
            )
            hydrated_disposition = repository.find_disposition(
                TENANT_ID,
                disposition.disposition_id,
            )
            hydrated_event = EventRepository(session).get(
                TENANT_ID,
                event.event_id,
            ).event
            hydrated_bridge = repository.find_event_bridge(
                TENANT_ID,
                bridge.idempotency_key,
            )
            replayed_event = EventStore(
                initial_events=(hydrated_event,)
            ).record_signal(
                resident_id=bridge.resident_id,
                room_id=bridge.room_id,
                objective_family=bridge.objective_family,
                headline=bridge.headline,
                priority=bridge.priority,
                observed_at=bridge.observed_at,
                actor_id=bridge.actor_id,
                resident_memory=ResidentMemory(RESIDENT_ID, 0, ()),
                source_anomaly_id=bridge.source_anomaly_id,
                evidence_revision=bridge.evidence_revision,
                bridge_idempotency_key=bridge.idempotency_key,
                provisional_urgent=bridge.provisional_urgent,
                evidence_kind=bridge.evidence_kind,
                room_level_only=bridge.room_level_only,
                related_event_ids=bridge.related_event_ids,
            )
        second_engine.dispose()

    return {
        "anomaly_revision_hydrated": (
            hydrated_anomaly is not None
            and hydrated_anomaly.update == final.anomaly
            and hydrated_anomaly.packet == packet
        ),
        "interpretation_hydrated": (
            hydrated_interpretation is not None
            and hydrated_interpretation.request == request
            and hydrated_interpretation.result == final.interpretation
        ),
        "disposition_hydrated": hydrated_disposition == disposition,
        "bridge_hydrated": (
            hydrated_bridge is not None
            and hydrated_bridge.record == bridge
            and hydrated_bridge.event_id == event.event_id
        ),
        "event_hydrated": hydrated_event == event,
        "event_lineage_matches": (
            hydrated_event.source_anomaly_id == packet.anomaly_id
            and hydrated_event.latest_evidence_revision == packet.packet_revision
            and bridge.idempotency_key in hydrated_event.bridge_idempotency_keys
        ),
        "exact_signal_replay_deduplicated": replayed_event == hydrated_event,
    }


def run_scenario(
    scenario_id: str,
    *,
    llm_client: LLMClient | None = None,
    frame_transform: FrameTransform | None = None,
) -> ScenarioExecution:
    """Run one stable fixture and optionally capture an injected provider exchange."""

    definitions = {definition.scenario_id: definition for definition in SCENARIOS}
    if scenario_id not in definitions:
        raise ValueError(f"unknown scenario_id: {scenario_id}")
    definition = definitions[scenario_id]
    index = REQUIRED_SCENARIO_IDS.index(scenario_id)
    start = SUITE_START + timedelta(minutes=index * 5)
    capture = RecordingLLMClient(llm_client) if llm_client is not None else None
    options = {"llm_client": capture, "frame_transform": frame_transform}
    if scenario_id == "fall_like":
        record = _fall_scenario(definition, start, **options)
    elif scenario_id == "fall_like_confounder":
        record = _fall_confounder(definition, start, **options)
    elif scenario_id == "contradictory_sensors":
        record = _contradictory(definition, start, **options)
    elif scenario_id == "preentered_new_behavior":
        record = _adoption_scenario(definition, start, values=(0.2,), **options)
    elif scenario_id == "post_event_new_behavior":
        record = _adoption_scenario(
            definition,
            start,
            values=(0.2, 0.21, 0.22, 0.23, 0.24),
            **options,
        )
    elif scenario_id == "continuing_acknowledged_anomaly":
        record = _acknowledgment_scenario(definition, start, **options)
    elif scenario_id == "recurrence_after_recovery":
        record = _recurrence_scenario(definition, start, **options)
    else:
        record = _simple_scenario(definition, start, **options)
    return ScenarioExecution(
        scenario_id=scenario_id,
        record=record,
        interpretation_requests=tuple(capture.requests) if capture else (),
        interpretation_results=tuple(capture.raw_results) if capture else (),
        provider_errors=tuple(capture.errors) if capture else (),
    )


def run_scenarios() -> list[dict[str, Any]]:
    """Run each stable fixture through actual Phase 5 components."""

    return [run_scenario(definition.scenario_id).record for definition in SCENARIOS]


__all__ = [
    "REQUIRED_SCENARIO_IDS",
    "SCENARIOS",
    "ScenarioDefinition",
    "ScenarioExecution",
    "run_repository_restart_story",
    "run_scenario",
    "run_scenarios",
    "scenario_definitions",
]
