from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from backend.app.db.repositories import (
    EventRepository,
    FeedbackRepository,
    ResidentRepository,
)
from backend.app.db.device_repositories import (
    DeviceHealthRepository,
    DeviceRepository,
)
from backend.app.db.status_repositories import (
    CalibrationRepository,
    MonitoringStatusRepository,
)
from backend.app.domain._validation import require_nonblank_text
from backend.app.services.event_commands import EventCommandService
from backend.app.services.device_queries import ProductDeviceQueryService
from backend.app.services.errors import InvalidInputError
from backend.app.services.idempotency import IdempotencyService
from backend.app.services.queries import AccessContext, ProductQueryService
from backend.app.services.setup_commands import SetupChangeCommandService
from backend.app.services.status_queries import ProductStatusQueryService


def access_context(
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-Id")],
    x_actor_id: Annotated[str, Header(alias="X-Actor-Id")],
) -> AccessContext:
    try:
        return AccessContext(
            require_nonblank_text(x_tenant_id, "X-Tenant-Id"),
            require_nonblank_text(x_actor_id, "X-Actor-Id"),
        )
    except ValueError as error:
        field = "X-Tenant-Id" if not x_tenant_id.strip() else "X-Actor-Id"
        raise InvalidInputError(field=field) from error


def request_idempotency_key(
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> str:
    try:
        return require_nonblank_text(idempotency_key, "Idempotency-Key")
    except ValueError as error:
        raise InvalidInputError(field="Idempotency-Key") from error


def database_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def query_service(
    session: Annotated[Session, Depends(database_session)],
) -> ProductQueryService:
    return ProductQueryService(
        ResidentRepository(session),
        EventRepository(session),
        FeedbackRepository(session),
    )


def device_query_service(
    session: Annotated[Session, Depends(database_session)],
) -> ProductDeviceQueryService:
    return ProductDeviceQueryService(
        DeviceRepository(session),
        DeviceHealthRepository(session),
    )


def status_query_service(
    session: Annotated[Session, Depends(database_session)],
) -> ProductStatusQueryService:
    return ProductStatusQueryService(
        ResidentRepository(session),
        MonitoringStatusRepository(session),
        CalibrationRepository(session),
        DeviceRepository(session),
        DeviceHealthRepository(session),
    )


@dataclass(frozen=True)
class EventMutationServices:
    session: Session
    commands: EventCommandService
    idempotency: IdempotencyService


@dataclass(frozen=True)
class SetupMutationServices:
    session: Session
    commands: SetupChangeCommandService
    idempotency: IdempotencyService


def event_mutation_services(
    session: Annotated[Session, Depends(database_session)],
) -> EventMutationServices:
    return EventMutationServices(
        session=session,
        commands=EventCommandService(session, EventRepository(session)),
        idempotency=IdempotencyService(session),
    )


def setup_mutation_services(
    request: Request,
    session: Annotated[Session, Depends(database_session)],
) -> SetupMutationServices:
    repository_factory = getattr(
        request.app.state,
        "calibration_repository_factory",
        CalibrationRepository,
    )
    return SetupMutationServices(
        session=session,
        commands=SetupChangeCommandService(
            session,
            residents=ResidentRepository(session),
            calibration=repository_factory(session),
        ),
        idempotency=IdempotencyService(session),
    )
