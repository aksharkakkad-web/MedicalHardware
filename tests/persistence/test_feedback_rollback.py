from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.mappers import feedback_to_row
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
from backend.app.domain.feedback import LearningDecision
from backend.app.services.queries import AccessContext


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


@pytest.fixture
def session() -> Session:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session
    engine.dispose()


def _resolve_seeded_event(session: Session) -> None:
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
    repository.save(story.tenant_id, event, expected_version=stored.version)
    session.commit()


def test_feedback_failure_rolls_back_every_effect(session: Session) -> None:
    from backend.app.services.feedback_commands import FeedbackCommandService

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
            json=body,
        )
        assert response.status_code == 200

    api_client.app.state.feedback_repository_factory = FaultingFeedbackRepository
    try:
        with TestClient(api_client.app, raise_server_exceptions=False) as safe_client:
            response = safe_client.post(
                f"{event_path}/feedback",
                headers=headers,
                json={
                    "actual_event_label": "Assisted movement",
                    "routine": True,
                    "created_at": "2026-08-24T21:06:00Z",
                },
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
