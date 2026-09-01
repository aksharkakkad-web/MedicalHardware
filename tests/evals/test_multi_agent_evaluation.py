import gzip
import json

from backend.app.ai.analysis_orchestration import MultiAgentAnalysisOrchestrator
from evals.monitoring.artifacts import ArtifactRun
from evals.monitoring.grading import (
    MultiAgentExpectation,
    multi_agent_evaluation_record,
)
from evals.monitoring.metrics import calculate_multi_agent_metrics
from tests.ai.test_analysis_context import _memory, _packet
from tests.ai.test_analysis_orchestration import ScriptedAnalysisClient


def _run(mode: str = "complete"):
    client = ScriptedAnalysisClient(mode)
    run = MultiAgentAnalysisOrchestrator(
        recall_client=client,
        precision_client=client,
        final_client=client,
    ).analyze(_packet(), _memory())
    latencies = {
        stage: sum(
            request.stage.value == stage for request in client.calls
        ) * 2.0
        for stage in ("recall", "specialist", "final", "repair")
    }
    calls = {
        stage: sum(request.stage.value == stage for request in client.calls)
        for stage in ("recall", "specialist", "final", "repair")
    }
    return run, latencies, calls


def _expectation() -> MultiAgentExpectation:
    packet = _packet()
    return MultiAgentExpectation(
        possibility_labels=("routine movement", "sensor issue"),
        specialist_names=("routine_context", "signal_integrity"),
        final_disposition="observe",
        final_severity="watch",
        allowed_evidence_refs=packet.evidence_refs,
    )


def test_multi_agent_metrics_measure_each_stage_and_end_to_end_result() -> None:
    run, latencies, calls = _run()
    record = multi_agent_evaluation_record(
        "case_1",
        "routine_variation",
        run,
        _expectation(),
        stage_latencies_ms=latencies,
        stage_call_counts=calls,
    )

    metrics = calculate_multi_agent_metrics([record])

    assert metrics["possibility_recall"]["rate"] == 1.0
    assert metrics["routing_accuracy"]["rate"] == 1.0
    assert metrics["specialist_precision"]["rate"] == 1.0
    assert metrics["alternative_preservation"]["rate"] == 1.0
    assert metrics["hallucination_count"] == 0
    assert metrics["final_action_agreement"] == 1.0
    assert metrics["final_severity_agreement"] == 1.0
    assert metrics["stage_calls"] == {
        "final": 1,
        "recall": 1,
        "repair": 0,
        "specialist": 2,
    }


def test_metrics_record_missing_specialist_and_repair_without_hiding_them() -> None:
    missing, latencies, calls = _run("one_specialist_unavailable")
    repaired, repaired_latencies, repaired_calls = _run("repair_once")
    records = [
        multi_agent_evaluation_record(
            "case_missing",
            "sensor_degradation",
            missing,
            _expectation(),
            stage_latencies_ms=latencies,
            stage_call_counts=calls,
        ),
        multi_agent_evaluation_record(
            "case_repair",
            "movement_change",
            repaired,
            _expectation(),
            stage_latencies_ms=repaired_latencies,
            stage_call_counts=repaired_calls,
        ),
    ]

    metrics = calculate_multi_agent_metrics(records)

    assert metrics["unavailable_stage_cases"] == 1
    assert metrics["repair_rate"] == 0.5
    assert metrics["stage_calls"]["repair"] == 1


def test_stage_artifacts_are_redacted_checksummed_and_counted(tmp_path) -> None:
    run, latencies, calls = _run()
    record = multi_agent_evaluation_record(
        "case_artifact",
        "routine_variation",
        run,
        _expectation(),
        stage_latencies_ms=latencies,
        stage_call_counts=calls,
    )
    artifact = ArtifactRun.create(
        tmp_path,
        run_id="multi_agent_test",
        manifest={"provider_api_key": "AIzaThisWouldBeSecret123456789"},
    )
    path = artifact.append_chunk("responses", 0, (record,))
    artifact.write_checkpoint(
        {"attempted": 1, "completed": 1, "failed": 0, "completed_case_ids": []}
    )
    artifact.finalize(
        metrics=calculate_multi_agent_metrics([record]),
        hard_gates={"all_passed": True},
        report="synthetic multi-agent proof",
    )

    saved = gzip.decompress(path.read_bytes()).decode("utf-8")
    manifest = json.loads((artifact.path / "manifest.json").read_text())
    assert manifest["provider_api_key"] == "[REDACTED]"
    assert "AIzaThisWouldBeSecret" not in saved
    assert (artifact.path / "checksums.sha256").is_file()
