"""Explicit reversible mappings for immutable monitoring-intelligence records."""

from dataclasses import dataclass, fields
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Any

from backend.app.ai.client import (
    InterpretationAlternative,
    InterpretationRequest,
    InterpretationResult,
)
from backend.app.ai.analysis_contracts import (
    AnalysisRun,
    FinalAnalysis,
    Possibility,
    RoutingPlan,
    SpecialistAssessment,
    SpecialistAssignment,
)
from backend.app.ai.context import (
    validate_interpretation_request_payload,
    validate_interpretation_request_shape,
)
from backend.app.ai.validation import validate_interpretation
from backend.app.db.models import (
    AnomalyRevisionRow,
    BaselineDimensionRow,
    BaselineSnapshotRow,
    DispositionDecisionRow,
    EventBridgeRecordRow,
    LLMInterpretationRow,
    MultiAgentAnalysisRow,
)
from backend.app.domain.events import (
    BridgeEvidenceKind,
    EventBridgeRecord,
    EventPriority,
)
from backend.app.domain._validation import (
    require_aware_datetime,
    require_nonblank_text,
)
from backend.app.intelligence.anomaly import (
    AnomalyEpisode,
    AnomalyState,
    AnomalyUpdate,
    FeatureDeviation,
)
from backend.app.intelligence.baseline import BaselineSnapshot, FeatureBaseline
from backend.app.intelligence.evidence import EvidencePacket, build_evidence_packet
from backend.app.intelligence.observations import FeaturePurpose, QualityClass
from backend.app.intelligence.policy import (
    DispositionDecision,
    PolicyDisposition,
)
from backend.app.services.errors import ConcurrentUpdateError


def canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _possibility_data(item: Possibility) -> dict[str, object]:
    return {
        "possibility_id": item.possibility_id,
        "label": item.label,
        "confidence": item.confidence.value,
        "supporting_evidence_refs": list(item.supporting_evidence_refs),
        "contradicting_evidence_refs": list(item.contradicting_evidence_refs),
        "missing_information": list(item.missing_information),
        "rationale": item.rationale,
        "schema_version": item.schema_version,
    }


def _possibility_from_data(data: dict[str, Any]) -> Possibility:
    return Possibility(
        possibility_id=data["possibility_id"],
        label=data["label"],
        confidence=data["confidence"],
        supporting_evidence_refs=tuple(data["supporting_evidence_refs"]),
        contradicting_evidence_refs=tuple(data["contradicting_evidence_refs"]),
        missing_information=tuple(data["missing_information"]),
        rationale=data["rationale"],
        schema_version=data["schema_version"],
    )


def _assignment_data(item: SpecialistAssignment) -> dict[str, object]:
    return {
        "specialist": item.specialist,
        "possibility_ids": list(item.possibility_ids),
        "reason": item.reason,
        "schema_version": item.schema_version,
    }


def _assignment_from_data(data: dict[str, Any]) -> SpecialistAssignment:
    return SpecialistAssignment(
        specialist=data["specialist"],
        possibility_ids=tuple(data["possibility_ids"]),
        reason=data["reason"],
        schema_version=data["schema_version"],
    )


def _routing_data(item: RoutingPlan) -> dict[str, object]:
    return {
        "routing_id": item.routing_id,
        "anomaly_id": item.anomaly_id,
        "packet_revision": item.packet_revision,
        "possibilities": [_possibility_data(value) for value in item.possibilities],
        "assignments": [_assignment_data(value) for value in item.assignments],
        "missing_information": list(item.missing_information),
        "evidence_refs": list(item.evidence_refs),
        "model_id": item.model_id,
        "model_version": item.model_version,
        "skill_version": item.skill_version,
        "schema_version": item.schema_version,
    }


def _routing_from_data(data: dict[str, Any]) -> RoutingPlan:
    return RoutingPlan(
        routing_id=data["routing_id"],
        anomaly_id=data["anomaly_id"],
        packet_revision=data["packet_revision"],
        possibilities=tuple(_possibility_from_data(value) for value in data["possibilities"]),
        assignments=tuple(_assignment_from_data(value) for value in data["assignments"]),
        missing_information=tuple(data["missing_information"]),
        evidence_refs=tuple(data["evidence_refs"]),
        model_id=data["model_id"],
        model_version=data["model_version"],
        skill_version=data["skill_version"],
        schema_version=data["schema_version"],
    )


def _assessment_data(item: SpecialistAssessment) -> dict[str, object]:
    return {
        "assessment_id": item.assessment_id,
        "specialist": item.specialist,
        "anomaly_id": item.anomaly_id,
        "packet_revision": item.packet_revision,
        "assessed_possibility_ids": list(item.assessed_possibility_ids),
        "possibilities": [_possibility_data(value) for value in item.possibilities],
        "severity": item.severity.value,
        "recommended_disposition": item.recommended_disposition.value,
        "missing_information": list(item.missing_information),
        "contradictions": list(item.contradictions),
        "evidence_refs": list(item.evidence_refs),
        "model_id": item.model_id,
        "model_version": item.model_version,
        "skill_version": item.skill_version,
        "schema_version": item.schema_version,
    }


def _assessment_from_data(data: dict[str, Any]) -> SpecialistAssessment:
    return SpecialistAssessment(
        assessment_id=data["assessment_id"],
        specialist=data["specialist"],
        anomaly_id=data["anomaly_id"],
        packet_revision=data["packet_revision"],
        assessed_possibility_ids=tuple(data["assessed_possibility_ids"]),
        possibilities=tuple(_possibility_from_data(value) for value in data["possibilities"]),
        severity=data["severity"],
        recommended_disposition=data["recommended_disposition"],
        missing_information=tuple(data["missing_information"]),
        contradictions=tuple(data["contradictions"]),
        evidence_refs=tuple(data["evidence_refs"]),
        model_id=data["model_id"],
        model_version=data["model_version"],
        skill_version=data["skill_version"],
        schema_version=data["schema_version"],
    )


def _final_data(item: FinalAnalysis) -> dict[str, object]:
    return {
        "analysis_id": item.analysis_id,
        "anomaly_id": item.anomaly_id,
        "packet_revision": item.packet_revision,
        "possibilities": [_possibility_data(value) for value in item.possibilities],
        "severity": item.severity.value,
        "recommended_disposition": item.recommended_disposition.value,
        "attribution_scope": item.attribution_scope.value,
        "caregiver_summary": item.caregiver_summary,
        "next_step": item.next_step,
        "missing_information": list(item.missing_information),
        "specialist_disagreements": list(item.specialist_disagreements),
        "evidence_refs": list(item.evidence_refs),
        "considered_possibility_ids": list(item.considered_possibility_ids),
        "coverage_complete": item.coverage_complete,
        "model_id": item.model_id,
        "model_version": item.model_version,
        "skill_versions": list(item.skill_versions),
        "schema_version": item.schema_version,
    }


def _final_from_data(data: dict[str, Any]) -> FinalAnalysis:
    return FinalAnalysis(
        analysis_id=data["analysis_id"],
        anomaly_id=data["anomaly_id"],
        packet_revision=data["packet_revision"],
        possibilities=tuple(_possibility_from_data(value) for value in data["possibilities"]),
        severity=data["severity"],
        recommended_disposition=data["recommended_disposition"],
        attribution_scope=data["attribution_scope"],
        caregiver_summary=data["caregiver_summary"],
        next_step=data["next_step"],
        missing_information=tuple(data["missing_information"]),
        specialist_disagreements=tuple(data["specialist_disagreements"]),
        evidence_refs=tuple(data["evidence_refs"]),
        considered_possibility_ids=tuple(data["considered_possibility_ids"]),
        coverage_complete=data["coverage_complete"],
        model_id=data["model_id"],
        model_version=data["model_version"],
        skill_versions=tuple(data["skill_versions"]),
        schema_version=data["schema_version"],
    )


def analysis_run_data(run: AnalysisRun) -> dict[str, object]:
    return {
        "analysis_id": run.analysis_id,
        "anomaly_id": run.anomaly_id,
        "packet_revision": run.packet_revision,
        "state": run.state.value,
        "routing_plan": None if run.routing_plan is None else _routing_data(run.routing_plan),
        "specialist_assessments": [_assessment_data(value) for value in run.specialist_assessments],
        "unavailable_specialists": list(run.unavailable_specialists),
        "final_analysis": None if run.final_analysis is None else _final_data(run.final_analysis),
        "errors": list(run.errors),
        "repair_count": run.repair_count,
        "schema_version": run.schema_version,
    }


def analysis_run_from_data(data: dict[str, Any]) -> AnalysisRun:
    return AnalysisRun(
        analysis_id=data["analysis_id"],
        anomaly_id=data["anomaly_id"],
        packet_revision=data["packet_revision"],
        state=data["state"],
        routing_plan=None if data["routing_plan"] is None else _routing_from_data(data["routing_plan"]),
        specialist_assessments=tuple(_assessment_from_data(value) for value in data["specialist_assessments"]),
        unavailable_specialists=tuple(data["unavailable_specialists"]),
        final_analysis=None if data["final_analysis"] is None else _final_from_data(data["final_analysis"]),
        errors=tuple(data["errors"]),
        repair_count=data["repair_count"],
        schema_version=data["schema_version"],
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _time(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _value(value: object) -> object:
    return value.value if isinstance(value, Enum) else value


def _require_shadow(field: str, actual: object, expected: object) -> None:
    if isinstance(actual, datetime) and isinstance(expected, datetime):
        actual = _utc(actual)
        expected = _utc(expected)
    if actual != expected:
        raise ConcurrentUpdateError(
            f"Stored {field} does not match canonical payload"
        )


def _parse_canonical_json(payload: str, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(payload)
    except (OverflowError, RecursionError, TypeError, ValueError) as exc:
        raise ConcurrentUpdateError(f"Stored {label} is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ConcurrentUpdateError(f"Stored {label} is not canonical JSON")
    try:
        canonical = canonical_json(parsed)
    except (OverflowError, RecursionError, TypeError, ValueError) as exc:
        raise ConcurrentUpdateError(
            f"Stored {label} is not canonical JSON"
        ) from exc
    if canonical != payload:
        raise ConcurrentUpdateError(f"Stored {label} is not canonical JSON")
    return parsed


def _payload_digest(payload: str) -> str:
    return sha256(payload.encode("ascii")).hexdigest()


def _feature_baseline_data(feature: FeatureBaseline) -> dict[str, object]:
    return {
        "context_key": feature.context_key,
        "eligible_sample_count": feature.eligible_sample_count,
        "feature_name": feature.feature_name,
        "iqr": feature.iqr,
        "lower_quantile": feature.lower_quantile,
        "mad": feature.mad,
        "median": feature.median,
        "purpose": feature.purpose.value,
        "resolution_floor": feature.resolution_floor,
        "schema_version": feature.schema_version,
        "unit": feature.unit,
        "upper_quantile": feature.upper_quantile,
    }


def _feature_baseline(data: dict[str, Any]) -> FeatureBaseline:
    return FeatureBaseline(
        feature_name=data["feature_name"],
        purpose=FeaturePurpose(data["purpose"]),
        median=data["median"],
        mad=data["mad"],
        iqr=data["iqr"],
        lower_quantile=data["lower_quantile"],
        upper_quantile=data["upper_quantile"],
        resolution_floor=data["resolution_floor"],
        unit=data["unit"],
        eligible_sample_count=data["eligible_sample_count"],
        context_key=data["context_key"],
        schema_version=data["schema_version"],
    )


def baseline_to_rows(
    tenant_id: str,
    baseline: BaselineSnapshot,
    recorded_at: datetime,
) -> tuple[BaselineSnapshotRow, tuple[BaselineDimensionRow, ...]]:
    dimensions = tuple(
        BaselineDimensionRow(
            tenant_id=tenant_id,
            baseline_id=baseline.baseline_id,
            feature_name=feature.feature_name,
            purpose=feature.purpose.value,
            context_key=feature.context_key,
            unit=feature.unit,
            payload_json=canonical_json(
                {
                    "baseline_id": baseline.baseline_id,
                    "feature": _feature_baseline_data(feature),
                    "tenant_id": tenant_id,
                }
            ),
        )
        for feature in sorted(
            baseline.features,
            key=lambda item: (item.feature_name, item.context_key),
        )
    )
    payload = {
        "adoption_candidate_id": baseline.adoption_candidate_id,
        "adoption_context_entry_id": baseline.adoption_context_entry_id,
        "baseline_id": baseline.baseline_id,
        "monitoring_setup_version": baseline.monitoring_setup_version,
        "policy_version": baseline.policy_version,
        "prior_baseline_id": baseline.prior_baseline_id,
        "resident_id": baseline.resident_id,
        "recorded_at": _time(recorded_at),
        "schema_version": baseline.schema_version,
        "tenant_id": tenant_id,
        "dimension_count": len(dimensions),
        "dimension_manifest": [
            {
                "context_key": row.context_key,
                "feature_name": row.feature_name,
                "payload_sha256": _payload_digest(row.payload_json),
            }
            for row in dimensions
        ],
    }
    snapshot = BaselineSnapshotRow(
        baseline_id=baseline.baseline_id,
        tenant_id=tenant_id,
        resident_id=baseline.resident_id,
        recorded_at=_utc(recorded_at),
        monitoring_setup_version=baseline.monitoring_setup_version,
        policy_version=baseline.policy_version,
        prior_baseline_id=baseline.prior_baseline_id,
        adoption_candidate_id=baseline.adoption_candidate_id,
        adoption_context_entry_id=baseline.adoption_context_entry_id,
        schema_version=baseline.schema_version,
        payload_json=canonical_json(payload),
    )
    return snapshot, dimensions


def baseline_from_rows(
    snapshot: BaselineSnapshotRow,
    dimensions: tuple[BaselineDimensionRow, ...],
) -> BaselineSnapshot:
    data = _parse_canonical_json(snapshot.payload_json, "baseline payload")
    for field, actual in (
        ("baseline_id", snapshot.baseline_id),
        ("resident_id", snapshot.resident_id),
        ("recorded_at", snapshot.recorded_at),
        ("monitoring_setup_version", snapshot.monitoring_setup_version),
        ("policy_version", snapshot.policy_version),
        ("prior_baseline_id", snapshot.prior_baseline_id),
        ("adoption_candidate_id", snapshot.adoption_candidate_id),
        ("adoption_context_entry_id", snapshot.adoption_context_entry_id),
        ("schema_version", snapshot.schema_version),
        ("tenant_id", snapshot.tenant_id),
    ):
        expected = (
            _parse_time(data[field]) if field == "recorded_at" else data[field]
        )
        _require_shadow(f"baseline.{field}", actual, expected)
    actual_manifest = [
        {
            "context_key": row.context_key,
            "feature_name": row.feature_name,
            "payload_sha256": _payload_digest(row.payload_json),
        }
        for row in dimensions
    ]
    if (
        data.get("dimension_count") != len(dimensions)
        or data.get("dimension_manifest") != actual_manifest
    ):
        raise ConcurrentUpdateError("Stored baseline dimension manifest mismatch")
    features = []
    try:
        dimension_payloads = tuple(
            _parse_canonical_json(row.payload_json, "baseline dimension payload")
            for row in dimensions
        )
        feature_records = tuple(
            _feature_baseline(item["feature"]) for item in dimension_payloads
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ConcurrentUpdateError(
            "Stored baseline dimension is not canonical domain data"
        ) from exc
    for row, dimension_data, feature in zip(
        dimensions,
        dimension_payloads,
        feature_records,
        strict=True,
    ):
        _require_shadow(
            "baseline_dimension.payload_tenant_id",
            row.tenant_id,
            dimension_data["tenant_id"],
        )
        _require_shadow(
            "baseline_dimension.payload_baseline_id",
            row.baseline_id,
            dimension_data["baseline_id"],
        )
        for field in ("feature_name", "purpose", "context_key", "unit"):
            expected = getattr(feature, field)
            if isinstance(expected, Enum):
                expected = expected.value
            _require_shadow(
                f"baseline_dimension.{field}",
                getattr(row, field),
                expected,
            )
        _require_shadow(
            "baseline_dimension.baseline_id",
            row.baseline_id,
            snapshot.baseline_id,
        )
        _require_shadow(
            "baseline_dimension.tenant_id",
            row.tenant_id,
            snapshot.tenant_id,
        )
        features.append(feature)
    baseline = BaselineSnapshot(
        baseline_id=data["baseline_id"],
        resident_id=data["resident_id"],
        monitoring_setup_version=data["monitoring_setup_version"],
        features=tuple(features),
        policy_version=data["policy_version"],
        prior_baseline_id=data["prior_baseline_id"],
        adoption_candidate_id=data["adoption_candidate_id"],
        adoption_context_entry_id=data["adoption_context_entry_id"],
        schema_version=data["schema_version"],
    )
    regenerated_snapshot, regenerated_dimensions = baseline_to_rows(
        snapshot.tenant_id,
        baseline,
        snapshot.recorded_at,
    )
    if regenerated_snapshot.payload_json != snapshot.payload_json or tuple(
        item.payload_json for item in regenerated_dimensions
    ) != tuple(item.payload_json for item in dimensions):
        raise ConcurrentUpdateError(
            "Stored baseline payload is not canonical domain data"
        )
    return baseline


def _deviation_data(item: FeatureDeviation) -> dict[str, object]:
    return {
        "baseline_context_key": item.baseline_context_key,
        "baseline_iqr": item.baseline_iqr,
        "baseline_lower_quantile": item.baseline_lower_quantile,
        "baseline_mad": item.baseline_mad,
        "baseline_median": item.baseline_median,
        "baseline_resolution_floor": item.baseline_resolution_floor,
        "baseline_upper_quantile": item.baseline_upper_quantile,
        "direction": item.direction,
        "feature_name": item.feature_name,
        "observation_id": item.observation_id,
        "persistence_frames": item.persistence_frames,
        "quality_class": item.quality_class.value,
        "quality_reasons": list(item.quality_reasons),
        "robust_z": item.robust_z,
        "schema_version": item.schema_version,
        "source": item.source,
        "trajectory": item.trajectory,
        "unit": item.unit,
        "value": item.value,
    }


def _deviation(data: dict[str, Any]) -> FeatureDeviation:
    return FeatureDeviation(
        feature_name=data["feature_name"],
        source=data["source"],
        observation_id=data["observation_id"],
        value=data["value"],
        unit=data["unit"],
        quality_class=QualityClass(data["quality_class"]),
        quality_reasons=tuple(data["quality_reasons"]),
        baseline_median=data["baseline_median"],
        baseline_mad=data["baseline_mad"],
        baseline_iqr=data["baseline_iqr"],
        baseline_lower_quantile=data["baseline_lower_quantile"],
        baseline_upper_quantile=data["baseline_upper_quantile"],
        baseline_resolution_floor=data["baseline_resolution_floor"],
        baseline_context_key=data["baseline_context_key"],
        robust_z=data["robust_z"],
        direction=data["direction"],
        trajectory=data["trajectory"],
        persistence_frames=data["persistence_frames"],
        schema_version=data["schema_version"],
    )


def _episode_data(episode: AnomalyEpisode) -> dict[str, object]:
    return {
        "activated_at": None if episode.activated_at is None else _time(episode.activated_at),
        "activation_count": episode.activation_count,
        "anomaly_id": episode.anomaly_id,
        "candidate_started_at": _time(episode.candidate_started_at),
        "closed_at": None if episode.closed_at is None else _time(episode.closed_at),
        "consecutive_missing_frames": episode.consecutive_missing_frames,
        "current_time": _time(episode.current_time),
        "initiating_features": list(episode.initiating_features),
        "last_frame_id": episode.last_frame_id,
        "packet_revision": episode.packet_revision,
        "policy_version": episode.policy_version,
        "recovering_started_at": (
            None if episode.recovering_started_at is None else _time(episode.recovering_started_at)
        ),
        "recovery_count": episode.recovery_count,
        "recurrence_of": episode.recurrence_of,
        "related_frame_count": episode.related_frame_count,
        "schema_version": episode.schema_version,
        "state": episode.state.value,
    }


def _episode(data: dict[str, Any]) -> AnomalyEpisode:
    return AnomalyEpisode(
        anomaly_id=data["anomaly_id"],
        state=AnomalyState(data["state"]),
        candidate_started_at=_parse_time(data["candidate_started_at"]),
        current_time=_parse_time(data["current_time"]),
        activation_count=data["activation_count"],
        recovery_count=data["recovery_count"],
        consecutive_missing_frames=data["consecutive_missing_frames"],
        related_frame_count=data["related_frame_count"],
        packet_revision=data["packet_revision"],
        initiating_features=tuple(data["initiating_features"]),
        policy_version=data["policy_version"],
        last_frame_id=data["last_frame_id"],
        activated_at=None if data["activated_at"] is None else _parse_time(data["activated_at"]),
        recovering_started_at=(
            None
            if data["recovering_started_at"] is None
            else _parse_time(data["recovering_started_at"])
        ),
        closed_at=None if data["closed_at"] is None else _parse_time(data["closed_at"]),
        recurrence_of=data["recurrence_of"],
        schema_version=data["schema_version"],
    )


def _update_data(update: AnomalyUpdate) -> dict[str, object]:
    return {
        "agreements": list(update.agreements),
        "baseline_id": update.baseline_id,
        "baseline_policy_version": update.baseline_policy_version,
        "config_version": update.config_version,
        "context_key": update.context_key,
        "contradictions": list(update.contradictions),
        "deviations": [_deviation_data(item) for item in update.deviations],
        "episode": None if update.episode is None else _episode_data(update.episode),
        "evidence_limited": update.evidence_limited,
        "feature_contract_version": update.feature_contract_version,
        "filter_version": update.filter_version,
        "frame_id": update.frame_id,
        "limitations": list(update.limitations),
        "missing_initiating_features": list(update.missing_initiating_features),
        "missing_sources": list(update.missing_sources),
        "monitoring_setup_version": update.monitoring_setup_version,
        "resident_id": update.resident_id,
        "room_id": update.room_id,
        "schema_version": update.schema_version,
        "unknowns": list(update.unknowns),
        "window_end": _time(update.window_end),
        "window_start": _time(update.window_start),
    }


def _update(data: dict[str, Any]) -> AnomalyUpdate:
    return AnomalyUpdate(
        episode=None if data["episode"] is None else _episode(data["episode"]),
        deviations=tuple(_deviation(item) for item in data["deviations"]),
        resident_id=data["resident_id"],
        room_id=data["room_id"],
        frame_id=data["frame_id"],
        window_start=_parse_time(data["window_start"]),
        window_end=_parse_time(data["window_end"]),
        agreements=tuple(data["agreements"]),
        contradictions=tuple(data["contradictions"]),
        missing_sources=tuple(data["missing_sources"]),
        missing_initiating_features=tuple(data["missing_initiating_features"]),
        feature_contract_version=data["feature_contract_version"],
        baseline_id=data["baseline_id"],
        baseline_policy_version=data["baseline_policy_version"],
        monitoring_setup_version=data["monitoring_setup_version"],
        context_key=data["context_key"],
        filter_version=data["filter_version"],
        config_version=data["config_version"],
        unknowns=tuple(data["unknowns"]),
        evidence_limited=data["evidence_limited"],
        limitations=tuple(data["limitations"]),
        schema_version=data["schema_version"],
    )


def _packet_data(packet: EvidencePacket) -> dict[str, object]:
    return {
        "activated_at": _time(packet.activated_at),
        "agreements": list(packet.agreements),
        "anomaly_id": packet.anomaly_id,
        "baseline_id": packet.baseline_id,
        "baseline_policy_version": packet.baseline_policy_version,
        "candidate_started_at": _time(packet.candidate_started_at),
        "changed_features": [_deviation_data(item) for item in packet.changed_features],
        "config_version": packet.config_version,
        "contradictions": list(packet.contradictions),
        "current_time": _time(packet.current_time),
        "evidence_limited": packet.evidence_limited,
        "evidence_refs": list(packet.evidence_refs),
        "feature_contract_version": packet.feature_contract_version,
        "filter_version": packet.filter_version,
        "frame_id": packet.frame_id,
        "lifecycle_state": packet.lifecycle_state.value,
        "limitations": list(packet.limitations),
        "missing_initiating_features": list(packet.missing_initiating_features),
        "missing_modalities": list(packet.missing_modalities),
        "monitoring_setup_version": packet.monitoring_setup_version,
        "overall_strength": packet.overall_strength,
        "packet_revision": packet.packet_revision,
        "progression": packet.progression,
        "resident_id": packet.resident_id,
        "room_id": packet.room_id,
        "schema_version": packet.schema_version,
        "semantic_label": packet.semantic_label,
        "strength_scale": packet.strength_scale,
        "unknowns": list(packet.unknowns),
    }


def _packet(data: dict[str, Any]) -> EvidencePacket:
    return EvidencePacket(
        anomaly_id=data["anomaly_id"],
        packet_revision=data["packet_revision"],
        lifecycle_state=AnomalyState(data["lifecycle_state"]),
        resident_id=data["resident_id"],
        room_id=data["room_id"],
        candidate_started_at=_parse_time(data["candidate_started_at"]),
        activated_at=_parse_time(data["activated_at"]),
        current_time=_parse_time(data["current_time"]),
        overall_strength=data["overall_strength"],
        strength_scale=data["strength_scale"],
        progression=data["progression"],
        changed_features=tuple(_deviation(item) for item in data["changed_features"]),
        agreements=tuple(data["agreements"]),
        contradictions=tuple(data["contradictions"]),
        missing_modalities=tuple(data["missing_modalities"]),
        missing_initiating_features=tuple(data["missing_initiating_features"]),
        evidence_limited=data["evidence_limited"],
        limitations=tuple(data["limitations"]),
        baseline_id=data["baseline_id"],
        baseline_policy_version=data["baseline_policy_version"],
        monitoring_setup_version=data["monitoring_setup_version"],
        filter_version=data["filter_version"],
        config_version=data["config_version"],
        feature_contract_version=data["feature_contract_version"],
        frame_id=data["frame_id"],
        unknowns=tuple(data["unknowns"]),
        evidence_refs=tuple(data["evidence_refs"]),
        semantic_label=data["semantic_label"],
        schema_version=data["schema_version"],
    )


@dataclass(frozen=True)
class StoredAnomalyRevision:
    update: AnomalyUpdate
    packet: EvidencePacket


def anomaly_to_row(
    tenant_id: str,
    update: AnomalyUpdate,
    packet: EvidencePacket,
) -> AnomalyRevisionRow:
    if update.episode is None:
        raise ValueError("anomaly update must contain an episode")
    expected_packet = build_evidence_packet(update)
    if packet != expected_packet:
        for field in fields(EvidencePacket):
            if getattr(packet, field.name) != getattr(expected_packet, field.name):
                raise ValueError(
                    f"anomaly update/packet provenance mismatch: {field.name}"
                )
        raise ValueError("anomaly update/packet provenance mismatch")
    return AnomalyRevisionRow(
        tenant_id=tenant_id,
        anomaly_id=packet.anomaly_id,
        packet_revision=packet.packet_revision,
        resident_id=packet.resident_id,
        room_id=packet.room_id,
        baseline_id=packet.baseline_id,
        lifecycle_state=packet.lifecycle_state.value,
        recorded_at=_utc(packet.current_time),
        update_json=canonical_json(
            {"tenant_id": tenant_id, "update": _update_data(update)}
        ),
        packet_json=canonical_json(
            {"packet": _packet_data(packet), "tenant_id": tenant_id}
        ),
    )


def anomaly_from_row(row: AnomalyRevisionRow) -> StoredAnomalyRevision:
    update_payload = _parse_canonical_json(row.update_json, "anomaly update")
    packet_payload = _parse_canonical_json(row.packet_json, "anomaly packet")
    _require_shadow(
        "anomaly.update_tenant_id",
        row.tenant_id,
        update_payload["tenant_id"],
    )
    _require_shadow(
        "anomaly.packet_tenant_id",
        row.tenant_id,
        packet_payload["tenant_id"],
    )
    stored = StoredAnomalyRevision(
        update=_update(update_payload["update"]),
        packet=_packet(packet_payload["packet"]),
    )
    anomaly_to_row(row.tenant_id, stored.update, stored.packet)
    packet = stored.packet
    for field, expected in (
        ("anomaly_id", packet.anomaly_id),
        ("packet_revision", packet.packet_revision),
        ("resident_id", packet.resident_id),
        ("room_id", packet.room_id),
        ("baseline_id", packet.baseline_id),
        ("lifecycle_state", packet.lifecycle_state.value),
        ("recorded_at", packet.current_time),
    ):
        _require_shadow(f"anomaly.{field}", getattr(row, field), expected)
    regenerated = anomaly_to_row(row.tenant_id, stored.update, stored.packet)
    if (
        regenerated.update_json != row.update_json
        or regenerated.packet_json != row.packet_json
    ):
        raise ConcurrentUpdateError(
            "Stored anomaly JSON is not canonical domain data"
        )
    return stored


def _request_data(request: InterpretationRequest) -> dict[str, object]:
    return {
        field: list(value) if isinstance(value, tuple) else value
        for field, value in request.__dict__.items()
    }


def _request(data: dict[str, Any]) -> InterpretationRequest:
    tuple_fields = {
        "skill_bundle",
        "available_evidence_refs",
        "available_measurements",
        "unavailable_measurements",
        "contradictions",
        "required_missing_information",
        "required_limitations",
        "required_unsupported_conclusions",
        "retrieved_context_refs",
    }
    expected_fields = {field.name for field in fields(InterpretationRequest)}
    if not isinstance(data, dict) or set(data) != expected_fields:
        raise ConcurrentUpdateError(
            "Stored interpretation request does not use the exact schema"
        )
    if any(not isinstance(data[field], list) for field in tuple_fields):
        raise ConcurrentUpdateError(
            "Stored interpretation request tuple fields must be arrays"
        )
    return InterpretationRequest(
        **{
            key: tuple(value) if key in tuple_fields else value
            for key, value in data.items()
        }
    )


def _alternative_data(item: InterpretationAlternative) -> dict[str, object]:
    return {
        "confidence": item.confidence,
        "contradicting_evidence_refs": list(item.contradicting_evidence_refs),
        "label": _value(item.label),
        "rank": item.rank,
        "supporting_evidence_refs": list(item.supporting_evidence_refs),
    }


def _result_data(result: InterpretationResult) -> dict[str, object]:
    data: dict[str, object] = {}
    for field, value in result.__dict__.items():
        if field == "alternatives":
            data[field] = [_alternative_data(item) for item in value]
        elif isinstance(value, tuple):
            data[field] = list(value)
        else:
            data[field] = _value(value)
    return data


def _result(data: dict[str, Any]) -> InterpretationResult:
    tuple_fields = {
        "supporting_evidence_refs",
        "contradicting_evidence_refs",
        "described_measurements",
        "addressed_contradictions",
        "missing_information",
        "limitations",
        "unsupported_conclusions",
        "skill_bundle",
    }
    values = {
        key: tuple(value) if key in tuple_fields else value
        for key, value in data.items()
        if key != "alternatives"
    }
    values["alternatives"] = tuple(
        InterpretationAlternative(
            rank=item["rank"],
            label=item["label"],
            confidence=item["confidence"],
            supporting_evidence_refs=tuple(item["supporting_evidence_refs"]),
            contradicting_evidence_refs=tuple(item["contradicting_evidence_refs"]),
        )
        for item in data["alternatives"]
    )
    return InterpretationResult(**values)


@dataclass(frozen=True)
class StoredInterpretation:
    request: InterpretationRequest
    result: InterpretationResult
    created_at: datetime


def interpretation_to_row(
    tenant_id: str,
    request: InterpretationRequest,
    result: InterpretationResult,
    created_at: datetime,
) -> LLMInterpretationRow:
    validate_interpretation_request_shape(request)
    validate_interpretation_request_payload(request)
    validate_interpretation(request, result)
    return LLMInterpretationRow(
        interpretation_id=result.interpretation_id,
        tenant_id=tenant_id,
        anomaly_id=result.anomaly_id,
        packet_revision=result.packet_revision,
        status=str(result.status),
        created_at=_utc(created_at),
        model_id=result.model_id,
        model_version=result.model_version,
        prompt_version=result.prompt_version,
        skill_bundle_version=result.skill_bundle_version,
        retrieval_contract_version=result.retrieval_contract_version,
        output_schema_version=result.output_schema_version,
        relevant_context_version=result.relevant_context_version,
        request_fingerprint=result.request_fingerprint,
        request_json=canonical_json(
            {"request": _request_data(request), "tenant_id": tenant_id}
        ),
        result_json=canonical_json(
            {
                "created_at": _time(created_at),
                "result": _result_data(result),
                "tenant_id": tenant_id,
            }
        ),
    )


def interpretation_from_row(row: LLMInterpretationRow) -> StoredInterpretation:
    request_payload = _parse_canonical_json(
        row.request_json,
        "interpretation request",
    )
    result_payload = _parse_canonical_json(
        row.result_json,
        "interpretation result",
    )
    if set(request_payload) != {"request", "tenant_id"}:
        raise ConcurrentUpdateError(
            "Stored interpretation request envelope is not canonical exact schema"
        )
    if set(result_payload) != {"created_at", "result", "tenant_id"}:
        raise ConcurrentUpdateError(
            "Stored interpretation result envelope is not canonical exact schema"
        )
    _require_shadow(
        "interpretation.request_tenant_id",
        row.tenant_id,
        request_payload["tenant_id"],
    )
    _require_shadow(
        "interpretation.result_tenant_id",
        row.tenant_id,
        result_payload["tenant_id"],
    )
    stored = StoredInterpretation(
        request=_request(request_payload["request"]),
        result=_result(result_payload["result"]),
        created_at=_parse_time(result_payload["created_at"]),
    )
    validate_interpretation_request_shape(stored.request)
    validate_interpretation_request_payload(stored.request)
    validate_interpretation(stored.request, stored.result)
    result = stored.result
    for field, expected in (
        ("interpretation_id", result.interpretation_id),
        ("anomaly_id", result.anomaly_id),
        ("packet_revision", result.packet_revision),
        ("status", str(result.status)),
        ("model_id", result.model_id),
        ("model_version", result.model_version),
        ("prompt_version", result.prompt_version),
        ("skill_bundle_version", result.skill_bundle_version),
        ("retrieval_contract_version", result.retrieval_contract_version),
        ("output_schema_version", result.output_schema_version),
        ("relevant_context_version", result.relevant_context_version),
        ("request_fingerprint", result.request_fingerprint),
        ("created_at", stored.created_at),
    ):
        _require_shadow(f"interpretation.{field}", getattr(row, field), expected)
    regenerated = interpretation_to_row(
        row.tenant_id,
        stored.request,
        stored.result,
        stored.created_at,
    )
    if (
        regenerated.request_json != row.request_json
        or regenerated.result_json != row.result_json
    ):
        raise ConcurrentUpdateError(
            "Stored interpretation JSON is not canonical domain data"
        )
    return stored


def _decision_data(decision: DispositionDecision) -> dict[str, object]:
    return {
        "attention_suppressed": decision.attention_suppressed,
        "confidence": decision.confidence,
        "disposition": decision.disposition.value,
        "fallback_used": decision.fallback_used,
        "headline": decision.headline,
        "interpretation_id": decision.interpretation_id,
        "objective_family": decision.objective_family,
        "policy_version": decision.policy_version,
        "priority": None if decision.priority is None else decision.priority.value,
        "provisional_urgent": decision.provisional_urgent,
        "reasons": list(decision.reasons),
        "room_level_only": decision.room_level_only,
        "schema_version": decision.schema_version,
    }


def _decision(data: dict[str, Any]) -> DispositionDecision:
    return DispositionDecision(
        disposition=PolicyDisposition(data["disposition"]),
        priority=None if data["priority"] is None else EventPriority(data["priority"]),
        confidence=data["confidence"],
        objective_family=data["objective_family"],
        headline=data["headline"],
        reasons=tuple(data["reasons"]),
        policy_version=data["policy_version"],
        fallback_used=data["fallback_used"],
        room_level_only=data["room_level_only"],
        interpretation_id=data["interpretation_id"],
        provisional_urgent=data["provisional_urgent"],
        attention_suppressed=data["attention_suppressed"],
        schema_version=data["schema_version"],
    )


@dataclass(frozen=True)
class DispositionRecord:
    disposition_id: str
    resident_id: str
    room_id: str
    anomaly_id: str
    evidence_kind: BridgeEvidenceKind
    evidence_revision: int
    packet_revision: int | None
    decided_at: datetime
    decision: DispositionDecision
    interpretation_id: str | None = None
    event_id: str | None = None

    def __post_init__(self) -> None:
        for field in (
            "disposition_id",
            "resident_id",
            "room_id",
            "anomaly_id",
        ):
            object.__setattr__(
                self,
                field,
                require_nonblank_text(getattr(self, field), field),
            )
        object.__setattr__(
            self,
            "evidence_kind",
            BridgeEvidenceKind(self.evidence_kind),
        )
        evidence_revision = self.evidence_revision
        if (
            isinstance(evidence_revision, bool)
            or not isinstance(evidence_revision, int)
            or evidence_revision < 1
        ):
            raise ValueError("evidence_revision must be a positive integer")
        if self.evidence_kind == BridgeEvidenceKind.PACKET:
            if (
                isinstance(self.packet_revision, bool)
                or not isinstance(self.packet_revision, int)
                or self.packet_revision < 1
                or self.packet_revision != evidence_revision
            ):
                raise ValueError(
                    "packet evidence requires matching positive packet_revision"
                )
        elif self.packet_revision is not None:
            raise ValueError("provisional evidence cannot claim a packet_revision")
        object.__setattr__(
            self,
            "decided_at",
            require_aware_datetime(self.decided_at, "decided_at"),
        )
        if not isinstance(self.decision, DispositionDecision):
            raise ValueError("decision must be a DispositionDecision")
        for field in ("interpretation_id", "event_id"):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(
                    self,
                    field,
                    require_nonblank_text(value, field),
                )
        if self.interpretation_id != self.decision.interpretation_id:
            raise ValueError(
                "interpretation_id must match decision.interpretation_id"
            )


def disposition_to_row(
    tenant_id: str,
    record: DispositionRecord,
) -> DispositionDecisionRow:
    payload = {
        "anomaly_id": record.anomaly_id,
        "decided_at": _time(record.decided_at),
        "decision": _decision_data(record.decision),
        "disposition_id": record.disposition_id,
        "event_id": record.event_id,
        "evidence_kind": record.evidence_kind.value,
        "evidence_revision": record.evidence_revision,
        "interpretation_id": record.interpretation_id,
        "packet_revision": record.packet_revision,
        "resident_id": record.resident_id,
        "room_id": record.room_id,
        "tenant_id": tenant_id,
    }
    return DispositionDecisionRow(
        disposition_id=record.disposition_id,
        tenant_id=tenant_id,
        resident_id=record.resident_id,
        room_id=record.room_id,
        anomaly_id=record.anomaly_id,
        evidence_kind=record.evidence_kind.value,
        evidence_revision=record.evidence_revision,
        packet_revision=record.packet_revision,
        interpretation_id=record.interpretation_id,
        event_id=record.event_id,
        status=record.decision.disposition.value,
        decided_at=_utc(record.decided_at),
        policy_version=record.decision.policy_version,
        payload_json=canonical_json(payload),
    )


def disposition_from_row(row: DispositionDecisionRow) -> DispositionRecord:
    payload = _parse_canonical_json(row.payload_json, "disposition")
    _require_shadow("disposition.tenant_id", row.tenant_id, payload["tenant_id"])
    record = DispositionRecord(
        disposition_id=payload["disposition_id"],
        resident_id=payload["resident_id"],
        room_id=payload["room_id"],
        anomaly_id=payload["anomaly_id"],
        evidence_kind=BridgeEvidenceKind(payload["evidence_kind"]),
        evidence_revision=payload["evidence_revision"],
        packet_revision=payload["packet_revision"],
        decided_at=_parse_time(payload["decided_at"]),
        decision=_decision(payload["decision"]),
        interpretation_id=payload["interpretation_id"],
        event_id=payload["event_id"],
    )
    for field, expected in (
        ("disposition_id", record.disposition_id),
        ("resident_id", record.resident_id),
        ("room_id", record.room_id),
        ("anomaly_id", record.anomaly_id),
        ("evidence_kind", record.evidence_kind.value),
        ("evidence_revision", record.evidence_revision),
        ("packet_revision", record.packet_revision),
        ("interpretation_id", record.interpretation_id),
        ("event_id", record.event_id),
        ("status", record.decision.disposition.value),
        ("decided_at", record.decided_at),
        ("policy_version", record.decision.policy_version),
    ):
        _require_shadow(f"disposition.{field}", getattr(row, field), expected)
    regenerated = disposition_to_row(row.tenant_id, record)
    if regenerated.payload_json != row.payload_json:
        raise ConcurrentUpdateError(
            "Stored disposition JSON is not canonical domain data"
        )
    return record


def event_bridge_data(record: EventBridgeRecord) -> dict[str, object]:
    return {
        "actor_id": record.actor_id,
        "evidence_kind": record.evidence_kind.value,
        "evidence_revision": record.evidence_revision,
        "headline": record.headline,
        "idempotency_key": record.idempotency_key,
        "objective_family": record.objective_family,
        "observed_at": _time(record.observed_at),
        "priority": record.priority.value,
        "provisional_urgent": record.provisional_urgent,
        "related_event_ids": list(record.related_event_ids),
        "resident_id": record.resident_id,
        "resident_memory_entry_ids": list(record.resident_memory_entry_ids),
        "resident_memory_version": record.resident_memory_version,
        "room_id": record.room_id,
        "room_level_only": record.room_level_only,
        "schema_version": record.schema_version,
        "source_anomaly_id": record.source_anomaly_id,
    }


def event_bridge_from_data(data: dict[str, Any]) -> EventBridgeRecord:
    return EventBridgeRecord(
        idempotency_key=data["idempotency_key"],
        resident_id=data["resident_id"],
        room_id=data["room_id"],
        source_anomaly_id=data["source_anomaly_id"],
        evidence_revision=data["evidence_revision"],
        evidence_kind=BridgeEvidenceKind(data["evidence_kind"]),
        objective_family=data["objective_family"],
        headline=data["headline"],
        priority=EventPriority(data["priority"]),
        provisional_urgent=data["provisional_urgent"],
        room_level_only=data["room_level_only"],
        observed_at=_parse_time(data["observed_at"]),
        actor_id=data["actor_id"],
        resident_memory_version=data["resident_memory_version"],
        resident_memory_entry_ids=tuple(data["resident_memory_entry_ids"]),
        related_event_ids=tuple(data["related_event_ids"]),
        schema_version=data["schema_version"],
    )


def event_bridge_to_row(
    tenant_id: str,
    event_id: str,
    record: EventBridgeRecord,
) -> EventBridgeRecordRow:
    return EventBridgeRecordRow(
        tenant_id=tenant_id,
        idempotency_key=record.idempotency_key,
        event_id=event_id,
        resident_id=record.resident_id,
        room_id=record.room_id,
        source_anomaly_id=record.source_anomaly_id,
        evidence_revision=record.evidence_revision,
        evidence_kind=record.evidence_kind.value,
        priority=record.priority.value,
        observed_at=_utc(record.observed_at),
        payload_json=canonical_json(
            {
                "event_id": event_id,
                "record": event_bridge_data(record),
                "tenant_id": tenant_id,
            }
        ),
    )


@dataclass(frozen=True)
class StoredEventBridge:
    event_id: str
    record: EventBridgeRecord


def event_bridge_from_row(row: EventBridgeRecordRow) -> StoredEventBridge:
    payload = _parse_canonical_json(row.payload_json, "event bridge")
    _require_shadow("event_bridge.tenant_id", row.tenant_id, payload["tenant_id"])
    _require_shadow("event_bridge.event_id", row.event_id, payload["event_id"])
    stored = StoredEventBridge(
        event_id=row.event_id,
        record=event_bridge_from_data(payload["record"]),
    )
    record = stored.record
    for field, expected in (
        ("idempotency_key", record.idempotency_key),
        ("resident_id", record.resident_id),
        ("room_id", record.room_id),
        ("source_anomaly_id", record.source_anomaly_id),
        ("evidence_revision", record.evidence_revision),
        ("evidence_kind", record.evidence_kind.value),
        ("priority", record.priority.value),
        ("observed_at", record.observed_at),
    ):
        _require_shadow(f"event_bridge.{field}", getattr(row, field), expected)
    regenerated = event_bridge_to_row(row.tenant_id, row.event_id, record)
    if regenerated.payload_json != row.payload_json:
        raise ConcurrentUpdateError(
            "Stored event bridge JSON is not canonical domain data"
        )
    return stored


def analysis_run_to_row(
    tenant_id: str,
    run: AnalysisRun,
    recorded_at: datetime,
) -> MultiAgentAnalysisRow:
    final = run.final_analysis
    return MultiAgentAnalysisRow(
        tenant_id=require_nonblank_text(tenant_id, "tenant_id"),
        analysis_id=run.analysis_id,
        anomaly_id=run.anomaly_id,
        packet_revision=run.packet_revision,
        state=run.state.value,
        recorded_at=_utc(recorded_at),
        final_model_id=None if final is None else final.model_id,
        final_model_version=None if final is None else final.model_version,
        schema_version=run.schema_version,
        payload_json=canonical_json(
            {
                "analysis_run": analysis_run_data(run),
                "recorded_at": _time(recorded_at),
                "tenant_id": tenant_id,
            }
        ),
    )


def analysis_run_from_row(row: MultiAgentAnalysisRow) -> AnalysisRun:
    payload = _parse_canonical_json(row.payload_json, "multi-agent analysis")
    _require_shadow("analysis.tenant_id", row.tenant_id, payload["tenant_id"])
    _require_shadow("analysis.recorded_at", row.recorded_at, _parse_time(payload["recorded_at"]))
    run = analysis_run_from_data(payload["analysis_run"])
    final = run.final_analysis
    for field, expected in (
        ("analysis_id", run.analysis_id),
        ("anomaly_id", run.anomaly_id),
        ("packet_revision", run.packet_revision),
        ("state", run.state.value),
        ("final_model_id", None if final is None else final.model_id),
        ("final_model_version", None if final is None else final.model_version),
        ("schema_version", run.schema_version),
    ):
        _require_shadow(f"analysis.{field}", getattr(row, field), expected)
    regenerated = analysis_run_to_row(row.tenant_id, run, row.recorded_at)
    if regenerated.payload_json != row.payload_json:
        raise ConcurrentUpdateError(
            "Stored multi-agent analysis JSON is not canonical domain data"
        )
    return run


__all__ = [
    "DispositionRecord",
    "StoredAnomalyRevision",
    "StoredEventBridge",
    "StoredInterpretation",
    "anomaly_from_row",
    "anomaly_to_row",
    "analysis_run_data",
    "analysis_run_from_data",
    "analysis_run_from_row",
    "analysis_run_to_row",
    "baseline_from_rows",
    "baseline_to_rows",
    "canonical_json",
    "disposition_from_row",
    "disposition_to_row",
    "event_bridge_data",
    "event_bridge_from_data",
    "event_bridge_from_row",
    "event_bridge_to_row",
    "interpretation_from_row",
    "interpretation_to_row",
]
