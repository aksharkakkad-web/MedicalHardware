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


def test_run_scenario_captures_provider_failure_without_hiding_fallback() -> None:
    class FailingClient:
        def interpret(self, request):
            raise RuntimeError("sanitized provider failure")

    execution = run_scenario("sustained_movement_change", llm_client=FailingClient())

    assert execution.interpretation_requests
    assert execution.interpretation_results == ()
    assert execution.provider_errors == ("RuntimeError: sanitized provider failure",)
    assert execution.record["fallback_used"] is True


def test_run_scenario_binds_provider_model_version_into_the_ai_request() -> None:
    class VersionedProvider(DeterministicFakeLLMClient):
        model = "gemini-3.5-flash"

    execution = run_scenario(
        "sustained_movement_change",
        llm_client=VersionedProvider(),
    )

    assert execution.interpretation_requests[0].model_id == "gemini"
    assert execution.interpretation_requests[0].model_version == "gemini-3.5-flash"
    assert execution.interpretation_results[0].model_version == "gemini-3.5-flash"
