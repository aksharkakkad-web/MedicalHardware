from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from backend.app.db.repositories import (
    EventRepository,
    FeedbackRepository,
    ResidentRepository,
)
from backend.app.domain._validation import require_nonblank_text
from backend.app.services.errors import InvalidInputError
from backend.app.services.queries import AccessContext, ProductQueryService


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
