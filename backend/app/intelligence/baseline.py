"""Robust numerical baselines with explicit, contamination-resistant learning gates."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from math import ceil, isfinite
from numbers import Real
from statistics import median
from typing import ClassVar

from backend.app.domain._validation import (
    coerce_enum,
    require_nonblank_text,
    require_strict_bool,
)
from backend.app.domain.calibration import CalibrationProgress
from backend.app.domain.feedback import MemoryEntry
from backend.app.domain.monitoring import MonitoringSnapshot
from backend.app.intelligence.fusion import AlignedFrame, FeatureEvidence
from backend.app.intelligence.observations import FeaturePurpose, QualityClass


def _require_finite_real(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a real number")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{field} must be finite")
    return normalized


def _require_positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _normalize_reasons(reasons: object) -> tuple[str, ...]:
    if not isinstance(reasons, tuple):
        raise ValueError("reasons must be a tuple")
    normalized = tuple(require_nonblank_text(reason, "reason") for reason in reasons)
    return tuple(dict.fromkeys(normalized))


@dataclass(frozen=True)
class BaselinePolicy:
    """Versioned synthetic fixture policy, not a clinical threshold set."""

    TEST_ONLY: ClassVar[bool] = True
    minimum_samples: int = 5
    lower_quantile: float = 0.1
    upper_quantile: float = 0.9
    new_normal_clean_windows: int = 5
    policy_version: str = "synthetic_baseline_v1"
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "minimum_samples",
            _require_positive_int(self.minimum_samples, "minimum_samples"),
        )
        lower = _require_finite_real(self.lower_quantile, "lower_quantile")
        upper = _require_finite_real(self.upper_quantile, "upper_quantile")
        if not 0.0 < lower < upper <= 1.0:
            raise ValueError("quantiles must satisfy 0 < lower < upper <= 1")
        object.__setattr__(self, "lower_quantile", lower)
        object.__setattr__(self, "upper_quantile", upper)
        object.__setattr__(
            self,
            "new_normal_clean_windows",
            _require_positive_int(
                self.new_normal_clean_windows,
                "new_normal_clean_windows",
            ),
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

    @property
    def test_only(self) -> bool:
        return self.TEST_ONLY


@dataclass(frozen=True)
class FeatureBaseline:
    feature_name: str
    purpose: FeaturePurpose
    median: float
    mad: float
    iqr: float
    lower_quantile: float
    upper_quantile: float
    resolution_floor: float
    unit: str
    eligible_sample_count: int
    context_key: str
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "feature_name",
            require_nonblank_text(self.feature_name, "feature_name"),
        )
        object.__setattr__(
            self,
            "purpose",
            coerce_enum(self.purpose, FeaturePurpose, "purpose"),
        )
        for field in (
            "median",
            "mad",
            "iqr",
            "lower_quantile",
            "upper_quantile",
            "resolution_floor",
        ):
            object.__setattr__(self, field, _require_finite_real(getattr(self, field), field))
        if self.mad < 0.0 or self.iqr < 0.0:
            raise ValueError("MAD and IQR must not be negative")
        if self.resolution_floor <= 0.0:
            raise ValueError("resolution_floor must be positive")
        if not self.lower_quantile <= self.median <= self.upper_quantile:
            raise ValueError("quantile bounds must contain the median")
        object.__setattr__(self, "unit", require_nonblank_text(self.unit, "unit"))
        object.__setattr__(
            self,
            "eligible_sample_count",
            _require_positive_int(self.eligible_sample_count, "eligible_sample_count"),
        )
        object.__setattr__(
            self,
            "context_key",
            require_nonblank_text(self.context_key, "context_key"),
        )
        object.__setattr__(
            self,
            "schema_version",
            require_nonblank_text(self.schema_version, "schema_version"),
        )


@dataclass(frozen=True)
class BaselineSnapshot:
    baseline_id: str
    resident_id: str
    monitoring_setup_version: str
    features: tuple[FeatureBaseline, ...]
    policy_version: str
    prior_baseline_id: str | None = None
    adoption_candidate_id: str | None = None
    adoption_context_entry_id: str | None = None
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field in (
            "baseline_id",
            "resident_id",
            "monitoring_setup_version",
            "policy_version",
            "schema_version",
        ):
            object.__setattr__(
                self,
                field,
                require_nonblank_text(getattr(self, field), field),
            )
        for field in (
            "prior_baseline_id",
            "adoption_candidate_id",
            "adoption_context_entry_id",
        ):
            value = getattr(self, field)
            if value is not None:
                object.__setattr__(self, field, require_nonblank_text(value, field))
        if not isinstance(self.features, tuple):
            raise ValueError("features must be a tuple")
        if any(not isinstance(feature, FeatureBaseline) for feature in self.features):
            raise ValueError("features must contain FeatureBaseline records")
        keys = tuple((feature.feature_name, feature.context_key) for feature in self.features)
        if len(set(keys)) != len(keys):
            raise ValueError("features must not contain duplicate feature/context pairs")
        object.__setattr__(
            self,
            "features",
            tuple(sorted(self.features, key=lambda item: (item.feature_name, item.context_key))),
        )

    def feature(self, feature_name: str, context_key: str) -> FeatureBaseline:
        target = (
            require_nonblank_text(feature_name, "feature_name"),
            require_nonblank_text(context_key, "context_key"),
        )
        for feature in self.features:
            if (feature.feature_name, feature.context_key) == target:
                return feature
        raise KeyError(f"Unknown baseline feature/context: {target[0]} / {target[1]}")


@dataclass(frozen=True)
class LearningGuard:
    frame_id: str
    window_start: datetime
    window_end: datetime
    resident_id: str
    setup_version: str
    purpose: FeaturePurpose
    evidence: tuple[FeatureEvidence, ...]
    eligible: bool
    reasons: tuple[str, ...]
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "frame_id",
            require_nonblank_text(self.frame_id, "frame_id"),
        )
        for field in ("window_start", "window_end"):
            value = getattr(self, field)
            if not isinstance(value, datetime) or value.tzinfo is None:
                raise ValueError(f"{field} must be a timezone-aware datetime")
            if value.utcoffset() != timedelta(0):
                raise ValueError(f"{field} must use UTC")
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start")
        for field in ("resident_id", "setup_version"):
            object.__setattr__(
                self,
                field,
                require_nonblank_text(getattr(self, field), field),
            )
        object.__setattr__(
            self,
            "purpose",
            coerce_enum(self.purpose, FeaturePurpose, "purpose"),
        )
        if not isinstance(self.evidence, tuple) or any(
            not isinstance(item, FeatureEvidence) for item in self.evidence
        ):
            raise ValueError("evidence must be a tuple of FeatureEvidence records")
        eligible = require_strict_bool(self.eligible, "eligible")
        reasons = _normalize_reasons(self.reasons)
        if eligible == bool(reasons):
            raise ValueError("eligible decisions have no reasons; ineligible decisions require reasons")
        object.__setattr__(self, "eligible", eligible)
        object.__setattr__(self, "reasons", reasons)
        object.__setattr__(
            self,
            "schema_version",
            require_nonblank_text(self.schema_version, "schema_version"),
        )

    @property
    def window_key(self) -> str:
        return "|".join(
            (
                self.frame_id,
                self.window_start.isoformat(),
                self.window_end.isoformat(),
            )
        )


@dataclass(frozen=True)
class NewNormalCandidate:
    candidate_id: str
    resident_id: str
    feature_name: str
    unit: str
    purpose: FeaturePurpose
    context_key: str
    semantic_context_entry_id: str
    setup_version: str
    clean_window_values: tuple[float, ...] = ()
    clean_window_keys: tuple[str, ...] = ()
    last_ineligibility_reasons: tuple[str, ...] = ()
    adopted_baseline_id: str | None = None
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field in (
            "candidate_id",
            "resident_id",
            "feature_name",
            "unit",
            "context_key",
            "semantic_context_entry_id",
            "setup_version",
            "schema_version",
        ):
            object.__setattr__(
                self,
                field,
                require_nonblank_text(getattr(self, field), field),
            )
        object.__setattr__(
            self,
            "purpose",
            coerce_enum(self.purpose, FeaturePurpose, "purpose"),
        )
        if not isinstance(self.clean_window_values, tuple):
            raise ValueError("clean_window_values must be a tuple")
        object.__setattr__(
            self,
            "clean_window_values",
            tuple(
                _require_finite_real(value, "clean_window_values")
                for value in self.clean_window_values
            ),
        )
        if not isinstance(self.clean_window_keys, tuple):
            raise ValueError("clean_window_keys must be a tuple")
        keys = tuple(
            require_nonblank_text(key, "clean_window_keys")
            for key in self.clean_window_keys
        )
        if len(keys) != len(self.clean_window_values):
            raise ValueError("clean_window_keys must align with clean_window_values")
        if len(set(keys)) != len(keys):
            raise ValueError("clean_window_keys must identify separate windows")
        object.__setattr__(self, "clean_window_keys", keys)
        object.__setattr__(
            self,
            "last_ineligibility_reasons",
            _normalize_reasons(self.last_ineligibility_reasons),
        )
        if self.adopted_baseline_id is not None:
            object.__setattr__(
                self,
                "adopted_baseline_id",
                require_nonblank_text(self.adopted_baseline_id, "adopted_baseline_id"),
            )

    @property
    def clean_windows(self) -> int:
        return len(self.clean_window_values)


def _nearest_rank(values: tuple[float, ...], quantile: float) -> float:
    rank = max(1, ceil(quantile * len(values)))
    return values[rank - 1]


def _baseline_from_values(
    values: tuple[float, ...],
    *,
    feature_name: str,
    purpose: FeaturePurpose,
    unit: str,
    context_key: str,
    resolution_floor: float,
    policy: BaselinePolicy,
) -> FeatureBaseline:
    ordered = tuple(sorted(values))
    center = float(median(ordered))
    deviations = tuple(sorted(abs(value - center) for value in ordered))
    lower_quartile = _nearest_rank(ordered, 0.25)
    upper_quartile = _nearest_rank(ordered, 0.75)
    return FeatureBaseline(
        feature_name=feature_name,
        purpose=purpose,
        median=center,
        mad=float(median(deviations)),
        iqr=upper_quartile - lower_quartile,
        lower_quantile=_nearest_rank(ordered, policy.lower_quantile),
        upper_quantile=_nearest_rank(ordered, policy.upper_quantile),
        resolution_floor=resolution_floor,
        unit=unit,
        eligible_sample_count=len(ordered),
        context_key=context_key,
    )


def build_feature_baseline(
    windows: tuple[LearningGuard, ...],
    *,
    resident_id: str,
    setup_version: str,
    feature_name: str,
    purpose: FeaturePurpose,
    context_key: str,
    resolution_floor: float,
    policy: BaselinePolicy,
) -> FeatureBaseline:
    """Build robust facts from explicitly good, numeric feature evidence."""

    if not isinstance(windows, tuple) or any(
        not isinstance(window, LearningGuard) for window in windows
    ):
        raise ValueError("windows must be a tuple of LearningGuard records")
    if not isinstance(policy, BaselinePolicy):
        raise ValueError("policy must be a BaselinePolicy")
    name = require_nonblank_text(feature_name, "feature_name")
    resident = require_nonblank_text(resident_id, "resident_id")
    setup = require_nonblank_text(setup_version, "setup_version")
    selected_purpose = coerce_enum(purpose, FeaturePurpose, "purpose")
    context = require_nonblank_text(context_key, "context_key")
    floor = _require_finite_real(resolution_floor, "resolution_floor")
    if floor <= 0.0:
        raise ValueError("resolution_floor must be positive")
    if any(window.resident_id != resident for window in windows):
        raise ValueError("learning-window resident must match baseline resident")
    if any(window.setup_version != setup for window in windows):
        raise ValueError("learning-window setup must match baseline setup")
    if any(window.purpose != selected_purpose for window in windows):
        raise ValueError("learning-window purpose must match baseline purpose")
    eligible_windows: list[LearningGuard] = []
    seen_windows: set[str] = set()
    for window in windows:
        if not window.eligible or window.window_key in seen_windows:
            continue
        seen_windows.add(window.window_key)
        eligible_windows.append(window)
    if not eligible_windows:
        raise ValueError("baseline requires eligible learning windows")
    selected = tuple(
        item.feature
        for window in eligible_windows
        for item in window.evidence
        if item.feature.name == name
        and selected_purpose in item.feature.purposes
        and item.feature.quality_class == QualityClass.GOOD
        and not isinstance(item.feature.value, bool)
        and isinstance(item.feature.value, Real)
    )
    if len(selected) < policy.minimum_samples:
        raise ValueError("not enough eligible good numeric samples")
    units = {feature.unit for feature in selected}
    if len(units) != 1:
        raise ValueError("eligible samples must use one unit")
    values = tuple(float(feature.value) for feature in selected)
    return _baseline_from_values(
        values,
        feature_name=name,
        purpose=selected_purpose,
        unit=next(iter(units)),
        context_key=context,
        resolution_floor=floor,
        policy=policy,
    )


def robust_deviation(value: float, baseline: FeatureBaseline) -> float:
    """Return signed robust deviation without allowing a zero denominator."""

    if not isinstance(baseline, FeatureBaseline):
        raise ValueError("baseline must be a FeatureBaseline")
    observed = _require_finite_real(value, "value")
    denominator = max(
        1.4826 * baseline.mad,
        baseline.iqr / 1.349,
        baseline.resolution_floor,
    )
    return (observed - baseline.median) / denominator


def window_is_learning_eligible(
    frame: AlignedFrame,
    *,
    monitoring_snapshot: MonitoringSnapshot,
    resident_id: str,
    setup_version: str,
    purpose: FeaturePurpose,
    active_candidate: bool = False,
    unresolved_anomaly: bool = False,
    setup_change: bool = False,
    recovery_freeze: bool = False,
) -> LearningGuard:
    """Explain every reason a resident-specific numerical window cannot teach."""

    if not isinstance(frame, AlignedFrame):
        raise ValueError("frame must be an AlignedFrame")
    if not isinstance(monitoring_snapshot, MonitoringSnapshot):
        raise ValueError("monitoring_snapshot must be a MonitoringSnapshot")
    resident = require_nonblank_text(resident_id, "resident_id")
    setup = require_nonblank_text(setup_version, "setup_version")
    selected_purpose = coerce_enum(purpose, FeaturePurpose, "purpose")
    flags = {
        "active_candidate": require_strict_bool(active_candidate, "active_candidate"),
        "unresolved_anomaly": require_strict_bool(
            unresolved_anomaly,
            "unresolved_anomaly",
        ),
        "setup_change": require_strict_bool(setup_change, "setup_change"),
        "recovery_freeze": require_strict_bool(recovery_freeze, "recovery_freeze"),
    }
    reasons: list[str] = []
    if not monitoring_snapshot.baseline_learning_allowed:
        reasons.extend(reason.value for reason in monitoring_snapshot.reasons)
        if not monitoring_snapshot.reasons:
            reasons.append("monitoring_disallows_learning")

    relevant = tuple(
        item.feature
        for item in frame.feature_evidence
        if selected_purpose in item.feature.purposes
    )
    if not relevant:
        reasons.append("purpose_not_eligible")
    else:
        if any(feature.quality_class == QualityClass.LIMITED for feature in relevant):
            reasons.append("limited_quality")
        if any(feature.quality_class == QualityClass.UNUSABLE for feature in relevant):
            reasons.append("unusable_quality")
        if any(
            isinstance(feature.value, bool) or not isinstance(feature.value, Real)
            for feature in relevant
            if feature.quality_class != QualityClass.UNUSABLE
        ):
            reasons.append("non_numeric_value")
    reasons.extend(reason for reason, blocked in flags.items() if blocked)
    normalized = tuple(dict.fromkeys(reasons))
    return LearningGuard(
        frame_id=frame.frame_id,
        window_start=frame.window_start,
        window_end=frame.window_end,
        resident_id=resident,
        setup_version=setup,
        purpose=selected_purpose,
        evidence=frame.feature_evidence,
        eligible=not normalized,
        reasons=normalized,
    )


def _setup_change_affects_feature(
    candidate: NewNormalCandidate,
    progress: CalibrationProgress,
) -> bool:
    if candidate.setup_version == progress.setup_version:
        return False
    tracked_version = candidate.setup_version
    found_transition = False
    affected = False
    for action in progress.setup_change_history:
        if action.previous_setup_version != tracked_version:
            continue
        found_transition = True
        tracked_version = action.new_setup_version
        affected = affected or candidate.feature_name in action.affected_dimensions
        affected = affected or "all_physical_dimensions" in action.affected_dimensions
        if tracked_version == progress.setup_version:
            break
    return affected if found_transition and tracked_version == progress.setup_version else True


def _setup_transition_is_traced(
    previous_setup_version: str,
    progress: CalibrationProgress,
) -> bool:
    tracked_version = previous_setup_version
    for action in progress.setup_change_history:
        if action.previous_setup_version != tracked_version:
            continue
        tracked_version = action.new_setup_version
        if tracked_version == progress.setup_version:
            return True
    return False


def _window_value(
    candidate: NewNormalCandidate,
    window: LearningGuard,
) -> float:
    matching = tuple(
        item
        for item in window.evidence
        if item.feature.name == candidate.feature_name
        and item.feature.unit == candidate.unit
        and candidate.purpose in item.feature.purposes
        and item.feature.quality_class == QualityClass.GOOD
        and not isinstance(item.feature.value, bool)
        and isinstance(item.feature.value, Real)
    )
    if not matching:
        raise ValueError("clean window has no matching good numeric candidate evidence")
    values = tuple(float(item.feature.value) for item in matching)
    return float(median(values))


def advance_new_normal(
    candidate: NewNormalCandidate,
    *,
    baseline: BaselineSnapshot,
    expected_behavior: MemoryEntry,
    learning_guard: LearningGuard,
    calibration_progress: CalibrationProgress,
    new_baseline_id: str,
    policy: BaselinePolicy,
) -> tuple[NewNormalCandidate, BaselineSnapshot | None]:
    """Advance one clean window and publish only at the controlled threshold."""

    if not isinstance(candidate, NewNormalCandidate):
        raise ValueError("candidate must be a NewNormalCandidate")
    if not isinstance(baseline, BaselineSnapshot):
        raise ValueError("baseline must be a BaselineSnapshot")
    if not isinstance(expected_behavior, MemoryEntry):
        raise ValueError("expected_behavior must be a MemoryEntry")
    if not isinstance(learning_guard, LearningGuard):
        raise ValueError("learning_guard must be a LearningGuard")
    if not isinstance(calibration_progress, CalibrationProgress):
        raise ValueError("calibration_progress must be a CalibrationProgress")
    if not isinstance(policy, BaselinePolicy):
        raise ValueError("policy must be a BaselinePolicy")
    next_baseline_id = require_nonblank_text(new_baseline_id, "new_baseline_id")
    if next_baseline_id == baseline.baseline_id:
        raise ValueError("new_baseline_id must differ from the current baseline_id")
    if expected_behavior.status != "active" or expected_behavior.context_kind != "expected_new_behavior":
        raise ValueError("expected_behavior must be active expected-new-behavior context")
    if candidate.semantic_context_entry_id != expected_behavior.entry_id:
        raise ValueError("candidate must reference expected_behavior")
    if candidate.resident_id != baseline.resident_id:
        raise ValueError("candidate and baseline resident must match")
    if learning_guard.resident_id != candidate.resident_id:
        raise ValueError("learning-window resident must match candidate resident")
    if learning_guard.purpose != candidate.purpose:
        raise ValueError("learning-window purpose must match candidate purpose")
    pending_traced_setup = (
        candidate.setup_version == calibration_progress.setup_version
        and _setup_transition_is_traced(
            baseline.monitoring_setup_version,
            calibration_progress,
        )
    )
    if (
        candidate.setup_version != baseline.monitoring_setup_version
        and not pending_traced_setup
    ):
        raise ValueError("candidate setup must match the current baseline setup")
    if learning_guard.setup_version != calibration_progress.setup_version:
        raise ValueError("learning-window setup must match calibration setup")
    if candidate.adopted_baseline_id is not None:
        raise ValueError("candidate has already been adopted")

    prior_feature = baseline.feature(candidate.feature_name, candidate.context_key)
    if prior_feature.purpose != candidate.purpose:
        raise ValueError("candidate purpose must match baseline feature purpose")
    retained_features = any(
        (feature.feature_name, feature.context_key)
        != (candidate.feature_name, candidate.context_key)
        for feature in baseline.features
    )
    if retained_features and policy.policy_version != baseline.policy_version:
        raise ValueError(
            "policy_version must match while untouched baseline features are retained"
        )

    updated = candidate
    if candidate.setup_version != calibration_progress.setup_version:
        values = () if _setup_change_affects_feature(candidate, calibration_progress) else candidate.clean_window_values
        updated = replace(
            candidate,
            setup_version=calibration_progress.setup_version,
            clean_window_values=values,
            clean_window_keys=() if not values else candidate.clean_window_keys,
            last_ineligibility_reasons=(),
        )
    if learning_guard.setup_version != updated.setup_version:
        raise ValueError("learning-window setup must match candidate setup")

    if not learning_guard.eligible:
        return (
            replace(updated, last_ineligibility_reasons=learning_guard.reasons),
            None,
        )

    value = _window_value(updated, learning_guard)
    window_key = learning_guard.window_key
    if window_key in updated.clean_window_keys:
        return replace(updated, last_ineligibility_reasons=("duplicate_window",)), None
    updated = replace(
        updated,
        clean_window_values=updated.clean_window_values + (value,),
        clean_window_keys=updated.clean_window_keys + (window_key,),
        last_ineligibility_reasons=(),
    )
    if updated.clean_windows < policy.new_normal_clean_windows:
        return updated, None

    adopted_feature = _baseline_from_values(
        updated.clean_window_values,
        feature_name=updated.feature_name,
        purpose=updated.purpose,
        unit=updated.unit,
        context_key=updated.context_key,
        resolution_floor=prior_feature.resolution_floor,
        policy=policy,
    )
    features = tuple(
        adopted_feature
        if (feature.feature_name, feature.context_key)
        == (updated.feature_name, updated.context_key)
        else feature
        for feature in baseline.features
    )
    published = BaselineSnapshot(
        baseline_id=next_baseline_id,
        resident_id=baseline.resident_id,
        monitoring_setup_version=calibration_progress.setup_version,
        features=features,
        policy_version=policy.policy_version,
        prior_baseline_id=baseline.baseline_id,
        adoption_candidate_id=updated.candidate_id,
        adoption_context_entry_id=expected_behavior.entry_id,
    )
    return replace(updated, adopted_baseline_id=published.baseline_id), published


__all__ = [
    "BaselinePolicy",
    "BaselineSnapshot",
    "FeatureBaseline",
    "LearningGuard",
    "NewNormalCandidate",
    "advance_new_normal",
    "build_feature_baseline",
    "robust_deviation",
    "window_is_learning_eligible",
]
