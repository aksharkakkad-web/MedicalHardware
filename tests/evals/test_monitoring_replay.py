from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

from backend.app.checkpoints.monitoring_intelligence import checkpoint_failures
from evals.monitoring.metrics import calculate_metrics
from evals.monitoring.replay import canonical_json_bytes, run_replay
from evals.monitoring.scenarios import REQUIRED_SCENARIO_IDS


ROOT = Path(__file__).resolve().parents[2]


def _by_id(report: dict[str, object]) -> dict[str, dict[str, object]]:
    return {
        scenario["scenario_id"]: scenario
        for scenario in report["scenarios"]
    }


def test_canonical_suite_covers_every_required_stable_scenario() -> None:
    # Break caught: a required product behavior silently drops out of the replay gate.
    report = run_replay()

    assert {scenario["scenario_id"] for scenario in report["scenarios"]} == set(
        REQUIRED_SCENARIO_IDS
    )
    assert report["aggregate"]["scenario_count"] == 24
    assert report["fixture_boundary"] == "synthetic_normalized_features"
    assert report["clinical_authority"] is False


def test_replay_records_come_from_the_real_phase5_component_path() -> None:
    # Break caught: fixtures hard-code final labels without exercising implemented components.
    report = run_replay()
    scenarios = _by_id(report)

    assert scenarios["normal_variation"]["component_trace"] == [
        "normalized_observation",
        "quality_learning_guard",
        "robust_baseline",
        "monitoring_intelligence_engine",
    ]
    assert scenarios["sustained_movement_change"]["candidate_count"] == 1
    assert scenarios["sustained_movement_change"]["packet_count"] >= 1
    assert scenarios["sustained_movement_change"]["interpretation"]["attempted"] >= 1
    assert scenarios["sustained_movement_change"]["caregiver_event_count"] == 1


def test_synthetic_safety_gates_are_computed_from_scenario_records() -> None:
    # Break caught: aggregate gates are copied constants or permit contamination/duplicates.
    report = run_replay()
    aggregate = report["aggregate"]

    assert aggregate["meaningful_anomaly_recall"] == {
        "captured": 7,
        "expected": 7,
        "rate": 1.0,
    }
    assert aggregate["missed_meaningful_events"] == []
    contamination = aggregate["baseline_contamination"]
    assert contamination["contaminated_learning_windows"] == 0
    assert contamination["eligible_learning_windows"] > 0
    assert contamination["evaluated_learning_windows"] > contamination[
        "eligible_learning_windows"
    ]
    assert contamination["rate"] == 0.0
    duplicates = aggregate["duplicate_events"]
    assert duplicates["duplicate_event_count"] == 0
    assert duplicates["event_signal_groups"] > 0
    assert duplicates["rate"] == 0.0
    assert aggregate["false_packets_per_resident_day"]["count"] == 0
    assert aggregate["false_caregiver_events_per_resident_day"]["count"] == 0
    assert aggregate["replay_reproducible"] is True
    assert report["safety_gates"] == {
        "baseline_contamination_zero": True,
        "duplicate_events_zero": True,
        "invalid_ai_rejected": True,
        "ordinary_routine_degraded_resident_events_zero": True,
        "urgent_fall_like_independent_of_ai": True,
    }


def test_metrics_change_when_replay_records_contain_regressions() -> None:
    # Break caught: an aggregate zero is copied or an urgent-path packet is under-counted.
    records = deepcopy(run_replay()["scenarios"])
    by_id = {record["scenario_id"]: record for record in records}
    by_id["fall_like"]["packet_count"] = 2
    by_id["normal_variation"]["caregiver_event_count"] = 1
    by_id["normal_variation"]["resident_specific_event_count"] = 0
    by_id["normal_variation"]["contaminated_learning_windows"] = 1
    by_id["normal_variation"]["duplicate_event_count"] = 1

    aggregate = calculate_metrics(records)

    assert aggregate["false_packets_per_resident_day"]["count"] == 2
    assert aggregate["false_caregiver_events_per_resident_day"]["count"] == 1
    assert aggregate["baseline_contamination"]["contaminated_learning_windows"] == 1
    assert aggregate["duplicate_events"]["duplicate_event_count"] == 1


def test_ordinary_away_routine_and_degraded_cases_do_not_create_resident_work() -> None:
    # Break caught: ordinary variation or unreliable attribution becomes resident work.
    report = run_replay()
    scenarios = _by_id(report)
    quiet_ids = {
        "normal_variation",
        "random_bathroom_away",
        "sleep_reading_stillness",
        "flexible_routine",
        "temporary_change",
        "visitor_multi_person",
        "fall_like_confounder",
        "respiration_quality_limited",
        "missing_signal",
        "stale_signal",
        "frozen_signal",
        "contradictory_sensors",
        "setup_change",
        "preentered_new_behavior",
        "post_event_new_behavior",
    }

    assert {
        scenario_id
        for scenario_id in quiet_ids
        if scenarios[scenario_id]["resident_specific_event_count"]
    } == set()
    assert scenarios["random_bathroom_away"]["monitoring_state"] == "paused"
    assert scenarios["visitor_multi_person"]["monitoring_state"] == "limited"
    assert scenarios["setup_change"]["monitoring_state"] == "unavailable"


def test_ai_failure_and_urgent_paths_preserve_deterministic_safety() -> None:
    # Break caught: invalid AI is trusted or an urgent event waits for provider output.
    scenarios = _by_id(run_replay())

    invalid = scenarios["llm_invalid_output"]
    assert invalid["interpretation"] == {
        "attempted": 1,
        "rejected": 1,
        "unavailable": 0,
        "valid": 0,
    }
    assert invalid["claims"]["supported"] == 0
    assert invalid["claims"]["rejected_or_unsupported"] >= 1
    assert invalid["fallback_used"] is True
    assert invalid["caregiver_event_count"] == 1

    unavailable = scenarios["llm_unavailable"]
    assert unavailable["interpretation"]["unavailable"] == 1
    assert unavailable["fallback_used"] is True

    urgent = scenarios["fall_like"]
    assert urgent["urgent_triggered"] is True
    assert urgent["packet_count"] == 0
    assert urgent["interpretation"]["attempted"] == 0
    assert urgent["caregiver_event_count"] == 1
    assert urgent["provisional_urgent_event"] is True


def test_acknowledgment_recovery_recurrence_and_learning_remain_separate() -> None:
    # Break caught: attention, anomaly closure, event history, or semantic learning collapse together.
    scenarios = _by_id(run_replay())

    acknowledged = scenarios["continuing_acknowledged_anomaly"]
    assert acknowledged["attention_suppressed"] is True
    assert acknowledged["anomaly_final_state"] == "active"
    assert acknowledged["event_status"] == "acknowledged"
    assert acknowledged["caregiver_event_count"] == 1

    recurrence = scenarios["recurrence_after_recovery"]
    assert recurrence["anomaly_final_state"] == "active"
    assert recurrence["closed_anomaly_count"] == 1
    assert recurrence["caregiver_event_count"] == 2
    assert recurrence["resolved_event_count"] == 0
    assert recurrence["recurrence_linked"] is True

    preentered = scenarios["preentered_new_behavior"]
    assert preentered["semantic_context_active"] is True
    assert preentered["numerical_baseline_changed"] is False
    post_event = scenarios["post_event_new_behavior"]
    assert post_event["semantic_context_active"] is True
    assert post_event["numerical_baseline_changed"] is True
    assert post_event["clean_adoption_windows"] == 5


def test_canonical_json_is_byte_identical_across_fresh_runs() -> None:
    # Break caught: wall time, UUIDs, unordered containers, or temp paths leak into output.
    first = canonical_json_bytes(run_replay())
    second = canonical_json_bytes(run_replay())

    assert first == second
    decoded = json.loads(first)
    assert "wall_clock" not in decoded
    assert decoded["aggregate"]["replay_reproducible"] is True


def test_replay_module_cli_emits_only_parseable_canonical_json() -> None:
    # Break caught: package import side effects add warnings or prose to the JSON boundary.
    completed = subprocess.run(
        [sys.executable, "-m", "evals.monitoring.replay", "--format", "json"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )

    assert completed.returncode == 0
    assert completed.stderr == b""
    assert completed.stdout == canonical_json_bytes(json.loads(completed.stdout))


def test_checkpoint_reports_failures_and_cli_prints_founder_walkthrough() -> None:
    # Break caught: the checkpoint prints success or exits zero after a safety regression.
    report = run_replay()
    assert checkpoint_failures(report) == ()

    contaminated = deepcopy(report)
    contaminated["aggregate"]["baseline_contamination"][
        "contaminated_learning_windows"
    ] = 1
    assert "baseline contamination is not zero" in checkpoint_failures(contaminated)

    completed = subprocess.run(
        [sys.executable, "-m", "backend.app.checkpoints.monitoring_intelligence"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "ordinary variation stayed quiet" in completed.stdout
    assert "urgent fall-like evidence created provisional caregiver work without AI" in completed.stdout
    assert "acknowledgment quieted attention without closing the anomaly" in completed.stdout
    assert "recovery closed the anomaly only; recurrence created linked caregiver history" in completed.stdout
    assert "baseline contamination: 0; duplicate caregiver events: 0" in completed.stdout
