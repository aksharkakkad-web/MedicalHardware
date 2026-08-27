"""Request fingerprinting and durable idempotent response replay."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models import IdempotencyRecordRow
from backend.app.services.errors import IdempotencyConflictError
from backend.app.services.queries import AccessContext


def fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class IdempotencyResult:
    status_code: int
    body: dict[str, object]


class IdempotencyService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def execute(
        self,
        *,
        context: AccessContext,
        key: str,
        method: str,
        path: str,
        request_body: dict[str, object],
        command: Callable[[], IdempotencyResult],
    ) -> IdempotencyResult:
        request_fingerprint = fingerprint(
            {
                "tenant_id": context.tenant_id,
                "actor_id": context.actor_id,
                "method": method,
                "path": path,
                "body": request_body,
            }
        )
        existing = self._session.scalar(
            select(IdempotencyRecordRow).where(
                IdempotencyRecordRow.tenant_id == context.tenant_id,
                IdempotencyRecordRow.actor_id == context.actor_id,
                IdempotencyRecordRow.key == key,
            )
        )
        if existing is not None:
            if existing.request_fingerprint != request_fingerprint:
                raise IdempotencyConflictError()
            return IdempotencyResult(
                status_code=existing.response_status,
                body=existing.response_body,
            )

        result = command()
        self._session.add(
            IdempotencyRecordRow(
                tenant_id=context.tenant_id,
                actor_id=context.actor_id,
                key=key,
                request_fingerprint=request_fingerprint,
                response_status=result.status_code,
                response_body=result.body,
                created_at=datetime.now(timezone.utc),
            )
        )
        self._session.flush()
        return result
