import unittest
from math import inf, nan

from backend.app.domain.monitoring import (
    MonitoringReason,
    MonitoringState,
    PresenceState,
    SyntheticMonitoringQualityPolicy,
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

    def test_valid_presence_string_is_normalized_before_decision(self) -> None:
        snapshot = derive_monitoring_snapshot(
            assignment_valid=True,
            device_healthy=True,
            presence="resident_present",
            signal_quality=0.9,
        )

        self.assertIs(snapshot.presence, PresenceState.RESIDENT_PRESENT)
        self.assertEqual(snapshot.state, MonitoringState.ACTIVE)

    def test_invalid_presence_never_falls_through_to_active(self) -> None:
        for presence in ("someone_else", "", None, 1):
            with self.subTest(presence=presence), self.assertRaises(ValueError):
                derive_monitoring_snapshot(
                    assignment_valid=True,
                    device_healthy=True,
                    presence=presence,
                    signal_quality=0.9,
                )

    def test_assignment_and_device_flags_require_real_booleans(self) -> None:
        invalid_flags = (
            {"assignment_valid": 1, "device_healthy": True},
            {"assignment_valid": True, "device_healthy": 0},
            {"assignment_valid": "true", "device_healthy": True},
            {"assignment_valid": True, "device_healthy": None},
        )
        for flags in invalid_flags:
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                derive_monitoring_snapshot(
                    **flags,
                    presence=PresenceState.RESIDENT_PRESENT,
                    signal_quality=0.9,
                )

    def test_signal_quality_and_minimum_bounds_fail_closed(self) -> None:
        for signal_quality in (-0.1, 1.1, nan, inf, True, "0.9", None):
            with self.subTest(signal_quality=signal_quality), self.assertRaises(ValueError):
                derive_monitoring_snapshot(
                    assignment_valid=True,
                    device_healthy=True,
                    presence=PresenceState.RESIDENT_PRESENT,
                    signal_quality=signal_quality,
                )

        for minimum_quality in (-0.1, 1.1, nan, inf, True, "0.6", None):
            with self.subTest(minimum_quality=minimum_quality), self.assertRaises(ValueError):
                derive_monitoring_snapshot(
                    assignment_valid=True,
                    device_healthy=True,
                    presence=PresenceState.RESIDENT_PRESENT,
                    signal_quality=0.9,
                    minimum_quality=minimum_quality,
                )

    def test_quality_decision_carries_synthetic_versioned_policy(self) -> None:
        policy = SyntheticMonitoringQualityPolicy(
            minimum_quality=0.75,
            policy_version="synthetic_monitoring_quality_test_v7",
        )
        limited = derive_monitoring_snapshot(
            assignment_valid=True,
            device_healthy=True,
            presence=PresenceState.RESIDENT_PRESENT,
            signal_quality=0.7,
            quality_policy=policy,
        )
        active = derive_monitoring_snapshot(
            assignment_valid=True,
            device_healthy=True,
            presence=PresenceState.RESIDENT_PRESENT,
            signal_quality=0.8,
            quality_policy=policy,
        )

        self.assertTrue(policy.test_only)
        self.assertEqual(limited.state, MonitoringState.LIMITED)
        self.assertEqual(active.state, MonitoringState.ACTIVE)
        self.assertTrue(active.quality_policy_test_only)
        self.assertEqual(active.quality_policy_version, policy.policy_version)

    def test_synthetic_quality_policy_rejects_malformed_values(self) -> None:
        invalid_values = (
            {"minimum_quality": -0.1, "policy_version": "policy_v1"},
            {"minimum_quality": 1.1, "policy_version": "policy_v1"},
            {"minimum_quality": True, "policy_version": "policy_v1"},
            {"minimum_quality": 0.6, "policy_version": " "},
        )
        for values in invalid_values:
            with self.subTest(values=values), self.assertRaises(ValueError):
                SyntheticMonitoringQualityPolicy(**values)


if __name__ == "__main__":
    unittest.main()
