"""Tenant-scoped append-only resident notification preference history."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db.models import (
    ResidentNotificationPreferenceVersionRow,
    ResidentRow,
)
from backend.app.db.preference_mappers import preference_from_row, preference_to_row
from backend.app.domain.preferences import ResidentNotificationPreferences
from backend.app.services.errors import ConcurrentUpdateError, NotFoundError


def _is_version_conflict(error: IntegrityError) -> bool:
    constraint_name = getattr(
        getattr(error.orig, "diag", None),
        "constraint_name",
        None,
    )
    if constraint_name == "uq_resident_preference_version":
        return True
    return (
        "unique constraint failed: "
        "resident_notification_preference_versions.tenant_id, "
        "resident_notification_preference_versions.resident_id, "
        "resident_notification_preference_versions.version"
    ) in str(error.orig).casefold()


class NotificationPreferenceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def current(
        self,
        tenant_id: str,
        resident_id: str,
    ) -> ResidentNotificationPreferences | None:
        row = self._session.scalar(
            select(ResidentNotificationPreferenceVersionRow)
            .where(
                ResidentNotificationPreferenceVersionRow.tenant_id == tenant_id,
                ResidentNotificationPreferenceVersionRow.resident_id == resident_id,
            )
            .order_by(
                ResidentNotificationPreferenceVersionRow.version.desc(),
                ResidentNotificationPreferenceVersionRow.preference_version_id.desc(),
            )
            .limit(1)
        )
        return None if row is None else preference_from_row(row)

    def timeline(
        self,
        tenant_id: str,
        resident_id: str,
    ) -> list[ResidentNotificationPreferences]:
        rows = self._session.scalars(
            select(ResidentNotificationPreferenceVersionRow)
            .where(
                ResidentNotificationPreferenceVersionRow.tenant_id == tenant_id,
                ResidentNotificationPreferenceVersionRow.resident_id == resident_id,
            )
            .order_by(
                ResidentNotificationPreferenceVersionRow.version,
                ResidentNotificationPreferenceVersionRow.preference_version_id,
            )
        ).all()
        return [preference_from_row(row) for row in rows]

    def save(
        self,
        tenant_id: str,
        preferences: ResidentNotificationPreferences,
        *,
        expected_version: int,
    ) -> ResidentNotificationPreferences:
        resident_exists = self._session.scalar(
            select(ResidentRow.resident_id).where(
                ResidentRow.tenant_id == tenant_id,
                ResidentRow.resident_id == preferences.resident_id,
            )
        )
        if resident_exists is None:
            raise NotFoundError()

        current = self.current(tenant_id, preferences.resident_id)
        actual_version = 0 if current is None else current.version
        if (
            actual_version != expected_version
            or preferences.version != expected_version + 1
        ):
            raise ConcurrentUpdateError()

        row = preference_to_row(tenant_id, preferences)
        self._session.add(row)
        try:
            self._session.flush((row,))
        except IntegrityError as error:
            if _is_version_conflict(error):
                raise ConcurrentUpdateError() from error
            raise
        saved = self.current(tenant_id, preferences.resident_id)
        if saved is None:
            raise RuntimeError("saved notification preferences are unavailable")
        return saved


__all__ = ["NotificationPreferenceRepository"]
