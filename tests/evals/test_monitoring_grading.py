from dataclasses import replace

from evals.monitoring.generation import canonical_cases
from evals.monitoring.grading import grade_case, summarize_grades
from evals.monitoring.scenarios import ScenarioExecution, run_scenario


def _case(base_scenario_id: str):
    return next(
        case
        for case in canonical_cases()
        if case.base_scenario_id == base_scenario_id and case.perturbation_kind == "reference"
    )


def test_reference_normal_and_urgent_cases_pass_exact_expectations() -> None:
    normal = grade_case(_case("normal_variation"), run_scenario("normal_variation"))
    urgent = grade_case(_case("fall_like"), run_scenario("fall_like"))

    assert normal.passed is True
    assert urgent.passed is True
    assert normal.hard_failures == ()
    assert urgent.hard_failures == ()


def test_grader_detects_false_work_and_urgent_suppression() -> None:
    normal_execution = run_scenario("normal_variation")
    normal_record = dict(normal_execution.record)
    normal_record["resident_specific_event_count"] = 1
    normal = grade_case(
        _case("normal_variation"),
        replace(normal_execution, record=normal_record),
    )

    urgent_execution = run_scenario("fall_like")
    urgent_record = dict(urgent_execution.record)
    urgent_record["urgent_triggered"] = False
    urgent_record["caregiver_event_count"] = 0
    urgent = grade_case(
        _case("fall_like"),
        replace(urgent_execution, record=urgent_record),
    )

    assert "false_resident_alert" in normal.hard_failures
    assert "urgent_event_suppressed" in urgent.hard_failures


def test_summary_keeps_hard_failures_above_average_scores() -> None:
    passing = grade_case(_case("normal_variation"), run_scenario("normal_variation"))
    failed_execution = run_scenario("normal_variation")
    failed_record = dict(failed_execution.record)
    failed_record["duplicate_event_count"] = 1
    failing = grade_case(
        _case("normal_variation"),
        replace(failed_execution, record=failed_record),
    )

    summary = summarize_grades((passing, failing))

    assert summary["passed"] is False
    assert summary["hard_failure_count"] == 1
    assert summary["case_count"] == 2
