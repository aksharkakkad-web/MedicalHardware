"""Deterministic structured provider used to load-test the staged AI pipeline."""

import json
from threading import Lock

from backend.app.ai.analysis_contracts import StageResponse, StageStatus


def _possibility(possibility_id: str, label: str, evidence_ref: str) -> dict[str, object]:
    return {
        "possibility_id": possibility_id,
        "label": label,
        "confidence": "medium",
        "supporting_evidence_refs": [evidence_ref],
        "contradicting_evidence_refs": [],
        "missing_information": ["direct confirmation"],
        "rationale": f"The bounded evidence leaves {label} plausible.",
    }


class ScriptedAnalysisClient:
    """Exercise every real contract/orchestration boundary without a paid API."""

    def __init__(self, mode: str = "complete") -> None:
        self.mode = mode
        self.calls = []
        self._lock = Lock()

    def analyze(self, request):
        with self._lock:
            self.calls.append(request)
        request_payload = json.loads(request.payload_json)
        evidence_ref = request_payload["output_contract"]["allowed_evidence_refs"][0]
        if request.stage.value == "recall":
            if self.mode == "recall_unavailable":
                return self._response(request, None, StageStatus.UNAVAILABLE)
            possibilities = [
                _possibility("possibility_routine", "routine movement", evidence_ref),
                _possibility("possibility_sensor", "sensor issue", evidence_ref),
            ]
            return self._response(
                request,
                {
                    "routing_id": f"routing_{request.anomaly_id}",
                    "anomaly_id": request.anomaly_id,
                    "packet_revision": request.packet_revision,
                    "possibilities": possibilities,
                    "assignments": [
                        {"specialist": "routine_context", "possibility_ids": ["possibility_routine"], "reason": "Review routine context."},
                        {"specialist": "signal_integrity", "possibility_ids": ["possibility_sensor"], "reason": "Review signal quality."},
                    ],
                    "missing_information": ["direct confirmation"],
                    "evidence_refs": [evidence_ref],
                },
            )
        if request.stage.value == "specialist":
            specialist = request.skill_names[0]
            if self.mode == "one_specialist_unavailable" and specialist == "signal_integrity":
                return self._response(request, None, StageStatus.UNAVAILABLE)
            routed = request_payload["routing_possibilities"][0]
            return self._response(
                request,
                {
                    "assessment_id": f"assessment_{specialist}_{request.anomaly_id}",
                    "specialist": specialist,
                    "anomaly_id": request.anomaly_id,
                    "packet_revision": request.packet_revision,
                    "assessed_possibility_ids": [routed["possibility_id"]],
                    "possibilities": [_possibility(routed["possibility_id"], routed["label"], evidence_ref)],
                    "severity": "watch",
                    "recommended_disposition": "observe",
                    "missing_information": ["direct confirmation"],
                    "contradictions": [],
                    "evidence_refs": [evidence_ref],
                },
            )
        if request.stage.value in {"final", "repair"}:
            if self.mode == "final_unavailable":
                return self._response(request, None, StageStatus.UNAVAILABLE)
            contract = request_payload["output_contract"]
            routed = request_payload["routing_plan"]["possibilities"]
            invalid = self.mode == "invalid_twice" or (
                self.mode == "repair_once" and request.stage.value == "final"
            )
            considered = ["possibility_skipped"] if invalid else contract["required_considered_possibility_ids"]
            return self._response(
                request,
                {
                    "analysis_id": contract["required_analysis_id"],
                    "anomaly_id": request.anomaly_id,
                    "packet_revision": request.packet_revision,
                    "possibilities": routed,
                    "severity": "watch",
                    "recommended_disposition": "observe",
                    "attribution_scope": "resident",
                    "caregiver_summary": contract["required_caregiver_summary"],
                    "next_step": contract["required_next_step_by_disposition"]["observe"],
                    "missing_information": ["direct confirmation"],
                    "specialist_disagreements": [],
                    "evidence_refs": [evidence_ref],
                    "considered_possibility_ids": considered,
                    "coverage_complete": True,
                },
            )
        raise AssertionError(f"unexpected stage: {request.stage}")

    @staticmethod
    def _response(request, payload, status=StageStatus.COMPLETE):
        return StageResponse(
            stage=request.stage,
            status=status,
            request_fingerprint=request.request_fingerprint,
            payload_json=None if payload is None else json.dumps(payload, sort_keys=True, separators=(",", ":")),
            model_id="scripted-structured-provider",
            model_version="scripted-v1",
            latency_ms=2,
            error="provider unavailable" if status is StageStatus.UNAVAILABLE else None,
        )


__all__ = ["ScriptedAnalysisClient"]
