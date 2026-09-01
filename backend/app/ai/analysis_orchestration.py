"""Checkpointed three-stage monitoring analysis orchestration."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from hashlib import sha256
from threading import Lock

from backend.app.ai.analysis_context import (
    build_final_request,
    build_recall_request,
    build_specialist_request,
)
from backend.app.ai.analysis_contracts import (
    AnalysisRun,
    AnalysisState,
    ConfidenceBand,
    Possibility,
    RoutingPlan,
    SpecialistAssessment,
    SpecialistAssignment,
    StageStatus,
    StructuredAnalysisClient,
)
from backend.app.ai.analysis_skills import fallback_specialists
from backend.app.ai.analysis_validation import (
    AnalysisValidationError,
    validate_final_analysis,
    validate_routing_plan,
    validate_specialist_assessment,
)
from backend.app.domain.feedback import ResidentMemory
from backend.app.intelligence.evidence import EvidencePacket


def _run_id(packet: EvidencePacket) -> str:
    digest = sha256(
        f"{packet.anomaly_id}:{packet.packet_revision}:multi_agent_v1".encode("utf-8")
    ).hexdigest()[:20]
    return f"analysis_{digest}"


def _measured_families(packet: EvidencePacket) -> tuple[str, ...]:
    families: list[str] = []
    for feature in packet.changed_features:
        name = feature.feature_name.casefold()
        if any(marker in name for marker in ("respirat", "breath", "heart")):
            family = "respiration"
        elif any(marker in name for marker in ("inactive", "still", "sleep")):
            family = "inactivity"
        elif any(marker in name for marker in ("presence", "occup", "away", "room")):
            family = "presence"
        elif any(marker in name for marker in ("repeat", "recurr", "frequency")):
            family = "repetition"
        elif any(marker in name for marker in ("move", "motion", "position", "height", "velocity")):
            family = "movement"
        else:
            family = "unknown"
        if family not in families:
            families.append(family)
    return tuple(families or ("unknown",))


def _fallback_plan(packet: EvidencePacket) -> RoutingPlan:
    possibility = Possibility(
        possibility_id="possibility_unclassified_change",
        label="unclassified measured change",
        confidence=ConfidenceBand.LOW,
        supporting_evidence_refs=packet.evidence_refs,
        contradicting_evidence_refs=(),
        missing_information=tuple(dict.fromkeys((*packet.unknowns, *packet.limitations))),
        rationale="The recall model was unavailable; measured signal families require specialist review.",
    )
    specialists = fallback_specialists(_measured_families(packet))
    return RoutingPlan(
        routing_id=f"routing_fallback_{packet.anomaly_id}_{packet.packet_revision}",
        anomaly_id=packet.anomaly_id,
        packet_revision=packet.packet_revision,
        possibilities=(possibility,),
        assignments=tuple(
            SpecialistAssignment(
                specialist=name,
                possibility_ids=(possibility.possibility_id,),
                reason="Selected from measured anomaly signal family; no semantic conclusion assigned.",
            )
            for name in specialists
        ),
        missing_information=possibility.missing_information,
        evidence_refs=packet.evidence_refs,
        model_id="deterministic_routing_only",
        model_version="fallback_routing_v1",
        skill_version="fallback_routing_v1",
    )


@dataclass
class MultiAgentAnalysisOrchestrator:
    recall_client: StructuredAnalysisClient
    precision_client: StructuredAnalysisClient
    final_client: StructuredAnalysisClient
    max_specialist_workers: int = 4
    _checkpoints: dict[tuple[str, int], AnalysisRun] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _checkpoint_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_specialist_workers, bool)
            or not isinstance(self.max_specialist_workers, int)
            or not 1 <= self.max_specialist_workers <= 8
        ):
            raise ValueError("max_specialist_workers must be between 1 and 8")

    def analyze(
        self,
        packet: EvidencePacket,
        resident_memory: ResidentMemory,
        relevant_context_entry_ids: tuple[str, ...] = (),
    ) -> AnalysisRun:
        if not isinstance(packet, EvidencePacket):
            raise ValueError("packet must be an EvidencePacket")
        if not isinstance(resident_memory, ResidentMemory):
            raise ValueError("resident_memory must be a ResidentMemory")
        key = (packet.anomaly_id, packet.packet_revision)
        with self._checkpoint_lock:
            cached = self._checkpoints.get(key)
        if cached is not None and cached.state in (
            AnalysisState.ANALYZED,
            AnalysisState.NEEDS_STAFF_REVIEW,
            AnalysisState.ANALYSIS_REJECTED,
        ):
            return cached

        errors: list[str] = []
        plan = self._recall(
            packet,
            resident_memory,
            relevant_context_entry_ids,
            errors,
        )
        assessments, unavailable = self._specialists(
            packet,
            resident_memory,
            relevant_context_entry_ids,
            plan,
            errors,
        )
        result = self._finalize(
            packet,
            resident_memory,
            relevant_context_entry_ids,
            plan,
            assessments,
            unavailable,
            errors,
        )
        with self._checkpoint_lock:
            current = self._checkpoints.get(key)
            if current is not None and current.state in (
                AnalysisState.ANALYZED,
                AnalysisState.NEEDS_STAFF_REVIEW,
                AnalysisState.ANALYSIS_REJECTED,
            ):
                return current
            self._checkpoints[key] = result
        return result

    def _recall(
        self,
        packet: EvidencePacket,
        resident_memory: ResidentMemory,
        context_ids: tuple[str, ...],
        errors: list[str],
    ) -> RoutingPlan:
        request = build_recall_request(
            packet,
            resident_memory,
            relevant_context_entry_ids=context_ids,
        )
        try:
            response = self.recall_client.analyze(request)
            if response.status is not StageStatus.COMPLETE:
                errors.append("recall_unavailable")
                return _fallback_plan(packet)
            return validate_routing_plan(packet, request, response)
        except AnalysisValidationError as exc:
            errors.extend(f"recall:{reason}" for reason in exc.reasons)
            return _fallback_plan(packet)
        except Exception as exc:
            errors.append(f"recall_unavailable:{type(exc).__name__}")
            return _fallback_plan(packet)

    def _specialists(
        self,
        packet: EvidencePacket,
        resident_memory: ResidentMemory,
        context_ids: tuple[str, ...],
        plan: RoutingPlan,
        errors: list[str],
    ) -> tuple[tuple[SpecialistAssessment, ...], tuple[str, ...]]:
        results: dict[str, SpecialistAssessment] = {}
        unavailable: list[str] = []

        def invoke(assignment: SpecialistAssignment) -> SpecialistAssessment:
            request = build_specialist_request(
                packet,
                resident_memory,
                plan,
                assignment,
                relevant_context_entry_ids=context_ids,
            )
            response = self.precision_client.analyze(request)
            return validate_specialist_assessment(
                packet,
                assignment,
                request,
                response,
            )

        workers = min(self.max_specialist_workers, len(plan.assignments))
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {
                executor.submit(invoke, assignment): assignment
                for assignment in plan.assignments
            }
            for future in as_completed(futures):
                assignment = futures[future]
                try:
                    results[assignment.specialist] = future.result()
                except AnalysisValidationError as exc:
                    unavailable.append(assignment.specialist)
                    errors.extend(
                        f"specialist:{assignment.specialist}:{reason}"
                        for reason in exc.reasons
                    )
                except Exception as exc:
                    unavailable.append(assignment.specialist)
                    errors.append(
                        f"specialist:{assignment.specialist}:unavailable:{type(exc).__name__}"
                    )
        ordered = tuple(
            results[item.specialist]
            for item in plan.assignments
            if item.specialist in results
        )
        return ordered, tuple(unavailable)

    def _finalize(
        self,
        packet: EvidencePacket,
        resident_memory: ResidentMemory,
        context_ids: tuple[str, ...],
        plan: RoutingPlan,
        assessments: tuple[SpecialistAssessment, ...],
        unavailable: tuple[str, ...],
        errors: list[str],
    ) -> AnalysisRun:
        pending_id = _run_id(packet)
        request = build_final_request(
            packet,
            resident_memory,
            plan,
            assessments,
            unavailable_specialists=unavailable,
            relevant_context_entry_ids=context_ids,
        )
        try:
            response = self.final_client.analyze(request)
        except Exception as exc:
            errors.append(f"final_unavailable:{type(exc).__name__}")
            return self._incomplete(
                pending_id,
                packet,
                plan,
                assessments,
                unavailable,
                errors,
                AnalysisState.ANALYSIS_PENDING,
                repair_count=0,
            )
        if response.status is not StageStatus.COMPLETE:
            errors.append("final_unavailable")
            return self._incomplete(
                pending_id,
                packet,
                plan,
                assessments,
                unavailable,
                errors,
                AnalysisState.ANALYSIS_PENDING,
                repair_count=0,
            )
        try:
            final = validate_final_analysis(packet, plan, request, response)
            return AnalysisRun(
                analysis_id=final.analysis_id,
                anomaly_id=packet.anomaly_id,
                packet_revision=packet.packet_revision,
                state=AnalysisState.ANALYZED,
                routing_plan=plan,
                specialist_assessments=assessments,
                unavailable_specialists=unavailable,
                final_analysis=final,
                errors=tuple(dict.fromkeys(errors)),
                repair_count=0,
            )
        except AnalysisValidationError as exc:
            errors.extend(f"final:{reason}" for reason in exc.reasons)
            repair = build_final_request(
                packet,
                resident_memory,
                plan,
                assessments,
                unavailable_specialists=unavailable,
                relevant_context_entry_ids=context_ids,
                repair_errors=exc.reasons,
                prior_result_json=response.payload_json,
            )
            try:
                repaired_response = self.final_client.analyze(repair)
                final = validate_final_analysis(packet, plan, repair, repaired_response)
            except AnalysisValidationError as repair_error:
                errors.extend(f"repair:{reason}" for reason in repair_error.reasons)
                return self._incomplete(
                    pending_id,
                    packet,
                    plan,
                    assessments,
                    unavailable,
                    errors,
                    AnalysisState.NEEDS_STAFF_REVIEW,
                    repair_count=1,
                )
            except Exception as repair_error:
                errors.append(f"repair_unavailable:{type(repair_error).__name__}")
                return self._incomplete(
                    pending_id,
                    packet,
                    plan,
                    assessments,
                    unavailable,
                    errors,
                    AnalysisState.ANALYSIS_PENDING,
                    repair_count=1,
                )
            return AnalysisRun(
                analysis_id=final.analysis_id,
                anomaly_id=packet.anomaly_id,
                packet_revision=packet.packet_revision,
                state=AnalysisState.ANALYZED,
                routing_plan=plan,
                specialist_assessments=assessments,
                unavailable_specialists=unavailable,
                final_analysis=final,
                errors=tuple(dict.fromkeys(errors)),
                repair_count=1,
            )

    @staticmethod
    def _incomplete(
        analysis_id: str,
        packet: EvidencePacket,
        plan: RoutingPlan,
        assessments: tuple[SpecialistAssessment, ...],
        unavailable: tuple[str, ...],
        errors: list[str],
        state: AnalysisState,
        *,
        repair_count: int,
    ) -> AnalysisRun:
        return AnalysisRun(
            analysis_id=analysis_id,
            anomaly_id=packet.anomaly_id,
            packet_revision=packet.packet_revision,
            state=state,
            routing_plan=plan,
            specialist_assessments=assessments,
            unavailable_specialists=unavailable,
            final_analysis=None,
            errors=tuple(dict.fromkeys(errors)),
            repair_count=repair_count,
        )


__all__ = ["MultiAgentAnalysisOrchestrator"]
