"""Product-facing device assignment and operational health concepts."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from backend.app.domain._validation import (
    coerce_enum,
    require_aware_datetime,
    require_nonblank_text,
    require_strict_bool,
)


class DeviceHealthState(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    BUFFERING = "buffering"
    RETRYING = "retrying"
    ASSIGNMENT_UNAVAILABLE = "assignment_unavailable"


class DeviceSourceHealthState(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


def _require_utc(value: object, field: str) -> datetime:
    normalized = require_aware_datetime(value, field)
    if normalized.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must use UTC")
    return normalized


def _normalize_nonblank_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ValueError(f"{field} must be a tuple")
    normalized = tuple(require_nonblank_text(item, field) for item in value)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field} must not contain duplicates")
    return normalized


@dataclass(frozen=True)
class DeviceSourceHealth:
    source: str
    state: DeviceSourceHealthState
    limitations: tuple[str, ...] = ()
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source",
            require_nonblank_text(self.source, "source"),
        )
        object.__setattr__(
            self,
            "state",
            coerce_enum(self.state, DeviceSourceHealthState, "state"),
        )
        object.__setattr__(
            self,
            "limitations",
            _normalize_nonblank_tuple(self.limitations, "limitations"),
        )


@dataclass(frozen=True)
class DeviceHealthObservation:
    device_id: str
    state: DeviceHealthState
    observed_at: datetime
    last_seen_at: datetime | None
    sources: tuple[DeviceSourceHealth, ...]
    limitations: tuple[str, ...]
    policy_version: str = "synthetic_device_health_v1"
    policy_test_only: bool = True
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "device_id",
            require_nonblank_text(self.device_id, "device_id"),
        )
        object.__setattr__(
            self,
            "state",
            coerce_enum(self.state, DeviceHealthState, "state"),
        )
        observed_at = _require_utc(self.observed_at, "observed_at")
        object.__setattr__(self, "observed_at", observed_at)
        if self.last_seen_at is not None:
            last_seen_at = _require_utc(self.last_seen_at, "last_seen_at")
            if last_seen_at > observed_at:
                raise ValueError("last_seen_at must not be after observed_at")
            object.__setattr__(self, "last_seen_at", last_seen_at)
        if not isinstance(self.sources, tuple):
            raise ValueError("sources must be a tuple")
        if any(not isinstance(source, DeviceSourceHealth) for source in self.sources):
            raise ValueError("sources must contain DeviceSourceHealth records")
        source_names = tuple(source.source for source in self.sources)
        if len(set(source_names)) != len(source_names):
            raise ValueError("sources must not contain duplicate source names")
        object.__setattr__(
            self,
            "limitations",
            _normalize_nonblank_tuple(self.limitations, "limitations"),
        )
        object.__setattr__(
            self,
            "policy_version",
            require_nonblank_text(self.policy_version, "policy_version"),
        )
        object.__setattr__(
            self,
            "policy_test_only",
            require_strict_bool(self.policy_test_only, "policy_test_only"),
        )


__all__ = [
    "DeviceHealthObservation",
    "DeviceHealthState",
    "DeviceSourceHealth",
    "DeviceSourceHealthState",
]
