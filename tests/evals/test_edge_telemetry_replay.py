import json

import pytest

from evals.telemetry.cli import main
from evals.telemetry.replay import run_replay
from evals.telemetry.scenarios import REQUIRED_FAMILIES, scenarios


@pytest.fixture(scope="module")
def replay_result():
    return run_replay(scenarios())


def test_required_scenario_families_and_volume_exist() -> None:
    suite = scenarios()

    assert len(suite) == 48
    assert REQUIRED_FAMILIES <= {scenario.family for scenario in suite}
    assert len({scenario.scenario_id for scenario in suite}) == len(suite)


def test_truth_never_enters_production_envelopes() -> None:
    for scenario in scenarios():
        payload = json.dumps(scenario.capture_payloads, sort_keys=True)
        assert "expected" not in payload.casefold()
        assert scenario.truth_label not in payload


def test_replay_proves_ingest_assignment_features_and_anomaly_behavior(
    replay_result,
) -> None:
    summary = replay_result.summary

    assert summary.total_cases == 48
    assert summary.passed_cases == 48
    assert summary.failed_cases == 0
    assert summary.accepted_packets > 48
    assert summary.duplicate_packets >= 3
    assert summary.expected_conflicts_detected == summary.expected_conflicts
    assert summary.assignment_blocks_detected == summary.expected_assignment_blocks
    assert summary.feature_mapping_failures == 0
    assert summary.supported_anomaly_recall == 1.0
    assert summary.normal_false_event_rate == 0.0
    assert summary.replay_idempotency_failures == 0


def test_replay_content_is_deterministic_apart_from_runtime_metrics() -> None:
    first = run_replay(scenarios())
    second = run_replay(scenarios())

    assert first.stable_data() == second.stable_data()


def test_cli_writes_machine_and_founder_readable_artifacts(tmp_path) -> None:
    output = tmp_path / "telemetry-eval"

    assert main(["--output", str(output)]) == 0
    assert (output / "results.json").is_file()
    assert (output / "summary.json").is_file()
    report = (output / "report.md").read_text()
    assert "48" in report
    assert "anomaly recall" in report.casefold()
