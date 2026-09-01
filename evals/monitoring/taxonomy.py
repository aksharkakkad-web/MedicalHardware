"""Stable product taxonomy and expectations for monitoring evaluation cases."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioCluster:
    cluster_id: str
    title: str
    safety_critical: bool
    description: str


@dataclass(frozen=True)
class ScenarioExpectation:
    scenario_id: str
    cluster_id: str
    event_outcome: str
    interpretation_outcome: str
    feedback_outcome: str
    forbidden_outcomes: tuple[str, ...]


_CLUSTERS = (
    ScenarioCluster("normal_variation", "Normal human variation", False, "Ordinary movement and stillness must remain quiet."),
    ScenarioCluster("temporary_absence", "Temporary room absence", False, "Bathroom and other short absences pause resident-specific monitoring without an alert."),
    ScenarioCluster("routine_variation", "Flexible routines", False, "Day-to-day schedule variation and temporary context must not become a rigid baseline."),
    ScenarioCluster("multi_person_ambiguity", "Visitors and attribution ambiguity", True, "Ambiguous occupancy must limit attribution rather than guess who did what."),
    ScenarioCluster("movement_change", "Sustained movement change", True, "Persistent movement deviations may form an anomaly while isolated variation stays quiet."),
    ScenarioCluster("inactivity", "Sustained inactivity", True, "Persistent, well-supported inactivity should create caregiver awareness."),
    ScenarioCluster("fall_like", "Fall-like motion", True, "Corroborated urgent motion creates an immediate deterministic event without waiting for AI."),
    ScenarioCluster("respiration_change", "Respiration concern", True, "Respiration-related interpretation must be limited by measurement quality."),
    ScenarioCluster("sensor_degradation", "Missing or degraded sensing", True, "Stale, frozen, missing, or moved sensors must be reported as monitoring limitations."),
    ScenarioCluster("new_behavior_learning", "New behavior and learning", True, "Explicit feedback may create guarded, reversible resident-memory candidates."),
    ScenarioCluster("event_lifecycle", "Acknowledgment and recurrence", True, "Acknowledgment controls attention while recovery and recurrence preserve event lineage."),
    ScenarioCluster("ai_provider_failure", "AI failure and invalid output", True, "Provider failure must fall back safely and never block deterministic product behavior."),
)

REQUIRED_CLUSTER_IDS = tuple(cluster.cluster_id for cluster in _CLUSTERS)

_SCENARIO_CLUSTERS = {
    "normal_variation": "normal_variation",
    "sleep_reading_stillness": "normal_variation",
    "fall_like_confounder": "normal_variation",
    "random_bathroom_away": "temporary_absence",
    "flexible_routine": "routine_variation",
    "temporary_change": "routine_variation",
    "visitor_multi_person": "multi_person_ambiguity",
    "contradictory_sensors": "multi_person_ambiguity",
    "sustained_movement_change": "movement_change",
    "repetitive_movement": "movement_change",
    "unknown_anomaly": "movement_change",
    "inactivity": "inactivity",
    "fall_like": "fall_like",
    "respiration_quality_limited": "respiration_change",
    "missing_signal": "sensor_degradation",
    "stale_signal": "sensor_degradation",
    "frozen_signal": "sensor_degradation",
    "setup_change": "sensor_degradation",
    "preentered_new_behavior": "new_behavior_learning",
    "post_event_new_behavior": "new_behavior_learning",
    "continuing_acknowledged_anomaly": "event_lifecycle",
    "recurrence_after_recovery": "event_lifecycle",
    "llm_unavailable": "ai_provider_failure",
    "llm_invalid_output": "ai_provider_failure",
}

_EVENT_OUTCOMES = {
    "fall_like": "urgent_event_without_ai_wait",
    "random_bathroom_away": "awareness_only_room_absence",
    "sustained_movement_change": "caregiver_event",
    "repetitive_movement": "caregiver_event",
    "inactivity": "caregiver_event",
    "unknown_anomaly": "caregiver_event",
    "continuing_acknowledged_anomaly": "single_acknowledged_event_remains_open",
    "recurrence_after_recovery": "linked_recurrence_event",
    "llm_unavailable": "deterministic_fallback_event",
    "llm_invalid_output": "deterministic_fallback_event",
}

_INTERPRETATION_OUTCOMES = {
    "fall_like": "not_required_for_urgent_path",
    "llm_unavailable": "provider_unavailable",
    "llm_invalid_output": "invalid_output_rejected",
    "sustained_movement_change": "valid_bounded_explanation",
    "repetitive_movement": "valid_bounded_explanation",
    "inactivity": "valid_bounded_explanation",
    "unknown_anomaly": "valid_bounded_explanation",
    "continuing_acknowledged_anomaly": "valid_bounded_explanation",
    "recurrence_after_recovery": "valid_bounded_explanation",
}


def scenario_clusters() -> tuple[ScenarioCluster, ...]:
    return _CLUSTERS


def scenario_contracts() -> dict[str, ScenarioExpectation]:
    contracts: dict[str, ScenarioExpectation] = {}
    for scenario_id, cluster_id in _SCENARIO_CLUSTERS.items():
        event_outcome = _EVENT_OUTCOMES.get(scenario_id, "no_resident_work")
        interpretation_outcome = _INTERPRETATION_OUTCOMES.get(
            scenario_id, "no_semantic_claim_required"
        )
        feedback_outcome = (
            "explicit_feedback_may_propose_guarded_memory_change"
            if cluster_id == "new_behavior_learning"
            else "no_memory_change_without_explicit_feedback"
        )
        forbidden = ["invented_measurement", "cross_resident_attribution"]
        if event_outcome == "no_resident_work":
            forbidden.append("false_resident_alert")
        if scenario_id == "fall_like":
            forbidden.append("urgent_event_suppressed")
        if cluster_id == "event_lifecycle":
            forbidden.append("acknowledgment_closes_unresolved_anomaly")
        contracts[scenario_id] = ScenarioExpectation(
            scenario_id=scenario_id,
            cluster_id=cluster_id,
            event_outcome=event_outcome,
            interpretation_outcome=interpretation_outcome,
            feedback_outcome=feedback_outcome,
            forbidden_outcomes=tuple(forbidden),
        )
    return contracts
