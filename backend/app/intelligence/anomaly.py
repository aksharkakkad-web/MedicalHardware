"""Transparent numerical anomaly gating with immutable episode revisions."""

from dataclasses import dataclass, replace
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
from backend.app.intelligence.baseline import (
    BaselineSnapshot,
    FeatureBaseline,
    robust_deviation,
)
from backend.app.intelligence.fusion import AlignedFrame
from backend.app.intelligence.observations import QualityClass, _require_utc


class AnomalyState(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    RECOVERING = "recovering"
    CLOSED = "closed"


def _require_finite_real(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a real number")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{field} must be finite")
    return normalized


def _require_nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def _require_positive_int(value: object, field: str) -> int:
    normalized = _require_nonnegative_int(value, field)
    if normalized == 0:
        raise ValueError(f"{field} must be a positive integer")
    return normalized


def _normalize_texts(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ValueError(f"{field} must be a tuple")
    normalized = tuple(require_nonblank_text(item, field) for item in value)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field} must not contain duplicates")
    return normalized


@dataclass(frozen=True)
class SyntheticAnomalyPolicy:
    """Synthetic engineering policy; it carries no clinical authority."""

    TEST_ONLY: ClassVar[bool] = True
    start_abs_z: float = 3.0
    end_abs_z: float = 1.5
    activation_frames: int = 3
    recovery_frames: int = 3
    missing_grace_frames: int = 2
    policy_version: str = "synthetic_anomaly_v1"
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        start = _require_finite_real(self.start_abs_z, "start_abs_z")
        end = _require_finite_real(self.end_abs_z, "end_abs_z")
        if not 0.0 <= end < start:
            raise ValueError("thresholds must satisfy 0 <= end_abs_z < start_abs_z")
        object.__setattr__(self, "start_abs_z", start)
        object.__setattr__(self, "end_abs_z", end)
        for field in ("activation_frames", "recovery_frames"):
            object.__setattr__(
                self,
                field,
                _require_positive_int(getattr(self, field), field),
            )
        object.__setattr__(
            self,
            "missing_grace_frames",
            _require_nonnegative_int(
                self.missing_grace_frames,
                "missing_grace_frames",
            ),
        )
        for field in ("policy_version", "schema_version"):
            object.__setattr__(
                self,
                field,
                require_nonblank_text(getattr(self, field), field),
            )

    @property
    def test_only(self) -> bool:
        return self.TEST_ONLY


@dataclass(frozen=True)
class FeatureDeviation:
    feature_name: str
    source: str
    observation_id: str
    value: float
    unit: str
    quality_class: QualityClass
    quality_reasons: tuple[str, ...]
    baseline_median: float
    baseline_mad: float
    baseline_iqr: float
    baseline_lower_quantile: float
    baseline_upper_quantile: float
    baseline_resolution_floor: float
    baseline_context_key: str
    robust_z: float
    direction: str
    trajectory: str
    persistence_frames: int
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field in (
            "feature_name",
            "source",
            "observation_id",
            "unit",
            "baseline_context_key",
            "direction",
            "trajectory",
            "schema_version",
        ):
            object.__setattr__(
                self,
                field,
                require_nonblank_text(getattr(self, field), field),
            )
        for field in (
            "value",
            "baseline_median",
            "baseline_mad",
            "baseline_iqr",
            "baseline_lower_quantile",
            "baseline_upper_quantile",
            "baseline_resolution_floor",
            "robust_z",
        ):
            object.__setattr__(
                self,
                field,
                _require_finite_real(getattr(self, field), field),
            )
        quality = coerce_enum(self.quality_class, QualityClass, "quality_class")
        if quality == QualityClass.UNUSABLE:
            raise ValueError("unusable evidence cannot produce a numerical deviation")
        object.__setattr__(self, "quality_class", quality)
        object.__setattr__(
            self,
            "quality_reasons",
            _normalize_texts(self.quality_reasons, "quality_reasons"),
        )
        if self.direction not in ("up", "down", "unchanged"):
            raise ValueError("direction must be up, down, or unchanged")
        object.__setattr__(
            self,
            "persistence_frames",
            _require_nonnegative_int(self.persistence_frames, "persistence_frames"),
        )


@dataclass(frozen=True)
class AnomalyEpisode:
    anomaly_id: str
    state: AnomalyState
    candidate_started_at: datetime
    current_time: datetime
    activation_count: int
    recovery_count: int
    consecutive_missing_frames: int
    related_frame_count: int
    packet_revision: int
    initiating_features: tuple[str, ...]
    policy_version: str
    last_frame_id: str
    activated_at: datetime | None = None
    recovering_started_at: datetime | None = None
    closed_at: datetime | None = None
    recurrence_of: str | None = None
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field in ("anomaly_id", "policy_version", "last_frame_id", "schema_version"):
            object.__setattr__(
                self,
                field,
                require_nonblank_text(getattr(self, field), field),
            )
        object.__setattr__(self, "state", coerce_enum(self.state, AnomalyState, "state"))
        candidate_started_at = _require_utc(
            self.candidate_started_at,
            "candidate_started_at",
        )
        current_time = _require_utc(self.current_time, "current_time")
        if current_time < candidate_started_at:
            raise ValueError("current_time must not precede candidate_started_at")
        object.__setattr__(self, "candidate_started_at", candidate_started_at)
        object.__setattr__(self, "current_time", current_time)
        for field in ("activated_at", "recovering_started_at", "closed_at"):
            value = getattr(self, field)
            if value is not None:
                normalized = _require_utc(value, field)
                if not candidate_started_at <= normalized <= current_time:
                    raise ValueError(f"{field} must fall inside the episode interval")
                object.__setattr__(self, field, normalized)
        for field in (
            "activation_count",
            "recovery_count",
            "consecutive_missing_frames",
            "related_frame_count",
            "packet_revision",
        ):
            object.__setattr__(
                self,
                field,
                _require_nonnegative_int(getattr(self, field), field),
            )
        initiating = _normalize_texts(self.initiating_features, "initiating_features")
        if not initiating:
            raise ValueError("initiating_features must not be empty")
        object.__setattr__(self, "initiating_features", tuple(sorted(initiating)))
        if self.recurrence_of is not None:
            recurrence = require_nonblank_text(self.recurrence_of, "recurrence_of")
            if recurrence == self.anomaly_id:
                raise ValueError("recurrence_of must identify a prior anomaly")
            object.__setattr__(self, "recurrence_of", recurrence)
        if self.state == AnomalyState.CANDIDATE:
            if self.activated_at is not None or self.packet_revision != 0:
                raise ValueError("candidate episodes cannot have activation evidence")
        elif self.activated_at is None:
            raise ValueError("active, recovering, and closed episodes require activated_at")
        if self.state == AnomalyState.CLOSED:
            if self.closed_at is None:
                raise ValueError("closed episodes require closed_at")
        elif self.closed_at is not None:
            raise ValueError("only closed episodes may have closed_at")


@dataclass(frozen=True)
class AnomalyUpdate:
    episode: AnomalyEpisode | None
    deviations: tuple[FeatureDeviation, ...]
    frame_id: str
    window_start: datetime
    window_end: datetime
    baseline_id: str
    baseline_policy_version: str
    monitoring_setup_version: str
    context_key: str
    policy_version: str
    evidence_limited: bool
    limitations: tuple[str, ...]
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if self.episode is not None and not isinstance(self.episode, AnomalyEpisode):
            raise ValueError("episode must be an AnomalyEpisode or None")
        if not isinstance(self.deviations, tuple) or any(
            not isinstance(item, FeatureDeviation) for item in self.deviations
        ):
            raise ValueError("deviations must be a tuple of FeatureDeviation records")
        object.__setattr__(
            self,
            "deviations",
            tuple(
                sorted(
                    self.deviations,
                    key=lambda item: (
                        item.feature_name,
                        item.source,
                        item.observation_id,
                    ),
                )
            ),
        )
        for field in (
            "frame_id",
            "baseline_id",
            "baseline_policy_version",
            "monitoring_setup_version",
            "context_key",
            "policy_version",
            "schema_version",
        ):
            object.__setattr__(
                self,
                field,
                require_nonblank_text(getattr(self, field), field),
            )
        window_start = _require_utc(self.window_start, "window_start")
        window_end = _require_utc(self.window_end, "window_end")
        if window_end <= window_start:
            raise ValueError("window_end must be after window_start")
        object.__setattr__(self, "window_start", window_start)
        object.__setattr__(self, "window_end", window_end)
        object.__setattr__(
            self,
            "evidence_limited",
            require_strict_bool(self.evidence_limited, "evidence_limited"),
        )
        object.__setattr__(
            self,
            "limitations",
            _normalize_texts(self.limitations, "limitations"),
        )

    @property
    def overall_strength(self) -> float:
        return max((abs(item.robust_z) for item in self.deviations), default=0.0)


def _baseline_for_evidence(
    baseline: BaselineSnapshot,
    feature_name: str,
    unit: str,
    context_key: str,
) -> FeatureBaseline | None:
    try:
        feature = baseline.feature(feature_name, context_key)
    except KeyError:
        return None
    return feature if feature.unit == unit else None


def _frame_deviations(
    frame: AlignedFrame,
    baseline: BaselineSnapshot,
    context_key: str,
    policy: SyntheticAnomalyPolicy,
    *,
    continuing: bool,
) -> tuple[FeatureDeviation, ...]:
    deviations: list[FeatureDeviation] = []
    for evidence in frame.feature_evidence:
        value = evidence.feature.value
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
            or evidence.feature.quality_class == QualityClass.UNUSABLE
        ):
            continue
        feature_baseline = _baseline_for_evidence(
            baseline,
            evidence.feature.name,
            evidence.feature.unit,
            context_key,
        )
        if feature_baseline is None or feature_baseline.purpose not in evidence.feature.purposes:
            continue
        observed = float(value)
        deviation = robust_deviation(observed, feature_baseline)
        direction = "up" if deviation > 0.0 else "down" if deviation < 0.0 else "unchanged"
        if abs(deviation) >= policy.start_abs_z:
            trajectory = "sustained" if continuing else "initiating"
        elif abs(deviation) < policy.end_abs_z:
            trajectory = "returning_toward_baseline"
        else:
            trajectory = "changing"
        deviations.append(
            FeatureDeviation(
                feature_name=evidence.feature.name,
                source=evidence.source,
                observation_id=evidence.observation_id,
                value=observed,
                unit=evidence.feature.unit,
                quality_class=evidence.feature.quality_class,
                quality_reasons=evidence.feature.quality_reasons,
                baseline_median=feature_baseline.median,
                baseline_mad=feature_baseline.mad,
                baseline_iqr=feature_baseline.iqr,
                baseline_lower_quantile=feature_baseline.lower_quantile,
                baseline_upper_quantile=feature_baseline.upper_quantile,
                baseline_resolution_floor=feature_baseline.resolution_floor,
                baseline_context_key=feature_baseline.context_key,
                robust_z=deviation,
                direction=direction,
                trajectory=trajectory,
                persistence_frames=0,
            )
        )
    return tuple(deviations)


def _update_record(
    episode: AnomalyEpisode | None,
    deviations: tuple[FeatureDeviation, ...],
    *,
    frame: AlignedFrame,
    baseline: BaselineSnapshot,
    context_key: str,
    policy: SyntheticAnomalyPolicy,
    evidence_limited: bool,
    limitations: tuple[str, ...],
) -> AnomalyUpdate:
    persistence = episode.related_frame_count if episode is not None else 0
    return AnomalyUpdate(
        episode=episode,
        deviations=tuple(
            replace(item, persistence_frames=persistence) for item in deviations
        ),
        frame_id=frame.frame_id,
        window_start=frame.window_start,
        window_end=frame.window_end,
        baseline_id=baseline.baseline_id,
        baseline_policy_version=baseline.policy_version,
        monitoring_setup_version=baseline.monitoring_setup_version,
        context_key=context_key,
        policy_version=policy.policy_version,
        evidence_limited=evidence_limited,
        limitations=limitations,
    )


def advance_episode(
    episode: AnomalyEpisode | None,
    *,
    frame: AlignedFrame,
    baseline: BaselineSnapshot,
    context_key: str,
    anomaly_id: str,
    policy: SyntheticAnomalyPolicy,
) -> AnomalyUpdate:
    """Advance one numerical frame; caregiver event state is intentionally absent."""

    if episode is not None and not isinstance(episode, AnomalyEpisode):
        raise ValueError("episode must be an AnomalyEpisode or None")
    if not isinstance(frame, AlignedFrame):
        raise ValueError("frame must be an AlignedFrame")
    if not isinstance(baseline, BaselineSnapshot):
        raise ValueError("baseline must be a BaselineSnapshot")
    if not isinstance(policy, SyntheticAnomalyPolicy):
        raise ValueError("policy must be a SyntheticAnomalyPolicy")
    selected_id = require_nonblank_text(anomaly_id, "anomaly_id")
    context = require_nonblank_text(context_key, "context_key")
    if episode is not None:
        if frame.window_start < episode.current_time:
            raise ValueError("frame must not precede the episode's current_time")
        if episode.policy_version != policy.policy_version:
            raise ValueError("episode and policy versions must match")
        if episode.state != AnomalyState.CLOSED and selected_id != episode.anomaly_id:
            raise ValueError("anomaly_id must match the open episode")

    deviations = _frame_deviations(
        frame,
        baseline,
        context,
        policy,
        continuing=episode is not None,
    )
    crossing = tuple(
        item for item in deviations if abs(item.robust_z) >= policy.start_abs_z
    )

    if episode is None or episode.state == AnomalyState.CLOSED:
        if not crossing:
            return _update_record(
                episode,
                deviations,
                frame=frame,
                baseline=baseline,
                context_key=context,
                policy=policy,
                evidence_limited=False,
                limitations=(),
            )
        recurrence_of = episode.anomaly_id if episode is not None else None
        if recurrence_of == selected_id:
            raise ValueError("a recurrence requires a new anomaly_id")
        created = AnomalyEpisode(
            anomaly_id=selected_id,
            state=AnomalyState.CANDIDATE,
            candidate_started_at=frame.window_start,
            current_time=frame.window_end,
            activation_count=1,
            recovery_count=0,
            consecutive_missing_frames=0,
            related_frame_count=1,
            packet_revision=0,
            initiating_features=tuple(
                sorted({item.feature_name for item in crossing})
            ),
            policy_version=policy.policy_version,
            last_frame_id=frame.frame_id,
            recurrence_of=recurrence_of,
        )
        return _update_record(
            created,
            deviations,
            frame=frame,
            baseline=baseline,
            context_key=context,
            policy=policy,
            evidence_limited=False,
            limitations=(),
        )

    related = tuple(
        item for item in deviations if item.feature_name in episode.initiating_features
    )
    related_names = {item.feature_name for item in related}
    all_initiating_good = all(
        any(
            item.feature_name == feature_name
            and item.quality_class == QualityClass.GOOD
            for item in related
        )
        for feature_name in episode.initiating_features
    )
    missing = not related
    limited = bool(related) and not all_initiating_good
    missing_count = episode.consecutive_missing_frames + 1 if missing else 0
    limitations: list[str] = []
    if limited:
        limitations.append("limited_quality")
    if missing_count > policy.missing_grace_frames:
        limitations.append("missing_evidence_beyond_grace")

    related_frame_count = episode.related_frame_count + 1
    initiating_features = tuple(
        sorted(set(episode.initiating_features) | {item.feature_name for item in crossing})
    )
    next_episode: AnomalyEpisode

    if episode.state == AnomalyState.CANDIDATE:
        activation_count = episode.activation_count + 1 if crossing else 0
        activated = activation_count >= policy.activation_frames
        next_episode = replace(
            episode,
            state=AnomalyState.ACTIVE if activated else AnomalyState.CANDIDATE,
            current_time=frame.window_end,
            activation_count=activation_count,
            consecutive_missing_frames=missing_count,
            related_frame_count=related_frame_count,
            packet_revision=1 if activated else 0,
            initiating_features=initiating_features,
            last_frame_id=frame.frame_id,
            activated_at=frame.window_end if activated else None,
        )
    else:
        above_end = bool(crossing) or any(
            abs(item.robust_z) >= policy.end_abs_z for item in related
        )
        inside_end = (
            bool(related_names)
            and all_initiating_good
            and not above_end
        )
        next_revision = episode.packet_revision + 1
        if episode.state == AnomalyState.ACTIVE:
            next_episode = replace(
                episode,
                state=AnomalyState.RECOVERING if inside_end else AnomalyState.ACTIVE,
                current_time=frame.window_end,
                recovery_count=1 if inside_end else 0,
                consecutive_missing_frames=missing_count,
                related_frame_count=related_frame_count,
                packet_revision=next_revision,
                initiating_features=initiating_features,
                last_frame_id=frame.frame_id,
                recovering_started_at=frame.window_start if inside_end else None,
            )
        else:
            recovery_count = episode.recovery_count + 1 if inside_end else episode.recovery_count
            if above_end:
                next_episode = replace(
                    episode,
                    state=AnomalyState.ACTIVE,
                    current_time=frame.window_end,
                    recovery_count=0,
                    consecutive_missing_frames=missing_count,
                    related_frame_count=related_frame_count,
                    packet_revision=next_revision,
                    initiating_features=initiating_features,
                    last_frame_id=frame.frame_id,
                    recovering_started_at=None,
                )
            elif inside_end and recovery_count >= policy.recovery_frames:
                next_episode = replace(
                    episode,
                    state=AnomalyState.CLOSED,
                    current_time=frame.window_end,
                    recovery_count=recovery_count,
                    consecutive_missing_frames=0,
                    related_frame_count=related_frame_count,
                    packet_revision=next_revision,
                    last_frame_id=frame.frame_id,
                    closed_at=frame.window_end,
                )
            else:
                next_episode = replace(
                    episode,
                    current_time=frame.window_end,
                    recovery_count=recovery_count,
                    consecutive_missing_frames=missing_count,
                    related_frame_count=related_frame_count,
                    packet_revision=next_revision,
                    initiating_features=initiating_features,
                    last_frame_id=frame.frame_id,
                )

    return _update_record(
        next_episode,
        deviations,
        frame=frame,
        baseline=baseline,
        context_key=context,
        policy=policy,
        evidence_limited=bool(limitations),
        limitations=tuple(limitations),
    )


__all__ = [
    "AnomalyEpisode",
    "AnomalyState",
    "AnomalyUpdate",
    "FeatureDeviation",
    "SyntheticAnomalyPolicy",
    "advance_episode",
]
