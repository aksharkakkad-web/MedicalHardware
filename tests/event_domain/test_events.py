import unittest
from dataclasses import FrozenInstanceError
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

    def test_related_signals_at_quiet_gap_boundary_update_one_episode(self) -> None:
        first = self.record(at=self.started)
        boundary = self.record(at=self.started + timedelta(minutes=5))
        after_gap = self.record(
            at=self.started + timedelta(minutes=10, microseconds=1)
        )

        self.assertEqual(boundary.event_id, first.event_id)
        self.assertEqual(boundary.signal_count, 2)
        self.assertNotEqual(after_gap.event_id, first.event_id)

    def test_open_signal_after_gap_creates_linked_event(self) -> None:
        first = self.record(at=self.started)
        recurrence = self.record(at=self.started + timedelta(minutes=6))

        self.assertNotEqual(recurrence.event_id, first.event_id)
        self.assertEqual(recurrence.related_event_ids, (first.event_id,))
        self.assertEqual(recurrence.recurrence_count, 2)
        self.assertEqual(recurrence.status, EventStatus.OPEN)

    def test_out_of_order_signal_is_rejected(self) -> None:
        first = self.record(at=self.started + timedelta(minutes=10))

        with self.assertRaises(ValueError):
            self.record(at=self.started)

        stored = self.store.get(first.event_id)
        self.assertEqual(stored.created_at, self.started + timedelta(minutes=10))
        self.assertEqual(stored.last_signal_at, self.started + timedelta(minutes=10))

    def test_recurrence_after_resolution_creates_linked_event(self) -> None:
        first = self.record(at=self.started)
        self.store.acknowledge(first.event_id)
        self.store.check(first.event_id)
        resolved = self.store.resolve(first.event_id, ResolutionOutcome.FALSE_POSITIVE)

        recurrence = self.record(at=self.started + timedelta(minutes=10))

        self.assertNotEqual(recurrence.event_id, first.event_id)
        self.assertEqual(recurrence.related_event_ids, (first.event_id,))
        self.assertEqual(recurrence.recurrence_count, 2)
        self.assertEqual(resolved.status, EventStatus.RESOLVED)

    def test_high_and_critical_events_become_overdue_instead_of_expiring(self) -> None:
        for offset, priority in enumerate((EventPriority.HIGH, EventPriority.CRITICAL)):
            with self.subTest(priority=priority):
                event = self.record(
                    at=self.started + timedelta(minutes=offset * 10),
                    priority=priority,
                )
                overdue = self.store.mark_overdue(
                    event.event_id,
                    at=event.created_at + timedelta(minutes=6),
                )

                self.assertTrue(overdue.overdue)
                self.assertEqual(overdue.status, EventStatus.OPEN)

    def test_watch_event_never_receives_overdue_escalation(self) -> None:
        event = self.record(at=self.started, priority=EventPriority.WATCH)

        with self.assertRaises(ValueError):
            self.store.mark_overdue(
                event.event_id,
                at=self.started + timedelta(minutes=6),
            )

    def test_invalid_status_jump_is_rejected(self) -> None:
        event = self.record(at=self.started)
        with self.assertRaises(ValueError):
            self.store.resolve(event.event_id, ResolutionOutcome.CONFIRMED)

    def test_resolved_event_snapshot_cannot_reopen_or_transition_again(self) -> None:
        event = self.record(at=self.started)
        self.store.acknowledge(event.event_id)
        self.store.check(event.event_id)
        resolved = self.store.resolve(event.event_id, ResolutionOutcome.CONFIRMED)

        with self.assertRaises(FrozenInstanceError):
            resolved.status = EventStatus.OPEN
        with self.assertRaises(ValueError):
            self.store.acknowledge(resolved.event_id)

        self.assertEqual(self.store.get(resolved.event_id).status, EventStatus.RESOLVED)

    def test_all_resolution_outcomes_are_preserved(self) -> None:
        for offset, outcome in enumerate(ResolutionOutcome):
            with self.subTest(outcome=outcome):
                event = self.record(at=self.started + timedelta(minutes=offset * 10))
                self.store.acknowledge(event.event_id)
                self.store.check(event.event_id)

                resolved = self.store.resolve(event.event_id, outcome)

                self.assertEqual(resolved.resolution_outcome, outcome)

    def test_invalid_resolution_outcome_is_rejected(self) -> None:
        event = self.record(at=self.started)
        self.store.acknowledge(event.event_id)
        self.store.check(event.event_id)

        with self.assertRaises(ValueError):
            self.store.resolve(event.event_id, "other")


if __name__ == "__main__":
    unittest.main()
