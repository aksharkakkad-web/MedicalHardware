from backend.app.ai.client import DeterministicFakeLLMClient
from evals.monitoring.scenarios import run_scenario, run_scenarios


def test_run_scenario_preserves_default_record_and_captures_ai_exchange() -> None:
    expected = next(
        record
        for record in run_scenarios()
        if record["scenario_id"] == "sustained_movement_change"
    )

    execution = run_scenario(
        "sustained_movement_change",
        llm_client=DeterministicFakeLLMClient(),
    )

    assert execution.record["scenario_id"] == expected["scenario_id"]
    assert len(execution.interpretation_requests) == 1
    assert len(execution.interpretation_results) == 1
    assert execution.interpretation_results[0].anomaly_id == execution.interpretation_requests[0].anomaly_id


def test_run_scenario_rejects_unknown_id() -> None:
    try:
        run_scenario("not_a_real_case")
    except ValueError as error:
        assert "unknown scenario_id" in str(error)
    else:
        raise AssertionError("unknown scenario id was accepted")
