"""Purpose-specific eligibility checks for normalized feature values."""

from backend.app.domain._validation import coerce_enum
from backend.app.intelligence.observations import (
    FeaturePurpose,
    FeatureValue,
    QualityClass,
)


def _require_feature(feature: object) -> FeatureValue:
    if not isinstance(feature, FeatureValue):
        raise ValueError("feature must be a FeatureValue")
    return feature


def quality_allows_detection(feature: FeatureValue, purpose: FeaturePurpose) -> bool:
    """Return whether one feature can support detection for one purpose."""

    feature = _require_feature(feature)
    purpose = coerce_enum(purpose, FeaturePurpose, "purpose")
    return (
        feature.quality_class in (QualityClass.GOOD, QualityClass.LIMITED)
        and purpose in feature.purposes
    )


def quality_allows_learning(feature: FeatureValue, purpose: FeaturePurpose) -> bool:
    """Return whether one feature can teach a numerical baseline purpose."""

    feature = _require_feature(feature)
    purpose = coerce_enum(purpose, FeaturePurpose, "purpose")
    return feature.quality_class == QualityClass.GOOD and purpose in feature.purposes


__all__ = ["quality_allows_detection", "quality_allows_learning"]
