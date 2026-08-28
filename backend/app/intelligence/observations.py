"""Immutable, hardware-neutral normalized observation records."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from math import isfinite

from backend.app.domain._validation import (
    coerce_enum,
    require_aware_datetime,
    require_nonblank_text,
)


class QualityClass(StrEnum):
    GOOD = "good"
    LIMITED = "limited"
    UNUSABLE = "unusable"


class FeaturePurpose(StrEnum):
    MOVEMENT = "movement"
    POSTURE = "posture"
    RESPIRATION = "respiration"
    PRESENCE = "presence"


FeaturePrimitive = float | int | bool | str | None


def _require_utc(value: object, field: str) -> datetime:
    normalized = require_aware_datetime(value, field)
    if normalized.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must use UTC")
    return normalized


def _normalize_text_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise ValueError(f"{field} must be a tuple")
    normalized = tuple(require_nonblank_text(item, field) for item in value)
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field} must not contain duplicates")
    return tuple(sorted(normalized))


def _normalize_purposes(value: object) -> tuple[FeaturePurpose, ...]:
    if not isinstance(value, tuple):
        raise ValueError("purposes must be a tuple")
    normalized = tuple(
        coerce_enum(item, FeaturePurpose, "purposes") for item in value
    )
    if len(set(normalized)) != len(normalized):
        raise ValueError("purposes must not contain duplicates")
    return tuple(sorted(normalized, key=str))


def _normalize_feature_value(value: object) -> FeaturePrimitive:
    if value is None or type(value) is bool:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("feature value must be finite")
        return value
    if isinstance(value, str):
        return require_nonblank_text(value, "feature value")
    raise ValueError("feature value must be a float, int, bool, str, or None")


@dataclass(frozen=True)
class FeatureValue:
    name: str
    value: FeaturePrimitive
    unit: str
    quality_class: QualityClass
    quality_reasons: tuple[str, ...] = ()
    purposes: tuple[FeaturePurpose, ...] = ()
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", require_nonblank_text(self.name, "name"))
        object.__setattr__(self, "value", _normalize_feature_value(self.value))
        object.__setattr__(self, "unit", require_nonblank_text(self.unit, "unit"))
        quality_class = coerce_enum(
            self.quality_class, QualityClass, "quality_class"
        )
        object.__setattr__(self, "quality_class", quality_class)
        object.__setattr__(
            self,
            "quality_reasons",
            _normalize_text_tuple(self.quality_reasons, "quality_reasons"),
        )
        purposes = _normalize_purposes(self.purposes)
        object.__setattr__(self, "purposes", purposes)
        object.__setattr__(
            self,
            "schema_version",
            require_nonblank_text(self.schema_version, "schema_version"),
        )
        if quality_class == QualityClass.UNUSABLE:
            if self.value is not None:
                raise ValueError("unusable feature value must be None")
            return
        if self.value is None:
            raise ValueError("usable feature value must not be None")
        if quality_class == QualityClass.GOOD and not purposes:
            raise ValueError("good feature must declare at least one purpose")


@dataclass(frozen=True)
class NormalizedObservation:
    observation_id: str
    tenant_id: str
    room_id: str
    resident_id: str
    device_id: str
    source: str
    window_start: datetime
    window_end: datetime
    features: tuple[FeatureValue, ...]
    source_quality_class: QualityClass
    source_quality_reasons: tuple[str, ...]
    processor_version: str
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field in (
            "observation_id",
            "tenant_id",
            "room_id",
            "resident_id",
            "device_id",
            "source",
            "processor_version",
            "schema_version",
        ):
            object.__setattr__(
                self, field, require_nonblank_text(getattr(self, field), field)
            )
        window_start = _require_utc(self.window_start, "window_start")
        window_end = _require_utc(self.window_end, "window_end")
        if window_end <= window_start:
            raise ValueError("window_end must be after window_start")
        object.__setattr__(self, "window_start", window_start)
        object.__setattr__(self, "window_end", window_end)
        if not isinstance(self.features, tuple):
            raise ValueError("features must be a tuple")
        if not self.features:
            raise ValueError("features must not be empty")
        if any(not isinstance(feature, FeatureValue) for feature in self.features):
            raise ValueError("features must contain FeatureValue records")
        feature_keys = tuple((feature.name, feature.unit) for feature in self.features)
        if len(set(feature_keys)) != len(feature_keys):
            raise ValueError("features must not contain duplicate name and unit pairs")
        object.__setattr__(
            self,
            "features",
            tuple(sorted(self.features, key=lambda feature: (feature.name, feature.unit))),
        )
        object.__setattr__(
            self,
            "source_quality_class",
            coerce_enum(
                self.source_quality_class, QualityClass, "source_quality_class"
            ),
        )
        object.__setattr__(
            self,
            "source_quality_reasons",
            _normalize_text_tuple(
                self.source_quality_reasons, "source_quality_reasons"
            ),
        )


__all__ = [
    "FeaturePurpose",
    "FeatureValue",
    "NormalizedObservation",
    "QualityClass",
]
