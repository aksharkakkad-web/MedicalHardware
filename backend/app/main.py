from fastapi import FastAPI

from backend.app.api.errors import register_error_handlers
from backend.app.api.v1.router import router as v1_router
from backend.app.config import Settings
from backend.app.contracts.common import HealthResponse
from backend.app.db.session import create_engine_for_url, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Contactless Monitoring Product API", version="0.1.0")
    app.state.settings = settings or Settings()
    app.state.engine = create_engine_for_url(app.state.settings.database_url)
    app.state.session_factory = create_session_factory(app.state.engine)
    register_error_handlers(app)
    app.include_router(v1_router)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ready", service="product-api")

    return app


app = create_app()
