"""Tenant-scoped trusted feedback commands backed by hydrated domain state."""

from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.db.models import AuditLogRow
from backend.app.db.repositories import EventRepository, FeedbackRepository
from backend.app.domain.feedback import FeedbackService, LearningDecision
from backend.app.services.errors import InvalidTransitionError
from backend.app.services.queries import AccessContext


class FeedbackCommandService:
    def __init__(
        self,
        session: Session,
        *,
        event_repository: EventRepository,
        feedback_repository: FeedbackRepository,
    ) -> None:
        self._session = session
        self._events = event_repository
        self._feedback = feedback_repository

    def submit_feedback(
        self,
        context: AccessContext,
        event_id: str,
        actual_event_label: str,
        routine: bool,
        created_at: datetime,
    ) -> LearningDecision:
        event = self._events.get(context.tenant_id, event_id).event
        memory = self._feedback.current_memory(
            context.tenant_id,
            event.resident_id,
        )
        existing_decision = self._feedback.find_by_event(
            context.tenant_id,
            event_id,
        )
        service = FeedbackService(
            initial_memories=(memory,) if memory.version > 0 else (),
            initial_decisions=(
                (existing_decision,) if existing_decision is not None else ()
            ),
        )
        try:
            decision = service.submit_feedback(
                event=event,
                actor_id=context.actor_id,
                actual_event_label=actual_event_label,
                routine=routine,
                created_at=created_at,
            )
        except ValueError as error:
            raise InvalidTransitionError() from error

        if existing_decision is None:
            self._feedback.save_decision(context.tenant_id, decision)
            self._append_audit(context, decision)
            saved_decision = self._feedback.find_by_event(
                context.tenant_id,
                event_id,
            )
            if saved_decision is None:
                raise RuntimeError("saved feedback decision is unavailable")
            return saved_decision
        return decision

    def _append_audit(
        self,
        context: AccessContext,
        decision: LearningDecision,
    ) -> None:
        feedback = decision.feedback
        self._session.add(
            AuditLogRow(
                tenant_id=context.tenant_id,
                actor_id=context.actor_id,
                action="feedback.submitted",
                target_type="feedback_record",
                target_id=feedback.feedback_id,
                occurred_at=feedback.created_at,
                details={
                    "event_id": feedback.event_id,
                    "resident_id": feedback.resident_id,
                    "outcome": feedback.outcome.value,
                    "actual_event_label": feedback.actual_event_label,
                    "routine": feedback.routine,
                    "memory_version": decision.memory.version,
                    "memory_updated": decision.memory_updated,
                    "baseline_window_eligible": (
                        decision.baseline_window_eligible
                    ),
                    "global_label_recorded": decision.global_label_recorded,
                },
            )
        )
        self._session.flush()
