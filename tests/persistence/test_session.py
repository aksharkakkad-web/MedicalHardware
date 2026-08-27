import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.db.session import create_engine_for_url


def test_sqlite_engine_rejects_orphaned_foreign_key_rows() -> None:
    engine = create_engine_for_url("sqlite+pysqlite:///:memory:")

    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql(
            "CREATE TABLE child (parent_id INTEGER NOT NULL REFERENCES parent(id))"
        )

        with pytest.raises(IntegrityError):
            connection.exec_driver_sql("INSERT INTO child (parent_id) VALUES (1)")

    engine.dispose()
