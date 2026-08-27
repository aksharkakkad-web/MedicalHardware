"""Add durable device assignment and operational health history."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_device_health"
down_revision: str | None = "0002_status_calibration"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("location_id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("location_id"),
        sa.UniqueConstraint("tenant_id", "location_id"),
    )
    op.create_index("ix_locations_tenant_id", "locations", ["tenant_id"])

    op.create_table(
        "devices",
        sa.Column("device_id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("display_label", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.PrimaryKeyConstraint("device_id"),
        sa.UniqueConstraint("tenant_id", "device_id"),
    )
    op.create_index("ix_devices_tenant_id", "devices", ["tenant_id"])

    op.create_table(
        "device_room_assignments",
        sa.Column("assignment_id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=False),
        sa.Column("location_id", sa.String(length=255), nullable=False),
        sa.Column("room_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.location_id"]),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.room_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "device_id"],
            ["devices.tenant_id", "devices.device_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "location_id"],
            ["locations.tenant_id", "locations.location_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "room_id"],
            ["rooms.tenant_id", "rooms.room_id"],
        ),
        sa.PrimaryKeyConstraint("assignment_id"),
    )
    op.create_index(
        "ix_device_room_assignments_tenant_id",
        "device_room_assignments",
        ["tenant_id"],
    )
    op.create_index(
        "ix_device_room_assignments_device_id",
        "device_room_assignments",
        ["device_id"],
    )
    op.create_index(
        "ix_device_room_assignments_location_id",
        "device_room_assignments",
        ["location_id"],
    )
    op.create_index(
        "ix_device_room_assignments_room_id",
        "device_room_assignments",
        ["room_id"],
    )
    op.create_index(
        "uq_active_device_room_assignment",
        "device_room_assignments",
        ["tenant_id", "device_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "uq_active_room_device_assignment",
        "device_room_assignments",
        ["tenant_id", "room_id"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "device_health_observations",
        sa.Column(
            "device_health_observation_id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("policy_version", sa.String(length=255), nullable=False),
        sa.Column("policy_test_only", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "device_id"],
            ["devices.tenant_id", "devices.device_id"],
        ),
        sa.PrimaryKeyConstraint("device_health_observation_id"),
    )
    op.create_index(
        "ix_device_health_observations_tenant_id",
        "device_health_observations",
        ["tenant_id"],
    )
    op.create_index(
        "ix_device_health_observations_device_id",
        "device_health_observations",
        ["device_id"],
    )


def downgrade() -> None:
    op.drop_table("device_health_observations")
    op.drop_table("device_room_assignments")
    op.drop_table("devices")
    op.drop_table("locations")
