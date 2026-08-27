from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.config import Settings
from backend.app.db.base import Base
from backend.app.db.seed import seed_synthetic_story
from backend.app.db.session import create_engine_for_url
from backend.app.main import create_app


@pytest.fixture
def api_client(tmp_path) -> Iterator[TestClient]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'product-api.db'}"
    engine = create_engine_for_url(database_url)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_synthetic_story(session)
    engine.dispose()

    with TestClient(
        create_app(Settings(app_env="test", database_url=database_url))
    ) as client:
        yield client
