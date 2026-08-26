"""Synthetic, in-memory demonstration of the complete monitoring journey."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from backend.app.domain.calibration import (
    BaselineStatus,
    CalibrationPolicy,
    CalibrationProgress,
    observe_calibration_window,
)
from backend.app.domain.events import (
    EventPriority,
    EventStatus,
    EventStore,
    ResolutionOutcome,
)
from backend.app.domain.feedback import FeedbackService
from backend.app.domain.monitoring import (
    MonitoringState,
    PresenceState,
    derive_monitoring_snapshot,
)


@dataclass(frozen=True)
class ToyScenarioResult:
    calibration_status: BaselineStatus
    away_state: MonitoringState
    visitor_state: MonitoringState
    first_event_status: EventStatus
    memory_updated: bool
    baseline_window_eligible: bool
    recurrence_count: int
    events_are_linked: bool


def run_complete_toy_scenario() -> ToyScenarioResult:
    """Run a deterministic synthetic room journey across all V1 domain slices."""
    policy = CalibrationPolicy(
        partial_eligible_windows=2,
        established_eligible_windows=4,
    )
    progress = CalibrationProgress.new("setup_room_214_v1")
    active = derive_monitoring_snapshot(
        assignment_valid=True,
        device_healthy=True,
        presence=PresenceState.RESIDENT_PRESENT,
        signal_quality=0.9,
    )
    for _ in range(4):
        progress = observe_calibration_window(
            progress,
            policy=policy,
            learning_allowed=active.baseline_learning_allowed,
            concerning=False,
            unresolved_anomaly=False,
        )

    away = derive_monitoring_snapshot(
        assignment_valid=True,
        device_healthy=True,
        presence=PresenceState.RESIDENT_AWAY,
        signal_quality=0.9,
    )
    visitor = derive_monitoring_snapshot(
        assignment_valid=True,
        device_healthy=True,
        presence=PresenceState.POSSIBLE_MULTI_PERSON,
        signal_quality=0.9,
    )

    started = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
    events = EventStore(quiet_gap=timedelta(minutes=5))
    first = events.record_signal(
        resident_id="resident_demo_a",
        room_id="room_214",
        objective_family="unusual_movement",
        headline="Unusual movement detected",
        priority=EventPriority.HIGH,
        observed_at=started,
    )
    events.acknowledge(first.event_id)
    events.check(first.event_id)
    first = events.resolve(first.event_id, ResolutionOutcome.FALSE_POSITIVE)

    learning = FeedbackService().submit_feedback(
        event=first,
        actor_id="operator_001",
        actual_event_label="assisted_transfer",
        routine=True,
        created_at=started + timedelta(minutes=2),
    )
    recurrence = events.record_signal(
        resident_id="resident_demo_a",
        room_id="room_214",
        objective_family="unusual_movement",
        headline="Unusual movement detected",
        priority=EventPriority.HIGH,
        observed_at=started + timedelta(minutes=10),
    )

    return ToyScenarioResult(
        calibration_status=progress.status,
        away_state=away.state,
        visitor_state=visitor.state,
        first_event_status=first.status,
        memory_updated=learning.memory_updated,
        baseline_window_eligible=learning.baseline_window_eligible,
        recurrence_count=recurrence.recurrence_count,
        events_are_linked=first.event_id in recurrence.related_event_ids,
    )
