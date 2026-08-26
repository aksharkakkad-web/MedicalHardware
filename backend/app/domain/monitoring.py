from dataclasses import dataclass
from enum import StrEnum


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
    RESIDENT_AWAY = "resident_away"
    POSSIBLE_MULTI_PERSON = "possible_multi_person"
    PRESENCE_UNKNOWN = "presence_unknown"
    LOW_SIGNAL_QUALITY = "low_signal_quality"


@dataclass(frozen=True)
class MonitoringSnapshot:
    state: MonitoringState
    presence: PresenceState
    baseline_learning_allowed: bool
    resident_measurements_allowed: bool
    reasons: tuple[MonitoringReason, ...]


def derive_monitoring_snapshot(
    *,
    assignment_valid: bool,
    device_healthy: bool,
    presence: PresenceState,
    signal_quality: float,
    minimum_quality: float = 0.6,
) -> MonitoringSnapshot:
    if not 0.0 <= signal_quality <= 1.0:
        raise ValueError("signal_quality must be between 0.0 and 1.0")

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
        )

    if presence == PresenceState.RESIDENT_AWAY:
        return MonitoringSnapshot(
            state=MonitoringState.PAUSED,
            presence=presence,
            baseline_learning_allowed=False,
            resident_measurements_allowed=False,
            reasons=(MonitoringReason.RESIDENT_AWAY,),
        )

    if presence == PresenceState.POSSIBLE_MULTI_PERSON:
        return MonitoringSnapshot(
            state=MonitoringState.LIMITED,
            presence=presence,
            baseline_learning_allowed=False,
            resident_measurements_allowed=False,
            reasons=(MonitoringReason.POSSIBLE_MULTI_PERSON,),
        )

    if presence == PresenceState.UNKNOWN:
        reasons.append(MonitoringReason.PRESENCE_UNKNOWN)
    if signal_quality < minimum_quality:
        reasons.append(MonitoringReason.LOW_SIGNAL_QUALITY)

    if reasons:
        return MonitoringSnapshot(
            state=MonitoringState.LIMITED,
            presence=presence,
            baseline_learning_allowed=False,
            resident_measurements_allowed=False,
            reasons=tuple(reasons),
        )

    return MonitoringSnapshot(
        state=MonitoringState.ACTIVE,
        presence=presence,
        baseline_learning_allowed=True,
        resident_measurements_allowed=True,
        reasons=(),
    )
