from dataclasses import replace

from evals.monitoring.generation import canonical_cases
from evals.monitoring.grading import grade_case
from evals.monitoring.scenarios import run_scenario


def _case(scenario_id: str):
    return next(case for case in canonical_cases() if case.case_id == f"{scenario_id}__reference")


def test_acknowledgment_cannot_close_an_unresolved_anomaly() -> None:
    execution = run_scenario("continuing_acknowledged_anomaly")
    record = dict(execution.record)
    record["anomaly_final_state"] = "closed"

    grade = grade_case(_case("continuing_acknowledged_anomaly"), replace(execution, record=record))

    assert "acknowledgment_closes_unresolved_anomaly" in grade.hard_failures


def test_baseline_contamination_and_duplicate_events_are_zero_tolerance() -> None:
    execution = run_scenario("sustained_movement_change")
    record = dict(execution.record)
    record["contaminated_learning_windows"] = 1
    record["duplicate_event_count"] = 1

    grade = grade_case(_case("sustained_movement_change"), replace(execution, record=record))

    assert "baseline_contamination" in grade.hard_failures
    assert "duplicate_open_event" in grade.hard_failures
