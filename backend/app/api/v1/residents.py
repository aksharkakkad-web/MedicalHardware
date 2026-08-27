from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.dependencies import access_context, query_service
from backend.app.api.errors import READ_ERROR_RESPONSES
from backend.app.contracts.events import EventListResponse
from backend.app.contracts.feedback import ResidentMemoryResponse
from backend.app.contracts.residents import ResidentListResponse, ResidentSummary
from backend.app.services.queries import AccessContext, ProductQueryService


router = APIRouter(prefix="/residents", tags=["residents"])


@router.get(
    "",
    response_model=ResidentListResponse,
    responses={422: READ_ERROR_RESPONSES[422], 500: READ_ERROR_RESPONSES[500]},
)
def list_residents(
    context: Annotated[AccessContext, Depends(access_context)],
    service: Annotated[ProductQueryService, Depends(query_service)],
) -> ResidentListResponse:
    return service.list_residents(context)


@router.get(
    "/{resident_id}",
    response_model=ResidentSummary,
    responses=READ_ERROR_RESPONSES,
)
def get_resident(
    resident_id: str,
    context: Annotated[AccessContext, Depends(access_context)],
    service: Annotated[ProductQueryService, Depends(query_service)],
) -> ResidentSummary:
    return service.get_resident(context, resident_id)


@router.get(
    "/{resident_id}/events",
    response_model=EventListResponse,
    responses=READ_ERROR_RESPONSES,
)
def list_resident_events(
    resident_id: str,
    context: Annotated[AccessContext, Depends(access_context)],
    service: Annotated[ProductQueryService, Depends(query_service)],
) -> EventListResponse:
    return service.list_resident_events(context, resident_id)


@router.get(
    "/{resident_id}/memory",
    response_model=ResidentMemoryResponse,
    responses=READ_ERROR_RESPONSES,
)
def get_resident_memory(
    resident_id: str,
    context: Annotated[AccessContext, Depends(access_context)],
    service: Annotated[ProductQueryService, Depends(query_service)],
) -> ResidentMemoryResponse:
    return service.get_resident_memory(context, resident_id)
