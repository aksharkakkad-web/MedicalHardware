from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.models import (
    EventActionRow,
    EventPriorityHistoryRow,
    RoomResidentAssignmentRow,
    RoomRow,
    TenantRow,
)
from backend.app.db.repositories import EventRepository, FeedbackRepository, ResidentRepository
from backend.app.db.seed import seed_synthetic_story
from backend.app.db.session import create_engine_for_url
from backend.app.domain.events import EventStore, ResolutionOutcome
from backend.app.domain.feedback import FeedbackService
from backend.app.services.errors import ConcurrentUpdateError, NotFoundError


@pytest.fixture
def session() -> Session:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def test_event_round_trip_preserves_full_history(session: Session) -> None:
    story = seed_synthetic_story(session)

    loaded = EventRepository(session).get(story.tenant_id, story.event_id)

    assert loaded.event.event_id == story.event_id
    assert [action.action.value for action in loaded.event.action_history] == ["opened"]
    assert loaded.event.priority_history[0].priority.value == "high"
    assert loaded.event.created_at == datetime(2026, 8, 24, 21, 2, 11, tzinfo=timezone.utc)
    assert loaded.event.created_at.tzinfo is timezone.utc
    assert loaded.version == 1


def test_cross_tenant_repository_lookup_returns_none(session: Session) -> None:
    story = seed_synthetic_story(session)

    assert EventRepository(session).find("tenant_other", story.event_id) is None


def test_event_children_are_filtered_by_tenant(session: Session) -> None:
    story = seed_synthetic_story(session)
    session.add(TenantRow(tenant_id="tenant_other"))
    session.flush()
    session.add(
        EventActionRow(
            tenant_id="tenant_other",
            event_id=story.event_id,
            sequence=2,
            action="acknowledged",
            actor_id="operator_other",
            occurred_at=datetime(2026, 8, 24, 21, 3, tzinfo=timezone.utc),
            previous_status="open",
            status="acknowledged",
            resolution_outcome=None,
        )
    )
    session.add(
        EventPriorityHistoryRow(
            tenant_id="tenant_other",
            event_id=story.event_id,
            sequence=2,
            previous_priority="high",
            priority="critical",
            actor_id="operator_other",
            changed_at=datetime(2026, 8, 24, 21, 3, tzinfo=timezone.utc),
        )
    )
    session.commit()

    loaded = EventRepository(session).get(story.tenant_id, story.event_id)

    assert [action.action.value for action in loaded.event.action_history] == ["opened"]
    assert [item.priority.value for item in loaded.event.priority_history] == ["high"]


def test_resident_reads_filter_every_joined_table_by_tenant(session: Session) -> None:
    story = seed_synthetic_story(session)
    session.add(TenantRow(tenant_id="tenant_other"))
    session.flush()
    session.add(
        RoomResidentAssignmentRow(
            assignment_id="assignment_cross_tenant",
            tenant_id="tenant_other",
            room_id=story.room_id,
            resident_id=story.resident_id,
            status="active",
            effective_from=datetime(2026, 8, 24, tzinfo=timezone.utc),
            effective_to=None,
        )
    )
    session.commit()

    repository = ResidentRepository(session)

    assert repository.list("tenant_other") == []
    assert repository.find("tenant_other", story.resident_id) is None
    assert repository.list(story.tenant_id)[0].room_label == "Room 214"


def test_get_raises_tenant_safe_not_found_error(session: Session) -> None:
    story = seed_synthetic_story(session)

    with pytest.raises(NotFoundError) as error:
        EventRepository(session).get("tenant_other", story.event_id)

    assert story.event_id not in str(error.value)


def test_event_save_appends_only_new_history_and_rejects_stale_version(
    session: Session,
) -> None:
    story = seed_synthetic_story(session)
    repository = EventRepository(session)
    first_reader = repository.get(story.tenant_id, story.event_id)
    stale_reader = repository.get(story.tenant_id, story.event_id)
    acknowledged_at = first_reader.event.created_at + timedelta(minutes=1)
    first_event = EventStore(initial_events=(first_reader.event,)).acknowledge(
        story.event_id,
        actor_id="operator_001",
        at=acknowledged_at,
    )
    stale_event = EventStore(initial_events=(stale_reader.event,)).acknowledge(
        story.event_id,
        actor_id="operator_002",
        at=acknowledged_at,
    )

    saved = repository.save(story.tenant_id, first_event, expected_version=1)

    assert saved.version == 2
    assert [action.action.value for action in saved.event.action_history] == [
        "opened",
        "acknowledged",
    ]
    assert session.scalar(select(func.count()).select_from(EventActionRow)) == 2
    assert session.scalar(select(func.count()).select_from(EventPriorityHistoryRow)) == 1
    session.commit()

    with pytest.raises(ConcurrentUpdateError):
        repository.save(story.tenant_id, stale_event, expected_version=1)

    session.rollback()
    assert session.scalar(select(func.count()).select_from(EventActionRow)) == 2


def test_feedback_round_trip_preserves_memory_and_learning_effects(
    session: Session,
) -> None:
    story = seed_synthetic_story(session)
    event_repository = EventRepository(session)
    loaded = event_repository.get(story.tenant_id, story.event_id)
    event_store = EventStore(initial_events=(loaded.event,))
    at = loaded.event.created_at
    event_store.acknowledge(story.event_id, actor_id="operator_001", at=at + timedelta(minutes=1))
    event_store.check(story.event_id, actor_id="operator_001", at=at + timedelta(minutes=2))
    resolved = event_store.resolve(
        story.event_id,
        ResolutionOutcome.FALSE_POSITIVE,
        actor_id="operator_001",
        at=at + timedelta(minutes=3),
    )
    event_repository.save(story.tenant_id, resolved, expected_version=1)
    decision = FeedbackService().submit_feedback(
        event=resolved,
        actor_id="operator_001",
        actual_event_label="assisted_transfer",
        routine=True,
        created_at=at + timedelta(minutes=4),
    )

    repository = FeedbackRepository(session)
    repository.save_decision(story.tenant_id, decision)
    loaded_decision = repository.find_by_event(story.tenant_id, story.event_id)

    assert loaded_decision == decision
    assert repository.current_memory(story.tenant_id, story.resident_id) == decision.memory
    assert repository.find_by_event("tenant_other", story.event_id) is None


def test_current_memory_uses_latest_complete_snapshot(session: Session) -> None:
    story = seed_synthetic_story(session)
    event_repository = EventRepository(session)
    loaded = event_repository.get(story.tenant_id, story.event_id)
    event_store = EventStore(initial_events=(loaded.event,))
    at = loaded.event.created_at
    event_store.acknowledge(story.event_id, actor_id="operator_001", at=at + timedelta(minutes=1))
    event_store.check(story.event_id, actor_id="operator_001", at=at + timedelta(minutes=2))
    resolved = event_store.resolve(
        story.event_id,
        ResolutionOutcome.FALSE_POSITIVE,
        actor_id="operator_001",
        at=at + timedelta(minutes=3),
    )
    event_repository.save(story.tenant_id, resolved, expected_version=1)
    decision = FeedbackService().submit_feedback(
        event=resolved,
        actor_id="operator_001",
        actual_event_label="assisted_transfer",
        routine=True,
        created_at=at + timedelta(minutes=4),
    )
    repository = FeedbackRepository(session)
    repository.save_decision(story.tenant_id, decision)
    corrected = FeedbackService(initial_memories=(decision.memory,)).correct_memory(
        resident_id=story.resident_id,
        entry_id=decision.memory.entries[0].entry_id,
        actor_id="operator_002",
        reason="Routine ended",
        corrected_at=at + timedelta(days=1),
    )
    from backend.app.db.mappers import memory_to_rows

    bundle = memory_to_rows(story.tenant_id, corrected, at + timedelta(days=1))
    session.add(bundle.snapshot)
    session.add_all(bundle.entries)
    session.commit()

    current = repository.current_memory(story.tenant_id, story.resident_id)

    assert current.version == 2
    assert len(current.entries) == 1
    assert current.entries[0].status == "retired"


def test_missing_memory_is_an_empty_version_zero_snapshot(session: Session) -> None:
    story = seed_synthetic_story(session)

    memory = FeedbackRepository(session).current_memory(
        story.tenant_id,
        story.resident_id,
    )

    assert memory.resident_id == story.resident_id
    assert memory.version == 0
    assert memory.entries == ()
