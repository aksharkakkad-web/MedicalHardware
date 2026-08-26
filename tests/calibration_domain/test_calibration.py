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

    def test_concerning_window_is_excluded_even_when_learning_is_allowed(self) -> None:
        progress = observe_calibration_window(
            CalibrationProgress.new("setup_v1"),
            policy=self.policy,
            learning_allowed=True,
            concerning=True,
            unresolved_anomaly=False,
        )

        self.assertEqual(progress.eligible_windows, 0)
        self.assertEqual(progress.excluded_windows, 1)

    def test_unresolved_anomaly_window_is_excluded_even_when_learning_is_allowed(self) -> None:
        progress = observe_calibration_window(
            CalibrationProgress.new("setup_v1"),
            policy=self.policy,
            learning_allowed=True,
            concerning=False,
            unresolved_anomaly=True,
        )

        self.assertEqual(progress.eligible_windows, 0)
        self.assertEqual(progress.excluded_windows, 1)

    def test_policy_is_explicitly_synthetic_test_only(self) -> None:
        self.assertTrue(CalibrationPolicy.SYNTHETIC_TEST_ONLY)

    def test_policy_rejects_invalid_thresholds(self) -> None:
        with self.assertRaises(ValueError):
            CalibrationPolicy(partial_eligible_windows=0, established_eligible_windows=4)
        with self.assertRaises(ValueError):
            CalibrationPolicy(partial_eligible_windows=2, established_eligible_windows=2)

    def test_recalibration_rejects_unchanged_setup_version(self) -> None:
        progress = CalibrationProgress.new("setup_v1")
        with self.assertRaises(ValueError):
            start_recalibration(
                progress,
                new_setup_version="setup_v1",
                reason="operator_requested",
            )

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
