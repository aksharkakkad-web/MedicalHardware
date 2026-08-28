"""Add flexible semantic context to resident memory entries."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005_flexible_resident_context"
down_revision: str | None = "0004_preferences_memory_admin"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("resident_memory_entries") as batch_op:
        batch_op.add_column(
            sa.Column("context_kind", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("local_time_start", sa.String(length=5), nullable=True)
        )
        batch_op.add_column(
            sa.Column("local_time_end", sa.String(length=5), nullable=True)
        )
        batch_op.add_column(
            sa.Column("recurrence_note", sa.String(length=1000), nullable=True)
        )
        batch_op.add_column(
            sa.Column("flexibility_note", sa.String(length=1000), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("resident_memory_entries") as batch_op:
        batch_op.drop_column("flexibility_note")
        batch_op.drop_column("recurrence_note")
        batch_op.drop_column("local_time_end")
        batch_op.drop_column("local_time_start")
        batch_op.drop_column("effective_until")
        batch_op.drop_column("effective_from")
        batch_op.drop_column("context_kind")
