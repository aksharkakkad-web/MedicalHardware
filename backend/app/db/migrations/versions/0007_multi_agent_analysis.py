"""Persist canonical multi-agent analysis runs."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0007_multi_agent_analysis"
down_revision: str | None = "0006_monitoring_intelligence"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "multi_agent_analysis_runs",
        sa.Column("analysis_id", sa.String(255), nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("anomaly_id", sa.String(255), nullable=False),
        sa.Column("packet_revision", sa.Integer(), nullable=False),
        sa.Column("resident_id", sa.String(255), nullable=False),
        sa.Column("room_id", sa.String(255), nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("final_model_id", sa.String(255)),
        sa.Column("final_model_version", sa.String(255)),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "resident_id"],
            ["residents.tenant_id", "residents.resident_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "room_id"],
            ["rooms.tenant_id", "rooms.room_id"],
        ),
        sa.PrimaryKeyConstraint("tenant_id", "analysis_id"),
    )
    op.create_index(
        "ix_multi_agent_analysis_runs_tenant_id",
        "multi_agent_analysis_runs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_multi_agent_analysis_runs_state",
        "multi_agent_analysis_runs",
        ["state"],
    )
    op.create_index(
        "ix_multi_agent_analysis_anomaly_revision",
        "multi_agent_analysis_runs",
        ["anomaly_id", "packet_revision"],
    )
    naming_convention = {
        "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s"
    }
    with op.batch_alter_table(
        "disposition_decisions",
        naming_convention=naming_convention,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_disposition_decisions_tenant_id_anomaly_id_packet_revision_anomaly_revisions",
            type_="foreignkey",
        )
        batch_op.add_column(sa.Column("analysis_id", sa.String(255)))
        batch_op.create_foreign_key(
            "fk_disposition_multi_agent_analysis",
            "multi_agent_analysis_runs",
            ["tenant_id", "analysis_id"],
            ["tenant_id", "analysis_id"],
        )
    op.create_index(
        "ix_multi_agent_analysis_runs_resident_id",
        "multi_agent_analysis_runs",
        ["resident_id"],
    )
    op.create_index(
        "ix_multi_agent_analysis_runs_room_id",
        "multi_agent_analysis_runs",
        ["room_id"],
    )
    op.create_index(
        "ix_multi_agent_analysis_runs_input_fingerprint",
        "multi_agent_analysis_runs",
        ["input_fingerprint"],
    )


def downgrade() -> None:
    analysis_count = op.get_bind().scalar(
        sa.text("SELECT COUNT(*) FROM multi_agent_analysis_runs")
    )
    if analysis_count:
        raise RuntimeError(
            "Cannot downgrade while multi-agent analysis history exists; "
            "export or migrate that evidence before removing analysis support."
        )
    with op.batch_alter_table("disposition_decisions") as batch_op:
        batch_op.drop_constraint(
            "fk_disposition_multi_agent_analysis",
            type_="foreignkey",
        )
        batch_op.drop_column("analysis_id")
        batch_op.create_foreign_key(
            "fk_disposition_decisions_tenant_id_anomaly_id_packet_revision_anomaly_revisions",
            "anomaly_revisions",
            ["tenant_id", "anomaly_id", "packet_revision"],
            ["tenant_id", "anomaly_id", "packet_revision"],
        )
    op.drop_index(
        "ix_multi_agent_analysis_runs_input_fingerprint",
        table_name="multi_agent_analysis_runs",
    )
    op.drop_index(
        "ix_multi_agent_analysis_runs_room_id",
        table_name="multi_agent_analysis_runs",
    )
    op.drop_index(
        "ix_multi_agent_analysis_runs_resident_id",
        table_name="multi_agent_analysis_runs",
    )
    op.drop_index(
        "ix_multi_agent_analysis_anomaly_revision",
        table_name="multi_agent_analysis_runs",
    )
    op.drop_index(
        "ix_multi_agent_analysis_runs_state",
        table_name="multi_agent_analysis_runs",
    )
    op.drop_index(
        "ix_multi_agent_analysis_runs_tenant_id",
        table_name="multi_agent_analysis_runs",
    )
    op.drop_table("multi_agent_analysis_runs")
