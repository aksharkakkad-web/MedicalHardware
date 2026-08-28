"""Explicit reversible mappings for immutable monitoring-intelligence records."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any

from backend.app.ai.client import (
    InterpretationAlternative,
    InterpretationRequest,
    InterpretationResult,
)
from backend.app.db.models import (
    AnomalyRevisionRow,
    BaselineDimensionRow,
    BaselineSnapshotRow,
    DispositionDecisionRow,
    EventBridgeRecordRow,
    LLMInterpretationRow,
)
from backend.app.domain.events import (
    BridgeEvidenceKind,
    EventBridgeRecord,
    EventPriority,
)
from backend.app.intelligence.anomaly import (
    AnomalyEpisode,
    AnomalyState,
    AnomalyUpdate,
    FeatureDeviation,
)
from backend.app.intelligence.baseline import BaselineSnapshot, FeatureBaseline
from backend.app.intelligence.evidence import EvidencePacket
from backend.app.intelligence.observations import FeaturePurpose, QualityClass
from backend.app.intelligence.policy import (
    DispositionDecision,
    PolicyDisposition,
)


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


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
    payload = {
        "adoption_candidate_id": baseline.adoption_candidate_id,
        "adoption_context_entry_id": baseline.adoption_context_entry_id,
        "baseline_id": baseline.baseline_id,
        "monitoring_setup_version": baseline.monitoring_setup_version,
        "policy_version": baseline.policy_version,
        "prior_baseline_id": baseline.prior_baseline_id,
        "resident_id": baseline.resident_id,
        "schema_version": baseline.schema_version,
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
    dimensions = tuple(
        BaselineDimensionRow(
            tenant_id=tenant_id,
            baseline_id=baseline.baseline_id,
            feature_name=feature.feature_name,
            purpose=feature.purpose.value,
            context_key=feature.context_key,
            unit=feature.unit,
            payload_json=canonical_json(_feature_baseline_data(feature)),
        )
        for feature in baseline.features
    )
    return snapshot, dimensions


def baseline_from_rows(
    snapshot: BaselineSnapshotRow,
    dimensions: tuple[BaselineDimensionRow, ...],
) -> BaselineSnapshot:
    data = json.loads(snapshot.payload_json)
    return BaselineSnapshot(
        baseline_id=data["baseline_id"],
        resident_id=data["resident_id"],
        monitoring_setup_version=data["monitoring_setup_version"],
        features=tuple(
            _feature_baseline(json.loads(row.payload_json))
            for row in sorted(
                dimensions,
                key=lambda item: (item.feature_name, item.context_key),
            )
        ),
        policy_version=data["policy_version"],
        prior_baseline_id=data["prior_baseline_id"],
        adoption_candidate_id=data["adoption_candidate_id"],
        adoption_context_entry_id=data["adoption_context_entry_id"],
        schema_version=data["schema_version"],
    )


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
    if update.episode is None or update.episode.anomaly_id != packet.anomaly_id:
        raise ValueError("anomaly update and evidence packet must share an anomaly")
    if update.episode.packet_revision != packet.packet_revision:
        raise ValueError("anomaly update and evidence packet must share a revision")
    return AnomalyRevisionRow(
        tenant_id=tenant_id,
        anomaly_id=packet.anomaly_id,
        packet_revision=packet.packet_revision,
        resident_id=packet.resident_id,
        room_id=packet.room_id,
        baseline_id=packet.baseline_id,
        lifecycle_state=packet.lifecycle_state.value,
        recorded_at=_utc(packet.current_time),
        update_json=canonical_json(_update_data(update)),
        packet_json=canonical_json(_packet_data(packet)),
    )


def anomaly_from_row(row: AnomalyRevisionRow) -> StoredAnomalyRevision:
    return StoredAnomalyRevision(
        update=_update(json.loads(row.update_json)),
        packet=_packet(json.loads(row.packet_json)),
    )


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
    return InterpretationRequest(
        **{key: tuple(value) if key in tuple_fields else value for key, value in data.items()}
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
    if (request.anomaly_id, request.packet_revision) != (
        result.anomaly_id,
        result.packet_revision,
    ):
        raise ValueError("interpretation request and result must share an anomaly revision")
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
        request_json=canonical_json(_request_data(request)),
        result_json=canonical_json(_result_data(result)),
    )


def interpretation_from_row(row: LLMInterpretationRow) -> StoredInterpretation:
    return StoredInterpretation(
        request=_request(json.loads(row.request_json)),
        result=_result(json.loads(row.result_json)),
        created_at=_utc(row.created_at),
    )


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
    packet_revision: int
    decided_at: datetime
    decision: DispositionDecision
    interpretation_id: str | None = None
    event_id: str | None = None


def disposition_to_row(tenant_id: str, record: DispositionRecord) -> DispositionDecisionRow:
    return DispositionDecisionRow(
        disposition_id=record.disposition_id,
        tenant_id=tenant_id,
        resident_id=record.resident_id,
        room_id=record.room_id,
        anomaly_id=record.anomaly_id,
        packet_revision=record.packet_revision,
        interpretation_id=record.interpretation_id,
        event_id=record.event_id,
        status=record.decision.disposition.value,
        decided_at=_utc(record.decided_at),
        policy_version=record.decision.policy_version,
        payload_json=canonical_json(_decision_data(record.decision)),
    )


def disposition_from_row(row: DispositionDecisionRow) -> DispositionRecord:
    return DispositionRecord(
        disposition_id=row.disposition_id,
        resident_id=row.resident_id,
        room_id=row.room_id,
        anomaly_id=row.anomaly_id,
        packet_revision=row.packet_revision,
        decided_at=_utc(row.decided_at),
        decision=_decision(json.loads(row.payload_json)),
        interpretation_id=row.interpretation_id,
        event_id=row.event_id,
    )


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
        payload_json=canonical_json(event_bridge_data(record)),
    )


@dataclass(frozen=True)
class StoredEventBridge:
    event_id: str
    record: EventBridgeRecord


def event_bridge_from_row(row: EventBridgeRecordRow) -> StoredEventBridge:
    return StoredEventBridge(
        event_id=row.event_id,
        record=event_bridge_from_data(json.loads(row.payload_json)),
    )


__all__ = [
    "DispositionRecord",
    "StoredAnomalyRevision",
    "StoredEventBridge",
    "StoredInterpretation",
    "anomaly_from_row",
    "anomaly_to_row",
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
