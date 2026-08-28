from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.models import ResidentRow, TenantRow
from backend.app.db.preference_repositories import NotificationPreferenceRepository
from backend.app.domain.preferences import (
    AwarenessDeliveryPreferences,
    EventDeliveryPreferences,
    update_notification_preferences,
)
from backend.app.services.errors import ConcurrentUpdateError, NotFoundError


NOW = datetime(2026, 8, 25, 15, 0, tzinfo=timezone.utc)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                TenantRow(tenant_id="tenant_a"),
                TenantRow(tenant_id="tenant_b"),
            ]
        )
        session.flush()
        session.add_all(
            [
                ResidentRow(
                    resident_id="resident_a",
                    tenant_id="tenant_a",
                    display_label="Resident A",
                ),
                ResidentRow(
                    resident_id="resident_b",
                    tenant_id="tenant_b",
                    display_label="Resident B",
                ),
            ]
        )
        session.commit()
        yield session
    engine.dispose()


def _next(current=None, *, resident_id: str = "resident_a", changed_at=NOW):
    return update_notification_preferences(
        current=current,
        resident_id=resident_id,
        expected_version=0 if current is None else current.version,
        event_delivery=EventDeliveryPreferences(
            watch=False,
            high=True,
            critical=True,
        ),
        awareness_delivery=AwarenessDeliveryPreferences(
            away=True,
            return_=True,
            limited=False,
            unavailable=True,
        ),
        actor_id="operator_1",
        changed_at=changed_at,
    )


def test_repository_returns_honest_missing_then_appends_versions(
    session: Session,
) -> None:
    repository = NotificationPreferenceRepository(session)

    assert repository.current("tenant_a", "resident_a") is None
    first = repository.save("tenant_a", _next(), expected_version=0)
    second = repository.save(
        "tenant_a",
        _next(first, changed_at=NOW + timedelta(minutes=1)),
        expected_version=1,
    )

    assert first.version == 1
    assert second.version == 2
    assert repository.current("tenant_a", "resident_a") == second
    assert repository.timeline("tenant_a", "resident_a") == [first, second]


def test_repository_rejects_stale_writer_without_partial_history(
    session: Session,
) -> None:
    repository = NotificationPreferenceRepository(session)
    first = repository.save("tenant_a", _next(), expected_version=0)

    with pytest.raises(ConcurrentUpdateError):
        repository.save(
            "tenant_a",
            _next(first, changed_at=NOW + timedelta(minutes=1)),
            expected_version=0,
        )

    assert repository.timeline("tenant_a", "resident_a") == [first]


def test_repository_masks_cross_tenant_resident_as_not_found(
    session: Session,
) -> None:
    repository = NotificationPreferenceRepository(session)

    with pytest.raises(NotFoundError):
        repository.save(
            "tenant_a",
            _next(resident_id="resident_b"),
            expected_version=0,
        )

    assert repository.current("tenant_a", "resident_b") is None
    assert repository.timeline("tenant_a", "resident_b") == []
