import json
from threading import Lock
import time

from backend.app.ai.analysis_contracts import AnalysisState, StageResponse, StageStatus
from backend.app.ai.analysis_orchestration import MultiAgentAnalysisOrchestrator
from tests.ai.test_analysis_context import EVIDENCE_REF, _memory, _packet


def _possibility(possibility_id: str, label: str) -> dict[str, object]:
    return {
        "possibility_id": possibility_id,
        "label": label,
        "confidence": "medium",
        "supporting_evidence_refs": [EVIDENCE_REF],
        "contradicting_evidence_refs": [],
        "missing_information": ["direct confirmation"],
        "rationale": f"Evidence leaves {label} plausible.",
    }


class ScriptedAnalysisClient:
    def __init__(self, mode: str = "complete") -> None:
        self.mode = mode
        self.calls = []
        self._lock = Lock()
        self._active_specialists = 0
        self.max_active_specialists = 0

    def analyze(self, request):
        with self._lock:
            self.calls.append(request)
        if request.stage.value == "recall":
            if self.mode == "recall_unavailable":
                return self._response(request, None, status=StageStatus.UNAVAILABLE)
            payload = {
                "routing_id": "routing_1",
                "anomaly_id": request.anomaly_id,
                "packet_revision": request.packet_revision,
                "possibilities": [
                    _possibility("possibility_routine", "routine movement"),
                    _possibility("possibility_sensor", "sensor issue"),
                ],
                "assignments": [
                    {
                        "specialist": "routine_context",
                        "possibility_ids": ["possibility_routine"],
                        "reason": "Routine context may explain the activity.",
                    },
                    {
                        "specialist": "signal_integrity",
                        "possibility_ids": ["possibility_sensor"],
                        "reason": "Signal quality needs independent review.",
                    },
                ],
                "missing_information": ["direct confirmation"],
                "evidence_refs": [EVIDENCE_REF],
            }
            return self._response(request, payload)
        if request.stage.value == "specialist":
            specialist = request.skill_names[0]
            if self.mode == "one_specialist_unavailable" and specialist == "signal_integrity":
                return self._response(request, None, status=StageStatus.UNAVAILABLE)
            with self._lock:
                self._active_specialists += 1
                self.max_active_specialists = max(
                    self.max_active_specialists,
                    self._active_specialists,
                )
            time.sleep(0.02)
            try:
                request_payload = json.loads(request.payload_json)
                routed = request_payload["routing_possibilities"][0]
                possibility_id = routed["possibility_id"]
                label = routed["label"]
                payload = {
                    "assessment_id": f"assessment_{specialist}",
                    "specialist": specialist,
                    "anomaly_id": request.anomaly_id,
                    "packet_revision": request.packet_revision,
                    "assessed_possibility_ids": [possibility_id],
                    "possibilities": [_possibility(possibility_id, label)],
                    "severity": "watch",
                    "recommended_disposition": "observe",
                    "missing_information": ["direct confirmation"],
                    "contradictions": [],
                    "evidence_refs": [EVIDENCE_REF],
                }
                return self._response(request, payload)
            finally:
                with self._lock:
                    self._active_specialists -= 1
        if request.stage.value in {"final", "repair"}:
            if self.mode == "final_unavailable":
                return self._response(request, None, status=StageStatus.UNAVAILABLE)
            request_payload = json.loads(request.payload_json)
            routed = request_payload["routing_plan"]["possibilities"]
            required_ids = request_payload["output_contract"][
                "required_considered_possibility_ids"
            ]
            invalid = self.mode == "invalid_twice" or (
                self.mode == "repair_once" and request.stage.value == "final"
            )
            considered = ["possibility_skipped"] if invalid else required_ids
            payload = {
                "analysis_id": "analysis_final_1",
                "anomaly_id": request.anomaly_id,
                "packet_revision": request.packet_revision,
                "possibilities": routed,
                "severity": "watch",
                "recommended_disposition": "observe",
                "attribution_scope": "resident",
                "caregiver_summary": "Routine activity is plausible, with a sensor issue also possible.",
                "next_step": "Observe and review if the pattern continues.",
                "missing_information": ["direct confirmation"],
                "specialist_disagreements": [],
                "evidence_refs": [EVIDENCE_REF],
                "considered_possibility_ids": considered,
                "coverage_complete": True,
            }
            return self._response(request, payload)
        raise AssertionError(f"unexpected stage: {request.stage}")

    @staticmethod
    def _response(request, payload, *, status=StageStatus.COMPLETE):
        return StageResponse(
            stage=request.stage,
            status=status,
            request_fingerprint=request.request_fingerprint,
            payload_json=(
                None
                if payload is None
                else json.dumps(payload, sort_keys=True, separators=(",", ":"))
            ),
            model_id="scripted",
            model_version="scripted-v1",
            latency_ms=2,
            error="provider unavailable" if status is StageStatus.UNAVAILABLE else None,
        )


def _orchestrator(client: ScriptedAnalysisClient) -> MultiAgentAnalysisOrchestrator:
    return MultiAgentAnalysisOrchestrator(
        recall_client=client,
        precision_client=client,
        final_client=client,
        max_specialist_workers=4,
    )


def test_happy_path_runs_recall_parallel_specialists_and_one_final_combination() -> None:
    client = ScriptedAnalysisClient()
    result = _orchestrator(client).analyze(_packet(), _memory())

    assert result.state is AnalysisState.ANALYZED
    assert result.final_analysis is not None
    assert len(result.final_analysis.possibilities) == 2
    assert [request.stage.value for request in client.calls].count("recall") == 1
    assert [request.stage.value for request in client.calls].count("specialist") == 2
    assert [request.stage.value for request in client.calls].count("final") == 1
    assert [request.stage.value for request in client.calls].count("repair") == 0
    assert client.max_active_specialists == 2
    for request in client.calls:
        if request.stage.value == "specialist":
            assert "specialist_assessments" not in request.payload_json


def test_recall_failure_uses_family_routing_only_and_still_reaches_final_analysis() -> None:
    client = ScriptedAnalysisClient("recall_unavailable")
    result = _orchestrator(client).analyze(_packet(), _memory())

    assert result.state is AnalysisState.ANALYZED
    assert result.routing_plan is not None
    assert result.routing_plan.model_id == "deterministic_routing_only"
    assert "recall_unavailable" in result.errors


def test_missing_specialist_is_explicit_and_final_stage_can_preserve_uncertainty() -> None:
    client = ScriptedAnalysisClient("one_specialist_unavailable")
    result = _orchestrator(client).analyze(_packet(), _memory())

    assert result.state is AnalysisState.ANALYZED
    assert result.unavailable_specialists == ("signal_integrity",)
    final_request = next(item for item in client.calls if item.stage.value == "final")
    assert json.loads(final_request.payload_json)["unavailable_specialists"] == [
        "signal_integrity"
    ]


def test_invalid_final_result_gets_exactly_one_targeted_repair() -> None:
    client = ScriptedAnalysisClient("repair_once")
    result = _orchestrator(client).analyze(_packet(), _memory())

    assert result.state is AnalysisState.ANALYZED
    assert result.repair_count == 1
    assert [request.stage.value for request in client.calls].count("repair") == 1
    repair_request = next(item for item in client.calls if item.stage.value == "repair")
    assert "incomplete_possibility_coverage" in repair_request.payload_json


def test_second_invalid_result_becomes_staff_review_without_an_endless_loop() -> None:
    client = ScriptedAnalysisClient("invalid_twice")
    result = _orchestrator(client).analyze(_packet(), _memory())

    assert result.state is AnalysisState.NEEDS_STAFF_REVIEW
    assert result.final_analysis is None
    assert result.repair_count == 1
    assert [request.stage.value for request in client.calls].count("repair") == 1


def test_completed_checkpoint_is_reused_without_repeating_model_calls() -> None:
    client = ScriptedAnalysisClient()
    orchestrator = _orchestrator(client)
    first = orchestrator.analyze(_packet(), _memory())
    call_count = len(client.calls)

    replay = orchestrator.analyze(_packet(), _memory())

    assert replay == first
    assert len(client.calls) == call_count


def test_pending_checkpoint_is_retried_and_can_recover() -> None:
    client = ScriptedAnalysisClient("final_unavailable")
    orchestrator = _orchestrator(client)

    pending = orchestrator.analyze(_packet(), _memory())
    first_call_count = len(client.calls)
    client.mode = "complete"
    recovered = orchestrator.analyze(_packet(), _memory())

    assert pending.state is AnalysisState.ANALYSIS_PENDING
    assert recovered.state is AnalysisState.ANALYZED
    assert len(client.calls) > first_call_count
