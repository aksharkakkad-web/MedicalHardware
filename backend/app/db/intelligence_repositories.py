"""Tenant-scoped append-only repositories for monitoring intelligence."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
    MonitoringEventRow,
)
from backend.app.intelligence.anomaly import AnomalyUpdate
from backend.app.intelligence.baseline import BaselineSnapshot
from backend.app.intelligence.evidence import EvidencePacket
from backend.app.services.errors import ConcurrentUpdateError


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _same_row(
    left: object,
    right: object,
    *,
    exclude: frozenset[str] = frozenset(),
) -> bool:
    table = type(left).__table__
    if type(left) is not type(right):
        return False
    for column in table.columns:
        if column.name in exclude:
            continue
        left_value = getattr(left, column.name)
        right_value = getattr(right, column.name)
        if isinstance(left_value, datetime) and isinstance(right_value, datetime):
            left_value = _utc(left_value)
            right_value = _utc(right_value)
        if left_value != right_value:
            return False
    return True


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
        existing = self._session.get(
            BaselineSnapshotRow,
            (tenant_id, baseline.baseline_id),
        )
        if existing is not None:
            return self._reconcile_baseline(existing, row, dimensions)
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
                self._session.add_all(dimensions)
                self._session.flush()
        except IntegrityError as exc:
            winner = self._session.get(
                BaselineSnapshotRow,
                (tenant_id, baseline.baseline_id),
                populate_existing=True,
            )
            if winner is None:
                raise ConcurrentUpdateError() from exc
            return self._reconcile_baseline(winner, row, dimensions)
        return baseline_from_rows(row, dimensions)

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
            if not _same_row(
                existing,
                candidate,
                exclude=frozenset({"anomaly_revision_id"}),
            ):
                raise ConcurrentUpdateError()
            return anomaly_from_row(existing)
        try:
            with self._session.begin_nested():
                self._session.add(candidate)
                self._session.flush()
        except IntegrityError as exc:
            winner = self._anomaly_revision(
                tenant_id,
                packet.anomaly_id,
                packet.packet_revision,
            )
            if winner is None or not _same_row(
                winner,
                candidate,
                exclude=frozenset({"anomaly_revision_id"}),
            ):
                raise ConcurrentUpdateError() from exc
            return anomaly_from_row(winner)
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
            LLMInterpretationRow,
            (tenant_id, result.interpretation_id),
        )
        if existing is not None:
            if not _same_row(existing, candidate):
                raise ConcurrentUpdateError()
            return interpretation_from_row(existing)
        try:
            with self._session.begin_nested():
                self._session.add(candidate)
                self._session.flush()
        except IntegrityError as exc:
            winner = self._session.get(
                LLMInterpretationRow,
                (tenant_id, result.interpretation_id),
                populate_existing=True,
            )
            if winner is None or not _same_row(winner, candidate):
                raise ConcurrentUpdateError() from exc
            return interpretation_from_row(winner)
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
        self._validate_disposition_links(tenant_id, record)
        candidate = disposition_to_row(tenant_id, record)
        existing = self._session.get(
            DispositionDecisionRow,
            (tenant_id, record.disposition_id),
        )
        if existing is not None:
            if not _same_row(existing, candidate):
                raise ConcurrentUpdateError()
            return disposition_from_row(existing)
        try:
            with self._session.begin_nested():
                self._session.add(candidate)
                self._session.flush()
        except IntegrityError as exc:
            winner = self._session.get(
                DispositionDecisionRow,
                (tenant_id, record.disposition_id),
                populate_existing=True,
            )
            if winner is None or not _same_row(winner, candidate):
                raise ConcurrentUpdateError() from exc
            return disposition_from_row(winner)
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

    def _reconcile_baseline(
        self,
        existing: BaselineSnapshotRow,
        candidate: BaselineSnapshotRow,
        candidate_dimensions: tuple[BaselineDimensionRow, ...],
    ) -> BaselineSnapshot:
        existing_dimensions = self._baseline_dimensions(
            existing.tenant_id,
            existing.baseline_id,
        )
        if (
            not _same_row(existing, candidate)
            or len(existing_dimensions) != len(candidate_dimensions)
            or any(
                not _same_row(
                    stored,
                    proposed,
                    exclude=frozenset({"baseline_dimension_id"}),
                )
                for stored, proposed in zip(
                    existing_dimensions,
                    candidate_dimensions,
                    strict=True,
                )
            )
        ):
            raise ConcurrentUpdateError()
        return baseline_from_rows(existing, existing_dimensions)

    def _anomaly_revision(
        self,
        tenant_id: str,
        anomaly_id: str,
        packet_revision: int,
    ) -> AnomalyRevisionRow | None:
        return self._session.scalar(
            select(AnomalyRevisionRow).where(
                AnomalyRevisionRow.tenant_id == tenant_id,
                AnomalyRevisionRow.anomaly_id == anomaly_id,
                AnomalyRevisionRow.packet_revision == packet_revision,
            )
        )

    def _validate_disposition_links(
        self,
        tenant_id: str,
        record: DispositionRecord,
    ) -> None:
        anomaly = self._anomaly_revision(
            tenant_id,
            record.anomaly_id,
            record.packet_revision,
        )
        if anomaly is None:
            raise ValueError("disposition anomaly revision does not exist")
        if (anomaly.resident_id, anomaly.room_id) != (
            record.resident_id,
            record.room_id,
        ):
            raise ValueError("disposition lane does not match anomaly revision")
        if record.interpretation_id is not None:
            interpretation = self._session.get(
                LLMInterpretationRow,
                (tenant_id, record.interpretation_id),
            )
            if interpretation is None or (
                interpretation.anomaly_id,
                interpretation.packet_revision,
            ) != (record.anomaly_id, record.packet_revision):
                raise ValueError(
                    "disposition interpretation does not match anomaly revision"
                )
        if record.event_id is not None:
            event = self._session.scalar(
                select(MonitoringEventRow).where(
                    MonitoringEventRow.tenant_id == tenant_id,
                    MonitoringEventRow.event_id == record.event_id,
                )
            )
            if event is None or (event.resident_id, event.room_id) != (
                record.resident_id,
                record.room_id,
            ):
                raise ValueError("disposition event does not match resident lane")


__all__ = ["IntelligenceRepository"]
