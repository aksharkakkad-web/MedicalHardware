from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


class TenantRow(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(String(255), primary_key=True)


class LocationRow(Base):
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("tenant_id", "location_id"),)

    location_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    label: Mapped[str] = mapped_column(String(255))


class DeviceRow(Base):
    __tablename__ = "devices"
    __table_args__ = (UniqueConstraint("tenant_id", "device_id"),)

    device_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    display_label: Mapped[str] = mapped_column(String(255))


class RoomRow(Base):
    __tablename__ = "rooms"
    __table_args__ = (UniqueConstraint("tenant_id", "room_id"),)

    room_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    label: Mapped[str] = mapped_column(String(255))


class ResidentRow(Base):
    __tablename__ = "residents"
    __table_args__ = (UniqueConstraint("tenant_id", "resident_id"),)

    resident_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    display_label: Mapped[str] = mapped_column(String(255))


class RoomResidentAssignmentRow(Base):
    __tablename__ = "room_resident_assignments"
    __table_args__ = (
        Index(
            "uq_active_room_assignment",
            "tenant_id",
            "room_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "uq_active_resident_assignment",
            "tenant_id",
            "resident_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        ForeignKeyConstraint(
            ("tenant_id", "room_id"),
            ("rooms.tenant_id", "rooms.room_id"),
        ),
        ForeignKeyConstraint(
            ("tenant_id", "resident_id"),
            ("residents.tenant_id", "residents.resident_id"),
        ),
    )

    assignment_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.room_id"), index=True)
    resident_id: Mapped[str] = mapped_column(ForeignKey("residents.resident_id"), index=True)
    status: Mapped[str] = mapped_column(String(64))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeviceRoomAssignmentRow(Base):
    __tablename__ = "device_room_assignments"
    __table_args__ = (
        Index(
            "uq_active_device_room_assignment",
            "tenant_id",
            "device_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "uq_active_room_device_assignment",
            "tenant_id",
            "room_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        ForeignKeyConstraint(
            ("tenant_id", "device_id"),
            ("devices.tenant_id", "devices.device_id"),
        ),
        ForeignKeyConstraint(
            ("tenant_id", "location_id"),
            ("locations.tenant_id", "locations.location_id"),
        ),
        ForeignKeyConstraint(
            ("tenant_id", "room_id"),
            ("rooms.tenant_id", "rooms.room_id"),
        ),
    )

    assignment_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.device_id"), index=True)
    location_id: Mapped[str] = mapped_column(
        ForeignKey("locations.location_id"),
        index=True,
    )
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.room_id"), index=True)
    status: Mapped[str] = mapped_column(String(64))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeviceHealthObservationRow(Base):
    __tablename__ = "device_health_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ("tenant_id", "device_id"),
            ("devices.tenant_id", "devices.device_id"),
        ),
    )

    device_health_observation_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.device_id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(64))
    sources: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    limitations: Mapped[list[str]] = mapped_column(JSON)
    policy_version: Mapped[str] = mapped_column(String(255))
    policy_test_only: Mapped[bool] = mapped_column(Boolean)


class MonitoringStatusSnapshotRow(Base):
    __tablename__ = "monitoring_status_snapshots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "resident_id", "observed_at"),
        ForeignKeyConstraint(
            ("tenant_id", "room_id"),
            ("rooms.tenant_id", "rooms.room_id"),
        ),
        ForeignKeyConstraint(
            ("tenant_id", "resident_id"),
            ("residents.tenant_id", "residents.resident_id"),
        ),
    )

    monitoring_status_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.tenant_id"),
        index=True,
    )
    resident_id: Mapped[str] = mapped_column(
        ForeignKey("residents.resident_id"),
        index=True,
    )
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.room_id"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    monitoring_state: Mapped[str] = mapped_column(String(64))
    presence_state: Mapped[str] = mapped_column(String(64))
    baseline_learning_allowed: Mapped[bool] = mapped_column(Boolean)
    resident_measurements_allowed: Mapped[bool] = mapped_column(Boolean)
    reasons: Mapped[list[str]] = mapped_column(JSON)
    quality_policy_version: Mapped[str] = mapped_column(String(255))
    quality_policy_test_only: Mapped[bool] = mapped_column(Boolean)


class CalibrationSnapshotRow(Base):
    __tablename__ = "calibration_snapshots"
    __table_args__ = (
        UniqueConstraint("tenant_id", "resident_id", "version"),
        ForeignKeyConstraint(
            ("tenant_id", "resident_id"),
            ("residents.tenant_id", "residents.resident_id"),
        ),
    )

    calibration_snapshot_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.tenant_id"),
        index=True,
    )
    resident_id: Mapped[str] = mapped_column(
        ForeignKey("residents.resident_id"),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    setup_version: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64))
    eligible_windows: Mapped[int] = mapped_column(Integer)
    excluded_windows: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(500))
    prior_setup_versions: Mapped[list[str]] = mapped_column(JSON)
    dimension_progress: Mapped[list[dict[str, object]]] = mapped_column(JSON)


class MonitoringSetupChangeRow(Base):
    __tablename__ = "monitoring_setup_changes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "resident_id", "calibration_version"),
        ForeignKeyConstraint(
            ("tenant_id", "resident_id"),
            ("residents.tenant_id", "residents.resident_id"),
        ),
    )

    monitoring_setup_change_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.tenant_id"),
        index=True,
    )
    resident_id: Mapped[str] = mapped_column(
        ForeignKey("residents.resident_id"),
        index=True,
    )
    calibration_version: Mapped[int] = mapped_column(Integer)
    previous_setup_version: Mapped[str] = mapped_column(String(255))
    new_setup_version: Mapped[str] = mapped_column(String(255))
    affected_dimensions: Mapped[list[str]] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(String(500))
    actor_id: Mapped[str] = mapped_column(String(255))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MonitoringEventRow(Base):
    __tablename__ = "monitoring_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ("tenant_id", "room_id"),
            ("rooms.tenant_id", "rooms.room_id"),
        ),
        ForeignKeyConstraint(
            ("tenant_id", "resident_id"),
            ("residents.tenant_id", "residents.resident_id"),
        ),
    )

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    episode_id: Mapped[str] = mapped_column(String(255), index=True)
    resident_id: Mapped[str] = mapped_column(ForeignKey("residents.resident_id"), index=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.room_id"), index=True)
    objective_family: Mapped[str] = mapped_column(String(128))
    headline: Mapped[str] = mapped_column(String(500))
    priority: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_signal_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    signal_count: Mapped[int] = mapped_column(Integer)
    related_event_ids: Mapped[list[str]] = mapped_column(JSON)
    recurrence_count: Mapped[int] = mapped_column(Integer)
    overdue_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_outcome: Mapped[str | None] = mapped_column(String(255))
    episode_policy_version: Mapped[str] = mapped_column(String(255))
    episode_policy_test_only: Mapped[bool] = mapped_column(Boolean)
    resident_memory_version: Mapped[int | None] = mapped_column(Integer)
    resident_memory_entry_ids: Mapped[list[str]] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(Integer)


class EventActionRow(Base):
    __tablename__ = "event_actions"
    __table_args__ = (UniqueConstraint("event_id", "sequence"),)

    action_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("monitoring_events.event_id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(255))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    previous_status: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64))
    resolution_outcome: Mapped[str | None] = mapped_column(String(255))


class EventPriorityHistoryRow(Base):
    __tablename__ = "event_priority_history"
    __table_args__ = (UniqueConstraint("event_id", "sequence"),)

    priority_history_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("monitoring_events.event_id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    previous_priority: Mapped[str | None] = mapped_column(String(64))
    priority: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str] = mapped_column(String(255))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FeedbackRecordRow(Base):
    __tablename__ = "feedback_records"
    __table_args__ = (UniqueConstraint("tenant_id", "event_id"),)

    feedback_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("monitoring_events.event_id"), index=True)
    resident_id: Mapped[str] = mapped_column(ForeignKey("residents.resident_id"), index=True)
    actor_id: Mapped[str] = mapped_column(String(255))
    outcome: Mapped[str] = mapped_column(String(64))
    actual_event_label: Mapped[str] = mapped_column(String(255))
    routine: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    memory_updated: Mapped[bool] = mapped_column(Boolean)
    baseline_window_eligible: Mapped[bool] = mapped_column(Boolean)
    global_label_recorded: Mapped[bool] = mapped_column(Boolean)


class ResidentMemorySnapshotRow(Base):
    __tablename__ = "resident_memory_snapshots"
    __table_args__ = (UniqueConstraint("resident_id", "version"),)

    memory_snapshot_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    resident_id: Mapped[str] = mapped_column(ForeignKey("residents.resident_id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ResidentMemoryEntryRow(Base):
    __tablename__ = "resident_memory_entries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "resident_id", "memory_version", "entry_id"),
        CheckConstraint(
            "(source_kind = 'feedback' AND source_feedback_id IS NOT NULL) OR "
            "(source_kind = 'operator' AND source_feedback_id IS NULL)",
            name="ck_resident_memory_entry_source",
        ),
    )

    memory_entry_row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[str] = mapped_column(String(255))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    resident_id: Mapped[str] = mapped_column(ForeignKey("residents.resident_id"), index=True)
    memory_version: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(String(1000))
    source_kind: Mapped[str] = mapped_column(String(64), default="feedback")
    source_feedback_id: Mapped[str | None] = mapped_column(
        ForeignKey("feedback_records.feedback_id"),
        index=True,
    )
    supersedes_entry_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    retired_by: Mapped[str | None] = mapped_column(String(255))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retirement_reason: Mapped[str | None] = mapped_column(String(500))


class ResidentNotificationPreferenceVersionRow(Base):
    __tablename__ = "resident_notification_preference_versions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "resident_id", "version"),
        ForeignKeyConstraint(
            ("tenant_id", "resident_id"),
            ("residents.tenant_id", "residents.resident_id"),
        ),
        CheckConstraint("version >= 1", name="ck_resident_preference_version"),
    )

    preference_version_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("tenants.tenant_id"),
        index=True,
    )
    resident_id: Mapped[str] = mapped_column(
        ForeignKey("residents.resident_id"),
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer)
    watch_delivery_enabled: Mapped[bool] = mapped_column(Boolean)
    high_delivery_enabled: Mapped[bool] = mapped_column(Boolean)
    critical_delivery_enabled: Mapped[bool] = mapped_column(Boolean)
    away_awareness_enabled: Mapped[bool] = mapped_column(Boolean)
    return_awareness_enabled: Mapped[bool] = mapped_column(Boolean)
    limited_awareness_enabled: Mapped[bool] = mapped_column(Boolean)
    unavailable_awareness_enabled: Mapped[bool] = mapped_column(Boolean)
    changed_by: Mapped[str] = mapped_column(String(255))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IdempotencyRecordRow(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("tenant_id", "actor_id", "key"),)

    idempotency_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    actor_id: Mapped[str] = mapped_column(String(255))
    key: Mapped[str] = mapped_column(String(255))
    request_fingerprint: Mapped[str] = mapped_column(String(255))
    response_status: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict[str, object]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditLogRow(Base):
    __tablename__ = "audit_log"

    audit_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.tenant_id"), index=True)
    actor_id: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(255))
    target_type: Mapped[str] = mapped_column(String(255))
    target_id: Mapped[str] = mapped_column(String(255))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, object]] = mapped_column(JSON)
