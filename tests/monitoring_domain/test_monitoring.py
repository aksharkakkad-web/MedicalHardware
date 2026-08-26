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
