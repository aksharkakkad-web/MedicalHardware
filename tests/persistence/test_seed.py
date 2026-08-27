import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.models import (
    EventActionRow,
    EventPriorityHistoryRow,
    MonitoringEventRow,
    ResidentRow,
    RoomResidentAssignmentRow,
    RoomRow,
    TenantRow,
)
from backend.app.db.seed import (
    EVENT_ID,
    RESIDENT_ID,
    ROOM_ID,
    TENANT_ID,
    seed_synthetic_story,
)
from backend.app.db.session import create_engine_for_url


def test_seed_is_deterministic_and_idempotent() -> None:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        first = seed_synthetic_story(session)
        second = seed_synthetic_story(session)

        assert first == second
        assert (first.tenant_id, first.room_id, first.resident_id, first.event_id) == (
            TENANT_ID,
            ROOM_ID,
            RESIDENT_ID,
            EVENT_ID,
        )
        for row_type in (
            TenantRow,
            RoomRow,
            ResidentRow,
            RoomResidentAssignmentRow,
            MonitoringEventRow,
            EventActionRow,
            EventPriorityHistoryRow,
        ):
            assert session.scalar(select(func.count()).select_from(row_type)) == 1
    engine.dispose()


def test_seed_does_not_fill_partial_story_when_tenant_already_exists() -> None:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(TenantRow(tenant_id=TENANT_ID))
        session.commit()

        seed_synthetic_story(session)

        assert session.scalar(select(func.count()).select_from(TenantRow)) == 1
        assert session.scalar(select(func.count()).select_from(MonitoringEventRow)) == 0
    engine.dispose()


def test_seed_module_migrates_seeds_and_prints_only_synthetic_ids(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "seed.db"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite+pysqlite:///{database_path}"

    completed = subprocess.run(
        [sys.executable, "-m", "backend.app.db.seed"],
        cwd=Path(__file__).parents[2],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.splitlines() == [TENANT_ID, ROOM_ID, RESIDENT_ID, EVENT_ID]
    assert "sqlite" not in completed.stdout
    assert completed.stderr == ""
