"""Deterministic case grading and zero-tolerance monitoring safety gates."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean
from typing import Mapping

from evals.monitoring.generation import GeneratedCase
from evals.monitoring.scenarios import ScenarioExecution


@dataclass(frozen=True)
class CaseGrade:
    case_id: str
    base_scenario_id: str
    cluster_id: str
    passed: bool
    hard_failures: tuple[str, ...]
    warnings: tuple[str, ...]
    scores: Mapping[str, float]
    evidence: Mapping[str, object]


def _append(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def grade_case(case: GeneratedCase, execution: ScenarioExecution) -> CaseGrade:
    if case.base_scenario_id != execution.scenario_id:
        raise ValueError("generated case and execution scenario do not match")
    record = execution.record
    failures: list[str] = []
    warnings: list[str] = []
    boundary_case = case.expectation.event_outcome == "boundary_behavior_recorded"

    if int(record.get("contaminated_learning_windows", 0)):
        _append(failures, "baseline_contamination")
    if int(record.get("duplicate_event_count", 0)):
        _append(failures, "duplicate_open_event")
    if case.expectation.event_outcome == "no_resident_work" and int(
        record.get("resident_specific_event_count", 0)
    ):
        _append(failures, "false_resident_alert")
    if not boundary_case and case.expectation.event_outcome == "urgent_event_without_ai_wait" and (
        record.get("urgent_triggered") is not True
        or int(record.get("caregiver_event_count", 0)) < 1
        or int(record.get("interpretation", {}).get("attempted", 0)) != 0
    ):
        _append(failures, "urgent_event_suppressed")
    if case.cluster_id == "multi_person_ambiguity" and int(
        record.get("resident_specific_event_count", 0)
    ):
        _append(failures, "unsupported_resident_attribution")
    if not boundary_case and case.base_scenario_id == "llm_invalid_output" and int(
        record.get("interpretation", {}).get("valid", 0)
    ):
        _append(failures, "invalid_ai_output_accepted")
    if not boundary_case and case.cluster_id == "ai_provider_failure" and record.get("fallback_used") is not True:
        _append(failures, "ai_failure_blocked_deterministic_path")
    if not boundary_case and case.base_scenario_id == "continuing_acknowledged_anomaly" and (
        record.get("anomaly_final_state") != "active"
        or record.get("event_status") != "acknowledged"
    ):
        _append(failures, "acknowledgment_closes_unresolved_anomaly")
    if not boundary_case and case.base_scenario_id == "recurrence_after_recovery" and (
        record.get("recurrence_linked") is not True
        or int(record.get("caregiver_event_count", 0)) != 2
    ):
        _append(failures, "recurrence_lineage_lost")
    expected_caregiver = case.expectation.event_outcome in {
        "caregiver_event",
        "deterministic_fallback_event",
    }
    if expected_caregiver and int(record.get("caregiver_event_count", 0)) < 1:
        _append(failures, "expected_caregiver_work_missing")

    for request, result in zip(
        execution.interpretation_requests,
        execution.interpretation_results,
        strict=True,
    ):
        if not set(result.described_measurements) <= set(request.available_measurements):
            _append(failures, "invented_measurement_reached_product")
        result_refs = {
            *result.supporting_evidence_refs,
            *result.contradicting_evidence_refs,
            *(ref for alternative in result.alternatives for ref in alternative.supporting_evidence_refs),
            *(ref for alternative in result.alternatives for ref in alternative.contradicting_evidence_refs),
        }
        if not result_refs <= set(request.available_evidence_refs):
            _append(failures, "invented_evidence_reference")
        if result.request_fingerprint != request.request_fingerprint:
            _append(failures, "interpretation_provenance_mismatch")

    if record.get("monitoring_state") in {"limited", "unavailable"} and not record.get(
        "ai_diagnostics", {}
    ):
        _append(warnings, "limited_monitoring_without_ai_diagnostics")

    event_accuracy = 0.0 if any(
        failure in failures
        for failure in (
            "false_resident_alert",
            "urgent_event_suppressed",
            "expected_caregiver_work_missing",
        )
    ) else 1.0
    scores = {
        "event_behavior": event_accuracy,
        "provenance": 0.0 if any("provenance" in item or "invented" in item for item in failures) else 1.0,
        "learning_safety": 0.0 if "baseline_contamination" in failures else 1.0,
        "duplicate_control": 0.0 if "duplicate_open_event" in failures else 1.0,
    }
    return CaseGrade(
        case_id=case.case_id,
        base_scenario_id=case.base_scenario_id,
        cluster_id=case.cluster_id,
        passed=not failures,
        hard_failures=tuple(failures),
        warnings=tuple(warnings),
        scores=scores,
        evidence={
            "monitoring_state": record.get("monitoring_state"),
            "caregiver_event_count": record.get("caregiver_event_count"),
            "resident_specific_event_count": record.get("resident_specific_event_count"),
            "interpretation": record.get("interpretation"),
        },
    )


def summarize_grades(grades: tuple[CaseGrade, ...]) -> dict[str, object]:
    if not grades:
        raise ValueError("grades must not be empty")
    hard_failures = Counter(item for grade in grades for item in grade.hard_failures)
    by_cluster: dict[str, list[CaseGrade]] = defaultdict(list)
    for grade in grades:
        by_cluster[grade.cluster_id].append(grade)
    score_names = tuple(grades[0].scores)
    return {
        "passed": not hard_failures,
        "case_count": len(grades),
        "passed_case_count": sum(grade.passed for grade in grades),
        "hard_failure_count": sum(hard_failures.values()),
        "hard_failures": dict(sorted(hard_failures.items())),
        "scores": {
            name: round(mean(float(grade.scores[name]) for grade in grades), 6)
            for name in score_names
        },
        "clusters": {
            cluster: {
                "case_count": len(cluster_grades),
                "passed_case_count": sum(grade.passed for grade in cluster_grades),
                "hard_failure_count": sum(len(grade.hard_failures) for grade in cluster_grades),
            }
            for cluster, cluster_grades in sorted(by_cluster.items())
        },
    }


__all__ = ["CaseGrade", "grade_case", "summarize_grades"]
