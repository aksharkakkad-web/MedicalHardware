# Backend Domain Toy Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the approved V1 monitoring logic executable end-to-end with synthetic data before adding the database, HTTP API, or real hardware.

**Architecture:** Implement small standard-library Python domain modules for monitoring suitability, calibration, event episodes, feedback, and resident memory. Keep the rules independent from storage and web frameworks so the next phase can place persistent repositories and FastAPI routes around the already-tested behavior.

**Tech Stack:** Python 3.12+, standard library dataclasses/enums, `unittest`

**Spec:** `docs/superpowers/specs/2026-08-26-v1-product-logic-design.md`

## Global Constraints

- V1 supports one assigned resident per monitored room.
- Core sensing inputs are radar, thermal, and Wi-Fi CSI.
- Resident-away and possible-multi-person periods pause resident-specific baseline learning.
- Low-quality or ambiguous data must become limited/unavailable rather than fabricated precision.
- Prototype calibration and warning policies are explicitly synthetic/test-only.
- Resolved events remain immutable; recurrences create new linked events.
- High/critical events never silently expire.
- Feedback can update resident memory quickly but cannot directly rewrite warnings or the numerical baseline.
- No real PHI, medical claims, or invented clinical thresholds.
- This phase intentionally excludes database persistence, HTTP APIs, authentication, notification delivery, real sensor processing, and production threshold selection.

---

### Task 1: Monitoring Suitability State

**Files:**
- Create: `backend/app/domain/monitoring.py`
- Create: `tests/monitoring_domain/__init__.py`
- Create: `tests/monitoring_domain/test_monitoring.py`

**Interfaces:**
- Consumes: Approved room/presence behavior from the spec.
- Produces: `PresenceState`, `MonitoringState`, `MonitoringReason`, `MonitoringSnapshot`, and `derive_monitoring_snapshot()` for calibration and scenario tasks.

- [ ] **Step 1: Write the failing monitoring-state tests**

```python
import unittest

from backend.app.domain.monitoring import (
    MonitoringReason,
    MonitoringState,
    PresenceState,
    derive_monitoring_snapshot,
)


class MonitoringSuitabilityTests(unittest.TestCase):
    def test_present_resident_with_good_conditions_is_active(self) -> None:
        snapshot = derive_monitoring_snapshot(
            assignment_valid=True,
            device_healthy=True,
            presence=PresenceState.RESIDENT_PRESENT,
            signal_quality=0.9,
        )

        self.assertEqual(snapshot.state, MonitoringState.ACTIVE)
        self.assertTrue(snapshot.baseline_learning_allowed)
        self.assertEqual(snapshot.reasons, ())

    def test_resident_away_pauses_learning_without_warning(self) -> None:
        snapshot = derive_monitoring_snapshot(
            assignment_valid=True,
            device_healthy=True,
            presence=PresenceState.RESIDENT_AWAY,
            signal_quality=0.9,
        )

        self.assertEqual(snapshot.state, MonitoringState.PAUSED)
        self.assertFalse(snapshot.baseline_learning_allowed)
        self.assertEqual(snapshot.reasons, (MonitoringReason.RESIDENT_AWAY,))

    def test_possible_multiple_people_limits_resident_monitoring(self) -> None:
        snapshot = derive_monitoring_snapshot(
            assignment_valid=True,
            device_healthy=True,
            presence=PresenceState.POSSIBLE_MULTI_PERSON,
            signal_quality=0.9,
        )

        self.assertEqual(snapshot.state, MonitoringState.LIMITED)
        self.assertFalse(snapshot.baseline_learning_allowed)
        self.assertIn(MonitoringReason.POSSIBLE_MULTI_PERSON, snapshot.reasons)

    def test_missing_assignment_makes_monitoring_unavailable(self) -> None:
        snapshot = derive_monitoring_snapshot(
            assignment_valid=False,
            device_healthy=True,
            presence=PresenceState.RESIDENT_PRESENT,
            signal_quality=0.9,
        )

        self.assertEqual(snapshot.state, MonitoringState.UNAVAILABLE)
        self.assertIn(MonitoringReason.ASSIGNMENT_INVALID, snapshot.reasons)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify the missing-domain failure**

Run: `python3 -m unittest tests/monitoring_domain/test_monitoring.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.domain.monitoring'`.

- [ ] **Step 3: Implement monitoring suitability**

```python
from dataclasses import dataclass
from enum import StrEnum


class PresenceState(StrEnum):
    UNKNOWN = "unknown"
    RESIDENT_PRESENT = "resident_present"
    RESIDENT_AWAY = "resident_away"
    POSSIBLE_MULTI_PERSON = "possible_multi_person"


class MonitoringState(StrEnum):
    ACTIVE = "active"
    LIMITED = "limited"
    PAUSED = "paused"
    UNAVAILABLE = "unavailable"


class MonitoringReason(StrEnum):
    ASSIGNMENT_INVALID = "assignment_invalid"
    DEVICE_UNHEALTHY = "device_unhealthy"
    RESIDENT_AWAY = "resident_away"
    POSSIBLE_MULTI_PERSON = "possible_multi_person"
    PRESENCE_UNKNOWN = "presence_unknown"
    LOW_SIGNAL_QUALITY = "low_signal_quality"


@dataclass(frozen=True)
class MonitoringSnapshot:
    state: MonitoringState
    presence: PresenceState
    baseline_learning_allowed: bool
    resident_measurements_allowed: bool
    reasons: tuple[MonitoringReason, ...]


def derive_monitoring_snapshot(
    *,
    assignment_valid: bool,
    device_healthy: bool,
    presence: PresenceState,
    signal_quality: float,
    minimum_quality: float = 0.6,
) -> MonitoringSnapshot:
    if not 0.0 <= signal_quality <= 1.0:
        raise ValueError("signal_quality must be between 0.0 and 1.0")

    reasons: list[MonitoringReason] = []
    if not assignment_valid:
        reasons.append(MonitoringReason.ASSIGNMENT_INVALID)
    if not device_healthy:
        reasons.append(MonitoringReason.DEVICE_UNHEALTHY)

    if reasons:
        return MonitoringSnapshot(
            state=MonitoringState.UNAVAILABLE,
            presence=presence,
            baseline_learning_allowed=False,
            resident_measurements_allowed=False,
            reasons=tuple(reasons),
        )

    if presence == PresenceState.RESIDENT_AWAY:
        return MonitoringSnapshot(
            state=MonitoringState.PAUSED,
            presence=presence,
            baseline_learning_allowed=False,
            resident_measurements_allowed=False,
            reasons=(MonitoringReason.RESIDENT_AWAY,),
        )

    if presence == PresenceState.POSSIBLE_MULTI_PERSON:
        return MonitoringSnapshot(
            state=MonitoringState.LIMITED,
            presence=presence,
            baseline_learning_allowed=False,
            resident_measurements_allowed=False,
            reasons=(MonitoringReason.POSSIBLE_MULTI_PERSON,),
        )

    if presence == PresenceState.UNKNOWN:
        reasons.append(MonitoringReason.PRESENCE_UNKNOWN)
    if signal_quality < minimum_quality:
        reasons.append(MonitoringReason.LOW_SIGNAL_QUALITY)

    if reasons:
        return MonitoringSnapshot(
            state=MonitoringState.LIMITED,
            presence=presence,
            baseline_learning_allowed=False,
            resident_measurements_allowed=False,
            reasons=tuple(reasons),
        )

    return MonitoringSnapshot(
        state=MonitoringState.ACTIVE,
        presence=presence,
        baseline_learning_allowed=True,
        resident_measurements_allowed=True,
        reasons=(),
    )
```

- [ ] **Step 4: Run monitoring tests**

Run: `python3 -m unittest tests/monitoring_domain/test_monitoring.py -v`

Expected: 4 tests PASS.

- [ ] **Step 5: Commit the monitoring state**

```bash
git add backend/app/domain/monitoring.py tests/monitoring_domain
git commit -m "feat: model resident monitoring suitability"
```

---

### Task 2: Calibration Eligibility and Recalibration

**Files:**
- Create: `backend/app/domain/calibration.py`
- Create: `tests/calibration_domain/__init__.py`
- Create: `tests/calibration_domain/test_calibration.py`

**Interfaces:**
- Consumes: `MonitoringSnapshot.baseline_learning_allowed` from Task 1.
- Produces: `BaselineStatus`, `CalibrationPolicy`, `CalibrationProgress`, `observe_calibration_window()`, and `start_recalibration()` for the toy scenario.

- [ ] **Step 1: Write failing calibration tests**

```python
import unittest

from backend.app.domain.calibration import (
    BaselineStatus,
    CalibrationPolicy,
    CalibrationProgress,
    observe_calibration_window,
    start_recalibration,
)


class CalibrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = CalibrationPolicy(
            partial_eligible_windows=2,
            established_eligible_windows=4,
        )

    def test_eligible_windows_advance_calibration(self) -> None:
        progress = CalibrationProgress.new("setup_v1")
        self.assertEqual(progress.status, BaselineStatus.NEW)

        for _ in range(2):
            progress = observe_calibration_window(
                progress,
                policy=self.policy,
                learning_allowed=True,
                concerning=False,
                unresolved_anomaly=False,
            )
        self.assertEqual(progress.status, BaselineStatus.PARTIAL)

        for _ in range(2):
            progress = observe_calibration_window(
                progress,
                policy=self.policy,
                learning_allowed=True,
                concerning=False,
                unresolved_anomaly=False,
            )
        self.assertEqual(progress.status, BaselineStatus.ESTABLISHED)

    def test_ineligible_windows_never_advance_calibration(self) -> None:
        progress = CalibrationProgress.new("setup_v1")
        progress = observe_calibration_window(
            progress,
            policy=self.policy,
            learning_allowed=False,
            concerning=False,
            unresolved_anomaly=False,
        )

        self.assertEqual(progress.status, BaselineStatus.CALIBRATING)
        self.assertEqual(progress.eligible_windows, 0)
        self.assertEqual(progress.excluded_windows, 1)

    def test_setup_change_preserves_history_but_restarts_physical_calibration(self) -> None:
        established = CalibrationProgress(
            setup_version="setup_v1",
            status=BaselineStatus.ESTABLISHED,
            eligible_windows=8,
            excluded_windows=2,
            reason="initial_setup",
        )

        recalibrating = start_recalibration(
            established,
            new_setup_version="setup_v2",
            reason="device_moved",
        )

        self.assertEqual(recalibrating.status, BaselineStatus.CALIBRATING)
        self.assertEqual(recalibrating.setup_version, "setup_v2")
        self.assertEqual(recalibrating.eligible_windows, 0)
        self.assertEqual(recalibrating.prior_setup_versions, ("setup_v1",))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the calibration test and verify the missing-domain failure**

Run: `python3 -m unittest tests/calibration_domain/test_calibration.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.domain.calibration'`.

- [ ] **Step 3: Implement calibration policy and progress**

```python
from dataclasses import dataclass, replace
from enum import StrEnum


class BaselineStatus(StrEnum):
    NEW = "new"
    CALIBRATING = "calibrating"
    PARTIAL = "partial"
    ESTABLISHED = "established"


@dataclass(frozen=True)
class CalibrationPolicy:
    partial_eligible_windows: int
    established_eligible_windows: int

    def __post_init__(self) -> None:
        if self.partial_eligible_windows < 1:
            raise ValueError("partial_eligible_windows must be positive")
        if self.established_eligible_windows <= self.partial_eligible_windows:
            raise ValueError("established threshold must exceed partial threshold")


@dataclass(frozen=True)
class CalibrationProgress:
    setup_version: str
    status: BaselineStatus
    eligible_windows: int
    excluded_windows: int
    reason: str
    prior_setup_versions: tuple[str, ...] = ()

    @classmethod
    def new(cls, setup_version: str) -> "CalibrationProgress":
        return cls(
            setup_version=setup_version,
            status=BaselineStatus.NEW,
            eligible_windows=0,
            excluded_windows=0,
            reason="initial_setup",
        )


def observe_calibration_window(
    progress: CalibrationProgress,
    *,
    policy: CalibrationPolicy,
    learning_allowed: bool,
    concerning: bool,
    unresolved_anomaly: bool,
) -> CalibrationProgress:
    eligible = learning_allowed and not concerning and not unresolved_anomaly
    eligible_windows = progress.eligible_windows + int(eligible)
    excluded_windows = progress.excluded_windows + int(not eligible)

    if eligible_windows >= policy.established_eligible_windows:
        status = BaselineStatus.ESTABLISHED
    elif eligible_windows >= policy.partial_eligible_windows:
        status = BaselineStatus.PARTIAL
    else:
        status = BaselineStatus.CALIBRATING

    return replace(
        progress,
        status=status,
        eligible_windows=eligible_windows,
        excluded_windows=excluded_windows,
    )


def start_recalibration(
    progress: CalibrationProgress,
    *,
    new_setup_version: str,
    reason: str,
) -> CalibrationProgress:
    if new_setup_version == progress.setup_version:
        raise ValueError("recalibration requires a new setup version")
    return CalibrationProgress(
        setup_version=new_setup_version,
        status=BaselineStatus.CALIBRATING,
        eligible_windows=0,
        excluded_windows=0,
        reason=reason,
        prior_setup_versions=progress.prior_setup_versions + (progress.setup_version,),
    )
```

- [ ] **Step 4: Run calibration tests**

Run: `python3 -m unittest tests/calibration_domain/test_calibration.py -v`

Expected: 3 tests PASS.

- [ ] **Step 5: Commit calibration behavior**

```bash
git add backend/app/domain/calibration.py tests/calibration_domain
git commit -m "feat: add controlled calibration behavior"
```

---

### Task 3: Event Episodes, Recurrence, and Overdue Behavior

**Files:**
- Modify: `backend/app/domain/events.py`
- Modify: `tests/event_domain/test_events.py`

**Interfaces:**
- Consumes: `resident_id`, `room_id`, objective family, priority, timestamps, and approved lifecycle rules.
- Produces: `EventPriority`, expanded `MonitoringEvent`, `EventStore.record_signal()`, linked recurrence, and overdue state for feedback and toy-scenario tasks.

- [ ] **Step 1: Replace the event tests with the approved episode behavior**

```python
import unittest
from datetime import datetime, timedelta, timezone

from backend.app.domain.events import (
    EventPriority,
    EventStatus,
    EventStore,
    ResolutionOutcome,
)


class EventFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = EventStore(quiet_gap=timedelta(minutes=5))
        self.started = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)

    def record(self, *, at: datetime, priority: EventPriority = EventPriority.HIGH):
        return self.store.record_signal(
            resident_id="resident_demo_a",
            room_id="room_214",
            objective_family="unusual_movement",
            headline="Unusual movement detected",
            priority=priority,
            observed_at=at,
        )

    def test_related_signals_inside_gap_update_one_episode(self) -> None:
        first = self.record(at=self.started)
        updated = self.record(at=self.started + timedelta(minutes=2))

        self.assertEqual(updated.event_id, first.event_id)
        self.assertEqual(updated.signal_count, 2)

    def test_recurrence_after_resolution_creates_linked_event(self) -> None:
        first = self.record(at=self.started)
        self.store.acknowledge(first.event_id)
        self.store.check(first.event_id)
        self.store.resolve(first.event_id, ResolutionOutcome.FALSE_POSITIVE)

        recurrence = self.record(at=self.started + timedelta(minutes=10))

        self.assertNotEqual(recurrence.event_id, first.event_id)
        self.assertEqual(recurrence.related_event_ids, (first.event_id,))
        self.assertEqual(recurrence.recurrence_count, 2)
        self.assertEqual(first.status, EventStatus.RESOLVED)

    def test_high_event_becomes_overdue_instead_of_expiring(self) -> None:
        event = self.record(at=self.started)
        overdue = self.store.mark_overdue(
            event.event_id,
            at=self.started + timedelta(minutes=6),
        )

        self.assertTrue(overdue.overdue)
        self.assertEqual(overdue.status, EventStatus.OPEN)

    def test_invalid_status_jump_is_rejected(self) -> None:
        event = self.record(at=self.started)
        with self.assertRaises(ValueError):
            self.store.resolve(event.event_id, ResolutionOutcome.CONFIRMED)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run event tests and verify they fail for missing episode interfaces**

Run: `python3 -m unittest tests/event_domain/test_events.py -v`

Expected: FAIL because `EventPriority`, `quiet_gap`, and `record_signal()` do not exist.

- [ ] **Step 3: Replace the event domain with episode-aware behavior**

```python
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from uuid import uuid4


class EventStatus(StrEnum):
    DETECTED = "detected"
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    CHECKED = "checked"
    RESOLVED = "resolved"


class EventPriority(StrEnum):
    WATCH = "watch"
    HIGH = "high"
    CRITICAL = "critical"


class ResolutionOutcome(StrEnum):
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    UNCERTAIN = "uncertain"


@dataclass
class MonitoringEvent:
    event_id: str
    episode_id: str
    resident_id: str
    room_id: str
    objective_family: str
    headline: str
    priority: EventPriority
    status: EventStatus
    created_at: datetime
    last_signal_at: datetime
    signal_count: int = 1
    related_event_ids: tuple[str, ...] = ()
    recurrence_count: int = 1
    overdue: bool = False
    resolution_outcome: ResolutionOutcome | None = None
    schema_version: str = "1.0"


class EventStore:
    def __init__(self, quiet_gap: timedelta = timedelta(minutes=5)) -> None:
        if quiet_gap <= timedelta(0):
            raise ValueError("quiet_gap must be positive")
        self.quiet_gap = quiet_gap
        self._events: dict[str, MonitoringEvent] = {}

    def record_signal(
        self,
        *,
        resident_id: str,
        room_id: str,
        objective_family: str,
        headline: str,
        priority: EventPriority,
        observed_at: datetime,
    ) -> MonitoringEvent:
        active = self._latest_related(resident_id, room_id, objective_family)
        if (
            active is not None
            and active.status != EventStatus.RESOLVED
            and observed_at - active.last_signal_at <= self.quiet_gap
        ):
            active.last_signal_at = observed_at
            active.signal_count += 1
            active.priority = max(
                active.priority,
                priority,
                key=lambda value: (
                    EventPriority.WATCH,
                    EventPriority.HIGH,
                    EventPriority.CRITICAL,
                ).index(value),
            )
            return active

        related = self._related_events(resident_id, room_id, objective_family)
        event_id = f"evt_{uuid4().hex}"
        event = MonitoringEvent(
            event_id=event_id,
            episode_id=f"episode_{uuid4().hex}",
            resident_id=resident_id,
            room_id=room_id,
            objective_family=objective_family,
            headline=headline,
            priority=priority,
            status=EventStatus.OPEN,
            created_at=observed_at,
            last_signal_at=observed_at,
            related_event_ids=tuple(item.event_id for item in related),
            recurrence_count=len(related) + 1,
        )
        self._events[event_id] = event
        return event

    def get(self, event_id: str) -> MonitoringEvent:
        try:
            return self._events[event_id]
        except KeyError as exc:
            raise KeyError(f"Unknown event: {event_id}") from exc

    def acknowledge(self, event_id: str) -> MonitoringEvent:
        return self._transition(event_id, EventStatus.OPEN, EventStatus.ACKNOWLEDGED)

    def check(self, event_id: str) -> MonitoringEvent:
        return self._transition(
            event_id,
            EventStatus.ACKNOWLEDGED,
            EventStatus.CHECKED,
        )

    def resolve(
        self,
        event_id: str,
        outcome: ResolutionOutcome,
    ) -> MonitoringEvent:
        event = self._transition(event_id, EventStatus.CHECKED, EventStatus.RESOLVED)
        event.resolution_outcome = outcome
        return event

    def mark_overdue(self, event_id: str, *, at: datetime) -> MonitoringEvent:
        event = self.get(event_id)
        if event.priority == EventPriority.WATCH:
            raise ValueError("watch events do not use overdue escalation")
        if event.status != EventStatus.OPEN:
            raise ValueError("only unacknowledged open events become overdue")
        if at <= event.created_at:
            raise ValueError("overdue time must follow event creation")
        event.overdue = True
        return event

    def _transition(
        self,
        event_id: str,
        expected: EventStatus,
        target: EventStatus,
    ) -> MonitoringEvent:
        event = self.get(event_id)
        if event.status != expected:
            raise ValueError(
                f"Cannot move event {event_id} from {event.status} to {target}"
            )
        event.status = target
        return event

    def _related_events(
        self,
        resident_id: str,
        room_id: str,
        objective_family: str,
    ) -> list[MonitoringEvent]:
        return sorted(
            (
                event
                for event in self._events.values()
                if event.resident_id == resident_id
                and event.room_id == room_id
                and event.objective_family == objective_family
            ),
            key=lambda event: event.created_at,
        )

    def _latest_related(
        self,
        resident_id: str,
        room_id: str,
        objective_family: str,
    ) -> MonitoringEvent | None:
        related = self._related_events(resident_id, room_id, objective_family)
        return related[-1] if related else None
```

- [ ] **Step 4: Run event tests**

Run: `python3 -m unittest tests/event_domain/test_events.py -v`

Expected: 4 tests PASS.

- [ ] **Step 5: Commit event episode behavior**

```bash
git add backend/app/domain/events.py tests/event_domain/test_events.py
git commit -m "feat: model event episodes and recurrence"
```

---

### Task 4: Trusted Feedback and Editable Resident Memory

**Files:**
- Create: `backend/app/domain/feedback.py`
- Create: `tests/feedback_domain/__init__.py`
- Create: `tests/feedback_domain/test_feedback.py`

**Interfaces:**
- Consumes: `MonitoringEvent`, `ResolutionOutcome`, and resolved event status from Task 3.
- Produces: `FeedbackRecord`, `MemoryEntry`, `ResidentMemory`, `LearningDecision`, `FeedbackService.submit_feedback()`, and `FeedbackService.correct_memory()` for the toy scenario.

- [ ] **Step 1: Write failing feedback and memory tests**

```python
import unittest
from datetime import datetime, timezone

from backend.app.domain.events import (
    EventPriority,
    EventStore,
    ResolutionOutcome,
)
from backend.app.domain.feedback import FeedbackService


class FeedbackLearningTests(unittest.TestCase):
    def setUp(self) -> None:
        now = datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
        store = EventStore()
        self.event = store.record_signal(
            resident_id="resident_demo_a",
            room_id="room_214",
            objective_family="unusual_movement",
            headline="Unusual movement detected",
            priority=EventPriority.HIGH,
            observed_at=now,
        )
        store.acknowledge(self.event.event_id)
        store.check(self.event.event_id)
        store.resolve(self.event.event_id, ResolutionOutcome.FALSE_POSITIVE)
        self.service = FeedbackService()

    def test_confirmed_routine_updates_memory_and_marks_window_eligible(self) -> None:
        decision = self.service.submit_feedback(
            event=self.event,
            actor_id="operator_001",
            actual_event_label="assisted_transfer",
            routine=True,
            created_at=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
        )

        self.assertTrue(decision.memory_updated)
        self.assertTrue(decision.baseline_window_eligible)
        self.assertTrue(decision.global_label_recorded)
        self.assertEqual(
            decision.memory.active_entries[0].description,
            "assisted_transfer",
        )

    def test_uncertain_event_never_makes_baseline_window_eligible(self) -> None:
        self.event.resolution_outcome = ResolutionOutcome.UNCERTAIN
        decision = self.service.submit_feedback(
            event=self.event,
            actor_id="operator_001",
            actual_event_label="unknown",
            routine=False,
            created_at=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
        )

        self.assertFalse(decision.baseline_window_eligible)

    def test_operator_can_retire_incorrect_memory_without_deleting_history(self) -> None:
        decision = self.service.submit_feedback(
            event=self.event,
            actor_id="operator_001",
            actual_event_label="assisted_transfer",
            routine=True,
            created_at=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
        )
        entry = decision.memory.active_entries[0]

        corrected = self.service.correct_memory(
            resident_id="resident_demo_a",
            entry_id=entry.entry_id,
            actor_id="operator_002",
            reason="Routine no longer applies",
            corrected_at=datetime(2026, 8, 27, 9, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(corrected.active_entries, ())
        self.assertEqual(len(corrected.entries), 1)
        self.assertEqual(corrected.entries[0].status, "retired")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run feedback tests and verify the missing-domain failure**

Run: `python3 -m unittest tests/feedback_domain/test_feedback.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.domain.feedback'`.

- [ ] **Step 3: Implement trusted feedback and versioned memory**

```python
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import uuid4

from backend.app.domain.events import (
    EventStatus,
    MonitoringEvent,
    ResolutionOutcome,
)


@dataclass(frozen=True)
class FeedbackRecord:
    feedback_id: str
    event_id: str
    resident_id: str
    actor_id: str
    outcome: ResolutionOutcome
    actual_event_label: str
    routine: bool
    created_at: datetime


@dataclass(frozen=True)
class MemoryEntry:
    entry_id: str
    description: str
    source_feedback_id: str
    status: str
    created_by: str
    created_at: datetime
    retired_by: str | None = None
    retired_at: datetime | None = None
    retirement_reason: str | None = None


@dataclass(frozen=True)
class ResidentMemory:
    resident_id: str
    version: int
    entries: tuple[MemoryEntry, ...]

    @property
    def active_entries(self) -> tuple[MemoryEntry, ...]:
        return tuple(entry for entry in self.entries if entry.status == "active")


@dataclass(frozen=True)
class LearningDecision:
    feedback: FeedbackRecord
    memory: ResidentMemory
    memory_updated: bool
    baseline_window_eligible: bool
    global_label_recorded: bool


class FeedbackService:
    def __init__(self) -> None:
        self._memories: dict[str, ResidentMemory] = {}
        self._feedback: dict[str, FeedbackRecord] = {}

    def submit_feedback(
        self,
        *,
        event: MonitoringEvent,
        actor_id: str,
        actual_event_label: str,
        routine: bool,
        created_at: datetime,
    ) -> LearningDecision:
        if event.status != EventStatus.RESOLVED or event.resolution_outcome is None:
            raise ValueError("feedback requires a resolved event")

        feedback = FeedbackRecord(
            feedback_id=f"fb_{uuid4().hex}",
            event_id=event.event_id,
            resident_id=event.resident_id,
            actor_id=actor_id,
            outcome=event.resolution_outcome,
            actual_event_label=actual_event_label,
            routine=routine,
            created_at=created_at,
        )
        self._feedback[feedback.feedback_id] = feedback

        memory = self._memories.get(
            event.resident_id,
            ResidentMemory(event.resident_id, 0, ()),
        )
        memory_updated = bool(routine and actual_event_label != "unknown")
        if memory_updated:
            entry = MemoryEntry(
                entry_id=f"memory_{uuid4().hex}",
                description=actual_event_label,
                source_feedback_id=feedback.feedback_id,
                status="active",
                created_by=actor_id,
                created_at=created_at,
            )
            memory = ResidentMemory(
                resident_id=event.resident_id,
                version=memory.version + 1,
                entries=memory.entries + (entry,),
            )
            self._memories[event.resident_id] = memory

        baseline_window_eligible = (
            event.resolution_outcome == ResolutionOutcome.FALSE_POSITIVE and routine
        )
        return LearningDecision(
            feedback=feedback,
            memory=memory,
            memory_updated=memory_updated,
            baseline_window_eligible=baseline_window_eligible,
            global_label_recorded=True,
        )

    def correct_memory(
        self,
        *,
        resident_id: str,
        entry_id: str,
        actor_id: str,
        reason: str,
        corrected_at: datetime,
    ) -> ResidentMemory:
        memory = self._memories[resident_id]
        found = False
        updated_entries: list[MemoryEntry] = []
        for entry in memory.entries:
            if entry.entry_id == entry_id:
                if entry.status != "active":
                    raise ValueError("only active memory can be retired")
                entry = replace(
                    entry,
                    status="retired",
                    retired_by=actor_id,
                    retired_at=corrected_at,
                    retirement_reason=reason,
                )
                found = True
            updated_entries.append(entry)
        if not found:
            raise KeyError(f"Unknown memory entry: {entry_id}")

        updated = ResidentMemory(
            resident_id=resident_id,
            version=memory.version + 1,
            entries=tuple(updated_entries),
        )
        self._memories[resident_id] = updated
        return updated
```

- [ ] **Step 4: Run feedback tests**

Run: `python3 -m unittest tests/feedback_domain/test_feedback.py -v`

Expected: 3 tests PASS.

- [ ] **Step 5: Commit feedback and resident memory behavior**

```bash
git add backend/app/domain/feedback.py tests/feedback_domain
git commit -m "feat: add trusted feedback and resident memory"
```

---

### Task 5: Complete Toy-Data Product Story

**Files:**
- Create: `backend/app/domain/toy_scenario.py`
- Create: `tests/toy_scenario/__init__.py`
- Create: `tests/toy_scenario/test_complete_flow.py`

**Interfaces:**
- Consumes: Monitoring, calibration, event, feedback, and memory interfaces from Tasks 1–4.
- Produces: `ToyScenarioResult` and `run_complete_toy_scenario()` as the first executable product-logic demonstration.

- [ ] **Step 1: Write the failing complete-flow test**

```python
import unittest

from backend.app.domain.calibration import BaselineStatus
from backend.app.domain.events import EventStatus
from backend.app.domain.monitoring import MonitoringState
from backend.app.domain.toy_scenario import run_complete_toy_scenario


class CompleteToyScenarioTests(unittest.TestCase):
    def test_complete_calibration_event_feedback_and_recurrence_story(self) -> None:
        result = run_complete_toy_scenario()

        self.assertEqual(result.calibration_status, BaselineStatus.ESTABLISHED)
        self.assertEqual(result.away_state, MonitoringState.PAUSED)
        self.assertEqual(result.visitor_state, MonitoringState.LIMITED)
        self.assertEqual(result.first_event_status, EventStatus.RESOLVED)
        self.assertTrue(result.memory_updated)
        self.assertTrue(result.baseline_window_eligible)
        self.assertEqual(result.recurrence_count, 2)
        self.assertTrue(result.events_are_linked)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the scenario test and verify the missing-domain failure**

Run: `python3 -m unittest tests/toy_scenario/test_complete_flow.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.app.domain.toy_scenario'`.

- [ ] **Step 3: Implement the complete synthetic story**

```python
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
    events.resolve(first.event_id, ResolutionOutcome.FALSE_POSITIVE)

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
```

- [ ] **Step 4: Run the complete scenario test**

Run: `python3 -m unittest tests/toy_scenario/test_complete_flow.py -v`

Expected: 1 test PASS.

- [ ] **Step 5: Run the complete repository suite**

Run: `python3 -m unittest discover -s tests -p 'test_*.py' -v`

Expected: All monitoring, calibration, event, feedback, scenario, and repository-policy tests PASS.

- [ ] **Step 6: Commit the complete toy scenario**

```bash
git add backend/app/domain/toy_scenario.py tests/toy_scenario
git commit -m "feat: demonstrate complete toy monitoring flow"
```

---

### Task 6: Document Phase Completion and Next Boundary

**Files:**
- Modify: `docs/AKSHAR_START_HERE.md`
- Modify: `AGENTS.md`

**Interfaces:**
- Consumes: Verified test commands and completed domain behavior from Tasks 1–5.
- Produces: Accurate current status and canonical backend verification command for the next database/API phase.

- [ ] **Step 1: Update the plain-language current status**

Replace the `Current starting point` section in `docs/AKSHAR_START_HERE.md` with:

```markdown
## Current starting point

The approved V1 product logic now runs end-to-end with synthetic data. The backend can represent monitoring suitability, calibration, resident-away awareness, possible caregiver/visitor presence, event episodes and recurrence, trusted feedback, controlled baseline eligibility, and editable resident memory.

The next backend phase adds durable database storage and the real product API around these tested rules. Rishit can continue building the clinic product against the same contract-valid scenarios, while the hardware engineer continues preparing the device telemetry boundary.
```

- [ ] **Step 2: Record the canonical backend verification command**

Add under `Testing expectations` in `AGENTS.md`:

````markdown
Current backend/domain verification:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
```
````

- [ ] **Step 3: Run final verification**

Run: `python3 -m unittest discover -s tests -p 'test_*.py' -v`

Expected: All tests PASS with no errors or warnings.

Run: `git diff --check`

Expected: no output and exit code 0.

- [ ] **Step 4: Commit phase documentation**

```bash
git add docs/AKSHAR_START_HERE.md AGENTS.md
git commit -m "docs: record backend toy-slice completion"
```

## Phase Completion Check

This phase is complete when one deterministic synthetic scenario proves:

- monitoring is active only for a valid, healthy, single-resident room condition;
- resident-away and possible-multi-person states pause learning;
- eligible toy data advances calibration to established;
- setup changes can restart calibration without deleting prior setup history;
- related signals group into one event episode;
- recurrences become new linked events;
- high events become overdue rather than expiring;
- trusted false-positive routine feedback updates resident memory and only marks the specific window eligible for later baseline processing;
- inaccurate memory can be retired without deleting audit history;
- the full repository test suite passes.

The next plan is `Backend Persistence and Product API`, which will add Postgres-compatible storage, migrations, FastAPI routes, authentication boundaries, and contract responses around these domain rules.
