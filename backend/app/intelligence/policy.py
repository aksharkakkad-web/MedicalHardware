"""Versioned deterministic disposition and caregiver-attention policy."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from math import isfinite
from numbers import Real
from typing import ClassVar

from backend.app.ai.client import (
    InterpretationResult,
    InterpretationStatus,
    RecommendedDisposition,
)
from backend.app.domain._validation import require_nonblank_text
from backend.app.domain.events import EventPriority
from backend.app.intelligence.degradation import DegradationAssessment
from backend.app.intelligence.evidence import EvidencePacket
from backend.app.intelligence.fall_detection import FallLikeAssessment
from backend.app.intelligence.observations import _require_utc


class PolicyDisposition(StrEnum):
    NO_ACTION = "no_action"
    OBSERVE = "observe"
    AWARENESS = "awareness"
    CAREGIVER_EVENT = "caregiver_event"


@dataclass(frozen=True)
class DispositionDecision:
    disposition: PolicyDisposition
    priority: EventPriority | None
    confidence: str
    objective_family: str
    headline: str
    reasons: tuple[str, ...]
    policy_version: str
    fallback_used: bool
    room_level_only: bool
    interpretation_id: str | None = None
    provisional_urgent: bool = False
    attention_suppressed: bool = False
    schema_version: str = "1.0"


@dataclass(frozen=True)
class SyntheticDispositionPolicy:
    """Synthetic test-only thresholds; these values have no clinical authority."""

    TEST_ONLY: ClassVar[bool] = True
    CLINICAL_AUTHORITY: ClassVar[bool] = False
    awareness_strength: float = 3.0
    caregiver_event_strength: float = 5.0
    critical_strength: float = 7.0
    policy_version: str = "synthetic_disposition_v1"
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        values = []
        for field in (
            "awareness_strength",
            "caregiver_event_strength",
            "critical_strength",
        ):
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, Real):
                raise ValueError(f"{field} must be a real number")
            normalized = float(value)
            if not isfinite(normalized) or normalized < 0.0:
                raise ValueError(f"{field} must be finite and nonnegative")
            object.__setattr__(self, field, normalized)
            values.append(normalized)
        if not values[0] <= values[1] <= values[2]:
            raise ValueError(
                "strengths must satisfy awareness <= caregiver event <= critical"
            )
        object.__setattr__(
            self,
            "policy_version",
            require_nonblank_text(self.policy_version, "policy_version"),
        )
        object.__setattr__(
            self,
            "schema_version",
            require_nonblank_text(self.schema_version, "schema_version"),
        )
        if (
            self.policy_version == "synthetic_disposition_v1"
            and tuple(values) != (3.0, 5.0, 7.0)
        ):
            raise ValueError("custom policy values require a distinct policy_version")

    @property
    def test_only(self) -> bool:
        return self.TEST_ONLY

    @property
    def clinical_authority(self) -> bool:
        return self.CLINICAL_AUTHORITY

    def decide(
        self,
        *,
        packet: EvidencePacket | None,
        interpretation: InterpretationResult | None,
        interpretation_failed: bool,
        fall_assessment: FallLikeAssessment,
        degradation: DegradationAssessment,
        resident_away: bool,
        possible_multiple_people: bool,
    ) -> DispositionDecision:
        """Apply the fixed safety-first ordering to already-derived evidence."""

        if fall_assessment.urgent_triggered:
            room_level = fall_assessment.room_level_only or possible_multiple_people
            return self._decision(
                PolicyDisposition.CAREGIVER_EVENT,
                priority=EventPriority.CRITICAL,
                confidence=fall_assessment.confidence,
                objective_family="fall_like",
                headline=(
                    "Room-level fall-like signal pattern"
                    if room_level
                    else "Fall-like signal pattern"
                ),
                reasons=("urgent_fall_like", *fall_assessment.limitations),
                room_level_only=room_level,
                provisional_urgent=True,
            )

        if degradation.degraded:
            return self._decision(
                PolicyDisposition.AWARENESS,
                confidence="operational",
                objective_family="monitoring_degraded",
                headline="Monitoring quality needs review",
                reasons=tuple(kind.value for kind in degradation.kinds),
            )

        if resident_away:
            return self._decision(
                PolicyDisposition.NO_ACTION,
                confidence="not_applicable",
                objective_family="resident_away",
                headline="Resident-away context",
                reasons=("resident_away",),
            )

        if possible_multiple_people:
            return self._decision(
                (
                    PolicyDisposition.AWARENESS
                    if packet is not None
                    else PolicyDisposition.NO_ACTION
                ),
                confidence="attribution_ambiguous",
                objective_family="multi_person_ambiguity",
                headline="Room occupancy attribution is ambiguous",
                reasons=("possible_multiple_people",),
                room_level_only=True,
            )

        if packet is None or packet.lifecycle_state.value == "closed":
            return self._decision(
                PolicyDisposition.NO_ACTION,
                confidence="none",
                objective_family="none",
                headline="No active anomaly",
                reasons=("no_active_anomaly",),
            )

        strength = packet.overall_strength
        if interpretation is not None and (
            interpretation.status == InterpretationStatus.COMPLETE
        ):
            recommended = RecommendedDisposition(
                interpretation.recommended_disposition
            )
            selected = PolicyDisposition(recommended.value)
            if selected == PolicyDisposition.CAREGIVER_EVENT and (
                strength is None or strength < self.caregiver_event_strength
            ):
                selected = PolicyDisposition.AWARENESS
            priority = self._priority(strength) if (
                selected == PolicyDisposition.CAREGIVER_EVENT
            ) else None
            family = str(interpretation.likely_explanation)
            return self._decision(
                selected,
                priority=priority,
                confidence="interpreted",
                objective_family=family,
                headline=self._headline(family),
                reasons=("validated_interpretation",),
                interpretation_id=interpretation.interpretation_id,
            )

        fallback = interpretation_failed or interpretation is None
        if strength is None:
            selected = PolicyDisposition.OBSERVE
        elif strength >= self.caregiver_event_strength:
            selected = PolicyDisposition.CAREGIVER_EVENT
        elif strength >= self.awareness_strength:
            selected = PolicyDisposition.AWARENESS
        else:
            selected = PolicyDisposition.OBSERVE
        return self._decision(
            selected,
            priority=(
                self._priority(strength)
                if selected == PolicyDisposition.CAREGIVER_EVENT
                else None
            ),
            confidence="objective_only",
            objective_family="unknown_anomaly",
            headline="Unclassified anomaly evidence",
            reasons=("objective_fallback",),
            fallback_used=fallback,
        )

    def _priority(self, strength: float | None) -> EventPriority:
        return (
            EventPriority.CRITICAL
            if strength is not None and strength >= self.critical_strength
            else EventPriority.HIGH
        )

    def _decision(
        self,
        disposition: PolicyDisposition,
        *,
        priority: EventPriority | None = None,
        confidence: str,
        objective_family: str,
        headline: str,
        reasons: tuple[str, ...],
        fallback_used: bool = False,
        room_level_only: bool = False,
        interpretation_id: str | None = None,
        provisional_urgent: bool = False,
    ) -> DispositionDecision:
        return DispositionDecision(
            disposition=disposition,
            priority=priority,
            confidence=confidence,
            objective_family=objective_family,
            headline=headline,
            reasons=tuple(dict.fromkeys(reasons)),
            policy_version=self.policy_version,
            fallback_used=fallback_used,
            room_level_only=room_level_only,
            interpretation_id=interpretation_id,
            provisional_urgent=provisional_urgent,
        )

    @staticmethod
    def _headline(objective_family: str) -> str:
        return {
            "unusual_movement": "Unusual movement pattern",
            "routine_movement": "Possible routine movement pattern",
            "inactivity": "Inactivity pattern",
            "respiratory_change": "Respiratory signal change",
            "routine_change": "Routine-change pattern",
            "unknown": "Unclassified anomaly evidence",
        }.get(objective_family, "Anomaly evidence needs review")


@dataclass(frozen=True)
class EventAttentionPolicy:
    """Synthetic recommendation policy; external notification delivery is out of scope."""

    TEST_ONLY: ClassVar[bool] = True
    acknowledged_cooldown: timedelta = timedelta(minutes=30)
    policy_version: str = "synthetic_event_attention_v1"
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if not isinstance(self.acknowledged_cooldown, timedelta):
            raise ValueError("acknowledged_cooldown must be a timedelta")
        if self.acknowledged_cooldown <= timedelta(0):
            raise ValueError("acknowledged_cooldown must be positive")
        object.__setattr__(
            self,
            "policy_version",
            require_nonblank_text(self.policy_version, "policy_version"),
        )
        object.__setattr__(
            self,
            "schema_version",
            require_nonblank_text(self.schema_version, "schema_version"),
        )
        if (
            self.policy_version == "synthetic_event_attention_v1"
            and self.acknowledged_cooldown != timedelta(minutes=30)
        ):
            raise ValueError("custom policy values require a distinct policy_version")

    @property
    def test_only(self) -> bool:
        return self.TEST_ONLY

    def suppression_until(
        self,
        priority: EventPriority,
        acknowledged_at: datetime,
    ) -> datetime | None:
        acknowledged = _require_utc(acknowledged_at, "acknowledged_at")
        if EventPriority(priority) == EventPriority.CRITICAL:
            return None
        return acknowledged + self.acknowledged_cooldown


__all__ = [
    "DispositionDecision",
    "EventAttentionPolicy",
    "PolicyDisposition",
    "SyntheticDispositionPolicy",
]
