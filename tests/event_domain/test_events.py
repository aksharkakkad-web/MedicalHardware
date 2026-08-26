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
