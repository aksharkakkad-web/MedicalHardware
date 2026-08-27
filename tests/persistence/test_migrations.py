from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


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
    "idempotency_records",
    "audit_log",
    "monitoring_status_snapshots",
    "calibration_snapshots",
    "monitoring_setup_changes",
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
        "source_feedback_id": False,
        "status": False,
        "created_by": False,
        "created_at": False,
        "retired_by": True,
        "retired_at": True,
        "retirement_reason": True,
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

    command.downgrade(config, "base")

    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
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
