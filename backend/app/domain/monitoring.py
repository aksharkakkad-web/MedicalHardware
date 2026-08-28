from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from backend.app.domain._validation import (
    coerce_enum,
    require_bounded_real,
    require_nonblank_text,
    require_strict_bool,
)


_MINIMUM_QUALITY_UNSET = object()


class PresenceState(StrEnum):
    UNKNOWN = "unknown"
    RESIDENT_PRESENT = "resident_present"
    RESIDENT_AWAY = "resident_away"
    POSSIBLE_MULTI_PERSON = "possible_multi_person"


class MonitoringState(StrEnum):
    ACTIVE = "active"
    LIMITED = "limited"
    PAUSED = "paused"
    UNAVAILABLE = "unavailable"


class MonitoringReason(StrEnum):
    ASSIGNMENT_INVALID = "assignment_invalid"
    DEVICE_UNHEALTHY = "device_unhealthy"
    DEVICE_HEALTH_UNAVAILABLE = "device_health_unavailable"
    RESIDENT_AWAY = "resident_away"
    POSSIBLE_MULTI_PERSON = "possible_multi_person"
    PRESENCE_UNKNOWN = "presence_unknown"
    LOW_SIGNAL_QUALITY = "low_signal_quality"


@dataclass(frozen=True)
class SyntheticMonitoringQualityPolicy:
    """Versioned toy-only signal-quality gate; not a production threshold."""

    TEST_ONLY: ClassVar[bool] = True
    minimum_quality: float = 0.6
    policy_version: str = "synthetic_monitoring_quality_v1"
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "minimum_quality",
            require_bounded_real(
                self.minimum_quality,
                "minimum_quality",
                minimum=0.0,
                maximum=1.0,
            ),
        )
        object.__setattr__(
            self,
            "policy_version",
            require_nonblank_text(self.policy_version, "policy_version"),
        )

    @property
    def test_only(self) -> bool:
        return self.TEST_ONLY


@dataclass(frozen=True)
class MonitoringSnapshot:
    state: MonitoringState
    presence: PresenceState
    baseline_learning_allowed: bool
    resident_measurements_allowed: bool
    reasons: tuple[MonitoringReason, ...]
    quality_policy_version: str = "synthetic_monitoring_quality_v1"
    quality_policy_test_only: bool = True
    schema_version: str = "1.0"


def derive_monitoring_snapshot(
    *,
    assignment_valid: bool,
    device_healthy: bool,
    presence: PresenceState,
    signal_quality: float,
    minimum_quality: object = _MINIMUM_QUALITY_UNSET,
    quality_policy: SyntheticMonitoringQualityPolicy | None = None,
) -> MonitoringSnapshot:
    assignment_valid = require_strict_bool(assignment_valid, "assignment_valid")
    device_healthy = require_strict_bool(device_healthy, "device_healthy")
    presence = coerce_enum(presence, PresenceState, "presence")
    signal_quality = require_bounded_real(
        signal_quality,
        "signal_quality",
        minimum=0.0,
        maximum=1.0,
    )
    if quality_policy is not None and minimum_quality is not _MINIMUM_QUALITY_UNSET:
        raise ValueError("provide quality_policy or minimum_quality, not both")
    if quality_policy is None:
        if minimum_quality is _MINIMUM_QUALITY_UNSET:
            quality_policy = SyntheticMonitoringQualityPolicy()
        else:
            quality_policy = SyntheticMonitoringQualityPolicy(
                minimum_quality=minimum_quality,
                policy_version="synthetic_monitoring_quality_compat_v1",
            )
    elif not isinstance(quality_policy, SyntheticMonitoringQualityPolicy):
        raise ValueError(
            "quality_policy must be a SyntheticMonitoringQualityPolicy"
        )

    reasons: list[MonitoringReason] = []
    if not assignment_valid:
        reasons.append(MonitoringReason.ASSIGNMENT_INVALID)
    if not device_healthy:
        reasons.append(MonitoringReason.DEVICE_UNHEALTHY)

    if reasons:
        return MonitoringSnapshot(
            state=MonitoringState.UNAVAILABLE,
            presence=presence,
            baseline_learning_allowed=False,
            resident_measurements_allowed=False,
            reasons=tuple(reasons),
            quality_policy_version=quality_policy.policy_version,
            quality_policy_test_only=quality_policy.test_only,
        )

    if presence == PresenceState.RESIDENT_AWAY:
        return MonitoringSnapshot(
            state=MonitoringState.PAUSED,
            presence=presence,
            baseline_learning_allowed=False,
            resident_measurements_allowed=False,
            reasons=(MonitoringReason.RESIDENT_AWAY,),
            quality_policy_version=quality_policy.policy_version,
            quality_policy_test_only=quality_policy.test_only,
        )

    if presence == PresenceState.POSSIBLE_MULTI_PERSON:
        return MonitoringSnapshot(
            state=MonitoringState.LIMITED,
            presence=presence,
            baseline_learning_allowed=False,
            resident_measurements_allowed=False,
            reasons=(MonitoringReason.POSSIBLE_MULTI_PERSON,),
            quality_policy_version=quality_policy.policy_version,
            quality_policy_test_only=quality_policy.test_only,
        )

    if presence == PresenceState.UNKNOWN:
        reasons.append(MonitoringReason.PRESENCE_UNKNOWN)
    if signal_quality < quality_policy.minimum_quality:
        reasons.append(MonitoringReason.LOW_SIGNAL_QUALITY)

    if reasons:
        return MonitoringSnapshot(
            state=MonitoringState.LIMITED,
            presence=presence,
            baseline_learning_allowed=False,
            resident_measurements_allowed=False,
            reasons=tuple(reasons),
            quality_policy_version=quality_policy.policy_version,
            quality_policy_test_only=quality_policy.test_only,
        )

    return MonitoringSnapshot(
        state=MonitoringState.ACTIVE,
        presence=presence,
        baseline_learning_allowed=True,
        resident_measurements_allowed=True,
        reasons=(),
        quality_policy_version=quality_policy.policy_version,
        quality_policy_test_only=quality_policy.test_only,
    )
