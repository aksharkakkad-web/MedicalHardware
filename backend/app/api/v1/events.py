from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.app.api.dependencies import (
    EventMutationServices,
    access_context,
    database_session,
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
from backend.app.contracts.feedback import (
    FeedbackResponse,
    LearningDecisionResponse,
    MemoryEntryResponse,
    ResidentMemoryResponse,
    SubmitFeedbackRequest,
)
from backend.app.db.mappers import StoredEvent
from backend.app.db.repositories import EventRepository, FeedbackRepository
from backend.app.domain.feedback import LearningDecision
from backend.app.services.feedback_commands import FeedbackCommandService
from backend.app.services.idempotency import IdempotencyResult, IdempotencyService
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


def _learning_decision_response(
    decision: LearningDecision,
) -> LearningDecisionResponse:
    feedback = decision.feedback
    memory = decision.memory
    return LearningDecisionResponse(
        feedback=FeedbackResponse(
            feedback_id=feedback.feedback_id,
            event_id=feedback.event_id,
            resident_id=feedback.resident_id,
            actor_id=feedback.actor_id,
            outcome=feedback.outcome,
            actual_event_label=feedback.actual_event_label,
            routine=feedback.routine,
            created_at=feedback.created_at,
        ),
        memory=ResidentMemoryResponse(
            resident_id=memory.resident_id,
            version=memory.version,
            entries=[
                MemoryEntryResponse(
                    entry_id=entry.entry_id,
                    description=entry.description,
                    source_feedback_id=entry.source_feedback_id,
                    status=entry.status,
                    created_by=entry.created_by,
                    created_at=entry.created_at,
                    retired_by=entry.retired_by,
                    retired_at=entry.retired_at,
                    retirement_reason=entry.retirement_reason,
                )
                for entry in memory.entries
            ],
        ),
        memory_updated=decision.memory_updated,
        baseline_window_eligible=decision.baseline_window_eligible,
        global_label_recorded=decision.global_label_recorded,
    )


def _feedback_repository(request: Request, session: Session) -> FeedbackRepository:
    repository_factory = getattr(
        request.app.state,
        "feedback_repository_factory",
        FeedbackRepository,
    )
    return repository_factory(session)


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


@router.post(
    "/{event_id}/feedback",
    response_model=LearningDecisionResponse,
    responses=MUTATION_ERROR_RESPONSES,
)
def submit_feedback(
    event_id: str,
    body: SubmitFeedbackRequest,
    request: Request,
    context: Annotated[AccessContext, Depends(access_context)],
    key: Annotated[str, Depends(request_idempotency_key)],
    session: Annotated[Session, Depends(database_session)],
) -> LearningDecisionResponse:
    feedback_repository = _feedback_repository(request, session)
    commands = FeedbackCommandService(
        session,
        event_repository=EventRepository(session),
        feedback_repository=feedback_repository,
    )
    idempotency = IdempotencyService(session)
    request_body = body.model_dump(mode="json")
    try:
        result = idempotency.execute(
            context=context,
            key=key,
            method=request.method,
            path=request.url.path,
            request_body=request_body,
            command=lambda: IdempotencyResult(
                status_code=200,
                body=_learning_decision_response(
                    commands.submit_feedback(
                        context,
                        event_id,
                        body.actual_event_label,
                        body.routine,
                        body.created_at,
                    )
                ).model_dump(mode="json"),
            ),
        )
        response = LearningDecisionResponse.model_validate(result.body)
        session.commit()
        return response
    except Exception:
        session.rollback()
        raise
