from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.mappers import StoredEvent
from backend.app.db.models import AuditLogRow, EventActionRow, MonitoringEventRow
from backend.app.db.repositories import EventRepository
from backend.app.db.seed import seed_synthetic_story
from backend.app.db.session import create_engine_for_url
from backend.app.domain.events import EventStore
from backend.app.services.errors import ConcurrentUpdateError
from backend.app.services.event_commands import EventCommandService
from backend.app.services.queries import AccessContext


class StaleReadEventRepository(EventRepository):
    """Return one captured aggregate, then use the real repository behavior."""

    def __init__(self, session: Session, stale: StoredEvent) -> None:
        super().__init__(session)
        self._stale: StoredEvent | None = stale

    def get(self, tenant_id: str, event_id: str) -> StoredEvent:
        if self._stale is not None:
            stale, self._stale = self._stale, None
            return stale
        return super().get(tenant_id, event_id)


@pytest.fixture
def engine(tmp_path):
    database_url = f"sqlite+pysqlite:///{tmp_path / 'concurrency.db'}"
    database_engine = create_engine_for_url(database_url)
    Base.metadata.create_all(database_engine)
    with Session(database_engine) as session:
        seed_synthetic_story(session)
    yield database_engine
    database_engine.dispose()


def test_repository_rejects_a_stale_expected_version(engine) -> None:
    with Session(engine) as first_session, Session(engine) as second_session:
        first_repository = EventRepository(first_session)
        second_repository = EventRepository(second_session)
        first = first_repository.get("tenant_demo", "evt_phase2_demo")
        stale = second_repository.get("tenant_demo", "evt_phase2_demo")
        second_session.rollback()
        occurred_at = first.event.created_at + timedelta(minutes=1)
        first_event = EventStore(initial_events=(first.event,)).acknowledge(
            first.event.event_id,
            actor_id="operator_1",
            at=occurred_at,
        )
        stale_event = EventStore(initial_events=(stale.event,)).acknowledge(
            stale.event.event_id,
            actor_id="operator_2",
            at=occurred_at,
        )

        saved = first_repository.save("tenant_demo", first_event, expected_version=1)
        first_session.commit()

        with pytest.raises(ConcurrentUpdateError):
            second_repository.save("tenant_demo", stale_event, expected_version=1)
        second_session.rollback()

    with Session(engine) as verification_session:
        assert saved.version == 2
        assert verification_session.scalar(
            select(MonitoringEventRow.version).where(
                MonitoringEventRow.event_id == "evt_phase2_demo"
            )
        ) == 2
        assert verification_session.scalar(
            select(func.count()).select_from(EventActionRow)
        ) == 2


def test_stale_service_command_does_not_append_history_or_audit(engine) -> None:
    context = AccessContext("tenant_demo", "operator_1")
    with Session(engine) as stale_session:
        stale = EventRepository(stale_session).get(context.tenant_id, "evt_phase2_demo")
        stale_session.rollback()

        with Session(engine) as winner_session:
            winner = EventCommandService(
                winner_session,
                EventRepository(winner_session),
            ).acknowledge(
                context,
                stale.event.event_id,
                stale.event.created_at + timedelta(minutes=1),
            )
            winner_session.commit()

        stale_service = EventCommandService(
            stale_session,
            StaleReadEventRepository(stale_session, stale),
        )
        with pytest.raises(ConcurrentUpdateError):
            stale_service.acknowledge(
                context,
                stale.event.event_id,
                stale.event.created_at + timedelta(minutes=1),
            )
        stale_session.rollback()

    with Session(engine) as verification_session:
        persisted = EventRepository(verification_session).get(
            context.tenant_id,
            stale.event.event_id,
        )
        assert winner.version == persisted.version == 2
        assert [action.actor_id for action in persisted.event.action_history] == [
            "system:monitoring_event",
            "operator_1",
        ]
        assert verification_session.scalar(
            select(func.count()).select_from(EventActionRow)
        ) == 2
        audits = verification_session.scalars(select(AuditLogRow)).all()
        assert len(audits) == 1
        assert audits[0].actor_id == "operator_1"
