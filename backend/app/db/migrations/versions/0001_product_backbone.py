"""Create the initial durable product backbone."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_product_backbone"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("tenant_id"),
    )
    op.create_table(
        "rooms",
        sa.Column("room_id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("room_id"),
        sa.UniqueConstraint("tenant_id", "room_id"),
    )
    op.create_index("ix_rooms_tenant_id", "rooms", ["tenant_id"])
    op.create_table(
        "residents",
        sa.Column("resident_id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("display_label", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("resident_id"),
        sa.UniqueConstraint("tenant_id", "resident_id"),
    )
    op.create_index("ix_residents_tenant_id", "residents", ["tenant_id"])
    op.create_table(
        "room_resident_assignments",
        sa.Column("assignment_id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("room_id", sa.String(length=255), nullable=False),
        sa.Column("resident_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.resident_id"]),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.room_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "room_id"],
            ["rooms.tenant_id", "rooms.room_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "resident_id"],
            ["residents.tenant_id", "residents.resident_id"],
        ),
        sa.PrimaryKeyConstraint("assignment_id"),
    )
    op.create_index("ix_room_resident_assignments_tenant_id", "room_resident_assignments", ["tenant_id"])
    op.create_index("ix_room_resident_assignments_room_id", "room_resident_assignments", ["room_id"])
    op.create_index("ix_room_resident_assignments_resident_id", "room_resident_assignments", ["resident_id"])
    op.create_index(
        "uq_active_room_assignment",
        "room_resident_assignments",
        ["tenant_id", "room_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "uq_active_resident_assignment",
        "room_resident_assignments",
        ["tenant_id", "resident_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "monitoring_events",
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("episode_id", sa.String(length=255), nullable=False),
        sa.Column("resident_id", sa.String(length=255), nullable=False),
        sa.Column("room_id", sa.String(length=255), nullable=False),
        sa.Column("objective_family", sa.String(length=128), nullable=False),
        sa.Column("headline", sa.String(length=500), nullable=False),
        sa.Column("priority", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_signal_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signal_count", sa.Integer(), nullable=False),
        sa.Column("related_event_ids", sa.JSON(), nullable=False),
        sa.Column("recurrence_count", sa.Integer(), nullable=False),
        sa.Column("overdue_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_outcome", sa.String(length=255), nullable=True),
        sa.Column("episode_policy_version", sa.String(length=255), nullable=False),
        sa.Column("episode_policy_test_only", sa.Boolean(), nullable=False),
        sa.Column("resident_memory_version", sa.Integer(), nullable=True),
        sa.Column("resident_memory_entry_ids", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.resident_id"]),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.room_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "room_id"],
            ["rooms.tenant_id", "rooms.room_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "resident_id"],
            ["residents.tenant_id", "residents.resident_id"],
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_monitoring_events_tenant_id", "monitoring_events", ["tenant_id"])
    op.create_index("ix_monitoring_events_episode_id", "monitoring_events", ["episode_id"])
    op.create_index("ix_monitoring_events_resident_id", "monitoring_events", ["resident_id"])
    op.create_index("ix_monitoring_events_room_id", "monitoring_events", ["room_id"])
    op.create_table(
        "event_actions",
        sa.Column("action_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_status", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("resolution_outcome", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["monitoring_events.event_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("action_id"),
        sa.UniqueConstraint("event_id", "sequence"),
    )
    op.create_index("ix_event_actions_tenant_id", "event_actions", ["tenant_id"])
    op.create_index("ix_event_actions_event_id", "event_actions", ["event_id"])
    op.create_table(
        "event_priority_history",
        sa.Column("priority_history_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("previous_priority", sa.String(length=64), nullable=True),
        sa.Column("priority", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["monitoring_events.event_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("priority_history_id"),
        sa.UniqueConstraint("event_id", "sequence"),
    )
    op.create_index("ix_event_priority_history_tenant_id", "event_priority_history", ["tenant_id"])
    op.create_index("ix_event_priority_history_event_id", "event_priority_history", ["event_id"])
    op.create_table(
        "feedback_records",
        sa.Column("feedback_id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("resident_id", sa.String(length=255), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column("actual_event_label", sa.String(length=255), nullable=False),
        sa.Column("routine", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("memory_updated", sa.Boolean(), nullable=False),
        sa.Column("baseline_window_eligible", sa.Boolean(), nullable=False),
        sa.Column("global_label_recorded", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["monitoring_events.event_id"]),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.resident_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("feedback_id"),
        sa.UniqueConstraint("tenant_id", "event_id"),
    )
    op.create_index("ix_feedback_records_tenant_id", "feedback_records", ["tenant_id"])
    op.create_index("ix_feedback_records_event_id", "feedback_records", ["event_id"])
    op.create_index("ix_feedback_records_resident_id", "feedback_records", ["resident_id"])
    op.create_table(
        "resident_memory_snapshots",
        sa.Column("memory_snapshot_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("resident_id", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.resident_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("memory_snapshot_id"),
        sa.UniqueConstraint("resident_id", "version"),
    )
    op.create_index("ix_resident_memory_snapshots_tenant_id", "resident_memory_snapshots", ["tenant_id"])
    op.create_index("ix_resident_memory_snapshots_resident_id", "resident_memory_snapshots", ["resident_id"])
    op.create_table(
        "resident_memory_entries",
        sa.Column("memory_entry_row_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entry_id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("resident_id", sa.String(length=255), nullable=False),
        sa.Column("memory_version", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("source_feedback_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_by", sa.String(length=255), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retirement_reason", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.resident_id"]),
        sa.ForeignKeyConstraint(["source_feedback_id"], ["feedback_records.feedback_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("memory_entry_row_id"),
        sa.UniqueConstraint("tenant_id", "resident_id", "memory_version", "entry_id"),
    )
    op.create_index("ix_resident_memory_entries_tenant_id", "resident_memory_entries", ["tenant_id"])
    op.create_index("ix_resident_memory_entries_resident_id", "resident_memory_entries", ["resident_id"])
    op.create_index("ix_resident_memory_entries_source_feedback_id", "resident_memory_entries", ["source_feedback_id"])
    op.create_table(
        "idempotency_records",
        sa.Column("idempotency_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=255), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("idempotency_id"),
        sa.UniqueConstraint("tenant_id", "actor_id", "key"),
    )
    op.create_index("ix_idempotency_records_tenant_id", "idempotency_records", ["tenant_id"])
    op.create_table(
        "audit_log",
        sa.Column("audit_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("target_type", sa.String(length=255), nullable=False),
        sa.Column("target_id", sa.String(length=255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("audit_id"),
    )
    op.create_index("ix_audit_log_tenant_id", "audit_log", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("idempotency_records")
    op.drop_table("resident_memory_entries")
    op.drop_table("resident_memory_snapshots")
    op.drop_table("feedback_records")
    op.drop_table("event_priority_history")
    op.drop_table("event_actions")
    op.drop_table("monitoring_events")
    op.drop_table("room_resident_assignments")
    op.drop_table("residents")
    op.drop_table("rooms")
    op.drop_table("tenants")
