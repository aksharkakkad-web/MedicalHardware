"""Metrics and executable founder gates derived from deterministic replay records."""

from collections import Counter
from statistics import mean
from typing import Any

from evals.monitoring.scenarios import REQUIRED_SCENARIO_IDS


def _rate(count: int, denominator: float) -> float:
    return round(count / denominator, 6) if denominator else 0.0


def _latency(records: list[dict[str, Any]], field: str) -> dict[str, Any]:
    values = [float(record[field]) for record in records if record[field] is not None]
    return {
        "available": len(values),
        "unavailable": len(records) - len(values),
        "mean_seconds": round(mean(values), 6) if values else None,
        "maximum_seconds": max(values) if values else None,
    }


def calculate_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    exposure_units = sum(
        float(record["declared_exposure_units"]) for record in records
    )
    meaningful = [record for record in records if record["meaningful_expected"]]
    captured = [
        record
        for record in meaningful
        if record["packet_count"] > 0 or record["urgent_triggered"]
    ]
    missed = sorted(
        record["scenario_id"]
        for record in meaningful
        if record["caregiver_event_expected"]
        and record["caregiver_event_count"] == 0
    )
    false_packets = sum(
        int(record["packet_count"])
        for record in records
        if not record["packet_expected"]
    )
    false_events = sum(
        int(record["caregiver_event_count"])
        for record in records
        if not record["caregiver_event_expected"]
    )
    evaluated_learning = sum(
        int(record["evaluated_learning_windows"]) for record in records
    )
    eligible_learning = sum(
        int(record["eligible_learning_windows"]) for record in records
    )
    contaminated = sum(
        int(record["contaminated_learning_windows"]) for record in records
    )
    event_signal_groups = sum(int(record["event_signal_groups"]) for record in records)
    duplicate_events = sum(int(record["duplicate_event_count"]) for record in records)
    monitoring_counts = Counter(str(record["monitoring_state"]) for record in records)
    monitoring_durations: Counter[str] = Counter()
    for record in records:
        monitoring_durations[str(record["monitoring_state"])] += float(
            record["monitoring_duration_seconds"]
        )
    interpretation = {
        key: sum(int(record["interpretation"][key]) for record in records)
        for key in ("attempted", "valid", "rejected", "unavailable")
    }


def calculate_multi_agent_metrics(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    if not records:
        raise ValueError("multi-agent records must not be empty")

    def normalized(values: object) -> set[str]:
        return {str(value).strip().casefold() for value in values or ()}

    expected_possibilities = sum(
        len(normalized(record["expected_possibility_labels"])) for record in records
    )
    recalled_possibilities = sum(
        len(
            normalized(record["expected_possibility_labels"])
            & normalized(record["routed_possibility_labels"])
        )
        for record in records
    )
    routed_total = sum(len(normalized(record["routed_specialists"])) for record in records)
    routed_correct = sum(
        len(
            normalized(record["expected_specialists"])
            & normalized(record["routed_specialists"])
        )
        for record in records
    )
    specialist_total = sum(
        len(normalized(record["specialist_possibility_labels"])) for record in records
    )
    specialist_correct = sum(
        len(
            normalized(record["expected_possibility_labels"])
            & normalized(record["specialist_possibility_labels"])
        )
        for record in records
    )
    alternatives_expected = sum(
        max(0, len(normalized(record["expected_possibility_labels"])) - 1)
        for record in records
    )
    alternatives_retained = sum(
        max(
            0,
            len(
                normalized(record["expected_possibility_labels"])
                & normalized(record["final_possibility_labels"])
            )
            - 1,
        )
        for record in records
    )
    latency_values: dict[str, list[float]] = {}
    calls: Counter[str] = Counter()
    for record in records:
        for stage, value in record.get("stage_latencies_ms", {}).items():
            latency_values.setdefault(str(stage), []).append(float(value))
        calls.update(
            {
                str(stage): int(count)
                for stage, count in record.get("stage_call_counts", {}).items()
            }
        )
    return {
        "case_count": len(records),
        "cluster_count": len({record["cluster_id"] for record in records}),
        "possibility_recall": {
            "recalled": recalled_possibilities,
            "expected": expected_possibilities,
            "rate": _rate(recalled_possibilities, expected_possibilities),
        },
        "routing_accuracy": {
            "correct": routed_correct,
            "routed": routed_total,
            "rate": _rate(routed_correct, routed_total),
        },
        "specialist_precision": {
            "supported": specialist_correct,
            "returned": specialist_total,
            "rate": _rate(specialist_correct, specialist_total),
        },
        "alternative_preservation": {
            "retained": alternatives_retained,
            "expected": alternatives_expected,
            "rate": _rate(alternatives_retained, alternatives_expected),
        },
        "hallucination_count": sum(
            len(record["hallucinated_evidence_refs"]) for record in records
        ),
        "final_action_agreement": _rate(
            sum(
                record["actual_disposition"] == record["expected_disposition"]
                for record in records
            ),
            len(records),
        ),
        "final_severity_agreement": _rate(
            sum(
                record["actual_severity"] == record["expected_severity"]
                for record in records
            ),
            len(records),
        ),
        "repair_rate": _rate(
            sum(int(record["repair_count"]) > 0 for record in records),
            len(records),
        ),
        "unavailable_stage_cases": sum(
            bool(record["unavailable_specialists"])
            or record["analysis_state"] != "analyzed"
            for record in records
        ),
        "stage_latency_ms": {
            stage: {
                "count": len(values),
                "mean": round(mean(values), 6),
                "maximum": max(values),
            }
            for stage, values in sorted(latency_values.items())
        },
        "stage_calls": dict(sorted(calls.items())),
    }
    diagnostics = {
        key: sum(int(record["ai_diagnostics"][key]) for record in records)
        for key in (
            "validation_reason_count",
            "validated_evidence_reference_count",
            "rejected_result_evidence_reference_count",
            "explicit_unsupported_conclusion_count",
        )
    }
    duration_errors = [
        abs(
            float(record["actual_event_duration_seconds"])
            - float(record["expected_event_duration_seconds"])
        )
        for record in records
        if record["expected_event_duration_seconds"] is not None
        and record["actual_event_duration_seconds"] is not None
    ]
    return {
        "scenario_count": len(records),
        "declared_exposure_units": exposure_units,
        "meaningful_anomaly_recall": {
            "captured": len(captured),
            "expected": len(meaningful),
            "rate": _rate(len(captured), len(meaningful)),
        },
        "false_packets_per_declared_exposure_unit": {
            "count": false_packets,
            "declared_exposure_units": exposure_units,
            "rate": _rate(false_packets, exposure_units),
        },
        "false_caregiver_events_per_declared_exposure_unit": {
            "count": false_events,
            "declared_exposure_units": exposure_units,
            "rate": _rate(false_events, exposure_units),
        },
        "missed_meaningful_events": missed,
        "latency": {
            "candidate": _latency(records, "candidate_latency_seconds"),
            "packet": _latency(records, "packet_latency_seconds"),
            "event": _latency(records, "event_latency_seconds"),
        },
        "duplicate_events": {
            "duplicate_event_count": duplicate_events,
            "event_signal_groups": event_signal_groups,
            "rate": _rate(duplicate_events, event_signal_groups),
        },
        "event_duration_error": {
            "available": len(duration_errors),
            "unavailable": len(records) - len(duration_errors),
            "mean_absolute_seconds": (
                round(mean(duration_errors), 6) if duration_errors else None
            ),
            "maximum_absolute_seconds": max(duration_errors) if duration_errors else None,
        },
        "baseline_contamination": {
            "contaminated_learning_windows": contaminated,
            "eligible_learning_windows": eligible_learning,
            "evaluated_learning_windows": evaluated_learning,
            "rate": _rate(contaminated, evaluated_learning),
        },
        "monitoring_states": {
            "counts": {
                state: monitoring_counts.get(state, 0)
                for state in ("active", "limited", "paused", "unavailable")
            },
            "durations_seconds": {
                state: monitoring_durations.get(state, 0.0)
                for state in ("active", "limited", "paused", "unavailable")
            },
        },
        "interpretation": interpretation,
        "ai_diagnostics": diagnostics,
        "replay_reproducible": False,
    }


def safety_gates(
    records: list[dict[str, Any]],
    aggregate: dict[str, Any],
    repository_restart: dict[str, bool] | None = None,
) -> dict[str, bool]:
    by_id = {record["scenario_id"]: record for record in records}

    def scenario(scenario_id: str) -> dict[str, Any]:
        return by_id.get(scenario_id, {})

    normal = scenario("normal_variation")
    away = scenario("random_bathroom_away")
    flexible = scenario("flexible_routine")
    preentered = scenario("preentered_new_behavior")
    post_event = scenario("post_event_new_behavior")
    sustained = scenario("sustained_movement_change")
    invalid = scenario("llm_invalid_output")
    unavailable = scenario("llm_unavailable")
    urgent = scenario("fall_like")
    acknowledged = scenario("continuing_acknowledged_anomaly")
    recurrence = scenario("recurrence_after_recovery")
    interpretation = aggregate["interpretation"]
    recomputed_monitoring = calculate_metrics(records)["monitoring_states"]
    quiet_records = [
        record for record in records if record.get("quiet_resident_work_required")
    ]
    restart = repository_restart or {}

    return {
        "required_scenarios_complete": (
            set(by_id) == set(REQUIRED_SCENARIO_IDS)
            and len(records) == len(REQUIRED_SCENARIO_IDS)
        ),
        "ordinary_variation_quiet": (
            normal.get("packet_count") == 0
            and normal.get("caregiver_event_count") == 0
        ),
        "bathroom_away_quiet_and_paused": (
            away.get("monitoring_state") == "paused"
            and away.get("resident_specific_event_count") == 0
        ),
        "routine_context_separate_from_baseline": (
            flexible.get("semantic_context_active") is True
            and flexible.get("numerical_baseline_changed") is False
            and preentered.get("semantic_context_active") is True
            and preentered.get("numerical_baseline_changed") is False
        ),
        "meaningful_sustained_path": (
            sustained.get("candidate_count") == 1
            and sustained.get("packet_count", 0) > 0
            and sustained.get("interpretation", {}).get("valid", 0) > 0
            and sustained.get("caregiver_event_count") == 1
            and sustained.get("context_provenance", {}).get("explicit_selection")
            is True
            and sustained.get("context_provenance", {}).get("selected_entry_ids")
            == ["sustained_movement_context"]
            and sustained.get("context_provenance", {}).get(
                "retrieved_context_refs"
            )
            == [
                "resident-memory://resident_demo_a/1/entries/"
                "sustained_movement_context"
            ]
            and sustained.get("context_provenance", {}).get(
                "result_request_fingerprint_matches"
            )
            is True
        ),
        "ai_failure_fallback_safe": (
            invalid.get("interpretation", {}).get("rejected") == 1
            and invalid.get("interpretation", {}).get("valid") == 0
            and invalid.get("fallback_used") is True
            and unavailable.get("interpretation", {}).get("unavailable") == 1
            and unavailable.get("fallback_used") is True
        ),
        "interpretation_terminal_accounting_balanced": (
            interpretation["attempted"]
            == interpretation["valid"]
            + interpretation["rejected"]
            + interpretation["unavailable"]
            and all(
                record["interpretation"]["attempted"]
                == record["interpretation"]["valid"]
                + record["interpretation"]["rejected"]
                + record["interpretation"]["unavailable"]
                for record in records
            )
        ),
        "urgent_fall_like_independent_of_ai": (
            urgent.get("urgent_triggered") is True
            and urgent.get("caregiver_event_count") == 1
            and urgent.get("interpretation", {}).get("attempted") == 0
        ),
        "degradation_and_ambiguity_honest": (
            scenario("visitor_multi_person").get("monitoring_state") == "limited"
            and scenario("respiration_quality_limited").get("monitoring_state")
            == "limited"
            and scenario("missing_signal").get("monitoring_state") == "limited"
            and scenario("stale_signal").get("monitoring_state") == "unavailable"
            and scenario("frozen_signal").get("monitoring_state") == "unavailable"
            and scenario("setup_change").get("monitoring_state") == "unavailable"
            and all(record["resident_specific_event_count"] == 0 for record in quiet_records)
        ),
        "acknowledgment_separate_from_anomaly": (
            acknowledged.get("attention_suppressed") is True
            and acknowledged.get("anomaly_final_state") == "active"
            and acknowledged.get("event_status") == "acknowledged"
            and acknowledged.get("caregiver_event_count") == 1
        ),
        "recovery_and_recurrence_lineage": (
            recurrence.get("closed_anomaly_count") == 1
            and recurrence.get("anomaly_final_state") == "active"
            and recurrence.get("caregiver_event_count") == 2
            and recurrence.get("resolved_event_count") == 0
            and recurrence.get("recurrence_linked") is True
        ),
        "new_normal_adoption_requires_clean_windows": (
            post_event.get("semantic_context_active") is True
            and post_event.get("numerical_baseline_changed") is True
            and post_event.get("clean_adoption_windows") == 5
        ),
        "false_packets_and_events_zero": (
            aggregate["false_packets_per_declared_exposure_unit"]["count"] == 0
            and aggregate[
                "false_caregiver_events_per_declared_exposure_unit"
            ]["count"]
            == 0
        ),
        "expected_caregiver_work_complete": all(
            not record["caregiver_event_expected"]
            or record["caregiver_event_count"] > 0
            for record in records
        ),
        "baseline_contamination_zero": (
            aggregate["baseline_contamination"]["contaminated_learning_windows"]
            == 0
        ),
        "duplicate_events_zero": (
            aggregate["duplicate_events"]["duplicate_event_count"] == 0
        ),
        "monitoring_state_reporting_matches_records": (
            aggregate["monitoring_states"] == recomputed_monitoring
        ),
        "repository_restart_lineage_hydrated": (
            bool(restart) and all(restart.values())
        ),
    }


__all__ = ["calculate_metrics", "calculate_multi_agent_metrics", "safety_gates"]
