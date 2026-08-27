from fastapi import FastAPI

from backend.app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Contactless Monitoring Product API", version="0.1.0")
    app.state.settings = settings or Settings()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "schema_version": "1.0",
            "status": "ready",
            "service": "product-api",
        }

    return app


app = create_app()
