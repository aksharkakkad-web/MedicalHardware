from dataclasses import dataclass

from backend.app.contracts.events import (
    AnalysisPossibilityResponse,
    EventAnalysisResponse,
    EventActionResponse,
    EventListResponse,
    EventPriorityHistoryResponse,
    EventResponse,
    ResidentAnalysisListResponse,
    ResidentAnalysisResponse,
)
from backend.app.ai.analysis_contracts import AnalysisRun
from backend.app.db.intelligence_repositories import IntelligenceRepository
from backend.app.contracts.feedback import MemoryEntryResponse, ResidentMemoryResponse
from backend.app.contracts.residents import ResidentListResponse, ResidentSummary
from backend.app.db.mappers import StoredEvent
from backend.app.db.repositories import (
    EventRepository,
    FeedbackRepository,
    ResidentRecord,
    ResidentRepository,
)
from backend.app.domain.feedback import ResidentMemory
from backend.app.services.errors import NotFoundError


@dataclass(frozen=True)
class AccessContext:
    tenant_id: str
    actor_id: str


def analysis_response(run: AnalysisRun | None) -> EventAnalysisResponse | None:
    if run is None:
        return None
    final = run.final_analysis
    return EventAnalysisResponse(
        analysis_id=run.analysis_id,
        packet_revision=run.packet_revision,
        state=run.state,
        possibilities=(
            []
            if final is None
            else [
                AnalysisPossibilityResponse(
                    possibility_id=item.possibility_id,
                    label=item.label,
                    confidence=item.confidence,
                    supporting_evidence_refs=list(item.supporting_evidence_refs),
                    contradicting_evidence_refs=list(item.contradicting_evidence_refs),
                    missing_information=list(item.missing_information),
                )
                for item in final.possibilities
            ]
        ),
        severity=None if final is None else final.severity,
        recommended_disposition=(
            None if final is None else final.recommended_disposition
        ),
        attribution_scope=None if final is None else final.attribution_scope,
        caregiver_summary=None if final is None else final.caregiver_summary,
        next_step=None if final is None else final.next_step,
        missing_information=(
            [] if final is None else list(final.missing_information)
        ),
        specialist_disagreements=(
            [] if final is None else list(final.specialist_disagreements)
        ),
        evidence_refs=[] if final is None else list(final.evidence_refs),
        unavailable_specialists=list(run.unavailable_specialists),
        errors=list(run.errors),
        model_id=None if final is None else final.model_id,
        model_version=None if final is None else final.model_version,
        skill_versions=[] if final is None else list(final.skill_versions),
    )


def event_response(
    stored: StoredEvent,
    analysis: AnalysisRun | None = None,
) -> EventResponse:
    event = stored.event
    return EventResponse(
        event_id=event.event_id,
        episode_id=event.episode_id,
        resident_id=event.resident_id,
        room_id=event.room_id,
        objective_family=event.objective_family,
        headline=event.headline,
        priority=event.priority,
        status=event.status,
        created_at=event.created_at,
        last_signal_at=event.last_signal_at,
        signal_count=event.signal_count,
        related_event_ids=list(event.related_event_ids),
        recurrence_count=event.recurrence_count,
        overdue_at=event.overdue_at,
        overdue=event.overdue,
        resolution_outcome=event.resolution_outcome,
        action_history=[
            EventActionResponse(
                action=action.action,
                actor_id=action.actor_id,
                occurred_at=action.occurred_at,
                previous_status=action.previous_status,
                status=action.status,
                resolution_outcome=action.resolution_outcome,
            )
            for action in event.action_history
        ],
        priority_history=[
            EventPriorityHistoryResponse(
                previous_priority=item.previous_priority,
                priority=item.priority,
                actor_id=item.actor_id,
                changed_at=item.changed_at,
            )
            for item in event.priority_history
        ],
        resident_memory_version=event.resident_memory_version,
        resident_memory_entry_ids=list(event.resident_memory_entry_ids),
        analysis=analysis_response(analysis),
        version=stored.version,
    )


class ProductQueryService:
    def __init__(
        self,
        residents: ResidentRepository,
        events: EventRepository,
        feedback: FeedbackRepository,
        intelligence: IntelligenceRepository | None = None,
    ) -> None:
        self._residents = residents
        self._events = events
        self._feedback = feedback
        self._intelligence = intelligence

    def _event_response(self, context: AccessContext, stored: StoredEvent) -> EventResponse:
        anomaly_id = stored.event.source_anomaly_id
        revision = stored.event.latest_evidence_revision
        analysis = (
            None
            if self._intelligence is None or anomaly_id is None or revision is None
            else self._intelligence.analysis_for_revision(
                context.tenant_id,
                anomaly_id,
                revision,
            )
        )
        return event_response(stored, analysis)

    def list_residents(self, context: AccessContext) -> ResidentListResponse:
        return ResidentListResponse(
            items=[
                self._resident_response(record)
                for record in self._residents.list(context.tenant_id)
            ]
        )

    def get_resident(
        self,
        context: AccessContext,
        resident_id: str,
    ) -> ResidentSummary:
        record = self._residents.find(context.tenant_id, resident_id)
        if record is None:
            raise NotFoundError()
        return self._resident_response(record)

    def list_resident_events(
        self,
        context: AccessContext,
        resident_id: str,
    ) -> EventListResponse:
        self.get_resident(context, resident_id)
        return EventListResponse(
            items=[
                self._event_response(context, stored)
                for stored in self._events.list_for_resident(
                    context.tenant_id,
                    resident_id,
                )
            ]
        )

    def list_resident_analyses(
        self,
        context: AccessContext,
        resident_id: str,
    ) -> ResidentAnalysisListResponse:
        self.get_resident(context, resident_id)
        if self._intelligence is None:
            return ResidentAnalysisListResponse(items=[])
        return ResidentAnalysisListResponse(
            items=[
                ResidentAnalysisResponse(
                    anomaly_id=packet.anomaly_id,
                    resident_id=packet.resident_id,
                    room_id=packet.room_id,
                    observed_at=packet.current_time,
                    analysis=analysis_response(run),
                )
                for packet, run in self._intelligence.list_analysis_runs_for_resident(
                    context.tenant_id,
                    resident_id,
                )
            ]
        )

    def get_event(
        self,
        context: AccessContext,
        event_id: str,
    ) -> EventResponse:
        return self._event_response(
            context,
            self._events.get(context.tenant_id, event_id),
        )

    def get_resident_memory(
        self,
        context: AccessContext,
        resident_id: str,
    ) -> ResidentMemoryResponse:
        self.get_resident(context, resident_id)
        return self._memory_response(
            self._feedback.current_memory(context.tenant_id, resident_id)
        )

    @staticmethod
    def _resident_response(record: ResidentRecord) -> ResidentSummary:
        return ResidentSummary.model_validate(record, from_attributes=True)

    @staticmethod
    def _memory_response(memory: ResidentMemory) -> ResidentMemoryResponse:
        return ResidentMemoryResponse(
            resident_id=memory.resident_id,
            version=memory.version,
            entries=[
                MemoryEntryResponse(
                    entry_id=entry.entry_id,
                    description=entry.description,
                    source_kind=entry.source_kind,
                    source_feedback_id=entry.source_feedback_id,
                    supersedes_entry_id=entry.supersedes_entry_id,
                    status=entry.status,
                    created_by=entry.created_by,
                    created_at=entry.created_at,
                    retired_by=entry.retired_by,
                    retired_at=entry.retired_at,
                    retirement_reason=entry.retirement_reason,
                )
                for entry in memory.entries
            ],
        )
