from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


CHECKPOINT_B_TABLES = {
    "locations",
    "devices",
    "device_room_assignments",
    "device_health_observations",
}


def _database(tmp_path: Path, filename: str):
    database_url = f"sqlite+pysqlite:///{tmp_path / filename}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config, create_engine(database_url)


def _seed_device_ownership(connection) -> None:
    connection.execute(
        text("INSERT INTO tenants (tenant_id) VALUES ('tenant_a'), ('tenant_b')")
    )
    connection.execute(
        text(
            "INSERT INTO rooms (room_id, tenant_id, label) VALUES "
            "('room_a', 'tenant_a', 'Room A'), "
            "('room_a_2', 'tenant_a', 'Room A2'), "
            "('room_b', 'tenant_b', 'Room B')"
        )
    )
    connection.execute(
        text(
            "INSERT INTO locations (location_id, tenant_id, label) VALUES "
            "('location_a', 'tenant_a', 'Location A'), "
            "('location_b', 'tenant_b', 'Location B')"
        )
    )
    connection.execute(
        text(
            "INSERT INTO devices (device_id, tenant_id, display_label) VALUES "
            "('device_a', 'tenant_a', 'Device A'), "
            "('device_a_2', 'tenant_a', 'Device A2'), "
            "('device_b', 'tenant_b', 'Device B')"
        )
    )


def test_checkpoint_b_migration_upgrades_and_downgrades_only_its_tables(
    tmp_path: Path,
) -> None:
    config, engine = _database(tmp_path, "checkpoint-b-migration.db")
    command.upgrade(config, "0002_status_calibration")
    original_tables = set(inspect(engine).get_table_names())

    command.upgrade(config, "head")
    assert CHECKPOINT_B_TABLES <= set(inspect(engine).get_table_names())

    command.downgrade(config, "0002_status_calibration")
    assert set(inspect(engine).get_table_names()) == original_tables
    engine.dispose()


def test_device_assignment_cannot_cross_tenant_boundaries(tmp_path: Path) -> None:
    config, engine = _database(tmp_path, "device-tenant.db")
    command.upgrade(config, "head")

    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        _seed_device_ownership(connection)
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO device_room_assignments "
                    "(assignment_id, tenant_id, device_id, location_id, room_id, "
                    "status, effective_from, effective_to) VALUES "
                    "('cross_tenant', 'tenant_a', 'device_b', 'location_b', "
                    "'room_b', 'active', '2026-08-25T14:00:00Z', NULL)"
                )
            )
    engine.dispose()


def test_one_active_device_per_room_and_one_active_room_per_device(
    tmp_path: Path,
) -> None:
    config, engine = _database(tmp_path, "device-assignment-unique.db")
    command.upgrade(config, "head")

    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        _seed_device_ownership(connection)
        connection.execute(
            text(
                "INSERT INTO device_room_assignments "
                "(assignment_id, tenant_id, device_id, location_id, room_id, "
                "status, effective_from, effective_to) VALUES "
                "('history', 'tenant_a', 'device_a', 'location_a', 'room_a', "
                "'inactive', '2026-08-20T14:00:00Z', '2026-08-21T14:00:00Z'), "
                "('active', 'tenant_a', 'device_a', 'location_a', 'room_a', "
                "'active', '2026-08-25T14:00:00Z', NULL)"
            )
        )

    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text(
                "INSERT INTO device_room_assignments "
                "(assignment_id, tenant_id, device_id, location_id, room_id, "
                "status, effective_from, effective_to) VALUES "
                "('duplicate_device', 'tenant_a', 'device_a', 'location_a', "
                "'room_a_2', 'active', '2026-08-26T14:00:00Z', NULL)"
            )
        )

    with engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text(
                "INSERT INTO device_room_assignments "
                "(assignment_id, tenant_id, device_id, location_id, room_id, "
                "status, effective_from, effective_to) VALUES "
                "('duplicate_room', 'tenant_a', 'device_a_2', 'location_a', "
                "'room_a', 'active', '2026-08-26T14:00:00Z', NULL)"
            )
        )
    engine.dispose()


def test_health_observation_cannot_reference_cross_tenant_device(
    tmp_path: Path,
) -> None:
    config, engine = _database(tmp_path, "device-health-tenant.db")
    command.upgrade(config, "head")

    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        _seed_device_ownership(connection)
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO device_health_observations "
                    "(tenant_id, device_id, observed_at, last_seen_at, state, "
                    "sources, limitations, policy_version, policy_test_only) VALUES "
                    "('tenant_a', 'device_b', '2026-08-25T14:00:00Z', NULL, "
                    "'offline', '[]', '[]', 'synthetic_device_health_v1', 1)"
                )
            )
    engine.dispose()
