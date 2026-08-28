"""Immutable resident notification and awareness preference rules."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from backend.app.domain._validation import (
    require_aware_datetime,
    require_nonblank_text,
    require_strict_bool,
)


DashboardVisibility = Literal["always_visible"]


@dataclass(frozen=True)
class EventDeliveryPreferences:
    watch: bool
    high: bool
    critical: bool
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        require_strict_bool(self.watch, "watch")
        require_strict_bool(self.high, "high")
        require_strict_bool(self.critical, "critical")


@dataclass(frozen=True)
class AwarenessDeliveryPreferences:
    away: bool
    return_: bool
    limited: bool
    unavailable: bool
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        require_strict_bool(self.away, "away")
        require_strict_bool(self.return_, "return")
        require_strict_bool(self.limited, "limited")
        require_strict_bool(self.unavailable, "unavailable")


@dataclass(frozen=True)
class ResidentNotificationPreferences:
    resident_id: str
    version: int
    event_delivery: EventDeliveryPreferences
    awareness_delivery: AwarenessDeliveryPreferences
    changed_by: str
    changed_at: datetime
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        require_nonblank_text(self.resident_id, "resident_id")
        if (
            isinstance(self.version, bool)
            or not isinstance(self.version, int)
            or self.version < 1
        ):
            raise ValueError("version must be a positive integer")
        if type(self.event_delivery) is not EventDeliveryPreferences:
            raise ValueError("event_delivery must be EventDeliveryPreferences")
        if type(self.awareness_delivery) is not AwarenessDeliveryPreferences:
            raise ValueError(
                "awareness_delivery must be AwarenessDeliveryPreferences"
            )
        require_nonblank_text(self.changed_by, "changed_by")
        require_aware_datetime(self.changed_at, "changed_at")

    @property
    def high_critical_dashboard_visibility(self) -> DashboardVisibility:
        return "always_visible"


def _require_expected_version(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("expected_version must be a nonnegative integer")
    return value


def update_notification_preferences(
    *,
    current: ResidentNotificationPreferences | None,
    resident_id: str,
    expected_version: int,
    event_delivery: EventDeliveryPreferences,
    awareness_delivery: AwarenessDeliveryPreferences,
    actor_id: str,
    changed_at: datetime,
) -> ResidentNotificationPreferences:
    """Create the next preference version after validating its current view."""

    resident_id = require_nonblank_text(resident_id, "resident_id")
    actor_id = require_nonblank_text(actor_id, "actor_id")
    expected_version = _require_expected_version(expected_version)
    changed_at = require_aware_datetime(changed_at, "changed_at")
    if not isinstance(event_delivery, EventDeliveryPreferences):
        raise ValueError("event_delivery must be EventDeliveryPreferences")
    if not isinstance(awareness_delivery, AwarenessDeliveryPreferences):
        raise ValueError(
            "awareness_delivery must be AwarenessDeliveryPreferences"
        )

    current_version = 0 if current is None else current.version
    if current is not None:
        if current.resident_id != resident_id:
            raise ValueError("current preferences must belong to resident_id")
        if changed_at < current.changed_at:
            raise ValueError("changed_at cannot precede preference history")
    if expected_version != current_version:
        raise ValueError("expected_version does not match current version")

    return ResidentNotificationPreferences(
        resident_id=resident_id,
        version=current_version + 1,
        event_delivery=event_delivery,
        awareness_delivery=awareness_delivery,
        changed_by=actor_id,
        changed_at=changed_at,
    )
