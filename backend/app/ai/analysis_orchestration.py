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
    StageResponse,
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


def _input_fingerprint(
    tenant_id: str,
    packet: EvidencePacket,
    resident_memory: ResidentMemory,
    context_ids: tuple[str, ...],
) -> str:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ValueError("tenant_id must be nonblank text")
    return sha256(
        repr(
            (
                tenant_id.strip(),
                packet,
                resident_memory,
                context_ids,
                "multi_agent_input_v1",
            )
        ).encode("utf-8")
    ).hexdigest()


def _run_id(packet: EvidencePacket, input_fingerprint: str, attempt_number: int) -> str:
    digest = sha256(
        f"{input_fingerprint}:{attempt_number}:multi_agent_v1".encode("utf-8")
    ).hexdigest()[:20]
    return f"analysis_{digest}"


def _measured_families(packet: EvidencePacket) -> tuple[str, ...]:
    if packet.strength_scale == "fall_like_state_machine":
        return ("fall_like",)
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
    _checkpoints: dict[str, AnalysisRun] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _checkpoint_lock: Lock = field(default_factory=Lock, init=False, repr=False)
    _run_locks: dict[str, Lock] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

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
        *,
        tenant_id: str,
    ) -> AnalysisRun:
        key = _input_fingerprint(
            tenant_id,
            packet,
            resident_memory,
            relevant_context_entry_ids,
        )
        with self._checkpoint_lock:
            run_lock = self._run_locks.setdefault(key, Lock())
        with run_lock:
            try:
                return self._analyze_locked(
                    packet,
                    resident_memory,
                    relevant_context_entry_ids,
                    key,
                )
            except Exception as exc:
                # Expected provider and validation failures are handled by the
                # individual stages. This last boundary makes an unexpected
                # orchestration failure durable and visible instead of losing
                # the anomaly after a process restart.
                with self._checkpoint_lock:
                    cached = self._checkpoints.get(key)
                    attempt_number = (
                        1 if cached is None else cached.attempt_number + 1
                    )
                    failed = AnalysisRun(
                        analysis_id=_run_id(packet, key, attempt_number),
                        anomaly_id=packet.anomaly_id,
                        packet_revision=packet.packet_revision,
                        state=AnalysisState.ANALYSIS_PENDING,
                        routing_plan=None if cached is None else cached.routing_plan,
                        specialist_assessments=(
                            () if cached is None else cached.specialist_assessments
                        ),
                        unavailable_specialists=(
                            () if cached is None else cached.unavailable_specialists
                        ),
                        final_analysis=None,
                        errors=tuple(
                            dict.fromkeys(
                                (
                                    *(() if cached is None else cached.errors),
                                    f"analysis_unavailable:{type(exc).__name__}",
                                )
                            )
                        ),
                        repair_count=0 if cached is None else cached.repair_count,
                        input_fingerprint=key,
                        attempt_number=attempt_number,
                        stage_responses=(
                            () if cached is None else cached.stage_responses
                        ),
                        resident_memory_version=resident_memory.version,
                        relevant_context_entry_ids=relevant_context_entry_ids,
                    )
                    self._checkpoints[key] = failed
                return failed

    def restore_checkpoint(self, run: AnalysisRun) -> None:
        """Restore one validated persisted checkpoint after a process restart."""

        if not isinstance(run, AnalysisRun):
            raise ValueError("run must be an AnalysisRun")
        key = run.input_fingerprint
        with self._checkpoint_lock:
            existing = self._checkpoints.get(key)
            if existing is not None and existing != run:
                same_attempt = (
                    existing.analysis_id == run.analysis_id
                    and existing.state == run.state
                    and existing.attempt_number == run.attempt_number
                    and existing.input_fingerprint == run.input_fingerprint
                )
                if not same_attempt:
                    raise ValueError("checkpoint identity already has different state")
                return
            self._checkpoints[key] = run

    def _analyze_locked(
        self,
        packet: EvidencePacket,
        resident_memory: ResidentMemory,
        relevant_context_entry_ids: tuple[str, ...],
        input_fingerprint: str,
    ) -> AnalysisRun:
        if not isinstance(packet, EvidencePacket):
            raise ValueError("packet must be an EvidencePacket")
        if not isinstance(resident_memory, ResidentMemory):
            raise ValueError("resident_memory must be a ResidentMemory")
        key = input_fingerprint
        with self._checkpoint_lock:
            cached = self._checkpoints.get(key)
        if cached is not None and cached.input_fingerprint != input_fingerprint:
            raise ValueError("analysis checkpoint context does not match request")
        if cached is not None and cached.state in (
            AnalysisState.ANALYZED,
            AnalysisState.NEEDS_STAFF_REVIEW,
            AnalysisState.ANALYSIS_REJECTED,
        ):
            return cached

        errors: list[str] = [] if cached is None else list(cached.errors)
        stage_responses: list[StageResponse] = (
            [] if cached is None else list(cached.stage_responses)
        )
        if cached is not None and cached.routing_plan is not None:
            plan = cached.routing_plan
            assessments = cached.specialist_assessments
            unavailable = cached.unavailable_specialists
        else:
            plan = self._recall(
                packet,
                resident_memory,
                relevant_context_entry_ids,
                errors,
                stage_responses,
            )
            assessments, unavailable = self._specialists(
                packet,
                resident_memory,
                relevant_context_entry_ids,
                plan,
                errors,
                stage_responses,
            )
        attempt_number = 1 if cached is None else cached.attempt_number + 1
        result = self._finalize(
            packet,
            resident_memory,
            relevant_context_entry_ids,
            plan,
            assessments,
            unavailable,
            errors,
            stage_responses,
            input_fingerprint,
            attempt_number,
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
        stage_responses: list[StageResponse],
    ) -> RoutingPlan:
        request = build_recall_request(
            packet,
            resident_memory,
            relevant_context_entry_ids=context_ids,
        )
        try:
            response = self.recall_client.analyze(request)
            stage_responses.append(response)
            if response.status is not StageStatus.COMPLETE:
                errors.append("recall_unavailable")
                return _fallback_plan(packet)
            return validate_routing_plan(packet, request, response)
        except AnalysisValidationError as exc:
            errors.extend(f"recall:{reason}" for reason in exc.reasons)
            return _fallback_plan(packet)
        except Exception as exc:
            stage_responses.append(self._unavailable(request, self.recall_client, exc))
            errors.append(f"recall_unavailable:{type(exc).__name__}")
            return _fallback_plan(packet)

    def _specialists(
        self,
        packet: EvidencePacket,
        resident_memory: ResidentMemory,
        context_ids: tuple[str, ...],
        plan: RoutingPlan,
        errors: list[str],
        stage_responses: list[StageResponse],
    ) -> tuple[tuple[SpecialistAssessment, ...], tuple[str, ...]]:
        results: dict[str, SpecialistAssessment] = {}
        unavailable: list[str] = []

        def invoke(
            assignment: SpecialistAssignment,
        ) -> tuple[SpecialistAssessment | None, StageResponse, tuple[str, ...]]:
            request = build_specialist_request(
                packet,
                resident_memory,
                plan,
                assignment,
                relevant_context_entry_ids=context_ids,
            )
            try:
                response = self.precision_client.analyze(request)
            except Exception as exc:
                return (
                    None,
                    self._unavailable(request, self.precision_client, exc),
                    (f"unavailable:{type(exc).__name__}",),
                )
            try:
                assessment = validate_specialist_assessment(
                    packet,
                    assignment,
                    request,
                    response,
                )
            except AnalysisValidationError as exc:
                return None, response, exc.reasons
            return assessment, response, ()

        workers = min(self.max_specialist_workers, len(plan.assignments))
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {
                executor.submit(invoke, assignment): assignment
                for assignment in plan.assignments
            }
            for future in as_completed(futures):
                assignment = futures[future]
                try:
                    assessment, response, reasons = future.result()
                    stage_responses.append(response)
                    if assessment is None:
                        unavailable.append(assignment.specialist)
                        errors.extend(
                            f"specialist:{assignment.specialist}:{reason}"
                            for reason in reasons
                        )
                    else:
                        results[assignment.specialist] = assessment
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
        stage_responses: list[StageResponse],
        input_fingerprint: str,
        attempt_number: int,
    ) -> AnalysisRun:
        pending_id = _run_id(packet, input_fingerprint, attempt_number)
        request = build_final_request(
            packet,
            resident_memory,
            plan,
            assessments,
            unavailable_specialists=unavailable,
            relevant_context_entry_ids=context_ids,
            required_analysis_id=pending_id,
        )
        try:
            response = self.final_client.analyze(request)
            stage_responses.append(response)
        except Exception as exc:
            stage_responses.append(self._unavailable(request, self.final_client, exc))
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
                stage_responses=stage_responses,
                resident_memory=resident_memory,
                context_ids=context_ids,
                input_fingerprint=input_fingerprint,
                attempt_number=attempt_number,
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
                stage_responses=stage_responses,
                resident_memory=resident_memory,
                context_ids=context_ids,
                input_fingerprint=input_fingerprint,
                attempt_number=attempt_number,
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
                input_fingerprint=input_fingerprint,
                attempt_number=attempt_number,
                stage_responses=tuple(stage_responses),
                resident_memory_version=resident_memory.version,
                relevant_context_entry_ids=context_ids,
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
                required_analysis_id=pending_id,
            )
            try:
                repaired_response = self.final_client.analyze(repair)
                stage_responses.append(repaired_response)
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
                    stage_responses=stage_responses,
                    resident_memory=resident_memory,
                    context_ids=context_ids,
                    input_fingerprint=input_fingerprint,
                    attempt_number=attempt_number,
                )
            except Exception as repair_error:
                stage_responses.append(
                    self._unavailable(repair, self.final_client, repair_error)
                )
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
                    stage_responses=stage_responses,
                    resident_memory=resident_memory,
                    context_ids=context_ids,
                    input_fingerprint=input_fingerprint,
                    attempt_number=attempt_number,
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
                input_fingerprint=input_fingerprint,
                attempt_number=attempt_number,
                stage_responses=tuple(stage_responses),
                resident_memory_version=resident_memory.version,
                relevant_context_entry_ids=context_ids,
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
        stage_responses: list[StageResponse],
        resident_memory: ResidentMemory,
        context_ids: tuple[str, ...],
        input_fingerprint: str,
        attempt_number: int,
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
            input_fingerprint=input_fingerprint,
            attempt_number=attempt_number,
            stage_responses=tuple(stage_responses),
            resident_memory_version=resident_memory.version,
            relevant_context_entry_ids=context_ids,
        )

    @staticmethod
    def _unavailable(
        request,
        client: StructuredAnalysisClient,
        error: Exception,
    ) -> StageResponse:
        return StageResponse(
            stage=request.stage,
            status=StageStatus.UNAVAILABLE,
            request_fingerprint=request.request_fingerprint,
            payload_json=None,
            model_id=type(client).__name__,
            model_version="unavailable",
            latency_ms=0.0,
            error=f"{type(error).__name__}",
        )


__all__ = ["MultiAgentAnalysisOrchestrator"]
