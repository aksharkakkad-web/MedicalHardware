import unittest
from dataclasses import MISSING, fields

from backend.app.domain.calibration import (
    CalibrationDimensionProgress,
    CalibrationPolicy,
    CalibrationProgress,
    SetupChangeAction,
)
from backend.app.domain.events import (
    EventAction,
    EventPriorityHistoryEntry,
    MonitoringEvent,
    SyntheticEventEpisodePolicy,
)
from backend.app.domain.device_health import (
    DeviceHealthObservation,
    DeviceSourceHealth,
)
from backend.app.domain.feedback import (
    FeedbackRecord,
    LearningDecision,
    MemoryEntry,
    ResidentMemory,
)
from backend.app.domain.monitoring import (
    MonitoringSnapshot,
    SyntheticMonitoringQualityPolicy,
)
from backend.app.domain.toy_scenario import ToyScenarioResult, ToyScenarioStep


class DomainSchemaVersionTests(unittest.TestCase):
    def test_every_public_domain_record_has_a_schema_version(self) -> None:
        public_domain_records = (
            SyntheticMonitoringQualityPolicy,
            MonitoringSnapshot,
            CalibrationPolicy,
            CalibrationDimensionProgress,
            SetupChangeAction,
            CalibrationProgress,
            DeviceSourceHealth,
            DeviceHealthObservation,
            EventAction,
            EventPriorityHistoryEntry,
            SyntheticEventEpisodePolicy,
            MonitoringEvent,
            FeedbackRecord,
            MemoryEntry,
            ResidentMemory,
            LearningDecision,
            ToyScenarioStep,
            ToyScenarioResult,
        )

        for record_type in public_domain_records:
            with self.subTest(record_type=record_type.__name__):
                schema_fields = {
                    field.name: field for field in fields(record_type)
                }
                self.assertIn("schema_version", schema_fields)
                schema_field = schema_fields["schema_version"]
                self.assertIsNot(schema_field.default, MISSING)
                self.assertEqual(schema_field.default, "1.0")


if __name__ == "__main__":
    unittest.main()
