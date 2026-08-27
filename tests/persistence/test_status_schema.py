from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


CHECKPOINT_A_TABLES = {
    "monitoring_status_snapshots",
    "calibration_snapshots",
    "monitoring_setup_changes",
}


def _migrated_database(tmp_path: Path, filename: str):
    database_url = f"sqlite+pysqlite:///{tmp_path / filename}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return config, create_engine(database_url)


def _seed_ownership(connection) -> None:
    connection.execute(
        text("INSERT INTO tenants (tenant_id) VALUES ('tenant_a'), ('tenant_b')")
    )
    connection.execute(
        text(
            "INSERT INTO rooms (room_id, tenant_id, label) VALUES "
            "('room_a', 'tenant_a', 'Room A'), "
            "('room_b', 'tenant_b', 'Room B')"
        )
    )
    connection.execute(
        text(
            "INSERT INTO residents (resident_id, tenant_id, display_label) VALUES "
            "('resident_a', 'tenant_a', 'Resident A'), "
            "('resident_b', 'tenant_b', 'Resident B')"
        )
    )


def test_checkpoint_a_migration_upgrades_and_downgrades_only_its_tables(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'upgrade-downgrade.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "0001_product_backbone")
    engine = create_engine(database_url)

    original_tables = set(inspect(engine).get_table_names())
    assert not CHECKPOINT_A_TABLES & original_tables

    command.upgrade(config, "head")
    assert CHECKPOINT_A_TABLES <= set(inspect(engine).get_table_names())

    command.downgrade(config, "0001_product_backbone")
    assert set(inspect(engine).get_table_names()) == original_tables
    engine.dispose()


def test_status_rows_cannot_cross_tenant_resident_or_room_boundaries(
    tmp_path: Path,
) -> None:
    _, engine = _migrated_database(tmp_path, "status-ownership.db")
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        _seed_ownership(connection)

        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO monitoring_status_snapshots "
                    "(tenant_id, resident_id, room_id, observed_at, monitoring_state, "
                    "presence_state, baseline_learning_allowed, "
                    "resident_measurements_allowed, reasons, quality_policy_version, "
                    "quality_policy_test_only) VALUES "
                    "('tenant_a', 'resident_b', 'room_b', '2026-08-24T21:00:00Z', "
                    "'active', 'resident_present', 1, 1, '[]', "
                    "'synthetic_monitoring_quality_v1', 1)"
                )
            )
    engine.dispose()


def test_calibration_versions_are_unique_per_tenant_resident(
    tmp_path: Path,
) -> None:
    _, engine = _migrated_database(tmp_path, "calibration-version.db")
    insert = text(
        "INSERT INTO calibration_snapshots "
        "(tenant_id, resident_id, version, recorded_at, setup_version, status, "
        "eligible_windows, excluded_windows, reason, prior_setup_versions, "
        "dimension_progress) VALUES "
        "('tenant_a', 'resident_a', 1, '2026-08-24T21:00:00Z', "
        "'setup_room_a_v1', 'established', 12, 2, 'calibration_complete', "
        "'[]', '[]')"
    )
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        _seed_ownership(connection)
        connection.execute(insert)
        with pytest.raises(IntegrityError):
            connection.execute(insert)
    engine.dispose()
