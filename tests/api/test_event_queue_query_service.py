from datetime import datetime, timezone

import pytest

from backend.app.contracts.events import ClinicEventStatus
from backend.app.db.repositories import EventQueuePosition
from backend.app.domain.events import EventPriority
from backend.app.services.errors import InvalidInputError
from backend.app.services.event_queue import (
    EventQueueQuery,
    decode_event_queue_cursor,
    encode_event_queue_cursor,
    normalize_event_queue_query,
)


def _position() -> EventQueuePosition:
    return EventQueuePosition(
        resolved=False,
        priority=EventPriority.HIGH,
        overdue=True,
        last_signal_at=datetime(2026, 8, 24, 21, 2, 11, tzinfo=timezone.utc),
        created_at=datetime(2026, 8, 24, 21, 0, tzinfo=timezone.utc),
        event_id="evt_cursor",
    )


def test_query_defaults_to_active_work_and_normalizes_repeated_filters() -> None:
    default = normalize_event_queue_query(EventQueueQuery())
    filtered = normalize_event_queue_query(
        EventQueueQuery(
            statuses=(
                ClinicEventStatus.RESOLVED,
                ClinicEventStatus.OPEN,
                ClinicEventStatus.RESOLVED,
            ),
            priorities=(
                EventPriority.WATCH,
                EventPriority.CRITICAL,
                EventPriority.WATCH,
            ),
            resident_id=" resident_a ",
            room_id=" room_a ",
            limit=100,
        )
    )

    assert default.statuses == (
        ClinicEventStatus.OPEN,
        ClinicEventStatus.ACKNOWLEDGED,
        ClinicEventStatus.CHECKED,
    )
    assert filtered.statuses == (
        ClinicEventStatus.OPEN,
        ClinicEventStatus.RESOLVED,
    )
    assert filtered.priorities == (
        EventPriority.CRITICAL,
        EventPriority.WATCH,
    )
    assert filtered.resident_id == "resident_a"
    assert filtered.room_id == "room_a"


@pytest.mark.parametrize(
    ("query", "field"),
    (
        (EventQueueQuery(resident_id=" "), "resident_id"),
        (EventQueueQuery(room_id=" "), "room_id"),
        (EventQueueQuery(limit=0), "limit"),
        (EventQueueQuery(limit=101), "limit"),
    ),
)
def test_query_rejects_invalid_direct_service_inputs(
    query: EventQueueQuery,
    field: str,
) -> None:
    with pytest.raises(InvalidInputError) as error:
        normalize_event_queue_query(query)

    assert error.value.field == field


def test_cursor_round_trip_is_opaque_and_filter_bound() -> None:
    query = normalize_event_queue_query(
        EventQueueQuery(
            statuses=(ClinicEventStatus.OPEN, ClinicEventStatus.CHECKED),
            priorities=(EventPriority.HIGH,),
            resident_id="resident_a",
            limit=25,
        )
    )

    cursor = encode_event_queue_cursor(query, _position())

    assert "evt_cursor" not in cursor
    assert decode_event_queue_cursor(cursor, query) == _position()

    changed_filter = normalize_event_queue_query(
        EventQueueQuery(
            statuses=query.statuses,
            priorities=(EventPriority.CRITICAL,),
            resident_id=query.resident_id,
            limit=query.limit,
        )
    )
    with pytest.raises(InvalidInputError) as error:
        decode_event_queue_cursor(cursor, changed_filter)
    assert error.value.field == "cursor"


@pytest.mark.parametrize("cursor", ("", "not json", "%%%%", "e30"))
def test_cursor_rejects_malformed_values(cursor: str) -> None:
    query = normalize_event_queue_query(EventQueueQuery())

    with pytest.raises(InvalidInputError) as error:
        decode_event_queue_cursor(cursor, query)

    assert error.value.field == "cursor"

