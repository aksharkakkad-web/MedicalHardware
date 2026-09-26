"""Add durable edge telemetry ingestion and replay records."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008_edge_telemetry_ingestion"
down_revision: str | None = "0007_multi_agent_analysis"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telemetry_capture_batches",
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("batch_id", sa.String(255), nullable=False),
        sa.Column("device_id", sa.String(255), nullable=False),
        sa.Column("room_id", sa.String(255), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processing_state", sa.String(64), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.Column("processing_error", sa.String(500)),
        sa.CheckConstraint(
            "processing_state IN ('pending', 'processing', 'processed', "
            "'calibrating', 'blocked', 'failed')",
            name="ck_telemetry_capture_processing_state",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "device_id"],
            ["devices.tenant_id", "devices.device_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "room_id"],
            ["rooms.tenant_id", "rooms.room_id"],
        ),
        sa.PrimaryKeyConstraint("tenant_id", "batch_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "request_fingerprint",
            name="uq_telemetry_capture_fingerprint",
        ),
    )
    for name, columns in (
        ("ix_telemetry_capture_batches_device_id", ["device_id"]),
        ("ix_telemetry_capture_batches_room_id", ["room_id"]),
        ("ix_telemetry_capture_batches_received_at", ["received_at"]),
        ("ix_telemetry_capture_batches_processing_state", ["processing_state"]),
    ):
        op.create_index(name, "telemetry_capture_batches", columns)

    op.create_table(
        "edge_telemetry",
        sa.Column("telemetry_id", sa.String(255), nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("batch_id", sa.String(255), nullable=False),
        sa.Column("device_id", sa.String(255), nullable=False),
        sa.Column("room_id", sa.String(255), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("sensor_model", sa.String(255), nullable=False),
        sa.Column("stream_id", sa.String(255), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("sequence_gap", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(64), nullable=False),
        sa.Column("device_time", sa.DateTime(timezone=True)),
        sa.Column("device_monotonic_ms", sa.Integer()),
        sa.Column("payload_format", sa.String(255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("quality_reasons", sa.JSON(), nullable=False),
        sa.Column("transport", sa.JSON(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sequence >= 1", name="ck_edge_telemetry_sequence"),
        sa.CheckConstraint("sequence_gap >= 0", name="ck_edge_telemetry_sequence_gap"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "batch_id"],
            [
                "telemetry_capture_batches.tenant_id",
                "telemetry_capture_batches.batch_id",
            ],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "device_id"],
            ["devices.tenant_id", "devices.device_id"],
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "room_id"],
            ["rooms.tenant_id", "rooms.room_id"],
        ),
        sa.PrimaryKeyConstraint("telemetry_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "device_id",
            "source",
            "stream_id",
            "sequence",
            "schema_version",
            name="uq_edge_telemetry_packet_identity",
        ),
    )
    for name, columns in (
        ("ix_edge_telemetry_tenant_id", ["tenant_id"]),
        ("ix_edge_telemetry_batch_id", ["batch_id"]),
        ("ix_edge_telemetry_device_id", ["device_id"]),
        ("ix_edge_telemetry_room_id", ["room_id"]),
        ("ix_edge_telemetry_source", ["source"]),
    ):
        op.create_index(name, "edge_telemetry", columns)

    op.create_table(
        "normalized_observations",
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("observation_id", sa.String(255), nullable=False),
        sa.Column("batch_id", sa.String(255), nullable=False),
        sa.Column("observation", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "batch_id"],
            [
                "telemetry_capture_batches.tenant_id",
                "telemetry_capture_batches.batch_id",
            ],
        ),
        sa.PrimaryKeyConstraint("tenant_id", "observation_id"),
    )
    op.create_index(
        "ix_normalized_observations_batch_id",
        "normalized_observations",
        ["batch_id"],
    )

    op.create_table(
        "fused_frames",
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("frame_id", sa.String(255), nullable=False),
        sa.Column("batch_id", sa.String(255), nullable=False),
        sa.Column("frame", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "batch_id"],
            [
                "telemetry_capture_batches.tenant_id",
                "telemetry_capture_batches.batch_id",
            ],
        ),
        sa.PrimaryKeyConstraint("tenant_id", "frame_id"),
        sa.UniqueConstraint("tenant_id", "batch_id", name="uq_fused_frame_batch"),
    )
    op.create_index("ix_fused_frames_batch_id", "fused_frames", ["batch_id"])

    op.create_table(
        "device_heartbeat_identities",
        sa.Column("heartbeat_identity_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=False),
        sa.Column("device_id", sa.String(255), nullable=False),
        sa.Column("stream_id", sa.String(255), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"]),
        sa.ForeignKeyConstraint(
            ["tenant_id", "device_id"],
            ["devices.tenant_id", "devices.device_id"],
        ),
        sa.PrimaryKeyConstraint("heartbeat_identity_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "device_id",
            "stream_id",
            "sequence",
            name="uq_device_heartbeat_identity",
        ),
    )
    op.create_index(
        "ix_device_heartbeat_identities_tenant_id",
        "device_heartbeat_identities",
        ["tenant_id"],
    )
    op.create_index(
        "ix_device_heartbeat_identities_device_id",
        "device_heartbeat_identities",
        ["device_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_device_heartbeat_identities_device_id",
        table_name="device_heartbeat_identities",
    )
    op.drop_index(
        "ix_device_heartbeat_identities_tenant_id",
        table_name="device_heartbeat_identities",
    )
    op.drop_table("device_heartbeat_identities")
    op.drop_index("ix_fused_frames_batch_id", table_name="fused_frames")
    op.drop_table("fused_frames")
    op.drop_index(
        "ix_normalized_observations_batch_id",
        table_name="normalized_observations",
    )
    op.drop_table("normalized_observations")
    for name in (
        "ix_edge_telemetry_source",
        "ix_edge_telemetry_room_id",
        "ix_edge_telemetry_device_id",
        "ix_edge_telemetry_batch_id",
        "ix_edge_telemetry_tenant_id",
    ):
        op.drop_index(name, table_name="edge_telemetry")
    op.drop_table("edge_telemetry")
    for name in (
        "ix_telemetry_capture_batches_processing_state",
        "ix_telemetry_capture_batches_received_at",
        "ix_telemetry_capture_batches_room_id",
        "ix_telemetry_capture_batches_device_id",
    ):
        op.drop_index(name, table_name="telemetry_capture_batches")
    op.drop_table("telemetry_capture_batches")
