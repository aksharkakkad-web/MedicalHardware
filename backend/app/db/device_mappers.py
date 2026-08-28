"""Mappings between device domain records and durable rows."""

from dataclasses import dataclass
from datetime import datetime, timezone

from backend.app.db.models import DeviceHealthObservationRow
from backend.app.domain.device_health import (
    DeviceHealthObservation,
    DeviceHealthState,
    DeviceSourceHealth,
    DeviceSourceHealthState,
)


@dataclass(frozen=True)
class StoredDeviceAssignment:
    assignment_id: str
    location_id: str
    location_label: str
    room_id: str
    room_label: str
    effective_from: datetime


@dataclass(frozen=True)
class StoredDevice:
    device_id: str
    display_label: str
    assignment: StoredDeviceAssignment | None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _stored_nonblank(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"stored {field} must be a nonblank string")
    return value.strip()


def _stored_string_list(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"stored {field} must be a list")
    normalized = tuple(_stored_nonblank(item, field) for item in value)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"stored {field} must not contain duplicates")
    return normalized


def health_to_row(
    tenant_id: str,
    observation: DeviceHealthObservation,
) -> DeviceHealthObservationRow:
    return DeviceHealthObservationRow(
        tenant_id=tenant_id,
        device_id=observation.device_id,
        observed_at=_utc(observation.observed_at),
        last_seen_at=(
            None
            if observation.last_seen_at is None
            else _utc(observation.last_seen_at)
        ),
        state=observation.state.value,
        sources=[
            {
                "source": source.source,
                "state": source.state.value,
                "limitations": list(source.limitations),
            }
            for source in observation.sources
        ],
        limitations=list(observation.limitations),
        policy_version=observation.policy_version,
        policy_test_only=observation.policy_test_only,
    )


def health_from_row(row: DeviceHealthObservationRow) -> DeviceHealthObservation:
    if not isinstance(row.sources, list):
        raise ValueError("stored sources must be a list")
    required_keys = {"source", "state", "limitations"}
    sources: list[DeviceSourceHealth] = []
    seen: set[str] = set()
    for item in row.sources:
        if not isinstance(item, dict) or set(item) != required_keys:
            raise ValueError("stored sources are malformed")
        source_name = _stored_nonblank(item["source"], "source")
        if source_name in seen:
            raise ValueError("stored sources must not contain duplicates")
        seen.add(source_name)
        sources.append(
            DeviceSourceHealth(
                source=source_name,
                state=DeviceSourceHealthState(
                    _stored_nonblank(item["state"], "source state")
                ),
                limitations=_stored_string_list(
                    item["limitations"],
                    "source limitations",
                ),
            )
        )
    return DeviceHealthObservation(
        device_id=row.device_id,
        state=DeviceHealthState(row.state),
        observed_at=_utc(row.observed_at),
        last_seen_at=(None if row.last_seen_at is None else _utc(row.last_seen_at)),
        sources=tuple(sources),
        limitations=_stored_string_list(row.limitations, "limitations"),
        policy_version=row.policy_version,
        policy_test_only=row.policy_test_only,
    )


__all__ = [
    "StoredDevice",
    "StoredDeviceAssignment",
    "health_from_row",
    "health_to_row",
]
