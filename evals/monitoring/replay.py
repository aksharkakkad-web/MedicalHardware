"""Canonical Phase 5 normalized-fixture replay command."""

import argparse
from copy import deepcopy
import json
import sys
from typing import Any

from backend.app.ai.client import INTERPRETATION_SCHEMA_VERSION
from backend.app.domain.monitoring import SyntheticMonitoringQualityPolicy
from backend.app.intelligence.anomaly import SyntheticAnomalyPolicy
from backend.app.intelligence.baseline import BaselinePolicy
from backend.app.intelligence.fall_detection import SyntheticFallPolicy
from backend.app.intelligence.policy import EventAttentionPolicy, SyntheticDispositionPolicy
from evals.monitoring.metrics import calculate_metrics, safety_gates
from evals.monitoring.scenarios import run_scenarios


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _report(records: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate = calculate_metrics(records)
    return {
        "schema_version": "1.0",
        "suite_id": "phase5_monitoring_intelligence_synthetic_v1",
        "fixture_boundary": "synthetic_normalized_features",
        "clinical_authority": False,
        "notice": "Engineering evaluation on synthetic normalized fixtures; not clinical, hardware, or production-provider validation.",
        "versions": {
            "anomaly_policy": SyntheticAnomalyPolicy().policy_version,
            "baseline_policy": BaselinePolicy().policy_version,
            "disposition_policy": SyntheticDispositionPolicy().policy_version,
            "event_attention_policy": EventAttentionPolicy().policy_version,
            "fall_like_policy": SyntheticFallPolicy().policy_version,
            "monitoring_quality_policy": SyntheticMonitoringQualityPolicy().policy_version,
            "feature_contract_schema": "1.0",
            "interpretation_output_schema": INTERPRETATION_SCHEMA_VERSION,
        },
        "metric_definitions": {
            "resident_day_denominator": "Each compact stable scenario declares one synthetic resident-day; no wall-clock duration is extrapolated.",
            "meaningful_anomaly_recall": "Meaningful scenarios with an evidence packet or an urgent deterministic event divided by declared meaningful scenarios.",
            "false_packet_rate": "Packets in scenarios that do not expect a packet, including the urgent bypass, divided by synthetic resident-days.",
            "false_event_rate": "All caregiver events in scenarios that do not expect caregiver work, divided by synthetic resident-days.",
            "duplicate_event_rate": "Extra event IDs within one source-anomaly signal group divided by event signal groups.",
            "baseline_contamination": "Learning guards that admitted an operationally unsafe, poor-quality, contradictory, candidate, anomaly, fall-transition, setup-change, or recovery window.",
            "latency": "Seconds from injected scenario start to the first actual candidate, packet, or caregiver event; unavailable is reported when the stage does not occur.",
            "event_duration_error": "Absolute error between an explicitly declared fixture event-signal interval and the actual first-to-latest event signal span.",
        },
        "aggregate": aggregate,
        "safety_gates": safety_gates(records, aggregate),
        "scenarios": records,
    }


def run_replay() -> dict[str, Any]:
    first = _report(run_scenarios())
    second = _report(run_scenarios())
    reproducible = canonical_json_bytes(first) == canonical_json_bytes(second)
    completed = deepcopy(first)
    completed["aggregate"]["replay_reproducible"] = reproducible
    return completed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json",), default="json")
    parser.parse_args(argv)
    sys.stdout.buffer.write(canonical_json_bytes(run_replay()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["canonical_json_bytes", "main", "run_replay"]
