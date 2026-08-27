from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.dependencies import access_context, status_query_service
from backend.app.api.errors import READ_ERROR_RESPONSES
from backend.app.contracts.status import (
    AwarenessTimelineResponse,
    CalibrationResponse,
    ResidentStatusResponse,
)
from backend.app.services.queries import AccessContext
from backend.app.services.status_queries import ProductStatusQueryService


router = APIRouter(prefix="/residents", tags=["resident-status"])


@router.get(
    "/{resident_id}/status",
    response_model=ResidentStatusResponse,
    responses=READ_ERROR_RESPONSES,
)
def get_resident_status(
    resident_id: str,
    context: Annotated[AccessContext, Depends(access_context)],
    service: Annotated[ProductStatusQueryService, Depends(status_query_service)],
) -> ResidentStatusResponse:
    return service.get_status(context, resident_id)


@router.get(
    "/{resident_id}/awareness",
    response_model=AwarenessTimelineResponse,
    responses=READ_ERROR_RESPONSES,
)
def get_resident_awareness(
    resident_id: str,
    context: Annotated[AccessContext, Depends(access_context)],
    service: Annotated[ProductStatusQueryService, Depends(status_query_service)],
) -> AwarenessTimelineResponse:
    return service.get_awareness(context, resident_id)


@router.get(
    "/{resident_id}/calibration",
    response_model=CalibrationResponse,
    responses=READ_ERROR_RESPONSES,
)
def get_resident_calibration(
    resident_id: str,
    context: Annotated[AccessContext, Depends(access_context)],
    service: Annotated[ProductStatusQueryService, Depends(status_query_service)],
) -> CalibrationResponse:
    return service.get_calibration(context, resident_id)
