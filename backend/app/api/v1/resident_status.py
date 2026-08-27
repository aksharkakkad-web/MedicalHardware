from typing import Annotated

from fastapi import APIRouter, Depends, Request

from backend.app.api.dependencies import (
    SetupMutationServices,
    access_context,
    request_idempotency_key,
    setup_mutation_services,
    status_query_service,
)
from backend.app.api.errors import MUTATION_ERROR_RESPONSES, READ_ERROR_RESPONSES
from backend.app.contracts.status import (
    AwarenessTimelineResponse,
    CalibrationResponse,
    ResidentStatusResponse,
    SetupChangeRequest,
)
from backend.app.services.idempotency import IdempotencyResult
from backend.app.services.queries import AccessContext
from backend.app.services.status_queries import (
    ProductStatusQueryService,
    calibration_response,
)


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


@router.post(
    "/{resident_id}/setup-changes",
    response_model=CalibrationResponse,
    responses=MUTATION_ERROR_RESPONSES,
)
def change_resident_setup(
    resident_id: str,
    body: SetupChangeRequest,
    request: Request,
    context: Annotated[AccessContext, Depends(access_context)],
    key: Annotated[str, Depends(request_idempotency_key)],
    services: Annotated[SetupMutationServices, Depends(setup_mutation_services)],
) -> CalibrationResponse:
    request_body = body.model_dump(mode="json")
    try:
        result = services.idempotency.execute(
            context=context,
            key=key,
            method=request.method,
            path=request.url.path,
            request_body=request_body,
            command=lambda: IdempotencyResult(
                status_code=200,
                body=calibration_response(
                    services.commands.change_setup(
                        context,
                        resident_id,
                        reason=body.reason,
                        affected_dimensions=tuple(body.affected_dimensions),
                        changed_at=body.changed_at,
                        expected_calibration_version=(
                            body.expected_calibration_version
                        ),
                    )
                ).model_dump(mode="json"),
            ),
        )
        response = CalibrationResponse.model_validate(result.body)
        services.session.commit()
        return response
    except Exception:
        services.session.rollback()
        raise
