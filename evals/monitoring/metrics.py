"""Metrics derived only from deterministic replay records."""

from collections import Counter
from statistics import mean
from typing import Any


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
    resident_days = sum(float(record["resident_days"]) for record in records)
    meaningful = [record for record in records if record["meaningful_expected"]]
    captured = [
        record
        for record in meaningful
        if record["packet_count"] > 0 or record["urgent_triggered"]
    ]
    missed = sorted(
        record["scenario_id"]
        for record in meaningful
        if record not in captured
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
    evaluated_learning = sum(int(record["evaluated_learning_windows"]) for record in records)
    eligible_learning = sum(int(record["eligible_learning_windows"]) for record in records)
    contaminated = sum(int(record["contaminated_learning_windows"]) for record in records)
    event_signal_groups = sum(int(record["event_signal_groups"]) for record in records)
    duplicate_events = sum(int(record["duplicate_event_count"]) for record in records)
    monitoring_counts = Counter(str(record["monitoring_state"]) for record in records)
    monitoring_durations: Counter[str] = Counter()
    for record in records:
        monitoring_durations[str(record["monitoring_state"])] += float(record["monitoring_duration_seconds"])
    interpretation = {
        key: sum(int(record["interpretation"][key]) for record in records)
        for key in ("attempted", "valid", "rejected", "unavailable")
    }
    supported = sum(int(record["claims"]["supported"]) for record in records)
    rejected = sum(int(record["claims"]["rejected_or_unsupported"]) for record in records)
    duration_errors = [
        abs(float(record["actual_event_duration_seconds"]) - float(record["expected_event_duration_seconds"]))
        for record in records
        if record["expected_event_duration_seconds"] is not None
        and record["actual_event_duration_seconds"] is not None
    ]
    return {
        "scenario_count": len(records),
        "simulated_resident_days": resident_days,
        "meaningful_anomaly_recall": {
            "captured": len(captured),
            "expected": len(meaningful),
            "rate": _rate(len(captured), len(meaningful)),
        },
        "false_packets_per_resident_day": {
            "count": false_packets,
            "resident_days": resident_days,
            "rate": _rate(false_packets, resident_days),
        },
        "false_caregiver_events_per_resident_day": {
            "count": false_events,
            "resident_days": resident_days,
            "rate": _rate(false_events, resident_days),
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
            "mean_absolute_seconds": round(mean(duration_errors), 6) if duration_errors else None,
            "maximum_absolute_seconds": max(duration_errors) if duration_errors else None,
        },
        "baseline_contamination": {
            "contaminated_learning_windows": contaminated,
            "eligible_learning_windows": eligible_learning,
            "evaluated_learning_windows": evaluated_learning,
            "rate": _rate(contaminated, evaluated_learning),
        },
        "monitoring_states": {
            "counts": {state: monitoring_counts.get(state, 0) for state in ("active", "limited", "paused", "unavailable")},
            "durations_seconds": {state: monitoring_durations.get(state, 0.0) for state in ("active", "limited", "paused", "unavailable")},
        },
        "interpretation": interpretation,
        "claims": {
            "supported": supported,
            "rejected_or_unsupported": rejected,
        },
        "replay_reproducible": False,
    }


def safety_gates(records: list[dict[str, Any]], aggregate: dict[str, Any]) -> dict[str, bool]:
    by_id = {record["scenario_id"]: record for record in records}
    return {
        "baseline_contamination_zero": aggregate["baseline_contamination"]["contaminated_learning_windows"] == 0,
        "duplicate_events_zero": aggregate["duplicate_events"]["duplicate_event_count"] == 0,
        "invalid_ai_rejected": (
            by_id["llm_invalid_output"]["interpretation"]["rejected"] > 0
            and by_id["llm_invalid_output"]["interpretation"]["valid"] == 0
        ),
        "ordinary_routine_degraded_resident_events_zero": all(
            record["resident_specific_event_count"] == 0
            for record in records
            if record["quiet_resident_work_required"]
        ),
        "urgent_fall_like_independent_of_ai": (
            by_id["fall_like"]["urgent_triggered"]
            and by_id["fall_like"]["caregiver_event_count"] == 1
            and by_id["fall_like"]["interpretation"]["attempted"] == 0
        ),
    }


__all__ = ["calculate_metrics", "safety_gates"]
