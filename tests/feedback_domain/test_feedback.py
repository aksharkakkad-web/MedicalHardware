import unittest
from dataclasses import replace
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
        self.event = store.resolve(self.event.event_id, ResolutionOutcome.FALSE_POSITIVE)
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
        self.event = replace(self.event, resolution_outcome=ResolutionOutcome.UNCERTAIN)
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
