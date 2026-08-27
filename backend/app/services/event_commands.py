"""Tenant-scoped caregiver commands backed by the event domain aggregate."""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.db.mappers import StoredEvent
from backend.app.db.models import AuditLogRow
from backend.app.db.repositories import EventRepository
from backend.app.domain.events import (
    EventAction,
    EventStore,
    MonitoringEvent,
    ResolutionOutcome,
)
from backend.app.services.errors import InvalidTransitionError
from backend.app.services.queries import AccessContext


class EventCommandService:
    def __init__(self, session: Session, event_repository: EventRepository) -> None:
        self._session = session
        self._events = event_repository

    def acknowledge(
        self,
        context: AccessContext,
        event_id: str,
        occurred_at: datetime,
    ) -> StoredEvent:
        return self._transition(
            context,
            event_id,
            lambda store: store.acknowledge(
                event_id,
                actor_id=context.actor_id,
                at=occurred_at,
            ),
        )

    def check(
        self,
        context: AccessContext,
        event_id: str,
        occurred_at: datetime,
    ) -> StoredEvent:
        return self._transition(
            context,
            event_id,
            lambda store: store.check(
                event_id,
                actor_id=context.actor_id,
                at=occurred_at,
            ),
        )

    def resolve(
        self,
        context: AccessContext,
        event_id: str,
        occurred_at: datetime,
        outcome: ResolutionOutcome,
    ) -> StoredEvent:
        return self._transition(
            context,
            event_id,
            lambda store: store.resolve(
                event_id,
                outcome,
                actor_id=context.actor_id,
                at=occurred_at,
            ),
        )

    def _transition(
        self,
        context: AccessContext,
        event_id: str,
        transition: Callable[[EventStore], MonitoringEvent],
    ) -> StoredEvent:
        stored = self._events.get(context.tenant_id, event_id)
        try:
            event = transition(EventStore(initial_events=(stored.event,)))
        except ValueError as error:
            raise InvalidTransitionError() from error

        saved = self._events.save(
            context.tenant_id,
            event,
            expected_version=stored.version,
        )
        self._append_audit(context, saved, saved.event.action_history[-1])
        return saved

    def _append_audit(
        self,
        context: AccessContext,
        stored: StoredEvent,
        action: EventAction,
    ) -> None:
        self._session.add(
            AuditLogRow(
                tenant_id=context.tenant_id,
                actor_id=context.actor_id,
                action=f"event.{action.action.value}",
                target_type="monitoring_event",
                target_id=stored.event.event_id,
                occurred_at=action.occurred_at,
                details={
                    "previous_status": action.previous_status.value,
                    "status": action.status.value,
                    "resolution_outcome": (
                        None
                        if action.resolution_outcome is None
                        else action.resolution_outcome.value
                    ),
                    "version": stored.version,
                },
            )
        )
        self._session.flush()
