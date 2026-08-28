from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.mappers import event_to_rows
from backend.app.db.models import ResidentRow, RoomRow, TenantRow
from backend.app.db.repositories import EventQueuePage, EventRepository
from backend.app.db.session import create_engine_for_url
from backend.app.domain.events import (
    EventAction,
    EventActionType,
    EventPriority,
    EventPriorityHistoryEntry,
    EventStatus,
    MonitoringEvent,
    ResolutionOutcome,
)


STARTED_AT = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
EXPECTED_QUEUE_ORDER = [
    "evt_critical_overdue",
    "evt_critical_fresh",
    "evt_high_overdue",
    "evt_watch_newer",
    "evt_watch_tie_a",
    "evt_watch_tie_b",
    "evt_watch_older_created",
    "evt_resolved_critical",
]


@pytest.fixture
def session() -> Session:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        database_session.add_all(
            [TenantRow(tenant_id="tenant_a"), TenantRow(tenant_id="tenant_b")]
        )
        database_session.flush()
        database_session.add_all(
            [
                RoomRow(room_id="room_a", tenant_id="tenant_a", label="Room A"),
                RoomRow(room_id="room_b", tenant_id="tenant_a", label="Room B"),
                RoomRow(
                    room_id="room_other",
                    tenant_id="tenant_b",
                    label="Room Other",
                ),
                ResidentRow(
                    resident_id="resident_a",
                    tenant_id="tenant_a",
                    display_label="Resident A",
                ),
                ResidentRow(
                    resident_id="resident_b",
                    tenant_id="tenant_a",
                    display_label="Resident B",
                ),
                ResidentRow(
                    resident_id="resident_other",
                    tenant_id="tenant_b",
                    display_label="Resident Other",
                ),
            ]
        )
        database_session.flush()
        _seed_queue(database_session)
        database_session.commit()
        yield database_session
    engine.dispose()


def _add_event(
    session: Session,
    *,
    event_id: str,
    tenant_id: str = "tenant_a",
    resident_id: str = "resident_a",
    room_id: str = "room_a",
    priority: EventPriority,
    status: EventStatus,
    created_minute: int,
    last_signal_minute: int,
    overdue: bool,
) -> None:
    created_at = STARTED_AT + timedelta(minutes=created_minute)
    last_signal_at = STARTED_AT + timedelta(minutes=last_signal_minute)
    domain_event = MonitoringEvent(
        event_id=event_id,
        episode_id=f"episode_{event_id}",
        resident_id=resident_id,
        room_id=room_id,
        objective_family="unusual_movement",
        headline=f"Synthetic queue event {event_id}",
        priority=priority,
        status=status,
        created_at=created_at,
        last_signal_at=last_signal_at,
        overdue_at=(last_signal_at + timedelta(minutes=1) if overdue else None),
        resolution_outcome=(
            ResolutionOutcome.CONFIRMED
            if status is EventStatus.RESOLVED
            else None
        ),
        action_history=(
            EventAction(
                action=EventActionType.OPENED,
                actor_id="system:monitoring_event",
                occurred_at=created_at,
                previous_status=EventStatus.DETECTED,
                status=EventStatus.OPEN,
            ),
        ),
        priority_history=(
            EventPriorityHistoryEntry(
                previous_priority=None,
                priority=priority,
                actor_id="system:monitoring_event",
                changed_at=created_at,
            ),
        ),
    )
    bundle = event_to_rows(tenant_id, domain_event, version=1)
    session.add(bundle.event)
    session.flush()
    session.add_all(bundle.actions)
    session.add_all(bundle.priorities)
    session.flush()


def _seed_queue(session: Session) -> None:
    _add_event(
        session,
        event_id="evt_critical_overdue",
        priority=EventPriority.CRITICAL,
        status=EventStatus.OPEN,
        created_minute=0,
        last_signal_minute=10,
        overdue=True,
    )
    _add_event(
        session,
        event_id="evt_critical_fresh",
        priority=EventPriority.CRITICAL,
        status=EventStatus.ACKNOWLEDGED,
        created_minute=1,
        last_signal_minute=20,
        overdue=False,
    )
    _add_event(
        session,
        event_id="evt_high_overdue",
        priority=EventPriority.HIGH,
        status=EventStatus.CHECKED,
        created_minute=2,
        last_signal_minute=30,
        overdue=True,
    )
    _add_event(
        session,
        event_id="evt_watch_newer",
        resident_id="resident_b",
        room_id="room_b",
        priority=EventPriority.WATCH,
        status=EventStatus.OPEN,
        created_minute=4,
        last_signal_minute=50,
        overdue=False,
    )
    for event_id in ("evt_watch_tie_a", "evt_watch_tie_b"):
        _add_event(
            session,
            event_id=event_id,
            priority=EventPriority.WATCH,
            status=EventStatus.OPEN,
            created_minute=3,
            last_signal_minute=40,
            overdue=False,
        )
    _add_event(
        session,
        event_id="evt_watch_older_created",
        priority=EventPriority.WATCH,
        status=EventStatus.OPEN,
        created_minute=2,
        last_signal_minute=40,
        overdue=False,
    )
    _add_event(
        session,
        event_id="evt_resolved_critical",
        priority=EventPriority.CRITICAL,
        status=EventStatus.RESOLVED,
        created_minute=5,
        last_signal_minute=100,
        overdue=True,
    )
    _add_event(
        session,
        event_id="evt_other_tenant",
        tenant_id="tenant_b",
        resident_id="resident_other",
        room_id="room_other",
        priority=EventPriority.CRITICAL,
        status=EventStatus.OPEN,
        created_minute=6,
        last_signal_minute=200,
        overdue=True,
    )


def _ids(page: EventQueuePage) -> list[str]:
    return [stored.event.event_id for stored in page.items]


def test_clinic_queue_is_tenant_scoped_and_uses_product_order(
    session: Session,
) -> None:
    page = EventRepository(session).list_for_tenant("tenant_a", limit=20)

    assert _ids(page) == EXPECTED_QUEUE_ORDER
    assert page.total_items == 8
    assert page.next_position is None


def test_clinic_queue_combines_filter_categories_with_documented_boolean_logic(
    session: Session,
) -> None:
    page = EventRepository(session).list_for_tenant(
        "tenant_a",
        statuses=(EventStatus.OPEN, EventStatus.CHECKED),
        priorities=(EventPriority.CRITICAL, EventPriority.HIGH),
        resident_id="resident_a",
        room_id="room_a",
        limit=20,
    )

    assert _ids(page) == ["evt_critical_overdue", "evt_high_overdue"]
    assert page.total_items == 2


@pytest.mark.parametrize(
    ("resident_id", "room_id"),
    (
        ("resident_missing", None),
        ("resident_other", None),
        (None, "room_missing"),
        (None, "room_other"),
    ),
)
def test_missing_and_cross_tenant_filter_ids_return_an_empty_page(
    session: Session,
    resident_id: str | None,
    room_id: str | None,
) -> None:
    page = EventRepository(session).list_for_tenant(
        "tenant_a",
        resident_id=resident_id,
        room_id=room_id,
        limit=20,
    )

    assert page.items == ()
    assert page.total_items == 0
    assert page.next_position is None


def test_keyset_pages_cover_matching_events_once_in_stable_order(
    session: Session,
) -> None:
    repository = EventRepository(session)
    seen: list[str] = []
    position = None
    totals: list[int] = []

    while True:
        page = repository.list_for_tenant(
            "tenant_a",
            limit=2,
            after=position,
        )
        seen.extend(_ids(page))
        totals.append(page.total_items)
        position = page.next_position
        if position is None:
            break

    assert seen == EXPECTED_QUEUE_ORDER
    assert len(seen) == len(set(seen))
    assert totals == [8, 8, 8, 8]


def test_queue_page_batch_hydrates_complete_event_histories(
    session: Session,
) -> None:
    select_count = 0

    def count_selects(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        nonlocal select_count
        if statement.lstrip().casefold().startswith("select"):
            select_count += 1

    engine = session.get_bind()
    sqlalchemy_event.listen(engine, "before_cursor_execute", count_selects)
    try:
        page = EventRepository(session).list_for_tenant("tenant_a", limit=5)
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", count_selects)

    assert len(page.items) == 5
    assert all(len(stored.event.action_history) == 1 for stored in page.items)
    assert all(len(stored.event.priority_history) == 1 for stored in page.items)
    assert select_count == 4
