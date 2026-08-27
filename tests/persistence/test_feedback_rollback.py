from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.mappers import (
    StoredEvent,
    event_to_rows,
    feedback_to_row,
    memory_to_rows,
)
from backend.app.db.models import (
    AuditLogRow,
    FeedbackRecordRow,
    IdempotencyRecordRow,
    ResidentMemoryEntryRow,
    ResidentMemorySnapshotRow,
)
from backend.app.db.repositories import EventRepository, FeedbackRepository
from backend.app.db.seed import seed_synthetic_story
from backend.app.db.session import create_engine_for_url
from backend.app.domain.events import EventStore, ResolutionOutcome
from backend.app.domain.feedback import (
    FeedbackService,
    LearningDecision,
    ResidentMemory,
)
from backend.app.services.errors import ConcurrentUpdateError
from backend.app.services.feedback_commands import FeedbackCommandService
from backend.app.services.queries import AccessContext


def _versioned(body: dict[str, object]) -> dict[str, object]:
    return {"schema_version": "1.0", **body}


class FaultingFeedbackRepository(FeedbackRepository):
    """Stage the feedback row, then fail at the memory persistence boundary."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._fault_session = session

    def save_decision(
        self,
        tenant_id: str,
        decision: LearningDecision,
    ) -> None:
        self._fault_session.add(feedback_to_row(tenant_id, decision))
        self._fault_session.flush()
        raise RuntimeError("synthetic persistence failure")


class CoordinatedFeedbackRepository(FeedbackRepository):
    """Give two commands the same memory view before real persistence."""

    def __init__(self, session: Session, memory_barrier: Barrier) -> None:
        super().__init__(session)
        self._memory_barrier = memory_barrier
        self._memory_reads = 0

    def current_memory(
        self,
        tenant_id: str,
        resident_id: str,
    ) -> ResidentMemory:
        self._memory_reads += 1
        if self._memory_reads == 1:
            self._memory_barrier.wait(timeout=5)
            return ResidentMemory(resident_id, 0, ())
        return super().current_memory(tenant_id, resident_id)


class HydratedDecisionFeedbackRepository(FeedbackRepository):
    """Expose a memory advance between the command's potential reads."""

    def __init__(
        self,
        session: Session,
        stale_memory: ResidentMemory,
        current_decision: LearningDecision,
    ) -> None:
        super().__init__(session)
        self._stale_memory = stale_memory
        self._current_decision = current_decision

    def current_memory(
        self,
        tenant_id: str,
        resident_id: str,
    ) -> ResidentMemory:
        assert tenant_id == "tenant_demo"
        assert resident_id == "resident_demo_a"
        return self._stale_memory

    def find_by_event(
        self,
        tenant_id: str,
        event_id: str,
    ) -> LearningDecision | None:
        assert tenant_id == "tenant_demo"
        assert event_id == "evt_phase2_demo"
        return self._current_decision

    def save_decision(
        self,
        tenant_id: str,
        decision: LearningDecision,
    ) -> None:
        raise AssertionError("an existing-decision retry must not persist")


class FirstReadStaleFeedbackRepository(FeedbackRepository):
    """Model both route transactions reading before the winner commits."""

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self._find_count = 0

    def find_by_event(
        self,
        tenant_id: str,
        event_id: str,
    ) -> LearningDecision | None:
        assert tenant_id == "tenant_demo"
        assert event_id == "evt_phase2_demo"
        self._find_count += 1
        if self._find_count == 1:
            return None
        return super().find_by_event(tenant_id, event_id)


class StaticEventRepository:
    def __init__(self, stored_event: StoredEvent) -> None:
        self._stored_event = stored_event

    def get(self, tenant_id: str, event_id: str) -> StoredEvent:
        assert tenant_id == "tenant_demo"
        assert event_id == self._stored_event.event.event_id
        return self._stored_event


@pytest.fixture
def session() -> Session:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def _resolve_seeded_event(session: Session) -> StoredEvent:
    story = seed_synthetic_story(session)
    repository = EventRepository(session)
    stored = repository.get(story.tenant_id, story.event_id)
    event_store = EventStore(initial_events=(stored.event,))
    opened_at = stored.event.created_at
    event_store.acknowledge(
        story.event_id,
        actor_id="operator_1",
        at=opened_at + timedelta(minutes=1),
    )
    event_store.check(
        story.event_id,
        actor_id="operator_1",
        at=opened_at + timedelta(minutes=2),
    )
    event = event_store.resolve(
        story.event_id,
        ResolutionOutcome.FALSE_POSITIVE,
        actor_id="operator_1",
        at=opened_at + timedelta(minutes=3),
    )
    saved = repository.save(
        story.tenant_id,
        event,
        expected_version=stored.version,
    )
    session.commit()
    return saved


def _add_event_copy(
    session: Session,
    source: StoredEvent,
    event_id: str,
) -> StoredEvent:
    event = replace(
        source.event,
        event_id=event_id,
        episode_id=f"episode_{event_id}",
    )
    bundle = event_to_rows("tenant_demo", event, version=source.version)
    session.add(bundle.event)
    session.flush()
    session.add_all(bundle.actions)
    session.add_all(bundle.priorities)
    session.commit()
    return StoredEvent(event, source.version)


def test_feedback_failure_rolls_back_every_effect(session: Session) -> None:
    _resolve_seeded_event(session)
    service = FeedbackCommandService(
        session,
        event_repository=EventRepository(session),
        feedback_repository=FaultingFeedbackRepository(session),
    )

    with pytest.raises(RuntimeError, match="synthetic persistence failure"):
        service.submit_feedback(
            AccessContext("tenant_demo", "operator_1"),
            "evt_phase2_demo",
            "assisted_movement",
            True,
            EventRepository(session)
            .get("tenant_demo", "evt_phase2_demo")
            .event.latest_recorded_at
            + timedelta(minutes=1),
        )
    session.rollback()

    assert session.scalar(select(func.count()).select_from(FeedbackRecordRow)) == 0
    assert session.scalar(
        select(func.count()).select_from(ResidentMemorySnapshotRow)
    ) == 0
    assert session.scalar(select(func.count()).select_from(ResidentMemoryEntryRow)) == 0
    assert session.scalar(select(func.count()).select_from(AuditLogRow)) == 0


def test_route_failure_rolls_back_feedback_and_idempotency_reservation(
    api_client: TestClient,
) -> None:
    event_path = "/v1/events/evt_phase2_demo"
    headers = {
        "X-Tenant-Id": "tenant_demo",
        "X-Actor-Id": "operator_1",
        "Idempotency-Key": "feedback-route-rollback",
    }
    for action, key, body in (
        ("acknowledge", "rollback-ack", {"occurred_at": "2026-08-24T21:03:00Z"}),
        ("checked", "rollback-check", {"occurred_at": "2026-08-24T21:04:00Z"}),
        (
            "resolve",
            "rollback-resolve",
            {
                "occurred_at": "2026-08-24T21:05:00Z",
                "outcome": "false_positive",
            },
        ),
    ):
        response = api_client.post(
            f"{event_path}/{action}",
            headers={**headers, "Idempotency-Key": key},
            json=_versioned(body),
        )
        assert response.status_code == 200

    api_client.app.state.feedback_repository_factory = FaultingFeedbackRepository
    try:
        with TestClient(api_client.app, raise_server_exceptions=False) as safe_client:
            response = safe_client.post(
                f"{event_path}/feedback",
                headers=headers,
                json=_versioned({
                    "actual_event_label": "Assisted movement",
                    "routine": True,
                    "created_at": "2026-08-24T21:06:00Z",
                }),
            )
    finally:
        del api_client.app.state.feedback_repository_factory

    assert response.status_code == 500
    assert response.json() == {
        "schema_version": "1.0",
        "error": {
            "code": "internal_error",
            "message": "Internal server error",
            "field": None,
        },
    }
    with api_client.app.state.session_factory() as database_session:
        assert database_session.scalar(
            select(func.count()).select_from(FeedbackRecordRow)
        ) == 0
        assert database_session.scalar(
            select(func.count()).select_from(ResidentMemorySnapshotRow)
        ) == 0
        assert database_session.scalar(
            select(func.count()).select_from(ResidentMemoryEntryRow)
        ) == 0
        assert database_session.scalar(
            select(func.count())
            .select_from(AuditLogRow)
            .where(AuditLogRow.action == "feedback.submitted")
        ) == 0
        assert database_session.scalar(
            select(func.count())
            .select_from(IdempotencyRecordRow)
            .where(IdempotencyRecordRow.key == "feedback-route-rollback")
        ) == 0


def test_concurrent_resident_memory_version_has_one_canonical_loser(
    tmp_path,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'memory-race.db'}"
    engine = create_engine_for_url(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as setup_session:
        first_event = _resolve_seeded_event(setup_session)
        second_event = _add_event_copy(
            setup_session,
            first_event,
            "evt_phase2_concurrent",
        )

    memory_barrier = Barrier(2)
    snapshot_check_barrier = Barrier(2)

    def synchronize_snapshot_check(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        normalized = " ".join(statement.casefold().split())
        if (
            normalized.startswith("select")
            and "from resident_memory_snapshots" in normalized
            and "resident_memory_snapshots.version =" in normalized
        ):
            snapshot_check_barrier.wait(timeout=5)

    sqlalchemy_event.listen(
        engine,
        "after_cursor_execute",
        synchronize_snapshot_check,
    )

    def submit(stored_event: StoredEvent) -> LearningDecision | Exception:
        with Session(engine) as worker_session:
            repository = CoordinatedFeedbackRepository(
                worker_session,
                memory_barrier,
            )
            service = FeedbackCommandService(
                worker_session,
                event_repository=StaticEventRepository(stored_event),
                feedback_repository=repository,
            )
            try:
                decision = service.submit_feedback(
                    AccessContext("tenant_demo", "operator_1"),
                    stored_event.event.event_id,
                    "assisted_movement",
                    True,
                    stored_event.event.latest_recorded_at + timedelta(minutes=1),
                )
                worker_session.commit()
                return decision
            except Exception as error:
                worker_session.rollback()
                return error

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(submit, (first_event, second_event)))
    finally:
        sqlalchemy_event.remove(
            engine,
            "after_cursor_execute",
            synchronize_snapshot_check,
        )

    decisions = [item for item in results if isinstance(item, LearningDecision)]
    errors = [item for item in results if isinstance(item, Exception)]
    assert len(decisions) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], ConcurrentUpdateError)
    assert not isinstance(errors[0], IntegrityError)
    with Session(engine) as verification_session:
        assert verification_session.scalar(
            select(func.count()).select_from(FeedbackRecordRow)
        ) == 1
        assert verification_session.scalar(
            select(func.count()).select_from(ResidentMemorySnapshotRow)
        ) == 1
        assert verification_session.scalar(
            select(func.count()).select_from(ResidentMemoryEntryRow)
        ) == 1
        assert verification_session.scalar(
            select(func.count())
            .select_from(AuditLogRow)
            .where(AuditLogRow.action == "feedback.submitted")
        ) == 1
    engine.dispose()


def test_memory_snapshot_collision_is_a_stable_api_conflict(
    api_client: TestClient,
) -> None:
    event_path = "/v1/events/evt_phase2_demo"
    headers = {
        "X-Tenant-Id": "tenant_demo",
        "X-Actor-Id": "operator_1",
    }
    for action, key, body in (
        ("acknowledge", "collision-ack", {"occurred_at": "2026-08-24T21:03:00Z"}),
        ("checked", "collision-check", {"occurred_at": "2026-08-24T21:04:00Z"}),
        (
            "resolve",
            "collision-resolve",
            {
                "occurred_at": "2026-08-24T21:05:00Z",
                "outcome": "false_positive",
            },
        ),
    ):
        response = api_client.post(
            f"{event_path}/{action}",
            headers={**headers, "Idempotency-Key": key},
            json=_versioned(body),
        )
        assert response.status_code == 200

    with api_client.app.state.session_factory() as setup_session:
        stored = EventRepository(setup_session).get(
            "tenant_demo",
            "evt_phase2_demo",
        )
        _add_event_copy(setup_session, stored, "evt_phase2_collision")

    winner = api_client.post(
        f"{event_path}/feedback",
        headers={**headers, "Idempotency-Key": "collision-winner"},
        json=_versioned({
            "actual_event_label": "Assisted movement",
            "routine": True,
            "created_at": "2026-08-24T21:06:00Z",
        }),
    )

    def inject_snapshot_collision(
        _connection: object,
        _cursor: object,
        statement: str,
        parameters: object,
        _context: object,
        _executemany: object,
    ) -> None:
        if statement.lstrip().casefold().startswith(
            "insert into resident_memory_snapshots"
        ):
            raise IntegrityError(
                statement,
                parameters,
                RuntimeError(
                    "UNIQUE constraint failed: "
                    "resident_memory_snapshots.resident_id, "
                    "resident_memory_snapshots.version"
                ),
            )

    engine = api_client.app.state.engine
    sqlalchemy_event.listen(
        engine,
        "before_cursor_execute",
        inject_snapshot_collision,
    )
    try:
        with TestClient(api_client.app, raise_server_exceptions=False) as safe_client:
            loser = safe_client.post(
                "/v1/events/evt_phase2_collision/feedback",
                headers={**headers, "Idempotency-Key": "collision-loser"},
                json=_versioned({
                    "actual_event_label": "Assisted movement",
                    "routine": True,
                    "created_at": "2026-08-24T21:07:00Z",
                }),
            )
    finally:
        sqlalchemy_event.remove(
            engine,
            "before_cursor_execute",
            inject_snapshot_collision,
        )

    assert winner.status_code == 200
    assert loser.status_code == 409
    assert loser.json() == {
        "schema_version": "1.0",
        "error": {
            "code": "concurrent_update",
            "message": "Resource was updated by another request",
            "field": None,
        },
    }
    with api_client.app.state.session_factory() as verification_session:
        assert verification_session.scalar(
            select(func.count()).select_from(FeedbackRecordRow)
        ) == 1
        assert verification_session.scalar(
            select(func.count()).select_from(ResidentMemorySnapshotRow)
        ) == 1
        assert verification_session.scalar(
            select(func.count()).select_from(ResidentMemoryEntryRow)
        ) == 1
        assert verification_session.scalar(
            select(func.count())
            .select_from(AuditLogRow)
            .where(AuditLogRow.action == "feedback.submitted")
        ) == 1
        assert verification_session.scalar(
            select(func.count())
            .select_from(IdempotencyRecordRow)
            .where(IdempotencyRecordRow.key == "collision-winner")
        ) == 1
        assert verification_session.scalar(
            select(func.count())
            .select_from(IdempotencyRecordRow)
            .where(IdempotencyRecordRow.key == "collision-loser")
        ) == 0


def test_existing_feedback_retry_uses_same_hydration_current_memory(
    session: Session,
) -> None:
    stored = _resolve_seeded_event(session)
    repository = FeedbackRepository(session)
    first = FeedbackCommandService(
        session,
        event_repository=EventRepository(session),
        feedback_repository=repository,
    ).submit_feedback(
        AccessContext("tenant_demo", "operator_1"),
        "evt_phase2_demo",
        "assisted_movement",
        True,
        stored.event.latest_recorded_at + timedelta(minutes=1),
    )
    session.commit()
    corrected = FeedbackService(initial_memories=(first.memory,)).correct_memory(
        resident_id="resident_demo_a",
        entry_id=first.memory.entries[0].entry_id,
        actor_id="operator_2",
        reason="Synthetic routine ended",
        corrected_at=first.feedback.created_at + timedelta(days=1),
    )
    bundle = memory_to_rows(
        "tenant_demo",
        corrected,
        first.feedback.created_at + timedelta(days=1),
    )
    session.add(bundle.snapshot)
    session.add_all(bundle.entries)
    session.commit()
    current_decision = repository.find_by_event(
        "tenant_demo",
        "evt_phase2_demo",
    )
    assert current_decision is not None

    retry = FeedbackCommandService(
        session,
        event_repository=EventRepository(session),
        feedback_repository=HydratedDecisionFeedbackRepository(
            session,
            first.memory,
            current_decision,
        ),
    ).submit_feedback(
        AccessContext("tenant_demo", "operator_1"),
        "evt_phase2_demo",
        "assisted_movement",
        True,
        first.feedback.created_at + timedelta(days=2),
    )

    assert retry.memory == corrected
    assert retry.memory.version == 2
    assert retry.memory.entries[0].status == "retired"
    assert retry.memory_updated is False


def test_same_event_feedback_race_has_one_versioned_concurrent_loser(
    api_client: TestClient,
) -> None:
    event_path = "/v1/events/evt_phase2_demo"
    base_headers = {
        "X-Tenant-Id": "tenant_demo",
        "X-Actor-Id": "operator_1",
    }
    for action, key, body in (
        ("acknowledge", "same-event-ack", {"occurred_at": "2026-08-24T21:03:00Z"}),
        ("checked", "same-event-check", {"occurred_at": "2026-08-24T21:04:00Z"}),
        (
            "resolve",
            "same-event-resolve",
            {
                "occurred_at": "2026-08-24T21:05:00Z",
                "outcome": "false_positive",
            },
        ),
    ):
        response = api_client.post(
            f"{event_path}/{action}",
            headers={**base_headers, "Idempotency-Key": key},
            json=_versioned(body),
        )
        assert response.status_code == 200

    submissions = (
        ("same-event-feedback-a", "Assisted movement"),
        ("same-event-feedback-b", "Unexplained movement"),
    )

    def post(submission: tuple[str, str]):
        key, actual_event_label = submission
        with TestClient(api_client.app, raise_server_exceptions=False) as client:
            return client.post(
                f"{event_path}/feedback",
                headers={**base_headers, "Idempotency-Key": key},
                json=_versioned({
                    "actual_event_label": actual_event_label,
                    "routine": True,
                    "created_at": "2026-08-24T21:06:00Z",
                }),
            )

    api_client.app.state.feedback_repository_factory = (
        FirstReadStaleFeedbackRepository
    )
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(post, submissions))
    finally:
        del api_client.app.state.feedback_repository_factory

    success = next(response for response in responses if response.status_code == 200)
    conflict = next(response for response in responses if response.status_code != 200)
    assert success.status_code == 200
    assert conflict.status_code == 409
    assert conflict.json() == {
        "schema_version": "1.0",
        "error": {
            "code": "concurrent_update",
            "message": "Resource was updated by another request",
            "field": None,
        },
    }
    with api_client.app.state.session_factory() as verification_session:
        assert verification_session.scalar(
            select(func.count()).select_from(FeedbackRecordRow)
        ) == 1
        assert verification_session.scalar(
            select(func.count()).select_from(ResidentMemorySnapshotRow)
        ) == 1
        assert verification_session.scalar(
            select(func.count()).select_from(ResidentMemoryEntryRow)
        ) == 1
        assert verification_session.scalar(
            select(func.count())
            .select_from(AuditLogRow)
            .where(AuditLogRow.action == "feedback.submitted")
        ) == 1
        assert verification_session.scalar(
            select(func.count())
            .select_from(IdempotencyRecordRow)
            .where(
                IdempotencyRecordRow.key.in_(
                    ("same-event-feedback-a", "same-event-feedback-b")
                )
            )
        ) == 1
