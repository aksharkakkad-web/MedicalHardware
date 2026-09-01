from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.repositories import FeedbackRepository


EXPECTED_TABLES = {
    "tenants",
    "rooms",
    "residents",
    "room_resident_assignments",
    "monitoring_events",
    "event_actions",
    "event_priority_history",
    "feedback_records",
    "resident_memory_snapshots",
    "resident_memory_entries",
    "resident_notification_preference_versions",
    "idempotency_records",
    "audit_log",
    "monitoring_status_snapshots",
    "calibration_snapshots",
    "monitoring_setup_changes",
    "locations",
    "devices",
    "device_room_assignments",
    "device_health_observations",
    "baseline_snapshots",
    "baseline_dimensions",
    "anomaly_revisions",
    "llm_interpretations",
    "disposition_decisions",
    "event_bridge_records",
    "multi_agent_analysis_runs",
}

EXPECTED_COLUMNS = {
    "tenants": {"tenant_id": False},
    "rooms": {"room_id": False, "tenant_id": False, "label": False},
    "residents": {"resident_id": False, "tenant_id": False, "display_label": False},
    "room_resident_assignments": {
        "assignment_id": False,
        "tenant_id": False,
        "room_id": False,
        "resident_id": False,
        "status": False,
        "effective_from": False,
        "effective_to": True,
    },
    "monitoring_events": {
        "event_id": False,
        "tenant_id": False,
        "episode_id": False,
        "resident_id": False,
        "room_id": False,
        "objective_family": False,
        "headline": False,
        "priority": False,
        "status": False,
        "created_at": False,
        "last_signal_at": False,
        "signal_count": False,
        "related_event_ids": False,
        "recurrence_count": False,
        "overdue_at": True,
        "resolution_outcome": True,
        "episode_policy_version": False,
        "episode_policy_test_only": False,
        "resident_memory_version": True,
        "resident_memory_entry_ids": False,
        "source_anomaly_id": True,
        "latest_evidence_revision": True,
        "latest_provisional_evidence_revision": True,
        "attention_suppressed_until": True,
        "provisional_urgent": False,
        "room_level_only": False,
        "bridge_idempotency_keys": False,
        "version": False,
    },
    "event_actions": {
        "action_id": False,
        "tenant_id": False,
        "event_id": False,
        "sequence": False,
        "action": False,
        "actor_id": False,
        "occurred_at": False,
        "previous_status": False,
        "status": False,
        "resolution_outcome": True,
    },
    "event_priority_history": {
        "priority_history_id": False,
        "tenant_id": False,
        "event_id": False,
        "sequence": False,
        "previous_priority": True,
        "priority": False,
        "actor_id": False,
        "changed_at": False,
    },
    "feedback_records": {
        "feedback_id": False,
        "tenant_id": False,
        "event_id": False,
        "resident_id": False,
        "actor_id": False,
        "outcome": False,
        "actual_event_label": False,
        "routine": False,
        "created_at": False,
        "memory_updated": False,
        "baseline_window_eligible": False,
        "global_label_recorded": False,
    },
    "resident_memory_snapshots": {
        "memory_snapshot_id": False,
        "tenant_id": False,
        "resident_id": False,
        "version": False,
        "created_at": False,
    },
    "resident_memory_entries": {
        "memory_entry_row_id": False,
        "entry_id": False,
        "tenant_id": False,
        "resident_id": False,
        "memory_version": False,
        "description": False,
        "source_kind": False,
        "source_feedback_id": True,
        "supersedes_entry_id": True,
        "status": False,
        "created_by": False,
        "created_at": False,
        "retired_by": True,
        "retired_at": True,
        "retirement_reason": True,
        "context_kind": True,
        "effective_from": True,
        "effective_until": True,
        "local_time_start": True,
        "local_time_end": True,
        "recurrence_note": True,
        "flexibility_note": True,
    },
    "idempotency_records": {
        "idempotency_id": False,
        "tenant_id": False,
        "actor_id": False,
        "key": False,
        "request_fingerprint": False,
        "response_status": False,
        "response_body": False,
        "created_at": False,
    },
    "audit_log": {
        "audit_id": False,
        "tenant_id": False,
        "actor_id": False,
        "action": False,
        "target_type": False,
        "target_id": False,
        "occurred_at": False,
        "details": False,
    },
    "resident_notification_preference_versions": {
        "preference_version_id": False,
        "tenant_id": False,
        "resident_id": False,
        "version": False,
        "watch_delivery_enabled": False,
        "high_delivery_enabled": False,
        "critical_delivery_enabled": False,
        "away_awareness_enabled": False,
        "return_awareness_enabled": False,
        "limited_awareness_enabled": False,
        "unavailable_awareness_enabled": False,
        "changed_by": False,
        "changed_at": False,
    },
    "monitoring_status_snapshots": {
        "monitoring_status_id": False,
        "tenant_id": False,
        "resident_id": False,
        "room_id": False,
        "observed_at": False,
        "monitoring_state": False,
        "presence_state": False,
        "baseline_learning_allowed": False,
        "resident_measurements_allowed": False,
        "reasons": False,
        "quality_policy_version": False,
        "quality_policy_test_only": False,
    },
    "calibration_snapshots": {
        "calibration_snapshot_id": False,
        "tenant_id": False,
        "resident_id": False,
        "version": False,
        "recorded_at": False,
        "setup_version": False,
        "status": False,
        "eligible_windows": False,
        "excluded_windows": False,
        "reason": False,
        "prior_setup_versions": False,
        "dimension_progress": False,
    },
    "monitoring_setup_changes": {
        "monitoring_setup_change_id": False,
        "tenant_id": False,
        "resident_id": False,
        "calibration_version": False,
        "previous_setup_version": False,
        "new_setup_version": False,
        "affected_dimensions": False,
        "reason": False,
        "actor_id": False,
        "changed_at": False,
    },
    "locations": {
        "location_id": False,
        "tenant_id": False,
        "label": False,
    },
    "devices": {
        "device_id": False,
        "tenant_id": False,
        "display_label": False,
    },
    "device_room_assignments": {
        "assignment_id": False,
        "tenant_id": False,
        "device_id": False,
        "location_id": False,
        "room_id": False,
        "status": False,
        "effective_from": False,
        "effective_to": True,
    },
    "device_health_observations": {
        "device_health_observation_id": False,
        "tenant_id": False,
        "device_id": False,
        "observed_at": False,
        "last_seen_at": True,
        "state": False,
        "sources": False,
        "limitations": False,
        "policy_version": False,
        "policy_test_only": False,
    },
    "baseline_snapshots": {
        "baseline_id": False,
        "tenant_id": False,
        "resident_id": False,
        "recorded_at": False,
        "monitoring_setup_version": False,
        "policy_version": False,
        "prior_baseline_id": True,
        "adoption_candidate_id": True,
        "adoption_context_entry_id": True,
        "schema_version": False,
        "payload_json": False,
    },
    "baseline_dimensions": {
        "baseline_dimension_id": False,
        "tenant_id": False,
        "baseline_id": False,
        "feature_name": False,
        "purpose": False,
        "context_key": False,
        "unit": False,
        "payload_json": False,
    },
    "anomaly_revisions": {
        "anomaly_revision_id": False,
        "tenant_id": False,
        "anomaly_id": False,
        "packet_revision": False,
        "resident_id": False,
        "room_id": False,
        "baseline_id": False,
        "lifecycle_state": False,
        "recorded_at": False,
        "update_json": False,
        "packet_json": False,
    },
    "llm_interpretations": {
        "interpretation_id": False,
        "tenant_id": False,
        "anomaly_id": False,
        "packet_revision": False,
        "status": False,
        "created_at": False,
        "model_id": False,
        "model_version": False,
        "prompt_version": False,
        "skill_bundle_version": False,
        "retrieval_contract_version": False,
        "output_schema_version": False,
        "relevant_context_version": False,
        "request_fingerprint": False,
        "request_json": False,
        "result_json": False,
    },
    "multi_agent_analysis_runs": {
        "analysis_id": False,
        "tenant_id": False,
        "anomaly_id": False,
        "packet_revision": False,
        "state": False,
        "recorded_at": False,
        "final_model_id": True,
        "final_model_version": True,
        "schema_version": False,
        "payload_json": False,
    },
    "disposition_decisions": {
        "disposition_id": False,
        "tenant_id": False,
        "resident_id": False,
        "room_id": False,
        "anomaly_id": False,
        "evidence_kind": False,
        "evidence_revision": False,
        "packet_revision": True,
        "interpretation_id": True,
        "event_id": True,
        "status": False,
        "decided_at": False,
        "policy_version": False,
        "payload_json": False,
    },
    "event_bridge_records": {
        "event_bridge_record_id": False,
        "tenant_id": False,
        "idempotency_key": False,
        "event_id": False,
        "resident_id": False,
        "room_id": False,
        "source_anomaly_id": False,
        "evidence_revision": False,
        "evidence_kind": False,
        "priority": False,
        "observed_at": False,
        "payload_json": False,
    },
}

EXPECTED_PRIMARY_KEYS = {
    "tenants": ("tenant_id",),
    "rooms": ("room_id",),
    "residents": ("resident_id",),
    "room_resident_assignments": ("assignment_id",),
    "monitoring_events": ("event_id",),
    "event_actions": ("action_id",),
    "event_priority_history": ("priority_history_id",),
    "feedback_records": ("feedback_id",),
    "resident_memory_snapshots": ("memory_snapshot_id",),
    "resident_memory_entries": ("memory_entry_row_id",),
    "idempotency_records": ("idempotency_id",),
    "audit_log": ("audit_id",),
    "monitoring_status_snapshots": ("monitoring_status_id",),
    "calibration_snapshots": ("calibration_snapshot_id",),
    "monitoring_setup_changes": ("monitoring_setup_change_id",),
    "locations": ("location_id",),
    "devices": ("device_id",),
    "device_room_assignments": ("assignment_id",),
    "device_health_observations": ("device_health_observation_id",),
    "resident_notification_preference_versions": ("preference_version_id",),
    "baseline_snapshots": ("tenant_id", "baseline_id"),
    "baseline_dimensions": ("baseline_dimension_id",),
    "anomaly_revisions": ("anomaly_revision_id",),
    "llm_interpretations": ("tenant_id", "interpretation_id"),
    "multi_agent_analysis_runs": ("tenant_id", "analysis_id"),
    "disposition_decisions": ("tenant_id", "disposition_id"),
    "event_bridge_records": ("event_bridge_record_id",),
}

EXPECTED_FOREIGN_KEYS = {
    "rooms": {("tenant_id", "tenants", "tenant_id")},
    "residents": {("tenant_id", "tenants", "tenant_id")},
    "room_resident_assignments": {
        ("tenant_id", "tenants", "tenant_id"),
        ("tenant_id", "rooms", "tenant_id"),
        ("tenant_id", "residents", "tenant_id"),
        ("room_id", "rooms", "room_id"),
        ("resident_id", "residents", "resident_id"),
    },
    "monitoring_events": {
        ("tenant_id", "tenants", "tenant_id"),
        ("tenant_id", "rooms", "tenant_id"),
        ("tenant_id", "residents", "tenant_id"),
        ("resident_id", "residents", "resident_id"),
        ("room_id", "rooms", "room_id"),
    },
    "event_actions": {
        ("tenant_id", "tenants", "tenant_id"),
        ("event_id", "monitoring_events", "event_id"),
    },
    "event_priority_history": {
        ("tenant_id", "tenants", "tenant_id"),
        ("event_id", "monitoring_events", "event_id"),
    },
    "feedback_records": {
        ("tenant_id", "tenants", "tenant_id"),
        ("event_id", "monitoring_events", "event_id"),
        ("resident_id", "residents", "resident_id"),
    },
    "resident_memory_snapshots": {
        ("tenant_id", "tenants", "tenant_id"),
        ("resident_id", "residents", "resident_id"),
    },
    "resident_memory_entries": {
        ("tenant_id", "tenants", "tenant_id"),
        ("resident_id", "residents", "resident_id"),
        ("source_feedback_id", "feedback_records", "feedback_id"),
    },
    "idempotency_records": {("tenant_id", "tenants", "tenant_id")},
    "audit_log": {("tenant_id", "tenants", "tenant_id")},
    "resident_notification_preference_versions": {
        ("tenant_id", "tenants", "tenant_id"),
        ("resident_id", "residents", "resident_id"),
        ("tenant_id", "residents", "tenant_id"),
    },
    "monitoring_status_snapshots": {
        ("tenant_id", "tenants", "tenant_id"),
        ("tenant_id", "rooms", "tenant_id"),
        ("tenant_id", "residents", "tenant_id"),
        ("room_id", "rooms", "room_id"),
        ("resident_id", "residents", "resident_id"),
    },
    "calibration_snapshots": {
        ("tenant_id", "tenants", "tenant_id"),
        ("tenant_id", "residents", "tenant_id"),
        ("resident_id", "residents", "resident_id"),
    },
    "monitoring_setup_changes": {
        ("tenant_id", "tenants", "tenant_id"),
        ("tenant_id", "residents", "tenant_id"),
        ("resident_id", "residents", "resident_id"),
    },
    "locations": {("tenant_id", "tenants", "tenant_id")},
    "devices": {("tenant_id", "tenants", "tenant_id")},
    "device_room_assignments": {
        ("tenant_id", "tenants", "tenant_id"),
        ("tenant_id", "devices", "tenant_id"),
        ("tenant_id", "locations", "tenant_id"),
        ("tenant_id", "rooms", "tenant_id"),
        ("device_id", "devices", "device_id"),
        ("location_id", "locations", "location_id"),
        ("room_id", "rooms", "room_id"),
    },
    "device_health_observations": {
        ("tenant_id", "tenants", "tenant_id"),
        ("tenant_id", "devices", "tenant_id"),
        ("device_id", "devices", "device_id"),
    },
    "baseline_snapshots": {
        ("tenant_id", "tenants", "tenant_id"),
        ("tenant_id", "residents", "tenant_id"),
        ("resident_id", "residents", "resident_id"),
    },
    "baseline_dimensions": {
        ("tenant_id", "tenants", "tenant_id"),
        ("tenant_id", "baseline_snapshots", "tenant_id"),
    },
    "anomaly_revisions": {
        ("tenant_id", "tenants", "tenant_id"),
        ("tenant_id", "residents", "tenant_id"),
        ("tenant_id", "rooms", "tenant_id"),
        ("tenant_id", "baseline_snapshots", "tenant_id"),
        ("resident_id", "residents", "resident_id"),
        ("room_id", "rooms", "room_id"),
    },
    "llm_interpretations": {
        ("tenant_id", "tenants", "tenant_id"),
        ("tenant_id", "anomaly_revisions", "tenant_id"),
    },
    "multi_agent_analysis_runs": {
        ("tenant_id", "tenants", "tenant_id"),
        ("tenant_id", "anomaly_revisions", "tenant_id"),
    },
    "disposition_decisions": {
        ("tenant_id", "tenants", "tenant_id"),
        ("tenant_id", "residents", "tenant_id"),
        ("tenant_id", "rooms", "tenant_id"),
        ("tenant_id", "anomaly_revisions", "tenant_id"),
        ("tenant_id", "llm_interpretations", "tenant_id"),
        ("tenant_id", "monitoring_events", "tenant_id"),
        ("resident_id", "residents", "resident_id"),
        ("room_id", "rooms", "room_id"),
    },
    "event_bridge_records": {
        ("tenant_id", "tenants", "tenant_id"),
        ("tenant_id", "monitoring_events", "tenant_id"),
        ("tenant_id", "residents", "tenant_id"),
        ("tenant_id", "rooms", "tenant_id"),
        ("resident_id", "residents", "resident_id"),
        ("room_id", "rooms", "room_id"),
    },
}

EXPECTED_UNIQUES = {
    "rooms": {("tenant_id", "room_id")},
    "residents": {("tenant_id", "resident_id")},
    "event_actions": {("event_id", "sequence")},
    "event_priority_history": {("event_id", "sequence")},
    "feedback_records": {("tenant_id", "event_id")},
    "resident_memory_snapshots": {("resident_id", "version")},
    "resident_memory_entries": {("tenant_id", "resident_id", "memory_version", "entry_id")},
    "idempotency_records": {("tenant_id", "actor_id", "key")},
    "monitoring_status_snapshots": {
        ("tenant_id", "resident_id", "observed_at"),
    },
    "calibration_snapshots": {("tenant_id", "resident_id", "version")},
    "monitoring_setup_changes": {
        ("tenant_id", "resident_id", "calibration_version"),
    },
    "locations": {("tenant_id", "location_id")},
    "devices": {("tenant_id", "device_id")},
    "resident_notification_preference_versions": {
        ("tenant_id", "resident_id", "version")
    },
    "monitoring_events": {("tenant_id", "event_id")},
    "baseline_snapshots": set(),
    "baseline_dimensions": {
        ("tenant_id", "baseline_id", "feature_name", "context_key")
    },
    "anomaly_revisions": {("tenant_id", "anomaly_id", "packet_revision")},
    "llm_interpretations": set(),
    "multi_agent_analysis_runs": {
        ("tenant_id", "anomaly_id", "packet_revision")
    },
    "disposition_decisions": set(),
    "event_bridge_records": {("tenant_id", "idempotency_key")},
}

EXPECTED_INDEXES = {
    "rooms": {("tenant_id",)},
    "residents": {("tenant_id",)},
    "room_resident_assignments": {
        ("tenant_id",),
        ("room_id",),
        ("resident_id",),
        ("tenant_id", "room_id"),
        ("tenant_id", "resident_id"),
    },
    "monitoring_events": {("tenant_id",), ("episode_id",), ("resident_id",), ("room_id",)},
    "event_actions": {("tenant_id",), ("event_id",)},
    "event_priority_history": {("tenant_id",), ("event_id",)},
    "feedback_records": {("tenant_id",), ("event_id",), ("resident_id",)},
    "resident_memory_snapshots": {("tenant_id",), ("resident_id",)},
    "resident_memory_entries": {("tenant_id",), ("resident_id",), ("source_feedback_id",)},
    "idempotency_records": {("tenant_id",)},
    "audit_log": {("tenant_id",)},
    "monitoring_status_snapshots": {
        ("tenant_id",),
        ("resident_id",),
        ("room_id",),
    },
    "calibration_snapshots": {("tenant_id",), ("resident_id",)},
    "monitoring_setup_changes": {("tenant_id",), ("resident_id",)},
    "locations": {("tenant_id",)},
    "devices": {("tenant_id",)},
    "device_room_assignments": {
        ("tenant_id",),
        ("device_id",),
        ("location_id",),
        ("room_id",),
        ("tenant_id", "device_id"),
        ("tenant_id", "room_id"),
    },
    "device_health_observations": {("tenant_id",), ("device_id",)},
    "resident_notification_preference_versions": {
        ("tenant_id",),
        ("resident_id",),
    },
    "baseline_snapshots": {("tenant_id",), ("resident_id",), ("recorded_at",)},
    "baseline_dimensions": {("tenant_id",), ("baseline_id",)},
    "anomaly_revisions": {
        ("tenant_id",),
        ("resident_id",),
        ("room_id",),
        ("baseline_id",),
        ("anomaly_id", "packet_revision"),
    },
    "llm_interpretations": {
        ("tenant_id",),
        ("anomaly_id", "packet_revision"),
        ("request_fingerprint",),
    },
    "multi_agent_analysis_runs": {
        ("tenant_id",),
        ("state",),
        ("anomaly_id", "packet_revision"),
    },
    "disposition_decisions": {
        ("tenant_id",),
        ("resident_id",),
        ("room_id",),
        ("anomaly_id", "packet_revision"),
        ("event_id",),
    },
    "event_bridge_records": {
        ("tenant_id",),
        ("event_id",),
        ("source_anomaly_id", "evidence_revision"),
    },
}

EXPECTED_COMPOSITE_OWNERSHIP_FOREIGN_KEYS = {
    "room_resident_assignments": {
        (("tenant_id", "room_id"), "rooms", ("tenant_id", "room_id")),
        (
            ("tenant_id", "resident_id"),
            "residents",
            ("tenant_id", "resident_id"),
        ),
    },
    "monitoring_events": {
        (("tenant_id", "room_id"), "rooms", ("tenant_id", "room_id")),
        (
            ("tenant_id", "resident_id"),
            "residents",
            ("tenant_id", "resident_id"),
        ),
    },
    "monitoring_status_snapshots": {
        (("tenant_id", "room_id"), "rooms", ("tenant_id", "room_id")),
        (
            ("tenant_id", "resident_id"),
            "residents",
            ("tenant_id", "resident_id"),
        ),
    },
    "calibration_snapshots": {
        (
            ("tenant_id", "resident_id"),
            "residents",
            ("tenant_id", "resident_id"),
        ),
    },
    "monitoring_setup_changes": {
        (
            ("tenant_id", "resident_id"),
            "residents",
            ("tenant_id", "resident_id"),
        ),
    },
    "device_room_assignments": {
        (("tenant_id", "device_id"), "devices", ("tenant_id", "device_id")),
        (
            ("tenant_id", "location_id"),
            "locations",
            ("tenant_id", "location_id"),
        ),
        (("tenant_id", "room_id"), "rooms", ("tenant_id", "room_id")),
    },
    "device_health_observations": {
        (("tenant_id", "device_id"), "devices", ("tenant_id", "device_id")),
    },
    "resident_notification_preference_versions": {
        (
            ("tenant_id", "resident_id"),
            "residents",
            ("tenant_id", "resident_id"),
        ),
    },
    "baseline_snapshots": {
        (("tenant_id", "resident_id"), "residents", ("tenant_id", "resident_id")),
    },
    "baseline_dimensions": {
        (("tenant_id", "baseline_id"), "baseline_snapshots", ("tenant_id", "baseline_id")),
    },
    "anomaly_revisions": {
        (("tenant_id", "resident_id"), "residents", ("tenant_id", "resident_id")),
        (("tenant_id", "room_id"), "rooms", ("tenant_id", "room_id")),
        (("tenant_id", "baseline_id"), "baseline_snapshots", ("tenant_id", "baseline_id")),
    },
    "llm_interpretations": {
        (
            ("tenant_id", "anomaly_id", "packet_revision"),
            "anomaly_revisions",
            ("tenant_id", "anomaly_id", "packet_revision"),
        ),
    },
    "multi_agent_analysis_runs": {
        (
            ("tenant_id", "anomaly_id", "packet_revision"),
            "anomaly_revisions",
            ("tenant_id", "anomaly_id", "packet_revision"),
        ),
    },
    "disposition_decisions": {
        (("tenant_id", "resident_id"), "residents", ("tenant_id", "resident_id")),
        (("tenant_id", "room_id"), "rooms", ("tenant_id", "room_id")),
        (
            ("tenant_id", "anomaly_id", "packet_revision"),
            "anomaly_revisions",
            ("tenant_id", "anomaly_id", "packet_revision"),
        ),
    },
    "event_bridge_records": {
        (("tenant_id", "event_id"), "monitoring_events", ("tenant_id", "event_id")),
        (("tenant_id", "resident_id"), "residents", ("tenant_id", "resident_id")),
        (("tenant_id", "room_id"), "rooms", ("tenant_id", "room_id")),
    },
}


def test_initial_migration_creates_product_backbone(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migration.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert set(inspector.get_table_names()) - {"alembic_version"} == EXPECTED_TABLES

    for table_name, expected_columns in EXPECTED_COLUMNS.items():
        actual_columns = {
            column["name"]: column["nullable"]
            for column in inspector.get_columns(table_name)
        }
        assert actual_columns == expected_columns

        assert tuple(inspector.get_pk_constraint(table_name)["constrained_columns"]) == (
            EXPECTED_PRIMARY_KEYS[table_name]
        )

    for table_name in EXPECTED_TABLES:
        actual_foreign_keys = {
            (
                foreign_key["constrained_columns"][0],
                foreign_key["referred_table"],
                foreign_key["referred_columns"][0],
            )
            for foreign_key in inspector.get_foreign_keys(table_name)
        }
        assert actual_foreign_keys == EXPECTED_FOREIGN_KEYS.get(table_name, set())

    for table_name, expected_foreign_keys in (
        EXPECTED_COMPOSITE_OWNERSHIP_FOREIGN_KEYS.items()
    ):
        actual_foreign_keys = {
            (
                tuple(foreign_key["constrained_columns"]),
                foreign_key["referred_table"],
                tuple(foreign_key["referred_columns"]),
            )
            for foreign_key in inspector.get_foreign_keys(table_name)
        }
        assert expected_foreign_keys <= actual_foreign_keys

    for table_name in EXPECTED_TABLES:
        actual_uniques = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(table_name)
        }
        assert actual_uniques == EXPECTED_UNIQUES.get(table_name, set())

    orm_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(orm_engine)
    orm_inspector = inspect(orm_engine)
    task_8_tables = {
        "monitoring_events",
        "baseline_snapshots",
        "baseline_dimensions",
        "anomaly_revisions",
        "llm_interpretations",
        "disposition_decisions",
        "event_bridge_records",
    }
    for table_name in task_8_tables:
        migrated_uniques = {
            (item["name"], tuple(item["column_names"]))
            for item in inspector.get_unique_constraints(table_name)
        }
        orm_uniques = {
            (item["name"], tuple(item["column_names"]))
            for item in orm_inspector.get_unique_constraints(table_name)
        }
        assert orm_uniques == migrated_uniques
        migrated_checks = {
            (item["name"], item["sqltext"])
            for item in inspector.get_check_constraints(table_name)
        }
        orm_checks = {
            (item["name"], item["sqltext"])
            for item in orm_inspector.get_check_constraints(table_name)
        }
        assert orm_checks == migrated_checks

    task_8_event_defaults = {
        column["name"]: column["default"]
        for column in inspector.get_columns("monitoring_events")
        if column["name"]
        in {"provisional_urgent", "room_level_only", "bridge_idempotency_keys"}
    }
    orm_event_defaults = {
        column["name"]: column["default"]
        for column in orm_inspector.get_columns("monitoring_events")
        if column["name"] in task_8_event_defaults
    }
    assert orm_event_defaults == task_8_event_defaults
    orm_engine.dispose()

    for table_name in EXPECTED_TABLES:
        actual_indexes = {
            tuple(index["column_names"])
            for index in inspector.get_indexes(table_name)
        }
        assert actual_indexes == EXPECTED_INDEXES.get(table_name, set())

    assignment_indexes = {
        index["name"]: index
        for index in inspector.get_indexes("room_resident_assignments")
    }
    assert bool(assignment_indexes["uq_active_room_assignment"]["unique"])
    assert bool(assignment_indexes["uq_active_resident_assignment"]["unique"])

    device_assignment_indexes = {
        index["name"]: index
        for index in inspector.get_indexes("device_room_assignments")
    }
    assert bool(
        device_assignment_indexes["uq_active_device_room_assignment"]["unique"]
    )
    assert bool(
        device_assignment_indexes["uq_active_room_device_assignment"]["unique"]
    )

    command.downgrade(config, "base")

    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    engine.dispose()


def test_flexible_context_migration_defaults_old_memory_to_general_context(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'old-memory.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "0004_preferences_memory_admin")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO tenants (tenant_id) VALUES ('tenant_a')"))
        connection.execute(
            text(
                "INSERT INTO residents (resident_id, tenant_id, display_label) "
                "VALUES ('resident_a', 'tenant_a', 'Resident A')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO resident_memory_snapshots "
                "(tenant_id, resident_id, version, created_at) VALUES "
                "('tenant_a', 'resident_a', 1, '2026-08-25T15:10:00Z')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO resident_memory_entries "
                "(entry_id, tenant_id, resident_id, memory_version, description, "
                "source_kind, source_feedback_id, supersedes_entry_id, status, "
                "created_by, created_at, retired_by, retired_at, retirement_reason) "
                "VALUES ('memory_old', 'tenant_a', 'resident_a', 1, "
                "'Existing routine', 'operator', NULL, NULL, 'active', "
                "'operator_1', '2026-08-25T15:10:00Z', NULL, NULL, NULL)"
            )
        )

    command.upgrade(config, "head")

    with Session(engine) as session:
        restored = FeedbackRepository(session).current_memory(
            "tenant_a",
            "resident_a",
        )
        revision = session.scalar(text("SELECT version_num FROM alembic_version"))

    assert revision == "0007_multi_agent_analysis"
    assert restored.entries[0].context_kind == "general_context"
    assert restored.entries[0].effective_from is None
    assert restored.entries[0].effective_until is None
    engine.dispose()


def test_assignment_cannot_cross_tenant_boundaries(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'tenant-integrity.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text("INSERT INTO tenants (tenant_id) VALUES ('tenant_a'), ('tenant_b')")
        )
        connection.execute(
            text(
                "INSERT INTO rooms (room_id, tenant_id, label) "
                "VALUES ('room_b', 'tenant_b', 'Room B')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO residents (resident_id, tenant_id, display_label) "
                "VALUES ('resident_b', 'tenant_b', 'Resident B')"
            )
        )

        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO room_resident_assignments "
                    "(assignment_id, tenant_id, room_id, resident_id, status, "
                    "effective_from, effective_to) VALUES "
                    "('assignment_cross_tenant', 'tenant_a', 'room_b', "
                    "'resident_b', 'active', '2026-08-24T00:00:00Z', NULL)"
                )
            )

    engine.dispose()


def test_intelligence_foreign_keys_reject_cross_tenant_ownership(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'intelligence-tenant-integrity.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text("INSERT INTO tenants (tenant_id) VALUES ('tenant_a'), ('tenant_b')")
        )
        connection.execute(
            text(
                "INSERT INTO rooms (room_id, tenant_id, label) VALUES "
                "('room_a', 'tenant_a', 'Room A'), ('room_b', 'tenant_b', 'Room B')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO residents (resident_id, tenant_id, display_label) VALUES "
                "('resident_a', 'tenant_a', 'Resident A'), "
                "('resident_b', 'tenant_b', 'Resident B')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO baseline_snapshots "
                "(baseline_id, tenant_id, resident_id, recorded_at, "
                "monitoring_setup_version, policy_version, prior_baseline_id, "
                "adoption_candidate_id, adoption_context_entry_id, schema_version, "
                "payload_json) VALUES "
                "('baseline_a', 'tenant_a', 'resident_a', '2026-08-28T16:00:00Z', "
                "'setup_a', 'policy_a', NULL, NULL, NULL, '1.0', '{}')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO monitoring_events "
                "(event_id, tenant_id, episode_id, resident_id, room_id, "
                "objective_family, headline, priority, status, created_at, "
                "last_signal_at, signal_count, related_event_ids, recurrence_count, "
                "overdue_at, resolution_outcome, episode_policy_version, "
                "episode_policy_test_only, resident_memory_version, "
                "resident_memory_entry_ids, source_anomaly_id, latest_evidence_revision, "
                "latest_provisional_evidence_revision, attention_suppressed_until, "
                "provisional_urgent, room_level_only, bridge_idempotency_keys, version) "
                "VALUES ('event_b', 'tenant_b', 'episode_b', 'resident_b', 'room_b', "
                "'unknown_anomaly', 'Synthetic event', 'watch', 'open', "
                "'2026-08-28T16:00:00Z', '2026-08-28T16:00:00Z', 1, '[]', 1, "
                "NULL, NULL, 'event_policy_v1', 1, NULL, '[]', NULL, NULL, NULL, "
                "NULL, 0, 0, '[]', 1)"
            )
        )

    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text(
                "INSERT INTO baseline_snapshots "
                "(baseline_id, tenant_id, resident_id, recorded_at, "
                "monitoring_setup_version, policy_version, schema_version, payload_json) "
                "VALUES ('baseline_cross', 'tenant_a', 'resident_b', "
                "'2026-08-28T16:00:00Z', 'setup_a', 'policy_a', '1.0', '{}')"
            )
        )

    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text(
                "INSERT INTO anomaly_revisions "
                "(tenant_id, anomaly_id, packet_revision, resident_id, room_id, "
                "baseline_id, lifecycle_state, recorded_at, update_json, packet_json) "
                "VALUES ('tenant_a', 'anomaly_cross', 1, 'resident_a', 'room_b', "
                "'baseline_a', 'active', '2026-08-28T16:00:00Z', '{}', '{}')"
            )
        )

    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text(
                "INSERT INTO event_bridge_records "
                "(tenant_id, idempotency_key, event_id, resident_id, room_id, "
                "source_anomaly_id, evidence_revision, evidence_kind, priority, "
                "observed_at, payload_json) VALUES "
                "('tenant_a', 'bridge_cross', 'event_b', 'resident_a', 'room_a', "
                "'anomaly_a', 1, 'packet', 'watch', "
                "'2026-08-28T16:00:00Z', '{}')"
            )
        )
    engine.dispose()


def test_active_assignment_uniqueness_preserves_history(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'assignment-history.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(text("INSERT INTO tenants (tenant_id) VALUES ('tenant_a')"))
        connection.execute(
            text(
                "INSERT INTO rooms (room_id, tenant_id, label) VALUES "
                "('room_a', 'tenant_a', 'Room A'), "
                "('room_b', 'tenant_a', 'Room B')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO residents (resident_id, tenant_id, display_label) VALUES "
                "('resident_a', 'tenant_a', 'Resident A'), "
                "('resident_b', 'tenant_a', 'Resident B')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO room_resident_assignments "
                "(assignment_id, tenant_id, room_id, resident_id, status, "
                "effective_from, effective_to) VALUES "
                "('history_1', 'tenant_a', 'room_a', 'resident_a', 'inactive', "
                "'2026-08-20T00:00:00Z', '2026-08-21T00:00:00Z'), "
                "('history_2', 'tenant_a', 'room_a', 'resident_a', 'inactive', "
                "'2026-08-22T00:00:00Z', '2026-08-23T00:00:00Z'), "
                "('active_1', 'tenant_a', 'room_a', 'resident_a', 'active', "
                "'2026-08-24T00:00:00Z', NULL)"
            )
        )

    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text(
                "INSERT INTO room_resident_assignments "
                "(assignment_id, tenant_id, room_id, resident_id, status, "
                "effective_from, effective_to) VALUES "
                "('active_duplicate_resident', 'tenant_a', 'room_b', "
                "'resident_a', 'active', '2026-08-25T00:00:00Z', NULL)"
            )
        )

    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text(
                "INSERT INTO room_resident_assignments "
                "(assignment_id, tenant_id, room_id, resident_id, status, "
                "effective_from, effective_to) VALUES "
                "('active_duplicate_room', 'tenant_a', 'room_a', "
                "'resident_b', 'active', '2026-08-25T00:00:00Z', NULL)"
            )
        )

    engine.dispose()
