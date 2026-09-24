from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.ai.analysis_contracts import UnavailableStructuredAnalysisClient
from backend.app.ai.analysis_orchestration import MultiAgentAnalysisOrchestrator
from backend.app.api.errors import (
    METHOD_NOT_ALLOWED_ERROR_RESPONSES,
    register_error_handlers,
)
from backend.app.api.request_limits import install_ingest_body_limit
from backend.app.api.v1.router import router as v1_router
from backend.app.config import Settings
from backend.app.contracts.common import HealthResponse
from backend.app.db.session import create_engine_for_url, create_session_factory
from backend.app.intelligence.orchestration import MonitoringIntelligenceEngine
from backend.app.services.telemetry_worker import TelemetryProcessingWorker


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        settings = application.state.settings
        ingest_key = settings.ingest_bearer_key
        ingest_enabled = (
            ingest_key is not None
            and bool(ingest_key.get_secret_value())
            and bool(settings.ingest_tenant_id and settings.ingest_tenant_id.strip())
        )
        worker = None
        if ingest_enabled:
            worker = TelemetryProcessingWorker(
                application.state.session_factory,
                application.state.monitoring_engine,
            )
            application.state.telemetry_worker = worker
            application.state.telemetry_post_commit_processor = worker.enqueue
            worker.start()
        try:
            yield
        finally:
            if worker is not None:
                worker.stop()
            application.state.engine.dispose()

    app = FastAPI(
        title="Contactless Monitoring Product API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings or Settings()
    install_ingest_body_limit(app)
    app.state.engine = create_engine_for_url(app.state.settings.database_url)
    app.state.session_factory = create_session_factory(app.state.engine)
    unavailable_provider = UnavailableStructuredAnalysisClient()
    app.state.monitoring_engine = MonitoringIntelligenceEngine(
        analysis_orchestrator=MultiAgentAnalysisOrchestrator(
            recall_client=unavailable_provider,
            precision_client=unavailable_provider,
            final_client=unavailable_provider,
        )
    )

    register_error_handlers(app)
    app.include_router(v1_router)

    @app.get(
        "/health",
        response_model=HealthResponse,
        responses=METHOD_NOT_ALLOWED_ERROR_RESPONSES,
    )
    def health() -> HealthResponse:
        return HealthResponse(status="ready", service="product-api")

    return app


app = create_app()
