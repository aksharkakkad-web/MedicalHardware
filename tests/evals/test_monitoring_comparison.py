from pathlib import Path

import pytest

from evals.monitoring.artifacts import ArtifactRun
from evals.monitoring.comparison import compare_runs


def _run(root: Path, run_id: str, *, score: float, case_id: str = "case_1") -> Path:
    run = ArtifactRun.create(
        root,
        run_id=run_id,
        manifest={"mode": "gemini", "comparison_set": "fixed_v1", "provider": run_id},
    )
    run.append_chunk(
        "cases",
        0,
        [
            {
                "case_id": case_id,
                "case": {"cluster_id": "movement_change"},
                "grade": {
                    "passed": score == 1.0,
                    "hard_failures": [] if score == 1.0 else ["regression"],
                    "scores": {"event_behavior": score, "provenance": score},
                },
            }
        ],
    )
    run.write_checkpoint({"completed": 1, "next_index": 1})
    run.finalize(
        metrics={"case_count": 1, "hard_failure_count": int(score != 1.0)},
        hard_gates={"all_passed": score == 1.0},
        report="done",
    )
    return run.path


def test_comparison_pairs_identical_saved_cases_and_reports_regression(tmp_path: Path) -> None:
    first = _run(tmp_path, "model_a", score=1.0)
    second = _run(tmp_path, "model_b", score=0.0)

    comparison = compare_runs(first, second)

    assert comparison.paired_case_count == 1
    assert comparison.hard_gate_regression is True
    assert comparison.score_deltas["event_behavior"] == -1.0


def test_comparison_rejects_different_case_sets(tmp_path: Path) -> None:
    first = _run(tmp_path, "model_c", score=1.0, case_id="case_1")
    second = _run(tmp_path, "model_d", score=1.0, case_id="case_2")

    with pytest.raises(ValueError, match="identical case IDs"):
        compare_runs(first, second)
