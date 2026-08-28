"""Add resident preference history and honest memory provenance."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004_preferences_memory_admin"
down_revision: str | None = "0003_device_health"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resident_notification_preference_versions",
        sa.Column(
            "preference_version_id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("resident_id", sa.String(length=255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("watch_delivery_enabled", sa.Boolean(), nullable=False),
        sa.Column("high_delivery_enabled", sa.Boolean(), nullable=False),
        sa.Column("critical_delivery_enabled", sa.Boolean(), nullable=False),
        sa.Column("away_awareness_enabled", sa.Boolean(), nullable=False),
        sa.Column("return_awareness_enabled", sa.Boolean(), nullable=False),
        sa.Column("limited_awareness_enabled", sa.Boolean(), nullable=False),
        sa.Column("unavailable_awareness_enabled", sa.Boolean(), nullable=False),
        sa.Column("changed_by", sa.String(length=255), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_resident_preference_version",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.resident_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "resident_id"],
            ["residents.tenant_id", "residents.resident_id"],
        ),
        sa.PrimaryKeyConstraint("preference_version_id"),
        sa.UniqueConstraint("tenant_id", "resident_id", "version"),
    )
    op.create_index(
        "ix_resident_notification_preference_versions_tenant_id",
        "resident_notification_preference_versions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_resident_notification_preference_versions_resident_id",
        "resident_notification_preference_versions",
        ["resident_id"],
    )

    with op.batch_alter_table("resident_memory_entries") as batch_op:
        batch_op.add_column(
            sa.Column(
                "source_kind",
                sa.String(length=64),
                nullable=False,
                server_default="feedback",
            )
        )
        batch_op.add_column(
            sa.Column("supersedes_entry_id", sa.String(length=255), nullable=True)
        )
        batch_op.alter_column(
            "source_feedback_id",
            existing_type=sa.String(length=255),
            nullable=True,
        )
        batch_op.create_check_constraint(
            "ck_resident_memory_entry_source",
            "(source_kind = 'feedback' AND source_feedback_id IS NOT NULL) OR "
            "(source_kind = 'operator' AND source_feedback_id IS NULL)",
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM resident_memory_entries WHERE source_feedback_id IS NULL"
    )
    with op.batch_alter_table("resident_memory_entries") as batch_op:
        batch_op.drop_constraint(
            "ck_resident_memory_entry_source",
            type_="check",
        )
        batch_op.alter_column(
            "source_feedback_id",
            existing_type=sa.String(length=255),
            nullable=False,
        )
        batch_op.drop_column("supersedes_entry_id")
        batch_op.drop_column("source_kind")
    op.drop_table("resident_notification_preference_versions")
