import unittest

from backend.app.domain.calibration import BaselineStatus
from backend.app.domain.events import EventPriority, EventStatus
from backend.app.domain.monitoring import MonitoringState, PresenceState
from backend.app.domain.toy_scenario import run_complete_toy_scenario


class CompleteToyScenarioTests(unittest.TestCase):
    def test_complete_calibration_event_feedback_and_recurrence_story(self) -> None:
        result = run_complete_toy_scenario()

        self.assertEqual(result.calibration_status, BaselineStatus.ESTABLISHED)
        self.assertEqual(
            result.calibration_history,
            (
                BaselineStatus.NEW,
                BaselineStatus.CALIBRATING,
                BaselineStatus.PARTIAL,
                BaselineStatus.PARTIAL,
                BaselineStatus.ESTABLISHED,
            ),
        )
        self.assertEqual(result.away_state, MonitoringState.PAUSED)
        self.assertEqual(result.visitor_state, MonitoringState.LIMITED)
        self.assertEqual(result.resumed_state, MonitoringState.ACTIVE)
        self.assertEqual(result.calibration_after_away.eligible_windows, 4)
        self.assertEqual(result.calibration_after_away.excluded_windows, 1)
        self.assertEqual(result.calibration_after_visitor.eligible_windows, 4)
        self.assertEqual(result.calibration_after_visitor.excluded_windows, 2)
        self.assertEqual(
            result.blocked_presence_states,
            (
                PresenceState.RESIDENT_AWAY,
                PresenceState.POSSIBLE_MULTI_PERSON,
            ),
        )

        self.assertEqual(result.first_event_status, EventStatus.RESOLVED)
        self.assertEqual(result.first_event.signal_count, 2)
        self.assertEqual(
            tuple(entry.priority for entry in result.first_event.priority_history),
            (EventPriority.WATCH, EventPriority.HIGH),
        )
        self.assertIsNotNone(result.first_event.overdue_at)
        self.assertEqual(
            tuple(entry.action for entry in result.first_event.action_history),
            (
                "opened",
                "marked_overdue",
                "acknowledged",
                "checked",
                "resolved",
            ),
        )

        self.assertTrue(result.memory_updated)
        self.assertTrue(result.baseline_window_eligible)
        self.assertEqual(
            result.baseline_progress_before_feedback,
            result.baseline_progress_after_feedback,
        )
        self.assertEqual(
            result.baseline_progress_after_controlled_update.eligible_windows,
            result.baseline_progress_before_feedback.eligible_windows + 1,
        )

        self.assertEqual(result.recurrence_count, 2)
        self.assertTrue(result.events_are_linked)
        routine = result.learning_decision.memory.active_entries[0]
        self.assertEqual(
            result.recurrence_event.resident_memory_version,
            result.learning_decision.memory.version,
        )
        self.assertIn(
            routine.entry_id,
            result.recurrence_event.resident_memory_entry_ids,
        )
        self.assertEqual(result.recurrence_event.priority, EventPriority.HIGH)

        self.assertEqual(result.recalibration.status, BaselineStatus.PARTIAL)
        self.assertEqual(
            result.recalibration.dimension("movement").status,
            BaselineStatus.CALIBRATING,
        )
        self.assertEqual(
            result.recalibration.dimension("respiratory_rate").status,
            BaselineStatus.ESTABLISHED,
        )
        self.assertEqual(len(result.recalibration.setup_change_history), 1)
        self.assertEqual(
            result.recalibration.setup_change_history[0].affected_dimensions,
            ("movement",),
        )

        self.assertEqual(result.corrected_memory.active_entries, ())
        self.assertEqual(result.corrected_memory.entries[0].status, "retired")

        timeline_times = tuple(step.occurred_at for step in result.timeline)
        self.assertEqual(timeline_times, tuple(sorted(timeline_times)))
        self.assertTrue(
            all(
                occurred_at.tzinfo is not None
                and occurred_at.utcoffset() is not None
                for occurred_at in timeline_times
            )
        )
        timeline_names = {step.name for step in result.timeline}
        self.assertTrue(
            {
                "resident_away",
                "visitor_present",
                "monitoring_resumed",
                "event_grouped",
                "event_overdue",
                "feedback_recorded",
                "recurrence_created",
                "setup_changed",
                "memory_corrected",
            }.issubset(timeline_names)
        )


if __name__ == "__main__":
    unittest.main()
