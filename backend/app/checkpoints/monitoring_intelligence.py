"""Plain-language founder checkpoint for Phase 5 monitoring intelligence."""

from typing import Any

from evals.monitoring.metrics import calculate_metrics, safety_gates
from evals.monitoring.replay import run_replay


def checkpoint_failures(report: dict[str, Any]) -> tuple[str, ...]:
    records = report["scenarios"]
    aggregate = report["aggregate"]
    recomputed = calculate_metrics(records)
    recomputed["replay_reproducible"] = aggregate.get(
        "replay_reproducible",
        False,
    )
    gates = safety_gates(
        records,
        recomputed,
        report.get("repository_restart"),
    )
    failures: list[str] = []
    if aggregate != recomputed:
        failures.append("reported aggregate metrics do not match scenario records")
    if report.get("safety_gates") != gates:
        failures.append("reported safety gates do not match executable gates")
    if recomputed["baseline_contamination"]["contaminated_learning_windows"] != 0:
        failures.append("baseline contamination is not zero")
    if recomputed["duplicate_events"]["duplicate_event_count"] != 0:
        failures.append("duplicate caregiver events are not zero")
    if recomputed["missed_meaningful_events"]:
        failures.append("meaningful synthetic scenarios were missed")
    if not recomputed["replay_reproducible"]:
        failures.append("fresh replay results are not byte-reproducible")
    failures.extend(
        f"safety gate failed: {name}"
        for name, passed in gates.items()
        if not passed
    )
    return tuple(dict.fromkeys(failures))


def walkthrough_lines(report: dict[str, Any]) -> tuple[str, ...]:
    scenarios = {item["scenario_id"]: item for item in report["scenarios"]}
    contamination = report["aggregate"]["baseline_contamination"]["contaminated_learning_windows"]
    duplicates = report["aggregate"]["duplicate_events"]["duplicate_event_count"]
    return (
        "Phase 5 synthetic normalized-fixture checkpoint",
        "ordinary variation stayed quiet",
        "resident-away/bathroom stayed awareness or quiet, not a resident warning",
        "flexible and pre-entered routines changed semantic context without instantly rewriting the numerical baseline",
        "meaningful sustained evidence opened an internal anomaly, produced a packet, and invoked deterministic fake AI",
        "malformed and unavailable AI fell back safely",
        "urgent fall-like evidence created provisional caregiver work without AI",
        "degradation and multi-person ambiguity remained operationally honest",
        "acknowledgment quieted attention without closing the anomaly",
        "recovery closed the anomaly only; recurrence created linked caregiver history",
        "five clean post-feedback windows adopted a new numerical normal",
        "repository restart preserved anomaly, interpretation, disposition, bridge, and caregiver-event lineage",
        f"baseline contamination: {contamination}; duplicate caregiver events: {duplicates}",
        (
            "measured synthetic recall: "
            f"{report['aggregate']['meaningful_anomaly_recall']['captured']}/"
            f"{report['aggregate']['meaningful_anomaly_recall']['expected']}; "
            f"scenarios: {len(scenarios)}"
        ),
        "This is engineering evidence only; it is not clinical, real-provider, raw-stream, or real-hardware validation.",
    )


def main() -> int:
    report = run_replay()
    failures = checkpoint_failures(report)
    if failures:
        print("Phase 5 synthetic normalized-fixture checkpoint")
        for failure in failures:
            print(f"FAILED: {failure}")
        return 1
    for line in walkthrough_lines(report):
        print(line)
    print("PHASE 5 BACKEND CHECKPOINT READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["checkpoint_failures", "main", "walkthrough_lines"]
