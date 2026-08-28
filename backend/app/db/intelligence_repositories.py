"""Tenant-scoped append-only repositories for monitoring intelligence."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.ai.client import InterpretationRequest, InterpretationResult
from backend.app.db.intelligence_mappers import (
    DispositionRecord,
    StoredAnomalyRevision,
    StoredEventBridge,
    StoredInterpretation,
    anomaly_from_row,
    anomaly_to_row,
    baseline_from_rows,
    baseline_to_rows,
    disposition_from_row,
    disposition_to_row,
    event_bridge_from_row,
    interpretation_from_row,
    interpretation_to_row,
)
from backend.app.db.models import (
    AnomalyRevisionRow,
    BaselineDimensionRow,
    BaselineSnapshotRow,
    DispositionDecisionRow,
    EventBridgeRecordRow,
    LLMInterpretationRow,
)
from backend.app.intelligence.anomaly import AnomalyUpdate
from backend.app.intelligence.baseline import BaselineSnapshot
from backend.app.intelligence.evidence import EvidencePacket
from backend.app.services.errors import ConcurrentUpdateError


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class IntelligenceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save_baseline(
        self,
        tenant_id: str,
        baseline: BaselineSnapshot,
        recorded_at: datetime,
    ) -> BaselineSnapshot:
        row, dimensions = baseline_to_rows(tenant_id, baseline, recorded_at)
        existing = self._session.get(BaselineSnapshotRow, baseline.baseline_id)
        if existing is not None:
            if existing.tenant_id != tenant_id:
                raise ConcurrentUpdateError()
            existing_dimensions = self._baseline_dimensions(
                tenant_id, baseline.baseline_id
            )
            if (
                existing.payload_json != row.payload_json
                or _utc(existing.recorded_at) != _utc(recorded_at)
                or tuple(item.payload_json for item in existing_dimensions)
                != tuple(item.payload_json for item in dimensions)
            ):
                raise ConcurrentUpdateError()
            return baseline_from_rows(existing, existing_dimensions)
        self._session.add(row)
        self._session.flush()
        self._session.add_all(dimensions)
        self._session.flush()
        return baseline

    def latest_baseline(
        self,
        tenant_id: str,
        resident_id: str,
    ) -> BaselineSnapshot | None:
        row = self._session.scalar(
            select(BaselineSnapshotRow)
            .where(
                BaselineSnapshotRow.tenant_id == tenant_id,
                BaselineSnapshotRow.resident_id == resident_id,
            )
            .order_by(
                BaselineSnapshotRow.recorded_at.desc(),
                BaselineSnapshotRow.baseline_id.desc(),
            )
            .limit(1)
        )
        if row is None:
            return None
        return baseline_from_rows(
            row,
            self._baseline_dimensions(tenant_id, row.baseline_id),
        )

    def save_anomaly_revision(
        self,
        tenant_id: str,
        update: AnomalyUpdate,
        packet: EvidencePacket,
    ) -> StoredAnomalyRevision:
        candidate = anomaly_to_row(tenant_id, update, packet)
        existing = self._session.scalar(
            select(AnomalyRevisionRow).where(
                AnomalyRevisionRow.tenant_id == tenant_id,
                AnomalyRevisionRow.anomaly_id == packet.anomaly_id,
                AnomalyRevisionRow.packet_revision == packet.packet_revision,
            )
        )
        if existing is not None:
            if (
                existing.update_json != candidate.update_json
                or existing.packet_json != candidate.packet_json
            ):
                raise ConcurrentUpdateError()
            return anomaly_from_row(existing)
        self._session.add(candidate)
        self._session.flush()
        return anomaly_from_row(candidate)

    def latest_anomaly(
        self,
        tenant_id: str,
        anomaly_id: str,
    ) -> StoredAnomalyRevision | None:
        row = self._session.scalar(
            select(AnomalyRevisionRow)
            .where(
                AnomalyRevisionRow.tenant_id == tenant_id,
                AnomalyRevisionRow.anomaly_id == anomaly_id,
            )
            .order_by(AnomalyRevisionRow.packet_revision.desc())
            .limit(1)
        )
        return None if row is None else anomaly_from_row(row)

    def save_interpretation(
        self,
        tenant_id: str,
        request: InterpretationRequest,
        result: InterpretationResult,
        created_at: datetime,
    ) -> StoredInterpretation:
        candidate = interpretation_to_row(
            tenant_id, request, result, created_at
        )
        existing = self._session.get(
            LLMInterpretationRow, result.interpretation_id
        )
        if existing is not None:
            if existing.tenant_id != tenant_id or (
                existing.request_json != candidate.request_json
                or existing.result_json != candidate.result_json
                or _utc(existing.created_at) != _utc(created_at)
            ):
                raise ConcurrentUpdateError()
            return interpretation_from_row(existing)
        self._session.add(candidate)
        self._session.flush()
        return interpretation_from_row(candidate)

    def find_interpretation(
        self,
        tenant_id: str,
        interpretation_id: str,
    ) -> StoredInterpretation | None:
        row = self._session.scalar(
            select(LLMInterpretationRow).where(
                LLMInterpretationRow.tenant_id == tenant_id,
                LLMInterpretationRow.interpretation_id == interpretation_id,
            )
        )
        return None if row is None else interpretation_from_row(row)

    def save_disposition(
        self,
        tenant_id: str,
        record: DispositionRecord,
    ) -> DispositionRecord:
        candidate = disposition_to_row(tenant_id, record)
        existing = self._session.get(
            DispositionDecisionRow, record.disposition_id
        )
        if existing is not None:
            if existing.tenant_id != tenant_id or (
                existing.payload_json != candidate.payload_json
                or existing.resident_id != candidate.resident_id
                or existing.room_id != candidate.room_id
                or existing.anomaly_id != candidate.anomaly_id
                or existing.packet_revision != candidate.packet_revision
                or existing.interpretation_id != candidate.interpretation_id
                or existing.event_id != candidate.event_id
                or _utc(existing.decided_at) != _utc(candidate.decided_at)
            ):
                raise ConcurrentUpdateError()
            return disposition_from_row(existing)
        self._session.add(candidate)
        self._session.flush()
        return disposition_from_row(candidate)

    def find_disposition(
        self,
        tenant_id: str,
        disposition_id: str,
    ) -> DispositionRecord | None:
        row = self._session.scalar(
            select(DispositionDecisionRow).where(
                DispositionDecisionRow.tenant_id == tenant_id,
                DispositionDecisionRow.disposition_id == disposition_id,
            )
        )
        return None if row is None else disposition_from_row(row)

    def find_event_bridge(
        self,
        tenant_id: str,
        idempotency_key: str,
    ) -> StoredEventBridge | None:
        row = self._session.scalar(
            select(EventBridgeRecordRow).where(
                EventBridgeRecordRow.tenant_id == tenant_id,
                EventBridgeRecordRow.idempotency_key == idempotency_key,
            )
        )
        return None if row is None else event_bridge_from_row(row)

    def _baseline_dimensions(
        self,
        tenant_id: str,
        baseline_id: str,
    ) -> tuple[BaselineDimensionRow, ...]:
        return tuple(
            self._session.scalars(
                select(BaselineDimensionRow)
                .where(
                    BaselineDimensionRow.tenant_id == tenant_id,
                    BaselineDimensionRow.baseline_id == baseline_id,
                )
                .order_by(
                    BaselineDimensionRow.feature_name,
                    BaselineDimensionRow.context_key,
                )
            )
        )


__all__ = ["IntelligenceRepository"]
