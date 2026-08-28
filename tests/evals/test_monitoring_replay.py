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
    assert aggregate["false_packets_per_declared_exposure_unit"]["count"] == 0
    assert aggregate["false_caregiver_events_per_declared_exposure_unit"]["count"] == 0
    assert aggregate["declared_exposure_units"] == 24.0
    assert aggregate["replay_reproducible"] is True
    assert all(report["safety_gates"].values())
    assert {
        "required_scenarios_complete",
        "interpretation_terminal_accounting_balanced",
        "monitoring_state_reporting_matches_records",
        "repository_restart_lineage_hydrated",
    } <= set(report["safety_gates"])


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

    assert aggregate["false_packets_per_declared_exposure_unit"]["count"] == 2
    assert aggregate["false_caregiver_events_per_declared_exposure_unit"]["count"] == 1
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
    assert invalid["ai_diagnostics"]["validation_reason_count"] > 1
    assert invalid["ai_diagnostics"][
        "rejected_result_evidence_reference_count"
    ] >= 1
    assert invalid["fallback_used"] is True
    assert invalid["caregiver_event_count"] == 1

    unavailable = scenarios["llm_unavailable"]
    assert unavailable["interpretation"]["unavailable"] == 1
    assert unavailable["ai_diagnostics"][
        "rejected_result_evidence_reference_count"
    ] == 0
    assert unavailable["fallback_used"] is True

    urgent = scenarios["fall_like"]
    assert urgent["urgent_triggered"] is True
    assert urgent["packet_count"] == 0
    assert urgent["interpretation"]["attempted"] == 0
    assert urgent["caregiver_event_count"] == 1
    assert urgent["provisional_urgent_event"] is True

    for scenario in scenarios.values():
        outcomes = scenario["interpretation"]
        assert outcomes["attempted"] == (
            outcomes["valid"] + outcomes["rejected"] + outcomes["unavailable"]
        )


def test_nonurgent_ai_request_uses_explicit_selected_resident_context() -> None:
    # Break caught: resident context is looked up beside orchestration but never enters AI.
    sustained = _by_id(run_replay())["sustained_movement_change"]
    provenance = sustained["context_provenance"]

    assert provenance["explicit_selection"] is True
    assert provenance["selected_entry_ids"] == ["sustained_movement_context"]
    assert provenance["retrieved_context_refs"] == [
        "resident-memory://resident_demo_a/1/entries/sustained_movement_context"
    ]
    assert provenance["result_request_fingerprint_matches"] is True


def test_repository_restart_hydrates_complete_intelligence_event_lineage() -> None:
    # Break caught: replay proves in-memory behavior while Task 8 hydration is disconnected.
    restart = run_replay()["repository_restart"]

    assert restart == {
        "anomaly_revision_hydrated": True,
        "bridge_hydrated": True,
        "disposition_hydrated": True,
        "event_hydrated": True,
        "event_lineage_matches": True,
        "exact_signal_replay_deduplicated": True,
        "interpretation_hydrated": True,
    }


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
    assert "reported aggregate metrics do not match scenario records" in checkpoint_failures(
        contaminated
    )

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


def _assert_checkpoint_mutation_fails(mutator) -> None:
    report = deepcopy(run_replay())
    mutator(report)
    assert checkpoint_failures(report)


def test_checkpoint_rejects_a_missing_required_scenario() -> None:
    _assert_checkpoint_mutation_fails(
        lambda report: report["scenarios"].pop()
    )


def test_checkpoint_rejects_unearned_quiet_caregiver_event_claims() -> None:
    def mutate(report) -> None:
        normal = _by_id(report)["normal_variation"]
        normal["caregiver_event_count"] = 1
        normal["resident_specific_event_count"] = 1

    _assert_checkpoint_mutation_fails(mutate)


def test_checkpoint_rejects_acknowledgment_closing_the_anomaly() -> None:
    def mutate(report) -> None:
        _by_id(report)["continuing_acknowledged_anomaly"][
            "anomaly_final_state"
        ] = "closed"

    _assert_checkpoint_mutation_fails(mutate)


def test_checkpoint_rejects_broken_recovery_or_recurrence_lineage() -> None:
    def mutate(report) -> None:
        recurrence = _by_id(report)["recurrence_after_recovery"]
        recurrence["closed_anomaly_count"] = 0
        recurrence["recurrence_linked"] = False

    _assert_checkpoint_mutation_fails(mutate)


def test_checkpoint_rejects_unearned_new_normal_adoption() -> None:
    def mutate(report) -> None:
        _by_id(report)["preentered_new_behavior"][
            "numerical_baseline_changed"
        ] = True

    _assert_checkpoint_mutation_fails(mutate)


def test_checkpoint_rejects_ai_failure_without_objective_fallback() -> None:
    def mutate(report) -> None:
        _by_id(report)["llm_unavailable"]["fallback_used"] = False

    _assert_checkpoint_mutation_fails(mutate)


def test_checkpoint_rejects_unbalanced_ai_terminal_outcomes() -> None:
    def mutate(report) -> None:
        _by_id(report)["llm_invalid_output"]["interpretation"]["attempted"] = 2

    _assert_checkpoint_mutation_fails(mutate)


def test_checkpoint_rejects_false_packet_or_event_regression() -> None:
    def mutate(report) -> None:
        normal = _by_id(report)["normal_variation"]
        normal["packet_count"] = 1
        normal["caregiver_event_count"] = 1

    _assert_checkpoint_mutation_fails(mutate)


def test_checkpoint_rejects_monitoring_state_reporting_drift() -> None:
    def mutate(report) -> None:
        report["aggregate"]["monitoring_states"]["counts"]["active"] += 1

    _assert_checkpoint_mutation_fails(mutate)


def test_checkpoint_rejects_repository_restart_lineage_gap() -> None:
    def mutate(report) -> None:
        report["repository_restart"]["bridge_hydrated"] = False

    _assert_checkpoint_mutation_fails(mutate)
