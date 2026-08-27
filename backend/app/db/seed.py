"""Deterministic, non-PHI synthetic product story for local development."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from backend.app.config import Settings
from backend.app.db.mappers import event_to_rows
from backend.app.db.models import (
    ResidentRow,
    RoomResidentAssignmentRow,
    RoomRow,
    TenantRow,
)
from backend.app.db.session import create_engine_for_url, create_session_factory
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
)
from backend.app.domain.events import (
    EventAction,
    EventActionType,
    EventPriority,
    EventPriorityHistoryEntry,
    EventStatus,
    MonitoringEvent,
)
from backend.app.domain.monitoring import PresenceState, derive_monitoring_snapshot


TENANT_ID = "tenant_demo"
ROOM_ID = "room_214"
RESIDENT_ID = "resident_demo_a"
EVENT_ID = "evt_phase2_demo"


@dataclass(frozen=True)
class SeededStory:
    tenant_id: str
    room_id: str
    resident_id: str
    event_id: str


def seed_synthetic_story(session: Session) -> SeededStory:
    story = SeededStory(TENANT_ID, ROOM_ID, RESIDENT_ID, EVENT_ID)
    if session.get(TenantRow, TENANT_ID) is not None:
        return story

    opened_at = datetime(2026, 8, 24, 21, 2, 11, tzinfo=timezone.utc)
    event = MonitoringEvent(
        event_id=EVENT_ID,
        episode_id="episode_phase2_demo",
        resident_id=RESIDENT_ID,
        room_id=ROOM_ID,
        objective_family="unusual_movement",
        headline="Unusual movement detected",
        priority=EventPriority.HIGH,
        status=EventStatus.OPEN,
        created_at=opened_at,
        last_signal_at=opened_at,
        action_history=(
            EventAction(
                action=EventActionType.OPENED,
                actor_id="system:monitoring_event",
                occurred_at=opened_at,
                previous_status=EventStatus.DETECTED,
                status=EventStatus.OPEN,
            ),
        ),
        priority_history=(
            EventPriorityHistoryEntry(
                previous_priority=None,
                priority=EventPriority.HIGH,
                actor_id="system:monitoring_event",
                changed_at=opened_at,
            ),
        ),
    )
    event_bundle = event_to_rows(TENANT_ID, event, version=1)
    session.add(TenantRow(tenant_id=TENANT_ID))
    session.flush()
    session.add(RoomRow(room_id=ROOM_ID, tenant_id=TENANT_ID, label="Room 214"))
    session.add(
        ResidentRow(
            resident_id=RESIDENT_ID,
            tenant_id=TENANT_ID,
            display_label="Resident A",
        )
    )
    session.flush()
    session.add(
        RoomResidentAssignmentRow(
            assignment_id="assign_room_214_a",
            tenant_id=TENANT_ID,
            room_id=ROOM_ID,
            resident_id=RESIDENT_ID,
            status="active",
            effective_from=datetime(2026, 8, 24, tzinfo=timezone.utc),
            effective_to=None,
        )
    )
    session.add(event_bundle.event)
    session.flush()
    session.add_all(event_bundle.actions)
    session.add_all(event_bundle.priorities)

    status_started_at = datetime(2026, 8, 24, 20, 55, tzinfo=timezone.utc)
    monitoring_repository = MonitoringStatusRepository(session)
    for offset, presence in enumerate(
        (
            PresenceState.RESIDENT_PRESENT,
            PresenceState.RESIDENT_AWAY,
            PresenceState.RESIDENT_PRESENT,
            PresenceState.POSSIBLE_MULTI_PERSON,
            PresenceState.RESIDENT_PRESENT,
        )
    ):
        monitoring_repository.record(
            TENANT_ID,
            StoredMonitoringStatus(
                resident_id=RESIDENT_ID,
                room_id=ROOM_ID,
                observed_at=status_started_at + timedelta(minutes=offset),
                snapshot=derive_monitoring_snapshot(
                    assignment_valid=True,
                    device_healthy=True,
                    presence=presence,
                    signal_quality=0.9,
                ),
            ),
        )

    CalibrationRepository(session).save(
        TENANT_ID,
        StoredCalibration(
            resident_id=RESIDENT_ID,
            version=1,
            recorded_at=datetime(2026, 8, 24, 21, 0, tzinfo=timezone.utc),
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
        ),
        expected_version=0,
    )
    session.commit()
    return story


def main() -> None:
    settings = Settings()
    project_root = Path(__file__).resolve().parents[3]
    migration_config = Config()
    migration_config.set_main_option(
        "script_location",
        str(project_root / "backend/app/db/migrations"),
    )
    migration_config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(migration_config, "head")
    engine = create_engine_for_url(settings.database_url)
    try:
        with create_session_factory(engine)() as session:
            story = seed_synthetic_story(session)
    finally:
        engine.dispose()
    print(story.tenant_id)
    print(story.room_id)
    print(story.resident_id)
    print(story.event_id)


if __name__ == "__main__":
    main()
