"""Deterministic Product API document generation for frontend handoff."""

import json
from pathlib import Path
from typing import Any

from backend.app.config import Settings
from backend.app.main import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OPENAPI_PATH = PROJECT_ROOT / "docs/openapi/product-api-v1.json"


def generate_openapi_document() -> dict[str, Any]:
    app = create_app(
        Settings(
            app_env="test",
            database_url="sqlite+pysqlite:///:memory:",
        )
    )
    try:
        return app.openapi()
    finally:
        app.state.engine.dispose()


def render_openapi_document(document: dict[str, Any]) -> str:
    return json.dumps(
        document,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def export_openapi_document(path: Path = DEFAULT_OPENAPI_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        render_openapi_document(generate_openapi_document()),
        encoding="utf-8",
    )
    return path


def main() -> None:
    path = export_openapi_document()
    print(f"OPENAPI READY {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
