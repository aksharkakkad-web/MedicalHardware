"""Synthetic, in-memory demonstration of the complete monitoring journey."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from backend.app.domain.calibration import (
    BaselineStatus,
    CalibrationPolicy,
    CalibrationProgress,
    observe_calibration_window,
    start_recalibration,
)
from backend.app.domain.events import (
    EventPriority,
    EventStatus,
    EventStore,
    MonitoringEvent,
    ResolutionOutcome,
    SyntheticEventEpisodePolicy,
)
from backend.app.domain.feedback import (
    FeedbackService,
    LearningDecision,
    ResidentMemory,
)
from backend.app.domain.monitoring import (
    MonitoringSnapshot,
    MonitoringState,
    PresenceState,
    derive_monitoring_snapshot,
)


@dataclass(frozen=True)
class ToyScenarioStep:
    name: str
    occurred_at: datetime
    schema_version: str = "1.0"


@dataclass(frozen=True)
class ToyScenarioResult:
    timeline: tuple[ToyScenarioStep, ...]
    calibration_history: tuple[BaselineStatus, ...]
    away_snapshot: MonitoringSnapshot
    visitor_snapshot: MonitoringSnapshot
    resumed_snapshot: MonitoringSnapshot
    calibration_after_away: CalibrationProgress
    calibration_after_visitor: CalibrationProgress
    blocked_presence_states: tuple[PresenceState, ...]
    first_event: MonitoringEvent
    learning_decision: LearningDecision
    baseline_progress_before_feedback: CalibrationProgress
    baseline_progress_after_feedback: CalibrationProgress
    baseline_progress_after_controlled_update: CalibrationProgress
    recurrence_event: MonitoringEvent
    recalibration: CalibrationProgress
    corrected_memory: ResidentMemory
    schema_version: str = "1.0"

    @property
    def calibration_status(self) -> BaselineStatus:
        return self.baseline_progress_before_feedback.status

    @property
    def away_state(self) -> MonitoringState:
        return self.away_snapshot.state

    @property
    def visitor_state(self) -> MonitoringState:
        return self.visitor_snapshot.state

    @property
    def resumed_state(self) -> MonitoringState:
        return self.resumed_snapshot.state

    @property
    def first_event_status(self) -> EventStatus:
        return self.first_event.status

    @property
    def memory_updated(self) -> bool:
        return self.learning_decision.memory_updated

    @property
    def baseline_window_eligible(self) -> bool:
        return self.learning_decision.baseline_window_eligible

    @property
    def recurrence_count(self) -> int:
        return self.recurrence_event.recurrence_count

    @property
    def events_are_linked(self) -> bool:
        return self.first_event.event_id in self.recurrence_event.related_event_ids


def run_complete_toy_scenario() -> ToyScenarioResult:
    """Run a deterministic synthetic room journey across all V1 domain slices."""
    started = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    timeline: list[ToyScenarioStep] = []
    policy = CalibrationPolicy(
        partial_eligible_windows=2,
        established_eligible_windows=4,
    )
    progress = CalibrationProgress.new(
        "setup_room_214_v1",
        dimensions=("movement", "respiratory_rate"),
    )
    calibration_history = [progress.status]
    active = derive_monitoring_snapshot(
        assignment_valid=True,
        device_healthy=True,
        presence=PresenceState.RESIDENT_PRESENT,
        signal_quality=0.9,
    )
    for window in range(4):
        progress = observe_calibration_window(
            progress,
            policy=policy,
            monitoring_snapshot=active,
            concerning=False,
            unresolved_anomaly=False,
        )
        calibration_history.append(progress.status)
        timeline.append(
            ToyScenarioStep(
                name=f"calibration_window_{window + 1}",
                occurred_at=started + timedelta(minutes=window),
            )
        )

    away = derive_monitoring_snapshot(
        assignment_valid=True,
        device_healthy=True,
        presence=PresenceState.RESIDENT_AWAY,
        signal_quality=0.9,
    )
    progress = observe_calibration_window(
        progress,
        policy=policy,
        monitoring_snapshot=away,
        concerning=False,
        unresolved_anomaly=False,
    )
    calibration_after_away = progress
    timeline.append(
        ToyScenarioStep(
            name="resident_away",
            occurred_at=started + timedelta(minutes=5),
        )
    )

    visitor = derive_monitoring_snapshot(
        assignment_valid=True,
        device_healthy=True,
        presence=PresenceState.POSSIBLE_MULTI_PERSON,
        signal_quality=0.9,
    )
    progress = observe_calibration_window(
        progress,
        policy=policy,
        monitoring_snapshot=visitor,
        concerning=False,
        unresolved_anomaly=False,
    )
    calibration_after_visitor = progress
    timeline.append(
        ToyScenarioStep(
            name="visitor_present",
            occurred_at=started + timedelta(minutes=6),
        )
    )

    events = EventStore(
        policy=SyntheticEventEpisodePolicy(
            quiet_gap=timedelta(minutes=5),
            policy_version="synthetic_toy_story_episode_v1",
        )
    )
    blocked_presence_states: list[PresenceState] = []
    for offset, snapshot in ((5, away), (6, visitor)):
        try:
            events.record_signal(
                resident_id="resident_demo_a",
                room_id="room_214",
                objective_family="unusual_movement",
                headline="Unusual movement detected",
                priority=EventPriority.HIGH,
                observed_at=started + timedelta(minutes=offset),
                monitoring_snapshot=snapshot,
            )
        except ValueError:
            blocked_presence_states.append(snapshot.presence)
        else:
            raise AssertionError("unsuitable monitoring created a resident event")

    resumed = derive_monitoring_snapshot(
        assignment_valid=True,
        device_healthy=True,
        presence=PresenceState.RESIDENT_PRESENT,
        signal_quality=0.9,
    )
    progress = observe_calibration_window(
        progress,
        policy=policy,
        monitoring_snapshot=resumed,
        concerning=False,
        unresolved_anomaly=False,
    )
    timeline.append(
        ToyScenarioStep(
            name="monitoring_resumed",
            occurred_at=started + timedelta(minutes=7),
        )
    )

    events.record_signal(
        resident_id="resident_demo_a",
        room_id="room_214",
        objective_family="unusual_movement",
        headline="Unusual movement detected",
        priority=EventPriority.WATCH,
        observed_at=started + timedelta(minutes=10),
        actor_id="system:anomaly_engine",
        monitoring_snapshot=resumed,
    )
    first = events.record_signal(
        resident_id="resident_demo_a",
        room_id="room_214",
        objective_family="unusual_movement",
        headline="Unusual movement detected",
        priority=EventPriority.HIGH,
        observed_at=started + timedelta(minutes=12),
        actor_id="system:warning_policy",
        monitoring_snapshot=resumed,
    )
    timeline.append(
        ToyScenarioStep(
            name="event_grouped",
            occurred_at=started + timedelta(minutes=12),
        )
    )
    first = events.mark_overdue(
        first.event_id,
        at=started + timedelta(minutes=18),
    )
    timeline.append(
        ToyScenarioStep(
            name="event_overdue",
            occurred_at=started + timedelta(minutes=18),
        )
    )
    first = events.acknowledge(
        first.event_id,
        actor_id="operator_001",
        at=started + timedelta(minutes=19),
    )
    first = events.check(
        first.event_id,
        actor_id="operator_001",
        at=started + timedelta(minutes=20),
    )
    first = events.resolve(
        first.event_id,
        ResolutionOutcome.FALSE_POSITIVE,
        actor_id="operator_001",
        at=started + timedelta(minutes=21),
    )

    baseline_before_feedback = progress
    feedback = FeedbackService()
    learning = feedback.submit_feedback(
        event=first,
        actor_id="operator_001",
        actual_event_label="Assisted Transfer",
        routine=True,
        created_at=started + timedelta(minutes=22),
    )
    baseline_after_feedback = progress
    timeline.append(
        ToyScenarioStep(
            name="feedback_recorded",
            occurred_at=started + timedelta(minutes=22),
        )
    )
    progress = observe_calibration_window(
        progress,
        policy=policy,
        learning_allowed=learning.baseline_window_eligible,
        concerning=False,
        unresolved_anomaly=False,
    )

    recurrence = events.record_signal(
        resident_id="resident_demo_a",
        room_id="room_214",
        objective_family="unusual_movement",
        headline="Unusual movement detected",
        priority=EventPriority.HIGH,
        observed_at=started + timedelta(minutes=30),
        actor_id="system:warning_policy",
        monitoring_snapshot=resumed,
        resident_memory=learning.memory,
    )
    timeline.append(
        ToyScenarioStep(
            name="recurrence_created",
            occurred_at=started + timedelta(minutes=30),
        )
    )

    recalibration = start_recalibration(
        progress,
        new_setup_version="setup_room_214_v2",
        reason="device_moved",
        actor_id="operator_007",
        changed_at=started + timedelta(minutes=31),
        affected_dimensions=("movement",),
    )
    timeline.append(
        ToyScenarioStep(
            name="setup_changed",
            occurred_at=started + timedelta(minutes=31),
        )
    )

    corrected_memory = feedback.correct_memory(
        resident_id="resident_demo_a",
        entry_id=learning.memory.active_entries[0].entry_id,
        actor_id="operator_002",
        reason="Routine no longer applies",
        corrected_at=started + timedelta(minutes=32),
    )
    timeline.append(
        ToyScenarioStep(
            name="memory_corrected",
            occurred_at=started + timedelta(minutes=32),
        )
    )

    return ToyScenarioResult(
        timeline=tuple(timeline),
        calibration_history=tuple(calibration_history),
        away_snapshot=away,
        visitor_snapshot=visitor,
        resumed_snapshot=resumed,
        calibration_after_away=calibration_after_away,
        calibration_after_visitor=calibration_after_visitor,
        blocked_presence_states=tuple(blocked_presence_states),
        first_event=first,
        learning_decision=learning,
        baseline_progress_before_feedback=baseline_before_feedback,
        baseline_progress_after_feedback=baseline_after_feedback,
        baseline_progress_after_controlled_update=progress,
        recurrence_event=recurrence,
        recalibration=recalibration,
        corrected_memory=corrected_memory,
    )
