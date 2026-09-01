"""Paired artifact comparison and production release-gate contracts."""

from dataclasses import dataclass
import gzip
import json
from pathlib import Path
from statistics import mean
from typing import Mapping

from evals.monitoring.artifacts import open_artifact_run


@dataclass(frozen=True)
class RunComparison:
    run_a: str
    run_b: str
    provider_a: str
    provider_b: str
    paired_case_count: int
    hard_gate_regression: bool
    score_deltas: Mapping[str, float]
    cluster_deltas: Mapping[str, Mapping[str, float]]


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return value


def _case_records(path: Path) -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for chunk in sorted((path / "cases").glob("*.jsonl.gz")):
        for line in gzip.decompress(chunk.read_bytes()).decode("utf-8").splitlines():
            record = json.loads(line)
            case_id = record.get("case_id")
            if not isinstance(case_id, str) or case_id in records:
                raise ValueError("artifact contains invalid or duplicate case_id")
            records[case_id] = record
    return records


def _scores(record: dict[str, object]) -> dict[str, float]:
    grade = record.get("grade")
    if not isinstance(grade, dict) or not isinstance(grade.get("scores"), dict):
        raise ValueError("case record is missing grade scores")
    return {str(key): float(value) for key, value in grade["scores"].items()}


def _hard_failure_count(record: dict[str, object]) -> int:
    grade = record.get("grade")
    if not isinstance(grade, dict) or not isinstance(grade.get("hard_failures"), list):
        raise ValueError("case record is missing hard failures")
    return len(grade["hard_failures"])


def _cluster(record: dict[str, object]) -> str:
    case = record.get("case")
    if not isinstance(case, dict) or not isinstance(case.get("cluster_id"), str):
        raise ValueError("case record is missing cluster_id")
    return case["cluster_id"]


def compare_runs(run_a_path: Path, run_b_path: Path) -> RunComparison:
    run_a = open_artifact_run(run_a_path)
    run_b = open_artifact_run(run_b_path)
    manifest_a = _read_json(run_a.path / "manifest.json")
    manifest_b = _read_json(run_b.path / "manifest.json")
    if manifest_a.get("comparison_set") != manifest_b.get("comparison_set"):
        raise ValueError("runs use different comparison sets")
    cases_a = _case_records(run_a.path)
    cases_b = _case_records(run_b.path)
    if set(cases_a) != set(cases_b):
        raise ValueError("comparison requires identical case IDs")
    if not cases_a:
        raise ValueError("comparison runs contain no cases")
    score_names = set.intersection(*[set(_scores(record)) for record in (*cases_a.values(), *cases_b.values())])
    deltas = {
        name: round(
            mean(_scores(cases_b[case_id])[name] - _scores(cases_a[case_id])[name] for case_id in sorted(cases_a)),
            6,
        )
        for name in sorted(score_names)
    }
    cluster_deltas: dict[str, dict[str, float]] = {}
    for cluster in sorted({_cluster(record) for record in cases_a.values()}):
        ids = [case_id for case_id, record in cases_a.items() if _cluster(record) == cluster]
        cluster_deltas[cluster] = {
            name: round(mean(_scores(cases_b[case_id])[name] - _scores(cases_a[case_id])[name] for case_id in ids), 6)
            for name in sorted(score_names)
        }
    hard_a = sum(_hard_failure_count(record) for record in cases_a.values())
    hard_b = sum(_hard_failure_count(record) for record in cases_b.values())
    return RunComparison(
        run_a=run_a.run_id,
        run_b=run_b.run_id,
        provider_a=str(manifest_a.get("provider", "unknown")),
        provider_b=str(manifest_b.get("provider", "unknown")),
        paired_case_count=len(cases_a),
        hard_gate_regression=hard_b > hard_a,
        score_deltas=deltas,
        cluster_deltas=cluster_deltas,
    )


def evaluate_release_gate(
    *,
    terra_metrics: Mapping[str, object],
    sol_metrics: Mapping[str, object],
    paid_calls_approved: bool,
) -> dict[str, object]:
    failures: list[str] = []
    if not paid_calls_approved:
        failures.append("paid_calls_not_approved")
    if int(terra_metrics.get("completed", 0)) < 5_000:
        failures.append("terra_case_count_incomplete")
    if int(sol_metrics.get("completed", 0)) < 1_000:
        failures.append("sol_case_count_incomplete")
    if int(terra_metrics.get("hard_failure_count", 0)):
        failures.append("terra_hard_gate_failure")
    if int(sol_metrics.get("hard_failure_count", 0)):
        failures.append("sol_hard_gate_failure")
    return {
        "passed": not failures,
        "failures": failures,
        "required_terra_cases": 5_000,
        "required_sol_cases": 1_000,
        "paid_calls_approved": paid_calls_approved,
    }


__all__ = ["RunComparison", "compare_runs", "evaluate_release_gate"]
