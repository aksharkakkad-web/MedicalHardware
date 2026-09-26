"""Authenticated hardware telemetry and heartbeat endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.app.api.dependencies import ingest_tenant_id, telemetry_ingestion_service
from backend.app.api.errors import INGEST_ERROR_RESPONSES
from backend.app.contracts.ingestion import (
    DeviceHeartbeatRequest,
    HeartbeatIngestResponse,
    TelemetryCaptureRequest,
    TelemetryIngestResponse,
)
from backend.app.services.telemetry_ingestion import TelemetryIngestionService


router = APIRouter(prefix="/ingest", tags=["device-ingestion"])


@router.post(
    "/telemetry",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TelemetryIngestResponse,
    responses=INGEST_ERROR_RESPONSES,
)
def ingest_telemetry(
    capture: TelemetryCaptureRequest,
    tenant_id: Annotated[str, Depends(ingest_tenant_id)],
    service: Annotated[
        TelemetryIngestionService,
        Depends(telemetry_ingestion_service),
    ],
) -> TelemetryIngestResponse:
    return service.ingest_capture(tenant_id, capture)


@router.post(
    "/heartbeat",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=HeartbeatIngestResponse,
    responses=INGEST_ERROR_RESPONSES,
)
def ingest_heartbeat(
    heartbeat: DeviceHeartbeatRequest,
    tenant_id: Annotated[str, Depends(ingest_tenant_id)],
    service: Annotated[
        TelemetryIngestionService,
        Depends(telemetry_ingestion_service),
    ],
) -> HeartbeatIngestResponse:
    return service.ingest_heartbeat(tenant_id, heartbeat)


__all__ = ["router"]
