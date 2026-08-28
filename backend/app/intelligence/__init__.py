"""Hardware-neutral monitoring intelligence boundaries."""

from backend.app.intelligence.fusion import AlignedFrame, FeatureEvidence, align_observations
from backend.app.intelligence.observations import (
    FeaturePurpose,
    FeatureValue,
    NormalizedObservation,
    QualityClass,
)
from backend.app.intelligence.quality import (
    quality_allows_detection,
    quality_allows_learning,
)

__all__ = [
    "AlignedFrame",
    "FeatureEvidence",
    "FeaturePurpose",
    "FeatureValue",
    "NormalizedObservation",
    "QualityClass",
    "align_observations",
    "quality_allows_detection",
    "quality_allows_learning",
]
