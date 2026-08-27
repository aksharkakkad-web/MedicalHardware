from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.models import MonitoringSetupChangeRow, MonitoringStatusSnapshotRow
from backend.app.db.seed import seed_synthetic_story
from backend.app.db.session import create_engine_for_url
from backend.app.db.status_repositories import (
    CalibrationRepository,
    MonitoringStatusRepository,
    StoredCalibration,
    StoredMonitoringStatus,
)
from backend.app.domain.calibration import (
    BaselineStatus,
    CalibrationDimensionProgress,
    CalibrationProgress,
    start_recalibration,
)
from backend.app.domain.monitoring import PresenceState, derive_monitoring_snapshot
from backend.app.services.errors import ConcurrentUpdateError, NotFoundError


@pytest.fixture
def session() -> Session:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        seed_synthetic_story(database_session)
        yield database_session
    engine.dispose()


def _status(
    *,
    resident_id: str,
    room_id: str,
    observed_at: datetime,
    presence: PresenceState,
) -> StoredMonitoringStatus:
    return StoredMonitoringStatus(
        resident_id=resident_id,
        room_id=room_id,
        observed_at=observed_at,
        snapshot=derive_monitoring_snapshot(
            assignment_valid=True,
            device_healthy=True,
            presence=presence,
            signal_quality=0.9,
        ),
    )


def _established_calibration(resident_id: str) -> StoredCalibration:
    return StoredCalibration(
        resident_id=resident_id,
        version=1,
        recorded_at=datetime(2026, 8, 24, 21, 5, tzinfo=timezone.utc),
        progress=CalibrationProgress(
            setup_version="setup_room_214_v1",
            status=BaselineStatus.ESTABLISHED,
            eligible_windows=12,
            excluded_windows=2,
            reason="calibration_complete",
            dimension_progress=(
                CalibrationDimensionProgress(
                    dimension="movement",
                    status=BaselineStatus.ESTABLISHED,
                    eligible_windows=12,
                    excluded_windows=2,
                ),
                CalibrationDimensionProgress(
                    dimension="respiratory_rate",
                    status=BaselineStatus.ESTABLISHED,
                    eligible_windows=12,
                    excluded_windows=2,
                ),
            ),
        ),
    )


def test_monitoring_repository_preserves_order_states_and_utc(
    session: Session,
) -> None:
    story = seed_synthetic_story(session)
    repository = MonitoringStatusRepository(session)
    local_zone = timezone(timedelta(hours=5, minutes=30))
    start = datetime(2026, 8, 25, 2, 30, tzinfo=local_zone)
    presences = (
        PresenceState.RESIDENT_PRESENT,
        PresenceState.RESIDENT_AWAY,
        PresenceState.POSSIBLE_MULTI_PERSON,
        PresenceState.RESIDENT_PRESENT,
    )
    for offset, presence in enumerate(presences):
        repository.record(
            story.tenant_id,
            _status(
                resident_id=story.resident_id,
                room_id=story.room_id,
                observed_at=start + timedelta(minutes=offset),
                presence=presence,
            ),
        )
    session.commit()

    timeline = repository.timeline(story.tenant_id, story.resident_id)

    assert [item.snapshot.presence for item in timeline] == list(presences)
    assert timeline[0].observed_at == datetime(
        2026,
        8,
        24,
        21,
        0,
        tzinfo=timezone.utc,
    )
    assert repository.latest(story.tenant_id, story.resident_id) == timeline[-1]
    with pytest.raises(NotFoundError):
        repository.latest("tenant_other", story.resident_id)


def test_calibration_repository_round_trips_dimensions_and_setup_history(
    session: Session,
) -> None:
    story = seed_synthetic_story(session)
    repository = CalibrationRepository(session)
    initial = _established_calibration(story.resident_id)
    repository.save(story.tenant_id, initial, expected_version=0)
    recalibrated = StoredCalibration(
        resident_id=story.resident_id,
        version=2,
        recorded_at=datetime(2026, 8, 24, 22, 0, tzinfo=timezone.utc),
        progress=start_recalibration(
            initial.progress,
            new_setup_version="setup_room_214_v2",
            reason="device_moved",
            actor_id="operator_001",
            changed_at=datetime(2026, 8, 24, 22, 0, tzinfo=timezone.utc),
            affected_dimensions=("movement",),
        ),
    )

    saved = repository.save(story.tenant_id, recalibrated, expected_version=1)
    session.commit()
    loaded = repository.current(story.tenant_id, story.resident_id)

    assert saved == loaded
    assert loaded.version == 2
    assert loaded.progress.dimension("movement").status == BaselineStatus.CALIBRATING
    assert (
        loaded.progress.dimension("respiratory_rate").status
        == BaselineStatus.ESTABLISHED
    )
    assert loaded.progress.setup_change_history[0].reason == "device_moved"
    assert loaded.recorded_at.tzinfo is timezone.utc
    with pytest.raises(NotFoundError):
        repository.current("tenant_other", story.resident_id)


def test_calibration_repository_rejects_stale_expected_version(
    session: Session,
) -> None:
    story = seed_synthetic_story(session)
    repository = CalibrationRepository(session)
    initial = _established_calibration(story.resident_id)
    repository.save(story.tenant_id, initial, expected_version=0)
    session.commit()

    first = StoredCalibration(
        resident_id=story.resident_id,
        version=2,
        recorded_at=datetime(2026, 8, 24, 22, 0, tzinfo=timezone.utc),
        progress=start_recalibration(
            initial.progress,
            new_setup_version="setup_room_214_v2",
            reason="device_moved",
            actor_id="operator_001",
            changed_at=datetime(2026, 8, 24, 22, 0, tzinfo=timezone.utc),
            affected_dimensions=("movement",),
        ),
    )
    repository.save(story.tenant_id, first, expected_version=1)
    session.commit()

    stale = StoredCalibration(
        resident_id=story.resident_id,
        version=2,
        recorded_at=datetime(2026, 8, 24, 22, 1, tzinfo=timezone.utc),
        progress=start_recalibration(
            initial.progress,
            new_setup_version="setup_room_214_v2_stale",
            reason="stale_move",
            actor_id="operator_002",
            changed_at=datetime(2026, 8, 24, 22, 1, tzinfo=timezone.utc),
            affected_dimensions=("movement",),
        ),
    )
    with pytest.raises(ConcurrentUpdateError):
        repository.save(story.tenant_id, stale, expected_version=1)


def test_calibration_progress_does_not_duplicate_setup_change_history(
    session: Session,
) -> None:
    story = seed_synthetic_story(session)
    repository = CalibrationRepository(session)
    initial = _established_calibration(story.resident_id)
    repository.save(story.tenant_id, initial, expected_version=0)
    recalibrated = StoredCalibration(
        resident_id=story.resident_id,
        version=2,
        recorded_at=datetime(2026, 8, 24, 22, 0, tzinfo=timezone.utc),
        progress=start_recalibration(
            initial.progress,
            new_setup_version="setup_room_214_v2",
            reason="device_moved",
            actor_id="operator_001",
            changed_at=datetime(2026, 8, 24, 22, 0, tzinfo=timezone.utc),
            affected_dimensions=("movement",),
        ),
    )
    repository.save(story.tenant_id, recalibrated, expected_version=1)
    later_progress = StoredCalibration(
        resident_id=story.resident_id,
        version=3,
        recorded_at=datetime(2026, 8, 24, 22, 5, tzinfo=timezone.utc),
        progress=replace(recalibrated.progress, eligible_windows=13),
    )

    loaded = repository.save(story.tenant_id, later_progress, expected_version=2)

    assert len(loaded.progress.setup_change_history) == 1
    assert session.scalar(
        select(func.count()).select_from(MonitoringSetupChangeRow)
    ) == 1


def test_monitoring_repository_rejects_malformed_stored_enum(
    session: Session,
) -> None:
    story = seed_synthetic_story(session)
    repository = MonitoringStatusRepository(session)
    stored = _status(
        resident_id=story.resident_id,
        room_id=story.room_id,
        observed_at=datetime(2026, 8, 24, 21, 0, tzinfo=timezone.utc),
        presence=PresenceState.RESIDENT_PRESENT,
    )
    repository.record(story.tenant_id, stored)
    session.flush()
    row = session.get(MonitoringStatusSnapshotRow, 1)
    assert row is not None
    row.monitoring_state = "invented_state"
    session.commit()

    with pytest.raises(ValueError):
        repository.latest(story.tenant_id, story.resident_id)
