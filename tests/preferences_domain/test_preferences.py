from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.domain.preferences import (
    AwarenessDeliveryPreferences,
    EventDeliveryPreferences,
    ResidentNotificationPreferences,
    update_notification_preferences,
)


STARTED_AT = datetime(2026, 8, 25, 15, 0, tzinfo=timezone.utc)


def _event_delivery(
    *,
    watch: bool = False,
    high: bool = True,
    critical: bool = True,
) -> EventDeliveryPreferences:
    return EventDeliveryPreferences(
        watch=watch,
        high=high,
        critical=critical,
    )


def _awareness_delivery() -> AwarenessDeliveryPreferences:
    return AwarenessDeliveryPreferences(
        away=True,
        return_=True,
        limited=False,
        unavailable=True,
    )


def _create_preferences():
    return update_notification_preferences(
        current=None,
        resident_id="resident_demo_a",
        expected_version=0,
        event_delivery=_event_delivery(),
        awareness_delivery=_awareness_delivery(),
        actor_id="operator_1",
        changed_at=STARTED_AT,
    )


def test_first_preference_update_requires_expected_version_zero() -> None:
    created = _create_preferences()

    assert created.resident_id == "resident_demo_a"
    assert created.version == 1
    assert created.changed_by == "operator_1"
    assert created.changed_at == STARTED_AT

    with pytest.raises(ValueError, match="expected_version"):
        update_notification_preferences(
            current=None,
            resident_id="resident_demo_a",
            expected_version=1,
            event_delivery=_event_delivery(),
            awareness_delivery=_awareness_delivery(),
            actor_id="operator_1",
            changed_at=STARTED_AT,
        )


def test_preference_update_uses_current_version_without_mutating_history() -> None:
    first = _create_preferences()

    second = update_notification_preferences(
        current=first,
        resident_id="resident_demo_a",
        expected_version=1,
        event_delivery=_event_delivery(watch=True, high=False, critical=False),
        awareness_delivery=AwarenessDeliveryPreferences(
            away=False,
            return_=False,
            limited=True,
            unavailable=False,
        ),
        actor_id="operator_2",
        changed_at=STARTED_AT + timedelta(minutes=5),
    )

    assert second.version == 2
    assert second.event_delivery.watch is True
    assert second.event_delivery.high is False
    assert first.version == 1
    assert first.event_delivery.watch is False
    with pytest.raises(FrozenInstanceError):
        first.version = 9  # type: ignore[misc]


def test_stale_preference_update_cannot_overwrite_current_choice() -> None:
    current = update_notification_preferences(
        current=_create_preferences(),
        resident_id="resident_demo_a",
        expected_version=1,
        event_delivery=_event_delivery(watch=True),
        awareness_delivery=_awareness_delivery(),
        actor_id="operator_2",
        changed_at=STARTED_AT + timedelta(minutes=5),
    )

    with pytest.raises(ValueError, match="expected_version"):
        update_notification_preferences(
            current=current,
            resident_id="resident_demo_a",
            expected_version=1,
            event_delivery=_event_delivery(watch=False),
            awareness_delivery=_awareness_delivery(),
            actor_id="operator_3",
            changed_at=STARTED_AT + timedelta(minutes=10),
        )

    assert current.version == 2
    assert current.event_delivery.watch is True


def test_preference_history_cannot_move_backward_in_time() -> None:
    first = _create_preferences()

    with pytest.raises(ValueError, match="changed_at"):
        update_notification_preferences(
            current=first,
            resident_id="resident_demo_a",
            expected_version=1,
            event_delivery=_event_delivery(),
            awareness_delivery=_awareness_delivery(),
            actor_id="operator_2",
            changed_at=STARTED_AT - timedelta(seconds=1),
        )


@pytest.mark.parametrize("invalid", (1, 0, "yes", None))
def test_preference_delivery_choices_require_strict_booleans(invalid: object) -> None:
    with pytest.raises(ValueError, match="boolean"):
        EventDeliveryPreferences(
            watch=invalid,  # type: ignore[arg-type]
            high=True,
            critical=True,
        )
    with pytest.raises(ValueError, match="boolean"):
        AwarenessDeliveryPreferences(
            away=True,
            return_=invalid,  # type: ignore[arg-type]
            limited=False,
            unavailable=True,
        )


def test_delivery_toggles_never_change_high_critical_dashboard_visibility() -> None:
    hidden_delivery = update_notification_preferences(
        current=None,
        resident_id="resident_demo_a",
        expected_version=0,
        event_delivery=_event_delivery(high=False, critical=False),
        awareness_delivery=_awareness_delivery(),
        actor_id="operator_1",
        changed_at=STARTED_AT,
    )

    assert hidden_delivery.event_delivery.high is False
    assert hidden_delivery.event_delivery.critical is False
    assert hidden_delivery.high_critical_dashboard_visibility == "always_visible"


def test_preference_update_rejects_invalid_product_values() -> None:
    with pytest.raises(ValueError, match="resident_id"):
        update_notification_preferences(
            current=None,
            resident_id="   ",
            expected_version=0,
            event_delivery=_event_delivery(),
            awareness_delivery=_awareness_delivery(),
            actor_id="operator_1",
            changed_at=STARTED_AT,
        )
    with pytest.raises(ValueError, match="expected_version"):
        update_notification_preferences(
            current=None,
            resident_id="resident_demo_a",
            expected_version=True,  # type: ignore[arg-type]
            event_delivery=_event_delivery(),
            awareness_delivery=_awareness_delivery(),
            actor_id="operator_1",
            changed_at=STARTED_AT,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        update_notification_preferences(
            current=None,
            resident_id="resident_demo_a",
            expected_version=0,
            event_delivery=_event_delivery(),
            awareness_delivery=_awareness_delivery(),
            actor_id="operator_1",
            changed_at=datetime(2026, 8, 25, 15, 0),
        )


@pytest.mark.parametrize(
    "change",
    (
        {"resident_id": "   "},
        {"version": 0},
        {"version": True},
        {"event_delivery": {"watch": True}},
        {"awareness_delivery": {"away": True}},
        {"changed_by": "   "},
        {"changed_at": datetime(2026, 8, 25, 15, 0)},
    ),
)
def test_hydrated_preference_snapshot_rejects_invalid_domain_values(
    change: dict[str, object],
) -> None:
    values = {
        "resident_id": "resident_demo_a",
        "version": 1,
        "event_delivery": _event_delivery(),
        "awareness_delivery": _awareness_delivery(),
        "changed_by": "operator_1",
        "changed_at": STARTED_AT,
    }

    with pytest.raises(ValueError):
        ResidentNotificationPreferences(**{**values, **change})  # type: ignore[arg-type]
