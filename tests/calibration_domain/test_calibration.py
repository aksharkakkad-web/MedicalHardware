import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from backend.app.domain.calibration import (
    BaselineStatus,
    CalibrationPolicy,
    CalibrationProgress,
    observe_calibration_window,
    start_recalibration,
)
from backend.app.domain.monitoring import PresenceState, derive_monitoring_snapshot


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
                actor_id="operator_001",
                changed_at=datetime(2026, 8, 26, 14, 0, tzinfo=timezone.utc),
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
            actor_id="operator_001",
            changed_at=datetime(2026, 8, 26, 14, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(recalibrating.status, BaselineStatus.CALIBRATING)
        self.assertEqual(recalibrating.setup_version, "setup_v2")
        self.assertEqual(recalibrating.eligible_windows, 0)
        self.assertEqual(recalibrating.prior_setup_versions, ("setup_v1",))

    def test_setup_change_resets_only_affected_dimension_and_records_audit(self) -> None:
        progress = CalibrationProgress.new(
            "setup_v1",
            dimensions=("movement", "respiratory_rate"),
        )
        for _ in range(4):
            progress = observe_calibration_window(
                progress,
                policy=self.policy,
                learning_allowed=True,
                concerning=False,
                unresolved_anomaly=False,
            )

        unchanged_respiratory = progress.dimension("respiratory_rate")
        recalibrating = start_recalibration(
            progress,
            new_setup_version="setup_v2",
            reason="device_moved",
            actor_id="operator_007",
            changed_at=datetime(2026, 8, 26, 14, 0, tzinfo=timezone.utc),
            affected_dimensions=("movement",),
        )

        self.assertEqual(progress.status, BaselineStatus.ESTABLISHED)
        self.assertEqual(recalibrating.status, BaselineStatus.PARTIAL)
        self.assertEqual(
            recalibrating.dimension("movement").status,
            BaselineStatus.CALIBRATING,
        )
        self.assertEqual(recalibrating.dimension("movement").eligible_windows, 0)
        self.assertEqual(
            recalibrating.dimension("respiratory_rate"),
            unchanged_respiratory,
        )
        self.assertEqual(len(recalibrating.setup_change_history), 1)
        action = recalibrating.setup_change_history[0]
        self.assertEqual(action.previous_setup_version, "setup_v1")
        self.assertEqual(action.new_setup_version, "setup_v2")
        self.assertEqual(action.affected_dimensions, ("movement",))
        self.assertEqual(action.reason, "device_moved")
        self.assertEqual(action.actor_id, "operator_007")
        self.assertEqual(
            action.changed_at,
            datetime(2026, 8, 26, 14, 0, tzinfo=timezone.utc),
        )
        with self.assertRaises(FrozenInstanceError):
            action.reason = "other"

    def test_recalibration_rejects_malformed_audit_or_dimension_values(self) -> None:
        established = CalibrationProgress.new(
            "setup_v1",
            dimensions=("movement", "respiratory_rate"),
        )
        valid = {
            "new_setup_version": "setup_v2",
            "reason": "device_moved",
            "actor_id": "operator_001",
            "changed_at": datetime(2026, 8, 26, 14, 0, tzinfo=timezone.utc),
            "affected_dimensions": ("movement",),
        }
        invalid_overrides = (
            {"new_setup_version": " "},
            {"reason": ""},
            {"actor_id": " "},
            {"changed_at": datetime(2026, 8, 26, 14, 0)},
            {"changed_at": "2026-08-26T14:00:00Z"},
            {"affected_dimensions": ("unknown_dimension",)},
            {"affected_dimensions": ()},
        )

        for override in invalid_overrides:
            with self.subTest(override=override), self.assertRaises(ValueError):
                start_recalibration(established, **(valid | override))

    def test_calibration_window_flags_require_real_booleans(self) -> None:
        valid = {
            "learning_allowed": True,
            "concerning": False,
            "unresolved_anomaly": False,
        }
        for override in (
            {"learning_allowed": 1},
            {"concerning": 0},
            {"unresolved_anomaly": "false"},
        ):
            with self.subTest(override=override), self.assertRaises(ValueError):
                observe_calibration_window(
                    CalibrationProgress.new("setup_v1"),
                    policy=self.policy,
                    **(valid | override),
                )

    def test_monitoring_snapshot_directly_controls_calibration_eligibility(self) -> None:
        progress = CalibrationProgress.new("setup_v1")
        away = derive_monitoring_snapshot(
            assignment_valid=True,
            device_healthy=True,
            presence=PresenceState.RESIDENT_AWAY,
            signal_quality=0.9,
        )
        resumed = derive_monitoring_snapshot(
            assignment_valid=True,
            device_healthy=True,
            presence=PresenceState.RESIDENT_PRESENT,
            signal_quality=0.9,
        )

        excluded = observe_calibration_window(
            progress,
            policy=self.policy,
            monitoring_snapshot=away,
            concerning=False,
            unresolved_anomaly=False,
        )
        eligible = observe_calibration_window(
            excluded,
            policy=self.policy,
            monitoring_snapshot=resumed,
            concerning=False,
            unresolved_anomaly=False,
        )

        self.assertEqual(excluded.eligible_windows, 0)
        self.assertEqual(excluded.excluded_windows, 1)
        self.assertEqual(eligible.eligible_windows, 1)
        self.assertEqual(eligible.excluded_windows, 1)


if __name__ == "__main__":
    unittest.main()
