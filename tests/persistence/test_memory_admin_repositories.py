from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.models import (
    ResidentMemoryEntryRow,
    ResidentMemorySnapshotRow,
    ResidentRow,
    TenantRow,
)
from backend.app.db.repositories import FeedbackRepository
from backend.app.domain.feedback import ResidentMemoryService
from backend.app.services.errors import ConcurrentUpdateError, NotFoundError


NOW = datetime(2026, 8, 25, 15, 10, tzinfo=timezone.utc)


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


def test_admin_memory_versions_append_with_provenance_and_correction_links(
    session: Session,
) -> None:
    repository = FeedbackRepository(session)
    service = ResidentMemoryService()

    added = service.add_entry(
        resident_id="resident_a",
        expected_version=0,
        description="Assisted standing is common before breakfast.",
        actor_id="operator_1",
        changed_at=NOW,
    )
    saved_added = repository.save_memory(
        "tenant_a",
        added,
        expected_version=0,
        changed_at=NOW,
    )
    original_entry = saved_added.active_entries[0]

    corrected = ResidentMemoryService(
        initial_memories=(saved_added,)
    ).correct_entry(
        resident_id="resident_a",
        entry_id=original_entry.entry_id,
        expected_version=1,
        description="Assisted standing is common after breakfast.",
        reason="The routine time was entered incorrectly.",
        actor_id="operator_2",
        changed_at=NOW + timedelta(minutes=1),
    )
    saved_corrected = repository.save_memory(
        "tenant_a",
        corrected,
        expected_version=1,
        changed_at=NOW + timedelta(minutes=1),
    )

    history = repository.memory_timeline("tenant_a", "resident_a")
    assert history == [saved_added, saved_corrected]
    assert history[0].active_entries == (original_entry,)
    assert history[1].entries[0].status == "retired"
    replacement = history[1].active_entries[0]
    assert replacement.source_kind == "operator"
    assert replacement.source_feedback_id is None
    assert replacement.supersedes_entry_id == original_entry.entry_id

    assert session.scalar(
        select(func.count()).select_from(ResidentMemorySnapshotRow)
    ) == 2
    assert session.scalar(
        select(func.count()).select_from(ResidentMemoryEntryRow)
    ) == 3


def test_admin_memory_repository_rejects_stale_and_cross_tenant_writes(
    session: Session,
) -> None:
    repository = FeedbackRepository(session)
    added = ResidentMemoryService().add_entry(
        resident_id="resident_a",
        expected_version=0,
        description="Morning routine",
        actor_id="operator_1",
        changed_at=NOW,
    )
    repository.save_memory(
        "tenant_a",
        added,
        expected_version=0,
        changed_at=NOW,
    )

    second = ResidentMemoryService(initial_memories=(added,)).add_entry(
        resident_id="resident_a",
        expected_version=1,
        description="Evening routine",
        actor_id="operator_1",
        changed_at=NOW + timedelta(minutes=1),
    )
    with pytest.raises(ConcurrentUpdateError):
        repository.save_memory(
            "tenant_a",
            second,
            expected_version=0,
            changed_at=NOW + timedelta(minutes=1),
        )

    cross_tenant = ResidentMemoryService().add_entry(
        resident_id="resident_b",
        expected_version=0,
        description="Other tenant routine",
        actor_id="operator_1",
        changed_at=NOW,
    )
    with pytest.raises(NotFoundError):
        repository.save_memory(
            "tenant_a",
            cross_tenant,
            expected_version=0,
            changed_at=NOW,
        )

    assert repository.current_memory("tenant_a", "resident_a") == added
    assert repository.current_memory("tenant_a", "resident_b").version == 0


def test_expected_new_behavior_survives_repository_restart_with_provenance(
    session: Session,
) -> None:
    saved = FeedbackRepository(session).save_memory(
        "tenant_a",
        ResidentMemoryService().add_entry(
            resident_id="resident_a",
            expected_version=0,
            description="A new medication may increase bathroom trips.",
            context_kind="expected_new_behavior",
            effective_from=NOW,
            effective_until=NOW + timedelta(days=7),
            local_time_start="07:30",
            local_time_end="11:00",
            recurrence_note="May happen several times each morning",
            flexibility_note="Timing varies day to day",
            actor_id="operator_1",
            changed_at=NOW,
        ),
        expected_version=0,
        changed_at=NOW,
    )
    session.commit()

    with Session(session.get_bind()) as restarted_session:
        restored = FeedbackRepository(restarted_session).current_memory(
            "tenant_a",
            "resident_a",
        )

    assert restored == saved
    entry = restored.active_entries[0]
    assert entry.context_kind == "expected_new_behavior"
    assert entry.effective_from == NOW
    assert entry.effective_until == NOW + timedelta(days=7)
    assert entry.local_time_start == "07:30"
    assert entry.local_time_end == "11:00"
    assert entry.recurrence_note == "May happen several times each morning"
    assert entry.flexibility_note == "Timing varies day to day"
    assert entry.source_kind == "operator"
    assert entry.created_by == "operator_1"
