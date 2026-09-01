"""Versioned deterministic disposition and caregiver-attention policy."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from math import isfinite
from numbers import Real
from typing import ClassVar

from backend.app.ai.analysis_contracts import (
    AnalysisRun,
    AnalysisState,
    AttributionScope,
    Severity,
)
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
    analysis_id: str | None = None
    provisional_urgent: bool = False
    attention_suppressed: bool = False
    schema_version: str = "1.0"


@dataclass(frozen=True)
class SyntheticDispositionPolicy:
    """Legacy one-shot compatibility policy with no clinical authority."""

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

        if possible_multiple_people and not fall_assessment.urgent_triggered:
            return self._decision(
                PolicyDisposition.AWARENESS,
                confidence="attribution_ambiguous",
                objective_family="multi_person_ambiguity",
                headline="Room occupancy attribution is ambiguous",
                reasons=("possible_multiple_people",),
                room_level_only=True,
            )

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
            interpreted = PolicyDisposition(recommended.value)
            if interpreted == PolicyDisposition.CAREGIVER_EVENT and (
                strength is None or strength < self.caregiver_event_strength
            ):
                interpreted = PolicyDisposition.AWARENESS
            if strength is None:
                objective = PolicyDisposition.OBSERVE
            elif strength >= self.caregiver_event_strength:
                objective = PolicyDisposition.CAREGIVER_EVENT
            elif strength >= self.awareness_strength:
                objective = PolicyDisposition.AWARENESS
            else:
                objective = PolicyDisposition.OBSERVE
            rank = {
                PolicyDisposition.NO_ACTION: 0,
                PolicyDisposition.OBSERVE: 1,
                PolicyDisposition.AWARENESS: 2,
                PolicyDisposition.CAREGIVER_EVENT: 3,
            }
            selected = objective if rank[objective] > rank[interpreted] else interpreted
            priority = self._priority(strength) if (
                selected == PolicyDisposition.CAREGIVER_EVENT
            ) else None
            family = str(interpretation.likely_explanation)
            reasons = ["validated_interpretation"]
            if selected == PolicyDisposition.CAREGIVER_EVENT and interpreted != selected:
                reasons.append("objective_strength_requires_caregiver_event")
            elif selected == PolicyDisposition.AWARENESS and interpreted != selected:
                reasons.append("objective_strength_requires_awareness")
            return self._decision(
                selected,
                priority=priority,
                confidence="interpreted",
                objective_family=family,
                headline=self._headline(family),
                reasons=tuple(reasons),
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
class MultiAgentDispositionPolicy:
    """Map one validated final analysis into operational event mechanics.

    This policy deliberately does not compare the AI decision with numerical
    anomaly strength. Grounding validation happens before this boundary.
    """

    policy_version: str = "multi_agent_disposition_v1"
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field in ("policy_version", "schema_version"):
            object.__setattr__(
                self,
                field,
                require_nonblank_text(getattr(self, field), field),
            )

    def decide(
        self,
        *,
        packet: EvidencePacket | None,
        analysis_run: AnalysisRun | None,
    ) -> DispositionDecision:
        if packet is None or packet.lifecycle_state.value == "closed":
            return self._decision(
                PolicyDisposition.NO_ACTION,
                confidence="none",
                objective_family="none",
                headline="No active anomaly",
                reasons=("no_active_anomaly",),
            )

        if analysis_run is None:
            return self._pending("analysis_pending", ("analysis_not_started",))

        if (
            analysis_run.anomaly_id != packet.anomaly_id
            or analysis_run.packet_revision != packet.packet_revision
        ):
            return self._pending(
                "needs_staff_review",
                ("analysis_identity_mismatch",),
            )

        if analysis_run.state is not AnalysisState.ANALYZED:
            confidence = (
                "needs_staff_review"
                if analysis_run.state
                in (AnalysisState.NEEDS_STAFF_REVIEW, AnalysisState.ANALYSIS_REJECTED)
                else "analysis_pending"
            )
            return self._pending(
                confidence,
                tuple(dict.fromkeys((analysis_run.state.value, *analysis_run.errors))),
                analysis_id=analysis_run.analysis_id,
            )

        final = analysis_run.final_analysis
        if final is None:
            return self._pending(
                "needs_staff_review",
                ("analyzed_result_missing_final_analysis",),
                analysis_id=analysis_run.analysis_id,
            )

        disposition = PolicyDisposition(final.recommended_disposition.value)
        priority = None
        if disposition is PolicyDisposition.CAREGIVER_EVENT:
            priority = (
                EventPriority.CRITICAL
                if final.severity is Severity.CRITICAL
                else EventPriority.HIGH
            )
        primary = final.possibilities[0]
        objective_family = "_".join(primary.label.casefold().split())[:80]
        return self._decision(
            disposition,
            priority=priority,
            confidence="interpreted",
            objective_family=objective_family,
            headline=final.caregiver_summary,
            reasons=("trusted_final_analysis",),
            room_level_only=(
                final.attribution_scope is not AttributionScope.RESIDENT
                or "resident_attribution_ambiguous" in packet.limitations
            ),
            analysis_id=final.analysis_id,
        )

    def _pending(
        self,
        confidence: str,
        reasons: tuple[str, ...],
        *,
        analysis_id: str | None = None,
    ) -> DispositionDecision:
        return self._decision(
            PolicyDisposition.OBSERVE,
            confidence=confidence,
            objective_family="unknown_anomaly",
            headline=(
                "Anomaly analysis needs staff review"
                if confidence == "needs_staff_review"
                else "Anomaly analysis is pending"
            ),
            reasons=reasons,
            fallback_used=True,
            analysis_id=analysis_id,
        )

    def _decision(
        self,
        disposition: PolicyDisposition,
        *,
        confidence: str,
        objective_family: str,
        headline: str,
        reasons: tuple[str, ...],
        priority: EventPriority | None = None,
        fallback_used: bool = False,
        room_level_only: bool = False,
        interpretation_id: str | None = None,
        analysis_id: str | None = None,
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
            analysis_id=analysis_id,
        )


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
    "MultiAgentDispositionPolicy",
    "PolicyDisposition",
    "SyntheticDispositionPolicy",
]
