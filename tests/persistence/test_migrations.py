from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


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
}


def test_initial_migration_creates_product_backbone(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migration.db'}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(config, "head")

    tables = set(inspect(create_engine(database_url)).get_table_names())
    assert EXPECTED_TABLES <= tables
