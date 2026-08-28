"""Deterministic, synthetic fall-like fast path with no clinical authority."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from numbers import Real
from typing import ClassVar

from backend.app.domain._validation import (
    coerce_enum,
    require_nonblank_text,
    require_strict_bool,
)
from backend.app.intelligence.fusion import AlignedFrame, FeatureEvidence
from backend.app.intelligence.observations import (
    FeaturePurpose,
    QualityClass,
    _normalize_text_tuple,
    _require_utc,
)
from backend.app.intelligence.quality import quality_allows_detection


class FallLikeState(StrEnum):
    STABLE = "stable"
    RAPID_DESCENT = "rapid_descent"
    LOW_POSITION = "low_position"
    POST_TRANSITION = "post_transition"
    CONFIRMED_FALL_LIKE = "confirmed_fall_like"
    RECOVERED = "recovered"


def _require_finite_real(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a real number")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{field} must be finite")
    return normalized


@dataclass(frozen=True)
class SyntheticFallPolicy:
    """Versioned engineering fixture values; not a medical detector."""

    TEST_ONLY: ClassVar[bool] = True
    CLINICAL_AUTHORITY: ClassVar[bool] = False
    descent_velocity_below_mps: float = -0.8
    minimum_height_drop_m: float = 0.7
    maximum_post_transition_movement: float = 0.15
    max_confirmation_seconds: float = 5.0
    policy_version: str = "synthetic_fall_like_v1"
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field in (
            "descent_velocity_below_mps",
            "minimum_height_drop_m",
            "maximum_post_transition_movement",
            "max_confirmation_seconds",
        ):
            object.__setattr__(
                self,
                field,
                _require_finite_real(getattr(self, field), field),
            )
        if self.descent_velocity_below_mps >= 0.0:
            raise ValueError("descent_velocity_below_mps must be negative")
        if self.minimum_height_drop_m <= 0.0:
            raise ValueError("minimum_height_drop_m must be positive")
        if not 0.0 <= self.maximum_post_transition_movement <= 1.0:
            raise ValueError(
                "maximum_post_transition_movement must be between 0 and 1"
            )
        if self.max_confirmation_seconds <= 0.0:
            raise ValueError("max_confirmation_seconds must be positive")
        for field in ("policy_version", "schema_version"):
            object.__setattr__(
                self,
                field,
                require_nonblank_text(getattr(self, field), field),
            )
        canonical = (-0.8, 0.7, 0.15, 5.0)
        actual = (
            self.descent_velocity_below_mps,
            self.minimum_height_drop_m,
            self.maximum_post_transition_movement,
            self.max_confirmation_seconds,
        )
        if self.policy_version == "synthetic_fall_like_v1" and actual != canonical:
            raise ValueError("custom policy values require a distinct policy_version")

    @property
    def test_only(self) -> bool:
        return self.TEST_ONLY

    @property
    def clinical_authority(self) -> bool:
        return self.CLINICAL_AUTHORITY


@dataclass(frozen=True)
class FallLikeAssessment:
    state: FallLikeState
    urgent_triggered: bool
    confidence: str
    assessed_at: datetime
    transition_started_at: datetime | None
    reference_height_m: float | None
    evidence: tuple[str, ...]
    evidence_sources: tuple[str, ...]
    contradictions: tuple[str, ...]
    missing_sources: tuple[str, ...]
    limitations: tuple[str, ...]
    room_level_only: bool
    policy_version: str
    test_only: bool = True
    clinical_authority: bool = False
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", coerce_enum(self.state, FallLikeState, "state"))
        for field in (
            "urgent_triggered",
            "room_level_only",
            "test_only",
            "clinical_authority",
        ):
            object.__setattr__(
                self,
                field,
                require_strict_bool(getattr(self, field), field),
            )
        object.__setattr__(self, "assessed_at", _require_utc(self.assessed_at, "assessed_at"))
        if self.transition_started_at is not None:
            started = _require_utc(
                self.transition_started_at,
                "transition_started_at",
            )
            if started > self.assessed_at:
                raise ValueError("transition_started_at must not follow assessed_at")
            object.__setattr__(self, "transition_started_at", started)
        if self.reference_height_m is not None:
            object.__setattr__(
                self,
                "reference_height_m",
                _require_finite_real(self.reference_height_m, "reference_height_m"),
            )
        if self.confidence not in ("none", "lower", "high"):
            raise ValueError("confidence must be none, lower, or high")
        for field in (
            "evidence",
            "evidence_sources",
            "contradictions",
            "missing_sources",
            "limitations",
        ):
            normalized = _normalize_text_tuple(getattr(self, field), field)
            object.__setattr__(self, field, normalized)
        for field in ("policy_version", "schema_version"):
            object.__setattr__(
                self,
                field,
                require_nonblank_text(getattr(self, field), field),
            )
        if self.urgent_triggered != (
            self.state == FallLikeState.CONFIRMED_FALL_LIKE
        ):
            raise ValueError("urgent_triggered requires confirmed fall-like state")
        if self.urgent_triggered and self.confidence == "none":
            raise ValueError("confirmed fall-like assessment requires confidence")
        if self.test_only is not True or self.clinical_authority is not False:
            raise ValueError("fall-like assessments are test-only and non-clinical")


def _eligible(
    frame: AlignedFrame,
    *,
    source: str,
    name: str,
    unit: str,
    purpose: FeaturePurpose,
) -> tuple[FeatureEvidence, ...]:
    return tuple(
        item
        for item in frame.feature_evidence
        if item.source == source
        and item.feature.name == name
        and item.feature.unit == unit
        and item.feature.quality_class != QualityClass.UNUSABLE
        and quality_allows_detection(item.feature, purpose)
    )


def _single_numeric(
    frame: AlignedFrame,
    *,
    source: str,
    name: str,
    unit: str,
    purpose: FeaturePurpose,
) -> tuple[float | None, tuple[FeatureEvidence, ...]]:
    items = _eligible(
        frame,
        source=source,
        name=name,
        unit=unit,
        purpose=purpose,
    )
    numeric = tuple(
        item
        for item in items
        if not isinstance(item.feature.value, bool)
        and isinstance(item.feature.value, Real)
    )
    values = {float(item.feature.value) for item in numeric}
    if len(values) != 1:
        return None, numeric
    return values.pop(), numeric


def _position_evidence(
    frame: AlignedFrame,
    source: str,
) -> tuple[str | None, tuple[FeatureEvidence, ...]]:
    items = _eligible(
        frame,
        source=source,
        name="position_state",
        unit="categorical",
        purpose=FeaturePurpose.POSTURE,
    )
    values = {
        item.feature.value for item in items if isinstance(item.feature.value, str)
    }
    if len(values) != 1:
        return None, items
    return values.pop(), items


def _evidence_text(item: FeatureEvidence) -> str:
    return (
        f"{item.source}:{item.observation_id}:{item.feature.name}="
        f"{item.feature.value} {item.feature.unit}"
    )


def _combined(previous: tuple[str, ...], additions: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(previous) | set(additions)))


def advance_fall_like(
    previous: FallLikeAssessment | None,
    frame: AlignedFrame,
    *,
    policy: SyntheticFallPolicy | None = None,
    possible_multiple_people: bool = False,
) -> FallLikeAssessment:
    """Advance one injected aligned frame without anomaly or LLM dependencies."""

    if previous is not None and not isinstance(previous, FallLikeAssessment):
        raise ValueError("previous must be a FallLikeAssessment or None")
    if not isinstance(frame, AlignedFrame):
        raise ValueError("frame must be an AlignedFrame")
    if policy is None:
        policy = SyntheticFallPolicy()
    if not isinstance(policy, SyntheticFallPolicy):
        raise ValueError("policy must be a SyntheticFallPolicy")
    possible_multiple_people = require_strict_bool(
        possible_multiple_people,
        "possible_multiple_people",
    )
    if previous is not None and frame.window_start < previous.assessed_at:
        raise ValueError("frame must follow previous assessment")
    if previous is not None and previous.policy_version != policy.policy_version:
        raise ValueError("previous assessment must use the same policy version")

    height, height_items = _single_numeric(
        frame,
        source="radar",
        name="tracked_height",
        unit="m",
        purpose=FeaturePurpose.POSTURE,
    )
    velocity, velocity_items = _single_numeric(
        frame,
        source="radar",
        name="vertical_velocity",
        unit="m/s",
        purpose=FeaturePurpose.MOVEMENT,
    )
    movement, movement_items = _single_numeric(
        frame,
        source="radar",
        name="movement_energy",
        unit="normalized",
        purpose=FeaturePurpose.MOVEMENT,
    )
    radar_position, radar_position_items = _position_evidence(frame, "radar")
    thermal_position, thermal_position_items = _position_evidence(frame, "thermal")
    consumed_items = (
        height_items
        + velocity_items
        + movement_items
        + radar_position_items
        + thermal_position_items
    )
    current_evidence = tuple(_evidence_text(item) for item in consumed_items)
    current_sources = tuple(item.source for item in consumed_items)

    prior_evidence = previous.evidence if previous else ()
    prior_sources = previous.evidence_sources if previous else ()
    prior_contradictions = previous.contradictions if previous else ()
    prior_missing = previous.missing_sources if previous else ()
    prior_limitations = previous.limitations if previous else ()
    evidence = _combined(prior_evidence, current_evidence)
    sources = _combined(prior_sources, current_sources)
    contradictions = _combined(prior_contradictions, frame.contradictions)
    missing_sources = _combined(prior_missing, frame.sources_missing)
    limitations = prior_limitations

    state = previous.state if previous else FallLikeState.STABLE
    started = previous.transition_started_at if previous else None
    reference_height = previous.reference_height_m if previous else None
    if state in (FallLikeState.STABLE, FallLikeState.RECOVERED):
        if height is not None:
            reference_height = (
                height if reference_height is None else max(reference_height, height)
            )

    rapid_descent = (
        velocity is not None
        and height is not None
        and reference_height is not None
        and velocity < policy.descent_velocity_below_mps
        and reference_height - height >= policy.minimum_height_drop_m
    )
    position_contradiction = any(
        item.startswith("position_state:") for item in frame.contradictions
    )
    low_position = radar_position == "floor_like"
    explicit_non_low_position = radar_position is not None and not low_position
    elapsed_seconds = (
        (frame.window_end - started).total_seconds() if started is not None else 0.0
    )
    expired = started is not None and elapsed_seconds > policy.max_confirmation_seconds

    if state in (FallLikeState.STABLE, FallLikeState.RECOVERED):
        if rapid_descent:
            state = FallLikeState.RAPID_DESCENT
            started = frame.window_end
    elif state == FallLikeState.RAPID_DESCENT:
        if expired:
            state = FallLikeState.RECOVERED
            limitations = _combined(limitations, ("confirmation_window_expired",))
        elif position_contradiction:
            state = FallLikeState.RECOVERED
            limitations = _combined(
                limitations,
                ("contradictory_low_position_evidence",),
            )
        elif low_position:
            state = FallLikeState.LOW_POSITION
        elif explicit_non_low_position:
            state = FallLikeState.RECOVERED
    elif state == FallLikeState.LOW_POSITION:
        if expired:
            state = FallLikeState.RECOVERED
            limitations = _combined(limitations, ("confirmation_window_expired",))
        elif position_contradiction:
            state = FallLikeState.RECOVERED
            limitations = _combined(
                limitations,
                ("contradictory_low_position_evidence",),
            )
        elif explicit_non_low_position:
            state = FallLikeState.RECOVERED
        elif (
            low_position
            and movement is not None
            and movement <= policy.maximum_post_transition_movement
        ):
            state = FallLikeState.POST_TRANSITION
    elif state == FallLikeState.POST_TRANSITION:
        if expired:
            state = FallLikeState.RECOVERED
            limitations = _combined(limitations, ("confirmation_window_expired",))
        elif position_contradiction:
            state = FallLikeState.RECOVERED
            limitations = _combined(
                limitations,
                ("contradictory_low_position_evidence",),
            )
        elif (
            low_position
            and movement is not None
            and movement <= policy.maximum_post_transition_movement
        ):
            state = FallLikeState.CONFIRMED_FALL_LIKE
        elif explicit_non_low_position or (
            movement is not None
            and movement > policy.maximum_post_transition_movement
        ):
            state = FallLikeState.RECOVERED
    elif state == FallLikeState.CONFIRMED_FALL_LIKE:
        if explicit_non_low_position or (
            movement is not None
            and movement > policy.maximum_post_transition_movement
        ):
            state = FallLikeState.RECOVERED
        elif position_contradiction:
            limitations = _combined(
                limitations,
                ("contradictory_low_position_evidence",),
            )

    urgent_triggered = state == FallLikeState.CONFIRMED_FALL_LIKE
    confidence = "none"
    limitations = tuple(
        item
        for item in limitations
        if item != "thermal_corroboration_unavailable"
    )
    if urgent_triggered:
        if thermal_position == "floor_like":
            confidence = "high"
        elif thermal_position is None:
            confidence = "lower"
            limitations = _combined(
                limitations,
                ("thermal_corroboration_unavailable",),
            )
        else:
            confidence = "lower"
            limitation = (
                "contradictory_low_position_evidence"
                if position_contradiction
                else "thermal_not_corroborating"
            )
            limitations = _combined(limitations, (limitation,))

    if previous is None or previous.state == FallLikeState.STABLE:
        room_level_only = possible_multiple_people
    elif (
        previous.state == FallLikeState.RECOVERED
        and state == FallLikeState.RAPID_DESCENT
    ):
        room_level_only = possible_multiple_people
    else:
        room_level_only = previous.room_level_only or possible_multiple_people
    if room_level_only:
        limitations = _combined(limitations, ("resident_attribution_uncertain",))
    else:
        limitations = tuple(
            item
            for item in limitations
            if item != "resident_attribution_uncertain"
        )

    return FallLikeAssessment(
        state=state,
        urgent_triggered=urgent_triggered,
        confidence=confidence,
        assessed_at=frame.window_end,
        transition_started_at=started,
        reference_height_m=reference_height,
        evidence=evidence,
        evidence_sources=sources,
        contradictions=contradictions,
        missing_sources=missing_sources,
        limitations=limitations,
        room_level_only=room_level_only,
        policy_version=policy.policy_version,
        test_only=policy.test_only,
        clinical_authority=policy.clinical_authority,
        schema_version=policy.schema_version,
    )


__all__ = [
    "FallLikeAssessment",
    "FallLikeState",
    "SyntheticFallPolicy",
    "advance_fall_like",
]
