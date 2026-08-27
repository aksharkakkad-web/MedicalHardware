from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from backend.app.api.dependencies import (
    EventMutationServices,
    access_context,
    event_mutation_services,
    query_service,
    request_idempotency_key,
)
from backend.app.api.errors import MUTATION_ERROR_RESPONSES, READ_ERROR_RESPONSES
from backend.app.contracts.events import (
    EventActionRequest,
    EventResponse,
    ResolveEventRequest,
)
from backend.app.db.mappers import StoredEvent
from backend.app.services.idempotency import IdempotencyResult
from backend.app.services.queries import (
    AccessContext,
    ProductQueryService,
    event_response,
)


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


def _execute_action(
    *,
    request: Request,
    context: AccessContext,
    key: str,
    request_body: dict[str, object],
    services: EventMutationServices,
    command: Callable[[], StoredEvent],
) -> EventResponse:
    try:
        result = services.idempotency.execute(
            context=context,
            key=key,
            method=request.method,
            path=request.url.path,
            request_body=request_body,
            command=lambda: IdempotencyResult(
                status_code=200,
                body=event_response(command()).model_dump(mode="json"),
            ),
        )
        response = EventResponse.model_validate(result.body)
        services.session.commit()
        return response
    except Exception:
        services.session.rollback()
        raise


@router.post(
    "/{event_id}/acknowledge",
    response_model=EventResponse,
    responses=MUTATION_ERROR_RESPONSES,
)
def acknowledge_event(
    event_id: str,
    body: EventActionRequest,
    request: Request,
    context: Annotated[AccessContext, Depends(access_context)],
    key: Annotated[str, Depends(request_idempotency_key)],
    services: Annotated[EventMutationServices, Depends(event_mutation_services)],
) -> EventResponse:
    return _execute_action(
        request=request,
        context=context,
        key=key,
        request_body=body.model_dump(mode="json"),
        services=services,
        command=lambda: services.commands.acknowledge(
            context,
            event_id,
            body.occurred_at,
        ),
    )


@router.post(
    "/{event_id}/checked",
    response_model=EventResponse,
    responses=MUTATION_ERROR_RESPONSES,
)
def check_event(
    event_id: str,
    body: EventActionRequest,
    request: Request,
    context: Annotated[AccessContext, Depends(access_context)],
    key: Annotated[str, Depends(request_idempotency_key)],
    services: Annotated[EventMutationServices, Depends(event_mutation_services)],
) -> EventResponse:
    return _execute_action(
        request=request,
        context=context,
        key=key,
        request_body=body.model_dump(mode="json"),
        services=services,
        command=lambda: services.commands.check(
            context,
            event_id,
            body.occurred_at,
        ),
    )


@router.post(
    "/{event_id}/resolve",
    response_model=EventResponse,
    responses=MUTATION_ERROR_RESPONSES,
)
def resolve_event(
    event_id: str,
    body: ResolveEventRequest,
    request: Request,
    context: Annotated[AccessContext, Depends(access_context)],
    key: Annotated[str, Depends(request_idempotency_key)],
    services: Annotated[EventMutationServices, Depends(event_mutation_services)],
) -> EventResponse:
    return _execute_action(
        request=request,
        context=context,
        key=key,
        request_body=body.model_dump(mode="json"),
        services=services,
        command=lambda: services.commands.resolve(
            context,
            event_id,
            body.occurred_at,
            body.outcome,
        ),
    )
