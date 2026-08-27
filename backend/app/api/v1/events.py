from typing import Annotated

from fastapi import APIRouter, Depends

from backend.app.api.dependencies import access_context, query_service
from backend.app.api.errors import READ_ERROR_RESPONSES
from backend.app.contracts.events import EventResponse
from backend.app.services.queries import AccessContext, ProductQueryService


router = APIRouter(prefix="/events", tags=["events"])


@router.get(
    "/{event_id}",
    response_model=EventResponse,
    responses=READ_ERROR_RESPONSES,
)
def get_event(
    event_id: str,
    context: Annotated[AccessContext, Depends(access_context)],
    service: Annotated[ProductQueryService, Depends(query_service)],
) -> EventResponse:
    return service.get_event(context, event_id)
