from evals.monitoring.comparison import evaluate_release_gate


def test_release_gate_requires_exact_terra_and_sol_evidence_and_no_hard_failure() -> None:
    ready = evaluate_release_gate(
        terra_metrics={"completed": 5000, "hard_failure_count": 0},
        sol_metrics={"completed": 1000, "hard_failure_count": 0},
        paid_calls_approved=True,
    )
    blocked = evaluate_release_gate(
        terra_metrics={"completed": 5000, "hard_failure_count": 0},
        sol_metrics={"completed": 1000, "hard_failure_count": 1},
        paid_calls_approved=True,
    )

    assert ready["passed"] is True
    assert blocked["passed"] is False
    assert "sol_hard_gate_failure" in blocked["failures"]


def test_release_gate_never_authorizes_paid_calls_without_explicit_approval() -> None:
    result = evaluate_release_gate(
        terra_metrics={"completed": 5000, "hard_failure_count": 0},
        sol_metrics={"completed": 1000, "hard_failure_count": 0},
        paid_calls_approved=False,
    )

    assert result["passed"] is False
    assert "paid_calls_not_approved" in result["failures"]
