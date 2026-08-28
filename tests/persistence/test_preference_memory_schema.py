from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


def _database(tmp_path: Path, filename: str):
    database_url = f"sqlite+pysqlite:///{tmp_path / filename}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config, create_engine(database_url)


def _seed_residents(connection) -> None:
    connection.execute(
        text("INSERT INTO tenants (tenant_id) VALUES ('tenant_a'), ('tenant_b')")
    )
    connection.execute(
        text(
            "INSERT INTO residents (resident_id, tenant_id, display_label) VALUES "
            "('resident_a', 'tenant_a', 'Resident A'), "
            "('resident_b', 'tenant_b', 'Resident B')"
        )
    )


def _insert_preference(
    connection,
    *,
    tenant_id: str = "tenant_a",
    resident_id: str = "resident_a",
    version: int = 1,
) -> None:
    connection.execute(
        text(
            "INSERT INTO resident_notification_preference_versions "
            "(tenant_id, resident_id, version, watch_delivery_enabled, "
            "high_delivery_enabled, critical_delivery_enabled, "
            "away_awareness_enabled, return_awareness_enabled, "
            "limited_awareness_enabled, unavailable_awareness_enabled, "
            "changed_by, changed_at) VALUES "
            "(:tenant_id, :resident_id, :version, 0, 1, 1, 1, 1, 0, 1, "
            "'operator_1', '2026-08-25T15:00:00Z')"
        ),
        {
            "tenant_id": tenant_id,
            "resident_id": resident_id,
            "version": version,
        },
    )


def test_checkpoint_c_migration_adds_preferences_and_memory_provenance(
    tmp_path: Path,
) -> None:
    config, engine = _database(tmp_path, "checkpoint-c-migration.db")
    command.upgrade(config, "0003_device_health")

    command.upgrade(config, "head")

    inspector = inspect(engine)
    assert "resident_notification_preference_versions" in inspector.get_table_names()
    memory_columns = {
        column["name"]: column for column in inspector.get_columns("resident_memory_entries")
    }
    assert memory_columns["source_kind"]["nullable"] is False
    assert memory_columns["source_feedback_id"]["nullable"] is True
    assert memory_columns["supersedes_entry_id"]["nullable"] is True

    command.downgrade(config, "0003_device_health")
    inspector = inspect(engine)
    assert "resident_notification_preference_versions" not in inspector.get_table_names()
    assert "source_kind" not in {
        column["name"] for column in inspector.get_columns("resident_memory_entries")
    }
    engine.dispose()


def test_preference_versions_are_resident_tenant_safe_and_append_only(
    tmp_path: Path,
) -> None:
    config, engine = _database(tmp_path, "preference-safety.db")
    command.upgrade(config, "head")

    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        _seed_residents(connection)
        _insert_preference(connection)
        _insert_preference(connection, version=2)

    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("PRAGMA foreign_keys=ON"))
        _insert_preference(connection, version=2)

    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("PRAGMA foreign_keys=ON"))
        _insert_preference(
            connection,
            tenant_id="tenant_a",
            resident_id="resident_b",
        )
    engine.dispose()


def test_memory_provenance_allows_operator_entries_without_fake_feedback(
    tmp_path: Path,
) -> None:
    config, engine = _database(tmp_path, "memory-provenance.db")
    command.upgrade(config, "head")

    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        _seed_residents(connection)
        connection.execute(
            text(
                "INSERT INTO resident_memory_snapshots "
                "(tenant_id, resident_id, version, created_at) VALUES "
                "('tenant_a', 'resident_a', 1, '2026-08-25T15:00:00Z')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO resident_memory_entries "
                "(entry_id, tenant_id, resident_id, memory_version, description, "
                "source_kind, source_feedback_id, supersedes_entry_id, status, "
                "created_by, created_at, retired_by, retired_at, retirement_reason) "
                "VALUES ('memory_operator', 'tenant_a', 'resident_a', 1, "
                "'Morning routine', 'operator', NULL, NULL, 'active', "
                "'operator_1', '2026-08-25T15:00:00Z', NULL, NULL, NULL)"
            )
        )

    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text(
                "INSERT INTO resident_memory_entries "
                "(entry_id, tenant_id, resident_id, memory_version, description, "
                "source_kind, source_feedback_id, supersedes_entry_id, status, "
                "created_by, created_at, retired_by, retired_at, retirement_reason) "
                "VALUES ('memory_fake_feedback', 'tenant_a', 'resident_a', 1, "
                "'Invalid provenance', 'feedback', NULL, NULL, 'active', "
                "'operator_1', '2026-08-25T15:00:00Z', NULL, NULL, NULL)"
            )
        )
    engine.dispose()
