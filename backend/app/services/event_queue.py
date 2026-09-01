"""Clinic event queue normalization, pagination cursors, and public reads."""

from __future__ import annotations

import base64
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re

from backend.app.contracts.events import (
    ClinicEventQueueResponse,
    ClinicEventStatus,
)
from backend.app.db.repositories import EventQueuePosition, EventRepository
from backend.app.db.intelligence_repositories import IntelligenceRepository
from backend.app.domain.events import EventPriority, EventStatus
from backend.app.services.errors import InvalidInputError
from backend.app.services.queries import AccessContext, event_response


_ACTIVE_STATUSES = (
    ClinicEventStatus.OPEN,
    ClinicEventStatus.ACKNOWLEDGED,
    ClinicEventStatus.CHECKED,
)
_STATUS_ORDER = (
    ClinicEventStatus.OPEN,
    ClinicEventStatus.ACKNOWLEDGED,
    ClinicEventStatus.CHECKED,
    ClinicEventStatus.RESOLVED,
)
_PRIORITY_ORDER = (
    EventPriority.CRITICAL,
    EventPriority.HIGH,
    EventPriority.WATCH,
)
_CURSOR_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
_CURSOR_VERSION = 1


@dataclass(frozen=True)
class EventQueueQuery:
    statuses: Sequence[ClinicEventStatus] = ()
    priorities: Sequence[EventPriority] = ()
    resident_id: str | None = None
    room_id: str | None = None
    limit: int = 25
    cursor: str | None = None


@dataclass(frozen=True)
class NormalizedEventQueueQuery:
    statuses: tuple[ClinicEventStatus, ...]
    priorities: tuple[EventPriority, ...]
    resident_id: str | None
    room_id: str | None
    limit: int
    cursor: str | None


def normalize_event_queue_query(
    query: EventQueueQuery,
) -> NormalizedEventQueueQuery:
    statuses = _normalize_enum_values(
        query.statuses or _ACTIVE_STATUSES,
        ClinicEventStatus,
        _STATUS_ORDER,
        "status",
    )
    priorities = _normalize_enum_values(
        query.priorities,
        EventPriority,
        _PRIORITY_ORDER,
        "priority",
    )
    resident_id = _optional_nonblank(query.resident_id, "resident_id")
    room_id = _optional_nonblank(query.room_id, "room_id")
    if isinstance(query.limit, bool) or not isinstance(query.limit, int):
        raise InvalidInputError(field="limit")
    if not 1 <= query.limit <= 100:
        raise InvalidInputError(field="limit")
    cursor = _optional_nonblank(query.cursor, "cursor")
    return NormalizedEventQueueQuery(
        statuses=statuses,
        priorities=priorities,
        resident_id=resident_id,
        room_id=room_id,
        limit=query.limit,
        cursor=cursor,
    )


def encode_event_queue_cursor(
    query: NormalizedEventQueueQuery,
    position: EventQueuePosition,
    *,
    tenant_id: str,
) -> str:
    payload = {
        "v": _CURSOR_VERSION,
        "f": _filter_digest(query, tenant_id),
        "p": {
            "resolved": position.resolved,
            "priority": position.priority.value,
            "overdue": position.overdue,
            "last_signal_at": _utc_text(position.last_signal_at),
            "created_at": _utc_text(position.created_at),
            "event_id": position.event_id,
        },
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).decode("ascii")
    return encoded.rstrip("=")


def decode_event_queue_cursor(
    cursor: str,
    query: NormalizedEventQueueQuery,
    *,
    tenant_id: str,
) -> EventQueuePosition:
    try:
        if not cursor or len(cursor) > 4096 or not _CURSOR_PATTERN.fullmatch(cursor):
            raise ValueError("invalid cursor encoding")
        padding = "=" * (-len(cursor) % 4)
        decoded = base64.b64decode(
            cursor + padding,
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(decoded)
        if not isinstance(payload, dict) or set(payload) != {"v", "f", "p"}:
            raise ValueError("invalid cursor payload")
        if payload["v"] != _CURSOR_VERSION:
            raise ValueError("unsupported cursor version")
        expected_digest = _filter_digest(query, tenant_id)
        if not isinstance(payload["f"], str) or not hmac.compare_digest(
            payload["f"],
            expected_digest,
        ):
            raise ValueError("cursor filters do not match")
        position = payload["p"]
        if not isinstance(position, dict) or set(position) != {
            "resolved",
            "priority",
            "overdue",
            "last_signal_at",
            "created_at",
            "event_id",
        }:
            raise ValueError("invalid cursor position")
        if not isinstance(position["resolved"], bool):
            raise ValueError("invalid resolved position")
        if not isinstance(position["overdue"], bool):
            raise ValueError("invalid overdue position")
        event_id = position["event_id"]
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("invalid event position")
        return EventQueuePosition(
            resolved=position["resolved"],
            priority=EventPriority(position["priority"]),
            overdue=position["overdue"],
            last_signal_at=_parse_utc(position["last_signal_at"]),
            created_at=_parse_utc(position["created_at"]),
            event_id=event_id,
        )
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise InvalidInputError(field="cursor") from error


class ProductEventQueueQueryService:
    def __init__(
        self,
        events: EventRepository,
        intelligence: IntelligenceRepository | None = None,
    ) -> None:
        self._events = events
        self._intelligence = intelligence

    def _response(self, context: AccessContext, stored):
        event = stored.event
        analysis = (
            None
            if self._intelligence is None
            or event.source_anomaly_id is None
            or event.latest_evidence_revision is None
            else self._intelligence.analysis_for_revision(
                context.tenant_id,
                event.source_anomaly_id,
                event.latest_evidence_revision,
            )
        )
        return event_response(stored, analysis)

    def list_events(
        self,
        context: AccessContext,
        query: EventQueueQuery,
    ) -> ClinicEventQueueResponse:
        normalized = normalize_event_queue_query(query)
        after = (
            None
            if normalized.cursor is None
            else decode_event_queue_cursor(
                normalized.cursor,
                normalized,
                tenant_id=context.tenant_id,
            )
        )
        page = self._events.list_for_tenant(
            context.tenant_id,
            statuses=tuple(EventStatus(item.value) for item in normalized.statuses),
            priorities=normalized.priorities,
            resident_id=normalized.resident_id,
            room_id=normalized.room_id,
            limit=normalized.limit,
            after=after,
        )
        return ClinicEventQueueResponse(
            items=[self._response(context, item) for item in page.items],
            total_items=page.total_items,
            next_cursor=(
                None
                if page.next_position is None
                else encode_event_queue_cursor(
                    normalized,
                    page.next_position,
                    tenant_id=context.tenant_id,
                )
            ),
        )


def _normalize_enum_values(
    values: Sequence[object],
    enum_type: type[ClinicEventStatus] | type[EventPriority],
    order: Sequence[ClinicEventStatus] | Sequence[EventPriority],
    field: str,
) -> tuple:
    try:
        normalized = {enum_type(value) for value in values}
    except (TypeError, ValueError) as error:
        raise InvalidInputError(field=field) from error
    return tuple(item for item in order if item in normalized)


def _optional_nonblank(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidInputError(field=field)
    normalized = value.strip()
    if not normalized:
        raise InvalidInputError(field=field)
    return normalized


def _filter_digest(
    query: NormalizedEventQueueQuery,
    tenant_id: str,
) -> str:
    filters = {
        "tenant_id": tenant_id,
        "statuses": [status.value for status in query.statuses],
        "priorities": [priority.value for priority in query.priorities],
        "resident_id": query.resident_id,
        "room_id": query.room_id,
    }
    canonical = json.dumps(filters, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _utc_text(value: datetime) -> str:
    if value.utcoffset() != timedelta(0):
        raise ValueError("cursor timestamps must use UTC")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("cursor timestamp must be text")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("cursor timestamp must use UTC")
    return parsed.astimezone(timezone.utc)


__all__ = [
    "EventQueueQuery",
    "NormalizedEventQueueQuery",
    "ProductEventQueueQueryService",
    "decode_event_queue_cursor",
    "encode_event_queue_cursor",
    "normalize_event_queue_query",
]
