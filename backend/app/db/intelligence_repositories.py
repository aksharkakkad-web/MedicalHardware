"""Tenant-scoped append-only repositories for monitoring intelligence."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.ai.client import InterpretationRequest, InterpretationResult
from backend.app.ai.context import (
    build_interpretation_request,
    validate_interpretation_request_binding,
    validate_interpretation_request_payload,
)
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
from backend.app.db.mappers import memory_from_rows
from backend.app.db.models import (
    AnomalyRevisionRow,
    BaselineDimensionRow,
    BaselineSnapshotRow,
    DispositionDecisionRow,
    EventBridgeRecordRow,
    LLMInterpretationRow,
    ResidentMemoryEntryRow,
    ResidentMemorySnapshotRow,
)
from backend.app.db.repositories import EventRepository
from backend.app.domain.feedback import ResidentMemory
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
        proposed = interpretation_from_row(candidate)
        self._validate_interpretation_links(tenant_id, proposed)
        existing = self._session.get(
            LLMInterpretationRow,
            (tenant_id, result.interpretation_id),
        )
        if existing is not None:
            if not _same_row(existing, candidate):
                raise ConcurrentUpdateError()
            return self._hydrate_interpretation(tenant_id, existing)
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
            return self._hydrate_interpretation(tenant_id, winner)
        return proposed

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
        return None if row is None else self._hydrate_interpretation(tenant_id, row)

    def save_disposition(
        self,
        tenant_id: str,
        record: DispositionRecord,
    ) -> DispositionRecord:
        candidate = disposition_to_row(tenant_id, record)
        existing = self._session.get(
            DispositionDecisionRow,
            (tenant_id, record.disposition_id),
        )
        if existing is not None:
            if not _same_row(existing, candidate):
                raise ConcurrentUpdateError()
            return self._hydrate_disposition(tenant_id, existing)
        self._validate_disposition_links(tenant_id, record)
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
            return self._hydrate_disposition(tenant_id, winner)
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
        return None if row is None else self._hydrate_disposition(tenant_id, row)

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

    def _hydrate_interpretation(
        self,
        tenant_id: str,
        row: LLMInterpretationRow,
    ) -> StoredInterpretation:
        stored = interpretation_from_row(row)
        self._validate_interpretation_links(tenant_id, stored)
        return stored

    def _validate_interpretation_links(
        self,
        tenant_id: str,
        stored: StoredInterpretation,
    ) -> None:
        request = stored.request
        resident_id, memory_version, entry_ids = (
            validate_interpretation_request_payload(request)
        )
        anomaly = self._anomaly_revision(
            tenant_id,
            request.anomaly_id,
            request.packet_revision,
        )
        if anomaly is None:
            raise ValueError("interpretation anomaly revision does not exist")
        packet = anomaly_from_row(anomaly).packet
        validate_interpretation_request_binding(packet, request)
        if resident_id != packet.resident_id:
            raise ValueError("interpretation resident memory does not match packet")
        if memory_version == 0:
            if entry_ids:
                raise ValueError("resident memory version 0 must be explicitly empty")
            memory = ResidentMemory(resident_id, 0, ())
        else:
            snapshot = self._session.scalar(
                select(ResidentMemorySnapshotRow).where(
                    ResidentMemorySnapshotRow.tenant_id == tenant_id,
                    ResidentMemorySnapshotRow.resident_id == resident_id,
                    ResidentMemorySnapshotRow.version == memory_version,
                )
            )
            if snapshot is None:
                raise ValueError(
                    "interpretation resident memory snapshot does not exist"
                )
            entries = self._session.scalars(
                select(ResidentMemoryEntryRow)
                .where(
                    ResidentMemoryEntryRow.tenant_id == tenant_id,
                    ResidentMemoryEntryRow.resident_id == resident_id,
                    ResidentMemoryEntryRow.memory_version == memory_version,
                )
                .order_by(ResidentMemoryEntryRow.memory_entry_row_id)
            ).all()
            memory = memory_from_rows(snapshot, entries)
        rebuilt = build_interpretation_request(
            packet,
            memory,
            model_id=request.model_id,
            model_version=request.model_version,
            urgent_deterministic_event=request.urgent_deterministic_event,
            relevant_context_entry_ids=entry_ids,
        )
        if rebuilt != request:
            raise ValueError("interpretation request does not match resident memory")
        if _utc(stored.created_at) < _utc(packet.current_time):
            raise ValueError("interpretation cannot precede packet evidence")

    def _hydrate_disposition(
        self,
        tenant_id: str,
        row: DispositionDecisionRow,
    ) -> DispositionRecord:
        record = disposition_from_row(row)
        self._validate_disposition_links(tenant_id, record)
        return record

    def _validate_disposition_links(
        self,
        tenant_id: str,
        record: DispositionRecord,
    ) -> None:
        if record.evidence_kind.value == "provisional":
            self._validate_provisional_disposition(tenant_id, record)
            return
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
        packet = anomaly_from_row(anomaly).packet
        if _utc(record.decided_at) < _utc(packet.current_time):
            raise ValueError("disposition cannot precede packet evidence")
        if record.interpretation_id is not None:
            interpretation_row = self._session.get(
                LLMInterpretationRow,
                (tenant_id, record.interpretation_id),
            )
            if interpretation_row is None or (
                interpretation_row.anomaly_id,
                interpretation_row.packet_revision,
            ) != (record.anomaly_id, record.packet_revision):
                raise ValueError(
                    "disposition interpretation does not match anomaly revision"
                )
            interpretation = self._hydrate_interpretation(
                tenant_id,
                interpretation_row,
            )
            if _utc(record.decided_at) < _utc(interpretation.created_at):
                raise ValueError("disposition cannot precede interpretation")
        self._validate_disposition_event_chain(
            tenant_id,
            record,
            packet_time=packet.current_time,
        )

    def _validate_provisional_disposition(
        self,
        tenant_id: str,
        record: DispositionRecord,
    ) -> None:
        if (
            record.decision.disposition.value != "caregiver_event"
            or not record.decision.provisional_urgent
            or record.event_id is None
            or record.interpretation_id is not None
        ):
            raise ValueError(
                "provisional disposition requires urgent caregiver event without interpretation"
            )
        self._validate_disposition_event_chain(tenant_id, record)

    def _validate_disposition_event_chain(
        self,
        tenant_id: str,
        record: DispositionRecord,
        *,
        packet_time: datetime | None = None,
    ) -> None:
        caregiver = record.decision.disposition.value == "caregiver_event"
        if not caregiver:
            if record.event_id is not None:
                raise ValueError("non-caregiver disposition cannot link an event")
            return
        if record.event_id is None or record.decision.priority is None:
            raise ValueError("caregiver disposition requires linked event")
        revision_component = (
            f"provisional-{record.evidence_revision}"
            if record.evidence_kind.value == "provisional"
            else str(record.evidence_revision)
        )
        expected_key = ":".join(
            (
                record.anomaly_id,
                revision_component,
                record.decision.policy_version,
            )
        )
        bridge = self._session.scalar(
            select(EventBridgeRecordRow).where(
                EventBridgeRecordRow.tenant_id == tenant_id,
                EventBridgeRecordRow.idempotency_key == expected_key,
                EventBridgeRecordRow.event_id == record.event_id,
                EventBridgeRecordRow.source_anomaly_id == record.anomaly_id,
                EventBridgeRecordRow.evidence_revision == record.evidence_revision,
                EventBridgeRecordRow.evidence_kind == record.evidence_kind.value,
            )
        )
        if bridge is None:
            raise ValueError("disposition bridge does not exist")
        stored_bridge = event_bridge_from_row(bridge).record
        stored_event = EventRepository(self._session).find(
            tenant_id,
            record.event_id,
        )
        if stored_event is None or (
            stored_event.event.resident_id,
            stored_event.event.room_id,
        ) != (
            record.resident_id,
            record.room_id,
        ):
            raise ValueError("disposition event lane does not match")
        event = stored_event.event
        matching_event_bridges = tuple(
            item
            for item in event.bridge_records
            if item.idempotency_key == expected_key
        )
        if (
            expected_key not in event.bridge_idempotency_keys
            or matching_event_bridges != (stored_bridge,)
        ):
            raise ValueError("disposition event bridge ledger does not match")
        if any(
            not (
                _utc(event.created_at)
                <= _utc(item.observed_at)
                <= _utc(event.last_signal_at)
            )
            for item in event.bridge_records
        ):
            raise ValueError("disposition bridge falls outside event signal history")
        decision = record.decision
        expected_metadata = (
            (stored_bridge.idempotency_key, expected_key),
            (stored_bridge.resident_id, record.resident_id),
            (stored_bridge.room_id, record.room_id),
            (stored_bridge.objective_family, decision.objective_family),
            (stored_bridge.headline, decision.headline),
            (stored_bridge.priority, decision.priority),
            (stored_bridge.provisional_urgent, decision.provisional_urgent),
            (stored_bridge.room_level_only, decision.room_level_only),
            (event.objective_family, decision.objective_family),
            (event.headline, decision.headline),
            (event.priority, decision.priority),
            (event.provisional_urgent, decision.provisional_urgent),
            (event.room_level_only, decision.room_level_only),
        )
        if any(actual != expected for actual, expected in expected_metadata):
            raise ValueError("disposition event metadata does not match decision")
        if packet_time is not None and _utc(stored_bridge.observed_at) < _utc(
            packet_time
        ):
            raise ValueError("disposition bridge cannot precede packet evidence")
        if not (
            _utc(event.created_at)
            <= _utc(stored_bridge.observed_at)
            <= _utc(event.last_signal_at)
        ):
            raise ValueError("disposition bridge falls outside event signal history")
        if any(
            _utc(record.decided_at) < _utc(timestamp)
            for timestamp in (event.created_at, stored_bridge.observed_at)
        ):
            raise ValueError("disposition cannot precede event or bridge evidence")


__all__ = ["IntelligenceRepository"]
