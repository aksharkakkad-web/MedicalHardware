"""Persist immutable monitoring-intelligence evidence and decisions."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006_monitoring_intelligence"
down_revision: str | None = "0005_flexible_resident_context"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("monitoring_events") as batch_op:
        batch_op.create_unique_constraint(
            "uq_monitoring_events_tenant_event",
            ["tenant_id", "event_id"],
        )
        batch_op.add_column(sa.Column("source_anomaly_id", sa.String(255)))
        batch_op.add_column(sa.Column("latest_evidence_revision", sa.Integer()))
        batch_op.add_column(
            sa.Column("latest_provisional_evidence_revision", sa.Integer())
        )
        batch_op.add_column(
            sa.Column("attention_suppressed_until", sa.DateTime(timezone=True))
        )
        batch_op.add_column(
            sa.Column(
                "provisional_urgent",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "room_level_only",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "bridge_idempotency_keys",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            )
        )

    op.create_table(
        "baseline_snapshots",
        sa.Column("baseline_id", sa.String(255), nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("resident_id", sa.String(255), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("monitoring_setup_version", sa.String(255), nullable=False),
        sa.Column("policy_version", sa.String(255), nullable=False),
        sa.Column("prior_baseline_id", sa.String(255)),
        sa.Column("adoption_candidate_id", sa.String(255)),
        sa.Column("adoption_context_entry_id", sa.String(255)),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.resident_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "resident_id"],
            ["residents.tenant_id", "residents.resident_id"],
        ),
        sa.PrimaryKeyConstraint("tenant_id", "baseline_id"),
    )
    op.create_index("ix_baseline_snapshots_tenant_id", "baseline_snapshots", ["tenant_id"])
    op.create_index("ix_baseline_snapshots_resident_id", "baseline_snapshots", ["resident_id"])
    op.create_index("ix_baseline_snapshots_recorded_at", "baseline_snapshots", ["recorded_at"])

    op.create_table(
        "baseline_dimensions",
        sa.Column("baseline_dimension_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("baseline_id", sa.String(255), nullable=False),
        sa.Column("feature_name", sa.String(255), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("context_key", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "baseline_id"],
            ["baseline_snapshots.tenant_id", "baseline_snapshots.baseline_id"],
        ),
        sa.PrimaryKeyConstraint("baseline_dimension_id"),
        sa.UniqueConstraint("tenant_id", "baseline_id", "feature_name", "context_key"),
    )
    op.create_index("ix_baseline_dimensions_tenant_id", "baseline_dimensions", ["tenant_id"])
    op.create_index("ix_baseline_dimensions_baseline_id", "baseline_dimensions", ["baseline_id"])

    op.create_table(
        "anomaly_revisions",
        sa.Column("anomaly_revision_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("anomaly_id", sa.String(255), nullable=False),
        sa.Column("packet_revision", sa.Integer(), nullable=False),
        sa.Column("resident_id", sa.String(255), nullable=False),
        sa.Column("room_id", sa.String(255), nullable=False),
        sa.Column("baseline_id", sa.String(255), nullable=False),
        sa.Column("lifecycle_state", sa.String(64), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("update_json", sa.Text(), nullable=False),
        sa.Column("packet_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.resident_id"]),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.room_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "resident_id"],
            ["residents.tenant_id", "residents.resident_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "room_id"],
            ["rooms.tenant_id", "rooms.room_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "baseline_id"],
            ["baseline_snapshots.tenant_id", "baseline_snapshots.baseline_id"],
        ),
        sa.PrimaryKeyConstraint("anomaly_revision_id"),
        sa.UniqueConstraint("tenant_id", "anomaly_id", "packet_revision"),
    )
    op.create_index("ix_anomaly_revisions_tenant_id", "anomaly_revisions", ["tenant_id"])
    op.create_index("ix_anomaly_revisions_resident_id", "anomaly_revisions", ["resident_id"])
    op.create_index("ix_anomaly_revisions_room_id", "anomaly_revisions", ["room_id"])
    op.create_index("ix_anomaly_revisions_baseline_id", "anomaly_revisions", ["baseline_id"])
    op.create_index(
        "ix_anomaly_revisions_anomaly_revision",
        "anomaly_revisions",
        ["anomaly_id", "packet_revision"],
    )

    op.create_table(
        "llm_interpretations",
        sa.Column("interpretation_id", sa.String(255), nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("anomaly_id", sa.String(255), nullable=False),
        sa.Column("packet_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("model_id", sa.String(255), nullable=False),
        sa.Column("model_version", sa.String(255), nullable=False),
        sa.Column("prompt_version", sa.String(255), nullable=False),
        sa.Column("skill_bundle_version", sa.String(255), nullable=False),
        sa.Column("retrieval_contract_version", sa.String(255), nullable=False),
        sa.Column("output_schema_version", sa.String(255), nullable=False),
        sa.Column("relevant_context_version", sa.String(255), nullable=False),
        sa.Column("request_fingerprint", sa.String(255), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "anomaly_id", "packet_revision"],
            [
                "anomaly_revisions.tenant_id",
                "anomaly_revisions.anomaly_id",
                "anomaly_revisions.packet_revision",
            ],
        ),
        sa.PrimaryKeyConstraint("tenant_id", "interpretation_id"),
    )
    op.create_index("ix_llm_interpretations_tenant_id", "llm_interpretations", ["tenant_id"])
    op.create_index(
        "ix_llm_interpretations_request_fingerprint",
        "llm_interpretations",
        ["request_fingerprint"],
    )
    op.create_index(
        "ix_llm_interpretations_anomaly_revision",
        "llm_interpretations",
        ["anomaly_id", "packet_revision"],
    )

    op.create_table(
        "disposition_decisions",
        sa.Column("disposition_id", sa.String(255), nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("resident_id", sa.String(255), nullable=False),
        sa.Column("room_id", sa.String(255), nullable=False),
        sa.Column("anomaly_id", sa.String(255), nullable=False),
        sa.Column("evidence_kind", sa.String(64), nullable=False),
        sa.Column("evidence_revision", sa.Integer(), nullable=False),
        sa.Column("packet_revision", sa.Integer()),
        sa.Column("interpretation_id", sa.String(255)),
        sa.Column("event_id", sa.String(255)),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_version", sa.String(255), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.resident_id"]),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.room_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "resident_id"],
            ["residents.tenant_id", "residents.resident_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "room_id"],
            ["rooms.tenant_id", "rooms.room_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "anomaly_id", "packet_revision"],
            [
                "anomaly_revisions.tenant_id",
                "anomaly_revisions.anomaly_id",
                "anomaly_revisions.packet_revision",
            ],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "interpretation_id"],
            ["llm_interpretations.tenant_id", "llm_interpretations.interpretation_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["monitoring_events.tenant_id", "monitoring_events.event_id"],
        ),
        sa.PrimaryKeyConstraint("tenant_id", "disposition_id"),
        sa.CheckConstraint(
            "evidence_revision >= 1 AND ((evidence_kind = 'packet' "
            "AND packet_revision IS NOT NULL "
            "AND evidence_revision = packet_revision) OR "
            "(evidence_kind = 'provisional' AND packet_revision IS NULL))",
            name="ck_disposition_decisions_evidence_source",
        ),
    )
    op.create_index("ix_disposition_decisions_tenant_id", "disposition_decisions", ["tenant_id"])
    op.create_index(
        "ix_disposition_decisions_resident_id",
        "disposition_decisions",
        ["resident_id"],
    )
    op.create_index("ix_disposition_decisions_room_id", "disposition_decisions", ["room_id"])
    op.create_index("ix_disposition_decisions_event_id", "disposition_decisions", ["event_id"])
    op.create_index(
        "ix_disposition_decisions_anomaly_revision",
        "disposition_decisions",
        ["anomaly_id", "packet_revision"],
    )

    op.create_table(
        "event_bridge_records",
        sa.Column("event_bridge_record_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("idempotency_key", sa.String(500), nullable=False),
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("resident_id", sa.String(255), nullable=False),
        sa.Column("room_id", sa.String(255), nullable=False),
        sa.Column("source_anomaly_id", sa.String(255), nullable=False),
        sa.Column("evidence_revision", sa.Integer(), nullable=False),
        sa.Column("evidence_kind", sa.String(64), nullable=False),
        sa.Column("priority", sa.String(64), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(["resident_id"], ["residents.resident_id"]),
        sa.ForeignKeyConstraint(["room_id"], ["rooms.room_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "event_id"],
            ["monitoring_events.tenant_id", "monitoring_events.event_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "resident_id"],
            ["residents.tenant_id", "residents.resident_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "room_id"],
            ["rooms.tenant_id", "rooms.room_id"],
        ),
        sa.PrimaryKeyConstraint("event_bridge_record_id"),
        sa.UniqueConstraint("tenant_id", "idempotency_key"),
    )
    op.create_index("ix_event_bridge_records_tenant_id", "event_bridge_records", ["tenant_id"])
    op.create_index("ix_event_bridge_records_event_id", "event_bridge_records", ["event_id"])
    op.create_index(
        "ix_event_bridge_records_anomaly_revision",
        "event_bridge_records",
        ["source_anomaly_id", "evidence_revision"],
    )


def downgrade() -> None:
    op.drop_table("event_bridge_records")
    op.drop_table("disposition_decisions")
    op.drop_table("llm_interpretations")
    op.drop_table("anomaly_revisions")
    op.drop_table("baseline_dimensions")
    op.drop_table("baseline_snapshots")
    with op.batch_alter_table("monitoring_events") as batch_op:
        batch_op.drop_column("bridge_idempotency_keys")
        batch_op.drop_column("room_level_only")
        batch_op.drop_column("provisional_urgent")
        batch_op.drop_column("attention_suppressed_until")
        batch_op.drop_column("latest_provisional_evidence_revision")
        batch_op.drop_column("latest_evidence_revision")
        batch_op.drop_column("source_anomaly_id")
        batch_op.drop_constraint("uq_monitoring_events_tenant_event", type_="unique")
