import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

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
        store.acknowledge(
            self.event.event_id,
            actor_id="operator_001",
            at=now + timedelta(minutes=1),
        )
        store.check(
            self.event.event_id,
            actor_id="operator_001",
            at=now + timedelta(minutes=2),
        )
        self.event = store.resolve(
            self.event.event_id,
            ResolutionOutcome.FALSE_POSITIVE,
            actor_id="operator_001",
            at=now + timedelta(minutes=3),
        )
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

    def test_normalized_unknown_routine_cannot_become_baseline_eligible(self) -> None:
        decision = self.service.submit_feedback(
            event=self.event,
            actor_id="operator_001",
            actual_event_label="  UNKNOWN  ",
            routine=True,
            created_at=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
        )

        self.assertEqual(decision.feedback.actual_event_label, "unknown")
        self.assertFalse(decision.memory_updated)
        self.assertEqual(decision.memory.version, 0)
        self.assertFalse(decision.baseline_window_eligible)

    def test_known_label_is_normalized_before_memory_update(self) -> None:
        decision = self.service.submit_feedback(
            event=self.event,
            actor_id="operator_001",
            actual_event_label="  Assisted Transfer  ",
            routine=True,
            created_at=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
        )

        self.assertEqual(decision.feedback.actual_event_label, "assisted_transfer")
        self.assertEqual(
            decision.memory.active_entries[0].description,
            "assisted_transfer",
        )
        self.assertTrue(decision.memory_updated)
        self.assertTrue(decision.baseline_window_eligible)

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

    def test_feedback_requires_resolved_event(self) -> None:
        unresolved = replace(self.event, status="checked")
        with self.assertRaises(ValueError):
            self.service.submit_feedback(
                event=unresolved,
                actor_id="operator_001",
                actual_event_label="assisted_transfer",
                routine=True,
                created_at=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
            )

    def test_feedback_does_not_mutate_event_snapshot(self) -> None:
        original = self.event
        self.service.submit_feedback(
            event=self.event,
            actor_id="operator_001",
            actual_event_label="assisted_transfer",
            routine=True,
            created_at=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
        )
        self.assertEqual(self.event, original)

    def test_feedback_rejects_malformed_audit_fields(self) -> None:
        valid_time = datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc)
        invalid_inputs = (
            {"actor_id": "", "actual_event_label": "label", "routine": True, "created_at": valid_time},
            {"actor_id": "operator", "actual_event_label": "", "routine": True, "created_at": valid_time},
            {"actor_id": "operator", "actual_event_label": "label", "routine": 1, "created_at": valid_time},
            {"actor_id": "operator", "actual_event_label": "label", "routine": True, "created_at": datetime(2026, 8, 26, 12, 5)},
        )
        for values in invalid_inputs:
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.service.submit_feedback(event=self.event, **values)

    def test_feedback_rejects_timestamp_before_event(self) -> None:
        with self.assertRaises(ValueError):
            self.service.submit_feedback(
                event=self.event,
                actor_id="operator_001",
                actual_event_label="assisted_transfer",
                routine=True,
                created_at=datetime(2026, 8, 26, 11, 59, tzinfo=timezone.utc),
            )

    def test_feedback_datetime_boundaries_consistently_raise_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self.service.submit_feedback(
                event=self.event,
                actor_id="operator_001",
                actual_event_label="assisted_transfer",
                routine=True,
                created_at="2026-08-26T12:05:00Z",
            )

        decision = self.service.submit_feedback(
            event=self.event,
            actor_id="operator_001",
            actual_event_label="assisted_transfer",
            routine=True,
            created_at=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
        )
        with self.assertRaises(ValueError):
            self.service.correct_memory(
                resident_id="resident_demo_a",
                entry_id=decision.memory.active_entries[0].entry_id,
                actor_id="operator_002",
                reason="Routine no longer applies",
                corrected_at="2026-08-27T09:00:00Z",
            )

    def test_memory_correction_requires_auditable_ordered_fields(self) -> None:
        decision = self.service.submit_feedback(
            event=self.event,
            actor_id="operator_001",
            actual_event_label="assisted_transfer",
            routine=True,
            created_at=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
        )
        entry_id = decision.memory.active_entries[0].entry_id
        invalid_inputs = (
            {"actor_id": "", "reason": "reason", "corrected_at": datetime(2026, 8, 27, 9, tzinfo=timezone.utc)},
            {"actor_id": "operator", "reason": "", "corrected_at": datetime(2026, 8, 27, 9, tzinfo=timezone.utc)},
            {"actor_id": "operator", "reason": "reason", "corrected_at": datetime(2026, 8, 27, 9)},
            {"actor_id": "operator", "reason": "reason", "corrected_at": datetime(2026, 8, 26, 12, tzinfo=timezone.utc)},
        )
        for values in invalid_inputs:
            service = FeedbackService()
            decision = service.submit_feedback(
                event=self.event,
                actor_id="operator_001",
                actual_event_label="assisted_transfer",
                routine=True,
                created_at=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
            )
            with self.subTest(values=values), self.assertRaises(ValueError):
                service.correct_memory(
                    resident_id="resident_demo_a",
                    entry_id=decision.memory.active_entries[0].entry_id,
                    **values,
                )


if __name__ == "__main__":
    unittest.main()
