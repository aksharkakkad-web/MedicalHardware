from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.models import (
    EventActionRow,
    EventPriorityHistoryRow,
    FeedbackRecordRow,
    ResidentMemoryEntryRow,
    ResidentMemorySnapshotRow,
    ResidentRow,
    RoomResidentAssignmentRow,
    RoomRow,
    TenantRow,
)
from backend.app.db.mappers import event_to_rows
from backend.app.db.repositories import EventRepository, FeedbackRepository, ResidentRepository
from backend.app.db.seed import seed_synthetic_story
from backend.app.db.session import create_engine_for_url
from backend.app.domain.events import (
    EventAction,
    EventActionType,
    EventPriority,
    EventPriorityHistoryEntry,
    EventStatus,
    EventStore,
    MonitoringEvent,
    ResolutionOutcome,
)
from backend.app.domain.feedback import (
    FeedbackRecord,
    FeedbackService,
    LearningDecision,
    MemoryEntry,
    ResidentMemory,
)
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
    session.add(RoomRow(room_id="room_other", tenant_id="tenant_other", label="Room Other"))
    session.add(
        ResidentRow(
            resident_id="resident_other",
            tenant_id="tenant_other",
            display_label="Resident Other",
        )
    )
    session.flush()
    session.add(
        RoomResidentAssignmentRow(
            assignment_id="assignment_other",
            tenant_id="tenant_other",
            room_id="room_other",
            resident_id="resident_other",
            status="active",
            effective_from=datetime(2026, 8, 24, tzinfo=timezone.utc),
            effective_to=None,
        )
    )
    session.commit()

    repository = ResidentRepository(session)

    assert [record.resident_id for record in repository.list("tenant_other")] == [
        "resident_other"
    ]
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


def test_stale_memory_version_rejects_feedback_before_success_metadata_persists(
    session: Session,
) -> None:
    story = seed_synthetic_story(session)
    stored = EventRepository(session).get(story.tenant_id, story.event_id)
    second_event = replace(
        stored.event,
        event_id="evt_stale_memory_demo",
        episode_id="episode_stale_memory_demo",
    )
    second_bundle = event_to_rows(story.tenant_id, second_event, version=1)
    session.add(second_bundle.event)
    session.flush()
    session.add_all(second_bundle.actions)
    session.add_all(second_bundle.priorities)
    session.commit()
    decided_at = stored.event.created_at + timedelta(minutes=5)

    def decision(event_id: str, feedback_id: str, entry_id: str) -> LearningDecision:
        feedback = FeedbackRecord(
            feedback_id=feedback_id,
            event_id=event_id,
            resident_id=story.resident_id,
            actor_id="operator_001",
            outcome=ResolutionOutcome.FALSE_POSITIVE,
            actual_event_label="assisted_transfer",
            routine=True,
            created_at=decided_at,
        )
        memory = ResidentMemory(
            resident_id=story.resident_id,
            version=1,
            entries=(
                MemoryEntry(
                    entry_id=entry_id,
                    description="assisted_transfer",
                    source_feedback_id=feedback_id,
                    status="active",
                    created_by="operator_001",
                    created_at=decided_at,
                ),
            ),
        )
        return LearningDecision(feedback, memory, True, True, True)

    repository = FeedbackRepository(session)
    first = decision(story.event_id, "fb_memory_first", "memory_first")
    stale = decision(second_event.event_id, "fb_memory_stale", "memory_stale")
    repository.save_decision(story.tenant_id, first)
    session.commit()

    with pytest.raises(ConcurrentUpdateError):
        repository.save_decision(story.tenant_id, stale)

    assert session.scalar(select(func.count()).select_from(FeedbackRecordRow)) == 1
    assert session.scalar(select(func.count()).select_from(ResidentMemorySnapshotRow)) == 1
    assert session.scalar(select(func.count()).select_from(ResidentMemoryEntryRow)) == 1
    assert repository.find_by_event(story.tenant_id, second_event.event_id) is None


def test_non_utc_event_history_timestamps_round_trip_to_the_same_utc_instants(
    session: Session,
) -> None:
    story = seed_synthetic_story(session)
    local_zone = timezone(timedelta(hours=5, minutes=30))
    created_at = datetime(2026, 8, 25, 2, 32, 11, tzinfo=local_zone)
    priority_changed_at = created_at + timedelta(seconds=30)
    last_signal_at = created_at + timedelta(minutes=1)
    overdue_at = created_at + timedelta(minutes=2)
    event = MonitoringEvent(
        event_id="evt_offset_demo",
        episode_id="episode_offset_demo",
        resident_id=story.resident_id,
        room_id=story.room_id,
        objective_family="unknown_anomaly",
        headline="Synthetic offset timestamp check",
        priority=EventPriority.CRITICAL,
        status=EventStatus.OPEN,
        created_at=created_at,
        last_signal_at=last_signal_at,
        overdue_at=overdue_at,
        action_history=(
            EventAction(
                action=EventActionType.OPENED,
                actor_id="system:monitoring_event",
                occurred_at=created_at,
                previous_status=EventStatus.DETECTED,
                status=EventStatus.OPEN,
            ),
            EventAction(
                action=EventActionType.MARKED_OVERDUE,
                actor_id="system:overdue_policy",
                occurred_at=overdue_at,
                previous_status=EventStatus.OPEN,
                status=EventStatus.OPEN,
            ),
        ),
        priority_history=(
            EventPriorityHistoryEntry(
                previous_priority=None,
                priority=EventPriority.HIGH,
                actor_id="system:monitoring_event",
                changed_at=created_at,
            ),
            EventPriorityHistoryEntry(
                previous_priority=EventPriority.HIGH,
                priority=EventPriority.CRITICAL,
                actor_id="system:monitoring_event",
                changed_at=priority_changed_at,
            ),
        ),
    )
    bundle = event_to_rows(story.tenant_id, event, version=1)
    session.add(bundle.event)
    session.flush()
    session.add_all(bundle.actions)
    session.add_all(bundle.priorities)
    session.commit()

    loaded = EventRepository(session).get(story.tenant_id, event.event_id).event

    assert loaded.created_at == created_at.astimezone(timezone.utc)
    assert loaded.last_signal_at == last_signal_at.astimezone(timezone.utc)
    assert loaded.overdue_at == overdue_at.astimezone(timezone.utc)
    assert [item.occurred_at for item in loaded.action_history] == [
        created_at.astimezone(timezone.utc),
        overdue_at.astimezone(timezone.utc),
    ]
    assert [item.changed_at for item in loaded.priority_history] == [
        created_at.astimezone(timezone.utc),
        priority_changed_at.astimezone(timezone.utc),
    ]
    assert loaded.created_at.tzinfo is timezone.utc


def test_non_utc_feedback_and_memory_timestamps_round_trip_to_utc_instants(
    session: Session,
) -> None:
    story = seed_synthetic_story(session)
    local_zone = timezone(-timedelta(hours=7))
    entry_created_at = datetime(2026, 8, 24, 14, 2, 11, tzinfo=local_zone)
    entry_retired_at = entry_created_at + timedelta(minutes=2)
    feedback_created_at = entry_retired_at + timedelta(minutes=1)
    feedback = FeedbackRecord(
        feedback_id="fb_offset_demo",
        event_id=story.event_id,
        resident_id=story.resident_id,
        actor_id="operator_001",
        outcome=ResolutionOutcome.FALSE_POSITIVE,
        actual_event_label="assisted_transfer",
        routine=True,
        created_at=feedback_created_at,
    )
    memory = ResidentMemory(
        resident_id=story.resident_id,
        version=1,
        entries=(
            MemoryEntry(
                entry_id="memory_offset_demo",
                description="assisted_transfer",
                source_feedback_id=feedback.feedback_id,
                status="retired",
                created_by="operator_001",
                created_at=entry_created_at,
                retired_by="operator_002",
                retired_at=entry_retired_at,
                retirement_reason="Routine ended",
            ),
        ),
    )
    decision = LearningDecision(feedback, memory, True, True, True)

    repository = FeedbackRepository(session)
    repository.save_decision(story.tenant_id, decision)
    session.commit()
    loaded = repository.find_by_event(story.tenant_id, story.event_id)
    snapshot = session.scalar(select(ResidentMemorySnapshotRow))

    assert loaded is not None
    assert loaded.feedback.created_at == feedback_created_at.astimezone(timezone.utc)
    assert loaded.memory.entries[0].created_at == entry_created_at.astimezone(timezone.utc)
    assert loaded.memory.entries[0].retired_at == entry_retired_at.astimezone(timezone.utc)
    assert loaded.feedback.created_at.tzinfo is timezone.utc
    assert loaded.memory.entries[0].created_at.tzinfo is timezone.utc
    assert loaded.memory.entries[0].retired_at.tzinfo is timezone.utc
    assert snapshot is not None
    assert snapshot.created_at.replace(tzinfo=timezone.utc) == (
        feedback_created_at.astimezone(timezone.utc)
    )
