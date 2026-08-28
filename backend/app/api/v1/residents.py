from collections.abc import Callable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.dependencies import (
    access_context,
    database_session,
    query_service,
    request_idempotency_key,
)
from backend.app.api.errors import MUTATION_ERROR_RESPONSES, READ_ERROR_RESPONSES
from backend.app.contracts.events import EventListResponse
from backend.app.contracts.feedback import (
    AddMemoryEntryRequest,
    CorrectMemoryEntryRequest,
    ResidentMemoryResponse,
    RetireMemoryEntryRequest,
)
from backend.app.contracts.preferences import (
    ResidentNotificationPreferencesResponse,
    UpdateNotificationPreferencesRequest,
)
from backend.app.contracts.residents import ResidentListResponse, ResidentSummary
from backend.app.db.preference_repositories import NotificationPreferenceRepository
from backend.app.db.repositories import FeedbackRepository, ResidentRepository
from backend.app.domain.preferences import (
    AwarenessDeliveryPreferences,
    EventDeliveryPreferences,
)
from backend.app.services.idempotency import IdempotencyResult, IdempotencyService
from backend.app.services.queries import AccessContext, ProductQueryService
from backend.app.services.resident_controls import ResidentControlService


router = APIRouter(prefix="/residents", tags=["residents"])
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


def _resident_controls(request: Request, session: Session) -> ResidentControlService:
    preference_factory = getattr(
        request.app.state,
        "preference_repository_factory",
        NotificationPreferenceRepository,
    )
    memory_factory = getattr(
        request.app.state,
        "memory_repository_factory",
        FeedbackRepository,
    )
    return ResidentControlService(
        session,
        residents=ResidentRepository(session),
        preferences=preference_factory(session),
        memory=memory_factory(session),
    )


def _execute_control_mutation(
    *,
    request: Request,
    context: AccessContext,
    key: str,
    session: Session,
    request_body: dict[str, object],
    response_type: type[ResponseModel],
    command: Callable[[], ResponseModel],
) -> ResponseModel:
    try:
        result = IdempotencyService(session).execute(
            context=context,
            key=key,
            method=request.method,
            path=request.url.path,
            request_body=request_body,
            command=lambda: IdempotencyResult(
                status_code=200,
                body=command().model_dump(mode="json", by_alias=True),
            ),
        )
        response = response_type.model_validate(result.body)
        session.commit()
        return response
    except Exception:
        session.rollback()
        raise


@router.get(
    "",
    response_model=ResidentListResponse,
    responses={
        405: READ_ERROR_RESPONSES[405],
        422: READ_ERROR_RESPONSES[422],
        500: READ_ERROR_RESPONSES[500],
    },
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


@router.get(
    "/{resident_id}/notification-preferences",
    response_model=ResidentNotificationPreferencesResponse,
    responses=READ_ERROR_RESPONSES,
)
def get_resident_notification_preferences(
    resident_id: str,
    request: Request,
    context: Annotated[AccessContext, Depends(access_context)],
    session: Annotated[Session, Depends(database_session)],
) -> ResidentNotificationPreferencesResponse:
    return _resident_controls(request, session).get_preferences(context, resident_id)


@router.put(
    "/{resident_id}/notification-preferences",
    response_model=ResidentNotificationPreferencesResponse,
    responses=MUTATION_ERROR_RESPONSES,
)
def update_resident_notification_preferences(
    resident_id: str,
    body: UpdateNotificationPreferencesRequest,
    request: Request,
    context: Annotated[AccessContext, Depends(access_context)],
    key: Annotated[str, Depends(request_idempotency_key)],
    session: Annotated[Session, Depends(database_session)],
) -> ResidentNotificationPreferencesResponse:
    controls = _resident_controls(request, session)
    return _execute_control_mutation(
        request=request,
        context=context,
        key=key,
        session=session,
        request_body=body.model_dump(mode="json", by_alias=True),
        response_type=ResidentNotificationPreferencesResponse,
        command=lambda: controls.update_preferences(
            context,
            resident_id,
            expected_version=body.expected_version,
            event_delivery=EventDeliveryPreferences(
                watch=body.event_delivery.watch,
                high=body.event_delivery.high,
                critical=body.event_delivery.critical,
            ),
            awareness_delivery=AwarenessDeliveryPreferences(
                away=body.awareness_delivery.away,
                return_=body.awareness_delivery.return_,
                limited=body.awareness_delivery.limited,
                unavailable=body.awareness_delivery.unavailable,
            ),
            changed_at=body.changed_at,
        ),
    )


@router.post(
    "/{resident_id}/memory/entries",
    response_model=ResidentMemoryResponse,
    responses=MUTATION_ERROR_RESPONSES,
)
def add_resident_memory_entry(
    resident_id: str,
    body: AddMemoryEntryRequest,
    request: Request,
    context: Annotated[AccessContext, Depends(access_context)],
    key: Annotated[str, Depends(request_idempotency_key)],
    session: Annotated[Session, Depends(database_session)],
) -> ResidentMemoryResponse:
    controls = _resident_controls(request, session)
    return _execute_control_mutation(
        request=request,
        context=context,
        key=key,
        session=session,
        request_body=body.model_dump(mode="json"),
        response_type=ResidentMemoryResponse,
        command=lambda: controls.add_memory_entry(
            context,
            resident_id,
            expected_version=body.expected_version,
            description=body.description,
            changed_at=body.changed_at,
            context_kind=body.context_kind,
            effective_from=body.effective_from,
            effective_until=body.effective_until,
            local_time_start=body.local_time_start,
            local_time_end=body.local_time_end,
            recurrence_note=body.recurrence_note,
            flexibility_note=body.flexibility_note,
        ),
    )


@router.post(
    "/{resident_id}/memory/entries/{entry_id}/correct",
    response_model=ResidentMemoryResponse,
    responses=MUTATION_ERROR_RESPONSES,
)
def correct_resident_memory_entry(
    resident_id: str,
    entry_id: str,
    body: CorrectMemoryEntryRequest,
    request: Request,
    context: Annotated[AccessContext, Depends(access_context)],
    key: Annotated[str, Depends(request_idempotency_key)],
    session: Annotated[Session, Depends(database_session)],
) -> ResidentMemoryResponse:
    controls = _resident_controls(request, session)
    return _execute_control_mutation(
        request=request,
        context=context,
        key=key,
        session=session,
        request_body=body.model_dump(mode="json"),
        response_type=ResidentMemoryResponse,
        command=lambda: controls.correct_memory_entry(
            context,
            resident_id,
            entry_id,
            expected_version=body.expected_version,
            description=body.description,
            reason=body.reason,
            changed_at=body.changed_at,
            context_kind=body.context_kind,
            effective_from=body.effective_from,
            effective_until=body.effective_until,
            local_time_start=body.local_time_start,
            local_time_end=body.local_time_end,
            recurrence_note=body.recurrence_note,
            flexibility_note=body.flexibility_note,
        ),
    )


@router.post(
    "/{resident_id}/memory/entries/{entry_id}/retire",
    response_model=ResidentMemoryResponse,
    responses=MUTATION_ERROR_RESPONSES,
)
def retire_resident_memory_entry(
    resident_id: str,
    entry_id: str,
    body: RetireMemoryEntryRequest,
    request: Request,
    context: Annotated[AccessContext, Depends(access_context)],
    key: Annotated[str, Depends(request_idempotency_key)],
    session: Annotated[Session, Depends(database_session)],
) -> ResidentMemoryResponse:
    controls = _resident_controls(request, session)
    return _execute_control_mutation(
        request=request,
        context=context,
        key=key,
        session=session,
        request_body=body.model_dump(mode="json"),
        response_type=ResidentMemoryResponse,
        command=lambda: controls.retire_memory_entry(
            context,
            resident_id,
            entry_id,
            expected_version=body.expected_version,
            reason=body.reason,
            changed_at=body.changed_at,
        ),
    )
