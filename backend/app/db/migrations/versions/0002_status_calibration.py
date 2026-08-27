"""Add durable resident status and calibration history."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002_status_calibration"
down_revision: str | None = "0001_product_backbone"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monitoring_status_snapshots",
        sa.Column("monitoring_status_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("resident_id", sa.String(length=255), nullable=False),
        sa.Column("room_id", sa.String(length=255), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("monitoring_state", sa.String(length=64), nullable=False),
        sa.Column("presence_state", sa.String(length=64), nullable=False),
        sa.Column("baseline_learning_allowed", sa.Boolean(), nullable=False),
        sa.Column("resident_measurements_allowed", sa.Boolean(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("quality_policy_version", sa.String(length=255), nullable=False),
        sa.Column("quality_policy_test_only", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("monitoring_status_id"),
        sa.UniqueConstraint("tenant_id", "resident_id", "observed_at"),
    )
    op.create_index(
        "ix_monitoring_status_snapshots_tenant_id",
        "monitoring_status_snapshots",
        ["tenant_id"],
    )
    op.create_index(
        "ix_monitoring_status_snapshots_resident_id",
        "monitoring_status_snapshots",
        ["resident_id"],
    )
    op.create_index(
        "ix_monitoring_status_snapshots_room_id",
        "monitoring_status_snapshots",
        ["room_id"],
    )

    op.create_table(
        "calibration_snapshots",
        sa.Column("calibration_snapshot_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("resident_id", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("setup_version", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("eligible_windows", sa.Integer(), nullable=False),
        sa.Column("excluded_windows", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("prior_setup_versions", sa.JSON(), nullable=False),
        sa.Column("dimension_progress", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.resident_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "resident_id"],
            ["residents.tenant_id", "residents.resident_id"],
        ),
        sa.PrimaryKeyConstraint("calibration_snapshot_id"),
        sa.UniqueConstraint("tenant_id", "resident_id", "version"),
    )
    op.create_index(
        "ix_calibration_snapshots_tenant_id",
        "calibration_snapshots",
        ["tenant_id"],
    )
    op.create_index(
        "ix_calibration_snapshots_resident_id",
        "calibration_snapshots",
        ["resident_id"],
    )

    op.create_table(
        "monitoring_setup_changes",
        sa.Column("monitoring_setup_change_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("resident_id", sa.String(length=255), nullable=False),
        sa.Column("calibration_version", sa.Integer(), nullable=False),
        sa.Column("previous_setup_version", sa.String(length=255), nullable=False),
        sa.Column("new_setup_version", sa.String(length=255), nullable=False),
        sa.Column("affected_dimensions", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.resident_id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "resident_id"],
            ["residents.tenant_id", "residents.resident_id"],
        ),
        sa.PrimaryKeyConstraint("monitoring_setup_change_id"),
        sa.UniqueConstraint("tenant_id", "resident_id", "calibration_version"),
    )
    op.create_index(
        "ix_monitoring_setup_changes_tenant_id",
        "monitoring_setup_changes",
        ["tenant_id"],
    )
    op.create_index(
        "ix_monitoring_setup_changes_resident_id",
        "monitoring_setup_changes",
        ["resident_id"],
    )


def downgrade() -> None:
    op.drop_table("monitoring_setup_changes")
    op.drop_table("calibration_snapshots")
    op.drop_table("monitoring_status_snapshots")
