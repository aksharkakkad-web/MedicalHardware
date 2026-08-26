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
