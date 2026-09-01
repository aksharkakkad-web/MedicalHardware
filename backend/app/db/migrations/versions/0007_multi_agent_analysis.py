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
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("final_model_id", sa.String(255)),
        sa.Column("final_model_version", sa.String(255)),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "anomaly_id", "packet_revision"],
            [
                "anomaly_revisions.tenant_id",
                "anomaly_revisions.anomaly_id",
                "anomaly_revisions.packet_revision",
            ],
        ),
        sa.PrimaryKeyConstraint("tenant_id", "analysis_id"),
        sa.UniqueConstraint("tenant_id", "anomaly_id", "packet_revision"),
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


def downgrade() -> None:
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
