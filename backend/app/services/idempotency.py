"""Request fingerprinting and durable idempotent response replay."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from backend.app.db.models import IdempotencyRecordRow, TenantRow
from backend.app.services.errors import IdempotencyConflictError, NotFoundError
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
        if self._session.get(TenantRow, context.tenant_id) is None:
            raise NotFoundError()
        request_fingerprint = fingerprint(
            {
                "tenant_id": context.tenant_id,
                "actor_id": context.actor_id,
                "method": method,
                "path": path,
                "body": request_body,
            }
        )
        reservation_id = self._reserve(
            context,
            key,
            request_fingerprint,
        )
        if reservation_id is None:
            existing = self._get(context, key)
            if existing is None:
                raise RuntimeError("idempotency reservation winner is unavailable")
            if existing.request_fingerprint != request_fingerprint:
                raise IdempotencyConflictError()
            return IdempotencyResult(
                status_code=existing.response_status,
                body=existing.response_body,
            )

        result = command()
        self._session.execute(
            update(IdempotencyRecordRow)
            .where(IdempotencyRecordRow.idempotency_id == reservation_id)
            .values(
                response_status=result.status_code,
                response_body=result.body,
            )
        )
        self._session.flush()
        return result

    def _reserve(
        self,
        context: AccessContext,
        key: str,
        request_fingerprint: str,
    ) -> int | None:
        values = {
            "tenant_id": context.tenant_id,
            "actor_id": context.actor_id,
            "key": key,
            "request_fingerprint": request_fingerprint,
            "response_status": 0,
            "response_body": {},
            "created_at": datetime.now(timezone.utc),
        }
        dialect_name = self._session.get_bind().dialect.name
        if dialect_name == "sqlite":
            statement = sqlite_insert(IdempotencyRecordRow).values(**values)
        elif dialect_name == "postgresql":
            statement = postgresql_insert(IdempotencyRecordRow).values(**values)
        else:
            raise RuntimeError(
                f"unsupported idempotency database dialect: {dialect_name}"
            )
        statement = statement.on_conflict_do_nothing(
            index_elements=["tenant_id", "actor_id", "key"]
        ).returning(IdempotencyRecordRow.idempotency_id)
        return self._session.scalar(statement)

    def _get(
        self,
        context: AccessContext,
        key: str,
    ) -> IdempotencyRecordRow | None:
        return self._session.scalar(
            select(IdempotencyRecordRow).where(
                IdempotencyRecordRow.tenant_id == context.tenant_id,
                IdempotencyRecordRow.actor_id == context.actor_id,
                IdempotencyRecordRow.key == key,
            )
        )
