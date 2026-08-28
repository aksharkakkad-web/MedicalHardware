"""Resident preference and semantic-memory reads and commands."""

from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.contracts.feedback import MemoryEntryResponse, ResidentMemoryResponse
from backend.app.contracts.preferences import (
    AwarenessDeliveryPreferences as AwarenessDeliveryContract,
    EventDeliveryPreferences as EventDeliveryContract,
    ResidentNotificationPreferencesResponse,
)
from backend.app.db.models import AuditLogRow
from backend.app.db.preference_repositories import NotificationPreferenceRepository
from backend.app.db.repositories import FeedbackRepository, ResidentRepository
from backend.app.domain.feedback import ResidentMemory, ResidentMemoryService
from backend.app.domain.preferences import (
    AwarenessDeliveryPreferences,
    EventDeliveryPreferences,
    ResidentNotificationPreferences,
    update_notification_preferences,
)
from backend.app.services.errors import (
    ConcurrentUpdateError,
    InvalidTransitionError,
    NotFoundError,
)
from backend.app.services.queries import AccessContext


def notification_preferences_response(
    resident_id: str,
    preferences: ResidentNotificationPreferences | None,
) -> ResidentNotificationPreferencesResponse:
    if preferences is None:
        return ResidentNotificationPreferencesResponse(
            resident_id=resident_id,
            data_availability="not_yet_available",
            version=None,
            event_delivery=None,
            awareness_delivery=None,
            changed_by=None,
            changed_at=None,
        )
    return ResidentNotificationPreferencesResponse(
        resident_id=preferences.resident_id,
        data_availability="available",
        version=preferences.version,
        event_delivery=EventDeliveryContract(
            watch=preferences.event_delivery.watch,
            high=preferences.event_delivery.high,
            critical=preferences.event_delivery.critical,
        ),
        awareness_delivery=AwarenessDeliveryContract.model_validate(
            {
                "away": preferences.awareness_delivery.away,
                "return": preferences.awareness_delivery.return_,
                "limited": preferences.awareness_delivery.limited,
                "unavailable": preferences.awareness_delivery.unavailable,
            }
        ),
        changed_by=preferences.changed_by,
        changed_at=preferences.changed_at,
    )


def resident_memory_response(memory: ResidentMemory) -> ResidentMemoryResponse:
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


class ResidentControlService:
    def __init__(
        self,
        session: Session,
        *,
        residents: ResidentRepository,
        preferences: NotificationPreferenceRepository,
        memory: FeedbackRepository,
    ) -> None:
        self._session = session
        self._residents = residents
        self._preferences = preferences
        self._memory = memory

    def get_preferences(
        self,
        context: AccessContext,
        resident_id: str,
    ) -> ResidentNotificationPreferencesResponse:
        self._require_resident(context, resident_id)
        return notification_preferences_response(
            resident_id,
            self._preferences.current(context.tenant_id, resident_id),
        )

    def update_preferences(
        self,
        context: AccessContext,
        resident_id: str,
        *,
        expected_version: int,
        event_delivery: EventDeliveryPreferences,
        awareness_delivery: AwarenessDeliveryPreferences,
        changed_at: datetime,
    ) -> ResidentNotificationPreferencesResponse:
        self._require_resident(context, resident_id)
        current = self._preferences.current(context.tenant_id, resident_id)
        actual_version = 0 if current is None else current.version
        if actual_version != expected_version:
            raise ConcurrentUpdateError()
        try:
            updated = update_notification_preferences(
                current=current,
                resident_id=resident_id,
                expected_version=expected_version,
                event_delivery=event_delivery,
                awareness_delivery=awareness_delivery,
                actor_id=context.actor_id,
                changed_at=changed_at,
            )
        except ValueError as error:
            raise InvalidTransitionError() from error
        saved = self._preferences.save(
            context.tenant_id,
            updated,
            expected_version=expected_version,
        )
        self._audit_preferences(context, saved)
        return notification_preferences_response(resident_id, saved)

    def add_memory_entry(
        self,
        context: AccessContext,
        resident_id: str,
        *,
        expected_version: int,
        description: str,
        changed_at: datetime,
    ) -> ResidentMemoryResponse:
        current = self._memory_context(context, resident_id, expected_version)
        service = ResidentMemoryService(
            initial_memories=(current,) if current.version > 0 else ()
        )
        try:
            updated = service.add_entry(
                resident_id=resident_id,
                expected_version=expected_version,
                description=description,
                actor_id=context.actor_id,
                changed_at=changed_at,
            )
        except ValueError as error:
            raise InvalidTransitionError() from error
        saved = self._save_memory(
            context,
            updated,
            expected_version=expected_version,
            changed_at=changed_at,
        )
        entry = saved.entries[-1]
        self._audit_memory(
            context,
            resident_id,
            entry.entry_id,
            "resident_memory.entry_added",
            changed_at,
            {"memory_version": saved.version, "description": entry.description},
        )
        return resident_memory_response(saved)

    def correct_memory_entry(
        self,
        context: AccessContext,
        resident_id: str,
        entry_id: str,
        *,
        expected_version: int,
        description: str,
        reason: str,
        changed_at: datetime,
    ) -> ResidentMemoryResponse:
        current = self._memory_context(context, resident_id, expected_version)
        try:
            updated = ResidentMemoryService(
                initial_memories=(current,)
            ).correct_entry(
                resident_id=resident_id,
                entry_id=entry_id,
                expected_version=expected_version,
                description=description,
                reason=reason,
                actor_id=context.actor_id,
                changed_at=changed_at,
            )
        except KeyError as error:
            raise NotFoundError() from error
        except ValueError as error:
            raise InvalidTransitionError() from error
        saved = self._save_memory(
            context,
            updated,
            expected_version=expected_version,
            changed_at=changed_at,
        )
        replacement = saved.entries[-1]
        self._audit_memory(
            context,
            resident_id,
            entry_id,
            "resident_memory.entry_corrected",
            changed_at,
            {
                "memory_version": saved.version,
                "replacement_entry_id": replacement.entry_id,
                "reason": reason,
            },
        )
        return resident_memory_response(saved)

    def retire_memory_entry(
        self,
        context: AccessContext,
        resident_id: str,
        entry_id: str,
        *,
        expected_version: int,
        reason: str,
        changed_at: datetime,
    ) -> ResidentMemoryResponse:
        current = self._memory_context(context, resident_id, expected_version)
        try:
            updated = ResidentMemoryService(
                initial_memories=(current,)
            ).retire_entry(
                resident_id=resident_id,
                entry_id=entry_id,
                expected_version=expected_version,
                reason=reason,
                actor_id=context.actor_id,
                changed_at=changed_at,
            )
        except KeyError as error:
            raise NotFoundError() from error
        except ValueError as error:
            raise InvalidTransitionError() from error
        saved = self._save_memory(
            context,
            updated,
            expected_version=expected_version,
            changed_at=changed_at,
        )
        self._audit_memory(
            context,
            resident_id,
            entry_id,
            "resident_memory.entry_retired",
            changed_at,
            {"memory_version": saved.version, "reason": reason},
        )
        return resident_memory_response(saved)

    def _memory_context(
        self,
        context: AccessContext,
        resident_id: str,
        expected_version: int,
    ) -> ResidentMemory:
        self._require_resident(context, resident_id)
        current = self._memory.current_memory(context.tenant_id, resident_id)
        if current.version != expected_version:
            raise ConcurrentUpdateError()
        return current

    def _save_memory(
        self,
        context: AccessContext,
        memory: ResidentMemory,
        *,
        expected_version: int,
        changed_at: datetime,
    ) -> ResidentMemory:
        return self._memory.save_memory(
            context.tenant_id,
            memory,
            expected_version=expected_version,
            changed_at=changed_at,
        )

    def _require_resident(self, context: AccessContext, resident_id: str) -> None:
        if self._residents.find(context.tenant_id, resident_id) is None:
            raise NotFoundError()

    def _audit_preferences(
        self,
        context: AccessContext,
        saved: ResidentNotificationPreferences,
    ) -> None:
        self._session.add(
            AuditLogRow(
                tenant_id=context.tenant_id,
                actor_id=context.actor_id,
                action="resident.notification_preferences.changed",
                target_type="resident_notification_preferences",
                target_id=saved.resident_id,
                occurred_at=saved.changed_at,
                details={
                    "version": saved.version,
                    "event_delivery": {
                        "watch": saved.event_delivery.watch,
                        "high": saved.event_delivery.high,
                        "critical": saved.event_delivery.critical,
                    },
                    "awareness_delivery": {
                        "away": saved.awareness_delivery.away,
                        "return": saved.awareness_delivery.return_,
                        "limited": saved.awareness_delivery.limited,
                        "unavailable": saved.awareness_delivery.unavailable,
                    },
                    "high_critical_dashboard_visibility": "always_visible",
                },
            )
        )
        self._session.flush()

    def _audit_memory(
        self,
        context: AccessContext,
        resident_id: str,
        entry_id: str,
        action: str,
        changed_at: datetime,
        details: dict[str, object],
    ) -> None:
        self._session.add(
            AuditLogRow(
                tenant_id=context.tenant_id,
                actor_id=context.actor_id,
                action=action,
                target_type="resident_memory_entry",
                target_id=entry_id,
                occurred_at=changed_at,
                details={"resident_id": resident_id, **details},
            )
        )
        self._session.flush()


__all__ = [
    "ResidentControlService",
    "notification_preferences_response",
    "resident_memory_response",
]
