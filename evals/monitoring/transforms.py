"""Deterministic, bounded transformations of synthetic aligned frames."""

from dataclasses import dataclass, replace
from datetime import timedelta
from math import isfinite
from random import Random

from backend.app.intelligence.fusion import AlignedFrame, align_observations
from backend.app.intelligence.observations import (
    FeatureValue,
    NormalizedObservation,
    QualityClass,
)


@dataclass(frozen=True)
class FrameTransformSpec:
    seed: int
    time_shift_seconds: int = 0
    numeric_jitter: float = 0.0
    drop_sources: tuple[str, ...] = ()
    downgrade_quality: bool = False
    duplicate_last_frame: bool = False
    reverse_input_order: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.seed, int):
            raise ValueError("seed must be an int")
        if not -86_400 <= self.time_shift_seconds <= 86_400:
            raise ValueError("time_shift_seconds must be within one day")
        if not isfinite(self.numeric_jitter) or not 0.0 <= self.numeric_jitter <= 0.25:
            raise ValueError("numeric_jitter must be between 0 and 0.25")
        if not isinstance(self.drop_sources, tuple):
            raise ValueError("drop_sources must be a tuple")


def _source_quality(features: tuple[FeatureValue, ...]) -> QualityClass:
    if all(feature.quality_class == QualityClass.UNUSABLE for feature in features):
        return QualityClass.UNUSABLE
    if any(feature.quality_class != QualityClass.GOOD for feature in features):
        return QualityClass.LIMITED
    return QualityClass.GOOD


def _transform_feature(
    feature: FeatureValue,
    *,
    random: Random,
    numeric_jitter: float,
    downgrade_quality: bool,
) -> FeatureValue:
    value = feature.value
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value is not None:
        scale = max(abs(float(value)), 1.0)
        value = float(value) + random.uniform(-numeric_jitter, numeric_jitter) * scale
    quality = feature.quality_class
    reasons = feature.quality_reasons
    if downgrade_quality and quality == QualityClass.GOOD:
        quality = QualityClass.LIMITED
        reasons = tuple(sorted((*reasons, "synthetic_quality_boundary")))
    return replace(feature, value=value, quality_class=quality, quality_reasons=reasons)


def _transform_frame(
    frame: AlignedFrame,
    spec: FrameTransformSpec,
    *,
    random: Random,
) -> AlignedFrame:
    dropped = set(spec.drop_sources)
    retained = tuple(item for item in frame.feature_evidence if item.source not in dropped)
    if not retained:
        raise ValueError("frame transform cannot remove every source")
    shift = timedelta(seconds=spec.time_shift_seconds)
    groups: dict[tuple[str, str], list[FeatureValue]] = {}
    for item in retained:
        groups.setdefault((item.source, item.observation_id), []).append(
            _transform_feature(
                item.feature,
                random=random,
                numeric_jitter=spec.numeric_jitter,
                downgrade_quality=spec.downgrade_quality,
            )
        )
    observations = tuple(
        NormalizedObservation(
            observation_id=observation_id,
            tenant_id=frame.tenant_id,
            room_id=frame.room_id,
            resident_id=frame.resident_id,
            device_id="device_synthetic_transform",
            source=source,
            window_start=frame.window_start + shift,
            window_end=frame.window_end + shift,
            features=tuple(features),
            source_quality_class=_source_quality(tuple(features)),
            source_quality_reasons=tuple(
                sorted({reason for feature in features for reason in feature.quality_reasons})
            ),
            processor_version="synthetic_transform_v1",
        )
        for (source, observation_id), features in sorted(groups.items())
    )
    expected_sources = tuple(sorted(set(frame.sources_present) | set(frame.sources_missing)))
    return align_observations(
        observations,
        frame_id=frame.frame_id,
        window_start=frame.window_start + shift,
        window_end=frame.window_end + shift,
        expected_sources=expected_sources,
    )


def transform_frames(
    frames: tuple[AlignedFrame, ...],
    spec: FrameTransformSpec,
) -> tuple[AlignedFrame, ...]:
    if not isinstance(frames, tuple) or not frames:
        raise ValueError("frames must be a non-empty tuple")
    random = Random(spec.seed)
    transformed = tuple(_transform_frame(frame, spec, random=random) for frame in frames)
    if spec.duplicate_last_frame:
        transformed = (*transformed, transformed[-1])
    if spec.reverse_input_order:
        transformed = tuple(reversed(transformed))
    return transformed


__all__ = ["FrameTransformSpec", "transform_frames"]
