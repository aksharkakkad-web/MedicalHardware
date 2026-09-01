"""Provider-neutral contracts for staged monitoring analysis."""

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from numbers import Real
from typing import Protocol

from backend.app.ai.client import RecommendedDisposition


ANALYSIS_SCHEMA_VERSION = "1.0"


class AnalysisStage(StrEnum):
    RECALL = "recall"
    SPECIALIST = "specialist"
    FINAL = "final"
    REPAIR = "repair"


class AnalysisState(StrEnum):
    DETECTED = "detected"
    RECALL_IN_PROGRESS = "recall_in_progress"
    SPECIALISTS_IN_PROGRESS = "specialists_in_progress"
    FINAL_ANALYSIS_IN_PROGRESS = "final_analysis_in_progress"
    ANALYZED = "analyzed"
    ANALYSIS_PENDING = "analysis_pending"
    NEEDS_STAFF_REVIEW = "needs_staff_review"
    ANALYSIS_REJECTED = "analysis_rejected"


class StageStatus(StrEnum):
    COMPLETE = "complete"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class ConfidenceBand(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AttributionScope(StrEnum):
    RESIDENT = "resident"
    ROOM = "room"
    UNKNOWN = "unknown"


class Severity(StrEnum):
    OBSERVATION = "observation"
    WATCH = "watch"
    HIGH = "high"
    CRITICAL = "critical"


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonblank text")
    return value.strip()


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def _text_tuple(value: object, field: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ValueError(f"{field} must be a tuple")
    normalized = tuple(_text(item, field) for item in value)
    if not allow_empty and not normalized:
        raise ValueError(f"{field} must not be empty")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field} must not contain duplicates")
    return normalized


def _enum(value: object, enum_type: type[StrEnum], field: str) -> StrEnum:
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a valid {enum_type.__name__}") from None


@dataclass(frozen=True)
class Possibility:
    possibility_id: str
    label: str
    confidence: ConfidenceBand | str
    supporting_evidence_refs: tuple[str, ...]
    contradicting_evidence_refs: tuple[str, ...]
    missing_information: tuple[str, ...]
    rationale: str
    schema_version: str = ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "possibility_id", _text(self.possibility_id, "possibility_id"))
        object.__setattr__(self, "label", _text(self.label, "label"))
        object.__setattr__(self, "confidence", _enum(self.confidence, ConfidenceBand, "confidence"))
        supporting = _text_tuple(self.supporting_evidence_refs, "supporting_evidence_refs")
        contradicting = _text_tuple(self.contradicting_evidence_refs, "contradicting_evidence_refs")
        if set(supporting) & set(contradicting):
            raise ValueError("evidence reference cannot both support and contradict")
        object.__setattr__(self, "supporting_evidence_refs", supporting)
        object.__setattr__(self, "contradicting_evidence_refs", contradicting)
        object.__setattr__(self, "missing_information", _text_tuple(self.missing_information, "missing_information"))
        object.__setattr__(self, "rationale", _text(self.rationale, "rationale"))
        object.__setattr__(self, "schema_version", _text(self.schema_version, "schema_version"))

    @property
    def evidence_refs(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.supporting_evidence_refs, *self.contradicting_evidence_refs)))


@dataclass(frozen=True)
class SpecialistAssignment:
    specialist: str
    possibility_ids: tuple[str, ...]
    reason: str
    schema_version: str = ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "specialist", _text(self.specialist, "specialist"))
        object.__setattr__(self, "possibility_ids", _text_tuple(self.possibility_ids, "possibility_ids", allow_empty=False))
        object.__setattr__(self, "reason", _text(self.reason, "reason"))
        object.__setattr__(self, "schema_version", _text(self.schema_version, "schema_version"))

    def validate_against(self, possibilities: tuple[Possibility, ...]) -> None:
        known = {item.possibility_id for item in possibilities}
        if any(item not in known for item in self.possibility_ids):
            raise ValueError("assignment contains unknown possibility")


@dataclass(frozen=True)
class RoutingPlan:
    routing_id: str
    anomaly_id: str
    packet_revision: int
    possibilities: tuple[Possibility, ...]
    assignments: tuple[SpecialistAssignment, ...]
    missing_information: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    model_id: str
    model_version: str
    skill_version: str
    schema_version: str = ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "routing_id", _text(self.routing_id, "routing_id"))
        object.__setattr__(self, "anomaly_id", _text(self.anomaly_id, "anomaly_id"))
        object.__setattr__(self, "packet_revision", _positive_int(self.packet_revision, "packet_revision"))
        if not isinstance(self.possibilities, tuple) or not self.possibilities or any(not isinstance(item, Possibility) for item in self.possibilities):
            raise ValueError("possibilities must be a nonempty tuple of Possibility records")
        possibility_ids = [item.possibility_id for item in self.possibilities]
        if len(set(possibility_ids)) != len(possibility_ids):
            raise ValueError("possibility_id values must be unique")
        if not isinstance(self.assignments, tuple) or not self.assignments or any(not isinstance(item, SpecialistAssignment) for item in self.assignments):
            raise ValueError("assignments must be a nonempty tuple of SpecialistAssignment records")
        specialists = [item.specialist for item in self.assignments]
        if len(set(specialists)) != len(specialists):
            raise ValueError("specialist values must be unique")
        for assignment in self.assignments:
            assignment.validate_against(self.possibilities)
        object.__setattr__(self, "missing_information", _text_tuple(self.missing_information, "missing_information"))
        refs = _text_tuple(self.evidence_refs, "evidence_refs")
        possible_refs = {ref for item in self.possibilities for ref in item.evidence_refs}
        if not set(refs) <= possible_refs:
            raise ValueError("evidence_refs must be used by a routed possibility")
        object.__setattr__(self, "evidence_refs", refs)
        for field in ("model_id", "model_version", "skill_version", "schema_version"):
            object.__setattr__(self, field, _text(getattr(self, field), field))


_ACTION_SEVERITIES = {
    RecommendedDisposition.NO_ACTION: frozenset((Severity.OBSERVATION,)),
    RecommendedDisposition.OBSERVE: frozenset((Severity.OBSERVATION, Severity.WATCH)),
    RecommendedDisposition.AWARENESS: frozenset((Severity.WATCH, Severity.HIGH)),
    RecommendedDisposition.CAREGIVER_EVENT: frozenset((Severity.HIGH, Severity.CRITICAL)),
}


def _normalize_action_severity(instance: object) -> None:
    severity = _enum(getattr(instance, "severity"), Severity, "severity")
    disposition = _enum(getattr(instance, "recommended_disposition"), RecommendedDisposition, "recommended_disposition")
    object.__setattr__(instance, "severity", severity)
    object.__setattr__(instance, "recommended_disposition", disposition)
    if severity not in _ACTION_SEVERITIES[disposition]:
        raise ValueError("severity and recommended_disposition are inconsistent")


@dataclass(frozen=True)
class SpecialistAssessment:
    assessment_id: str
    specialist: str
    anomaly_id: str
    packet_revision: int
    assessed_possibility_ids: tuple[str, ...]
    possibilities: tuple[Possibility, ...]
    severity: Severity | str
    recommended_disposition: RecommendedDisposition | str
    missing_information: tuple[str, ...]
    contradictions: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    model_id: str
    model_version: str
    skill_version: str
    schema_version: str = ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field in ("assessment_id", "specialist", "anomaly_id"):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        object.__setattr__(self, "packet_revision", _positive_int(self.packet_revision, "packet_revision"))
        assessed = _text_tuple(self.assessed_possibility_ids, "assessed_possibility_ids", allow_empty=False)
        object.__setattr__(self, "assessed_possibility_ids", assessed)
        if not isinstance(self.possibilities, tuple) or not self.possibilities or any(not isinstance(item, Possibility) for item in self.possibilities):
            raise ValueError("possibilities must be a nonempty tuple of Possibility records")
        result_ids = [item.possibility_id for item in self.possibilities]
        if len(set(result_ids)) != len(result_ids) or not set(result_ids) <= set(assessed):
            raise ValueError("possibilities must uniquely match assessed_possibility_ids")
        _normalize_action_severity(self)
        object.__setattr__(self, "missing_information", _text_tuple(self.missing_information, "missing_information"))
        object.__setattr__(self, "contradictions", _text_tuple(self.contradictions, "contradictions"))
        refs = _text_tuple(self.evidence_refs, "evidence_refs")
        possible_refs = {ref for item in self.possibilities for ref in item.evidence_refs}
        if not set(refs) <= possible_refs:
            raise ValueError("evidence_refs must be used by a specialist possibility")
        object.__setattr__(self, "evidence_refs", refs)
        for field in ("model_id", "model_version", "skill_version", "schema_version"):
            object.__setattr__(self, field, _text(getattr(self, field), field))


@dataclass(frozen=True)
class FinalAnalysis:
    analysis_id: str
    anomaly_id: str
    packet_revision: int
    possibilities: tuple[Possibility, ...]
    severity: Severity | str
    recommended_disposition: RecommendedDisposition | str
    attribution_scope: AttributionScope | str
    caregiver_summary: str
    next_step: str
    missing_information: tuple[str, ...]
    specialist_disagreements: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    considered_possibility_ids: tuple[str, ...]
    coverage_complete: bool
    model_id: str
    model_version: str
    skill_versions: tuple[str, ...]
    schema_version: str = ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field in ("analysis_id", "anomaly_id"):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        object.__setattr__(self, "packet_revision", _positive_int(self.packet_revision, "packet_revision"))
        if not isinstance(self.possibilities, tuple) or not self.possibilities or any(not isinstance(item, Possibility) for item in self.possibilities):
            raise ValueError("possibilities must be a nonempty tuple of Possibility records")
        ids = [item.possibility_id for item in self.possibilities]
        if len(set(ids)) != len(ids):
            raise ValueError("possibility_id values must be unique")
        _normalize_action_severity(self)
        object.__setattr__(self, "attribution_scope", _enum(self.attribution_scope, AttributionScope, "attribution_scope"))
        object.__setattr__(self, "caregiver_summary", _text(self.caregiver_summary, "caregiver_summary"))
        object.__setattr__(self, "next_step", _text(self.next_step, "next_step"))
        object.__setattr__(self, "missing_information", _text_tuple(self.missing_information, "missing_information"))
        object.__setattr__(self, "specialist_disagreements", _text_tuple(self.specialist_disagreements, "specialist_disagreements"))
        refs = _text_tuple(self.evidence_refs, "evidence_refs")
        possible_refs = {ref for item in self.possibilities for ref in item.evidence_refs}
        if not set(refs) <= possible_refs:
            raise ValueError("evidence_refs must be used by a retained possibility")
        object.__setattr__(self, "evidence_refs", refs)
        object.__setattr__(self, "considered_possibility_ids", _text_tuple(self.considered_possibility_ids, "considered_possibility_ids", allow_empty=False))
        if not isinstance(self.coverage_complete, bool):
            raise ValueError("coverage_complete must be a boolean")
        for field in ("model_id", "model_version", "schema_version"):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        object.__setattr__(self, "skill_versions", _text_tuple(self.skill_versions, "skill_versions", allow_empty=False))


@dataclass(frozen=True)
class StageRequest:
    stage: AnalysisStage | str
    anomaly_id: str
    packet_revision: int
    skill_names: tuple[str, ...]
    prompt: str
    payload_json: str
    response_schema: dict[str, object]
    request_fingerprint: str
    model_tier: str
    schema_version: str = ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage", _enum(self.stage, AnalysisStage, "stage"))
        object.__setattr__(self, "anomaly_id", _text(self.anomaly_id, "anomaly_id"))
        object.__setattr__(self, "packet_revision", _positive_int(self.packet_revision, "packet_revision"))
        object.__setattr__(self, "skill_names", _text_tuple(self.skill_names, "skill_names", allow_empty=False))
        for field in ("prompt", "payload_json", "request_fingerprint", "model_tier", "schema_version"):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        if not isinstance(self.response_schema, dict) or not self.response_schema:
            raise ValueError("response_schema must be a nonempty object")


@dataclass(frozen=True)
class StageResponse:
    stage: AnalysisStage | str
    status: StageStatus | str
    request_fingerprint: str
    payload_json: str | None
    model_id: str
    model_version: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    error: str | None = None
    schema_version: str = ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage", _enum(self.stage, AnalysisStage, "stage"))
        object.__setattr__(self, "status", _enum(self.status, StageStatus, "status"))
        for field in ("request_fingerprint", "model_id", "model_version", "schema_version"):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        if isinstance(self.latency_ms, bool) or not isinstance(self.latency_ms, Real):
            raise ValueError("latency_ms must be a nonnegative real number")
        latency = float(self.latency_ms)
        if not isfinite(latency) or latency < 0:
            raise ValueError("latency_ms must be a nonnegative real number")
        object.__setattr__(self, "latency_ms", latency)
        for field in ("input_tokens", "output_tokens"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, _nonnegative_int(value, field))
        if self.status == StageStatus.COMPLETE:
            if self.payload_json is None:
                raise ValueError("complete response requires payload_json")
            object.__setattr__(self, "payload_json", _text(self.payload_json, "payload_json"))
        elif self.payload_json is not None:
            object.__setattr__(self, "payload_json", _text(self.payload_json, "payload_json"))
        if self.error is not None:
            object.__setattr__(self, "error", _text(self.error, "error"))

    def validate_for(self, request: StageRequest) -> None:
        if self.stage != request.stage:
            raise ValueError("response stage does not match request stage")
        if self.request_fingerprint != request.request_fingerprint:
            raise ValueError("response request_fingerprint does not match request")


@dataclass(frozen=True)
class AnalysisRun:
    analysis_id: str
    anomaly_id: str
    packet_revision: int
    state: AnalysisState | str
    routing_plan: RoutingPlan | None
    specialist_assessments: tuple[SpecialistAssessment, ...]
    unavailable_specialists: tuple[str, ...]
    final_analysis: FinalAnalysis | None
    errors: tuple[str, ...]
    repair_count: int
    input_fingerprint: str
    attempt_number: int
    stage_responses: tuple[StageResponse, ...] = ()
    resident_memory_version: int = 0
    relevant_context_entry_ids: tuple[str, ...] = ()
    schema_version: str = ANALYSIS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for field in ("analysis_id", "anomaly_id"):
            object.__setattr__(self, field, _text(getattr(self, field), field))
        object.__setattr__(self, "packet_revision", _positive_int(self.packet_revision, "packet_revision"))
        object.__setattr__(self, "state", _enum(self.state, AnalysisState, "state"))
        if self.routing_plan is not None and not isinstance(self.routing_plan, RoutingPlan):
            raise ValueError("routing_plan must be a RoutingPlan or None")
        if not isinstance(self.specialist_assessments, tuple) or any(not isinstance(item, SpecialistAssessment) for item in self.specialist_assessments):
            raise ValueError("specialist_assessments must contain SpecialistAssessment records")
        specialists = [item.specialist for item in self.specialist_assessments]
        if len(set(specialists)) != len(specialists):
            raise ValueError("specialist_assessments must have unique specialists")
        object.__setattr__(self, "unavailable_specialists", _text_tuple(self.unavailable_specialists, "unavailable_specialists"))
        object.__setattr__(self, "errors", _text_tuple(self.errors, "errors"))
        object.__setattr__(self, "repair_count", _nonnegative_int(self.repair_count, "repair_count"))
        object.__setattr__(self, "input_fingerprint", _text(self.input_fingerprint, "input_fingerprint"))
        object.__setattr__(self, "attempt_number", _positive_int(self.attempt_number, "attempt_number"))
        if not isinstance(self.stage_responses, tuple) or any(
            not isinstance(item, StageResponse) for item in self.stage_responses
        ):
            raise ValueError("stage_responses must contain StageResponse records")
        object.__setattr__(
            self,
            "resident_memory_version",
            _nonnegative_int(self.resident_memory_version, "resident_memory_version"),
        )
        object.__setattr__(
            self,
            "relevant_context_entry_ids",
            _text_tuple(self.relevant_context_entry_ids, "relevant_context_entry_ids"),
        )
        object.__setattr__(self, "schema_version", _text(self.schema_version, "schema_version"))
        if self.repair_count > 1:
            raise ValueError("repair_count cannot exceed one")
        if self.state == AnalysisState.ANALYZED and self.final_analysis is None:
            raise ValueError("analyzed state requires final_analysis")
        if self.final_analysis is not None:
            if self.state != AnalysisState.ANALYZED:
                raise ValueError("final_analysis requires analyzed state")
            if self.final_analysis.analysis_id != self.analysis_id or self.final_analysis.anomaly_id != self.anomaly_id or self.final_analysis.packet_revision != self.packet_revision:
                raise ValueError("final_analysis identity does not match analysis run")


class StructuredAnalysisClient(Protocol):
    def analyze(self, request: StageRequest) -> StageResponse:
        """Return one structured response for a bounded analysis stage."""


__all__ = [
    "ANALYSIS_SCHEMA_VERSION",
    "AnalysisRun",
    "AnalysisStage",
    "AnalysisState",
    "AttributionScope",
    "ConfidenceBand",
    "FinalAnalysis",
    "Possibility",
    "RoutingPlan",
    "Severity",
    "SpecialistAssessment",
    "SpecialistAssignment",
    "StageRequest",
    "StageResponse",
    "StageStatus",
    "StructuredAnalysisClient",
]
