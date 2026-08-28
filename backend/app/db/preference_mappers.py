"""Mappings for append-only resident notification preference versions."""

from datetime import datetime, timezone

from backend.app.db.models import ResidentNotificationPreferenceVersionRow
from backend.app.domain.preferences import (
    AwarenessDeliveryPreferences,
    EventDeliveryPreferences,
    ResidentNotificationPreferences,
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def preference_to_row(
    tenant_id: str,
    preferences: ResidentNotificationPreferences,
) -> ResidentNotificationPreferenceVersionRow:
    return ResidentNotificationPreferenceVersionRow(
        tenant_id=tenant_id,
        resident_id=preferences.resident_id,
        version=preferences.version,
        watch_delivery_enabled=preferences.event_delivery.watch,
        high_delivery_enabled=preferences.event_delivery.high,
        critical_delivery_enabled=preferences.event_delivery.critical,
        away_awareness_enabled=preferences.awareness_delivery.away,
        return_awareness_enabled=preferences.awareness_delivery.return_,
        limited_awareness_enabled=preferences.awareness_delivery.limited,
        unavailable_awareness_enabled=preferences.awareness_delivery.unavailable,
        changed_by=preferences.changed_by,
        changed_at=_utc(preferences.changed_at),
    )


def preference_from_row(
    row: ResidentNotificationPreferenceVersionRow,
) -> ResidentNotificationPreferences:
    return ResidentNotificationPreferences(
        resident_id=row.resident_id,
        version=row.version,
        event_delivery=EventDeliveryPreferences(
            watch=row.watch_delivery_enabled,
            high=row.high_delivery_enabled,
            critical=row.critical_delivery_enabled,
        ),
        awareness_delivery=AwarenessDeliveryPreferences(
            away=row.away_awareness_enabled,
            return_=row.return_awareness_enabled,
            limited=row.limited_awareness_enabled,
            unavailable=row.unavailable_awareness_enabled,
        ),
        changed_by=row.changed_by,
        changed_at=_utc(row.changed_at),
    )


__all__ = ["preference_from_row", "preference_to_row"]
